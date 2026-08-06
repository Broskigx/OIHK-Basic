"""Versioned local application settings and safe storage diagnostics."""

import asyncio
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.config import get_settings
from app.core.deps import CurrentUser, get_current_user
from app.database import get_session
from app.schemas import ApplicationSettingsRead, ApplicationSettingsWrite, StorageStatusRead

router = APIRouter(prefix="/settings", tags=["settings"])


def _directory_size(root: Path) -> int:
    if not root.is_dir():
        return 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _database_path() -> Path:
    configured = get_settings().database_url
    if not configured.startswith("sqlite"):
        raise HTTPException(status_code=409, detail="Storage backup is only available for the local SQLite runtime.")
    database = make_url(configured).database
    if not database or database == ":memory:":
        raise HTTPException(status_code=409, detail="The current SQLite runtime has no persistent database file.")
    return Path(database).resolve()


def _read(row: models.ApplicationSettings | None) -> ApplicationSettingsRead:
    if row is None:
        return ApplicationSettingsRead()
    return ApplicationSettingsRead(
        id=row.id,
        schema_version=row.schema_version,
        onboarding_complete=row.onboarding_complete,
        general=row.general or {},
        appearance=row.appearance or {},
        storage=row.storage or {},
        tools=row.tools or {},
        privacy=row.privacy or {},
        performance=row.performance or {},
        updated_at=row.updated_at,
    )


@router.get("", response_model=ApplicationSettingsRead)
async def get_application_settings(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApplicationSettingsRead:
    row = (
        await session.execute(
            select(models.ApplicationSettings).where(models.ApplicationSettings.user_id == current.id)
        )
    ).scalar_one_or_none()
    return _read(row)


@router.put("", response_model=ApplicationSettingsRead)
async def save_application_settings(
    payload: ApplicationSettingsWrite,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApplicationSettingsRead:
    row = (
        await session.execute(
            select(models.ApplicationSettings).where(models.ApplicationSettings.user_id == current.id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = models.ApplicationSettings(user_id=current.id)
        session.add(row)
    row.schema_version = 2
    row.onboarding_complete = payload.onboarding_complete
    row.general = payload.general.model_dump()
    row.appearance = payload.appearance.model_dump()
    row.storage = payload.storage.model_dump()
    row.tools = payload.tools.model_dump()
    row.privacy = payload.privacy.model_dump()
    row.performance = payload.performance.model_dump()
    await session.commit()
    await session.refresh(row)
    return _read(row)


@router.get("/storage", response_model=StorageStatusRead)
async def storage_status(
    _current: CurrentUser = Depends(get_current_user),
) -> StorageStatusRead:
    database = _database_path()
    storage = Path(get_settings().effective_storage_dir).resolve()

    def _snapshot() -> StorageStatusRead:
        database_bytes = database.stat().st_size if database.is_file() else 0
        evidence_bytes = _directory_size(storage)
        data_directory = database.parent
        writable = (
            os.access(data_directory, os.W_OK) if data_directory.exists() else os.access(data_directory.parent, os.W_OK)
        )
        return StorageStatusRead(
            data_directory=str(data_directory),
            database_path=str(database),
            storage_path=str(storage),
            database_bytes=database_bytes,
            evidence_bytes=evidence_bytes,
            total_bytes=database_bytes + evidence_bytes,
            writable=writable,
        )

    # The directory walk can be slow on large evidence trees — keep the
    # event loop responsive by running it on a worker thread.
    return await asyncio.to_thread(_snapshot)


def _backup_sqlite(source_path: Path) -> bytes:
    """Full SQLite backup + read; runs on a worker thread (blocking I/O)."""
    descriptor, temporary_name = tempfile.mkstemp(prefix="oihk-basic-backup-", suffix=".sqlite3")
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        source = sqlite3.connect(source_path)
        destination = sqlite3.connect(temporary)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        return temporary.read_bytes()
    finally:
        temporary.unlink(missing_ok=True)


@router.get("/backup")
async def download_sqlite_backup(
    _current: CurrentUser = Depends(get_current_user),
) -> Response:
    source_path = _database_path()
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="No local database exists yet.")
    content = await asyncio.to_thread(_backup_sqlite, source_path)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=content,
        media_type="application/vnd.sqlite3",
        headers={"Content-Disposition": f'attachment; filename="oihk-basic-{stamp}.sqlite3"'},
    )
