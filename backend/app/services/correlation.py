"""Cross-case correlation for OIHK Basic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


@dataclass
class CorrelationHit:
    case_id: str
    case_title: str
    source_id: str | None
    attr_type: str
    attr_value: str
    display: str
    first_seen_at: datetime


@dataclass
class CaseOverlap:
    case_id: str
    case_title: str
    shared_count: int
    samples: list[tuple[str, str]]


async def index_attribute(
    session: AsyncSession,
    *,
    organization_id: str,
    case_id: str,
    attr_type: str,
    value: str,
    source_id: str | None = None,
) -> bool:
    """Index an attribute for cross-case correlation. Returns True if newly added."""
    normalized_type = attr_type.strip().lower()[:40]
    normalized_value = value.strip().lower()[:400]

    existing = await session.execute(
        select(models.CorrelationAttribute.id).where(
            models.CorrelationAttribute.organization_id == organization_id,
            models.CorrelationAttribute.case_id == case_id,
            models.CorrelationAttribute.attr_type == normalized_type,
            models.CorrelationAttribute.attr_value == normalized_value,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    attr = models.CorrelationAttribute(
        organization_id=organization_id,
        case_id=case_id,
        source_id=source_id,
        attr_type=normalized_type,
        attr_value=normalized_value,
        display=value.strip(),
    )
    session.add(attr)
    return True


async def correlate(
    session: AsyncSession,
    *,
    organization_id: str,
    attr_type: str,
    value: str,
    exclude_case_id: str | None = None,
) -> list[CorrelationHit]:
    """Find all cases where this selector has been seen."""
    normalized_type = attr_type.strip().lower()[:40]
    normalized_value = value.strip().lower()[:400]

    statement = select(models.CorrelationAttribute).where(
        models.CorrelationAttribute.organization_id == organization_id,
        models.CorrelationAttribute.attr_type == normalized_type,
        models.CorrelationAttribute.attr_value == normalized_value,
    )
    if exclude_case_id:
        statement = statement.where(models.CorrelationAttribute.case_id != exclude_case_id)

    rows = (await session.execute(statement)).scalars().all()
    hits = []
    for row in rows:
        case = await session.get(models.Case, row.case_id)
        hits.append(
            CorrelationHit(
                case_id=row.case_id,
                case_title=case.title if case else "Unknown",
                source_id=row.source_id,
                attr_type=row.attr_type,
                attr_value=row.attr_value,
                display=row.display or row.attr_value,
                first_seen_at=row.first_seen_at,
            )
        )
    return hits


async def case_overlaps(
    session: AsyncSession,
    *,
    organization_id: str,
    case_id: str,
) -> list[CaseOverlap]:
    """Find other cases that share selectors with the given case."""
    selectors = (
        (
            await session.execute(
                select(models.CorrelationAttribute).where(
                    models.CorrelationAttribute.organization_id == organization_id,
                    models.CorrelationAttribute.case_id == case_id,
                )
            )
        )
        .scalars()
        .all()
    )

    if not selectors:
        return []

    # For each selector, find other cases with the same value
    overlaps: dict[str, set[str]] = {}
    for sel in selectors:
        others = await session.execute(
            select(models.CorrelationAttribute.case_id).where(
                models.CorrelationAttribute.organization_id == organization_id,
                models.CorrelationAttribute.attr_type == sel.attr_type,
                models.CorrelationAttribute.attr_value == sel.attr_value,
                models.CorrelationAttribute.case_id != case_id,
            )
        )
        for other_case_id in others.scalars().all():
            if other_case_id not in overlaps:
                overlaps[other_case_id] = set()
            overlaps[other_case_id].add(f"{sel.attr_type}:{sel.attr_value}")

    result = []
    for other_case_id, shared in overlaps.items():
        other_case = await session.get(models.Case, other_case_id)
        samples = list(shared)[:5]
        result.append(
            CaseOverlap(
                case_id=other_case_id,
                case_title=other_case.title if other_case else "Unknown",
                shared_count=len(shared),
                samples=[(s.split(":")[0], s.split(":")[1]) for s in samples],
            )
        )
    return result
