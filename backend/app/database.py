"""Database setup for OIHK Basic — SQLite local storage."""

import shutil
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Connection, make_url
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


def _backup_sqlite_before_schema_v2() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    database = make_url(settings.database_url).database
    if not database or database == ":memory:":
        return
    source = Path(database)
    backup = source.with_suffix(source.suffix + ".pre-v2.bak")
    if source.is_file() and not backup.exists():
        shutil.copy2(source, backup)


async def _migrate_sqlite_schema(conn: Connection) -> None:
    """Apply additive, backup-safe changes for databases created before v2."""
    if not settings.database_url.startswith("sqlite"):
        return
    rows = await conn.exec_driver_sql("PRAGMA table_info(cases)")
    columns = {row[1] for row in rows}
    additions = {
        "priority": "VARCHAR(20) NOT NULL DEFAULT 'normal'",
        "tags": "JSON NOT NULL DEFAULT '[]'",
        "notes": "TEXT NOT NULL DEFAULT ''",
        "graph_config": "JSON NOT NULL DEFAULT '{}'",
        "archived_at": "DATETIME",
    }
    for name, definition in additions.items():
        if name not in columns:
            await conn.exec_driver_sql(f"ALTER TABLE cases ADD COLUMN {name} {definition}")


async def init_db() -> None:
    from app import models  # noqa: F401

    if not settings.should_create_tables:
        return
    _backup_sqlite_before_schema_v2()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_sqlite_schema(conn)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
