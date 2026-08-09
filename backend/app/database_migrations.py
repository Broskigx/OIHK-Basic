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
    Migration(
        5,
        "transform_run_history",
        (),
    ),
    Migration(
        6,
        "system_link_v1_control_plane",
        (
            """CREATE TABLE IF NOT EXISTS system_link_installations (
                id VARCHAR(36) PRIMARY KEY,
                protocol_version VARCHAR(20) NOT NULL,
                public_key VARCHAR(120) NOT NULL,
                fingerprint VARCHAR(64) NOT NULL UNIQUE,
                key_storage VARCHAR(40) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS system_link_modules (
                module_id VARCHAR(120) PRIMARY KEY,
                product_name VARCHAR(160) NOT NULL,
                module_version VARCHAR(80) NOT NULL,
                protocol_version VARCHAR(20) NOT NULL,
                manifest_schema_version INTEGER NOT NULL,
                module_public_key VARCHAR(120) NOT NULL,
                module_fingerprint VARCHAR(64) NOT NULL,
                manifest JSON NOT NULL,
                manifest_sha256 VARCHAR(64) NOT NULL,
                manifest_signature VARCHAR(160) NOT NULL,
                package_root TEXT NOT NULL,
                package_sha256 VARCHAR(64) NOT NULL,
                lifecycle JSON NOT NULL,
                state VARCHAR(32) NOT NULL DEFAULT 'LINKED_OFF',
                enabled BOOLEAN NOT NULL DEFAULT 1,
                startup_policy VARCHAR(32) NOT NULL DEFAULT 'manual',
                last_error_code VARCHAR(80) NOT NULL DEFAULT '',
                last_error_detail VARCHAR(500) NOT NULL DEFAULT '',
                paired_at DATETIME NOT NULL,
                last_handshake_at DATETIME,
                last_health_at DATETIME,
                revoked_at DATETIME,
                crash_count INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS ix_system_link_modules_state ON system_link_modules (state)",
            """CREATE TABLE IF NOT EXISTS system_link_capability_grants (
                id VARCHAR(36) PRIMARY KEY,
                module_id VARCHAR(120) NOT NULL REFERENCES system_link_modules(module_id) ON DELETE CASCADE,
                capability VARCHAR(100) NOT NULL,
                manifest_sha256 VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL,
                revoked_at DATETIME,
                CONSTRAINT uq_system_link_module_capability UNIQUE (module_id, capability)
            )""",
            "CREATE INDEX IF NOT EXISTS ix_system_link_capability_grants_module_id ON system_link_capability_grants (module_id)",
            """CREATE TABLE IF NOT EXISTS system_link_pairing_nonces (
                id VARCHAR(36) PRIMARY KEY,
                link_key_hash VARCHAR(64) NOT NULL,
                challenge VARCHAR(160) NOT NULL,
                expires_at DATETIME NOT NULL,
                used_at DATETIME,
                approved_at DATETIME,
                pending_module JSON NOT NULL DEFAULT '{}',
                created_at DATETIME NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS ix_system_link_pairing_nonces_expires_at ON system_link_pairing_nonces (expires_at)",
            """CREATE TABLE IF NOT EXISTS system_link_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id VARCHAR(120),
                action VARCHAR(120) NOT NULL,
                payload JSON NOT NULL DEFAULT '{}',
                created_at DATETIME NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS ix_system_link_events_module_id ON system_link_events (module_id)",
            "CREATE INDEX IF NOT EXISTS ix_system_link_events_created_at ON system_link_events (created_at)",
        ),
    ),
    Migration(
        7,
        "system_link_replay_protection",
        (
            """CREATE TABLE IF NOT EXISTS system_link_replay_nonces (
                id VARCHAR(36) PRIMARY KEY,
                module_id VARCHAR(120) NOT NULL REFERENCES system_link_modules(module_id) ON DELETE CASCADE,
                nonce VARCHAR(128) NOT NULL,
                expires_at DATETIME NOT NULL,
                created_at DATETIME NOT NULL,
                CONSTRAINT uq_system_link_module_nonce UNIQUE (module_id, nonce)
            )""",
            "CREATE INDEX IF NOT EXISTS ix_system_link_replay_nonces_module_id ON system_link_replay_nonces (module_id)",
            "CREATE INDEX IF NOT EXISTS ix_system_link_replay_nonces_expires_at ON system_link_replay_nonces (expires_at)",
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
