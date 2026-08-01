"""Durable, local-model-only Copilot conversations for OIHK Basic."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import (
    ConversationCreate,
    ConversationMessageCreate,
    ConversationMessageRead,
    ConversationRead,
    ConversationReply,
    ConversationUpdate,
)
from app.services.local_models import LocalModelProvider, build_local_provider

router = APIRouter(prefix="/assistant", tags=["assistant"])

_DEFAULT_SYSTEM_PROMPT = """You are the local Copilot inside OIHK Basic.
Be evidence-first and concise. Never invent sources or claim an action was executed.
Clearly distinguish confirmed facts, unverified observations and model inference.
Do not produce commands or modify investigation data. Proposed actions require user confirmation.
All analysis remains within the local model endpoint selected by the user."""


async def _conversation(
    session: AsyncSession,
    conversation_id: str,
    current: CurrentUser,
) -> models.AssistantConversation:
    row = (
        await session.execute(
            select(models.AssistantConversation).where(
                models.AssistantConversation.id == conversation_id,
                models.AssistantConversation.user_id == current.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return row


async def _configuration(
    session: AsyncSession,
    current: CurrentUser,
) -> models.LocalModelConfiguration:
    row = (
        await session.execute(
            select(models.LocalModelConfiguration).where(models.LocalModelConfiguration.user_id == current.id)
        )
    ).scalar_one_or_none()
    if row is None or not row.endpoint or not row.model:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No local model is configured. Open Local Models and connect LM Studio or Ollama.",
        )
    return row


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    case_id: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationRead]:
    if case_id:
        await require_case_access(session, case_id, current)
    statement = (
        select(models.AssistantConversation, func.count(models.AssistantMessage.id))
        .outerjoin(
            models.AssistantMessage,
            models.AssistantMessage.conversation_id == models.AssistantConversation.id,
        )
        .where(models.AssistantConversation.user_id == current.id)
        .group_by(models.AssistantConversation.id)
        .order_by(models.AssistantConversation.updated_at.desc())
    )
    if case_id is not None:
        statement = statement.where(models.AssistantConversation.case_id == case_id)
    if not include_archived:
        statement = statement.where(models.AssistantConversation.archived.is_(False))
    rows = (await session.execute(statement)).all()
    return [
        ConversationRead(
            id=row.id,
            case_id=row.case_id,
            title=row.title,
            archived=row.archived,
            model=row.model or "",
            settings=row.settings or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
            message_count=count,
        )
        for row, count in rows
    ]


@router.post("/conversations", response_model=ConversationRead, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationRead:
    if payload.case_id:
        await require_case_access(session, payload.case_id, current)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Conversation title must not be empty")
    row = models.AssistantConversation(
        case_id=payload.case_id,
        user_id=current.id,
        title=title,
        model=payload.model.strip(),
        settings=payload.settings,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ConversationRead.model_validate(row)


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationRead:
    row = await _conversation(session, conversation_id, current)
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Conversation title must not be empty")
        row.title = title
    if payload.archived is not None:
        row.archived = payload.archived
    if payload.model is not None:
        row.model = payload.model.strip()
    if payload.settings is not None:
        row.settings = payload.settings
    row.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    count = (
        await session.execute(
            select(func.count(models.AssistantMessage.id)).where(
                models.AssistantMessage.conversation_id == conversation_id
            )
        )
    ).scalar_one()
    return ConversationRead(
        id=row.id,
        case_id=row.case_id,
        title=row.title,
        archived=row.archived,
        model=row.model or "",
        settings=row.settings or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
        message_count=count,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await _conversation(session, conversation_id, current)
    await session.execute(
        delete(models.AssistantMessage).where(models.AssistantMessage.conversation_id == conversation_id)
    )
    await session.delete(row)
    await session.commit()


@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessageRead])
async def list_messages(
    conversation_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.AssistantMessage]:
    await _conversation(session, conversation_id, current)
    return list(
        (
            await session.execute(
                select(models.AssistantMessage)
                .where(models.AssistantMessage.conversation_id == conversation_id)
                .order_by(models.AssistantMessage.created_at, models.AssistantMessage.id)
            )
        ).scalars()
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ConversationReply)
async def send_message(
    conversation_id: str,
    payload: ConversationMessageCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationReply:
    conversation = await _conversation(session, conversation_id, current)
    if conversation.archived:
        raise HTTPException(status_code=409, detail="Restore this conversation before sending a message")
    if conversation.case_id:
        await require_case_access(session, conversation.case_id, current)
    configuration = await _configuration(session, current)

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content must not be empty")
    user_message = models.AssistantMessage(
        conversation_id=conversation.id,
        case_id=conversation.case_id,
        user_id=current.id,
        role="user",
        content=content,
        provider="local",
    )
    session.add(user_message)
    if conversation.title == "New conversation":
        conversation.title = content.replace("\n", " ")[:72]
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user_message)

    recent = await _recent_messages(session, conversation.id)
    system_prompt = configuration.system_prompt.strip() or _DEFAULT_SYSTEM_PROMPT
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": row.role, "content": row.content[:16_000]} for row in recent)

    provider = build_local_provider(
        configuration.provider,
        configuration.endpoint,
        configuration.timeout_seconds,
    )
    model = conversation.model or configuration.role_models.get("chat") or configuration.model
    try:
        reply = await _complete_with_retries(
            provider,
            model=model,
            messages=messages,
            temperature=configuration.temperature,
            max_tokens=configuration.max_tokens,
        )
    except (httpx.HTTPError, KeyError, TypeError, AttributeError, IndexError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"The local model did not respond ({type(exc).__name__}). Check Local Models diagnostics.",
        ) from exc
    if conversation.model != model:
        conversation.model = model
        conversation.updated_at = datetime.now(UTC)
        await session.commit()

    assistant_message = models.AssistantMessage(
        conversation_id=conversation.id,
        case_id=conversation.case_id,
        user_id=current.id,
        role="assistant",
        content=reply.strip() or "The local model returned an empty response.",
        provider=configuration.provider,
    )
    session.add(assistant_message)
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(assistant_message)
    return ConversationReply(
        user_message=ConversationMessageRead.model_validate(user_message),
        assistant_message=ConversationMessageRead.model_validate(assistant_message),
    )


async def _recent_messages(session: AsyncSession, conversation_id: str) -> list[models.AssistantMessage]:
    rows = list(
        (
            await session.execute(
                select(models.AssistantMessage)
                .where(models.AssistantMessage.conversation_id == conversation_id)
                .order_by(models.AssistantMessage.created_at.desc(), models.AssistantMessage.id.desc())
                .limit(30)
            )
        ).scalars()
    )
    rows.reverse()
    return rows


async def _complete_with_retries(
    provider: LocalModelProvider,
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    """Non-streaming completion with a single bounded retry for transient HTTP errors.

    Only transient failures are retried (transport errors and 5xx responses);
    client-side errors (4xx) fail fast.
    """
    try:
        return await provider.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            return await provider.complete(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        raise
    except httpx.TransportError:
        return await provider.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/conversations/{conversation_id}/stream")
async def stream_message(
    conversation_id: str,
    payload: ConversationMessageCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream a Copilot reply as Server-Sent Events.

    Events:
    - ``delta``: incremental assistant content.
    - ``message``: the persisted user message (first, before any delta).
    - ``done``: the persisted assistant message and final summary.
    - ``error``: a human-readable failure; the stream then closes.

    The user message is persisted before generation starts, so a disconnect or
    model failure never loses the user's turn.
    """
    conversation = await _conversation(session, conversation_id, current)
    if conversation.archived:
        raise HTTPException(status_code=409, detail="Restore this conversation before sending a message")
    if conversation.case_id:
        await require_case_access(session, conversation.case_id, current)
    configuration = await _configuration(session, current)

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content must not be empty")

    user_message = models.AssistantMessage(
        conversation_id=conversation.id,
        case_id=conversation.case_id,
        user_id=current.id,
        role="user",
        content=content,
        provider="local",
    )
    session.add(user_message)
    if conversation.title == "New conversation":
        conversation.title = content.replace("\n", " ")[:72]
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user_message)

    recent = await _recent_messages(session, conversation.id)
    system_prompt = configuration.system_prompt.strip() or _DEFAULT_SYSTEM_PROMPT
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": row.role, "content": row.content[:16_000]} for row in recent)

    provider = build_local_provider(
        configuration.provider,
        configuration.endpoint,
        configuration.timeout_seconds,
    )
    model = conversation.model or configuration.role_models.get("chat") or configuration.model

    async def generate() -> AsyncIterator[str]:
        yield _sse({"type": "message", "message": ConversationMessageRead.model_validate(user_message).model_dump(mode="json")})
        if not configuration.streaming:
            try:
                reply = await _complete_with_retries(
                    provider,
                    model=model,
                    messages=messages,
                    temperature=configuration.temperature,
                    max_tokens=configuration.max_tokens,
                )
                yield _sse({"type": "delta", "content": reply})
            except (httpx.HTTPError, KeyError, TypeError, AttributeError, IndexError) as exc:
                yield _sse({"type": "error", "message": f"The local model did not respond ({type(exc).__name__})."})
                return
            final_content = reply
        else:
            final_content = ""
            try:
                async for chunk in provider.stream(
                    model=model,
                    messages=messages,
                    temperature=configuration.temperature,
                    max_tokens=configuration.max_tokens,
                ):
                    if chunk:
                        final_content += chunk
                        yield _sse({"type": "delta", "content": chunk})
            except (httpx.HTTPError, KeyError, TypeError, AttributeError, IndexError) as exc:
                yield _sse({"type": "error", "message": f"The local model did not respond ({type(exc).__name__})."})
                # Do not persist a partial/empty assistant reply on a mid-stream
                # failure: the user turn is already saved above, and the client
                # receives the error event instead of a fabricated `done`.
                return

        assistant_message = models.AssistantMessage(
            conversation_id=conversation.id,
            case_id=conversation.case_id,
            user_id=current.id,
            role="assistant",
            content=final_content.strip() or "The local model returned an empty response.",
            provider=configuration.provider,
        )
        session.add(assistant_message)
        if conversation.model != model:
            conversation.model = model
        conversation.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(assistant_message)
        yield _sse({
            "type": "done",
            "user_message": ConversationMessageRead.model_validate(user_message).model_dump(mode="json"),
            "assistant_message": ConversationMessageRead.model_validate(assistant_message).model_dump(mode="json"),
        })

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
