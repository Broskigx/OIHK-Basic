"""Updater backup, migration, and write-gate safety tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import update_service
from app.core.update_service import (
    BackupMetadata,
    UpdateCoordinator,
    UpdatePreparationError,
)
from app.database_migrations import MIGRATIONS, MigrationError, run_migrations


def test_verified_backup_has_integrity_hash_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "source.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT
        );
        INSERT INTO schema_migrations VALUES (3, 'ready', 'checksum', CURRENT_TIMESTAMP);
        CREATE TABLE cases (id TEXT PRIMARY KEY, title TEXT NOT NULL);
        INSERT INTO cases VALUES ('case-1', 'Preserved investigation');
        """
    )
    connection.commit()
    connection.close()

    backup_root = tmp_path / "backups"
    monkeypatch.setattr(update_service, "database_path", lambda: database)
    monkeypatch.setattr(
        update_service, "backup_directory", lambda _kind="pre-update": backup_root
    )
    backup_root.mkdir()

    backup, metadata = update_service.create_verified_backup(target_version="0.1.1")
    assert metadata.schema_version == 3
    assert metadata.integrity_check == "ok"
    assert metadata.sha256 == hashlib.sha256(backup.read_bytes()).hexdigest()
    persisted = json.loads(
        backup.with_suffix(".metadata.json").read_text(encoding="utf-8")
    )
    assert persisted["sha256"] == metadata.sha256
    restored = sqlite3.connect(backup)
    try:
        assert (
            restored.execute("SELECT title FROM cases").fetchone()[0]
            == "Preserved investigation"
        )
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        restored.close()


def test_backup_failure_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        update_service, "database_path", lambda: tmp_path / "missing.sqlite3"
    )
    with pytest.raises(UpdatePreparationError) as failure:
        update_service.create_verified_backup(target_version="0.1.1")
    assert failure.value.code == "database_missing"
    assert str(tmp_path) not in str(failure.value)


@pytest.mark.asyncio
async def test_migrations_upgrade_legacy_schema_without_losing_data(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    legacy = sqlite3.connect(database)
    legacy.executescript(
        """
        CREATE TABLE cases (id TEXT PRIMARY KEY, title TEXT NOT NULL);
        INSERT INTO cases VALUES ('case-1', 'Legacy case');
        CREATE TABLE audit_events (id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        INSERT INTO audit_events VALUES ('audit-1', '2026-01-01T00:00:00Z');
        """
    )
    legacy.close()
    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    try:
        async with engine.begin() as connection:
            version = await run_migrations(connection)
        assert version == MIGRATIONS[-1].version
    finally:
        await engine.dispose()

    migrated = sqlite3.connect(database)
    try:
        columns = {row[1] for row in migrated.execute("PRAGMA table_info(cases)")}
        assert {"priority", "tags", "notes", "graph_config", "archived_at"} <= columns
        assert (
            migrated.execute("SELECT title FROM cases WHERE id='case-1'").fetchone()[0]
            == "Legacy case"
        )
        assert migrated.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[
            0
        ] == len(MIGRATIONS)
    finally:
        migrated.close()


@pytest.mark.asyncio
async def test_migration_checksum_mismatch_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "mismatch.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE cases (id TEXT PRIMARY KEY, title TEXT NOT NULL);
        CREATE TABLE audit_events (id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO schema_migrations(version, name, checksum) VALUES (1, 'baseline', 'tampered');
        """
    )
    connection.close()
    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    try:
        with pytest.raises(MigrationError):
            async with engine.begin() as async_connection:
                await run_migrations(async_connection)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_gate_reopens_after_safe_deferral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup.sqlite3"
    backup.write_bytes(b"sqlite")
    metadata = BackupMetadata(
        backup_id="backup-id",
        created_at="2026-01-01T00:00:00Z",
        source_version="0.1.0",
        target_version="0.1.1",
        schema_version=3,
        database_bytes=6,
        sha256="a" * 64,
        integrity_check="ok",
        backup_file=backup.name,
    )
    monkeypatch.setattr(
        update_service, "create_verified_backup", lambda **_kwargs: (backup, metadata)
    )
    monkeypatch.setattr(update_service, "record_update_state", lambda **_kwargs: None)
    coordinator = UpdateCoordinator()

    token, _path, _metadata = await coordinator.prepare("0.1.1", "alpha")
    assert len(token) >= 32
    async with coordinator.mutation() as accepted:
        assert accepted is False
    await coordinator.resume()
    async with coordinator.mutation() as accepted:
        assert accepted is True


@pytest.mark.asyncio
async def test_shutdown_token_is_single_use_and_channels_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup.sqlite3"
    backup.write_bytes(b"sqlite")
    metadata = BackupMetadata(
        backup_id="backup-id",
        created_at="2026-01-01T00:00:00Z",
        source_version="0.1.0",
        target_version="0.1.1",
        schema_version=3,
        database_bytes=6,
        sha256="a" * 64,
        integrity_check="ok",
        backup_file=backup.name,
    )
    monkeypatch.setattr(
        update_service, "create_verified_backup", lambda **_kwargs: (backup, metadata)
    )
    monkeypatch.setattr(update_service, "record_update_state", lambda **_kwargs: None)
    coordinator = UpdateCoordinator()

    with pytest.raises(UpdatePreparationError) as unsupported:
        await coordinator.prepare("0.1.1", "nightly")
    assert unsupported.value.code == "invalid_channel"

    token, _path, _metadata = await coordinator.prepare("0.1.1", "alpha")
    assert await coordinator.consume_shutdown_token(token) is True
    assert await coordinator.consume_shutdown_token(token) is False


@pytest.mark.asyncio
async def test_cancelling_during_backup_keeps_writes_drained_until_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = tmp_path / "backup.sqlite3"
    backup.write_bytes(b"sqlite")
    metadata = BackupMetadata(
        backup_id="backup-id",
        created_at="2026-01-01T00:00:00Z",
        source_version="0.1.0",
        target_version="0.1.1",
        schema_version=3,
        database_bytes=6,
        sha256="a" * 64,
        integrity_check="ok",
        backup_file=backup.name,
    )
    started = threading.Event()
    release = threading.Event()

    def slow_backup(**_kwargs):
        started.set()
        assert release.wait(timeout=5)
        return backup, metadata

    monkeypatch.setattr(update_service, "create_verified_backup", slow_backup)
    monkeypatch.setattr(update_service, "record_update_state", lambda **_kwargs: None)
    coordinator = UpdateCoordinator()
    preparation = asyncio.create_task(coordinator.prepare("0.1.1", "alpha"))
    assert await asyncio.to_thread(started.wait, 2)

    await coordinator.resume()
    async with coordinator.mutation() as accepted:
        assert accepted is False
    release.set()
    with pytest.raises(UpdatePreparationError) as cancelled:
        await preparation
    assert cancelled.value.code == "preparation_cancelled"
    async with coordinator.mutation() as accepted:
        assert accepted is True
