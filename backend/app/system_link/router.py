"""FastAPI receptor and host control-plane endpoints for System Link v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_session
from app.system_link.lifecycle import runtime_supervisor
from app.system_link.protocol import ModuleState
from app.system_link.schemas import (
    LifecycleResultRead,
    LinkedModuleRead,
    ModuleEventRead,
    PairingApproveWrite,
    PairingCompleteWrite,
    PairingPendingRead,
    PairingStartRead,
    SystemLinkStatusRead,
)
from app.system_link.service import SystemLinkError, SystemLinkService

host_router = APIRouter(prefix="/system-link", tags=["system-link"])
pairing_router = APIRouter(prefix="/system-link", tags=["system-link-pairing"])


def _http_error(exc: SystemLinkError) -> HTTPException:
    status_code = 404 if exc.code in {"module_not_found", "pairing_not_found"} else 409
    if exc.code in {"pairing_key_invalid", "pairing_signature_invalid"}:
        status_code = 401
    return HTTPException(status_code=status_code, detail=f"{exc.code}: {exc}")


async def _module(session: AsyncSession, module_id: str) -> models.SystemLinkModule:
    row = await session.get(models.SystemLinkModule, module_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Linked System Link module not found")
    return row


@host_router.get("/status", response_model=SystemLinkStatusRead)
async def status(session: AsyncSession = Depends(get_session)) -> SystemLinkStatusRead:
    service = SystemLinkService(session)
    identity = await service.installation_identity()
    rows = list((await session.execute(select(models.SystemLinkModule))).scalars())
    for row in rows:
        await runtime_supervisor.reconcile(session, row)
    return SystemLinkStatusRead(
        protocol_version="1.0",
        installation_public_key=identity.public_key,
        installation_fingerprint=identity.fingerprint,
        key_storage=identity.storage_kind,
        modules=await service.list_modules(),
    )


@host_router.get("/modules", response_model=list[LinkedModuleRead])
async def modules(session: AsyncSession = Depends(get_session)) -> list[LinkedModuleRead]:
    return await SystemLinkService(session).list_modules()


@host_router.post("/pair/start", response_model=PairingStartRead, status_code=201)
async def pair_start(session: AsyncSession = Depends(get_session)) -> PairingStartRead:
    try:
        row, link_key, identity, signature = await SystemLinkService(session).begin_pairing()
    except SystemLinkError as exc:
        raise _http_error(exc) from exc
    return PairingStartRead(
        pairing_id=row.id,
        link_key=link_key,
        expires_at=row.expires_at,
        challenge=row.challenge,
        protocol_version="1.0",
        installation_public_key=identity.public_key,
        installation_fingerprint=identity.fingerprint,
        basic_signature=signature,
    )


@host_router.get("/pair/pending", response_model=list[PairingPendingRead])
async def pair_pending(session: AsyncSession = Depends(get_session)) -> list[PairingPendingRead]:
    return await SystemLinkService(session).pending_pairings()


@pairing_router.post("/pair/complete", response_model=PairingPendingRead)
async def pair_complete(
    payload: PairingCompleteWrite,
    session: AsyncSession = Depends(get_session),
) -> PairingPendingRead:
    service = SystemLinkService(session)
    try:
        row = await service.submit_pairing(
            pairing_id=payload.pairing_id,
            link_key=payload.link_key,
            module_public_key=payload.module_public_key,
            manifest=payload.manifest,
            manifest_signature=payload.manifest_signature,
            challenge_signature=payload.challenge_signature,
            package_root=payload.package_root,
        )
    except SystemLinkError as exc:
        raise _http_error(exc) from exc
    pending = row.pending_module
    return PairingPendingRead(
        pairing_id=row.id,
        module_id=payload.manifest.module_id,
        product_name=payload.manifest.name,
        module_version=payload.manifest.version,
        module_fingerprint=pending["module_fingerprint"],
        requested_capabilities=payload.manifest.requested_capabilities,
        categories=[category.model_dump(mode="json") for category in payload.manifest.categories],
        expires_at=row.expires_at,
    )


@host_router.post("/pair/{pairing_id}/approve", response_model=LinkedModuleRead)
async def pair_approve(
    pairing_id: str,
    payload: PairingApproveWrite,
    session: AsyncSession = Depends(get_session),
) -> LinkedModuleRead:
    service = SystemLinkService(session)
    try:
        module = await service.approve_pairing(pairing_id, payload.granted_capabilities)
        return await service.module_view(module)
    except SystemLinkError as exc:
        raise _http_error(exc) from exc


@host_router.post("/modules/{module_id}/start", response_model=LifecycleResultRead)
async def start_module(module_id: str, session: AsyncSession = Depends(get_session)) -> LifecycleResultRead:
    module = await _module(session, module_id)
    try:
        state = await runtime_supervisor.start(session, module)
    except SystemLinkError as exc:
        raise _http_error(exc) from exc
    return LifecycleResultRead(module_id=module_id, state=state, action="start", detail=module.last_error_detail)


@host_router.post("/modules/{module_id}/stop", response_model=LifecycleResultRead)
async def stop_module(module_id: str, session: AsyncSession = Depends(get_session)) -> LifecycleResultRead:
    module = await _module(session, module_id)
    try:
        state = await runtime_supervisor.stop(session, module)
    except SystemLinkError as exc:
        raise _http_error(exc) from exc
    return LifecycleResultRead(module_id=module_id, state=state, action="stop", detail=module.last_error_detail)


@host_router.post("/modules/{module_id}/restart", response_model=LifecycleResultRead)
async def restart_module(module_id: str, session: AsyncSession = Depends(get_session)) -> LifecycleResultRead:
    module = await _module(session, module_id)
    try:
        state = await runtime_supervisor.restart(session, module)
    except SystemLinkError as exc:
        raise _http_error(exc) from exc
    return LifecycleResultRead(module_id=module_id, state=state, action="restart", detail=module.last_error_detail)


@host_router.post("/modules/{module_id}/cancel", response_model=LifecycleResultRead)
async def cancel_module(module_id: str, session: AsyncSession = Depends(get_session)) -> LifecycleResultRead:
    module = await _module(session, module_id)
    if not runtime_supervisor.cancel(module_id):
        raise HTTPException(status_code=409, detail="No cancellable lifecycle operation is active")
    return LifecycleResultRead(module_id=module_id, state=ModuleState(module.state), action="cancel")


@host_router.post("/modules/{module_id}/disable", response_model=LinkedModuleRead)
async def disable_module(module_id: str, session: AsyncSession = Depends(get_session)) -> LinkedModuleRead:
    service = SystemLinkService(session)
    module = await _module(session, module_id)
    try:
        await service.disable(module)
    except SystemLinkError as exc:
        raise _http_error(exc) from exc
    return await service.module_view(module)


@host_router.post("/modules/{module_id}/enable", response_model=LinkedModuleRead)
async def enable_module(module_id: str, session: AsyncSession = Depends(get_session)) -> LinkedModuleRead:
    service = SystemLinkService(session)
    module = await _module(session, module_id)
    try:
        await service.enable(module)
    except SystemLinkError as exc:
        raise _http_error(exc) from exc
    return await service.module_view(module)


@host_router.post("/modules/{module_id}/revoke", response_model=LinkedModuleRead)
async def revoke_module(module_id: str, session: AsyncSession = Depends(get_session)) -> LinkedModuleRead:
    service = SystemLinkService(session)
    module = await _module(session, module_id)
    try:
        await service.revoke(module)
    except SystemLinkError as exc:
        raise _http_error(exc) from exc
    return await service.module_view(module)


@host_router.get("/events", response_model=list[ModuleEventRead])
async def events(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[models.SystemLinkEvent]:
    return list(
        (
            await session.execute(
                select(models.SystemLinkEvent).order_by(models.SystemLinkEvent.created_at.desc()).limit(limit)
            )
        ).scalars()
    )
