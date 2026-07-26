"""Database setup for OIHK Basic — SQLite local storage."""

import sqlite3
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_database_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return
    database_path = make_url(database_url).database
    if not database_path or database_path == ":memory:":
        return
    parent = Path(database_path).parent
    if parent != Path("."):
        parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_ensure_sqlite_database_parent(settings.database_url)
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_integrity(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _installed_schema_version() -> int:
    if not settings.database_url.startswith("sqlite"):
        return 0
    configured = make_url(settings.database_url).database
    if not configured or configured == ":memory:" or not Path(configured).is_file():
        return 0
    connection = sqlite3.connect(configured)
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if not exists:
            return 0
        row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
        return int(row[0]) if row else 0
    finally:
        connection.close()


async def init_db() -> None:
    from app import models  # noqa: F401
    from app.core.update_service import (
        create_verified_backup,
        mark_update_healthy_if_current,
        record_update_state,
    )
    from app.database_migrations import MIGRATIONS, run_migrations

    if not settings.should_create_tables:
        return
    migration_backup = ""
    configured_database = (
        make_url(settings.database_url).database if settings.database_url.startswith("sqlite") else None
    )
    source_exists = bool(
        configured_database and configured_database != ":memory:" and Path(configured_database).is_file()
    )
    if source_exists and _installed_schema_version() < MIGRATIONS[-1].version:
        try:
            backup, _metadata = create_verified_backup(
                target_version=f"schema-{MIGRATIONS[-1].version}",
                kind="migrations",
            )
            migration_backup = str(backup)
        except Exception:
            record_update_state(
                stage="migration_backup_failed",
                error_code="migration_backup_failed",
            )
            raise
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if settings.database_url.startswith("sqlite"):
                await run_migrations(conn)
        if settings.database_url.startswith("sqlite"):
            mark_update_healthy_if_current()
    except Exception:
        record_update_state(
            stage="migration_failed",
            backup_path=migration_backup,
            error_code="migration_failed",
        )
        raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
