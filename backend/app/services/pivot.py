"""Entity pivot/expansion service for OIHK Basic."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.analyzer import ExtractedEntity, normalize_value
from app.services.osint_lookups import lookup_domain, lookup_email, lookup_ip
from app.services.repository import upsert_entity


@dataclass
class ExpandResult:
    strategy: str
    summary: str
    new_entities: list[models.Entity]
    new_relationships: list[models.Relationship]


async def expand_entity(session: AsyncSession, entity: models.Entity) -> ExpandResult:
    entity_type = entity.type

    if entity_type == "domain":
        return await _expand_domain(session, entity)
    elif entity_type == "ip":
        return await _expand_ip(session, entity)
    elif entity_type == "email":
        return await _expand_email(session, entity)
    else:
        return ExpandResult(
            strategy="none",
            summary=f"No expansion strategy for type '{entity_type}'",
            new_entities=[],
            new_relationships=[],
        )


async def _expand_domain(session: AsyncSession, entity: models.Entity) -> ExpandResult:
    value = entity.value.lower()
    result = await lookup_domain(value)
    new_entities: list[models.Entity] = []
    new_relationships: list[models.Relationship] = []

    if result.ip_address:
        ip_entity = await upsert_entity(
            session, entity.case_id, entity.source_ids[0] if entity.source_ids else "",
            ExtractedEntity(type="ip", value=result.ip_address, display=result.ip_address, confidence=0.7),
        )
        new_entities.append(ip_entity)
        existing = await session.execute(
            select(models.Relationship).where(
                models.Relationship.case_id == entity.case_id,
                models.Relationship.subject_id == entity.id,
                models.Relationship.object_id == ip_entity.id,
            )
        )
        if not existing.scalar_one_or_none():
            rel = models.Relationship(
                case_id=entity.case_id, subject_id=entity.id,
                predicate="resolves_to", object_id=ip_entity.id,
                confidence=0.7, source_ids=entity.source_ids or [],
            )
            session.add(rel)
            new_relationships.append(rel)

    return ExpandResult(
        strategy="dns_lookup",
        summary=f"Domain {value}: {len(result.findings)} findings",
        new_entities=new_entities,
        new_relationships=new_relationships,
    )


async def _expand_ip(session: AsyncSession, entity: models.Entity) -> ExpandResult:
    value = entity.value
    result = await lookup_ip(value)
    new_entities: list[models.Entity] = []
    new_relationships: list[models.Relationship] = []

    return ExpandResult(
        strategy="geoip",
        summary=f"IP {value}: {len(result.findings)} findings",
        new_entities=new_entities,
        new_relationships=new_relationships,
    )


async def _expand_email(session: AsyncSession, entity: models.Entity) -> ExpandResult:
    value = entity.value.lower()
    result = await lookup_email(value)
    new_entities: list[models.Entity] = []
    new_relationships: list[models.Relationship] = []

    return ExpandResult(
        strategy="email_breach",
        summary=f"Email {value}: {len(result.findings)} findings",
        new_entities=new_entities,
        new_relationships=new_relationships,
    )
