"""Configuration and health operations for user-controlled model servers."""

from __future__ import annotations

from time import perf_counter

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user
from app.database import get_session
from app.schemas import (
    LocalModelConfigurationRead,
    LocalModelConfigurationWrite,
    LocalModelProbeRequest,
    LocalModelTestRequest,
)
from app.services.local_models import build_local_provider, detect_local_services, validate_local_endpoint

router = APIRouter(prefix="/local-models", tags=["local-models"])


async def _configuration(session: AsyncSession, user_id: str) -> models.LocalModelConfiguration | None:
    return (
        await session.execute(
            select(models.LocalModelConfiguration).where(models.LocalModelConfiguration.user_id == user_id)
        )
    ).scalar_one_or_none()


@router.get("/config", response_model=LocalModelConfigurationRead | None)
async def get_configuration(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> models.LocalModelConfiguration | None:
    return await _configuration(session, current.id)


@router.put("/config", response_model=LocalModelConfigurationRead)
async def save_configuration(
    payload: LocalModelConfigurationWrite,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> models.LocalModelConfiguration:
    try:
        endpoint = validate_local_endpoint(payload.endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = await _configuration(session, current.id)
    if row is None:
        row = models.LocalModelConfiguration(user_id=current.id)
        session.add(row)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.endpoint = endpoint
    await session.commit()
    await session.refresh(row)
    return row


@router.get("/detect")
async def detect() -> dict:
    return {"services": await detect_local_services()}


@router.post("/models")
async def list_models(payload: LocalModelProbeRequest) -> dict:
    try:
        provider = build_local_provider(payload.provider, payload.endpoint, 12)
        models_found = await provider.list_models()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Local model service unavailable: {type(exc).__name__}") from exc
    return {"models": [model.__dict__ for model in models_found]}


@router.post("/test")
async def test_inference(payload: LocalModelTestRequest) -> dict:
    started = perf_counter()
    try:
        provider = build_local_provider(payload.provider, payload.endpoint, payload.timeout_seconds)
        reply = await provider.complete(
            model=payload.model,
            messages=[{"role": "user", "content": payload.prompt}],
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Inference failed: {type(exc).__name__}") from exc
    return {"status": "ok", "reply": reply, "latency_ms": round((perf_counter() - started) * 1000)}
