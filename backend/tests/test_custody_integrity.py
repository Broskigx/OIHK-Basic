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


@pytest.mark.asyncio
async def test_verifying_a_chain_costs_the_same_number_of_queries_at_any_size(tmp_path):
    """The custody report must not issue one query per sealed item.

    Verification walks the whole chain by construction — stopping early cannot
    prove the chain is intact — so a per-seal lookup made the cost of the
    report grow with the size of the case, and this is the report an analyst
    opens to decide whether the evidence still stands. Measured before the
    fix: 250 seals issued 252 SELECTs in 241 ms.

    Asserting a constant rather than a threshold is deliberate. A time budget
    would be flaky on shared runners, and a generous bound would still pass
    against a reintroduced N+1 at small N; the query count would not.

    What this does *not* catch, stated so nobody trusts it further than it
    goes: a `session.get` put back inside the loop while the batch load still
    runs above it costs nothing, because the identity map already holds every
    row and no SQL is emitted. The property under test is that the batch load
    exists at all — remove it and this goes red.
    """
    from sqlalchemy import event

    async def count_selects_for(seal_count: int) -> int:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / f'chain-{seal_count}.db'}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async with sessions() as session:
            case = models.Case(
                id=f"chain-{seal_count}",
                title="Chain",
                legal_basis="Authorized test",
                scope_statement="Bounded scope for the custody query-count test.",
            )
            session.add(case)
            await session.flush()
            for index in range(seal_count):
                source = models.Source(
                    case_id=case.id,
                    title=f"Source {index}",
                    kind="note",
                    body=f"body {index}",
                    citation=f"cite-{index}",
                )
                session.add(source)
                await session.flush()
                await custody.seal_source(session, source)
            await session.commit()

        selects: list[str] = []

        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def _record(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        async with sessions() as session:
            report = await custody.verify_case_custody(session, f"chain-{seal_count}")

        assert report.sealed_count == seal_count
        assert report.intact, "a freshly sealed chain must verify"
        await engine.dispose()
        return len(selects)

    small = await count_selects_for(3)
    large = await count_selects_for(40)

    assert small == large, f"query count grew with the chain: {small} -> {large}"
