"""Authorization rules for cases and the resources hanging off them.

The desktop edition runs as a single loopback identity, so every integration
test in this suite authenticates as ``system`` — a user the access rules
deliberately wave through. That makes the *denials* invisible to the rest of
the suite: the organization boundary, the membership requirement and the admin
gate are only ever exercised on their permissive branch.

These call the dependency helpers directly with constructed identities, which
is the only way to reach the refusing branch at all. What they protect is the
property that a case, and anything reachable through one, is never handed to a
caller who is outside its organization or absent from its membership.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import models
from app.core.config import get_settings
from app.core.deps import (
    CurrentUser,
    accessible_cases_statement,
    get_current_user,
    require_admin,
    require_case_access,
    require_search_run_access,
    require_target_access,
    user_can_access_case,
)

ACME = "acme"
RIVAL = "rival"


def _user(user_id: str, *, role: str = "analyst", organization: str = ACME) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        email=f"{user_id}@example.test",
        username=user_id,
        role=role,
        organization_id=organization,
    )


async def _persist_user(session, user_id: str, *, role: str = "analyst", organization: str = ACME) -> models.User:
    row = models.User(
        id=user_id,
        email=f"{user_id}@example.test",
        username=user_id,
        hashed_password="not-used-by-these-tests",
        role=role,
        organization_id=organization,
    )
    session.add(row)
    await session.flush()
    return row


async def _persist_case(session, case_id: str, *, owner_id: str | None, organization: str | None) -> models.Case:
    case = models.Case(
        id=case_id,
        owner_id=owner_id,
        organization_id=organization,
        title=f"Case {case_id}",
        legal_basis="Authorized test",
        scope_statement="Bounded scope for the access control suite.",
    )
    session.add(case)
    await session.flush()
    return case


# --- The organization boundary ------------------------------------------------


@pytest.mark.asyncio
async def test_a_case_in_another_organization_is_denied_to_an_administrator(session) -> None:
    """Admin is a role inside one organization, not a key to every organization.

    The admin shortcut is evaluated *after* the organization comparison for
    exactly this reason. Reordering the two — checking ``is_admin`` first, which
    reads as the natural "admins can do anything" shape — would hand every case
    in the installation to any administrator of any tenant.
    """
    await _persist_user(session, "rival-admin", role="admin", organization=RIVAL)
    await _persist_case(session, "acme-case", owner_id=None, organization=ACME)
    await session.commit()

    intruder = _user("rival-admin", role="admin", organization=RIVAL)

    with pytest.raises(HTTPException) as error:
        await require_case_access(session, "acme-case", intruder)

    assert error.value.status_code == 403
    assert await user_can_access_case(session, "acme-case", intruder) is False


@pytest.mark.asyncio
async def test_a_foreign_organization_case_is_absent_from_the_listing(session) -> None:
    """The listing filter and the per-case gate must refuse the same rows.

    A case the direct-id path denies but the listing returns is an enumeration
    leak: the title, the legal basis and the scope statement are all in the list
    response, which is most of what the case is.
    """
    await _persist_case(session, "acme-case", owner_id=None, organization=ACME)
    await _persist_case(session, "rival-case", owner_id=None, organization=RIVAL)
    await session.commit()

    admin = _user("acme-admin", role="admin", organization=ACME)
    listed = set((await session.execute(accessible_cases_statement(admin))).scalars())

    assert "acme-case" in listed
    assert "rival-case" not in listed


# --- Membership ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_analyst_outside_the_membership_is_denied(session) -> None:
    """Sharing an organization is not sharing a case."""
    await _persist_user(session, "owner-user")
    await _persist_user(session, "bystander")
    await _persist_case(session, "owned-case", owner_id="owner-user", organization=ACME)
    await session.commit()

    bystander = _user("bystander")

    with pytest.raises(HTTPException) as error:
        await require_case_access(session, "owned-case", bystander)

    assert error.value.status_code == 403
    assert await user_can_access_case(session, "owned-case", bystander) is False


@pytest.mark.asyncio
async def test_a_membership_row_grants_access_to_a_case_owned_by_someone_else(session) -> None:
    """The membership table is the mechanism for sharing a case; it has to work.

    Paired with the denial above, this is what separates "membership is
    checked" from "everything is denied", which a broken query would also do.
    """
    await _persist_user(session, "owner-user")
    await _persist_user(session, "collaborator")
    await _persist_case(session, "shared-case", owner_id="owner-user", organization=ACME)
    session.add(models.CaseMembership(case_id="shared-case", user_id="collaborator", role="analyst"))
    await session.commit()

    collaborator = _user("collaborator")

    granted = await require_case_access(session, "shared-case", collaborator)

    assert granted.id == "shared-case"
    assert await user_can_access_case(session, "shared-case", collaborator) is True
    listed = set((await session.execute(accessible_cases_statement(collaborator))).scalars())
    assert listed == {"shared-case"}


@pytest.mark.asyncio
async def test_a_membership_in_a_different_case_does_not_travel(session) -> None:
    """A membership grants one case, not the set of cases the owner holds."""
    await _persist_user(session, "owner-user")
    await _persist_user(session, "collaborator")
    await _persist_case(session, "shared-case", owner_id="owner-user", organization=ACME)
    await _persist_case(session, "private-case", owner_id="owner-user", organization=ACME)
    session.add(models.CaseMembership(case_id="shared-case", user_id="collaborator", role="analyst"))
    await session.commit()

    collaborator = _user("collaborator")

    with pytest.raises(HTTPException) as error:
        await require_case_access(session, "private-case", collaborator)

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_the_owner_reaches_their_own_case(session) -> None:
    await _persist_user(session, "owner-user")
    await _persist_case(session, "owned-case", owner_id="owner-user", organization=ACME)
    await session.commit()

    owner = _user("owner-user")

    assert (await require_case_access(session, "owned-case", owner)).id == "owned-case"
    assert await user_can_access_case(session, "owned-case", owner) is True


@pytest.mark.asyncio
async def test_a_missing_case_is_reported_as_missing(session) -> None:
    """404 rather than 403: there is no case here whose existence could leak."""
    with pytest.raises(HTTPException) as error:
        await require_case_access(session, "no-such-case", _user("someone"))

    assert error.value.status_code == 404
    assert await user_can_access_case(session, "no-such-case", _user("someone")) is False


# --- Resources reached through a case -----------------------------------------


@pytest.mark.asyncio
async def test_a_target_in_a_foreign_case_is_refused_rather_than_returned(session) -> None:
    """Targets are named people; the case gate is the only thing guarding them.

    ``require_target_access`` loads the target *first* and then checks the case
    it belongs to. A refactor that returned the row before awaiting the case
    check would leak a full identity record — name, aliases and consent basis —
    to a caller in another organization.
    """
    await _persist_case(session, "rival-case", owner_id=None, organization=RIVAL)
    target = models.TargetProfile(
        case_id="rival-case",
        first_name="Dana",
        last_name="Prospect",
        consent_basis="Authorized test",
    )
    session.add(target)
    await session.commit()

    with pytest.raises(HTTPException) as error:
        await require_target_access(session, target.id, _user("acme-admin", role="admin", organization=ACME))

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_a_missing_target_is_reported_as_missing(session) -> None:
    with pytest.raises(HTTPException) as error:
        await require_target_access(session, "no-such-target", _user("someone"))

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_a_search_run_in_a_foreign_case_is_refused(session) -> None:
    """Search runs carry the queries that were issued against a target."""
    await _persist_case(session, "rival-case", owner_id=None, organization=RIVAL)
    target = models.TargetProfile(
        case_id="rival-case",
        first_name="Dana",
        last_name="Prospect",
        consent_basis="Authorized test",
    )
    session.add(target)
    await session.flush()
    run = models.SearchRun(case_id="rival-case", target_id=target.id, queries=["dana prospect"])
    session.add(run)
    await session.commit()

    with pytest.raises(HTTPException) as error:
        await require_search_run_access(session, run.id, _user("acme-admin", role="admin", organization=ACME))

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_a_missing_search_run_is_reported_as_missing(session) -> None:
    with pytest.raises(HTTPException) as error:
        await require_search_run_access(session, "no-such-run", _user("someone"))

    assert error.value.status_code == 404


# --- The admin gate -----------------------------------------------------------


def test_require_admin_refuses_an_analyst() -> None:
    with pytest.raises(HTTPException) as error:
        require_admin(_user("analyst-user"))

    assert error.value.status_code == 403


def test_require_admin_passes_an_administrator_through_unchanged() -> None:
    admin = _user("admin-user", role="admin")
    assert require_admin(admin) is admin


# --- The loopback identity ----------------------------------------------------


@pytest.mark.asyncio
async def test_the_loopback_system_identity_bypasses_every_case_rule(session) -> None:
    """Single-user desktop mode owns the whole database and must not be filtered.

    Stated explicitly because the rest of this file is about denials: the
    ``is_system`` shortcut is the reason the integration suite sees any data at
    all, and a rule added above it would break every route at once.
    """
    await _persist_case(session, "unowned-case", owner_id=None, organization=None)
    await session.commit()

    system = CurrentUser(
        id="system",
        email="system@oihk-basic.local",
        username="system",
        role="admin",
        organization_id="system",
    )

    assert (await require_case_access(session, "unowned-case", system)).id == "unowned-case"
    assert system.database_user_id is None


# --- Bearer authentication (opt-in deployments) -------------------------------


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/cases", "headers": raw, "query_string": b""})


@pytest.fixture
def auth_enabled(monkeypatch):
    monkeypatch.setenv("OIHK_AUTH_ENABLED", "true")
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_the_role_comes_from_the_stored_user_not_the_token_claim(session, auth_enabled) -> None:
    """A token is proof of identity; it is not a statement of privilege.

    ``create_access_token`` writes the role into the payload, so a token minted
    while an account was an administrator would keep asserting ``admin`` for its
    full lifetime — including after the account was demoted. Reading the role
    back from the user row is what makes a demotion take effect immediately,
    and what keeps a signed-but-stale claim from re-granting it.
    """
    from app.core.security import create_access_token

    await _persist_user(session, "demoted-user", role="analyst")
    await session.commit()

    stale_admin_token = create_access_token("demoted-user", role="admin")
    current = await get_current_user(_request({"Authorization": f"Bearer {stale_admin_token}"}), session)

    assert current.id == "demoted-user"
    assert current.role == "analyst"
    assert current.is_admin is False


@pytest.mark.asyncio
async def test_a_request_without_a_bearer_token_is_unauthenticated(session, auth_enabled) -> None:
    with pytest.raises(HTTPException) as error:
        await get_current_user(_request(), session)

    assert error.value.status_code == 401
    assert error.value.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_a_non_bearer_authorization_scheme_is_not_treated_as_a_token(session, auth_enabled) -> None:
    """A Basic credential is not a bearer token and must not be parsed as one.

    Asserting the *detail* rather than only the status is what gives this test
    teeth: both branches answer 401, so a scheme check that was dropped would
    still refuse the request — just by feeding password material into the token
    parser first and reporting "Invalid token". The distinction that matters is
    that the credential is never decoded at all.
    """
    with pytest.raises(HTTPException) as error:
        await get_current_user(_request({"Authorization": "Basic dXNlcjpwYXNz"}), session)

    assert error.value.status_code == 401
    assert error.value.detail == "Authentication required"


@pytest.mark.asyncio
async def test_a_forged_token_is_rejected_before_the_user_lookup(session, auth_enabled) -> None:
    with pytest.raises(HTTPException) as error:
        await get_current_user(_request({"Authorization": "Bearer not.a.token"}), session)

    assert error.value.status_code == 401
    assert "Invalid token" in error.value.detail


@pytest.mark.asyncio
async def test_a_deactivated_account_cannot_authenticate_with_a_live_token(session, auth_enabled) -> None:
    """Deactivation has to end the session, not wait for the token to expire.

    Tokens here carry a twelve-hour default lifetime and there is no revocation
    list, so the ``is_active`` check is the only thing that stops a disabled
    account from continuing to work for the rest of the day.
    """
    from app.core.security import create_access_token

    row = await _persist_user(session, "suspended-user")
    row.is_active = False
    await session.commit()

    with pytest.raises(HTTPException) as error:
        await get_current_user(
            _request({"Authorization": f"Bearer {create_access_token('suspended-user', role='analyst')}"}),
            session,
        )

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_a_token_for_a_deleted_account_is_rejected(session, auth_enabled) -> None:
    from app.core.security import create_access_token

    with pytest.raises(HTTPException) as error:
        await get_current_user(
            _request({"Authorization": f"Bearer {create_access_token('never-existed', role='admin')}"}),
            session,
        )

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_authentication_disabled_resolves_to_the_loopback_identity(session) -> None:
    """The desktop default: no header, no lookup, one fixed local identity."""
    get_settings.cache_clear()
    current = await get_current_user(_request(), session)

    assert current.id == "system"
    assert current.is_system is True
