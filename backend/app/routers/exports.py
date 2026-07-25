"""Exports router for OIHK Basic."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.database import get_session

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/cases/{case_id}/json")
async def export_case_json(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Export case data as JSON for local backup."""
    from sqlalchemy import select

    from app import models
    from app.core.deps import require_case_access

    case = await require_case_access(session, case_id, current)

    sources = (await session.execute(select(models.Source).where(models.Source.case_id == case_id))).scalars().all()
    entities = (await session.execute(select(models.Entity).where(models.Entity.case_id == case_id))).scalars().all()
    relationships = (
        (await session.execute(select(models.Relationship).where(models.Relationship.case_id == case_id)))
        .scalars()
        .all()
    )

    import json
    from datetime import datetime

    def json_default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    data = {
        "schema_version": 1,
        "case": {
            "id": case.id,
            "title": case.title,
            "summary": case.summary,
            "legal_basis": case.legal_basis,
            "scope_statement": case.scope_statement,
            "status": case.status,
            "priority": case.priority,
            "tags": case.tags,
            "notes": case.notes,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
        },
        "sources": [
            {
                "id": s.id,
                "title": s.title,
                "kind": s.kind,
                "body": s.body,
                "citation": s.citation,
                "reliability": s.reliability,
                "collected_at": s.collected_at,
            }
            for s in sources
        ],
        "entities": [
            {
                "id": e.id,
                "type": e.type,
                "value": e.value,
                "display": e.display,
                "confidence": e.confidence,
                "source_ids": e.source_ids,
                "properties": e.properties,
                "notes": e.notes,
                "first_seen": e.first_seen,
                "last_seen": e.last_seen,
            }
            for e in entities
        ],
        "relationships": [
            {
                "id": r.id,
                "subject_id": r.subject_id,
                "predicate": r.predicate,
                "object_id": r.object_id,
                "confidence": r.confidence,
            }
            for r in relationships
        ],
    }

    return Response(
        content=json.dumps(data, default=json_default, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="oihk-basic-case-{case_id}.json"'},
    )
