"""Repository service — core database operations for OIHK Basic."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.analyzer import ExtractedEntity, analyze_text


async def create_case(
    session: AsyncSession,
    *,
    title: str,
    summary: str,
    legal_basis: str,
    scope_statement: str,
    owner_id: str,
    organization_id: str = "default",
    priority: str = "normal",
    tags: list[str] | None = None,
    notes: str = "",
) -> models.Case:
    case = models.Case(
        owner_id=owner_id,
        organization_id=organization_id,
        title=title.strip(),
        summary=summary.strip(),
        legal_basis=legal_basis.strip(),
        scope_statement=scope_statement.strip(),
        priority=priority,
        tags=tags or [],
        notes=notes.strip(),
    )
    session.add(case)
    await session.flush()
    return case


async def ingest_source(
    session: AsyncSession,
    *,
    case_id: str,
    title: str,
    kind: str,
    body: str,
    citation: str = "",
    license: str = "unknown",
    reliability: float = 0.5,
    url: str | None = None,
    robot_compliant: bool = True,
) -> tuple[models.Source, list[models.Entity], list[models.Relationship]]:
    source = models.Source(
        case_id=case_id,
        title=title.strip()[:240],
        kind=kind,
        body=body,
        citation=citation.strip(),
        license=license,
        reliability=reliability,
        url=url,
        robot_compliant=robot_compliant,
    )
    session.add(source)
    await session.flush()

    entities: list[models.Entity] = []
    relationships: list[models.Relationship] = []

    extracted = analyze_text(body)
    for ex_entity in extracted:
        entity = await upsert_entity(session, case_id, source.id, ex_entity)
        entities.append(entity)

    return source, entities, relationships


async def upsert_entity(
    session: AsyncSession,
    case_id: str,
    source_id: str,
    extracted: ExtractedEntity,
) -> models.Entity:
    existing = (
        await session.execute(
            select(models.Entity).where(
                models.Entity.case_id == case_id,
                models.Entity.type == extracted.type,
                models.Entity.value == extracted.value,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if source_id not in (existing.source_ids or []):
            existing.source_ids = (existing.source_ids or []) + [source_id]
        existing.confidence = max(existing.confidence, extracted.confidence)
        existing.last_seen = datetime.now(UTC)
        return existing

    entity = models.Entity(
        case_id=case_id,
        type=extracted.type,
        value=extracted.value,
        display=extracted.display,
        confidence=extracted.confidence,
        source_ids=[source_id],
    )
    session.add(entity)
    await session.flush()
    return entity


async def audit(
    session: AsyncSession,
    action: str,
    case_id: str | None,
    payload: dict | None = None,
    *,
    actor: str = "system",
) -> models.AuditEvent:
    event = models.AuditEvent(
        actor=actor,
        action=action,
        case_id=case_id,
        payload=payload or {},
    )
    session.add(event)
    return event
