"""Capability-gated generic host APIs for authenticated System Link modules.

Every route here is reached only by a module that has proved its identity with
a signed, timestamped, replay-protected envelope (see ``module_auth``), and
each one names the single capability it requires. Granting a capability and
being able to use it are the same thing here by construction: a route without
a ``_capability`` call would be a route no grant controls.

The routes deliberately do not reimplement the application. Evidence written by
a module goes through the same ``store_evidence_bytes`` + ``seal_source`` pair
as an operator upload, so it lands in the same custody chain and is
indistinguishable from any other exhibit at verification time — the only
difference is the actor recorded against it, which is the module rather than a
person.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.config import get_settings
from app.database import get_session
from app.services.analyzer import ExtractedEntity, normalize_value
from app.services.custody import seal_source
from app.services.evidence_storage import safe_storage_path, store_evidence_bytes
from app.services.repository import audit, upsert_entity
from app.system_link.capabilities import CapabilityDenied, require_capability
from app.system_link.module_auth import authenticate_module_request
from app.system_link.protocol import ModuleState
from app.system_link.service import SystemLinkError, SystemLinkService

router = APIRouter(prefix="/system-link/module-api/v1", tags=["system-link-module-api"])


@dataclass(frozen=True)
class AuthenticatedModule:
    record: models.SystemLinkModule

    @property
    def actor(self) -> str:
        """Audit identity for anything this module writes.

        Prefixed so a module can never be confused with a username in the audit
        trail, and so filtering the trail by originator is a prefix match.
        """
        return f"module:{self.record.module_id}"


async def authenticated_module(
    request: Request,
    module_id: str = Header(alias="X-OIHK-Module-Id"),
    nonce: str = Header(alias="X-OIHK-Nonce"),
    timestamp: int = Header(alias="X-OIHK-Timestamp"),
    signature: str = Header(alias="X-OIHK-Signature"),
    session: AsyncSession = Depends(get_session),
) -> AuthenticatedModule:
    try:
        module = await authenticate_module_request(
            session,
            module_id=module_id,
            method=request.method,
            path=request.url.path,
            nonce=nonce,
            timestamp=timestamp,
            body=await request.body(),
            signature=signature,
        )
    except SystemLinkError as exc:
        raise HTTPException(status_code=401, detail=f"{exc.code}: {exc}") from exc
    return AuthenticatedModule(module)


async def _capability(
    session: AsyncSession,
    authenticated: AuthenticatedModule,
    capability: str,
) -> models.SystemLinkModule:
    try:
        return await require_capability(session, authenticated.record.module_id, capability)
    except CapabilityDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


async def _require_case(session: AsyncSession, case_id: str) -> models.Case:
    case = await session.get(models.Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _case_payload(case: models.Case) -> dict[str, Any]:
    return {
        "id": case.id,
        "title": case.title,
        "summary": case.summary,
        "legal_basis": case.legal_basis,
        "scope_statement": case.scope_statement,
        "status": case.status,
        "priority": case.priority,
        "tags": case.tags,
        "updated_at": case.updated_at,
    }


def _evidence_payload(item: models.EvidenceItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "case_id": item.case_id,
        "source_id": item.source_id,
        "original_name": item.original_name,
        "mime_type": item.mime_type,
        "size_bytes": item.size_bytes,
        "sha256": item.sha256,
        "notes": item.notes,
        "tags": item.tags,
        "entity_ids": item.entity_ids,
        "ingested_by": item.ingested_by,
        "original_reference": item.original_reference,
        "created_at": item.created_at,
        "verified_at": item.verified_at,
    }


def _decode_upload(encoded: str) -> bytes:
    """Decode a base64 body under the module upload ceiling.

    The encoded length is checked first: base64 inflates by 4/3, so refusing
    on the wire size avoids allocating the decoded buffer for a payload that
    was always going to be rejected.
    """
    limit = get_settings().max_module_upload_bytes
    if len(encoded) > (limit // 3 + 1) * 4 + 16:
        raise HTTPException(status_code=413, detail=f"Module upload exceeds the {limit}-byte limit")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="content_base64 is not valid base64") from exc
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"Module upload exceeds the {limit}-byte limit")
    if not data:
        raise HTTPException(status_code=422, detail="Module upload is empty")
    return data


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------


@router.get("/cases")
async def list_cases(
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List the investigations a module may attach work to."""
    await _capability(session, authenticated, "case.metadata.read")
    rows = list(
        (
            await session.execute(
                select(models.Case).where(models.Case.archived_at.is_(None)).order_by(models.Case.updated_at.desc())
            )
        ).scalars()
    )
    return [_case_payload(case) for case in rows]


@router.get("/cases/{case_id}")
async def read_case(
    case_id: str,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _capability(session, authenticated, "case.read")
    return _case_payload(await _require_case(session, case_id))


class CaseMetadataWrite(BaseModel):
    summary: str | None = Field(default=None, max_length=20_000)
    notes: str | None = Field(default=None, max_length=50_000)
    tags: list[str] | None = Field(default=None, max_length=100)


@router.patch("/cases/{case_id}")
async def update_case(
    case_id: str,
    payload: CaseMetadataWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Update descriptive case metadata.

    Deliberately narrower than the operator route: a module may enrich the
    description of an investigation but may not change its ``status``, its
    ``legal_basis`` or its ``scope_statement``. Those three state what the
    investigation is authorised to do, and that authorisation is the operator's
    to give, not a linked product's.
    """
    await _capability(session, authenticated, "case.write")
    case = await _require_case(session, case_id)
    changed: list[str] = []
    if payload.summary is not None:
        case.summary = payload.summary.strip()
        changed.append("summary")
    if payload.notes is not None:
        case.notes = payload.notes.strip()
        changed.append("notes")
    if payload.tags is not None:
        case.tags = [tag.strip()[:80] for tag in payload.tags if tag.strip()][:100]
        changed.append("tags")
    case.updated_at = datetime.now(UTC)
    await audit(session, "module.case_updated", case_id, {"fields": changed}, actor=authenticated.actor)
    await session.commit()
    await session.refresh(case)
    return _case_payload(case)


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------


@router.get("/cases/{case_id}/sources")
async def read_sources(
    case_id: str,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await _capability(session, authenticated, "source.read")
    rows = list(
        (
            await session.execute(
                select(models.Source)
                .where(models.Source.case_id == case_id)
                .order_by(models.Source.collected_at.desc())
            )
        ).scalars()
    )
    return [
        {
            "id": source.id,
            "case_id": source.case_id,
            "title": source.title,
            "kind": source.kind,
            "url": source.url,
            "citation": source.citation,
            "license": source.license,
            "reliability": source.reliability,
            "collected_at": source.collected_at,
        }
        for source in rows
    ]


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------


@router.get("/cases/{case_id}/evidence")
async def read_evidence(
    case_id: str,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await _capability(session, authenticated, "evidence.read")
    rows = list(
        (
            await session.execute(
                select(models.EvidenceItem)
                .where(models.EvidenceItem.case_id == case_id)
                .order_by(models.EvidenceItem.created_at.desc())
            )
        ).scalars()
    )
    return [_evidence_payload(item) for item in rows]


class EvidenceWrite(BaseModel):
    filename: str = Field(min_length=1, max_length=260)
    content_base64: str = Field(min_length=1)
    mime_type: str = Field(default="application/octet-stream", max_length=160)
    notes: str = Field(default="", max_length=50_000)
    tags: list[str] = Field(default_factory=list, max_length=100)


@router.post("/cases/{case_id}/evidence", status_code=201)
async def write_evidence(
    case_id: str,
    payload: EvidenceWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Ingest bytes supplied by a module as sealed, managed evidence.

    This is the same sequence the operator upload route runs — store, create a
    provenance source, seal it into the case's custody chain, then record the
    item — so module-supplied evidence verifies exactly like any other. The
    file is unlinked if any later step fails, so a failed ingest never leaves
    an orphan in managed storage that no record accounts for.
    """
    await _capability(session, authenticated, "evidence.write")
    await _require_case(session, case_id)
    data = _decode_upload(payload.content_base64)

    stored = store_evidence_bytes(
        case_id,
        payload.filename,
        data,
        content_type=payload.mime_type,
    )
    path_value = str(stored["storage_path"])
    try:
        source = models.Source(
            case_id=case_id,
            title=f"Evidence: {stored['filename']}"[:240],
            kind="module_evidence",
            body=(
                f"Module-supplied evidence file\nmodule_id={authenticated.record.module_id}\n"
                f"original_name={stored['filename']}\nsha256={stored['sha256']}\n"
                f"size_bytes={stored['size_bytes']}\nmime_type={stored['content_type']}"
            ),
            citation=f"sha256:{stored['sha256']}",
            license="case-evidence",
            reliability=1.0,
        )
        session.add(source)
        await session.flush()
        await seal_source(session, source, storage_path=path_value)
        item = models.EvidenceItem(
            case_id=case_id,
            source_id=source.id,
            original_name=str(stored["filename"]),
            storage_path=path_value,
            mime_type=str(stored["content_type"]),
            size_bytes=int(stored["size_bytes"]),
            sha256=str(stored["sha256"]),
            notes=payload.notes.strip(),
            tags=[tag.strip()[:80] for tag in payload.tags if tag.strip()][:100],
            ingested_by=authenticated.actor,
            original_reference=payload.filename,
        )
        session.add(item)
        await audit(
            session,
            "module.evidence_written",
            case_id,
            {"evidence_id": item.id, "sha256": item.sha256, "size_bytes": item.size_bytes},
            actor=authenticated.actor,
        )
        await session.commit()
        await session.refresh(item)
        return _evidence_payload(item)
    except Exception:
        safe_storage_path(path_value).unlink(missing_ok=True)
        raise


class EvidenceImport(BaseModel):
    """Register evidence a module holds in its own store, by reference."""

    original_name: str = Field(min_length=1, max_length=260)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")
    size_bytes: int = Field(ge=0)
    reference: str = Field(min_length=1, max_length=500)
    mime_type: str = Field(default="application/octet-stream", max_length=160)
    notes: str = Field(default="", max_length=50_000)
    tags: list[str] = Field(default_factory=list, max_length=100)


@router.post("/cases/{case_id}/evidence/import", status_code=201)
async def import_evidence(
    case_id: str,
    payload: EvidenceImport,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Record evidence that stays in the module's custody, without copying bytes.

    ``evidence.write`` moves the bytes into Basic's managed storage;
    this records that an exhibit exists elsewhere, under a digest Basic can
    later demand a match for. The two are separate capabilities because they
    carry different promises: an imported item's bytes are not in managed
    storage, so the custody seal covers the *assertion* about the file, not the
    file itself, and ``storage_path`` is left empty rather than pointing at
    something Basic does not hold.
    """
    await _capability(session, authenticated, "evidence.import")
    await _require_case(session, case_id)

    existing = (
        await session.execute(
            select(models.EvidenceItem).where(
                models.EvidenceItem.case_id == case_id,
                models.EvidenceItem.sha256 == payload.sha256.lower(),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Evidence with this digest is already recorded for the case")

    descriptor = (
        f"Referenced evidence held by a linked module\nmodule_id={authenticated.record.module_id}\n"
        f"original_name={payload.original_name}\nsha256={payload.sha256.lower()}\n"
        f"size_bytes={payload.size_bytes}\nreference={payload.reference}"
    )
    source = models.Source(
        case_id=case_id,
        title=f"Referenced evidence: {payload.original_name}"[:240],
        kind="module_evidence_reference",
        body=descriptor,
        citation=f"sha256:{payload.sha256.lower()}",
        license="case-evidence",
        reliability=1.0,
    )
    session.add(source)
    await session.flush()
    await seal_source(session, source, raw_bytes=descriptor.encode("utf-8"))
    item = models.EvidenceItem(
        case_id=case_id,
        source_id=source.id,
        original_name=payload.original_name,
        storage_path="",
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256.lower(),
        notes=payload.notes.strip(),
        tags=[tag.strip()[:80] for tag in payload.tags if tag.strip()][:100],
        ingested_by=authenticated.actor,
        original_reference=payload.reference,
    )
    session.add(item)
    await audit(
        session,
        "module.evidence_imported",
        case_id,
        {"evidence_id": item.id, "sha256": item.sha256, "reference": payload.reference},
        actor=authenticated.actor,
    )
    await session.commit()
    await session.refresh(item)
    return _evidence_payload(item)


class EvidenceMetadataWrite(BaseModel):
    notes: str | None = Field(default=None, max_length=50_000)
    tags: list[str] | None = Field(default=None, max_length=100)
    entity_ids: list[str] | None = Field(default=None, max_length=500)


@router.patch("/evidence/{evidence_id}")
async def update_evidence_metadata(
    evidence_id: str,
    payload: EvidenceMetadataWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Annotate an exhibit without touching the exhibit.

    ``sha256``, ``storage_path`` and ``size_bytes`` are absent from the payload
    by construction: they are what the custody seal covers, and a route that
    could rewrite them would let a linked module invalidate the chain from
    inside. Annotation and content are separate powers here.
    """
    await _capability(session, authenticated, "evidence.metadata.write")
    item = await session.get(models.EvidenceItem, evidence_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Evidence item not found")

    changed: list[str] = []
    if payload.notes is not None:
        item.notes = payload.notes.strip()
        changed.append("notes")
    if payload.tags is not None:
        item.tags = [tag.strip()[:80] for tag in payload.tags if tag.strip()][:100]
        changed.append("tags")
    if payload.entity_ids is not None:
        known = set(
            (
                await session.execute(
                    select(models.Entity.id).where(
                        models.Entity.case_id == item.case_id,
                        models.Entity.id.in_(payload.entity_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        unknown = sorted(set(payload.entity_ids) - known)
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Entity ids are not in this case: {', '.join(unknown[:5])}",
            )
        item.entity_ids = list(dict.fromkeys(payload.entity_ids))
        changed.append("entity_ids")

    item.updated_at = datetime.now(UTC)
    await audit(
        session,
        "module.evidence_annotated",
        item.case_id,
        {"evidence_id": item.id, "fields": changed},
        actor=authenticated.actor,
    )
    await session.commit()
    await session.refresh(item)
    return _evidence_payload(item)


# --------------------------------------------------------------------------
# Graph entities
# --------------------------------------------------------------------------


@router.get("/cases/{case_id}/entities")
async def read_entities(
    case_id: str,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await _capability(session, authenticated, "entity.read")
    rows = list(
        (
            await session.execute(
                select(models.Entity)
                .where(models.Entity.case_id == case_id)
                .order_by(models.Entity.last_seen.desc())
            )
        ).scalars()
    )
    return [
        {
            "id": entity.id,
            "case_id": entity.case_id,
            "type": entity.type,
            "value": entity.value,
            "display": entity.display,
            "confidence": entity.confidence,
            "source_ids": entity.source_ids,
            "properties": entity.properties,
            "first_seen": entity.first_seen,
            "last_seen": entity.last_seen,
        }
        for entity in rows
    ]


class EntityWrite(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=500)
    display: str = Field(default="", max_length=500)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    source_id: str | None = None


@router.post("/cases/{case_id}/entities", status_code=201)
async def write_entity(
    case_id: str,
    payload: EntityWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Add or reinforce one graph entity, reusing the app's own upsert.

    ``entities`` is unique on ``(case_id, type, value)``, so a module that
    re-reports a value it has seen before must merge with the existing row
    rather than collide with it — which is exactly what ``upsert_entity``
    already does for OSINT and transform results.
    """
    await _capability(session, authenticated, "entity.write")
    await _require_case(session, case_id)

    source_id = payload.source_id
    if source_id is not None:
        source = await session.get(models.Source, source_id)
        if source is None or source.case_id != case_id:
            raise HTTPException(status_code=422, detail="source_id does not belong to this case")
    else:
        # Provenance is not optional in a forensics graph: an entity with no
        # source cannot be traced back to why it is on the board. A module that
        # names no source gets one standing for the module itself.
        source = models.Source(
            case_id=case_id,
            title=f"Linked module: {authenticated.record.module_id}"[:240],
            kind="module_assertion",
            body=f"Entity asserted by linked module {authenticated.record.module_id}",
            citation=f"module:{authenticated.record.module_id}",
            license="module-supplied",
            reliability=payload.confidence,
        )
        session.add(source)
        await session.flush()
        source_id = source.id

    normalized = normalize_value(payload.type, payload.value)
    entity = await upsert_entity(
        session,
        case_id,
        source_id,
        ExtractedEntity(
            type=payload.type,
            value=normalized,
            display=payload.display.strip() or payload.value,
            confidence=payload.confidence,
        ),
    )
    await audit(
        session,
        "module.entity_written",
        case_id,
        {"entity_id": entity.id, "type": entity.type},
        actor=authenticated.actor,
    )
    await session.commit()
    await session.refresh(entity)
    return {
        "id": entity.id,
        "case_id": entity.case_id,
        "type": entity.type,
        "value": entity.value,
        "display": entity.display,
        "confidence": entity.confidence,
        "source_ids": entity.source_ids,
    }


class RelationshipWrite(BaseModel):
    subject_id: str = Field(min_length=1, max_length=36)
    predicate: str = Field(min_length=1, max_length=80)
    object_id: str = Field(min_length=1, max_length=36)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


@router.post("/cases/{case_id}/relationships", status_code=201)
async def write_relationship(
    case_id: str,
    payload: RelationshipWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _capability(session, authenticated, "entity.write")
    await _require_case(session, case_id)
    if payload.subject_id == payload.object_id:
        raise HTTPException(status_code=422, detail="A relationship may not connect an entity to itself")

    endpoints = {
        entity.id: entity
        for entity in (
            await session.execute(
                select(models.Entity).where(
                    models.Entity.case_id == case_id,
                    models.Entity.id.in_([payload.subject_id, payload.object_id]),
                )
            )
        )
        .scalars()
        .all()
    }
    missing = sorted({payload.subject_id, payload.object_id} - endpoints.keys())
    if missing:
        raise HTTPException(status_code=422, detail=f"Entity ids are not in this case: {', '.join(missing)}")

    relationship = models.Relationship(
        case_id=case_id,
        subject_id=payload.subject_id,
        predicate=payload.predicate.strip(),
        object_id=payload.object_id,
        confidence=payload.confidence,
    )
    session.add(relationship)
    await audit(
        session,
        "module.relationship_written",
        case_id,
        {"subject_id": payload.subject_id, "predicate": relationship.predicate, "object_id": payload.object_id},
        actor=authenticated.actor,
    )
    await session.commit()
    await session.refresh(relationship)
    return {
        "id": relationship.id,
        "case_id": relationship.case_id,
        "subject_id": relationship.subject_id,
        "predicate": relationship.predicate,
        "object_id": relationship.object_id,
        "confidence": relationship.confidence,
    }


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


@router.get("/cases/{case_id}/reports")
async def read_reports(
    case_id: str,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await _capability(session, authenticated, "report.read")
    rows = list(
        (
            await session.execute(
                select(models.ReportDocument)
                .where(models.ReportDocument.case_id == case_id)
                .order_by(models.ReportDocument.created_at.desc())
            )
        ).scalars()
    )
    return [
        {
            "id": report.id,
            "case_id": report.case_id,
            "title": report.title,
            "format": report.format,
            "sections": report.sections,
            "status": report.status,
            "created_at": report.created_at,
            "updated_at": report.updated_at,
        }
        for report in rows
    ]


class ReportSectionWrite(BaseModel):
    heading: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=200_000)


@router.post("/reports/{report_id}/sections", status_code=201)
async def write_report_section(
    report_id: str,
    payload: ReportSectionWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Append one attributed section to a draft report.

    A module may contribute findings; it may not sign off on them. Appending is
    refused once a report leaves ``draft``, so an approved document cannot
    acquire new content after the operator approved what it said — and every
    appended section carries the module's name in the text, so a reader can
    see which findings came from where without consulting the audit trail.
    """
    await _capability(session, authenticated, "report.section.write")
    report = await session.get(models.ReportDocument, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "draft":
        raise HTTPException(
            status_code=409,
            detail=f"Report is {report.status}; only a draft accepts new sections",
        )

    heading = payload.heading.strip()
    attribution = f"_Contributed by linked module `{authenticated.record.module_id}`._"
    report.content = f"{report.content.rstrip()}\n\n## {heading}\n\n{attribution}\n\n{payload.body.strip()}\n"
    report.sections = [*(report.sections or []), heading]
    report.updated_at = datetime.now(UTC)
    await audit(
        session,
        "module.report_section_written",
        report.case_id,
        {"report_id": report.id, "heading": heading},
        actor=authenticated.actor,
    )
    await session.commit()
    await session.refresh(report)
    return {
        "id": report.id,
        "case_id": report.case_id,
        "title": report.title,
        "sections": report.sections,
        "status": report.status,
        "updated_at": report.updated_at,
    }


# --------------------------------------------------------------------------
# Host UI
# --------------------------------------------------------------------------


class NotificationWrite(BaseModel):
    level: Literal["info", "warning", "error"] = "info"
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=2_000)
    case_id: str | None = Field(default=None, max_length=36)


@router.post("/notifications", status_code=201)
async def publish_notification(
    payload: NotificationWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Raise a message for the operator in Basic's own interface.

    Recorded as a ``SystemLinkEvent`` rather than in a table of its own: a
    notification *is* a module event, the control plane already reads that
    stream, and a second near-identical table would only create two places to
    look for the same history.
    """
    await _capability(session, authenticated, "ui.notification")
    if payload.case_id:
        await _require_case(session, payload.case_id)
    event = models.SystemLinkEvent(
        module_id=authenticated.record.module_id,
        action="module_notification",
        payload={
            "level": payload.level,
            "title": payload.title.strip(),
            "body": payload.body.strip(),
            "case_id": payload.case_id,
        },
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return {"id": event.id, "created_at": event.created_at}


# --------------------------------------------------------------------------
# Runtime status
# --------------------------------------------------------------------------


class ModuleStatusWrite(BaseModel):
    status: ModuleState
    detail: str = ""


@router.post("/status")
async def publish_status(
    payload: ModuleStatusWrite,
    authenticated: AuthenticatedModule = Depends(authenticated_module),
    session: AsyncSession = Depends(get_session),
) -> dict:
    module = await _capability(session, authenticated, "module.status.publish")
    if payload.status not in {ModuleState.READY, ModuleState.BUSY, ModuleState.ERROR}:
        raise HTTPException(status_code=422, detail="A runtime may publish only READY, BUSY, or ERROR")
    service = SystemLinkService(session)
    current = ModuleState(module.state)
    if payload.status != current:
        await service.transition(
            module,
            payload.status,
            error_code="module_reported_error" if payload.status == ModuleState.ERROR else "",
            error_detail=payload.detail,
            event="module_runtime_status_published",
        )
    else:
        module.last_health_at = datetime.now(UTC)
        await session.commit()
    return {"module_id": module.module_id, "state": module.state}
