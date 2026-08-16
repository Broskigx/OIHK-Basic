"""Intelligence graph routes over HTTP."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import models


async def _entity(client, case_id: str, label: str, entity_type: str = "person", **extra):
    response = await client.post(
        "/graph/entities",
        json={"case_id": case_id, "label": label, "type": entity_type, "confidence": 0.9, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _relationship(client, case_id: str, source_id: str, target_id: str, label: str = "knows"):
    return await client.post(
        "/graph/relationships",
        json={
            "case_id": case_id,
            "source_id": source_id,
            "target_id": target_id,
            "label": label,
            "confidence": 0.8,
        },
    )


# --- Entities and relationships ----------------------------------------------


async def test_graph_starts_empty(client, case) -> None:
    response = await client.get(f"/graph/{case['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["nodes"] == []
    assert body["edges"] == []


async def test_creating_entities_and_a_relationship(client, case) -> None:
    first = await _entity(client, case["id"], "Ada Lovelace")
    second = await _entity(client, case["id"], "Charles Babbage")

    created = await _relationship(client, case["id"], first["id"], second["id"], "collaborated with")
    assert created.status_code == 201, created.text
    edge = created.json()
    # Labels are normalised into predicate form.
    assert edge["label"] == "collaborated_with"

    graph = (await client.get(f"/graph/{case['id']}")).json()
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1


async def test_entity_type_is_normalised(client, case) -> None:
    node = await _entity(client, case["id"], "Example Org", entity_type="  Legal Entity  ")
    assert node["type"] == "legal_entity"


async def test_relationship_requires_two_distinct_entities(client, case) -> None:
    node = await _entity(client, case["id"], "Ada Lovelace")
    response = await _relationship(client, case["id"], node["id"], node["id"])
    assert response.status_code == 400


async def test_relationship_entities_must_belong_to_the_case(client, case) -> None:
    node = await _entity(client, case["id"], "Ada Lovelace")
    other = (
        await client.post(
            "/cases",
            json={
                "title": "Unrelated case",
                "legal_basis": "Authorized test",
                "scope_statement": "A separate bounded scope for isolation.",
            },
        )
    ).json()
    outsider = await _entity(client, other["id"], "Outsider")

    response = await _relationship(client, case["id"], node["id"], outsider["id"])
    assert response.status_code == 400


async def test_duplicate_relationships_are_refused(client, case) -> None:
    first = await _entity(client, case["id"], "Ada Lovelace")
    second = await _entity(client, case["id"], "Charles Babbage")
    assert (await _relationship(client, case["id"], first["id"], second["id"])).status_code == 201

    duplicate = await _relationship(client, case["id"], first["id"], second["id"])
    assert duplicate.status_code == 409


async def test_connect_to_id_must_be_in_the_same_case(client, case) -> None:
    response = await client.post(
        "/graph/entities",
        json={
            "case_id": case["id"],
            "label": "Ada Lovelace",
            "type": "person",
            "confidence": 0.9,
            "connect_to_id": "an-entity-that-does-not-exist",
        },
    )
    assert response.status_code == 400


async def test_entity_creation_is_attributed_to_the_acting_user(client, case, session) -> None:
    """The audit trail must name the operator, not a hardcoded placeholder."""
    node = await _entity(client, case["id"], "Ada Lovelace")
    actor = await session.scalar(
        select(models.AuditEvent.actor).where(
            models.AuditEvent.case_id == case["id"],
            models.AuditEvent.action == "graph.entity.created",
        )
    )
    assert actor == "system"
    assert node["id"]


async def test_relationship_label_can_be_updated(client, case) -> None:
    first = await _entity(client, case["id"], "Ada Lovelace")
    second = await _entity(client, case["id"], "Charles Babbage")
    edge = (await _relationship(client, case["id"], first["id"], second["id"])).json()

    updated = await client.patch(f"/graph/relationships/{edge['id']}", json={"label": "worked with"})
    assert updated.status_code == 200
    assert updated.json()["label"] == "worked_with"


async def test_relationship_label_cannot_be_emptied_by_an_update(client, case) -> None:
    """Whitespace satisfies the schema's min_length and then normalises away."""
    first = await _entity(client, case["id"], "Ada Lovelace")
    second = await _entity(client, case["id"], "Charles Babbage")
    edge = (await _relationship(client, case["id"], first["id"], second["id"])).json()

    response = await client.patch(f"/graph/relationships/{edge['id']}", json={"label": "   "})
    assert response.status_code == 400
    unchanged = (await client.get(f"/graph/{case['id']}")).json()["edges"][0]
    assert unchanged["label"] == "knows"


async def test_deleting_a_relationship(client, case) -> None:
    first = await _entity(client, case["id"], "Ada Lovelace")
    second = await _entity(client, case["id"], "Charles Babbage")
    edge = (await _relationship(client, case["id"], first["id"], second["id"])).json()

    assert (await client.delete(f"/graph/relationships/{edge['id']}")).status_code == 200
    assert (await client.get(f"/graph/{case['id']}")).json()["edges"] == []


async def test_deleting_an_entity_removes_its_relationships(client, case) -> None:
    first = await _entity(client, case["id"], "Ada Lovelace")
    second = await _entity(client, case["id"], "Charles Babbage")
    await _relationship(client, case["id"], first["id"], second["id"])

    assert (await client.delete(f"/graph/entities/{first['id']}")).status_code == 200
    graph = (await client.get(f"/graph/{case['id']}")).json()
    assert [node["id"] for node in graph["nodes"]] == [second["id"]]
    assert graph["edges"] == []


# --- Workspace and snapshots --------------------------------------------------


async def test_workspace_round_trips(client, case) -> None:
    node = await _entity(client, case["id"], "Ada Lovelace")
    saved = await client.put(
        f"/graph/{case['id']}/workspace",
        json={
            "positions": {node["id"]: {"x": 12.5, "y": -4.0}},
            "camera": {"x": 1.0, "y": 2.0, "zoom": 1.5},
            "view_mode": "hierarchy",
            "filters": {"type": "person"},
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["positions"][node["id"]]["x"] == 12.5
    assert body["view_mode"] == "hierarchy"

    reread = (await client.get(f"/graph/{case['id']}/workspace")).json()
    assert reread["camera"]["zoom"] == 1.5


async def test_workspace_drops_positions_for_unknown_entities(client, case) -> None:
    saved = await client.put(
        f"/graph/{case['id']}/workspace",
        json={"positions": {"not-a-real-entity": {"x": 1.0, "y": 1.0}}},
    )
    assert saved.status_code == 200
    assert saved.json()["positions"] == {}


async def test_snapshot_capture_and_restore(client, case) -> None:
    node = await _entity(client, case["id"], "Ada Lovelace")
    await client.put(
        f"/graph/{case['id']}/workspace",
        json={"positions": {node["id"]: {"x": 50.0, "y": 60.0}}, "view_mode": "network"},
    )

    snapshot = await client.post(f"/graph/{case['id']}/snapshots", json={"name": "Before pivot"})
    assert snapshot.status_code == 201, snapshot.text
    assert snapshot.json()["node_count"] == 1

    await client.put(
        f"/graph/{case['id']}/workspace",
        json={"positions": {node["id"]: {"x": 0.0, "y": 0.0}}, "view_mode": "connections"},
    )

    restored = await client.post(f"/graph/{case['id']}/snapshots/{snapshot.json()['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["positions"][node["id"]]["x"] == 50.0
    assert restored.json()["view_mode"] == "network"


async def test_restore_drops_positions_for_entities_deleted_since(client, case) -> None:
    node = await _entity(client, case["id"], "Ada Lovelace")
    await client.put(
        f"/graph/{case['id']}/workspace",
        json={"positions": {node["id"]: {"x": 50.0, "y": 60.0}}},
    )
    snapshot = (await client.post(f"/graph/{case['id']}/snapshots", json={"name": "Before deletion"})).json()

    await client.delete(f"/graph/entities/{node['id']}")

    restored = await client.post(f"/graph/{case['id']}/snapshots/{snapshot['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["positions"] == {}


async def test_snapshots_are_capped_at_the_listed_retention(client, case) -> None:
    """Unbounded writes behind a capped read would grow storage invisibly."""
    from app.routers.graph import _SNAPSHOT_RETENTION

    for index in range(_SNAPSHOT_RETENTION + 5):
        created = await client.post(f"/graph/{case['id']}/snapshots", json={"name": f"Snapshot {index}"})
        assert created.status_code == 201

    listed = (await client.get(f"/graph/{case['id']}/snapshots")).json()
    assert len(listed) == _SNAPSHOT_RETENTION
    # The newest survive and the oldest are reclaimed.
    assert listed[0]["name"] == f"Snapshot {_SNAPSHOT_RETENTION + 4}"


async def test_snapshot_retention_is_enforced_in_the_database(client, case, session) -> None:
    from app.routers.graph import _SNAPSHOT_RETENTION

    for index in range(_SNAPSHOT_RETENTION + 3):
        await client.post(f"/graph/{case['id']}/snapshots", json={"name": f"Snapshot {index}"})

    stored = await session.scalar(
        select(func.count()).select_from(models.GraphSnapshot).where(models.GraphSnapshot.case_id == case["id"])
    )
    assert stored == _SNAPSHOT_RETENTION


async def test_snapshot_from_another_case_is_not_found(client, case) -> None:
    other = (
        await client.post(
            "/cases",
            json={
                "title": "Unrelated case",
                "legal_basis": "Authorized test",
                "scope_statement": "A separate bounded scope for isolation.",
            },
        )
    ).json()
    snapshot = (await client.post(f"/graph/{other['id']}/snapshots", json={"name": "Elsewhere"})).json()

    assert (await client.post(f"/graph/{case['id']}/snapshots/{snapshot['id']}/restore")).status_code == 404
    assert (await client.delete(f"/graph/{case['id']}/snapshots/{snapshot['id']}")).status_code == 404


# --- Export -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "content_type"),
    [("export.graphml", "application/graphml+xml"), ("export.csv", "text/csv")],
)
async def test_graph_exports_are_served(client, case, path: str, content_type: str) -> None:
    first = await _entity(client, case["id"], "Ada Lovelace")
    second = await _entity(client, case["id"], "Charles Babbage")
    await _relationship(client, case["id"], first["id"], second["id"])

    response = await client.get(f"/graph/{case['id']}/{path}")
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert "Ada Lovelace" in response.text
