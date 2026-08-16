"""Browser-origin and Host validation for the loopback API.

The desktop edition runs with ``OIHK_AUTH_ENABLED=false``: every request that
reaches the loopback port is already trusted, and the CSRF middleware steps
aside because there is no session to forge. That reasoning holds for a *network*
attacker, who cannot reach 127.0.0.1 at all. It does not hold for a web page the
operator happens to visit while OIHK Basic is running, because the browser is
inside the trust boundary and will happily issue requests to loopback.

Two distinct attacks follow from that, and each needs its own control.

**Cross-origin writes.** ``POST /evidence`` and the other ingestion routes accept
``multipart/form-data``. That is a CORS-safelisted content type, so a plain
``<form>`` submission is *not* preflighted: the browser sends the request and
only withholds the response. CORS never blocked the write, it blocked the read.
For a forensics tool that is the wrong half to protect — planting a file in a
case is the damage, and the attacker does not need to see the reply. Any unsafe
method carrying a browser ``Origin`` outside the allowlist is refused here.

**Rebinding reads.** Origin checks cannot address this one. If an attacker's
domain re-resolves to 127.0.0.1, the browser believes the page and the API share
an origin, so it sends no ``Origin``, reports ``Sec-Fetch-Site: same-origin`` and
applies no CORS at all. The single header that still carries the attacker's own
name is ``Host``, which is why the authority is checked against an allowlist on
*every* method, reads included.

The two controls are complementary and deliberately kept in one place: the
Origin check bounds what a cross-origin page may cause, the Host check bounds
who may present themselves as this server.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
# Loopback authorities a browser can produce for a loopback bind. A rebinding
# attack necessarily presents the attacker's own name instead of one of these.
_LOOPBACK_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})
# The module API authenticates every call with a signed, timestamped envelope
# bound to a paired Ed25519 identity, and is reached by a sibling desktop
# process rather than a browser. It carries no Origin and must not be judged by
# browser rules.
_ORIGIN_EXEMPT_PREFIXES = ("/system-link/module-api/v1/",)


def _split_authority(value: str) -> str:
    """Return the bare hostname from a Host header value, without its port."""
    authority = value.strip().lower()
    if authority.startswith("["):
        # IPv6 literal: [::1] or [::1]:8000
        closing = authority.find("]")
        if closing == -1:
            return authority
        return authority[1:closing]
    host, separator, port = authority.rpartition(":")
    if separator and port.isdigit():
        return host
    return authority


def _normalize_origin(value: str) -> str:
    return value.strip().rstrip("/").lower()


def host_is_allowed(host_header: str, settings) -> bool:
    """Decide whether ``host_header`` may address this server."""
    if not host_header:
        # HTTP/1.0 clients and direct ASGI callers omit Host entirely. A browser
        # always sends one, so an absent header is never the rebinding case.
        return True
    authority = host_header.strip().lower()
    hostname = _split_authority(authority)

    configured = settings.allowed_host_list
    if configured:
        # An entry with a port pins that exact authority; one without accepts
        # any port, since the desktop backend picks a free port per launch.
        return authority in configured or hostname in configured

    if settings.binds_to_loopback:
        return hostname in _LOOPBACK_HOSTNAMES

    # A non-loopback bind is a deliberate deployment behind a proxy that
    # rewrites Host to a name only the operator knows. Guessing it here would
    # reject legitimate traffic, so the check defers to OIHK_ALLOWED_HOSTS.
    return True


def origin_is_allowed(origin: str, settings) -> bool:
    """Decide whether a browser ``Origin`` may issue a state-changing request."""
    allowed = {_normalize_origin(entry) for entry in settings.cors_origin_list}
    if "*" in allowed:
        # Wildcard CORS is a development-only escape hatch; production refuses
        # to start with it (see app.main._enforce_hardening).
        return True
    return _normalize_origin(origin) in allowed


class OriginGuardMiddleware(BaseHTTPMiddleware):
    """Reject rebound Host authorities and cross-origin state changes."""

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()

        if not host_is_allowed(request.headers.get("host", ""), settings):
            return JSONResponse(
                status_code=400,
                content={
                    "detail": (
                        "Request rejected: the Host header does not name this local service. "
                        "OIHK Basic answers only on its loopback address."
                    ),
                    "code": "host_not_allowed",
                },
            )

        if request.method in _SAFE_METHODS or request.url.path.startswith(_ORIGIN_EXEMPT_PREFIXES):
            return await call_next(request)

        origin = request.headers.get("origin", "")
        if origin and not origin_is_allowed(origin, settings):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Request rejected: cross-origin state changes are not permitted.",
                    "code": "origin_not_allowed",
                },
            )

        # Belt and braces for the case where a browser omits Origin but still
        # labels the request cross-origin. An absent Origin *and* an absent
        # Sec-Fetch-Site is the ordinary non-browser client (the Tauri core, the
        # System Link smoke runner, curl), which is allowed through.
        if not origin and request.headers.get("sec-fetch-site", "").strip().lower() in {"cross-site", "same-site"}:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Request rejected: cross-origin state changes are not permitted.",
                    "code": "origin_not_allowed",
                },
            )

        return await call_next(request)
