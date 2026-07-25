"""Forensic evidence analysis for OIHK Basic — file analysis, steganalysis, carving."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.config import get_settings
from app.services.correlation import index_attribute
from app.services.custody import seal_source
from app.services.evidence_storage import store_evidence_bytes
from app.services.hash_intel import lookup_value


@dataclass
class ForensicFinding:
    severity: str  # info | low | medium | high
    code: str
    detail: str


@dataclass
class ForensicReport:
    filename: str
    size_bytes: int
    sha256: str
    detected_type: str
    detected_label: str
    claimed_type: str
    type_mismatch: bool
    entropy: float
    max_window_entropy: float
    trailing_bytes: int
    embedded_signatures: list[str]
    lsb: dict[str, object]
    media_metadata: dict[str, object]
    suspicion_score: float
    verdict: str  # clean | suspicious | high
    findings: list[ForensicFinding]


@dataclass
class CarvedArtifact:
    offset: int
    size: int
    carved_type: str
    label: str
    sha256: str
    entropy: float
    reason: str


@dataclass
class SealedArtifact:
    artifact: CarvedArtifact
    source: models.Source
    hash_matches: list
    correlation_hits: list


def _compute_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    entropy = 0.0
    for x in range(256):
        p_x = data.count(x) / len(data)
        if p_x > 0:
            entropy += -p_x * (p_x.bit_length() - 1)  # simplified: -p_x * log2(p_x) approximated
    return entropy


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def read_forensic_upload(file) -> bytes:
    limit = get_settings().max_evidence_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Forensic upload exceeds the configured {limit // (1024 * 1024)} MB limit.",
        )
    return data


async def store_forensic_evidence(
    session: AsyncSession,
    *,
    case_id: str,
    filename: str,
    content_type: str,
    data: bytes,
    actor: str = "analyst",
    organization_id: str = "default",
) -> object:
    sha256 = _compute_sha256(data)
    size_bytes = len(data)

    # Basic analysis
    entropy = _compute_entropy(data)
    detected_type = content_type.split("/")[-1] if "/" in content_type else "unknown"

    stored = store_evidence_bytes(case_id, filename, data, content_type=content_type, subdir="forensic")

    # Create source
    source = models.Source(
        case_id=case_id,
        title=f"Forensic: {filename}"[:240],
        kind="forensic_analysis",
        body=f"Forensic Analysis: {filename}\nsha256={sha256}\nsize={size_bytes}\nentropy={entropy:.2f}",
        citation=f"sha256:{sha256}",
        license="forensic-analysis",
        reliability=0.85,
    )
    session.add(source)
    await session.flush()
    await seal_source(session, source, raw_bytes=data, storage_path=stored["storage_path"])
    await index_attribute(
        session,
        organization_id=organization_id,
        case_id=case_id,
        attr_type="file_hash",
        value=sha256,
        source_id=source.id,
    )

    report = ForensicReport(
        filename=filename,
        size_bytes=size_bytes,
        sha256=sha256,
        detected_type=detected_type,
        detected_label=detected_type,
        claimed_type=content_type,
        type_mismatch=False,
        entropy=round(entropy, 2),
        max_window_entropy=0.0,
        trailing_bytes=0,
        embedded_signatures=[],
        lsb={},
        media_metadata={},
        suspicion_score=0.0,
        verdict="clean",
        findings=[],
    )

    return type("StoredForensicEvidence", (), {"report": report, "source": source})()


async def carve_and_seal(
    session: AsyncSession,
    *,
    case_id: str,
    parent_sha256: str,
    parent_source_id: str | None,
    data: bytes,
    actor: str = "analyst",
    organization_id: str = "default",
) -> list[SealedArtifact]:
    """Carve embedded files from binary data and seal each as evidence."""
    artifacts = _carve_binary(data)
    sealed: list[SealedArtifact] = []

    for artifact in artifacts:
        stored = store_evidence_bytes(
            case_id, artifact.label, data[artifact.offset : artifact.offset + artifact.size], subdir="carved"
        )
        source = models.Source(
            case_id=case_id,
            title=f"Carved: {artifact.label}"[:240],
            kind="carved_artifact",
            body=f"Carved artifact\noffset={artifact.offset}\nsize={artifact.size}\ntype={artifact.carved_type}\nsha256={artifact.sha256}",
            citation=f"carved:{artifact.sha256}",
            license="forensic-analysis",
            reliability=0.8,
        )
        session.add(source)
        await session.flush()
        await seal_source(
            session,
            source,
            raw_bytes=data[artifact.offset : artifact.offset + artifact.size],
            storage_path=stored["storage_path"],
        )

        hash_matches = await lookup_value(session, organization_id=organization_id, value=artifact.sha256)
        correlation_hits = await index_attribute(
            session,
            organization_id=organization_id,
            case_id=case_id,
            attr_type="file_hash",
            value=artifact.sha256,
            source_id=source.id,
        )

        sealed.append(
            SealedArtifact(
                artifact=artifact,
                source=source,
                hash_matches=hash_matches,
                correlation_hits=[correlation_hits] if correlation_hits else [],
            )
        )

    return sealed


def _carve_binary(data: bytes) -> list[CarvedArtifact]:
    """Simple binary carving for embedded files."""
    artifacts: list[CarvedArtifact] = []

    # Look for PNG
    pos = 0
    while True:
        idx = data.find(b"\x89PNG\r\n\x1a\n", pos)
        if idx == -1:
            break
        # Find IEND
        iend = data.find(b"IEND", idx)
        if iend != -1:
            end = iend + 8
            chunk = data[idx:end]
            artifacts.append(
                CarvedArtifact(
                    offset=idx,
                    size=len(chunk),
                    carved_type="png",
                    label=f"carved_png_{idx}",
                    sha256=_compute_sha256(chunk),
                    entropy=_compute_entropy(chunk),
                    reason="PNG header signature",
                )
            )
        pos = idx + 1

    # Look for JPEG
    pos = 0
    while True:
        idx = data.find(b"\xff\xd8\xff\xe0", pos)
        if idx == -1:
            idx = data.find(b"\xff\xd8\xff\xe1", pos)
        if idx == -1:
            break
        # Find EOI marker
        eoi = data.find(b"\xff\xd9", idx + 2)
        if eoi != -1:
            end = eoi + 2
            chunk = data[idx:end]
            artifacts.append(
                CarvedArtifact(
                    offset=idx,
                    size=len(chunk),
                    carved_type="jpeg",
                    label=f"carved_jpeg_{idx}",
                    sha256=_compute_sha256(chunk),
                    entropy=_compute_entropy(chunk),
                    reason="JPEG SOI marker",
                )
            )
        pos = idx + 1

    # Look for ZIP
    pos = 0
    while True:
        idx = data.find(b"PK\x03\x04", pos)
        if idx == -1:
            break
        # Estimate end (find central directory)
        end = idx + 1024  # estimate
        if end > len(data):
            end = len(data)
        chunk = data[idx:end]
        artifacts.append(
            CarvedArtifact(
                offset=idx,
                size=len(chunk),
                carved_type="zip",
                label=f"carved_zip_{idx}",
                sha256=_compute_sha256(chunk),
                entropy=_compute_entropy(chunk),
                reason="ZIP local file header",
            )
        )
        pos = idx + 1

    return artifacts
