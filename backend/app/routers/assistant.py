"""Durable, local-model-only Copilot conversations for OIHK Basic."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.services.local_models import build_local_provider

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
    row = models.AssistantConversation(
        case_id=payload.case_id,
        user_id=current.id,
        title=payload.title.strip(),
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
        row.title = payload.title.strip()
    if payload.archived is not None:
        row.archived = payload.archived
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

    user_message = models.AssistantMessage(
        conversation_id=conversation.id,
        case_id=conversation.case_id,
        user_id=current.id,
        role="user",
        content=payload.content.strip(),
        provider="local",
    )
    session.add(user_message)
    if conversation.title == "New conversation":
        conversation.title = payload.content.strip().replace("\n", " ")[:72]
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user_message)

    recent = list(
        (
            await session.execute(
                select(models.AssistantMessage)
                .where(models.AssistantMessage.conversation_id == conversation.id)
                .order_by(models.AssistantMessage.created_at.desc(), models.AssistantMessage.id.desc())
                .limit(30)
            )
        ).scalars()
    )
    recent.reverse()
    system_prompt = configuration.system_prompt.strip() or _DEFAULT_SYSTEM_PROMPT
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": row.role, "content": row.content[:16_000]} for row in recent)

    provider = build_local_provider(
        configuration.provider,
        configuration.endpoint,
        configuration.timeout_seconds,
    )
    model = configuration.role_models.get("chat") or configuration.model
    try:
        reply = await provider.complete(
            model=model,
            messages=messages,
            temperature=configuration.temperature,
            max_tokens=configuration.max_tokens,
        )
    except (httpx.HTTPError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"The local model did not respond ({type(exc).__name__}). Check Local Models diagnostics.",
        ) from exc

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
