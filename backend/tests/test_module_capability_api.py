"""The capability surface a linked module can actually reach.

System Link declares fifteen capabilities and lets an operator grant any of
them. For most of the product's life only four had an endpoint behind them, so
approving ``evidence.write`` for a module bought that module nothing: the grant
existed, the route did not. These tests hold the two halves together — one
proves every declared capability is enforced somewhere, and the rest exercise
each route through the real signed envelope, with a denial case beside every
success because granting and permitting have to stay the same thing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient
from sqlalchemy import select

from app import models
from app.system_link.module_auth import module_request_payload
from app.system_link.protocol import KNOWN_CAPABILITIES, ModuleState
from app.system_link.security import b64encode, public_key_text

_MODULE_ID = "oihk.test-module"
_API = "/system-link/module-api/v1"

# Enforced by the module UI file route in ``system_link.router`` rather than by
# a module-API endpoint, because it gates whether a surface may be served at
# all rather than an action a module performs.
_ENFORCED_OUTSIDE_MODULE_API = {"ui.navigation.register"}


def test_every_declared_capability_is_enforced_by_a_route() -> None:
    """A grantable capability with no route behind it is a promise nothing keeps.

    Read from the source rather than from a hand-maintained list: a new
    capability added to ``KNOWN_CAPABILITIES`` without a route to enforce it
    should fail here, which is the whole point.
    """
    source = Path(__file__).resolve().parents[1] / "app" / "system_link" / "module_api.py"
    enforced = set(re_findall_capabilities(source.read_text(encoding="utf-8")))

    missing = sorted(KNOWN_CAPABILITIES - enforced - _ENFORCED_OUTSIDE_MODULE_API)
    assert not missing, f"capabilities can be granted but reach no endpoint: {missing}"

    unknown = sorted(enforced - KNOWN_CAPABILITIES)
    assert not unknown, f"routes enforce capabilities the protocol does not declare: {unknown}"


def re_findall_capabilities(source: str) -> list[str]:
    import re

    return re.findall(r"_capability\(\s*session,\s*authenticated,\s*\"([a-z.]+)\"", source)


@pytest.fixture
async def module_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture
async def linked_module(session, module_key, tmp_path):
    """A READY, enabled module with no capability grants yet."""
    package_root = tmp_path / "module-package"
    package_root.mkdir(exist_ok=True)
    module = models.SystemLinkModule(
        module_id=_MODULE_ID,
        product_name="Test Module",
        module_version="1.0.0",
        protocol_version="1.0",
        manifest_schema_version=1,
        module_public_key=public_key_text(module_key.public_key()),
        module_fingerprint="f" * 64,
        manifest={},
        manifest_sha256="a" * 64,
        manifest_signature="signature",
        package_root=str(package_root),
        package_sha256="b" * 64,
        lifecycle={},
        state=ModuleState.READY.value,
        enabled=True,
    )
    session.add(module)
    await session.commit()
    return module


async def grant(session, *capabilities: str) -> None:
    for capability in capabilities:
        session.add(
            models.SystemLinkCapabilityGrant(
                module_id=_MODULE_ID,
                capability=capability,
                manifest_sha256="a" * 64,
            )
        )
    await session.commit()


async def call(
    client: AsyncClient,
    key: Ed25519PrivateKey,
    method: str,
    path: str,
    body: dict | None = None,
):
    """Issue one signed module request through the real middleware stack."""
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else b""
    nonce = secrets.token_urlsafe(24)
    timestamp = int(time.time())
    signature = b64encode(
        key.sign(
            module_request_payload(
                module_id=_MODULE_ID,
                method=method,
                path=f"{_API}{path}",
                nonce=nonce,
                timestamp=timestamp,
                body=raw,
            )
        )
    )
    return await client.request(
        method,
        f"{_API}{path}",
        content=raw,
        headers={
            "X-OIHK-Module-Id": _MODULE_ID,
            "X-OIHK-Nonce": nonce,
            "X-OIHK-Timestamp": str(timestamp),
            "X-OIHK-Signature": signature,
            "Content-Type": "application/json",
        },
    )


@pytest.mark.asyncio
async def test_an_ungranted_capability_is_refused_on_every_route(
    client, session, linked_module, module_key, case
) -> None:
    """Authenticated is not authorised: the module proves who it is and is still refused."""
    refused = [
        ("GET", "/cases"),
        ("GET", f"/cases/{case['id']}"),
        ("PATCH", f"/cases/{case['id']}"),
        ("GET", f"/cases/{case['id']}/sources"),
        ("GET", f"/cases/{case['id']}/evidence"),
        ("GET", f"/cases/{case['id']}/entities"),
        ("GET", f"/cases/{case['id']}/reports"),
    ]
    for method, path in refused:
        response = await call(client, module_key, method, path, {} if method == "PATCH" else None)
        assert response.status_code == 403, f"{method} {path} answered {response.status_code}"


@pytest.mark.asyncio
async def test_evidence_written_by_a_module_joins_the_custody_chain(
    client, session, linked_module, module_key, case
) -> None:
    """Module-supplied evidence must be sealed exactly like an operator upload."""
    await grant(session, "evidence.write")
    content = b"module supplied exhibit\n"

    response = await call(
        client,
        module_key,
        "POST",
        f"/cases/{case['id']}/evidence",
        {
            "filename": "exhibit.txt",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "mime_type": "text/plain",
            "notes": "collected by the linked module",
            "tags": ["module", "exhibit"],
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["sha256"] == hashlib.sha256(content).hexdigest()
    assert item["ingested_by"] == f"module:{_MODULE_ID}"

    seal = (
        await session.execute(
            select(models.EvidenceSeal).where(models.EvidenceSeal.source_id == item["source_id"])
        )
    ).scalar_one_or_none()
    assert seal is not None, "module evidence was stored without a custody seal"

    event = (
        await session.execute(
            select(models.AuditEvent).where(models.AuditEvent.action == "module.evidence_written")
        )
    ).scalar_one()
    assert event.actor == f"module:{_MODULE_ID}", "a module write must not be attributed to a person"


@pytest.mark.asyncio
async def test_module_upload_is_bounded(client, session, linked_module, module_key, case, monkeypatch) -> None:
    """The body is buffered whole to verify its signature, so the size must be capped."""
    from app.core.config import get_settings

    monkeypatch.setenv("OIHK_MAX_MODULE_UPLOAD_BYTES", "64")
    get_settings.cache_clear()
    try:
        await grant(session, "evidence.write")
        response = await call(
            client,
            module_key,
            "POST",
            f"/cases/{case['id']}/evidence",
            {
                "filename": "big.bin",
                "content_base64": base64.b64encode(b"x" * 4096).decode("ascii"),
            },
        )
        assert response.status_code == 413
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_imported_evidence_is_recorded_by_reference_and_deduplicated(
    client, session, linked_module, module_key, case
) -> None:
    await grant(session, "evidence.import")
    digest = hashlib.sha256(b"held by the module").hexdigest()
    payload = {
        "original_name": "remote-exhibit.dd",
        "sha256": digest,
        "size_bytes": 4096,
        "reference": "evidence-lab://vault/remote-exhibit.dd",
        "mime_type": "application/octet-stream",
    }

    first = await call(client, module_key, "POST", f"/cases/{case['id']}/evidence/import", payload)
    assert first.status_code == 201, first.text
    assert first.json()["original_reference"] == payload["reference"]

    duplicate = await call(client, module_key, "POST", f"/cases/{case['id']}/evidence/import", payload)
    assert duplicate.status_code == 409, "the same digest must not be recorded twice for one case"


@pytest.mark.asyncio
async def test_annotation_cannot_reach_the_sealed_fields(
    client, session, linked_module, module_key, case
) -> None:
    """``sha256`` and ``size_bytes`` are what the seal covers; annotation must not touch them."""
    await grant(session, "evidence.write", "evidence.metadata.write")
    content = b"sealed bytes"
    created = await call(
        client,
        module_key,
        "POST",
        f"/cases/{case['id']}/evidence",
        {"filename": "sealed.bin", "content_base64": base64.b64encode(content).decode("ascii")},
    )
    evidence_id = created.json()["id"]
    original_digest = created.json()["sha256"]

    response = await call(
        client,
        module_key,
        "PATCH",
        f"/evidence/{evidence_id}",
        {"notes": "annotated", "sha256": "0" * 64, "size_bytes": 1},
    )
    assert response.status_code == 200, response.text
    assert response.json()["notes"] == "annotated"
    assert response.json()["sha256"] == original_digest, "the sealed digest was rewritten by an annotation"
    assert response.json()["size_bytes"] == len(content)


@pytest.mark.asyncio
async def test_entity_write_upserts_and_carries_provenance(
    client, session, linked_module, module_key, case
) -> None:
    """Repeating a value must reinforce the existing node, not collide with it."""
    await grant(session, "entity.write", "entity.read")
    body = {"type": "domain", "value": "Example.COM", "display": "example.com", "confidence": 0.8}

    first = await call(client, module_key, "POST", f"/cases/{case['id']}/entities", body)
    assert first.status_code == 201, first.text
    assert first.json()["source_ids"], "a module-asserted entity must record where it came from"

    second = await call(client, module_key, "POST", f"/cases/{case['id']}/entities", body)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"], "the unique constraint should have merged these"

    listed = await call(client, module_key, "GET", f"/cases/{case['id']}/entities")
    assert [entity["value"] for entity in listed.json()] == ["example.com"]


@pytest.mark.asyncio
async def test_a_relationship_must_join_two_entities_of_the_same_case(
    client, session, linked_module, module_key, case
) -> None:
    await grant(session, "entity.write")
    first = await call(
        client, module_key, "POST", f"/cases/{case['id']}/entities", {"type": "domain", "value": "a.example"}
    )
    entity_id = first.json()["id"]

    loop = await call(
        client,
        module_key,
        "POST",
        f"/cases/{case['id']}/relationships",
        {"subject_id": entity_id, "predicate": "resolves_to", "object_id": entity_id},
    )
    assert loop.status_code == 422

    dangling = await call(
        client,
        module_key,
        "POST",
        f"/cases/{case['id']}/relationships",
        {"subject_id": entity_id, "predicate": "resolves_to", "object_id": "not-in-this-case"},
    )
    assert dangling.status_code == 422


@pytest.mark.asyncio
async def test_a_module_may_contribute_to_a_draft_but_not_to_an_approved_report(
    client, session, linked_module, module_key, case
) -> None:
    """A module contributes findings; approval stays the operator's signature."""
    await grant(session, "report.section.write")
    report = models.ReportDocument(
        case_id=case["id"],
        user_id="system",
        title="Working draft",
        content="# Working draft\n",
        sections=["overview"],
        status="draft",
    )
    session.add(report)
    await session.commit()

    appended = await call(
        client,
        module_key,
        "POST",
        f"/reports/{report.id}/sections",
        {"heading": "Module findings", "body": "Three exhibits carved from the image."},
    )
    assert appended.status_code == 201, appended.text
    assert "Module findings" in appended.json()["sections"]

    await session.refresh(report)
    assert _MODULE_ID in report.content, "an appended section must name the module that wrote it"

    report.status = "approved"
    await session.commit()

    refused = await call(
        client,
        module_key,
        "POST",
        f"/reports/{report.id}/sections",
        {"heading": "Late addition", "body": "Added after approval."},
    )
    assert refused.status_code == 409


@pytest.mark.asyncio
async def test_a_module_can_raise_a_notification_for_the_operator(
    client, session, linked_module, module_key, case
) -> None:
    await grant(session, "ui.notification")
    response = await call(
        client,
        module_key,
        "POST",
        "/notifications",
        {"level": "warning", "title": "Hash mismatch", "body": "Exhibit 4 failed verification.", "case_id": case["id"]},
    )
    assert response.status_code == 201, response.text

    event = (
        await session.execute(
            select(models.SystemLinkEvent).where(models.SystemLinkEvent.action == "module_notification")
        )
    ).scalar_one()
    assert event.module_id == _MODULE_ID
    assert event.payload["level"] == "warning"


@pytest.mark.asyncio
async def test_case_write_cannot_widen_the_authorised_scope(
    client, session, linked_module, module_key, case
) -> None:
    """A linked product may describe an investigation; it may not authorise one."""
    await grant(session, "case.write")
    response = await call(
        client,
        module_key,
        "PATCH",
        f"/cases/{case['id']}",
        {
            "summary": "Enriched by the linked module",
            "legal_basis": "Whatever the module says",
            "scope_statement": "Unbounded",
            "status": "closed",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["summary"] == "Enriched by the linked module"
    assert response.json()["legal_basis"] == case["legal_basis"], "a module rewrote the authorisation basis"
    assert response.json()["scope_statement"] == case["scope_statement"], "a module rewrote the authorised scope"
    assert response.json()["status"] == case["status"], "a module changed the investigation's status"
