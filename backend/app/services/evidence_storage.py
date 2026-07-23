"""Local file storage for evidence in OIHK Basic."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException

from app.core.config import get_settings


def _ensure_storage(subdir: str = "") -> Path:
    base = Path(get_settings().storage_dir).resolve()
    if subdir:
        base = base / subdir
    base.mkdir(parents=True, exist_ok=True)
    return base


def safe_storage_path(path_value: str) -> Path:
    root = Path(get_settings().storage_dir).resolve()
    path = Path(path_value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="File path is outside managed storage.") from exc
    return path


def store_evidence_bytes(
    case_id: str,
    filename: str,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
    subdir: str = "evidence",
) -> dict:
    """Store raw bytes to disk and return metadata."""
    sha256 = hashlib.sha256(data).hexdigest()
    # Sanitize filename to prevent path traversal
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)[:200]
    storage_dir = _ensure_storage(os.path.join(subdir, case_id))
    stored_path = storage_dir / f"{sha256[:16]}_{safe_name}"
    descriptor, temporary_name = tempfile.mkstemp(prefix="incoming-", dir=storage_dir)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(data)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_name, stored_path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise

    return {
        "sha256": sha256,
        "storage_path": str(stored_path),
        "filename": safe_name,
        "size_bytes": len(data),
        "content_type": content_type,
    }


async def store_photo(case_id: str, target_id: str, upload) -> dict:
    """Store an uploaded photo to disk."""

    limit = get_settings().max_evidence_bytes
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="Photo exceeds the configured evidence file limit.")
    return store_evidence_bytes(
        case_id=case_id,
        filename=upload.filename or "photo",
        data=data,
        content_type=upload.content_type or "image/jpeg",
        subdir="photos",
    )
