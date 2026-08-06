"""In-process sliding-window rate limiter for OIHK Basic."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings

_WINDOW_SECONDS = 60.0
_EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = 0.0

    def _client_key(self, request: Request) -> str:
        direct_ip = request.client.host if request.client else "unknown"
        settings = get_settings()
        if settings.rate_limit_trust_forwarded:
            # Only trust X-Forwarded-For when the real peer is a proxy we
            # explicitly recognize; otherwise anyone could spoof the header
            # to evade the limiter. An empty trust list disables header trust.
            trusted = settings.trusted_proxy_ip_list
            if direct_ip in trusted:
                forwarded = request.headers.get("x-forwarded-for")
                if forwarded:
                    return forwarded.split(",")[0].strip()
        return direct_ip

    def _sweep(self, now: float) -> None:
        cutoff = now - _WINDOW_SECONDS
        stale = [key for key, bucket in self._hits.items() if not bucket or bucket[-1] < cutoff]
        for key in stale:
            self._hits.pop(key, None)

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path
        if not settings.rate_limit_enabled or path in _EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        limit = settings.rate_limit_per_minute
        key = self._client_key(request)
        now = time.monotonic()

        if now - self._last_sweep > _WINDOW_SECONDS:
            self._sweep(now)
            self._last_sweep = now
        bucket = self._hits[key]

        cutoff = now - _WINDOW_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - bucket[0])))
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Slow down and retry."},
                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limit)},
            )

        bucket.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(bucket)))
        if not bucket:
            self._hits.pop(key, None)
        return response
