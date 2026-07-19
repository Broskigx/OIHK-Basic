"""Reports router for OIHK Basic."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{case_id}.md")
async def markdown_report(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    case = await require_case_access(session, case_id, current)

    sources = (
        (await session.execute(
            select(models.Source).where(models.Source.case_id == case_id).order_by(models.Source.collected_at)
        )).scalars().all()
    )
    entities = (
        (await session.execute(
            select(models.Entity).where(models.Entity.case_id == case_id).order_by(models.Entity.type, models.Entity.value)
        )).scalars().all()
    )
    relationships = (
        (await session.execute(select(models.Relationship).where(models.Relationship.case_id == case_id))).scalars().all()
    )

    lines = [
        f"# {case.title}",
        "",
        f"Status: {case.status}",
        f"Legal basis: {case.legal_basis}",
        "",
        "## Scope",
        case.scope_statement,
        "",
        "## Sources",
    ]
    for source in sources:
        lines.append(
            f"- {source.title} ({source.kind}, reliability {source.reliability:.2f}) - {source.citation or source.url or source.id}"
        )

    lines.extend(["", "## Entities"])
    for entity in entities:
        source_count = len(entity.source_ids or [])
        lines.append(f"- {entity.type}: {entity.display} (confidence {entity.confidence:.2f}, sources {source_count})")

    lines.extend(["", "## Relationships"])
    label_by_id = {entity.id: f"{entity.display} [{entity.type}]" for entity in entities}
    for relationship in relationships:
        subject = label_by_id.get(relationship.subject_id, relationship.subject_id)
        obj = label_by_id.get(relationship.object_id, relationship.object_id)
        lines.append(f"- {subject} — {relationship.predicate} → {obj} (confidence {relationship.confidence:.2f})")

    lines.extend([
        "",
        "## Review note",
        "This report is machine-assisted. Verify identities, context, and legal basis before external use.",
    ])
    return Response("\n".join(lines), media_type="text/markdown")
