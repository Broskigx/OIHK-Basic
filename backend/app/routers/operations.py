"""Operations router for OIHK Basic — audit log and case monitoring."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user
from app.database import get_session
from app.schemas import (
    CaseRead, SourceRead, CaseMemoryRead, SearchRunRead, TargetPhotoRead,
    TargetProfileRead,
)

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/audit")
async def list_audit_events(
    case_id: str | None = Query(default=None),
    limit: int = Query(default=80, le=200),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List audit events, optionally filtered by case."""
    statement = select(models.AuditEvent).order_by(models.AuditEvent.created_at.desc()).limit(limit)
    if case_id:
        statement = statement.where(models.AuditEvent.case_id == case_id)
    if not current.is_system:
        statement = statement.where(models.AuditEvent.payload["organization_id"].as_string() == current.organization_id)
    result = await session.execute(statement)
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "case_id": e.case_id,
            "payload": e.payload,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.get("/cases/{case_id}/monitor")
async def get_case_monitor(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get a summary overview of a case's current state."""
    from app.core.deps import require_case_access

    case = await require_case_access(session, case_id, current)

    source_count = (
        await session.execute(select(models.Source.id).where(models.Source.case_id == case_id))
    ).scalar()
    entity_count = (
        await session.execute(select(models.Entity.id).where(models.Entity.case_id == case_id))
    ).scalar()
    relationship_count = (
        await session.execute(select(models.Relationship.id).where(models.Relationship.case_id == case_id))
    ).scalar()

    return {
        "case_id": case.id,
        "title": case.title,
        "status": case.status,
        "source_count": source_count or 0,
        "entity_count": entity_count or 0,
        "relationship_count": relationship_count or 0,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }
