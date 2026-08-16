"""Baseline response headers for every API response.

Individual routes that hand back files or embeddable documents already set the
headers their content needs — the evidence preview pins a sandbox CSP, the
System Link module surface pins ``frame-ancestors`` and its own resource policy.
This middleware supplies the defaults for everything else and never overwrites a
header a route set deliberately, so a route stays the authority on its own
content.

``Cache-Control: no-store`` is applied for the same reason the rest of the
product avoids incidental copies of case material: a response body here can be
evidence, and the webview's HTTP cache is an unmanaged copy of it on disk that
no custody record accounts for.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_DEFAULT_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cache-Control": "no-store",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), display-capture=(), geolocation=(), "
        "gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in _DEFAULT_HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value
        if "X-Frame-Options" not in response.headers:
            # A response that declares frame-ancestors has already stated its
            # embedding policy in the more expressive header. Adding the legacy
            # one alongside it only creates a contradiction for the browser to
            # resolve, so the modern directive is left to stand alone.
            csp = response.headers.get("Content-Security-Policy", "")
            if "frame-ancestors" not in csp:
                response.headers["X-Frame-Options"] = "DENY"
        return response
