"""OSINT lookup, history, and explicit graph promotion routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import OsintFindingRead, OsintLookupRequest, OsintLookupResult, OsintQueryRead
from app.services.osint_service import ingest_report, report_from_json, run_lookup

router = APIRouter(prefix="/osint", tags=["osint"])


def _finding_dict(finding: object) -> dict[str, str]:
    return {
        "source": str(getattr(finding, "source", "unknown")),
        "type": str(getattr(finding, "type", "observation")),
        "value": str(getattr(finding, "value", "")),
        "detail": str(getattr(finding, "detail", "")),
    }


def _finding_reads(findings: list) -> list[OsintFindingRead]:
    return [
        OsintFindingRead(
            source=str(getattr(item, "source", "unknown")),
            type=str(getattr(item, "type", "observation")),
            value=str(getattr(item, "value", "")),
            detail=str(getattr(item, "detail", "")),
        )
        for item in findings
    ]


def _history_read(row: models.OsintQuery) -> OsintQueryRead:
    return OsintQueryRead(
        id=row.id,
        case_id=row.case_id,
        value=row.value,
        kind=row.kind,
        findings=[OsintFindingRead(**item) for item in row.findings],
        errors=row.errors,
        promoted=row.promoted,
        source_id=row.source_id,
        created_at=row.created_at,
        promoted_at=row.promoted_at,
    )


@router.get("/history/{case_id}", response_model=list[OsintQueryRead])
async def osint_history(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OsintQueryRead]:
    await require_case_access(session, case_id, current)
    rows = (
        await session.execute(
            select(models.OsintQuery)
            .where(models.OsintQuery.case_id == case_id)
            .order_by(models.OsintQuery.created_at.desc())
            .limit(100)
        )
    ).scalars()
    return [_history_read(row) for row in rows]


@router.post("/lookup", response_model=OsintLookupResult, status_code=201)
async def osint_lookup(
    payload: OsintLookupRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OsintLookupResult:
    """Enrich a domain, IP, or email without changing the investigation graph."""
    await require_case_access(session, payload.case_id, current)
    report = await run_lookup(payload.value)
    if report.kind == "unknown":
        raise HTTPException(status_code=400, detail="Value must be a domain, IP address, or email.")

    row = models.OsintQuery(
        case_id=payload.case_id,
        created_by=current.id,
        value=report.value,
        kind=report.kind,
        findings=[_finding_dict(finding) for finding in report.findings],
        errors=report.errors,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return OsintLookupResult(
        query_id=row.id,
        value=report.value,
        kind=report.kind,
        summary=report.summary(),
        findings=_finding_reads(report.findings),
        errors=report.errors,
        entities=[],
        relationships=[],
        source=None,
        promoted=False,
    )


@router.post("/history/{query_id}/promote", response_model=OsintLookupResult)
async def promote_osint_query(
    query_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OsintLookupResult:
    row = await session.get(models.OsintQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="OSINT query not found")
    await require_case_access(session, row.case_id, current)
    if row.promoted:
        raise HTTPException(status_code=409, detail="This result is already in the graph.")

    stored = report_from_json(value=row.value, kind=row.kind, findings=row.findings, errors=row.errors)
    report, source, entities, relationships = await ingest_report(session, case_id=row.case_id, report=stored)
    row.promoted = True
    row.source_id = source.id
    row.promoted_at = datetime.now(UTC)
    await session.commit()
    return OsintLookupResult(
        query_id=row.id,
        value=report.value,
        kind=report.kind,
        summary=report.summary(),
        findings=_finding_reads(report.findings),
        errors=report.errors,
        entities=entities,
        relationships=relationships,
        source=source,
        promoted=True,
    )
