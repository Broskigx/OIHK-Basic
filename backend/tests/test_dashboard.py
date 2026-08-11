from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.deps import CurrentUser
from app.database import Base
from app.routers.dashboard import dashboard_summary
from app.routers.operations import list_audit_events


@pytest.mark.asyncio
async def test_dashboard_summary_uses_authorized_database_rows(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'dashboard.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    analyst = models.User(
        email="analyst@example.test",
        username="analyst",
        hashed_password="not-used",
        role="analyst",
        organization_id="alpha",
    )
    outsider = models.User(
        email="outsider@example.test",
        username="outsider",
        hashed_password="not-used",
        role="analyst",
        organization_id="bravo",
    )
    async with sessions() as session:
        session.add_all([analyst, outsider])
        await session.flush()
        visible = models.Case(
            owner_id=analyst.id,
            organization_id="alpha",
            title="Visible investigation",
            legal_basis="Authorized test",
            scope_statement="Bounded test scope",
            status="active",
        )
        hidden = models.Case(
            owner_id=outsider.id,
            organization_id="bravo",
            title="Hidden investigation",
            legal_basis="Authorized test",
            scope_statement="Separate test scope",
            status="active",
        )
        session.add_all([visible, hidden])
        await session.flush()
        visible_source = models.Source(
            case_id=visible.id,
            title="Visible source",
            kind="file",
            body="source",
        )
        hidden_source = models.Source(
            case_id=hidden.id,
            title="Hidden source",
            kind="file",
            body="source",
        )
        session.add_all([visible_source, hidden_source])
        await session.flush()
        session.add_all(
            [
                models.EvidenceItem(
                    case_id=visible.id,
                    source_id=visible_source.id,
                    original_name="visible.txt",
                    storage_path="managed/visible.txt",
                    size_bytes=7,
                    sha256="a" * 64,
                ),
                models.EvidenceItem(
                    case_id=hidden.id,
                    source_id=hidden_source.id,
                    original_name="hidden.txt",
                    storage_path="managed/hidden.txt",
                    size_bytes=6,
                    sha256="b" * 64,
                ),
                models.AuditEvent(actor="analyst", action="evidence.uploaded", case_id=visible.id),
                models.AuditEvent(actor="outsider", action="evidence.uploaded", case_id=hidden.id),
            ]
        )
        await session.commit()

        current = CurrentUser(
            id=analyst.id,
            email=analyst.email,
            username=analyst.username,
            role=analyst.role,
            organization_id=analyst.organization_id,
        )
        summary = await dashboard_summary(current, session)
        assert summary.counts.active_investigations == 1
        assert summary.counts.registered_evidence == 1
        assert summary.counts.pending_tasks is None
        assert summary.counts.tasks_available is False
        assert [item.title for item in summary.recent_investigations] == ["Visible investigation"]
        assert {item.case_title for item in summary.recent_activity} == {"Visible investigation"}

        activity = await list_audit_events(None, 80, current, session)
        assert [item["case_id"] for item in activity] == [visible.id]

    await engine.dispose()


@pytest.mark.asyncio
async def test_dashboard_empty_state_is_explicit(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'empty-dashboard.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        current = CurrentUser(id="system", email="system@local", username="system", role="admin")
        summary = await dashboard_summary(current, session)
        assert summary.counts.active_investigations == 0
        assert summary.counts.registered_evidence == 0
        assert summary.counts.connected_modules == 0
        assert summary.recent_investigations == []
        assert summary.recent_activity == []
    await engine.dispose()
