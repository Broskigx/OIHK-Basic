"""Managed evidence over HTTP, including what deletion leaves behind."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from app import models


async def _upload(client, case_id: str, name: str = "note.txt", content: bytes = b"observed artifact"):
    return await client.post(
        "/evidence",
        data={"case_id": case_id, "notes": "collected during the window", "tags": "field,raw"},
        files={"file": (name, content, "text/plain")},
    )


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


async def test_upload_stores_hashes_and_lists_evidence(client, case, session, storage_dir) -> None:
    response = await _upload(client, case["id"])
    assert response.status_code == 201, response.text
    item = response.json()

    assert item["size_bytes"] == len(b"observed artifact")
    assert len(item["sha256"]) == 64
    assert item["tags"] == ["field", "raw"]

    stored = await _stored_path(session, item["id"])
    assert stored.is_file()
    assert stored.is_relative_to(storage_dir.resolve())

    listed = await client.get(f"/evidence/{case['id']}")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [item["id"]]


async def test_managed_path_is_never_returned_to_the_client(client, case) -> None:
    """An absolute filesystem path is not part of the API contract."""
    item = (await _upload(client, case["id"])).json()
    assert "storage_path" not in item
    listed = (await client.get(f"/evidence/{case['id']}")).json()
    assert "storage_path" not in listed[0]


async def test_verify_confirms_an_intact_file(client, case) -> None:
    item = (await _upload(client, case["id"])).json()
    verified = await client.post(f"/evidence/items/{item['id']}/verify")
    assert verified.status_code == 200
    body = verified.json()
    assert body["intact"] is True
    assert body["actual_sha256"] == body["expected_sha256"]


async def test_verify_detects_a_tampered_file(client, case, session) -> None:
    item = (await _upload(client, case["id"])).json()
    (await _stored_path(session, item["id"])).write_bytes(b"substituted content")

    verified = await client.post(f"/evidence/items/{item['id']}/verify")
    assert verified.status_code == 200
    body = verified.json()
    assert body["intact"] is False
    assert body["actual_sha256"] != body["expected_sha256"]


async def test_preview_serves_a_raster_image_inline(client, case) -> None:
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
        "00000049454e44ae426082"
    )
    item = (
        await client.post(
            "/evidence",
            data={"case_id": case["id"]},
            files={"file": ("pixel.png", png, "image/png")},
        )
    ).json()

    preview = await client.get(f"/evidence/items/{item['id']}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/png")
    assert preview.headers["content-disposition"].startswith("inline")
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in preview.headers["content-security-policy"]


async def test_preview_forces_an_attachment_for_active_content(client, case) -> None:
    """SVG is a scriptable document; it must never render in the app context."""
    item = (
        await client.post(
            "/evidence",
            data={"case_id": case["id"]},
            files={"file": ("payload.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml")},
        )
    ).json()

    preview = await client.get(f"/evidence/items/{item['id']}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("application/octet-stream")
    assert preview.headers["content-disposition"].startswith("attachment")


async def test_upload_to_an_inaccessible_case_is_refused(client, storage_dir) -> None:
    response = await _upload(client, "does-not-exist")
    assert response.status_code == 404
    # A refused upload must not leave a file behind in managed storage.
    assert not any(storage_dir.rglob("*")) if storage_dir.exists() else True


async def test_case_id_cannot_escape_managed_storage(client, storage_dir) -> None:
    response = await _upload(client, "../../escaped")
    assert response.status_code in {400, 404}


async def test_evidence_association_must_stay_inside_the_case(client, case) -> None:
    item = (await _upload(client, case["id"])).json()
    response = await client.patch(
        f"/evidence/items/{item['id']}",
        json={"entity_ids": ["an-entity-from-another-case"]},
    )
    assert response.status_code == 400


async def test_deleting_evidence_removes_its_managed_file(client, case, session) -> None:
    item = (await _upload(client, case["id"])).json()
    stored = await _stored_path(session, item["id"])
    assert stored.is_file()

    deleted = await client.delete(f"/evidence/items/{item['id']}")
    assert deleted.status_code == 204, deleted.text
    assert not stored.exists(), "the managed file outlived its evidence record"


async def test_deleting_a_case_removes_its_evidence_and_files(client, case, session) -> None:
    """A deleted case must not leave evidence rows or unreferenced files behind."""
    item = (await _upload(client, case["id"])).json()
    stored = await _stored_path(session, item["id"])
    assert stored.is_file()

    deleted = await client.delete(f"/cases/{case['id']}")
    assert deleted.status_code == 204, deleted.text

    for model in (models.EvidenceItem, models.EvidenceSeal, models.Source):
        remaining = await session.scalar(
            select(func.count()).select_from(model).where(model.case_id == case["id"])
        )
        assert remaining == 0, f"{model.__name__} rows outlived the case"
    assert not stored.exists(), "managed evidence files outlived the case that owned them"
