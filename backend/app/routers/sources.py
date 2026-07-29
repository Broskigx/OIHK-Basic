"""Sources router for OIHK Basic."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import IngestResult, SourceRead, TextIngestRequest, UrlIngestRequest
from app.services.policy import PublicUrlError, fetch_public_url
from app.services.repository import ingest_source

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/{case_id}", response_model=list[SourceRead])
async def list_sources(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.Source]:
    await require_case_access(session, case_id, current)
    result = await session.execute(
        select(models.Source).where(models.Source.case_id == case_id).order_by(models.Source.collected_at.desc())
    )
    return list(result.scalars().all())


async def _ensure_case(session: AsyncSession, case_id: str, current: CurrentUser) -> None:
    await require_case_access(session, case_id, current)


@router.post("/text", response_model=IngestResult, status_code=201)
async def ingest_text(
    payload: TextIngestRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IngestResult:
    await _ensure_case(session, payload.case_id, current)
    source, entities, relationships = await ingest_source(
        session,
        case_id=payload.case_id,
        title=payload.title,
        kind="manual_text",
        body=payload.body,
        citation=payload.citation,
        license=payload.license,
        reliability=payload.reliability,
    )
    await session.commit()
    return IngestResult(source=source, entities=entities, relationships=relationships)


@router.post("/url", response_model=IngestResult, status_code=201)
async def ingest_url(
    payload: UrlIngestRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IngestResult:
    await _ensure_case(session, payload.case_id, current)
    try:
        fetched = await fetch_public_url(str(payload.url))
    except PublicUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    source, entities, relationships = await ingest_source(
        session,
        case_id=payload.case_id,
        title=payload.title or fetched.title,
        kind="public_url",
        body=fetched.body,
        citation=fetched.url,
        license=payload.license,
        reliability=payload.reliability,
        url=fetched.url,
        robot_compliant=fetched.robot_compliant,
    )
    await session.commit()
    return IngestResult(source=source, entities=entities, relationships=relationships)
