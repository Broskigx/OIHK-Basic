"""Dispatch and refusal behaviour for the tools the local Agent may invoke.

The agent layer is a dispatcher: it maps a name the model produced onto an
application route and runs it as the real user. Two things follow from that
shape, and neither was covered.

A dispatch branch that is never exercised is a tool that can be broken without
anything noticing — the model asks for it, the call raises, and the failure
surfaces as a sentence in a chat reply rather than a test failure. So every
read tool is dispatched here, which is what makes a renamed router argument or
a changed signature fail loudly.

And a refusal has to leave the session usable. A turn may carry several tool
calls; if the first one is rejected by the application and poisons the
transaction, the rest of the turn fails for a reason that has nothing to do
with what was asked.
"""

from __future__ import annotations

import pytest

from app import models
from app.core.deps import CurrentUser
from app.services import assistant_tools

SYSTEM = CurrentUser(
    id="system",
    email="system@oihk-basic.local",
    username="system",
    role="admin",
    organization_id="system",
)

# Every tool that only reads. Writes are covered separately because each needs
# its own arguments and its own intent phrasing to pass the write gate.
READ_TOOLS = [
    "list_investigations",
    "get_investigation",
    "get_investigation_overview",
    "list_graph",
    "list_sources",
    "list_evidence",
    "get_custody",
    "list_osint_history",
    "list_reports",
    "list_transforms",
    "list_audit_events",
]


@pytest.fixture
async def seeded_case(session) -> str:
    case = models.Case(
        id="agent-tools-case",
        title="Agent tools case",
        legal_basis="Authorized test",
        scope_statement="Bounded scope for the agent tool dispatch tests.",
    )
    session.add(case)
    await session.flush()
    session.add(
        models.Source(
            case_id=case.id,
            title="Seed source",
            kind="note",
            body="seed body",
            citation="seed",
        )
    )
    await session.commit()
    return case.id


async def _run(session, tool: str, arguments: dict, case_id: str | None, text: str = "lista todo"):
    return await assistant_tools.execute_agent_tool(
        tool_name=tool,
        arguments=arguments,
        user_text=text,
        active_case_id=case_id,
        enabled=None,
        current=SYSTEM,
        session=session,
    )


@pytest.mark.parametrize("tool", READ_TOOLS)
@pytest.mark.asyncio
async def test_every_read_tool_dispatches_to_a_working_route(tool, session, seeded_case) -> None:
    """A tool nobody calls in a test is a tool that can rot silently.

    These assert the dispatch reaches the route and the route answers — not
    what it answers, which belongs with the route's own tests. What this
    catches is the realistic breakage: a router signature changes, the keyword
    the dispatcher passes no longer matches, and the only symptom is the Agent
    telling a user it could not complete the request.
    """
    result = await _run(session, tool, {}, seeded_case)

    assert result.ok is True, result.result_summary
    assert result.tool == tool
    assert result.result_summary, "a successful tool must describe what it did"


@pytest.mark.asyncio
async def test_a_rejected_tool_leaves_the_session_usable_for_the_next_one(session, seeded_case) -> None:
    """A turn can carry several calls; one refusal must not take the rest with it.

    `require_case_access` raising inside a route leaves the transaction in a
    failed state, and every later statement on that session would raise too —
    so the second tool would fail with a database error that has nothing to do
    with what the user asked for. The rollback in the handler is what keeps the
    refusal local to the call that earned it.
    """
    refused = await _run(session, "list_sources", {"case_id": "no-such-case"}, None)
    assert refused.ok is False

    recovered = await _run(session, "list_sources", {}, seeded_case)
    assert recovered.ok is True, recovered.result_summary


@pytest.mark.asyncio
async def test_an_unknown_tool_name_is_refused_rather_than_dispatched(session, seeded_case) -> None:
    result = await _run(session, "drop_everything", {}, seeded_case)

    assert result.ok is False
    assert "Unknown tool" in result.result_summary


@pytest.mark.asyncio
async def test_a_tool_outside_the_configured_allowlist_is_refused(session, seeded_case) -> None:
    """An empty preference means every built-in tool; a non-empty one is an allowlist.

    The distinction matters in the refusing direction: a user who narrowed the
    set in Local Models has to actually get the narrowed set, or the setting is
    decorative.
    """
    result = await assistant_tools.execute_agent_tool(
        tool_name="list_sources",
        arguments={},
        user_text="lista las fuentes",
        active_case_id=seeded_case,
        enabled=["list_investigations"],
        current=SYSTEM,
        session=session,
    )

    assert result.ok is False
    assert "disabled" in result.result_summary


@pytest.mark.asyncio
async def test_a_tool_needing_an_investigation_says_so_when_there_is_none(session) -> None:
    result = await _run(session, "list_sources", {}, None)

    assert result.ok is False
    assert "investigation" in result.result_summary.lower()


@pytest.mark.asyncio
async def test_a_write_runs_when_the_user_asked_and_is_reported_with_its_id(session) -> None:
    result = await _run(
        session,
        "create_investigation",
        {"title": "Agent created case"},
        None,
        text="crea una investigación sobre esto",
    )

    assert result.ok is True, result.result_summary
    assert result.result["title"] == "Agent created case"
    assert result.result["id"] in result.result_summary


@pytest.mark.asyncio
async def test_the_same_write_is_refused_when_the_user_did_not_ask_for_it(session) -> None:
    """Paired with the test above: this is what separates a gate from a wall.

    Asserting only the refusal would also pass against an implementation that
    refuses every write, which would be a broken product rather than a safe
    one.
    """
    result = await _run(
        session,
        "create_investigation",
        {"title": "Unrequested case"},
        None,
        text="cuéntame un chiste",
    )

    assert result.ok is False
    assert "did not explicitly request" in result.result_summary


@pytest.mark.asyncio
async def test_the_catalog_reports_which_tools_change_data(session) -> None:
    """The catalog is what the model is shown, so the write flag has to be in it.

    Eight tools mutate. If that count moves, either a capability was added or
    one silently changed side, and both deserve a deliberate look — the write
    gate registry has to be updated in step, and forgetting it is the mistake
    the fail-closed check exists to catch.
    """
    catalog = assistant_tools.agent_tool_catalog()
    mutating = [entry for entry in catalog if entry["changes_data"]]

    assert len(catalog) == len(assistant_tools.AGENT_TOOLS)
    assert len(mutating) == 8
    assert {entry["name"] for entry in mutating} <= set(assistant_tools._WRITE_INTENT)
