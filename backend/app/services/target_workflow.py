"""Target workflow for OIHK Basic — create target cases and run searches."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.public_search import search_public

logger = logging.getLogger(__name__)


def parse_aliases(raw: str) -> list[str]:
    return [a.strip() for a in raw.replace(",", "\n").split("\n") if a.strip()]


async def create_memory(
    session: AsyncSession,
    *,
    case_id: str,
    target_id: str | None = None,
    kind: str,
    content: str,
    confidence: float = 0.5,
    source_ids: list[str] | None = None,
) -> models.CaseMemory:
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


async def create_target_case(
    session: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    aliases: list[str],
    notes: str,
    legal_basis: str,
    scope_statement: str,
    consent_basis: str,
    owner_id: str,
    organization_id: str = "default",
) -> tuple[models.Case, models.TargetProfile, list[models.CaseMemory]]:
    case = models.Case(
        owner_id=owner_id,
        organization_id=organization_id,
        title=f"{first_name} {last_name}",
        summary=f"Investigation: {first_name} {last_name}",
        legal_basis=legal_basis,
        scope_statement=scope_statement,
    )
    session.add(case)
    await session.flush()

    target = models.TargetProfile(
        case_id=case.id,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        aliases=aliases,
        notes=notes.strip(),
        consent_basis=consent_basis,
    )
    session.add(target)
    await session.flush()

    memories: list[models.CaseMemory] = []
    intro_memory = await create_memory(
        session,
        case_id=case.id,
        target_id=target.id,
        kind="target_intake",
        content=f"Target profile created for {first_name} {last_name}",
        confidence=0.95,
    )
    memories.append(intro_memory)

    return case, target, memories


async def run_target_search(
    session: AsyncSession,
    *,
    target: models.TargetProfile,
) -> tuple[models.SearchRun, list[models.SearchHit], list[models.CaseMemory]]:
    first = target.first_name
    last = target.last_name
    aliases = target.aliases or []

    queries = [f"{first} {last}"]
    for alias in aliases[:3]:
        queries.append(alias)

    search_run = models.SearchRun(
        case_id=target.case_id,
        target_id=target.id,
        status="running",
        provider="local",
        queries=queries,
    )
    session.add(search_run)
    await session.flush()

    hits: list[models.SearchHit] = []
    all_results: list[dict] = []

    for query in queries:
        try:
            results = await search_public(query, max_results=5)
            all_results.extend(results)
        except Exception:
            logger.warning("Public search failed for query %r; continuing with other queries", query, exc_info=True)
            continue

    seen_urls: set[str] = set()
    for i, result in enumerate(all_results):
        url = result.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        hit = models.SearchHit(
            run_id=search_run.id,
            case_id=target.case_id,
            target_id=target.id,
            title=result.get("title", "")[:500],
            url=url,
            snippet=result.get("snippet", ""),
            rank=i + 1,
            source_name=result.get("source_name", "public_web"),
            confidence=0.45,
        )
        session.add(hit)
        hits.append(hit)

    search_run.status = "completed" if not all_results else "completed"
    search_run.hit_count = len(hits)
    search_run.query_count = len(queries)
    search_run.completed_at = models.utcnow()

    memories: list[models.CaseMemory] = []
    if hits:
        mem = await create_memory(
            session,
            case_id=target.case_id,
            target_id=target.id,
            kind="search_results",
            content=f"Public search yielded {len(hits)} results from {len(queries)} queries",
            confidence=0.6,
        )
        memories.append(mem)

    return search_run, hits, memories
