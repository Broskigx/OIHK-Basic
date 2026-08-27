"""Managed evidence storage: the path Basic still owns.

Basic no longer accepts browser uploads — acquisition moved to the separately
installed Evidence Lab, which writes through the signed System Link module API.
``store_evidence_bytes`` is what that API calls, so the containment and
atomicity properties the old streaming uploader was tested for have to hold
here instead. They are tested here for exactly that reason.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import evidence_storage, managed_evidence


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(
        evidence_storage,
        "get_settings",
        lambda: SimpleNamespace(storage_dir=str(tmp_path)),
    )
    return tmp_path


def test_managed_storage_is_atomic_and_path_safe(storage) -> None:
    stored = evidence_storage.store_evidence_bytes("case-local", "../../note.txt", b"preserved")
    path = evidence_storage.safe_storage_path(stored["storage_path"])
    assert path.read_bytes() == b"preserved"
    assert path.is_relative_to(storage)
    # The sanitiser keeps dots but replaces separators, so "../../note.txt"
    # survives as ".._.._note.txt": no longer a path, just an odd-looking name.
    assert "/" not in stored["filename"] and "\\" not in stored["filename"]
    with pytest.raises(HTTPException, match="outside managed storage"):
        evidence_storage.safe_storage_path(str(storage.parent / "outside.txt"))
    with pytest.raises(HTTPException, match="outside managed storage"):
        evidence_storage.store_evidence_bytes("case", "note.txt", b"x", subdir="../../outside")


def test_a_traversing_case_id_cannot_escape_managed_storage(storage) -> None:
    """The case id reaches storage as a directory name, so it is a traversal vector.

    The module API resolves the case before it stores anything, so a hostile id
    is refused earlier in practice. This pins the storage layer's own guard so
    that ordering stays a convenience rather than the only thing preventing a
    write outside managed storage.
    """
    with pytest.raises(HTTPException, match="outside managed storage"):
        evidence_storage.store_evidence_bytes("../../outside", "note.txt", b"x")
    assert not (storage.parent / "outside").exists()


def test_stored_bytes_hash_to_the_recorded_digest(storage) -> None:
    content = b"local evidence\x00payload"
    stored = evidence_storage.store_evidence_bytes("case-local", "exhibit.bin", content)
    assert stored["sha256"] == hashlib.sha256(content).hexdigest()
    assert stored["size_bytes"] == len(content)


def test_the_custodian_can_rehash_a_held_file(storage, monkeypatch) -> None:
    """``hash_managed_file`` backs the verify route, which is still Basic's job."""
    monkeypatch.setattr(
        managed_evidence,
        "get_settings",
        lambda: SimpleNamespace(effective_storage_dir=str(storage), max_evidence_bytes=1024),
    )
    content = b"sealed exhibit"
    stored = evidence_storage.store_evidence_bytes("case-local", "exhibit.bin", content)
    assert managed_evidence.hash_managed_file(stored["storage_path"]) == hashlib.sha256(content).hexdigest()
    with pytest.raises(HTTPException, match="outside managed storage"):
        managed_evidence.safe_evidence_path(str(storage / "outside.txt"))
