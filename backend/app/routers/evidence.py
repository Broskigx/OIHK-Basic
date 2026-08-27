"""The evidence records Basic holds as custodian.

Basic is no longer where evidence is *acquired*. Acquisition, carving, hashing
and analysis belong to OIHK Evidence Lab, which is installed separately and
reaches these records through the signed System Link module API — see
``app.system_link.module_api`` for ``evidence.write``, ``evidence.import`` and
``evidence.metadata.write``. Those routes attribute every change to the module
and land it in the audit trail under the module's name, which is precisely what
an unauthenticated browser upload could not do.

What stays here is the custodian's own surface: read what the case holds, prove
a held file still matches its seal, export the manifest, and remove an exhibit.
Ingestion and annotation are deliberately absent — a second, unattributed way
in would defeat the reason the module API is signed.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import EvidenceItemRead, EvidenceVerifyRead
from app.services.managed_evidence import hash_managed_file, safe_evidence_path
from app.services.repository import audit

router = APIRouter(prefix="/evidence", tags=["evidence"])


async def _item(
    session: AsyncSession,
    item_id: str,
    current: CurrentUser,
) -> models.EvidenceItem:
    item = await session.get(models.EvidenceItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Evidence item not found")
    await require_case_access(session, item.case_id, current)
    return item


@router.get("/{case_id}", response_model=list[EvidenceItemRead])
async def list_evidence(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.EvidenceItem]:
    await require_case_access(session, case_id, current)
    rows = await session.execute(
        select(models.EvidenceItem)
        .where(models.EvidenceItem.case_id == case_id)
        .order_by(models.EvidenceItem.created_at.desc())
    )
    return list(rows.scalars().all())


@router.post("/items/{item_id}/verify", response_model=EvidenceVerifyRead)
async def verify_evidence(
    item_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EvidenceVerifyRead:
    """Re-hash a held file and compare it against the digest on record.

    Only meaningful for evidence whose bytes Basic actually holds. An item
    recorded by reference through ``evidence.import`` has no managed file, so
    there is nothing here to re-hash and the request is refused rather than
    answered with a misleading mismatch.
    """
    item = await _item(session, item_id, current)
    if not item.storage_path:
        raise HTTPException(
            status_code=409,
            detail="This exhibit is held by a linked module, not by Basic; verify it in the module that holds it.",
        )
    actual = await asyncio.to_thread(hash_managed_file, item.storage_path)
    item.verified_at = datetime.now(UTC)
    await audit(
        session,
        "evidence.verified",
        item.case_id,
        {"evidence_id": item.id, "intact": actual == item.sha256},
        actor=current.username,
    )
    await session.commit()
    return EvidenceVerifyRead(
        id=item.id,
        expected_sha256=item.sha256,
        actual_sha256=actual,
        intact=actual == item.sha256,
        verified_at=item.verified_at,
    )


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    item_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Remove one exhibit. Deliberately kept as an operator-only power.

    No module capability grants deletion, so this is the single path by which
    an exhibit leaves a case, and it is always a person's decision recorded
    against their name.
    """
    item = await _item(session, item_id, current)
    path = safe_evidence_path(item.storage_path) if item.storage_path else None
    case_id = item.case_id
    await session.delete(item)
    await audit(
        session,
        "evidence.file_deleted",
        case_id,
        {"evidence_id": item.id, "sha256": item.sha256},
        actor=current.username,
    )
    await session.commit()
    if path is not None:
        path.unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{case_id}/manifest.json")
async def evidence_manifest(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    case = await require_case_access(session, case_id, current)
    items = list(
        (
            await session.execute(
                select(models.EvidenceItem)
                .where(models.EvidenceItem.case_id == case_id)
                .order_by(models.EvidenceItem.created_at)
            )
        ).scalars()
    )
    now = datetime.now(UTC)
    payload = {
        "schema_version": 1,
        "product": "OIHK Basic",
        "case": {"id": case.id, "title": case.title},
        "exported_at": now.isoformat(),
        "items": [
            {
                "id": item.id,
                "original_name": item.original_name,
                "mime_type": item.mime_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
                "tags": item.tags,
                "entity_ids": item.entity_ids,
                "ingested_by": item.ingested_by,
                "original_reference": item.original_reference,
                "held_by_basic": bool(item.storage_path),
                "created_at": item.created_at.isoformat(),
                "verified_at": item.verified_at.isoformat() if item.verified_at else None,
            }
            for item in items
        ],
    }
    for item in items:
        item.export_count += 1
    await audit(session, "evidence.manifest_exported", case_id, {"item_count": len(items)}, actor=current.username)
    await session.commit()
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="oihk-basic-evidence-{case_id}.json"'},
    )
