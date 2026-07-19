"""Hash intelligence for OIHK Basic — known-file hash-set matching."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


@dataclass
class HashImportSummary:
    set_name: str
    category: str
    added: int
    skipped: int
    invalid: int


@dataclass
class HashMatch:
    set_name: str
    category: str
    severity: str
    algorithm: str
    digest: str
    label: str


@dataclass
class HashSetInfo:
    set_name: str
    category: str
    entries: int


def _infer_algorithm(digest: str) -> str:
    digest = digest.strip().lower()
    if len(digest) == 32:
        return "md5"
    elif len(digest) == 40:
        return "sha1"
    elif len(digest) == 64:
        return "sha256"
    return "sha256"


async def import_hash_entries(
    session: AsyncSession,
    *,
    organization_id: str,
    set_name: str,
    category: str,
    severity: str,
    text: str,
    created_by: str | None = None,
) -> HashImportSummary:
    added = 0
    skipped = 0
    invalid = 0

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue

        parts = line.split()
        if not parts:
            invalid += 1
            continue

        digest = parts[0].strip().lower()
        label = " ".join(parts[1:])[:240] if len(parts) > 1 else ""
        algorithm = _infer_algorithm(digest)

        if algorithm not in ("md5", "sha1", "sha256") or not all(c in "0123456789abcdef" for c in digest):
            invalid += 1
            continue

        existing = await session.execute(
            select(models.ForensicHashEntry.id).where(
                models.ForensicHashEntry.organization_id == organization_id,
                models.ForensicHashEntry.set_name == set_name,
                models.ForensicHashEntry.algorithm == algorithm,
                models.ForensicHashEntry.digest == digest,
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        entry = models.ForensicHashEntry(
            organization_id=organization_id,
            set_name=set_name,
            category=category,
            severity=severity,
            algorithm=algorithm,
            digest=digest,
            label=label,
            created_by=created_by,
        )
        session.add(entry)
        added += 1

    return HashImportSummary(set_name=set_name, category=category, added=added, skipped=skipped, invalid=invalid)


async def list_hash_sets(
    session: AsyncSession,
    *,
    organization_id: str,
) -> list[HashSetInfo]:
    result = await session.execute(
        select(
            models.ForensicHashEntry.set_name,
            models.ForensicHashEntry.category,
            func.count(models.ForensicHashEntry.id).label("entries"),
        ).where(
            models.ForensicHashEntry.organization_id == organization_id,
        ).group_by(
            models.ForensicHashEntry.set_name,
            models.ForensicHashEntry.category,
        ).order_by(models.ForensicHashEntry.set_name)
    )
    infos = []
    for row in result.all():
        infos.append(HashSetInfo(set_name=row.set_name, category=row.category, entries=row.entries))
    return infos


async def lookup_value(
    session: AsyncSession,
    *,
    organization_id: str,
    value: str,
) -> list[HashMatch]:
    algorithm = _infer_algorithm(value)
    digest = value.strip().lower()

    entries = (
        await session.execute(
            select(models.ForensicHashEntry).where(
                models.ForensicHashEntry.organization_id == organization_id,
                models.ForensicHashEntry.algorithm == algorithm,
                models.ForensicHashEntry.digest == digest,
            )
        )
    ).scalars().all()

    return [
        HashMatch(
            set_name=e.set_name,
            category=e.category,
            severity=e.severity,
            algorithm=e.algorithm,
            digest=e.digest,
            label=e.label,
        )
        for e in entries
    ]
