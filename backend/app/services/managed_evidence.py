"""Path-safe access to the managed evidence tree Basic holds as custodian.

The streaming uploader that used to live here went with the Evidence Lab
workspace: Basic no longer accepts evidence through a browser form, so the only
ingestion path is ``evidence_storage.store_evidence_bytes``, called by the
signed System Link module API where every write is attributed to a module.

What remains is what a custodian still needs — resolving a stored path without
letting it escape the tree, and re-hashing a held file to check it against its
seal.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException

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


def safe_evidence_path(path_value: str) -> Path:
    root = evidence_root()
    path = Path(path_value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Evidence path is outside managed storage.") from exc
    return path


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
