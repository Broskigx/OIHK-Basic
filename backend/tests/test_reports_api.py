"""Report generation, approval and export over HTTP."""

from __future__ import annotations

import json

import pytest

HOSTILE_TITLE = "<script>alert('xss')</script>"


async def _generate(client, case_id: str, **overrides):
    payload = {"title": "Interim findings", "sections": ["summary", "entities"], "format": "markdown"}
    payload.update(overrides)
    return await client.post(f"/reports/{case_id}/generate", json=payload)


async def test_generate_a_markdown_report(client, case) -> None:
    response = await _generate(client, case["id"])
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["format"] == "markdown"
    assert document["status"] == "draft"
    assert document["ai_generated"] is False
    assert "Interim findings" in document["content"]


async def test_generated_reports_are_listed_for_the_case(client, case) -> None:
    await _generate(client, case["id"], title="First")
    await _generate(client, case["id"], title="Second")

    listed = await client.get(f"/reports/case/{case['id']}")
    assert listed.status_code == 200
    assert {row["title"] for row in listed.json()} == {"First", "Second"}


@pytest.mark.parametrize("format_name", ["markdown", "html", "json"])
async def test_every_supported_format_renders(client, case, format_name: str) -> None:
    response = await _generate(client, case["id"], format=format_name)
    assert response.status_code == 201, response.text
    assert response.json()["format"] == format_name


async def test_json_reports_are_valid_json(client, case) -> None:
    document = (await _generate(client, case["id"], format="json")).json()
    parsed = json.loads(document["content"])
    assert parsed["title"] == "Interim findings"


async def test_html_reports_escape_untrusted_titles(client, case) -> None:
    """A report title is operator input, but it is not markup."""
    document = (await _generate(client, case["id"], format="html", title=HOSTILE_TITLE)).json()
    content = document["content"]
    assert "<script>" not in content
    assert "&lt;script&gt;" in content


async def test_markdown_reports_do_not_interpret_a_hostile_title(client, case) -> None:
    """Markdown is exported as-is; the escaping happens when it becomes HTML."""
    document = (await _generate(client, case["id"], format="markdown", title=HOSTILE_TITLE)).json()
    assert HOSTILE_TITLE in document["content"]

    html_document = (await _generate(client, case["id"], format="html", title=HOSTILE_TITLE)).json()
    assert "<script>" not in html_document["content"]


async def test_html_reports_carry_a_restrictive_policy(client, case) -> None:
    document = (await _generate(client, case["id"], format="html")).json()
    assert "default-src 'none'" in document["content"]


async def test_a_draft_can_be_approved_once(client, case) -> None:
    document = (await _generate(client, case["id"])).json()
    approved = await client.post(f"/reports/documents/{document['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


async def test_export_serves_the_document_as_an_attachment(client, case) -> None:
    document = (await _generate(client, case["id"])).json()
    exported = await client.get(f"/reports/documents/{document['id']}/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    assert "Interim findings" in exported.text


async def test_export_of_an_unknown_document_is_not_found(client) -> None:
    assert (await client.get("/reports/documents/does-not-exist/export")).status_code == 404


async def test_a_document_can_be_deleted(client, case) -> None:
    document = (await _generate(client, case["id"])).json()
    assert (await client.delete(f"/reports/documents/{document['id']}")).status_code == 204
    assert (await client.get(f"/reports/case/{case['id']}")).json() == []


async def test_case_markdown_shortcut_renders(client, case) -> None:
    response = await client.get(f"/reports/{case['id']}.md")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert case["title"] in response.text


async def test_reports_for_an_inaccessible_case_are_refused(client) -> None:
    assert (await _generate(client, "does-not-exist")).status_code == 404
    assert (await client.get("/reports/case/does-not-exist")).status_code == 404


# --- Templates ----------------------------------------------------------------


async def test_templates_can_be_created_listed_and_deleted(client) -> None:
    created = await client.post(
        "/reports/templates",
        json={
            "name": "Standard intake",
            "format": "markdown",
            "sections": ["summary", "entities"],
            "methodology": "Open-source collection only.",
            "limitations": "Unverified model output excluded.",
        },
    )
    assert created.status_code == 201, created.text
    template = created.json()

    listed = await client.get("/reports/templates")
    assert [row["id"] for row in listed.json()] == [template["id"]]

    assert (await client.delete(f"/reports/templates/{template['id']}")).status_code == 204
    assert (await client.get("/reports/templates")).json() == []
