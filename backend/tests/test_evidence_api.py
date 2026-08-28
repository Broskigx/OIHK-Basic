"""The evidence surface Basic keeps as custodian, over HTTP.

Ingestion is not here any more. Basic no longer accepts browser uploads —
Evidence Lab is installed separately and writes through the signed System Link
module API, which is exercised in ``test_module_capability_api``. These tests
cover what a custodian still does with records it holds: list them, prove a
held file still matches its seal, export the manifest, and remove an exhibit.

Evidence is arranged through the same services the module API calls, so the
fixtures below produce records indistinguishable from ones a linked module
wrote — which is the point: the custody surface must not care who ingested.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from app import models
from app.services.custody import seal_source
from app.services.evidence_storage import store_evidence_bytes


async def _ingest(
    session,
    case_id: str,
    *,
    name: str = "note.txt",
    content: bytes = b"observed artifact",
    ingested_by: str = "module:oihk.evidence-lab",
) -> models.EvidenceItem:
    """Create sealed managed evidence the way the module API does."""
    stored = store_evidence_bytes(case_id, name, content, content_type="text/plain")
    source = models.Source(
        case_id=case_id,
        title=f"Evidence: {stored['filename']}"[:240],
        kind="module_evidence",
        body=f"sha256={stored['sha256']}",
        citation=f"sha256:{stored['sha256']}",
        license="case-evidence",
        reliability=1.0,
    )
    session.add(source)
    await session.flush()
    await seal_source(session, source, storage_path=str(stored["storage_path"]))
    item = models.EvidenceItem(
        case_id=case_id,
        source_id=source.id,
        original_name=str(stored["filename"]),
        storage_path=str(stored["storage_path"]),
        mime_type="text/plain",
        size_bytes=int(stored["size_bytes"]),
        sha256=str(stored["sha256"]),
        notes="collected during the window",
        tags=["field", "raw"],
        ingested_by=ingested_by,
    )
    session.add(item)
    await session.commit()
    return item


async def _stored_path(session, item_id: str) -> Path:
    """Read the managed path from the database.

    The API deliberately does not return it — an absolute filesystem path is
    not something a client needs — so the test reads it the same way the
    backend does.
    """
    session.expire_all()
    path_value = await session.scalar(
        select(models.EvidenceItem.storage_path).where(models.EvidenceItem.id == item_id)
    )
    assert path_value, f"no stored path recorded for evidence {item_id}"
    return Path(path_value)


async def test_listing_returns_what_the_case_holds(client, case, session, storage_dir) -> None:
    item = await _ingest(session, case["id"])

    listed = await client.get(f"/evidence/{case['id']}")
    assert listed.status_code == 200
    rows = listed.json()
    assert [row["id"] for row in rows] == [item.id]
    assert rows[0]["sha256"] == item.sha256
    assert rows[0]["ingested_by"] == "module:oihk.evidence-lab"


async def test_managed_path_is_never_returned_to_the_client(client, case, session, storage_dir) -> None:
    await _ingest(session, case["id"])
    listed = await client.get(f"/evidence/{case['id']}")
    assert "storage_path" not in listed.text


async def test_ingestion_is_not_reachable_over_the_browser_api(client, case, storage_dir) -> None:
    """The upload route is gone on purpose, not by accident.

    An unauthenticated-by-module write path would be a second way in that no
    module signature covers, which is exactly what moving ingestion to the
    signed module API was meant to prevent.
    """
    response = await client.post(
        "/evidence",
        data={"case_id": case["id"]},
        files={"file": ("note.txt", b"payload", "text/plain")},
    )
    assert response.status_code == 404


async def test_annotation_is_not_reachable_over_the_browser_api(client, case, session, storage_dir) -> None:
    item = await _ingest(session, case["id"])
    response = await client.patch(f"/evidence/items/{item.id}", json={"notes": "edited"})
    assert response.status_code == 405


async def test_verify_confirms_an_intact_file(client, case, session, storage_dir) -> None:
    item = await _ingest(session, case["id"])

    verified = await client.post(f"/evidence/items/{item.id}/verify")
    assert verified.status_code == 200
    body = verified.json()
    assert body["intact"] is True
    assert body["actual_sha256"] == body["expected_sha256"] == item.sha256


async def test_verify_detects_a_tampered_file(client, case, session, storage_dir) -> None:
    item = await _ingest(session, case["id"])
    # Capture the identifier before _stored_path expires the session: touching
    # an expired ORM attribute afterwards triggers a lazy reload from sync
    # context, which asyncio SQLAlchemy cannot service.
    item_id = item.id
    (await _stored_path(session, item_id)).write_bytes(b"substituted content")

    verified = await client.post(f"/evidence/items/{item_id}/verify")
    assert verified.status_code == 200
    body = verified.json()
    assert body["intact"] is False
    assert body["actual_sha256"] != body["expected_sha256"]


async def test_verify_refuses_an_exhibit_basic_does_not_hold(client, case, session, storage_dir) -> None:
    """An imported record has no managed file; saying "not intact" would be a lie.

    ``evidence.import`` records that an exhibit exists in the module's own
    store. Re-hashing nothing and reporting a mismatch would read as tampering
    when the truth is that the bytes were never Basic's to check.
    """
    item = await _ingest(session, case["id"])
    item.storage_path = ""
    await session.commit()

    verified = await client.post(f"/evidence/items/{item.id}/verify")
    assert verified.status_code == 409
    assert "linked module" in verified.json()["detail"]


async def test_manifest_lists_holdings_and_marks_who_holds_them(client, case, session, storage_dir) -> None:
    held = await _ingest(session, case["id"], name="held.txt")
    referenced = await _ingest(session, case["id"], name="elsewhere.txt")
    referenced.storage_path = ""
    referenced.original_reference = "evidence-lab://vault/elsewhere.txt"
    await session.commit()

    response = await client.get(f"/evidence/{case['id']}/manifest.json")
    assert response.status_code == 200
    manifest = response.json()
    by_id = {row["id"]: row for row in manifest["items"]}
    assert by_id[held.id]["held_by_basic"] is True
    assert by_id[referenced.id]["held_by_basic"] is False
    assert by_id[referenced.id]["original_reference"] == "evidence-lab://vault/elsewhere.txt"


async def test_deleting_evidence_removes_its_managed_file(client, case, session, storage_dir) -> None:
    item = await _ingest(session, case["id"])
    item_id = item.id
    path = await _stored_path(session, item_id)
    assert path.is_file()

    removed = await client.delete(f"/evidence/items/{item_id}")
    assert removed.status_code == 204
    assert not path.exists()

    session.expire_all()
    remaining = await session.scalar(
        select(func.count(models.EvidenceItem.id)).where(models.EvidenceItem.case_id == case["id"])
    )
    assert remaining == 0


async def test_deleting_a_case_removes_its_evidence_and_files(client, case, session, storage_dir) -> None:
    item = await _ingest(session, case["id"])
    path = await _stored_path(session, item.id)
    assert path.is_file()

    removed = await client.delete(f"/cases/{case['id']}")
    assert removed.status_code == 204
    assert not path.exists(), "deleting a case must not leave its evidence files on disk"

    session.expire_all()
    remaining = await session.scalar(
        select(func.count(models.EvidenceItem.id)).where(models.EvidenceItem.case_id == case["id"])
    )
    assert remaining == 0


async def test_the_listing_says_who_holds_each_exhibit(client, case, session, storage_dir) -> None:
    """The register has to distinguish what Basic holds from what it only records.

    The two support different actions — a held file can be re-hashed against
    its seal, a referenced one cannot — and the operator cannot tell them apart
    from name, size or digest, all of which are present either way. The managed
    path itself is never exposed, so the answer travels as a boolean.
    """
    held = await _ingest(session, case["id"], name="held.txt")
    referenced = await _ingest(session, case["id"], name="elsewhere.txt")
    referenced.storage_path = ""
    await session.commit()

    rows = {row["id"]: row for row in (await client.get(f"/evidence/{case['id']}")).json()}
    assert rows[held.id]["held_by_basic"] is True
    assert rows[referenced.id]["held_by_basic"] is False
    assert "storage_path" not in rows[held.id]


async def test_a_failed_verification_survives_a_reload(client, case, session, storage_dir) -> None:
    """The register must remember the verdict, not just that a check happened.

    ``verified_at`` records *when* an exhibit was last checked and says nothing
    about the outcome, so a tampered file and an intact one looked identical
    the moment the page was refreshed — the one state a custody register can
    least afford to lose.
    """
    item = await _ingest(session, case["id"])
    item_id = item.id
    path = await _stored_path(session, item_id)

    await client.post(f"/evidence/items/{item_id}/verify")
    intact_row = next(row for row in (await client.get(f"/evidence/{case['id']}")).json() if row["id"] == item_id)
    assert intact_row["last_verification_intact"] is True

    path.write_bytes(b"substituted content")
    await client.post(f"/evidence/items/{item_id}/verify")
    broken_row = next(row for row in (await client.get(f"/evidence/{case['id']}")).json() if row["id"] == item_id)
    assert broken_row["last_verification_intact"] is False
    assert broken_row["verified_at"] is not None


async def test_an_unchecked_exhibit_reports_no_verdict(client, case, session, storage_dir) -> None:
    """Never-checked and checked-and-passed must not look the same either."""
    await _ingest(session, case["id"])
    row = (await client.get(f"/evidence/{case['id']}")).json()[0]
    assert row["last_verification_intact"] is None
    assert row["verified_at"] is None
