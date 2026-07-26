"""Reject new mutations while the desktop updater drains the backend."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.update_service import update_coordinator

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_CONTROL_PATHS = {"/updates/prepare", "/updates/resume", "/updates/shutdown"}


class UpdateGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in _MUTATING or request.url.path in _CONTROL_PATHS:
            return await call_next(request)
        async with update_coordinator.mutation() as accepted:
            if not accepted:
                return JSONResponse(
                    status_code=503,
                    headers={"Retry-After": "5"},
                    content={
                        "detail": "OIHK Basic is preparing a verified update backup. Try again after restart.",
                        "code": "update_preparing",
                    },
                )
            return await call_next(request)
