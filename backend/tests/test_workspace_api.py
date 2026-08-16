"""Settings, dashboard, custody, exports and operations over HTTP.

These are the routes the desktop shell calls on almost every screen, so their
contract matters more than their size suggests.
"""

from __future__ import annotations

import json

# --- Application settings -----------------------------------------------------


async def test_settings_start_at_their_documented_defaults(client) -> None:
    response = await client.get("/settings")
    assert response.status_code == 200
    body = response.json()
    # A fresh profile has not completed onboarding; the desktop shell keys the
    # first-run flow off exactly this.
    assert body["onboarding_complete"] is False


async def test_settings_round_trip(client) -> None:
    saved = await client.put(
        "/settings",
        json={
            "onboarding_complete": True,
            "appearance": {"dark_mode": False, "density": "compact"},
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["onboarding_complete"] is True

    reread = await client.get("/settings")
    assert reread.json()["onboarding_complete"] is True
    assert reread.json()["appearance"]["dark_mode"] is False
    assert reread.json()["appearance"]["density"] == "compact"


async def test_saving_settings_twice_updates_one_row(client) -> None:
    """The table carries a per-user unique constraint; a second save must not insert."""
    first = await client.put("/settings", json={"onboarding_complete": True})
    second = await client.put("/settings", json={"onboarding_complete": False})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert (await client.get("/settings")).json()["onboarding_complete"] is False


async def test_storage_status_reports_the_local_paths(client) -> None:
    response = await client.get("/settings/storage")
    assert response.status_code == 200
    body = response.json()
    assert body["database_path"].endswith(".db")
    assert body["writable"] is True
    assert body["total_bytes"] == body["database_bytes"] + body["evidence_bytes"]


async def test_backup_returns_a_restorable_sqlite_file(client, case, tmp_path) -> None:
    import sqlite3

    response = await client.get("/settings/backup")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.sqlite3"
    assert "attachment" in response.headers["content-disposition"]

    # The point of a backup is that it opens again and still holds the data.
    restored = tmp_path / "restored.sqlite3"
    restored.write_bytes(response.content)
    connection = sqlite3.connect(restored)
    try:
        titles = [row[0] for row in connection.execute("SELECT title FROM cases")]
    finally:
        connection.close()
    assert case["title"] in titles


# --- Dashboard ----------------------------------------------------------------


async def test_dashboard_summarises_an_empty_workspace(client) -> None:
    response = await client.get("/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["active_investigations"] == 0
    assert body["recent_investigations"] == []


async def test_dashboard_counts_real_rows_only(client, case) -> None:
    await client.post(
        "/sources/text",
        json={
            "case_id": case["id"],
            "title": "Observed infrastructure",
            "body": "Contact reachable at analyst@example.com from 203.0.113.10.",
        },
    )
    body = (await client.get("/dashboard/summary")).json()
    assert body["counts"]["active_investigations"] == 1
    assert [row["id"] for row in body["recent_investigations"]] == [case["id"]]
    assert {row["action"] for row in body["recent_activity"]}


# --- Custody ------------------------------------------------------------------


async def test_custody_chain_is_intact_after_ingestion(client, case) -> None:
    await client.post(
        "/sources/text",
        json={"case_id": case["id"], "title": "First", "body": "Observed at 203.0.113.10 during the window."},
    )
    response = await client.get(f"/custody/{case['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["intact"] is True


async def test_custody_chain_covers_managed_evidence(client, case) -> None:
    upload = await client.post(
        "/evidence",
        data={"case_id": case["id"]},
        files={"file": ("note.txt", b"observed artifact", "text/plain")},
    )
    assert upload.status_code == 201, upload.text

    body = (await client.get(f"/custody/{case['id']}")).json()
    assert body["intact"] is True
    assert body["sealed_count"] >= 1
    assert body["first_broken_sequence"] is None


# --- Exports ------------------------------------------------------------------


async def test_case_export_is_well_formed_json(client, case) -> None:
    await client.post(
        "/sources/text",
        json={"case_id": case["id"], "title": "First", "body": "Observed at 203.0.113.10."},
    )
    response = await client.get(f"/exports/cases/{case['id']}/json")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]

    document = json.loads(response.text)
    assert document["case"]["title"] == case["title"]
    assert len(document["sources"]) == 1


async def test_export_of_an_inaccessible_case_is_refused(client) -> None:
    assert (await client.get("/exports/cases/does-not-exist/json")).status_code == 404


# --- Operations ---------------------------------------------------------------


async def test_providers_are_reported_without_inventing_adapters(client) -> None:
    response = await client.get("/operations/providers")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["total"] == len(catalog["providers"])
    # Every entry states whether it is actually usable rather than implying a
    # capability this install does not have.
    for provider in catalog["providers"]:
        assert provider["status"] in {"operational", "configured", "catalogued"}
        assert isinstance(provider["configured"], bool)
    # An unconfigured install must not claim search or model providers work.
    unconfigured = {row["id"] for row in catalog["providers"] if row["status"] == "catalogued"}
    assert {"searxng", "brave", "local-model"} <= unconfigured


async def test_audit_events_are_recorded_for_case_activity(client, case) -> None:
    response = await client.get("/operations/audit")
    assert response.status_code == 200
    actions = {row["action"] for row in response.json()}
    assert "case.created" in actions


async def test_audit_events_can_be_scoped_to_a_case(client, case) -> None:
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

    response = await client.get("/operations/audit", params={"case_id": case["id"]})
    assert response.status_code == 200
    case_ids = {row["case_id"] for row in response.json()}
    assert case_ids == {case["id"]}
    assert other["id"] not in case_ids
