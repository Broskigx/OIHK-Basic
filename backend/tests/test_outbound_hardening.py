"""Adversarial regressions for outbound lookup and model-adapter boundaries.

Each test in this module fails against the pre-hardening implementation:

* the OSINT and transform adapters interpolated unvalidated entity values into
  third-party URLs and resolved them with a blocking ``socket.gethostbyname``;
* every adapter called ``response.json()`` with no ceiling, so a compressed
  body could expand without bound in memory.
"""

from __future__ import annotations

import asyncio
import gzip
import json

import httpx
import pytest

from app.services import local_models
from app.services.local_models import LMStudioProvider, OllamaProvider
from app.services.safe_http import (
    OutboundRequestError,
    ResponseTooLargeError,
    get_json_bounded,
    require_hostname,
    require_ipv4,
    resolve_hostname_a_record,
)
from app.transforms.catalog import _cert_search, _dns_resolve, _shodan_like, _whois_lookup

_REAL_ASYNC_CLIENT = httpx.AsyncClient


class _Entity:
    """Minimal stand-in for the entity attributes a transform handler reads."""

    def __init__(self, value: str) -> None:
        self.value = value


def _client_factory(handler):
    def _factory(*_args, **kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), timeout=kwargs.get("timeout"))

    return _factory


# --------------------------------------------------------------------------
# Input validation: investigation data must never reach a URL unvalidated
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "example.com/../../admin",  # path traversal in the RDAP URL
        "example.com&output=html",  # query-parameter injection at crt.sh
        "example.com?x=1",
        "example.com#fragment",
        "user@example.com",  # authority confusion
        "example.com:8080",
        "127.0.0.1",  # bare address is not a hostname
        "localhost",  # single label, no TLD
        "-leading-hyphen.com",
        "exa mple.com",
        "",
        "a" * 250 + ".com",  # over the 253-character ceiling
    ],
)
def test_require_hostname_rejects_url_metacharacters_and_malformed_names(hostile):
    with pytest.raises(OutboundRequestError):
        require_hostname(hostile)


def test_require_hostname_accepts_and_normalises_real_names():
    assert require_hostname("  Example.COM. ") == "example.com"
    assert require_hostname("sub.domain.example.co.uk") == "sub.domain.example.co.uk"


@pytest.mark.parametrize(
    "hostile",
    ["1.2.3.4/../x", "999.1.1.1", "1.2.3", "::1", "1.2.3.4:80", "not-an-ip", ""],
)
def test_require_ipv4_rejects_non_addresses(hostile):
    with pytest.raises(OutboundRequestError):
        require_ipv4(hostile)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler,entity_value",
    [
        (_whois_lookup, "example.com/../../etc/passwd"),
        (_cert_search, "example.com&output=html"),
        (_shodan_like, "1.1.1.1/../../admin"),
        (_dns_resolve, "example.com/evil"),
    ],
)
async def test_transform_handlers_refuse_hostile_entity_values_without_network(handler, entity_value, monkeypatch):
    """A transform only checks entity *type*; the value must be revalidated.

    Every handler wraps its body in ``except Exception``, so a probe that
    *raises* on contact would be swallowed and the test would pass against the
    vulnerable code. Contact is instead recorded in a list that survives the
    handler's exception handling, and the assertion is made on that list.
    """
    contacted: list[str] = []

    def _record(request: httpx.Request) -> httpx.Response:
        contacted.append(str(request.url))
        return httpx.Response(200, json={})

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(_record))
    monkeypatch.setattr("socket.gethostbyname", lambda hostname: contacted.append(f"dns:{hostname}") or "203.0.113.1")

    result = await handler(None, entity=_Entity(entity_value))

    assert contacted == [], f"hostile entity value reached the network: {contacted}"
    assert result == []


# --------------------------------------------------------------------------
# Non-blocking DNS: a stalled resolver must not freeze the event loop
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hostname_resolution_does_not_block_the_event_loop(monkeypatch):
    """A hanging resolver must not stop other coroutines from making progress."""
    release = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _hanging_resolver(_hostname: str) -> str:
        # Blocks in a worker thread until the concurrent coroutine has run.
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), loop).result(timeout=5)
        return "203.0.113.10"

    monkeypatch.setattr("socket.gethostbyname", _hanging_resolver)

    async def _other_work() -> str:
        await asyncio.sleep(0)
        release.set()
        return "progressed"

    resolved, other = await asyncio.wait_for(
        asyncio.gather(resolve_hostname_a_record("example.com"), _other_work()),
        timeout=10,
    )
    assert resolved == "203.0.113.10"
    assert other == "progressed"
    assert release.is_set()


@pytest.mark.asyncio
async def test_hostname_resolution_times_out_instead_of_hanging(monkeypatch):
    import threading

    # Stand-in for a blackholed name: the resolver blocks until released.
    #
    # The release matters. `asyncio.wait_for` stops *waiting* on the worker
    # thread but cannot cancel it, and a thread still blocked when the loop
    # shuts down is joined by the default executor — so an unreleased sleep
    # here is paid in full on every run of the suite, long after the assertion
    # it supports has already passed.
    blocked = threading.Event()

    def _blocking_resolver(_hostname: str) -> str:
        blocked.wait(30)
        return "203.0.113.10"

    monkeypatch.setattr("socket.gethostbyname", _blocking_resolver)
    try:
        with pytest.raises(OutboundRequestError):
            await resolve_hostname_a_record("example.com", timeout=0.25)
    finally:
        blocked.set()


# --------------------------------------------------------------------------
# Bounded reads: a decompression bomb must be refused mid-stream
# --------------------------------------------------------------------------


def _gzip_bomb_bytes(expanded_bytes: int) -> bytes:
    """A compressed payload that expands to roughly ``expanded_bytes``."""
    return gzip.compress(b'{"a":"' + (b"A" * expanded_bytes) + b'"}')


def _gzip_bomb(expanded_bytes: int) -> httpx.Response:
    return httpx.Response(
        200,
        content=_gzip_bomb_bytes(expanded_bytes),
        headers={"content-encoding": "gzip", "content-type": "application/json"},
    )


@pytest.mark.asyncio
async def test_bounded_json_read_refuses_a_decompression_bomb():
    # The compressed body is orders of magnitude under the ceiling; only the
    # decompressed stream crosses it. This is the case an unbounded
    # `response.json()` would have materialised in full.
    assert len(_gzip_bomb_bytes(4_000_000)) < 100_000

    async with _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(lambda _r: _gzip_bomb(4_000_000))) as client:
        with pytest.raises(ResponseTooLargeError):
            await get_json_bounded(client, "https://crt.sh/", max_bytes=1_000_000)


@pytest.mark.asyncio
async def test_bounded_json_read_refuses_an_oversized_declared_length():
    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, headers={"content-length": "999999999"})

    async with _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(_handler)) as client:
        with pytest.raises(ResponseTooLargeError):
            await get_json_bounded(client, "https://example.test/", max_bytes=1024)


@pytest.mark.asyncio
async def test_bounded_json_read_rejects_malformed_json():
    async with _REAL_ASYNC_CLIENT(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, content=b"{not json"))
    ) as client:
        with pytest.raises(OutboundRequestError):
            await get_json_bounded(client, "https://example.test/", max_bytes=1024)


@pytest.mark.asyncio
async def test_bounded_json_read_returns_none_for_unexpected_status():
    async with _REAL_ASYNC_CLIENT(
        transport=httpx.MockTransport(lambda _r: httpx.Response(404, json={"error": "nope"}))
    ) as client:
        assert await get_json_bounded(client, "https://example.test/", max_bytes=1024) is None


# --------------------------------------------------------------------------
# Model adapters: bounded bodies and bounded streams
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_model_listing_refuses_an_oversized_response(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(lambda _r: _gzip_bomb(4_000_000)))
    monkeypatch.setenv("OIHK_MAX_MODEL_RESPONSE_BYTES", "65536")

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="read limit"):
            await LMStudioProvider("http://127.0.0.1:1234", 10).list_models()
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_openai_stream_stops_at_the_character_budget(monkeypatch):
    """An endpoint that never emits [DONE] must not stream without a ceiling."""

    def _endless(_request: httpx.Request) -> httpx.Response:
        async def _lines():
            chunk = json.dumps({"choices": [{"delta": {"content": "x" * 1000}}]})
            for _ in range(1000):
                yield f"data: {chunk}\n\n".encode()

        return httpx.Response(200, content=_lines())

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(_endless))
    monkeypatch.setenv("OIHK_MAX_MODEL_STREAM_CHARS", "5000")

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        produced = 0
        async for delta in LMStudioProvider("http://127.0.0.1:1234", 10).stream(
            model="m", messages=[], temperature=0.1, max_tokens=10
        ):
            produced += len(delta)
        # Bounded by the budget plus at most the final chunk that crossed it.
        assert produced <= 5000
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ollama_stream_stops_at_the_character_budget(monkeypatch):
    def _endless(_request: httpx.Request) -> httpx.Response:
        async def _lines():
            chunk = json.dumps({"message": {"content": "y" * 1000}, "done": False})
            for _ in range(1000):
                yield (chunk + "\n").encode()

        return httpx.Response(200, content=_lines())

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(_endless))
    monkeypatch.setenv("OIHK_MAX_MODEL_STREAM_CHARS", "3000")

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        produced = 0
        async for delta in OllamaProvider("http://127.0.0.1:11434", 10).stream(
            model="m", messages=[], temperature=0.1, max_tokens=10
        ):
            produced += len(delta)
        assert produced <= 3000
    finally:
        get_settings.cache_clear()


def test_local_endpoint_policy_rejects_public_and_trailing_dot_evasion():
    with pytest.raises(ValueError):
        local_models.validate_local_endpoint("http://example.com./v1")
    with pytest.raises(ValueError):
        local_models.validate_local_endpoint("http://8.8.8.8:1234")
