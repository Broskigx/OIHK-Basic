"""End-to-end case lifecycle over HTTP.

Exercises the routes the desktop client actually calls, through the real
middleware stack, against a database with foreign keys enforced.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import models


async def test_create_read_and_list_a_case(client) -> None:
    created = await client.post(
        "/cases",
        json={
            "title": "Port scan follow-up",
            "legal_basis": "Authorized test",
            "scope_statement": "Bounded scope for the integration suite.",
            "priority": "high",
            "tags": ["  network  ", "", "recon"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "Port scan follow-up"
    assert body["priority"] == "high"
    # Blank tags are dropped and surviving ones are trimmed.
    assert body["tags"] == ["network", "recon"]

    fetched = await client.get(f"/cases/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]

    listed = await client.get("/cases")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]


async def test_scope_statement_is_required_to_be_meaningful(client) -> None:
    response = await client.post(
        "/cases",
        json={"title": "Too vague", "legal_basis": "Authorized test", "scope_statement": "short"},
    )
    assert response.status_code == 422


async def test_unknown_case_is_not_found(client) -> None:
    assert (await client.get("/cases/does-not-exist")).status_code == 404


async def test_update_archives_and_restores_a_case(client, case) -> None:
    archived = await client.patch(f"/cases/{case['id']}", json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_at"] is not None

    restored = await client.patch(f"/cases/{case['id']}", json={"status": "active"})
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None


async def test_counts_reflect_ingested_material(client, case) -> None:
    ingested = await client.post(
        "/sources/text",
        json={
            "case_id": case["id"],
            "title": "Observed infrastructure",
            "body": "Contact reachable at analyst@example.com from 203.0.113.10 during the window.",
        },
    )
    assert ingested.status_code == 201, ingested.text

    fetched = (await client.get(f"/cases/{case['id']}")).json()
    assert fetched["source_count"] == 1
    assert fetched["entity_count"] >= 1


async def test_duplicate_copies_material_into_a_new_case(client, case) -> None:
    await client.post(
        "/sources/text",
        json={
            "case_id": case["id"],
            "title": "Observed infrastructure",
            "body": "Contact reachable at analyst@example.com from 203.0.113.10.",
        },
    )
    original = (await client.get(f"/cases/{case['id']}")).json()

    duplicated = await client.post(f"/cases/{case['id']}/duplicate")
    assert duplicated.status_code == 201, duplicated.text
    copy = duplicated.json()
    assert copy["id"] != case["id"]
    assert copy["title"] == f"{case['title']} (copy)"
    assert copy["source_count"] == original["source_count"]
    assert copy["entity_count"] == original["entity_count"]

    # The copy is independent: editing it must not reach back into the original.
    await client.patch(f"/cases/{copy['id']}", json={"title": "Renamed copy"})
    assert (await client.get(f"/cases/{case['id']}")).json()["title"] == case["title"]


async def test_import_round_trips_an_exported_case(client, case) -> None:
    await client.post(
        "/sources/text",
        json={
            "case_id": case["id"],
            "title": "Observed infrastructure",
            "body": "Contact reachable at analyst@example.com from 203.0.113.10.",
        },
    )
    exported = await client.get(f"/exports/cases/{case['id']}/json")
    assert exported.status_code == 200, exported.text

    document = exported.json()
    imported = await client.post("/cases/import", json=document)
    assert imported.status_code == 201, imported.text
    assert imported.json()["id"] != case["id"]


async def test_import_rejects_an_oversized_document(client) -> None:
    """The list ceilings in the schema are what keep an import bounded."""
    response = await client.post(
        "/cases/import",
        json={
            "case": {
                "title": "Oversized",
                "legal_basis": "Authorized test",
                "scope_statement": "Bounded scope for the integration suite.",
            },
            "sources": [
                {"id": str(index), "title": f"Source {index}", "kind": "manual_text", "body": "x"}
                for index in range(5001)
            ],
        },
    )
    assert response.status_code == 422


async def test_delete_removes_a_case_and_its_material(client, case, session) -> None:
    await client.post(
        "/sources/text",
        json={
            "case_id": case["id"],
            "title": "Observed infrastructure",
            "body": "Contact reachable at analyst@example.com from 203.0.113.10.",
        },
    )

    deleted = await client.delete(f"/cases/{case['id']}")
    assert deleted.status_code == 204, deleted.text
    assert (await client.get(f"/cases/{case['id']}")).status_code == 404

    for model in (models.Source, models.Entity, models.Relationship, models.AuditEvent):
        remaining = await session.scalar(
            select(func.count()).select_from(model).where(model.case_id == case["id"])
        )
        assert remaining == 0, f"{model.__name__} rows outlived the case"


@pytest.mark.parametrize("status_value", ["active", "paused", "closed", "archived"])
async def test_every_declared_status_is_accepted(client, case, status_value: str) -> None:
    response = await client.patch(f"/cases/{case['id']}", json={"status": status_value})
    assert response.status_code == 200
    assert response.json()["status"] == status_value


async def test_undeclared_status_is_rejected(client, case) -> None:
    response = await client.patch(f"/cases/{case['id']}", json={"status": "deleted"})
    assert response.status_code == 422
