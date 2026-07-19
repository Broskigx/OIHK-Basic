"""CSRF protection middleware for OIHK Basic."""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

_EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/auth/login", "/auth/register"}
_CSRF_COOKIE = "oihk_basic_csrf_token"
_CSRF_HEADER = "x-csrf-token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-Submit Cookie CSRF protection."""

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if not settings.auth_enabled:
            return await call_next(request)

        path = request.url.path
        if path in _EXEMPT_PATHS:
            response: Response = await call_next(request)
            _ensure_csrf_cookie(response, current_token=request.cookies.get(_CSRF_COOKIE), secure=settings.is_production)
            return response

        if request.method in _SAFE_METHODS:
            response = await call_next(request)
            _ensure_csrf_cookie(response, current_token=request.cookies.get(_CSRF_COOKIE), secure=settings.is_production)
            return response

        cookie_token = request.cookies.get(_CSRF_COOKIE, "")
        header_token = request.headers.get(_CSRF_HEADER, "")

        if not cookie_token or not header_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing. Set the X-CSRF-Token header from the oihk_basic_csrf_token cookie."},
            )

        if not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token mismatch. Possible cross-site request forgery."},
            )

        response = await call_next(request)
        return response


def _ensure_csrf_cookie(response: Response, *, current_token: str | None, secure: bool) -> None:
    if current_token:
        return
    existing = response.headers.get("set-cookie", "")
    if existing.startswith(f"{_CSRF_COOKIE}="):
        return
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=_CSRF_COOKIE,
        value=token,
        max_age=3600,
        samesite="lax",
        secure=secure,
        httponly=False,
        path="/",
    )
