"""Target intake and the public-search run that follows it.

The search run is a record inside a case file, so the distinction that matters
most here is not how many hits it found but whether it can honestly claim to
have looked. A run stored as completed with no hits asserts that the sources
were searched and held nothing, which is a finding an analyst may rely on.
"""

from __future__ import annotations

import pytest

from app import models
from app.services import target_workflow


def test_aliases_are_parsed_from_either_separator() -> None:
    """Intake is a free-text box, so both shapes arrive in practice."""
    assert target_workflow.parse_aliases("Ada, Grace\nAlan") == ["Ada", "Grace", "Alan"]
    assert target_workflow.parse_aliases("  ,, \n  ") == []
    assert target_workflow.parse_aliases("") == []


@pytest.mark.asyncio
async def test_target_intake_creates_the_case_profile_and_its_first_memory(session) -> None:
    case, target, memories = await target_workflow.create_target_case(
        session,
        first_name="  Ada  ",
        last_name="  Lovelace ",
        aliases=["A. Lovelace"],
        notes="  handled with consent  ",
        legal_basis="Authorized research",
        scope_statement="Bounded scope for the target workflow tests.",
        consent_basis="Written consent on file",
        owner_id=None,
    )
    await session.commit()

    assert case.title == "Ada Lovelace", "the case title leads every list, export and report"
    assert case.summary == "Investigation: Ada Lovelace"
    assert target.first_name == "Ada", "intake has to strip what the operator typed"
    assert target.last_name == "Lovelace"
    assert target.notes == "handled with consent"
    assert target.case_id == case.id
    assert [m.kind for m in memories] == ["target_intake"]
    assert memories[0].target_id == target.id


async def _target(session) -> models.TargetProfile:
    case, target, _ = await target_workflow.create_target_case(
        session,
        first_name="Ada",
        last_name="Lovelace",
        aliases=["A. Lovelace", "Countess", "AL", "ignored-fourth"],
        notes="",
        legal_basis="Authorized research",
        scope_statement="Bounded scope for the target workflow tests.",
        consent_basis="Written consent on file",
        owner_id=None,
    )
    await session.commit()
    return target


@pytest.mark.asyncio
async def test_a_run_where_every_query_failed_is_not_recorded_as_completed(session, monkeypatch) -> None:
    """The distinction this whole module turns on.

    Storing "completed" here would put a conclusion in the case file that was
    never reached — the sources were never successfully consulted, so "nothing
    was found" is not something this run is entitled to assert.
    """
    async def always_fails(query, **kwargs):
        raise RuntimeError("search backend unavailable")

    monkeypatch.setattr(target_workflow, "search_public", always_fails)
    target = await _target(session)

    run, hits, memories = await target_workflow.run_target_search(session, target=target)

    assert run.status == "failed"
    assert hits == [] and memories == []
    assert run.hit_count == 0


@pytest.mark.asyncio
async def test_a_run_that_searched_and_found_nothing_is_completed(session, monkeypatch) -> None:
    """Paired with the test above: an empty result is a real answer.

    Without this, marking every empty run as failed would satisfy the previous
    test and destroy the distinction it exists to protect.
    """
    async def finds_nothing(query, **kwargs):
        return []

    monkeypatch.setattr(target_workflow, "search_public", finds_nothing)
    target = await _target(session)

    run, hits, _ = await target_workflow.run_target_search(session, target=target)

    assert run.status == "completed"
    assert hits == []


@pytest.mark.asyncio
async def test_one_failing_query_does_not_discard_what_the_others_found(session, monkeypatch) -> None:
    async def sometimes(query, **kwargs):
        if query == "Countess":
            raise RuntimeError("transient failure")
        return [{"url": f"https://example.test/{query}", "title": query, "snippet": "s"}]

    monkeypatch.setattr(target_workflow, "search_public", sometimes)
    target = await _target(session)

    run, hits, memories = await target_workflow.run_target_search(session, target=target)

    assert run.status == "completed"
    assert len(hits) >= 1
    assert [m.kind for m in memories] == ["search_results"]


@pytest.mark.asyncio
async def test_repeated_urls_across_queries_become_one_hit(session, monkeypatch) -> None:
    """Aliases search for the same person, so the same page comes back repeatedly.

    Storing it once per query would inflate the hit count, which is a metric
    that appears in the case record.
    """
    async def same_page(query, **kwargs):
        return [{"url": "https://example.test/profile", "title": query, "snippet": "s"}]

    monkeypatch.setattr(target_workflow, "search_public", same_page)
    target = await _target(session)

    run, hits, _ = await target_workflow.run_target_search(session, target=target)

    assert len(hits) == 1
    assert run.hit_count == 1


@pytest.mark.asyncio
async def test_only_the_first_three_aliases_become_queries(session, monkeypatch) -> None:
    """An unbounded alias list would turn one intake into unbounded outbound traffic."""
    asked: list[str] = []

    async def record(query, **kwargs):
        asked.append(query)
        return []

    monkeypatch.setattr(target_workflow, "search_public", record)
    target = await _target(session)

    run, _, _ = await target_workflow.run_target_search(session, target=target)

    assert asked == ["Ada Lovelace", "A. Lovelace", "Countess", "AL"]
    assert "ignored-fourth" not in asked
    assert run.query_count == 4
