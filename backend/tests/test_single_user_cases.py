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
