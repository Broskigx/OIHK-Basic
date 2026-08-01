"""Small, deterministic migration runner for the embedded SQLite database."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncConnection


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        source = f"{self.version}:{self.name}:" + "\n".join(self.statements)
        return hashlib.sha256(source.encode()).hexdigest()


MIGRATIONS = (
    Migration(1, "baseline", ()),
    Migration(
        2,
        "cases_additive_metadata",
        (
            "ALTER TABLE cases ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'normal'",
            "ALTER TABLE cases ADD COLUMN tags JSON NOT NULL DEFAULT '[]'",
            "ALTER TABLE cases ADD COLUMN notes TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cases ADD COLUMN graph_config JSON NOT NULL DEFAULT '{}'",
            "ALTER TABLE cases ADD COLUMN archived_at DATETIME",
        ),
    ),
    Migration(
        3,
        "update_readiness_indexes",
        ("CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events (created_at)",),
    ),
    Migration(
        4,
        "assistant_conversation_model_settings",
        (
            "ALTER TABLE assistant_conversations ADD COLUMN model VARCHAR(240) NOT NULL DEFAULT ''",
            "ALTER TABLE assistant_conversations ADD COLUMN settings JSON NOT NULL DEFAULT '{}'",
        ),
    ),
)

# Migration version → table whose ALTER ADD COLUMN statements must be guarded so
# they are skipped when the column already exists (fresh databases created via
# ``Base.metadata.create_all`` already contain the new columns).
_ALTER_GUARD_TABLES: dict[int, str] = {
    2: "cases",
    4: "assistant_conversations",
}


async def _table_columns(conn: AsyncConnection, table: str) -> set[str]:
    result = await conn.exec_driver_sql(f'PRAGMA table_info("{table}")')
    return {str(row[1]) for row in result}


async def _table_exists(conn: AsyncConnection, table: str) -> bool:
    result = await conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return result.scalar() is not None


async def run_migrations(conn: AsyncConnection) -> int:
    await conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    rows = await conn.exec_driver_sql("SELECT version, name, checksum FROM schema_migrations ORDER BY version")
    applied = {int(row[0]): (str(row[1]), str(row[2])) for row in rows}

    for migration in MIGRATIONS:
        previous = applied.get(migration.version)
        if previous:
            if previous != (migration.name, migration.checksum):
                raise MigrationError(f"Migration {migration.version} metadata does not match the installed database.")
            continue

        guard_table = _ALTER_GUARD_TABLES.get(migration.version)
        try:
            if guard_table and not await _table_exists(conn, guard_table):
                # The table does not exist in this schema (a legacy database
                # that predates the feature). The table and its columns are
                # created fresh by ``Base.metadata.create_all`` on the next
                # startup, so there is nothing to alter here.
                statements: tuple[str, ...] = ()
            else:
                existing_columns = (
                    await _table_columns(conn, guard_table) if guard_table else set()
                )
                statements = tuple(
                    statement
                    for statement in migration.statements
                    if not (
                        guard_table
                        and " ADD COLUMN " in statement
                        and statement.split(" ADD COLUMN ", 1)[1].split(" ", 1)[0]
                        in existing_columns
                    )
                )
            for statement in statements:
                await conn.exec_driver_sql(statement)
            await conn.exec_driver_sql(
                "INSERT INTO schema_migrations(version, name, checksum) VALUES (?, ?, ?)",
                (migration.version, migration.name, migration.checksum),
            )
        except Exception as exc:
            raise MigrationError(f"Migration {migration.version} ({migration.name}) failed.") from exc

    return MIGRATIONS[-1].version
