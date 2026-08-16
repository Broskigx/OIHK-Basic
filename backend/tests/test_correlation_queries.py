"""Cross-case correlation must not pay a query per selector or per hit.

Correlation answers "where else has this been seen". Both entry points walked
their results issuing one statement per row, so the cost grew with exactly the
thing that makes an answer worth having: a case that has been worked on, and a
selector that appears in many cases.

These assert an identical query count at two sizes rather than a time budget.
A threshold generous enough not to flake on a shared runner would still pass
against a reintroduced N+1 at small N; the count would not.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.database import Base
from app.services import correlation

ORG = "acme"


async def _seeded(tmp_path, name: str, *, cases: int, selectors: int):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / f'{name}.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        for case_index in range(cases):
            session.add(
                models.Case(
                    id=f"case-{case_index}",
                    organization_id=ORG,
                    title=f"Case {case_index}",
                    legal_basis="Authorized test",
                    scope_statement="Bounded scope for the correlation query-count tests.",
                )
            )
        await session.flush()
        for case_index in range(cases):
            for selector_index in range(selectors):
                session.add(
                    models.CorrelationAttribute(
                        organization_id=ORG,
                        case_id=f"case-{case_index}",
                        source_id=None,
                        attr_type="email",
                        attr_value=f"person{selector_index}@example.test",
                        display=f"person{selector_index}@example.test",
                    )
                )
        await session.commit()
    return engine, sessions


def _record_selects(engine, sink: list[str]) -> None:
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _listener(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            sink.append(statement)


@pytest.mark.asyncio
async def test_case_overlaps_costs_the_same_at_any_number_of_selectors(tmp_path) -> None:
    counts = []
    overlap_counts = []
    for label, selectors in (("small", 3), ("large", 40)):
        engine, sessions = await _seeded(tmp_path, f"ov-{label}", cases=4, selectors=selectors)
        selects: list[str] = []
        _record_selects(engine, selects)
        async with sessions() as session:
            result = await correlation.case_overlaps(session, organization_id=ORG, case_id="case-0")
        overlap_counts.append(len(result))
        counts.append(len(selects))
        await engine.dispose()

    assert overlap_counts == [3, 3], "every other seeded case shares every selector"
    assert counts[0] == counts[1], f"query count grew with the selector set: {counts[0]} -> {counts[1]}"


@pytest.mark.asyncio
async def test_correlate_costs_the_same_at_any_number_of_hits(tmp_path) -> None:
    counts = []
    hit_counts = []
    for label, cases in (("small", 3), ("large", 30)):
        engine, sessions = await _seeded(tmp_path, f"co-{label}", cases=cases, selectors=1)
        selects: list[str] = []
        _record_selects(engine, selects)
        async with sessions() as session:
            hits = await correlation.correlate(
                session,
                organization_id=ORG,
                attr_type="email",
                value="person0@example.test",
            )
        hit_counts.append(len(hits))
        counts.append(len(selects))
        await engine.dispose()

    assert hit_counts == [3, 30], "every seeded case holds the selector"
    assert counts[0] == counts[1], f"query count grew with the hits: {counts[0]} -> {counts[1]}"


@pytest.mark.asyncio
async def test_overlaps_still_report_the_shared_selectors_and_titles(tmp_path) -> None:
    """The batching must not cost the report its content.

    Paired with the counting tests above: a rewrite that returned nothing would
    satisfy a constant query count perfectly.
    """
    engine, sessions = await _seeded(tmp_path, "ov-content", cases=3, selectors=2)
    async with sessions() as session:
        result = await correlation.case_overlaps(session, organization_id=ORG, case_id="case-0")

    by_id = {overlap.case_id: overlap for overlap in result}
    assert set(by_id) == {"case-1", "case-2"}
    assert by_id["case-1"].case_title == "Case 1"
    assert by_id["case-1"].shared_count == 2
    assert {attr_type for attr_type, _ in by_id["case-1"].samples} == {"email"}
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_case_sharing_nothing_produces_no_overlap(tmp_path) -> None:
    engine, sessions = await _seeded(tmp_path, "ov-isolated", cases=2, selectors=1)
    async with sessions() as session:
        session.add(
            models.Case(
                id="lonely",
                organization_id=ORG,
                title="Lonely",
                legal_basis="Authorized test",
                scope_statement="Bounded scope with a selector nobody else holds.",
            )
        )
        await session.flush()
        session.add(
            models.CorrelationAttribute(
                organization_id=ORG,
                case_id="lonely",
                source_id=None,
                attr_type="email",
                attr_value="nobody-else@example.test",
                display="nobody-else@example.test",
            )
        )
        await session.commit()

        assert await correlation.case_overlaps(session, organization_id=ORG, case_id="lonely") == []

    await engine.dispose()


@pytest.mark.asyncio
async def test_overlaps_do_not_cross_the_organization_boundary(tmp_path) -> None:
    """Correlation is the one feature that reads across cases, so its filter matters.

    A selector shared with a case in another organization must not surface: the
    overlap report names the other case and quotes the shared value, which is
    most of what that case is about.
    """
    engine, sessions = await _seeded(tmp_path, "ov-org", cases=2, selectors=1)
    async with sessions() as session:
        session.add(
            models.Case(
                id="rival-case",
                organization_id="rival",
                title="Rival case",
                legal_basis="Authorized test",
                scope_statement="Bounded scope belonging to another organization.",
            )
        )
        await session.flush()
        session.add(
            models.CorrelationAttribute(
                organization_id="rival",
                case_id="rival-case",
                source_id=None,
                attr_type="email",
                attr_value="person0@example.test",
                display="person0@example.test",
            )
        )
        await session.commit()

        overlaps = await correlation.case_overlaps(session, organization_id=ORG, case_id="case-0")

    assert "rival-case" not in {overlap.case_id for overlap in overlaps}
    await engine.dispose()
