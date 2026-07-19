"""Chain of custody — tamper-evident sealing and verification for OIHK Basic."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.config import get_settings


@dataclass
class SealEntryResult:
    sequence: int
    source_id: str
    source_title: str
    sealed_at_iso: str
    content_sha256: str
    seal_hash: str
    content_ok: bool
    seal_ok: bool
    chain_ok: bool
    signature_ok: bool
    ok: bool


@dataclass
class CustodyVerificationReport:
    case_id: str
    intact: bool
    sealed_count: int
    first_broken_sequence: int | None
    entries: list[SealEntryResult]


def _hmac_sha256(key: str, data: bytes) -> str:
    return hmac.new(key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def _compute_seal_hash(
    prev_hash: str,
    content_sha256: str,
    source_id: str,
    sequence: int,
    sealed_at_iso: str,
) -> str:
    payload = f"{prev_hash}|{content_sha256}|{source_id}|{sequence}|{sealed_at_iso}"
    return hashlib.sha256(payload.encode("utf-8")).digest().hex()


def _compute_signature(seal_hash: str, signing_key: str) -> str:
    return _hmac_sha256(signing_key, seal_hash.encode("utf-8"))


async def seal_source(
    session: AsyncSession,
    source: models.Source,
    *,
    raw_bytes: bytes | None = None,
    storage_path: str | None = None,
) -> models.EvidenceSeal:
    settings = get_settings()

    content_to_hash = raw_bytes if raw_bytes is not None else (source.body or "").encode("utf-8")
    content_sha256 = hashlib.sha256(content_to_hash).hexdigest()

    anchor = await session.get(models.CustodyAnchor, source.case_id)
    if anchor is None:
        prev_hash = "0" * 64
        sequence = 1
        anchor = models.CustodyAnchor(case_id=source.case_id)
        session.add(anchor)
    else:
        prev_hash = anchor.last_seal_hash
        sequence = anchor.expected_sequence + 1

    sealed_at = datetime.now(UTC)
    sealed_at_iso = sealed_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    seal_hash = _compute_seal_hash(prev_hash, content_sha256, source.id, sequence, sealed_at_iso)
    signature = _compute_signature(seal_hash, settings.custody_signing_key)

    seal = models.EvidenceSeal(
        case_id=source.case_id,
        source_id=source.id,
        sequence=sequence,
        content_sha256=content_sha256,
        content_ref=f"file:{storage_path}" if storage_path else "body",
        size_bytes=len(content_to_hash),
        sealed_at=sealed_at,
        sealed_at_iso=sealed_at_iso,
        prev_seal_hash=prev_hash,
        seal_hash=seal_hash,
        signature=signature,
        key_id=settings.custody_key_id,
    )
    session.add(seal)

    anchor.expected_sequence = sequence
    anchor.last_seal_hash = seal_hash
    anchor.updated_at = sealed_at

    return seal


async def verify_case_custody(session: AsyncSession, case_id: str) -> CustodyVerificationReport:
    settings = get_settings()

    seals = (
        (await session.execute(
            select(models.EvidenceSeal).where(models.EvidenceSeal.case_id == case_id).order_by(models.EvidenceSeal.sequence)
        )).scalars().all()
    )

    if not seals:
        return CustodyVerificationReport(
            case_id=case_id, intact=True, sealed_count=0, first_broken_sequence=None, entries=[]
        )

    entries: list[SealEntryResult] = []
    first_broken: int | None = None
    prev_seal_hash = "0" * 64

    for seal in seals:
        content_ok = True
        if seal.content_ref == "body":
            source = await session.get(models.Source, seal.source_id)
            if source is not None:
                actual_content_hash = hashlib.sha256((source.body or "").encode("utf-8")).hexdigest()
                content_ok = actual_content_hash == seal.content_sha256

        expected_seal_hash = _compute_seal_hash(
            prev_seal_hash, seal.content_sha256, seal.source_id, seal.sequence, seal.sealed_at_iso
        )
        seal_ok = expected_seal_hash == seal.seal_hash
        chain_ok = seal.prev_seal_hash == prev_seal_hash

        expected_sig = _compute_signature(seal.seal_hash, settings.custody_signing_key)
        signature_ok = expected_sig == seal.signature

        ok = content_ok and seal_ok and chain_ok and signature_ok
        if not ok and first_broken is None:
            first_broken = seal.sequence

        source_title = ""
        source = await session.get(models.Source, seal.source_id)
        if source is not None:
            source_title = source.title

        entries.append(SealEntryResult(
            sequence=seal.sequence,
            source_id=seal.source_id,
            source_title=source_title,
            sealed_at_iso=seal.sealed_at_iso,
            content_sha256=seal.content_sha256,
            seal_hash=seal.seal_hash,
            content_ok=content_ok,
            seal_ok=seal_ok,
            chain_ok=chain_ok,
            signature_ok=signature_ok,
            ok=ok,
        ))

        prev_seal_hash = seal.seal_hash

    return CustodyVerificationReport(
        case_id=case_id,
        intact=first_broken is None,
        sealed_count=len(seals),
        first_broken_sequence=first_broken,
        entries=entries,
    )
