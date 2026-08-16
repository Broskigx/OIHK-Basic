"""Browser-facing hardening of the loopback API.

These exercise the middleware stack over real HTTP rather than the routes
underneath it, because the properties being asserted are properties of the
stack: a request must be judged before it reaches routing, body parsing or the
database. A test that called the endpoint function directly would pass whether
or not the guard is installed.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.middleware.origin_guard import host_is_allowed, origin_is_allowed

from .conftest import reset_rate_limiter

LOOPBACK = "http://127.0.0.1:8000"
# The default development CORS allowlist, i.e. the Vite dev server.
TRUSTED_ORIGIN = "http://127.0.0.1:5173"
HOSTILE_ORIGIN = "https://evil.example.com"


def _settings(**overrides) -> Settings:
    base = {
        "server_bind_host": "127.0.0.1",
        "allowed_hosts": "",
        "cors_origins": "http://127.0.0.1:5173,http://localhost:5173",
    }
    base.update(overrides)
    return Settings(**base)


async def _request(method: str, path: str, **kwargs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=LOOPBACK) as client:
        return await client.request(method, path, **kwargs)


# --- Host allowlist (DNS rebinding) ------------------------------------------


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1:8000", "127.0.0.1", "localhost:5173", "localhost", "[::1]:8000", "[::1]"],
)
def test_loopback_authorities_are_accepted(host: str) -> None:
    assert host_is_allowed(host, _settings()) is True


@pytest.mark.parametrize(
    "host",
    [
        "evil.example.com",
        "evil.example.com:8000",
        # The attacker-controlled name that a rebinding answer points at
        # loopback: the address is ours, the name never is.
        "rebind.attacker.test:8000",
        # A loopback name as a *prefix* or *suffix* of someone else's domain
        # must not be mistaken for the real thing.
        "127.0.0.1.evil.example.com",
        "localhost.evil.example.com",
        "notlocalhost",
    ],
)
def test_foreign_authorities_are_rejected(host: str) -> None:
    assert host_is_allowed(host, _settings()) is False


def test_absent_host_header_is_allowed() -> None:
    """HTTP/1.0 and direct ASGI callers omit Host; a browser never does."""
    assert host_is_allowed("", _settings()) is True


def test_explicit_allowlist_overrides_the_loopback_default() -> None:
    settings = _settings(allowed_hosts="oihk.internal,10.0.0.5:8000")
    assert host_is_allowed("oihk.internal", settings) is True
    # An entry without a port accepts any port, since the desktop backend picks
    # a free one per launch.
    assert host_is_allowed("oihk.internal:9000", settings) is True
    assert host_is_allowed("10.0.0.5:8000", settings) is True
    assert host_is_allowed("evil.example.com", settings) is False
    # The explicit list replaces the default rather than extending it.
    assert host_is_allowed("127.0.0.1:8000", settings) is False


def test_non_loopback_bind_without_an_allowlist_defers() -> None:
    """A proxied deployment rewrites Host to a name only the operator knows."""
    settings = _settings(server_bind_host="0.0.0.0")
    assert host_is_allowed("oihk.example.com", settings) is True


@pytest.mark.asyncio
async def test_rebound_host_is_refused_over_http() -> None:
    response = await _request("GET", "/health", headers={"Host": "rebind.attacker.test"})
    assert response.status_code == 400
    assert response.json()["code"] == "host_not_allowed"


@pytest.mark.asyncio
async def test_loopback_host_still_reaches_the_route() -> None:
    response = await _request("GET", "/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- Origin guard (cross-origin state change) --------------------------------


def test_origin_allowlist_matches_the_cors_configuration() -> None:
    settings = _settings()
    assert origin_is_allowed(TRUSTED_ORIGIN, settings) is True
    assert origin_is_allowed("http://127.0.0.1:5173/", settings) is True
    assert origin_is_allowed(HOSTILE_ORIGIN, settings) is False
    # A trusted origin's name inside a hostile one must not match.
    assert origin_is_allowed("http://127.0.0.1:5173.evil.example.com", settings) is False


def test_packaged_desktop_origins_are_allowed() -> None:
    settings = _settings(cors_origins="http://tauri.localhost,tauri://localhost")
    assert origin_is_allowed("http://tauri.localhost", settings) is True
    assert origin_is_allowed("tauri://localhost", settings) is True
    assert origin_is_allowed(HOSTILE_ORIGIN, settings) is False


@pytest.mark.asyncio
async def test_cross_origin_multipart_upload_is_refused() -> None:
    """The concrete attack: multipart is CORS-safelisted, so it is not preflighted.

    A hostile page can submit this form; CORS only withholds the response from
    it. The write is what matters for evidence integrity, so it has to be
    stopped before the route parses a body.
    """
    response = await _request(
        "POST",
        "/evidence",
        headers={"Origin": HOSTILE_ORIGIN},
        files={"file": ("planted.txt", b"planted", "text/plain")},
        data={"case_id": "any-case"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "origin_not_allowed"


@pytest.mark.asyncio
async def test_cross_origin_state_change_is_refused_before_routing() -> None:
    response = await _request("POST", "/__guard_probe__", headers={"Origin": HOSTILE_ORIGIN})
    assert response.status_code == 403
    assert response.json()["code"] == "origin_not_allowed"


@pytest.mark.asyncio
async def test_trusted_origin_passes_the_guard() -> None:
    """A trusted origin reaches routing, which is what 404 proves here."""
    response = await _request("POST", "/__guard_probe__", headers={"Origin": TRUSTED_ORIGIN})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_trusted_origin_is_not_rejected_by_same_site_fetch_metadata() -> None:
    """The Vite desktop UI is same-site with its random-port loopback API.

    Once the explicit Origin is allowlisted, Sec-Fetch-Site is supporting
    metadata rather than a second independent rejection rule.
    """
    response = await _request(
        "POST",
        "/__guard_probe__",
        headers={"Origin": TRUSTED_ORIGIN, "Sec-Fetch-Site": "same-site"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_request_without_an_origin_passes_the_guard() -> None:
    """The Tauri core and the System Link smoke runner are not browsers."""
    response = await _request("POST", "/__guard_probe__")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cross_site_fetch_metadata_is_refused_without_an_origin() -> None:
    response = await _request(
        "POST", "/__guard_probe__", headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "origin_not_allowed"


@pytest.mark.asyncio
async def test_same_origin_fetch_metadata_passes() -> None:
    response = await _request(
        "POST", "/__guard_probe__", headers={"Sec-Fetch-Site": "same-origin"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_safe_methods_are_not_origin_checked() -> None:
    """Reads are bounded by the Host allowlist, not by Origin."""
    response = await _request("GET", "/health", headers={"Origin": HOSTILE_ORIGIN})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_module_api_is_exempt_from_browser_rules() -> None:
    """System Link calls carry a signed envelope and arrive from a sibling app."""
    response = await _request(
        "POST",
        "/system-link/module-api/v1/__guard_probe__",
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code != 403


# --- Baseline response headers -----------------------------------------------


@pytest.mark.asyncio
async def test_baseline_security_headers_are_present() -> None:
    response = await _request("GET", "/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "camera=()" in response.headers["permissions-policy"]


@pytest.mark.asyncio
async def test_security_headers_reach_rejected_requests_too() -> None:
    response = await _request("GET", "/health", headers={"Host": "rebind.attacker.test"})
    assert response.status_code == 400
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_no_cors_headers_are_returned_to_a_rejected_origin() -> None:
    """A refusal must not also hand the caller permission to read it."""
    response = await _request("POST", "/__guard_probe__", headers={"Origin": HOSTILE_ORIGIN})
    assert "access-control-allow-origin" not in response.headers


# --- Rate limiting ------------------------------------------------------------


@pytest.mark.asyncio
async def test_requests_are_refused_past_the_per_minute_ceiling(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.main import app

    monkeypatch.setenv("OIHK_RATE_LIMIT_PER_MINUTE", "5")
    get_settings.cache_clear()
    reset_rate_limiter(app)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=LOOPBACK) as client:
            # /health is exempt, so the budget is spent on a route that counts.
            # An unrouted path still consumes it: the limiter runs before
            # routing, and using one keeps this test off the database entirely.
            statuses = [(await client.get("/__rate_probe__")).status_code for _ in range(7)]
        assert statuses[:5] == [404] * 5
        assert statuses[5:] == [429, 429]
    finally:
        get_settings.cache_clear()
        reset_rate_limiter(app)


@pytest.mark.asyncio
async def test_a_full_but_stale_limiter_map_still_admits_a_new_client(monkeypatch) -> None:
    """A map sitting exactly on the ceiling has to be swept before it refuses.

    The size trigger and the rejection compare the same number, and comparing
    it with different operators left one value — the ceiling itself — where no
    sweep ran and an unknown key was refused anyway. Every tracked entry here
    is already outside the window, so the only correct answer is to release
    them and admit the request.

    ``_last_sweep`` is pinned to now so the time trigger cannot fire and mask
    which of the two paths did the work.
    """
    import time as time_module

    from starlette.requests import Request
    from starlette.responses import PlainTextResponse

    from app.middleware import rate_limit as rate_limit_module
    from app.middleware.rate_limit import RateLimitMiddleware

    monkeypatch.setattr(rate_limit_module, "_MAX_TRACKED_KEYS", 4)
    middleware = RateLimitMiddleware(app=None)

    expired = time_module.monotonic() - 3600
    for index in range(4):
        middleware._hits[f"stale-{index}"].append(expired)
    middleware._last_sweep = time_module.monotonic()

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/__rate_probe__",
        "raw_path": b"/__rate_probe__",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("203.0.113.9", 44321),
        "server": ("127.0.0.1", 8000),
    }

    async def call_next(_request):
        return PlainTextResponse("ok")

    response = await middleware.dispatch(Request(scope), call_next)

    assert response.status_code == 200
    assert "stale-0" not in middleware._hits
    assert "203.0.113.9" in middleware._hits


@pytest.mark.asyncio
async def test_the_health_probe_is_never_rate_limited(monkeypatch) -> None:
    """The desktop core polls /health while waiting for the backend to come up."""
    from app.core.config import get_settings
    from app.main import app

    monkeypatch.setenv("OIHK_RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    reset_rate_limiter(app)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=LOOPBACK) as client:
            statuses = [(await client.get("/health")).status_code for _ in range(6)]
        assert statuses == [200] * 6
    finally:
        get_settings.cache_clear()
        reset_rate_limiter(app)


@pytest.mark.asyncio
async def test_rate_limit_headers_report_the_remaining_budget(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.main import app

    monkeypatch.setenv("OIHK_RATE_LIMIT_PER_MINUTE", "10")
    get_settings.cache_clear()
    reset_rate_limiter(app)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=LOOPBACK) as client:
            first = await client.get("/__rate_probe__")
            second = await client.get("/__rate_probe__")
        assert first.headers["x-ratelimit-limit"] == "10"
        assert int(first.headers["x-ratelimit-remaining"]) > int(second.headers["x-ratelimit-remaining"])
    finally:
        get_settings.cache_clear()
        reset_rate_limiter(app)
