from __future__ import annotations

import hashlib
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from app.services import evidence_storage, managed_evidence


@pytest.mark.asyncio
async def test_streamed_evidence_is_sanitized_hashed_and_confined(tmp_path, monkeypatch):
    monkeypatch.setattr(
        managed_evidence,
        "get_settings",
        lambda: SimpleNamespace(effective_storage_dir=str(tmp_path), max_evidence_bytes=1024),
    )
    content = b"local evidence\x00payload"
    upload = UploadFile(
        filename="../../unsafe<script>.txt", file=BytesIO(content), headers={"content-type": "text/plain"}
    )

    stored = await managed_evidence.store_upload("case-local", upload)
    path = managed_evidence.safe_evidence_path(str(stored["storage_path"]))

    assert path.is_file()
    assert path.read_bytes() == content
    assert ".." not in str(stored["original_name"])
    assert "<" not in str(stored["original_name"])
    assert stored["sha256"] == hashlib.sha256(content).hexdigest()
    assert managed_evidence.hash_managed_file(str(path)) == stored["sha256"]
    assert path.is_relative_to((tmp_path / "evidence").resolve())

    with pytest.raises(HTTPException, match="outside managed storage"):
        managed_evidence.safe_evidence_path(str(tmp_path / "outside.txt"))


@pytest.mark.asyncio
async def test_evidence_size_limit_leaves_no_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        managed_evidence,
        "get_settings",
        lambda: SimpleNamespace(effective_storage_dir=str(tmp_path), max_evidence_bytes=8),
    )
    upload = UploadFile(filename="large.bin", file=BytesIO(b"0123456789"))

    with pytest.raises(HTTPException) as error:
        await managed_evidence.store_upload("case-local", upload)

    assert error.value.status_code == 413
    assert list((tmp_path / "evidence" / "case-local").iterdir()) == []


@pytest.mark.asyncio
async def test_streamed_evidence_rejects_case_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(
        managed_evidence,
        "get_settings",
        lambda: SimpleNamespace(effective_storage_dir=str(tmp_path), max_evidence_bytes=1024),
    )
    upload = UploadFile(filename="evidence.bin", file=BytesIO(b"preserved"))
    with pytest.raises(HTTPException, match="outside managed storage"):
        await managed_evidence.store_upload("../../outside", upload)
    assert not (tmp_path.parent / "outside").exists()


def test_legacy_managed_storage_is_atomic_and_path_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(
        evidence_storage,
        "get_settings",
        lambda: SimpleNamespace(storage_dir=str(tmp_path)),
    )
    stored = evidence_storage.store_evidence_bytes("case-local", "../../note.txt", b"preserved")
    path = evidence_storage.safe_storage_path(stored["storage_path"])
    assert path.read_bytes() == b"preserved"
    assert path.is_relative_to(tmp_path)
    with pytest.raises(HTTPException, match="outside managed storage"):
        evidence_storage.safe_storage_path(str(tmp_path.parent / "outside.txt"))
    with pytest.raises(HTTPException, match="outside managed storage"):
        evidence_storage.store_evidence_bytes("case", "note.txt", b"x", subdir="../../outside")
