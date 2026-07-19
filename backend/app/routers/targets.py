"""Targets router for OIHK Basic."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import (
    CurrentUser,
    get_current_user,
    require_case_access,
    require_search_run_access,
    require_target_access,
)
from app.database import get_session
from app.schemas import (
    CaseMemoryRead,
    SearchHitRead,
    SearchRunRead,
    TargetIntakeResult,
    TargetPhotoRead,
    TargetProfileRead,
)
from app.services.custody import seal_source
from app.services.evidence_storage import store_photo
from app.services.repository import audit, ingest_source
from app.services.target_workflow import (
    create_memory,
    create_target_case,
    parse_aliases,
    run_target_search,
)

router = APIRouter(prefix="/targets", tags=["targets"])


async def _store_target_photo(
    session: AsyncSession,
    *,
    case: models.Case,
    target: models.TargetProfile,
    upload: UploadFile,
) -> tuple[models.TargetPhoto, models.CaseMemory]:
    stored = await store_photo(case.id, target.id, upload)
    source, _, _ = await ingest_source(
        session,
        case_id=case.id,
        title=f"Uploaded photo: {stored['filename']}",
        kind="photo_evidence",
        body=(
            f"Photo evidence uploaded for {target.first_name} {target.last_name}.\n"
            f"filename={stored['filename']}\n"
            f"content_type={stored['content_type']}\n"
            f"sha256={stored['sha256']}\n"
            f"size_bytes={stored['size_bytes']}"
        ),
        citation=f"local-upload:{stored['sha256']}",
        license="user-provided-evidence",
        reliability=0.82,
    )
    await seal_source(
        session,
        source,
        raw_bytes=Path(stored["storage_path"]).read_bytes(),
        storage_path=stored["storage_path"],
    )
    photo = models.TargetPhoto(
        case_id=case.id,
        target_id=target.id,
        source_id=source.id,
        filename=stored["filename"],
        content_type=stored["content_type"],
        sha256=stored["sha256"],
        size_bytes=stored["size_bytes"],
        storage_path=stored["storage_path"],
    )
    session.add(photo)
    memory = await create_memory(
        session,
        case_id=case.id,
        target_id=target.id,
        kind="photo_evidence_hash",
        content=f"{stored['filename']} sha256={stored['sha256']}",
        confidence=0.86,
        source_ids=[source.id],
    )
    return photo, memory


@router.post("/intake", response_model=TargetIntakeResult, status_code=201)
async def target_intake(
    first_name: str = Form(..., min_length=1, max_length=120),
    last_name: str = Form(..., min_length=1, max_length=120),
    aliases: str = Form(default=""),
    notes: str = Form(default=""),
    legal_basis: str = Form(default="Authorized research"),
    scope_statement: str = Form(default="Bounded authorized OSINT review using user-provided and public sources."),
    consent_basis: str = Form(default="User confirms authorization to investigate this target."),
    auto_search: bool = Form(default=True),
    photos: list[UploadFile] | None = File(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TargetIntakeResult:
    case, target, memories = await create_target_case(
        session,
        first_name=first_name,
        last_name=last_name,
        aliases=parse_aliases(aliases),
        notes=notes,
        legal_basis=legal_basis,
        scope_statement=scope_statement,
        consent_basis=consent_basis,
        owner_id=current.id,
        organization_id=current.organization_id,
    )

    photo_models: list[models.TargetPhoto] = []
    for upload in photos or []:
        photo, memory = await _store_target_photo(session, case=case, target=target, upload=upload)
        photo_models.append(photo)
        memories.append(memory)

    search_run: models.SearchRun | None = None
    hits: list[models.SearchHit] = []
    if auto_search:
        search_run, hits, generated_memories = await run_target_search(session, target=target)
        memories.extend(generated_memories)

    await audit(
        session,
        "target.intake.completed",
        case.id,
        {"target_id": target.id, "photo_count": len(photo_models), "auto_search": auto_search},
    )
    await session.commit()
    return TargetIntakeResult(
        case=case, target=target, photos=photo_models, memory=memories, search_run=search_run, hits=hits
    )


@router.get("/case/{case_id}", response_model=list[TargetProfileRead])
async def list_case_targets(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.TargetProfile]:
    await require_case_access(session, case_id, current)
    result = await session.execute(
        select(models.TargetProfile)
        .where(models.TargetProfile.case_id == case_id)
        .order_by(models.TargetProfile.created_at)
    )
    return list(result.scalars().all())


@router.get("/{target_id}/memory", response_model=list[CaseMemoryRead])
async def list_target_memory(
    target_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.CaseMemory]:
    await require_target_access(session, target_id, current)
    result = await session.execute(
        select(models.CaseMemory)
        .where(models.CaseMemory.target_id == target_id)
        .order_by(models.CaseMemory.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{target_id}/photos", response_model=list[TargetPhotoRead])
async def list_target_photos(
    target_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.TargetPhoto]:
    await require_target_access(session, target_id, current)
    result = await session.execute(
        select(models.TargetPhoto)
        .where(models.TargetPhoto.target_id == target_id)
        .order_by(models.TargetPhoto.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{target_id}/photos/{photo_id}/file")
async def serve_target_photo(
    target_id: str,
    photo_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_target_access(session, target_id, current)
    photo = await session.get(models.TargetPhoto, photo_id)
    if photo is None or photo.target_id != target_id:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = Path(photo.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Photo file not found on disk")
    from starlette.responses import FileResponse
    return FileResponse(path, media_type=photo.content_type)


@router.post("/{target_id}/photos", response_model=list[TargetPhotoRead], status_code=201)
async def upload_target_photos(
    target_id: str,
    photos: list[UploadFile] | None = File(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.TargetPhoto]:
    target = await require_target_access(session, target_id, current)
    case = await session.get(models.Case, target.case_id)
    if case is None:
        return []
    photo_models: list[models.TargetPhoto] = []
    for upload in photos or []:
        photo, _memory = await _store_target_photo(session, case=case, target=target, upload=upload)
        photo_models.append(photo)
    await audit(
        session,
        "target.photos.uploaded",
        case.id,
        {"target_id": target.id, "photo_count": len(photo_models)},
        actor=current.username,
    )
    await session.commit()
    return photo_models


@router.get("/{target_id}/search-runs", response_model=list[SearchRunRead])
async def list_search_runs(
    target_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.SearchRun]:
    await require_target_access(session, target_id, current)
    result = await session.execute(
        select(models.SearchRun)
        .where(models.SearchRun.target_id == target_id)
        .order_by(models.SearchRun.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/search-runs/{run_id}/hits", response_model=list[SearchHitRead])
async def list_search_hits(
    run_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.SearchHit]:
    await require_search_run_access(session, run_id, current)
    result = await session.execute(
        select(models.SearchHit).where(models.SearchHit.run_id == run_id).order_by(models.SearchHit.rank)
    )
    return list(result.scalars().all())


@router.post("/{target_id}/search", response_model=TargetIntakeResult)
async def rerun_target_search(
    target_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TargetIntakeResult:
    target = await require_target_access(session, target_id, current)
    case = await session.get(models.Case, target.case_id)

    photos = (
        (await session.execute(select(models.TargetPhoto).where(models.TargetPhoto.target_id == target.id)))
        .scalars()
        .all()
    )
    search_run, hits, generated_memory = await run_target_search(session, target=target)
    memory = (
        (
            await session.execute(
                select(models.CaseMemory)
                .where(models.CaseMemory.target_id == target.id)
                .order_by(models.CaseMemory.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    await session.commit()
    return TargetIntakeResult(
        case=case,
        target=target,
        photos=list(photos),
        memory=list(memory) or generated_memory,
        search_run=search_run,
        hits=hits,
    )
