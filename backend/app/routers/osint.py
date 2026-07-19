"""OSINT router for OIHK Basic."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import OsintFindingRead, OsintLookupRequest, OsintLookupResult
from app.services.osint_service import run_and_ingest

router = APIRouter(prefix="/osint", tags=["osint"])


@router.post("/lookup", response_model=OsintLookupResult, status_code=201)
async def osint_lookup(
    payload: OsintLookupRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OsintLookupResult:
    """Enrich a domain / IP / email against free public sources and add it to the case graph."""
    await require_case_access(session, payload.case_id, current)

    report, source, entities, relationships = await run_and_ingest(
        session, case_id=payload.case_id, value=payload.value
    )
    if report.kind == "unknown":
        raise HTTPException(status_code=400, detail="Value must be a domain, IP address, or email.")

    await session.commit()
    return OsintLookupResult(
        value=report.value,
        kind=report.kind,
        summary=report.summary(),
        findings=[
            OsintFindingRead(source=f.source, type=f.type, value=f.value, detail=f.detail) for f in report.findings
        ],
        errors=report.errors,
        entities=entities,
        relationships=relationships,
        source=source,
    )
