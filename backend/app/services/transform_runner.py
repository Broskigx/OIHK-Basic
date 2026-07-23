"""Transform runner for OIHK Basic — runs transforms on graph nodes."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.analyzer import ExtractedEntity
from app.services.repository import upsert_entity
from app.transforms import registry


class TransformError(Exception):
    def __init__(self, message: str, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


@dataclass
class TransformResult:
    strategy: str
    summary: str
    new_entities: list[models.Entity]
    new_relationships: list[models.Relationship]


async def run_transform_on_entity(
    session: AsyncSession,
    *,
    transform_id: str,
    entity: models.Entity,
    actor: str = "analyst",
    case: models.Case | None = None,
) -> TransformResult:
    spec = registry.get(transform_id)
    if spec is None:
        raise TransformError(f"Transform '{transform_id}' not found", not_found=True)
    if not spec.enabled:
        raise TransformError(f"Transform '{transform_id}' is not enabled")
    if entity.type not in spec.input_types:
        raise TransformError(
            f"Transform '{spec.title}' requires input type(s) {spec.input_types}, but entity is '{entity.type}'"
        )

    new_entities: list[models.Entity] = []
    new_relationships: list[models.Relationship] = []

    try:
        result = await spec.handler(session, entity=entity)
    except Exception as exc:
        raise TransformError(f"Transform '{spec.title}' failed: {exc}") from exc

    if result:
        for item in result:
            ex_entity = ExtractedEntity(
                type=item.get("type", entity.type),
                value=item.get("value", ""),
                display=item.get("display", item.get("value", "")),
                confidence=item.get("confidence", 0.5),
            )
            if ex_entity.value:
                new_entity = await upsert_entity(
                    session,
                    entity.case_id,
                    entity.source_ids[0] if entity.source_ids else "",
                    ex_entity,
                )
                new_entities.append(new_entity)

                rel = models.Relationship(
                    case_id=entity.case_id,
                    subject_id=entity.id,
                    predicate=item.get("relation", "related_to"),
                    object_id=new_entity.id,
                    confidence=min(entity.confidence, ex_entity.confidence, 0.82),
                    source_ids=entity.source_ids or [],
                )
                session.add(rel)
                new_relationships.append(rel)

    return TransformResult(
        strategy=spec.title,
        summary=f"{spec.title}: {len(new_entities)} entidad(es) nueva(s)",
        new_entities=new_entities,
        new_relationships=new_relationships,
    )
