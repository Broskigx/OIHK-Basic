"""Representative 0.1.0 -> 0.1.1 data-preservation upgrade smoke."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from app.core import update_service
from app.database_migrations import run_migrations
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_upgrade_fixture_preserves_all_local_data_categories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "oihk-basic.db"
    storage = tmp_path / "storage" / "evidence"
    storage.mkdir(parents=True)
    evidence_file = storage / "captured.bin"
    evidence_file.write_bytes(b"immutable evidence payload")
    evidence_digest = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
    previous_backup = tmp_path / "backups" / "manual" / "previous.sqlite3"
    previous_backup.parent.mkdir(parents=True)
    previous_backup.write_bytes(b"previous backup stays untouched")

    connection = sqlite3.connect(database)
    connection.executescript(
        f"""
        PRAGMA journal_mode=WAL;
        CREATE TABLE cases (id TEXT PRIMARY KEY, title TEXT NOT NULL);
        CREATE TABLE entities (id TEXT PRIMARY KEY, case_id TEXT, label TEXT);
        CREATE TABLE relationships (id TEXT PRIMARY KEY, case_id TEXT, source_id TEXT, target_id TEXT, label TEXT);
        CREATE TABLE report_documents (id TEXT PRIMARY KEY, case_id TEXT, content TEXT);
        CREATE TABLE evidence_items (id TEXT PRIMARY KEY, case_id TEXT, storage_path TEXT, sha256 TEXT);
        CREATE TABLE assistant_conversations (id TEXT PRIMARY KEY, case_id TEXT, title TEXT);
        CREATE TABLE assistant_messages (id TEXT PRIMARY KEY, conversation_id TEXT, content TEXT);
        CREATE TABLE application_settings (id TEXT PRIMARY KEY, general TEXT, privacy TEXT);
        CREATE TABLE audit_events (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT);
        CREATE TABLE sources (id TEXT PRIMARY KEY, case_id TEXT, title TEXT, url TEXT);
        INSERT INTO cases VALUES ('case-1', 'Upgrade fixture');
        INSERT INTO entities VALUES ('entity-1', 'case-1', 'Eliot Alderson');
        INSERT INTO relationships VALUES ('relation-1', 'case-1', 'entity-1', 'entity-2', 'linked');
        INSERT INTO report_documents VALUES ('report-1', 'case-1', 'preserved report');
        INSERT INTO evidence_items VALUES ('evidence-1', 'case-1', '{evidence_file.as_posix()}', '{evidence_digest}');
        INSERT INTO assistant_conversations VALUES ('conversation-1', 'case-1', 'local copilot');
        INSERT INTO assistant_messages VALUES ('message-1', 'conversation-1', 'preserved history');
        INSERT INTO application_settings VALUES ('settings-1', '{{"check_updates":true}}', '{{"telemetry":false}}');
        INSERT INTO audit_events VALUES ('audit-1', '2026-01-01T00:00:00Z', '{{"action":"created"}}');
        INSERT INTO sources VALUES ('source-1', 'case-1', 'public source', 'https://example.invalid');
        """
    )
    connection.commit()
    connection.close()

    update_backups = tmp_path / "backups" / "pre-update"
    update_backups.mkdir(parents=True)
    monkeypatch.setattr(update_service, "database_path", lambda: database)
    monkeypatch.setattr(
        update_service, "backup_directory", lambda _kind="pre-update": update_backups
    )
    backup, metadata = update_service.create_verified_backup(
        source_version="0.1.0",
        target_version="0.1.1",
    )

    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    try:
        async with engine.begin() as async_connection:
            await run_migrations(async_connection)
    finally:
        await engine.dispose()

    upgraded = sqlite3.connect(database)
    restored = sqlite3.connect(backup)
    try:
        tables = (
            "cases",
            "entities",
            "relationships",
            "report_documents",
            "evidence_items",
            "assistant_conversations",
            "assistant_messages",
            "application_settings",
            "audit_events",
            "sources",
        )
        for table in tables:
            assert (
                upgraded.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 1
            )
            assert (
                restored.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 1
            )
        assert upgraded.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert metadata.source_version == "0.1.0"
        assert metadata.target_version == "0.1.1"
        assert evidence_digest == hashlib.sha256(evidence_file.read_bytes()).hexdigest()
        assert previous_backup.read_bytes() == b"previous backup stays untouched"
    finally:
        upgraded.close()
        restored.close()
