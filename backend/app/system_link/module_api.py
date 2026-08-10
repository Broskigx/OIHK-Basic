"""Capability-gated generic host APIs for authenticated System Link modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_session
from app.system_link.capabilities import CapabilityDenied, require_capability
from app.system_link.module_auth import authenticate_module_request
from app.system_link.protocol import ModuleState
from app.system_link.service import SystemLinkError, SystemLinkService

router = APIRouter(prefix="/system-link/module-api/v1", tags=["system-link-module-api"])


@dataclass(frozen=True)
class AuthenticatedModule:
    record: models.SystemLinkModule


async def authenticated_module(
    request: Request,
    module_id: str = Header(alias="X-OIHK-Module-Id"),
    nonce: str = Header(alias="X-OIHK-Nonce"),
    timestamp: int = Header(alias="X-OIHK-Timestamp"),
    signature: str = Header(alias="X-OIHK-Signature"),
    session: AsyncSession = Depends(get_session),
) -> AuthenticatedModule:
    try:
        module = await authenticate_module_request(
            session,
            module_id=module_id,
            method=request.method,
            path=request.url.path,
            nonce=nonce,
            timestamp=timestamp,
            body=await request.body(),
            signature=signature,
        )
    except SystemLinkError as exc:
        raise HTTPException(status_code=401, detail=f"{exc.code}: {exc}") from exc
    return AuthenticatedModule(module)


async def _capability(
    session: AsyncSession,
    authenticated: AuthenticatedModule,
    capability: str,
) -> models.SystemLinkModule:
    try:
        return await require_capability(session, authenticated.record.module_id, capability)
    except CapabilityDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/cases/{case_id}")
async def read_case(
    case_id: str,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _capability(session, authenticated, "case.read")
    case = await session.get(models.Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "id": case.id,
        "title": case.title,
        "summary": case.summary,
        "legal_basis": case.legal_basis,
        "scope_statement": case.scope_statement,
        "status": case.status,
        "tags": case.tags,
        "updated_at": case.updated_at,
    }


@router.get("/cases/{case_id}/evidence")
async def read_evidence(
    case_id: str,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await _capability(session, authenticated, "evidence.read")
    rows = list(
        (
            await session.execute(
                select(models.EvidenceItem)
                .where(models.EvidenceItem.case_id == case_id)
                .order_by(models.EvidenceItem.created_at.desc())
            )
        ).scalars()
    )
    return [
        {
            "id": item.id,
            "case_id": item.case_id,
            "source_id": item.source_id,
            "original_name": item.original_name,
            "mime_type": item.mime_type,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
            "notes": item.notes,
            "tags": item.tags,
            "entity_ids": item.entity_ids,
            "created_at": item.created_at,
            "verified_at": item.verified_at,
        }
        for item in rows
    ]


class ModuleStatusWrite(BaseModel):
    status: ModuleState
    detail: str = ""


@router.post("/status")
async def publish_status(
    payload: ModuleStatusWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    module = await _capability(session, authenticated, "module.status.publish")
    if payload.status not in {ModuleState.READY, ModuleState.BUSY, ModuleState.ERROR}:
        raise HTTPException(status_code=422, detail="A runtime may publish only READY, BUSY, or ERROR")
    service = SystemLinkService(session)
    current = ModuleState(module.state)
    if payload.status != current:
        await service.transition(
            module,
            payload.status,
            error_code="module_reported_error" if payload.status == ModuleState.ERROR else "",
            error_detail=payload.detail,
            event="module_runtime_status_published",
        )
    else:
        module.last_health_at = datetime.now(UTC)
        await session.commit()
    return {"module_id": module.module_id, "state": module.state}
