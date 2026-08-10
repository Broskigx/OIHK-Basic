"""Forensic Core analysis pipeline for OIHK Basic."""

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_admin, require_case_access
from app.database import get_session
from app.forensic import analyze_file
from app.schemas import (
    CarvedArtifactRead,
    CarveResult,
    CorrelationHitRead,
    CorrelationIndexRequest,
    CorrelationQueryResult,
    FileAnalysisRead,
    ForensicCoreRead,
    HashLookupRequest,
    HashLookupResult,
    HashMatchRead,
    HashResultRead,
    HashSetImportRequest,
    HashSetImportResult,
    HashSetInfoRead,
    InterestingRuleCreate,
    InterestingRuleRead,
    IocMatchRead,
    IocReportRead,
    MetadataFieldRead,
    MetadataReportRead,
    TextExtractionRead,
    TimelineEventRead,
)
from app.services import correlation, hash_intel, interesting_files
from app.services.custody import seal_source
from app.services.evidence_storage import store_evidence_bytes
from app.services.forensic_evidence import carve_and_seal
from app.services.repository import audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forensic-core", tags=["forensic-core"])

MAX_UPLOAD_BYTES = 64 * 1024 * 1024  # 64 MB


def _report_to_schema(core_report, *, source_id=None, stored_sha256=None, custody_sequence=None, custody_sealed=False):
    return ForensicCoreRead(
        filename=core_report.filename,
        source_id=source_id,
        stored_sha256=stored_sha256,
        custody_sequence=custody_sequence,
        custody_sealed=custody_sealed,
        hashes=[
            HashResultRead(
                algorithm=h.algorithm,
                digest=h.digest,
                size_bytes=h.size_bytes,
                elapsed_ms=h.elapsed_ms,
                target=h.target,
            )
            for h in core_report.hashes
        ],
        file_analysis=FileAnalysisRead(
            filename=core_report.file_analysis.filename,
            size_bytes=core_report.file_analysis.size_bytes,
            extension=core_report.file_analysis.extension,
            mime_type=core_report.file_analysis.mime_type,
            magic_bytes=core_report.file_analysis.magic_bytes,
            detected_type=core_report.file_analysis.detected_type,
            detected_label=core_report.file_analysis.detected_label,
            entropy=core_report.file_analysis.entropy,
            hashes=core_report.file_analysis.hashes,
            timestamps=core_report.file_analysis.timestamps,
            permissions=core_report.file_analysis.permissions,
            discrepancies=core_report.file_analysis.discrepancies,
        )
        if core_report.file_analysis
        else None,
        metadata=MetadataReportRead(
            format=core_report.metadata.format,
            fields=[
                MetadataFieldRead(key=f.key, value=f.value, category=f.category) for f in core_report.metadata.fields
            ],
            raw=core_report.metadata.raw,
            errors=core_report.metadata.errors,
        )
        if core_report.metadata
        else None,
        text_extraction=TextExtractionRead(
            format=core_report.text_extraction.format,
            text=core_report.text_extraction.text,
            char_count=core_report.text_extraction.char_count,
            word_count=core_report.text_extraction.word_count,
            errors=core_report.text_extraction.errors,
        )
        if core_report.text_extraction
        else None,
        iocs=IocReportRead(
            matches=[
                IocMatchRead(
                    type=m.type,
                    value=m.value,
                    display=m.display,
                    confidence=m.confidence,
                    offset=m.offset,
                    context=m.context,
                )
                for m in core_report.iocs.matches
            ],
            asn_lookups=core_report.iocs.asn_lookups,
        )
        if core_report.iocs
        else None,
        timeline_events=[
            TimelineEventRead(
                event_id=e.event_id,
                source_id=e.source_id,
                title=e.title,
                event_type=e.event_type,
                timestamp=e.timestamp,
                detail=e.detail,
                metadata=e.metadata,
            )
            for e in core_report.timeline_events
        ],
        errors=core_report.errors,
    )


@router.post("/analyze", response_model=ForensicCoreRead, status_code=200)
async def core_analyze(
    case_id: str = Form(...),
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ForensicCoreRead:
    """Run the full Forensic Core pipeline on an uploaded file."""
    await require_case_access(session, case_id, current)

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_BYTES} bytes")

    report = analyze_file(
        data, filename=file.filename or "upload", content_type=file.content_type or ""
    )

    stored = store_evidence_bytes(
        case_id,
        report.filename,
        data,
        content_type=file.content_type or "application/octet-stream",
        subdir="forensic-core",
    )

    body_lines = [f"Forensic Core Analysis: {report.filename}", "", "--- Hashes ---"]
    for h in report.hashes:
        body_lines.append(f"  {h.algorithm}: {h.digest} ({h.elapsed_ms} ms)")
    if report.file_analysis:
        body_lines.extend(
            [
                "",
                "--- File Analysis ---",
                f"  MIME: {report.file_analysis.mime_type}",
                f"  Detected: {report.file_analysis.detected_type} ({report.file_analysis.detected_label})",
                f"  Entropy: {report.file_analysis.entropy}",
                f"  Size: {report.file_analysis.size_bytes} bytes",
            ]
        )
        if report.file_analysis.discrepancies:
            body_lines.extend(["  Discrepancies:", *[f"    - {d}" for d in report.file_analysis.discrepancies]])
    if report.iocs and report.iocs.matches:
        body_lines.extend(["", "--- IOCs Found ---"])
        ioc_types: dict[str, int] = {}
        for m in report.iocs.matches:
            ioc_types[m.type] = ioc_types.get(m.type, 0) + 1
        for ioc_type, count in sorted(ioc_types.items()):
            body_lines.append(f"  {ioc_type}: {count}")
        body_lines.append("")
        for m in report.iocs.matches[:50]:
            body_lines.append(f"  [{m.type}] {m.value}")
    if report.timeline_events:
        body_lines.extend(["", "--- Timeline ---"])
        for evt in report.timeline_events[:20]:
            body_lines.append(f"  {evt.timestamp} [{evt.event_type}] {evt.title}")

    source = models.Source(
        case_id=case_id,
        title=f"Forensic Core: {report.filename}"[:240],
        kind="forensic_core",
        body="\n".join(body_lines),
        citation=f"sha256:{stored['sha256']}",
        license="forensic-analysis",
        reliability=0.85,
    )
    session.add(source)
    await session.flush()
    seal = await seal_source(session, source, raw_bytes=data, storage_path=stored["storage_path"])
    await correlation.index_attribute(
        session,
        organization_id=current.organization_id,
        case_id=case_id,
        attr_type="file_hash",
        value=stored["sha256"],
        source_id=source.id,
    )
    await audit(
        session,
        "forensic_core.analyzed",
        case_id,
        {
            "source_id": source.id,
            "filename": report.filename,
            "hash_count": len(report.hashes),
            "ioc_count": len(report.iocs.matches) if report.iocs else 0,
            "errors": report.errors,
        },
        actor=current.username,
    )
    await session.commit()
    return _report_to_schema(
        report, source_id=source.id, stored_sha256=stored["sha256"], custody_sequence=seal.sequence, custody_sealed=True
    )


@router.get("/iocs/{case_id}", response_model=IocReportRead)
async def list_case_iocs(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IocReportRead:
    """Aggregate IOCs from all sources in a case."""
    from sqlalchemy import select

    from app import models
    from app.forensic.ioc.extractor import extract_iocs

    await require_case_access(session, case_id, current)
    sources = (
        (
            await session.execute(
                select(models.Source)
                .where(models.Source.case_id == case_id)
                .order_by(models.Source.collected_at.desc())
            )
        )
        .scalars()
        .all()
    )
    all_matches = []
    asn_lookups = []
    for source in sources:
        body = (source.body or "")[:10000]
        report = extract_iocs(body)
        for m in report.matches:
            m.context = f"source:{source.id}"
        all_matches.extend(report.matches)
        asn_lookups.extend(report.asn_lookups)
    seen = set()
    deduped = []
    for m in all_matches:
        key = (m.type, m.value.lower())
        if key not in seen:
            seen.add(key)
            deduped.append(m)
    return IocReportRead(
        matches=[
            IocMatchRead(type=m.type, value=m.value, display=m.display, confidence=m.confidence, context=m.context)
            for m in deduped[:200]
        ],
        asn_lookups=asn_lookups[:50],
    )


@router.post("/hashsets/import", response_model=HashSetImportResult, status_code=200)
async def import_hash_set(
    payload: HashSetImportRequest,
    current: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> HashSetImportResult:
    summary = await hash_intel.import_hash_entries(
        session,
        organization_id=current.organization_id,
        set_name=payload.set_name,
        category=payload.category,
        severity=payload.severity,
        text=payload.hashes,
        created_by=current.id,
    )
    await audit(
        session,
        "forensic_core.hashset_import",
        None,
        {
            "set_name": summary.set_name,
            "category": summary.category,
            "added": summary.added,
            "skipped": summary.skipped,
            "invalid": summary.invalid,
        },
        actor=current.username,
    )
    await session.commit()
    return HashSetImportResult(
        set_name=summary.set_name,
        category=summary.category,
        added=summary.added,
        skipped=summary.skipped,
        invalid=summary.invalid,
    )


@router.get("/hashsets", response_model=list[HashSetInfoRead])
async def list_hash_sets(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[HashSetInfoRead]:
    infos = await hash_intel.list_hash_sets(session, organization_id=current.organization_id)
    return [HashSetInfoRead(set_name=i.set_name, category=i.category, entries=i.entries) for i in infos]


@router.post("/hashsets/lookup", response_model=HashLookupResult, status_code=200)
async def lookup_hash(
    payload: HashLookupRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> HashLookupResult:
    matches = await hash_intel.lookup_value(session, organization_id=current.organization_id, value=payload.value)
    return HashLookupResult(
        value=payload.value.strip(),
        matched=bool(matches),
        matches=[
            HashMatchRead(
                set_name=m.set_name,
                category=m.category,
                severity=m.severity,
                algorithm=m.algorithm,
                digest=m.digest,
                label=m.label,
            )
            for m in matches
        ],
    )


@router.post("/correlate/index", status_code=200)
async def correlation_index(
    payload: CorrelationIndexRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.core.deps import require_case_access

    await require_case_access(session, payload.case_id, current)
    added = await correlation.index_attribute(
        session,
        organization_id=current.organization_id,
        case_id=payload.case_id,
        attr_type=payload.attr_type,
        value=payload.value,
        source_id=payload.source_id,
    )
    await session.commit()
    return {"indexed": added, "attr_type": payload.attr_type.strip().lower(), "value": payload.value.strip()}


@router.get("/correlate", response_model=CorrelationQueryResult)
async def correlation_query(
    attr_type: str,
    value: str,
    exclude_case_id: str | None = None,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CorrelationQueryResult:
    hits = await correlation.correlate(
        session,
        organization_id=current.organization_id,
        attr_type=attr_type,
        value=value,
        exclude_case_id=exclude_case_id,
    )
    return CorrelationQueryResult(
        attr_type=attr_type.strip().lower(),
        value=value.strip(),
        count=len(hits),
        hits=[
            CorrelationHitRead(
                case_id=h.case_id,
                case_title=h.case_title,
                source_id=h.source_id,
                attr_type=h.attr_type,
                attr_value=h.attr_value,
                display=h.display,
                first_seen_at=h.first_seen_at,
            )
            for h in hits
        ],
    )


@router.post("/carve", response_model=CarveResult, status_code=200)
async def carve_file(
    case_id: str = Form(...),
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CarveResult:
    await require_case_access(session, case_id, current)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_BYTES} bytes")
    parent_sha256 = hashlib.sha256(data).hexdigest()
    sealed = await carve_and_seal(
        session,
        case_id=case_id,
        parent_sha256=parent_sha256,
        parent_source_id=None,
        data=data,
        actor=current.username,
        organization_id=current.organization_id,
    )
    await session.commit()
    return CarveResult(
        parent_sha256=parent_sha256,
        count=len(sealed),
        artifacts=[
            CarvedArtifactRead(
                offset=s.artifact.offset,
                size=s.artifact.size,
                carved_type=s.artifact.carved_type,
                label=s.artifact.label,
                sha256=s.artifact.sha256,
                entropy=s.artifact.entropy,
                reason=s.artifact.reason,
                source_id=s.source.id,
                hash_matches=len(s.hash_matches),
                correlation_hits=len(s.correlation_hits),
            )
            for s in sealed
        ],
    )


@router.post("/interesting-rules", response_model=InterestingRuleRead, status_code=201)
async def create_interesting_rule(
    payload: InterestingRuleCreate,
    current: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> InterestingRuleRead:
    try:
        rule = await interesting_files.create_rule(
            session,
            organization_id=current.organization_id,
            name=payload.name,
            severity=payload.severity,
            name_contains=payload.name_contains,
            name_glob=payload.name_glob,
            extensions=payload.extensions,
            types=payload.types,
            min_size=payload.min_size,
            max_size=payload.max_size,
            min_entropy=payload.min_entropy,
            description=payload.description,
            created_by=current.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return InterestingRuleRead.model_validate(rule)


@router.get("/interesting-rules", response_model=list[InterestingRuleRead])
async def list_interesting_rules(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[InterestingRuleRead]:
    rules = await interesting_files.list_rules(session, organization_id=current.organization_id)
    return [InterestingRuleRead.model_validate(r) for r in rules]


@router.delete("/interesting-rules/{rule_id}", status_code=200)
async def delete_interesting_rule(
    rule_id: str,
    current: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    deleted = await interesting_files.delete_rule(session, organization_id=current.organization_id, rule_id=rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.commit()
    return {"deleted": True, "rule_id": rule_id}
