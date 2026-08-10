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


async def _seed_user(session, *, user_id: str, email: str, username: str, organization_id: str = "org-a", role: str = "analyst") -> models.User:
    user = models.User(
        id=user_id,
        email=email,
        username=username,
        hashed_password="not-a-real-hash",
        role=role,
        organization_id=organization_id,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user


def _as_user(user: models.User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        organization_id=user.organization_id or "default",
    )


async def _seed_case_for(session, user: CurrentUser, title: str) -> models.Case:
    return await cases.create_case_endpoint(
        CaseCreate(title=title, legal_basis="Authorized test", scope_statement="Bounded test scope."),
        user,
        session,
    )


async def _add_run(session, case_id: str, label: str) -> models.TransformRun:
    run = models.TransformRun(
        case_id=case_id,
        entity_id="entity-1",
        entity_label=label,
        entity_type="email",
        transform_id="email_to_domain",
        transform_title="Extract Domain from Email",
        status="completed",
        actor="tester",
    )
    session.add(run)
    await session.commit()
    return run


@pytest.mark.asyncio
async def test_unfiltered_transform_history_is_scoped_to_accessible_cases(tmp_path):
    engine, sessions = await _make_engine(tmp_path)
    async with sessions() as session:
        user_a = await _seed_user(session, user_id="user-a", email="a@corp.example", username="alice", organization_id="org-a")
        user_b = await _seed_user(session, user_id="user-b", email="b@corp.example", username="bob", organization_id="org-b")
        case_a = await _seed_case_for(session, _as_user(user_a), "Alice case")
        case_b = await _seed_case_for(session, _as_user(user_b), "Bob case")
        run_a = await _add_run(session, case_a.id, "alice@corp.example")
        run_b = await _add_run(session, case_b.id, "bob@corp.example")

        listed_a = await transforms.list_transform_runs(
            case_id=None, limit=20, current=_as_user(user_a), session=session
        )
        assert [r.id for r in listed_a] == [run_a.id]
        assert all(r.case_id == case_a.id for r in listed_a)

        listed_b = await transforms.list_transform_runs(
            case_id=None, limit=20, current=_as_user(user_b), session=session
        )
        assert [r.id for r in listed_b] == [run_b.id]
        assert all(r.case_id == case_b.id for r in listed_b)
    await engine.dispose()


@pytest.mark.asyncio
async def test_transform_history_explicit_case_id_still_enforces_authorization(tmp_path):
    engine, sessions = await _make_engine(tmp_path)
    async with sessions() as session:
        user_a = await _seed_user(session, user_id="user-a", email="a@corp.example", username="alice", organization_id="org-a")
        user_b = await _seed_user(session, user_id="user-b", email="b@corp.example", username="bob", organization_id="org-b")
        case_a = await _seed_case_for(session, _as_user(user_a), "Alice case")
        case_b = await _seed_case_for(session, _as_user(user_b), "Bob case")
        await _add_run(session, case_a.id, "alice@corp.example")
        await _add_run(session, case_b.id, "bob@corp.example")

        with pytest.raises(HTTPException) as denied:
            await transforms.list_transform_runs(
                case_id=case_b.id, limit=20, current=_as_user(user_a), session=session
            )
        assert denied.value.status_code == 403
    await engine.dispose()


@pytest.mark.asyncio
async def test_transform_history_uses_membership_and_owner_rules(tmp_path):
    engine, sessions = await _make_engine(tmp_path)
    async with sessions() as session:
        owner = await _seed_user(session, user_id="owner", email="owner@corp.example", username="owner", organization_id="org-x")
        member = await _seed_user(session, user_id="member", email="member@corp.example", username="member", organization_id="org-x")
        outsider = await _seed_user(session, user_id="outsider", email="out@corp.example", username="out", organization_id="org-y")
        case_x = await _seed_case_for(session, _as_user(owner), "Shared org case")
        case_y = await _seed_case_for(session, _as_user(outsider), "Foreign org case")
        session.add(models.CaseMembership(case_id=case_x.id, user_id=member.id, role="analyst", organization_id="org-x"))
        await session.commit()
        run_x = await _add_run(session, case_x.id, "shared@corp.example")
        await _add_run(session, case_y.id, "foreign@corp.example")

        listed_member = await transforms.list_transform_runs(
            case_id=None, limit=20, current=_as_user(member), session=session
        )
        assert [r.id for r in listed_member] == [run_x.id]

        listed_outsider = await transforms.list_transform_runs(
            case_id=None, limit=20, current=_as_user(outsider), session=session
        )
        assert [r.case_id for r in listed_outsider] == [case_y.id]
    await engine.dispose()


@pytest.mark.asyncio
async def test_transform_history_keeps_limit_and_ordering(tmp_path):
    engine, sessions = await _make_engine(tmp_path)
    async with sessions() as session:
        user = await _seed_user(session, user_id="user-a", email="a@corp.example", username="alice", organization_id="org-a")
        case = await _seed_case_for(session, _as_user(user), "Limit case")
        runs = [await _add_run(session, case.id, f"run-{index}") for index in range(5)]
        listed = await transforms.list_transform_runs(case_id=None, limit=3, current=_as_user(user), session=session)
        assert len(listed) == 3
        assert [r.id for r in listed] == [run.id for run in reversed(runs)][:3]
    await engine.dispose()
