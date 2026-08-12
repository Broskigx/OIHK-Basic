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
    LocalModelRuntimeStatusRead,
    LocalModelTestRequest,
)
from app.services.local_models import build_local_provider, detect_local_services, validate_local_endpoint

router = APIRouter(prefix="/local-models", tags=["local-models"])


def _runtime_http_error(exc: httpx.HTTPError, *, operation: str) -> HTTPException:
    """Translate model-runtime failures into actionable, non-sensitive UI copy."""

    if isinstance(exc, httpx.TimeoutException):
        return HTTPException(
            status_code=504,
            detail=(
                f"The local model endpoint timed out while {operation}. No OIHK data or configuration was changed. "
                "Confirm the runtime and model are ready, then retry or increase the timeout."
            ),
        )
    if isinstance(exc, httpx.ConnectError):
        return HTTPException(
            status_code=503,
            detail=(
                f"OIHK Basic could not reach the local model endpoint while {operation}. No OIHK data or "
                "configuration was changed. Start the LM Studio or Ollama server, verify the endpoint, and retry."
            ),
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return HTTPException(
            status_code=502,
            detail=(
                f"The local model endpoint rejected the request with HTTP {exc.response.status_code} while "
                f"{operation}. No OIHK data or configuration was changed. Check the provider type, endpoint, and "
                "loaded model."
            ),
        )
    return HTTPException(
        status_code=503,
        detail=(
            f"The local model endpoint became unavailable while {operation}. No OIHK data or configuration was "
            "changed. Check the runtime diagnostics and retry."
        ),
    )


def _malformed_runtime_response(*, operation: str) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail=(
            f"The local model endpoint returned an unsupported response while {operation}. No OIHK data or "
            "configuration was changed. Confirm that the selected provider matches the endpoint API."
        ),
    )


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


@router.get("/status", response_model=LocalModelRuntimeStatusRead)
async def runtime_status(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LocalModelRuntimeStatusRead:
    """Probe the saved private endpoint without running inference."""

    configuration = await _configuration(session, current.id)
    if configuration is None or not configuration.endpoint:
        return LocalModelRuntimeStatusRead(configured=False, connected=False)

    configured = bool(configuration.model)
    started = perf_counter()
    try:
        provider = build_local_provider(configuration.provider, configuration.endpoint, 4)
        available = await provider.list_models()
        model_ids = {model.id for model in available}
        return LocalModelRuntimeStatusRead(
            configured=configured,
            connected=True,
            provider=configuration.provider,
            endpoint=configuration.endpoint,
            model=configuration.model,
            model_available=bool(configuration.model and configuration.model in model_ids),
            model_count=len(available),
            context_length=configuration.context_length,
            max_tokens=configuration.max_tokens,
            latency_ms=round((perf_counter() - started) * 1000),
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        return LocalModelRuntimeStatusRead(
            configured=configured,
            connected=False,
            provider=configuration.provider,
            endpoint=configuration.endpoint,
            model=configuration.model,
            context_length=configuration.context_length,
            max_tokens=configuration.max_tokens,
            latency_ms=round((perf_counter() - started) * 1000),
            error=type(exc).__name__,
        )


@router.post("/models")
async def list_models(payload: LocalModelProbeRequest) -> dict:
    try:
        provider = build_local_provider(payload.provider, payload.endpoint, 12)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        models_found = await provider.list_models()
    except httpx.HTTPError as exc:
        raise _runtime_http_error(exc, operation="listing models") from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise _malformed_runtime_response(operation="listing models") from exc
    return {"models": [model.__dict__ for model in models_found]}


@router.post("/test")
async def test_inference(payload: LocalModelTestRequest) -> dict:
    started = perf_counter()
    try:
        provider = build_local_provider(payload.provider, payload.endpoint, payload.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        reply = await provider.complete(
            model=payload.model,
            messages=[{"role": "user", "content": payload.prompt}],
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except httpx.HTTPError as exc:
        raise _runtime_http_error(exc, operation="testing inference") from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise _malformed_runtime_response(operation="testing inference") from exc
    if not reply.strip():
        raise _malformed_runtime_response(operation="testing inference")
    return {"status": "ok", "reply": reply, "latency_ms": round((perf_counter() - started) * 1000)}
