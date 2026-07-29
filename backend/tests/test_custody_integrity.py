from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.database import Base
from app.services import custody


@pytest.mark.asyncio
async def test_file_seal_rehashes_managed_content_and_detects_truncation(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    storage.mkdir()
    evidence = storage / "evidence.bin"
    evidence.write_bytes(b"original evidence")
    monkeypatch.setattr(
        custody,
        "get_settings",
        lambda: SimpleNamespace(
            custody_signing_key="test-signing-key",
            custody_key_id="test-key",
            effective_storage_dir=str(storage),
        ),
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'custody.db').as_posix()}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            case = models.Case(
                title="Custody case",
                legal_basis="Authorized review",
                scope_statement="Bounded public evidence review",
            )
            session.add(case)
            await session.flush()
            source = models.Source(
                case_id=case.id,
                title="Evidence",
                kind="managed_evidence",
                body="hash metadata",
            )
            session.add(source)
            await session.flush()
            seal = await custody.seal_source(
                session,
                source,
                storage_path=str(evidence),
            )
            await session.commit()

            intact = await custody.verify_case_custody(session, case.id)
            assert intact.intact is True
            assert intact.entries[0].content_ok is True
            assert seal.content_sha256 == custody.hashlib.sha256(b"original evidence").hexdigest()
            assert seal.size_bytes == len(b"original evidence")

            evidence.write_bytes(b"tampered evidence")
            tampered = await custody.verify_case_custody(session, case.id)
            assert tampered.intact is False
            assert tampered.first_broken_sequence == 1
            assert tampered.entries[0].content_ok is False

            await session.delete(seal)
            await session.commit()
            truncated = await custody.verify_case_custody(session, case.id)
            assert truncated.intact is False
            assert truncated.first_broken_sequence == 1
    finally:
        await engine.dispose()
