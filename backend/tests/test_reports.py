from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.deps import CurrentUser
from app.database import Base
from app.routers import reports
from app.schemas import ReportGenerateRequest


@pytest.mark.asyncio
async def test_report_generation_persists_ordered_evidence_backed_document(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reports.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    current = CurrentUser(id="system", email="system@local", username="system", role="admin")
    async with sessions() as session:
        case = models.Case(
            title="Safety <review>",
            summary="Only verified records.",
            legal_basis="Authorized research",
            scope_statement="Local test scope",
        )
        session.add(case)
        await session.flush()
        session.add(
            models.Source(
                case_id=case.id,
                title="Primary source",
                kind="document",
                body="Preserved body",
                citation="sha256:test",
                reliability=0.95,
            )
        )
        await session.commit()

        document = await reports.generate_report(
            case.id,
            ReportGenerateRequest(
                title="Review <script>alert(1)</script>",
                format="html",
                sections=["investigation", "sources", "methodology", "limitations"],
                methodology="Review preserved records.",
                limitations="No unsupported attribution.",
            ),
            current,
            session,
        )

        assert document.sections == ["investigation", "sources", "methodology", "limitations"]
        assert "<script>" not in document.content
        assert "&lt;script&gt;" in document.content
        assert "Primary source" in document.content
        assert "default-src 'none'" in document.content
        assert (await reports.list_reports(case.id, current, session))[0].id == document.id

    await engine.dispose()
