"""Interesting Files Identifier for OIHK Basic — declarative file flagging rules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


async def create_rule(
    session: AsyncSession,
    *,
    organization_id: str,
    name: str,
    severity: str = "medium",
    name_contains: str = "",
    name_glob: str = "",
    extensions: list[str] | None = None,
    types: list[str] | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
    min_entropy: float | None = None,
    description: str = "",
    created_by: str | None = None,
) -> models.InterestingFileRule:
    existing = await session.execute(
        select(models.InterestingFileRule.id).where(
            models.InterestingFileRule.organization_id == organization_id,
            models.InterestingFileRule.name == name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Rule '{name}' already exists in this organization")

    rule = models.InterestingFileRule(
        organization_id=organization_id,
        name=name,
        severity=severity,
        name_contains=name_contains,
        name_glob=name_glob,
        extensions=extensions or [],
        types=types or [],
        min_size=min_size,
        max_size=max_size,
        min_entropy=min_entropy,
        description=description,
        created_by=created_by,
    )
    session.add(rule)
    await session.flush()
    return rule


async def list_rules(
    session: AsyncSession,
    *,
    organization_id: str,
) -> list[models.InterestingFileRule]:
    result = await session.execute(
        select(models.InterestingFileRule)
        .where(
            models.InterestingFileRule.organization_id == organization_id,
        )
        .order_by(models.InterestingFileRule.name)
    )
    return list(result.scalars().all())


async def delete_rule(
    session: AsyncSession,
    *,
    organization_id: str,
    rule_id: str,
) -> bool:
    rule = await session.get(models.InterestingFileRule, rule_id)
    if rule is None or rule.organization_id != organization_id:
        return False
    await session.delete(rule)
    return True
