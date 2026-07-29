"""Local update preparation, verified SQLite backups, and recovery metadata."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.version import PRODUCT_VERSION

logger = logging.getLogger("oihk.updater")
SAFE_UPDATE_CHANNELS = {"alpha", "beta", "stable"}


class UpdatePreparationError(RuntimeError):
    """A sanitized, user-actionable update preparation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BackupMetadata:
    backup_id: str
    created_at: str
    source_version: str
    target_version: str
    schema_version: int
    database_bytes: int
    sha256: str
    integrity_check: str
    backup_file: str


def database_path() -> Path:
    url = get_settings().database_url
    if not url.startswith("sqlite"):
        raise UpdatePreparationError("unsupported_database", "Automatic updates require the local SQLite runtime.")
    configured = make_url(url).database
    if not configured or configured == ":memory:":
        raise UpdatePreparationError("unsupported_database", "The current database has no persistent file.")
    return Path(configured).resolve()


def data_directory() -> Path:
    path = database_path().parent
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_directory(kind: str = "pre-update") -> Path:
    if kind not in {"pre-update", "migrations"}:
        raise ValueError("Unsupported backup kind")
    path = data_directory() / "backups" / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def recovery_file() -> Path:
    return data_directory() / "updates" / "last-update.json"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def record_update_state(
    *,
    stage: str,
    source_version: str = PRODUCT_VERSION,
    target_version: str = "",
    backup_path: str = "",
    error_code: str = "",
) -> None:
    """Persist only recovery facts; never case data, credentials, or raw exception text."""
    payload = {
        "stage": stage,
        "source_version": source_version,
        "target_version": target_version,
        "backup_path": backup_path,
        "error_code": error_code,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _atomic_json(recovery_file(), payload)
    logger.info(
        "update_stage=%s source_version=%s target_version=%s error_code=%s",
        stage,
        source_version,
        target_version or "unknown",
        error_code or "none",
    )


def read_recovery_state() -> dict[str, Any] | None:
    path = recovery_file()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "stage": "error",
            "source_version": PRODUCT_VERSION,
            "target_version": "",
            "backup_path": "",
            "error_code": "recovery_metadata_invalid",
            "updated_at": "",
        }
    allowed = {"stage", "source_version", "target_version", "backup_path", "error_code", "updated_at"}
    return {key: payload.get(key, "") for key in allowed}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_version(connection: sqlite3.Connection) -> int:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if not exists:
        return 0
    row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    return int(row[0]) if row else 0


def create_verified_backup(
    *,
    target_version: str,
    kind: str = "pre-update",
    source_version: str = PRODUCT_VERSION,
) -> tuple[Path, BackupMetadata]:
    """Create an online SQLite backup and verify both integrity and SHA-256."""
    source_path = database_path()
    if not source_path.is_file():
        raise UpdatePreparationError("database_missing", "No local database exists to back up.")

    backup_id = secrets.token_hex(12)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = (
        backup_directory(kind) / f"oihk-basic-{source_version}-to-{target_version}-{stamp}-{backup_id}.sqlite3"
    )
    partial = destination.with_suffix(".partial")
    partial.unlink(missing_ok=True)

    try:
        source = sqlite3.connect(source_path, timeout=30)
        target = sqlite3.connect(partial)
        try:
            source.execute("PRAGMA busy_timeout=30000")
            checkpoint = source.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint and int(checkpoint[0]) != 0:
                raise UpdatePreparationError(
                    "database_busy",
                    "The database is still busy and could not be checkpointed safely.",
                )
            schema_version = _schema_version(source)
            source.backup(target, pages=256, sleep=0.05)
            target.commit()
        finally:
            target.close()
            source.close()

        verification = sqlite3.connect(partial)
        try:
            quick = str(verification.execute("PRAGMA quick_check").fetchone()[0])
            integrity = str(verification.execute("PRAGMA integrity_check").fetchone()[0])
            if quick.lower() != "ok" or integrity.lower() != "ok":
                raise UpdatePreparationError("backup_integrity_failed", "The pre-update backup failed verification.")
        finally:
            verification.close()

        partial.replace(destination)
        digest = _sha256(destination)
        if len(digest) != 64 or destination.stat().st_size <= 0:
            raise UpdatePreparationError("backup_digest_failed", "The pre-update backup checksum is invalid.")
        metadata = BackupMetadata(
            backup_id=backup_id,
            created_at=datetime.now(UTC).isoformat(),
            source_version=source_version,
            target_version=target_version,
            schema_version=schema_version,
            database_bytes=destination.stat().st_size,
            sha256=digest,
            integrity_check="ok",
            backup_file=destination.name,
        )
        metadata_path = destination.with_suffix(".metadata.json")
        _atomic_json(metadata_path, asdict(metadata))
        if json.loads(metadata_path.read_text(encoding="utf-8")).get("sha256") != digest:
            raise UpdatePreparationError("backup_metadata_failed", "The backup metadata could not be verified.")
        return destination, metadata
    except UpdatePreparationError:
        partial.unlink(missing_ok=True)
        raise
    except (OSError, sqlite3.Error) as exc:
        partial.unlink(missing_ok=True)
        raise UpdatePreparationError("backup_failed", "The local database backup could not be created.") from exc


class UpdateCoordinator:
    """Drain mutating requests before an update without interrupting safe reads."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active_mutations = 0
        self._preparing = False
        self._backup_in_progress = False
        self._cancel_requested = False
        self._shutdown_token = ""
        self._target_version = ""
        self._backup_path = ""

    @property
    def preparing(self) -> bool:
        return self._preparing

    @asynccontextmanager
    async def mutation(self) -> AsyncIterator[bool]:
        async with self._condition:
            if self._preparing:
                yield False
                return
            self._active_mutations += 1
        try:
            yield True
        finally:
            async with self._condition:
                self._active_mutations -= 1
                self._condition.notify_all()

    async def prepare(
        self, target_version: str, channel: str, timeout_seconds: float = 30
    ) -> tuple[str, Path, BackupMetadata]:
        if channel not in SAFE_UPDATE_CHANNELS:
            raise UpdatePreparationError("invalid_channel", "The selected update channel is not supported.")
        if not target_version or len(target_version) > 80:
            raise UpdatePreparationError("invalid_version", "The target version is invalid.")

        async with self._condition:
            if self._preparing:
                raise UpdatePreparationError("update_in_progress", "An update is already being prepared.")
            self._preparing = True
            self._target_version = target_version
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: self._active_mutations == 0),
                    timeout=timeout_seconds,
                )
            except TimeoutError as exc:
                self._preparing = False
                self._target_version = ""
                self._condition.notify_all()
                raise UpdatePreparationError(
                    "writes_did_not_drain",
                    "OIHK Basic is still saving data. Wait for active operations and try again.",
                ) from exc
            self._backup_in_progress = True

        try:
            backup, metadata = await asyncio.to_thread(
                create_verified_backup,
                target_version=target_version,
            )
        except Exception:
            async with self._condition:
                self._backup_in_progress = False
            await self.resume(error_code="backup_failed")
            raise

        async with self._condition:
            self._backup_in_progress = False
            cancelled = self._cancel_requested
            self._cancel_requested = False
            if cancelled:
                self._preparing = False
                self._shutdown_token = ""
                self._target_version = ""
                self._backup_path = ""
                self._condition.notify_all()
                token = ""
            else:
                token = secrets.token_urlsafe(32)
                self._shutdown_token = token
                self._backup_path = str(backup)

        if cancelled:
            record_update_state(
                stage="deferred",
                target_version=target_version,
                backup_path=str(backup),
            )
            raise UpdatePreparationError(
                "preparation_cancelled",
                "Update preparation was cancelled safely after the verified backup completed.",
            )

        try:
            record_update_state(
                stage="backup_ready",
                target_version=target_version,
                backup_path=str(backup),
            )
        except OSError as exc:
            await self.resume(error_code="recovery_state_failed")
            raise UpdatePreparationError(
                "recovery_state_failed",
                "The update recovery state could not be persisted safely.",
            ) from exc
        return token, backup, metadata

    async def resume(self, error_code: str = "") -> None:
        async with self._condition:
            if self._backup_in_progress:
                self._cancel_requested = True
                return
            target_version = self._target_version
            backup_path = self._backup_path
            self._preparing = False
            self._cancel_requested = False
            self._shutdown_token = ""
            self._target_version = ""
            self._backup_path = ""
            self._condition.notify_all()
        previous = read_recovery_state() or {}
        record_update_state(
            stage="deferred" if not error_code else "error",
            source_version=previous.get("source_version") or PRODUCT_VERSION,
            target_version=target_version or previous.get("target_version") or "",
            backup_path=backup_path or previous.get("backup_path") or "",
            error_code=error_code,
        )

    async def consume_shutdown_token(self, token: str) -> bool:
        async with self._condition:
            if not self._preparing or not self._shutdown_token:
                return False
            if not secrets.compare_digest(self._shutdown_token, token):
                return False
            self._shutdown_token = ""
            record_update_state(
                stage="installing",
                target_version=self._target_version,
                backup_path=self._backup_path,
            )
            return True


def mark_update_healthy_if_current() -> None:
    state = read_recovery_state()
    if not state or state.get("stage") not in {"backup_ready", "installing"}:
        return
    if state.get("target_version") != PRODUCT_VERSION:
        return
    record_update_state(
        stage="healthy",
        source_version=state.get("source_version") or PRODUCT_VERSION,
        target_version=PRODUCT_VERSION,
        backup_path=state.get("backup_path") or "",
    )


update_coordinator = UpdateCoordinator()
