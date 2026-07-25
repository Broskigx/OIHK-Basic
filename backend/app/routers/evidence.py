"""Managed local evidence files with streaming ingestion and hash verification."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import EvidenceItemRead, EvidenceItemUpdate, EvidenceVerifyRead
from app.services.custody import seal_source
from app.services.managed_evidence import hash_managed_file, safe_evidence_path, store_upload
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


@router.post("", response_model=EvidenceItemRead, status_code=201)
async def upload_evidence(
    case_id: str = Form(...),
    notes: str = Form(default="", max_length=50_000),
    tags: str = Form(default="", max_length=4000),
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> models.EvidenceItem:
    await require_case_access(session, case_id, current)
    stored = await store_upload(case_id, file)
    path_value = str(stored["storage_path"])
    try:
        source = models.Source(
            case_id=case_id,
            title=f"Evidence: {stored['original_name']}"[:240],
            kind="managed_evidence",
            body=(
                f"Managed evidence file\noriginal_name={stored['original_name']}\n"
                f"sha256={stored['sha256']}\nsize_bytes={stored['size_bytes']}\n"
                f"mime_type={stored['mime_type']}"
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
            original_name=str(stored["original_name"]),
            storage_path=path_value,
            mime_type=str(stored["mime_type"]),
            size_bytes=int(stored["size_bytes"]),
            sha256=str(stored["sha256"]),
            notes=notes.strip(),
            tags=[tag.strip()[:80] for tag in tags.split(",") if tag.strip()][:100],
            ingested_by=current.username,
            original_reference=file.filename or str(stored["original_name"]),
        )
        session.add(item)
        await audit(
            session,
            "evidence.uploaded",
            case_id,
            {"evidence_id": item.id, "sha256": item.sha256, "size_bytes": item.size_bytes},
            actor=current.username,
        )
        await session.commit()
        await session.refresh(item)
        return item
    except Exception:
        safe_evidence_path(path_value).unlink(missing_ok=True)
        raise


@router.patch("/items/{item_id}", response_model=EvidenceItemRead)
async def update_evidence(
    item_id: str,
    payload: EvidenceItemUpdate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> models.EvidenceItem:
    item = await _item(session, item_id, current)
    if payload.notes is not None:
        item.notes = payload.notes.strip()
    if payload.tags is not None:
        item.tags = [tag.strip()[:80] for tag in payload.tags if tag.strip()][:100]
    if payload.entity_ids is not None:
        valid = set(
            (
                await session.execute(
                    select(models.Entity.id).where(
                        models.Entity.case_id == item.case_id,
                        models.Entity.id.in_(payload.entity_ids),
                    )
                )
            ).scalars()
        )
        if len(valid) != len(set(payload.entity_ids)):
            raise HTTPException(status_code=400, detail="One or more associated entities do not belong to this case.")
        item.entity_ids = sorted(valid)
    item.updated_at = datetime.now(UTC)
    await audit(session, "evidence.updated", item.case_id, {"evidence_id": item.id}, actor=current.username)
    await session.commit()
    return item


@router.post("/items/{item_id}/verify", response_model=EvidenceVerifyRead)
async def verify_evidence(
    item_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EvidenceVerifyRead:
    item = await _item(session, item_id, current)
    actual = hash_managed_file(item.storage_path)
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


@router.get("/items/{item_id}/preview")
async def preview_evidence(
    item_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    item = await _item(session, item_id, current)
    path = safe_evidence_path(item.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Managed evidence file is missing from storage.")
    safe_inline = item.mime_type.startswith("image/") and item.mime_type not in {"image/svg+xml"}
    media_type = item.mime_type if safe_inline else "application/octet-stream"
    disposition = "inline" if safe_inline else "attachment"
    return FileResponse(
        path,
        media_type=media_type,
        filename=item.original_name,
        content_disposition_type=disposition,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; sandbox",
        },
    )


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    item_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    item = await _item(session, item_id, current)
    path = safe_evidence_path(item.storage_path)
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
