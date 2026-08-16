from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.deps import CurrentUser
from app.database import Base
from app.routers import cases
from app.schemas import CaseCreate


@pytest.mark.asyncio
async def test_system_user_creates_fk_safe_unowned_case(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'single-user.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    current = CurrentUser(id="system", email="system@local", username="system", role="admin")
    async with sessions() as session:
        created = await cases.create_case_endpoint(
            CaseCreate(
                title="Local investigation",
                legal_basis="Authorized test",
                scope_statement="Bounded local single-user test scope.",
            ),
            current,
            session,
        )
        assert created.owner_id is None
        assert (await cases.list_cases(current, session))[0].id == created.id

    await engine.dispose()


@pytest.mark.asyncio
async def test_a_case_without_an_organization_is_listed_and_reachable_alike(session) -> None:
    """The listing filter and the per-case check must normalise NULL the same way.

    ``require_case_access`` reads a missing organization as ``"default"`` and
    grants on it. In SQL a NULL equals nothing, so a bare comparison in the
    listing statement hid precisely the rows the direct-id path admitted: the
    same case, present or absent depending on which route you arrived by. A
    record that cannot be listed also cannot be found again to be deleted.
    """
    from app import models
    from app.core.deps import accessible_cases_statement, user_can_access_case

    admin = CurrentUser(id="u-admin", email="admin@local", username="admin", role="admin")
    session.add(
        models.Case(
            id="case-without-org",
            owner_id=None,
            organization_id=None,
            title="Case carrying no organization",
            legal_basis="Authorized test",
            scope_statement="Bounded scope for the organization normalisation test.",
        )
    )
    await session.commit()

    listed = set((await session.execute(accessible_cases_statement(admin))).scalars())

    assert "case-without-org" in listed
    assert await user_can_access_case(session, "case-without-org", admin) is True
