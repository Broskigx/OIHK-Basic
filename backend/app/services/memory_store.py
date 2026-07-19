"""Memory store for OIHK Basic — case memory management, no Redis dependency."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


async def store_memory(
    session: AsyncSession,
    *,
    case_id: str,
    target_id: str | None = None,
    kind: str,
    content: str,
    confidence: float = 0.5,
    source_ids: list[str] | None = None,
) -> models.CaseMemory:
    """Store a memory entry in the database."""
    memory = models.CaseMemory(
        case_id=case_id,
        target_id=target_id,
        kind=kind,
        content=content,
        confidence=confidence,
        source_ids=source_ids or [],
    )
    session.add(memory)
    await session.flush()
    return memory


async def recall_memories(
    session: AsyncSession,
    *,
    case_id: str,
    limit: int = 40,
    target_id: str | None = None,
) -> list[models.CaseMemory]:
    """Retrieve memories for a case, most recent first."""
    statement = (
        select(models.CaseMemory)
        .where(models.CaseMemory.case_id == case_id)
        .order_by(models.CaseMemory.created_at.desc())
        .limit(limit)
    )
    if target_id:
        statement = statement.where(models.CaseMemory.target_id == target_id)
    result = await session.execute(statement)
    return list(result.scalars().all())
