"""Streaming, path-safe managed evidence storage."""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import get_settings

_CHUNK_SIZE = 1024 * 1024


def evidence_root() -> Path:
    storage_root = Path(get_settings().effective_storage_dir).resolve()
    root = (storage_root / "evidence").resolve()
    try:
        root.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Evidence storage escapes the configured directory.") from exc
    root.mkdir(parents=True, exist_ok=True)
    return root


def _confined_directory(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Evidence path is outside managed storage.") from exc
    return candidate


def safe_evidence_path(path_value: str) -> Path:
    root = evidence_root()
    path = Path(path_value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Evidence path is outside managed storage.") from exc
    return path


def safe_filename(filename: str) -> str:
    name = Path(filename or "evidence.bin").name
    cleaned = "".join(character if character.isalnum() or character in "._- " else "_" for character in name)
    return cleaned.strip(" .")[:200] or "evidence.bin"


async def store_upload(case_id: str, upload: UploadFile) -> dict[str, str | int]:
    root = evidence_root()
    case_root = _confined_directory(root, case_id)
    case_root.mkdir(parents=True, exist_ok=True)
    safe_name = safe_filename(upload.filename or "evidence.bin")
    descriptor, temporary_name = tempfile.mkstemp(prefix="incoming-", dir=case_root)
    digest = hashlib.sha256()
    size = 0
    limit = get_settings().max_evidence_bytes
    try:
        with os.fdopen(descriptor, "wb") as destination:
            while chunk := await upload.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Evidence file exceeds the configured {limit // (1024 * 1024)} MB limit.",
                    )
                digest.update(chunk)
                # Disk write/flush/fsync are blocking I/O inside an async
                # route — offload each to a worker thread so the event loop
                # keeps serving requests during large uploads.
                await asyncio.to_thread(destination.write, chunk)
            await asyncio.to_thread(destination.flush)
            await asyncio.to_thread(os.fsync, destination.fileno())
        final_path = (case_root / f"{uuid4()}-{safe_name}").resolve()
        try:
            final_path.relative_to(case_root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Evidence path is outside managed storage.") from exc
        os.replace(temporary_name, final_path)
        return {
            "storage_path": str(final_path),
            "original_name": safe_name,
            "sha256": digest.hexdigest(),
            "size_bytes": size,
            "mime_type": (upload.content_type or "application/octet-stream")[:160],
        }
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def hash_managed_file(path_value: str) -> str:
    path = safe_evidence_path(path_value)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(_CHUNK_SIZE):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Managed evidence file is missing from storage.") from exc
    return digest.hexdigest()
