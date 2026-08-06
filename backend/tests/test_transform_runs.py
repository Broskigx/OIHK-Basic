from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.deps import CurrentUser
from app.database import Base
from app.routers import cases, transforms
from app.schemas import CaseCreate, TransformRunRequest
from app.transforms.registry import registry


async def _make_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'transform-runs.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions


def _system_user() -> CurrentUser:
    return CurrentUser(id="system", email="system@local", username="system", role="admin")


async def _seed_case_with_entity(session) -> tuple[models.Case, models.Entity]:
    case = await cases.create_case_endpoint(
        CaseCreate(
            title="Transform test case",
            legal_basis="Authorized test",
            scope_statement="Bounded test scope.",
        ),
        _system_user(),
        session,
    )
    entity = models.Entity(case_id=case.id, type="email", value="jane@corp.example", display="jane@corp.example")
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return case, entity


@pytest.mark.asyncio
async def test_completed_run_is_recorded_and_listed(tmp_path):
    engine, sessions = await _make_engine(tmp_path)
    async with sessions() as session:
        case, entity = await _seed_case_with_entity(session)
        result = await transforms.run_transform(
            "email_to_domain", TransformRunRequest(entity_id=entity.id), _system_user(), session
        )
        assert result.new_nodes  # the domain entity was extracted

        rows = list((await session.execute(select(models.TransformRun))).scalars().all())
        assert len(rows) == 1
        run = rows[0]
        assert run.status == "completed"
        assert run.transform_id == "email_to_domain"
        assert run.transform_title == "Extract Domain from Email"
        assert run.entity_id == entity.id
        assert run.case_id == case.id
        assert run.new_nodes == len(result.new_nodes)

        listed = await transforms.list_transform_runs(case_id=None, limit=20, current=_system_user(), session=session)
        assert [r.id for r in listed] == [run.id]
        listed_case = await transforms.list_transform_runs(
            case_id=case.id, limit=20, current=_system_user(), session=session
        )
        assert [r.id for r in listed_case] == [run.id]
    await engine.dispose()


@pytest.mark.asyncio
async def test_failed_run_is_recorded_with_detail(tmp_path):
    engine, sessions = await _make_engine(tmp_path)
    async with sessions() as session:
        _, entity = await _seed_case_with_entity(session)

        async def _boom(_session, *, entity):
            raise RuntimeError("boom")

        spec = registry.get("email_to_domain")
        original_handler = spec.handler
        spec.handler = _boom
        try:
            with pytest.raises(HTTPException) as excinfo:
                await transforms.run_transform(
                    "email_to_domain", TransformRunRequest(entity_id=entity.id), _system_user(), session
                )
        finally:
            spec.handler = original_handler
        assert excinfo.value.status_code == 400

        rows = list((await session.execute(select(models.TransformRun))).scalars().all())
        assert len(rows) == 1
        assert rows[0].status == "failed"
        assert "boom" in rows[0].detail
    await engine.dispose()
