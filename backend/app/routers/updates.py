"""Authenticated update preparation and token-bound local shutdown."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.deps import CurrentUser, get_current_user
from app.core.update_service import (
    UpdatePreparationError,
    read_recovery_state,
    update_coordinator,
)
from app.schemas import UpdatePrepareRead, UpdatePrepareRequest, UpdateRecoveryRead

router = APIRouter(prefix="/updates", tags=["updates"])


@router.get("/recovery", response_model=UpdateRecoveryRead)
async def recovery_status(_current: CurrentUser = Depends(get_current_user)) -> UpdateRecoveryRead:
    return UpdateRecoveryRead.model_validate(read_recovery_state() or {})


@router.post("/prepare", response_model=UpdatePrepareRead)
async def prepare_update(
    payload: UpdatePrepareRequest,
    _current: CurrentUser = Depends(get_current_user),
) -> UpdatePrepareRead:
    try:
        token, backup, metadata = await update_coordinator.prepare(payload.target_version, payload.channel)
    except UpdatePreparationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return UpdatePrepareRead(
        update_token=token,
        backup_path=str(backup),
        backup_sha256=metadata.sha256,
        schema_version=metadata.schema_version,
        database_bytes=metadata.database_bytes,
    )


@router.post("/resume", status_code=status.HTTP_204_NO_CONTENT)
async def resume_after_deferred_update(_current: CurrentUser = Depends(get_current_user)) -> None:
    await update_coordinator.resume()


@router.post("/shutdown", status_code=status.HTTP_202_ACCEPTED)
async def shutdown_for_update(
    request: Request,
    x_oihk_update_token: str = Header(default=""),
) -> dict[str, str]:
    callback = getattr(request.app.state, "shutdown_callback", None)
    if not callable(callback):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Managed shutdown is unavailable.",
        )
    if not await update_coordinator.consume_shutdown_token(x_oihk_update_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired update token.")
    asyncio.get_running_loop().call_later(0.2, callback)
    return {"status": "shutting_down"}
