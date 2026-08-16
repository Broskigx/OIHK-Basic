"""Durable, local-model-only Copilot conversations for OIHK Basic."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

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
from app.services.assistant_tools import agent_tool_catalog, execute_agent_tool, prefers_spanish
from app.services.local_models import LocalModelProvider, build_local_provider

router = APIRouter(prefix="/assistant", tags=["assistant"])

_DEFAULT_SYSTEM_PROMPT = """You are OIHK Agent, the friendly and capable local assistant inside OIHK Basic.
Speak naturally, answer the user's actual message, and use the same language as the user unless asked otherwise.
A greeting is a greeting: respond warmly and ask how you can help. Never answer casual conversation with
boilerplate about missing evidence, unchanged observations, or unavailable information.

You can reason about investigations and use the application tools listed below. Use a tool whenever the user asks
you to read or change OIHK data. Never claim that a tool ran unless its result is supplied by OIHK. Clearly separate
confirmed investigation data from inference, never invent sources, and keep sensitive data local."""

_DECISION_PROTOCOL = """Return exactly one JSON object and no Markdown.
For a normal conversational answer:
{"reply":"your natural answer","tool_calls":[]}
To use tools:
{"reply":"","tool_calls":[{"tool":"exact_tool_name","arguments":{"exact_parameter":"value"}}]}
Use at most four tool calls. Never emit a write tool merely as a suggestion. Select a write tool only when the
latest user message explicitly asks for that action. If required information is missing, ask a concise question in
reply instead of inventing it. Ignore generic evidence-status boilerplate from older assistant turns."""


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


@router.get("/tools")
async def list_agent_tools(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Expose the effective local tool catalog used by the current agent."""
    configuration = await _configuration(session, current)
    return agent_tool_catalog(configuration.tools_enabled)


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
    provider = build_local_provider(
        configuration.provider,
        configuration.endpoint,
        configuration.timeout_seconds,
    )
    model = conversation.model or configuration.role_models.get("chat") or configuration.model
    try:
        reply, tool_calls = await _run_agent_turn(
            provider=provider,
            model=model,
            recent=recent,
            configuration=configuration,
            conversation=conversation,
            current=current,
            session=session,
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
        tool_calls=tool_calls,
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


def _decision_messages(
    *,
    recent: list[models.AssistantMessage],
    custom_prompt: str,
    tools_enabled: list[str],
    active_case_id: str | None,
) -> list[dict[str, str]]:
    catalog = json.dumps(agent_tool_catalog(tools_enabled), ensure_ascii=False, separators=(",", ":"))
    system_parts = [
        _DEFAULT_SYSTEM_PROMPT,
        (
            "The latest user message is in Spanish. Every user-facing word in your JSON reply must be Spanish."
            if recent and prefers_spanish(recent[-1].content)
            else "Reply in the language used by the latest user message."
        ),
        f"Active investigation id: {active_case_id or 'none'}.",
        f"Available OIHK tools: {catalog}",
        _DECISION_PROTOCOL,
    ]
    if custom_prompt.strip():
        system_parts.append(f"Additional analyst instructions:\n{custom_prompt.strip()}")
    messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
    messages.extend({"role": row.role, "content": row.content[:16_000]} for row in recent)
    return messages


def _parse_agent_decision(raw: str) -> tuple[str, list[dict[str, Any]]]:
    """Accept the documented JSON envelope, with a plain-text fallback for older local models."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    payload: dict[str, Any] | None = None
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[index:])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if payload is None:
        return text, []

    reply = str(payload.get("reply") or payload.get("message") or "").strip()
    raw_calls = payload.get("tool_calls")
    if not isinstance(raw_calls, list):
        single = payload.get("tool_call")
        raw_calls = [single] if isinstance(single, dict) else []
    calls: list[dict[str, Any]] = []
    for item in raw_calls[:4]:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool") or item.get("name") or "").strip()
        arguments = item.get("arguments") or item.get("args") or {}
        if tool_name and isinstance(arguments, dict):
            calls.append({"tool": tool_name, "arguments": arguments})
    return reply, calls


def _fallback_tool_answer(results: list[dict[str, Any]]) -> str:
    summaries = [str(item.get("result_summary") or "") for item in results if item.get("result_summary")]
    return "\n".join(summaries) or "The requested OIHK action finished without a result summary."


def _greeting_reply(text: str) -> str | None:
    normalized = " ".join(text.casefold().strip().strip(".!?¡¿").split())
    if normalized in {"hola", "holaa", "holaaa", "buenas", "buen día", "buen dia", "buenos días", "buenos dias"}:
        return "¡Hola! Soy OIHK Agent. Puedo conversar contigo, crear investigaciones y trabajar con el grafo, las fuentes, la evidencia, OSINT, reportes, transformaciones y auditoría. ¿Qué hacemos?"
    if normalized in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}:
        return "Hi! I'm OIHK Agent. I can chat with you, create investigations, and work with graphs, sources, evidence, OSINT, reports, transforms, and audit data. What should we do?"
    return None


def _fast_intent(text: str) -> tuple[str, list[dict[str, Any]]] | None:
    """Guarantee the most common app actions without relying on model-specific tool syntax."""
    normalized = " ".join(text.strip().split())
    folded = normalized.casefold()
    if re.search(r"\b(qué herramientas|que herramientas|todas las tools|what tools|what can you do)\b", folded):
        tool_count = len(agent_tool_catalog())
        if prefers_spanish(text):
            return (
                f"Tengo {tool_count} herramientas operativas: listar, abrir, crear y actualizar investigaciones; leer el resumen, "
                "grafo, fuentes, evidencia, custodia, historial OSINT, reportes y auditoría; añadir entidades y "
                "relaciones; ejecutar consultas OSINT; promover resultados; generar reportes; y listar o ejecutar "
                "transformaciones. Las acciones quedan registradas y las escrituras solo se ejecutan si las pides.",
                [],
            )
        return (
            f"I have {tool_count} operational tools for investigations, graphs, sources, evidence, custody, OSINT, reports, "
            "transforms, and audit data. Writes run only when you explicitly request them and remain auditable.",
            [],
        )
    if re.search(
        r"\b(lista|listar|muéstrame|muestrame|ver|dime|list|show)\b.*\b(investigaciones|casos|investigations|cases)\b",
        folded,
    ):
        return "", [{"tool": "list_investigations", "arguments": {}}]

    create_match = re.match(
        r"^(?:por favor[, ]*)?(?:crea|créame|creame|inicia|create|start)\s+"
        r"(?:una?\s+)?(?:investigación|investigacion|caso|investigation|case)"
        r"(?:\s+(?:llamada|llamado|titulada|titulado|sobre|de|named|called|about))?\s*[:\-]?\s*(.*)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if create_match:
        title = create_match.group(1).strip().strip("'\"").strip()
        title = re.sub(r"\s+(?:por favor|please)[.!]*$", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(
            r"\s+(?:con prioridad|with priority)\s+(?:baja|normal|alta|crítica|critica|low|high|critical)[.!]*$",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()
        if len(title) < 3:
            question = (
                "¿Qué título quieres para la investigación?"
                if prefers_spanish(text)
                else "What title should the investigation use?"
            )
            return question, []
        priority = (
            "critical"
            if re.search(r"\b(crítica|critica|critical)\b", folded)
            else "high"
            if re.search(r"\b(alta|high)\b", folded)
            else "normal"
        )
        return "", [{"tool": "create_investigation", "arguments": {"title": title[:200], "priority": priority}}]
    return None


def _tool_detail(item: dict[str, Any], *, spanish: bool) -> str:
    tool = item.get("tool")
    result = item.get("result")
    if not item.get("ok") or not isinstance(result, (dict, list)):
        return str(item.get("result_summary") or "")
    if tool == "list_investigations" and isinstance(result, list):
        heading = f"Encontré {len(result)} investigaciones:" if spanish else f"I found {len(result)} investigations:"
        rows = [
            f"- {row.get('title', 'Untitled')} — {row.get('status', 'unknown')} · {row.get('priority', 'normal')}"
            for row in result[:20]
            if isinstance(row, dict)
        ]
        return "\n".join([heading, *rows])
    if tool in {"create_investigation", "update_investigation"} and isinstance(result, dict):
        verb = "Creé" if tool == "create_investigation" else "Actualicé"
        if not spanish:
            verb = "Created" if tool == "create_investigation" else "Updated"
        return f"{verb} **{result.get('title', 'investigation')}** (`{result.get('id', '')}`), {result.get('status', 'active')} · {result.get('priority', 'normal')}."
    if tool == "get_investigation" and isinstance(result, dict):
        label = "Investigación" if spanish else "Investigation"
        summary = result.get("summary") or ("Sin resumen." if spanish else "No summary.")
        return f"{label}: **{result.get('title', '')}** — {result.get('status', '')} · {result.get('priority', '')}\n{summary}"
    if tool == "list_graph" and isinstance(result, dict):
        nodes = result.get("nodes") if isinstance(result.get("nodes"), list) else []
        edges = result.get("edges") if isinstance(result.get("edges"), list) else []
        heading = (
            f"El grafo tiene {len(nodes)} entidades y {len(edges)} relaciones."
            if spanish
            else f"The graph has {len(nodes)} entities and {len(edges)} relationships."
        )
        labels = [str(row.get("label")) for row in nodes[:12] if isinstance(row, dict) and row.get("label")]
        return heading + (("\n- " + "\n- ".join(labels)) if labels else "")
    if tool == "list_sources" and isinstance(result, list):
        heading = f"Encontré {len(result)} fuentes:" if spanish else f"I found {len(result)} sources:"
        rows = [f"- {row.get('title', '')}" for row in result[:15] if isinstance(row, dict)]
        return "\n".join([heading, *rows])
    if tool == "list_evidence" and isinstance(result, list):
        heading = f"Encontré {len(result)} evidencias:" if spanish else f"I found {len(result)} evidence items:"
        rows = [
            f"- {row.get('original_name', '')} · SHA-256 `{row.get('sha256', '')}`"
            for row in result[:15]
            if isinstance(row, dict)
        ]
        return "\n".join([heading, *rows])
    if tool == "run_osint_lookup" and isinstance(result, dict):
        heading = str(result.get("summary") or item.get("result_summary") or "")
        findings = result.get("findings") if isinstance(result.get("findings"), list) else []
        rows = [
            f"- {row.get('type', 'finding')}: {row.get('value', '')} — {row.get('detail', '')}"
            for row in findings[:12]
            if isinstance(row, dict)
        ]
        return "\n".join([heading, *rows])
    return str(item.get("result_summary") or "")


def _direct_tool_answer(results: list[dict[str, Any]], user_text: str) -> str:
    spanish = prefers_spanish(user_text)
    successful = [item for item in results if item.get("ok")]
    failed = [item for item in results if not item.get("ok")]
    parts = [_tool_detail(item, spanish=spanish) for item in successful]
    if failed:
        heading = "No pude completar:" if spanish else "I couldn't complete:"
        parts.append(
            heading + "\n" + "\n".join(f"- {item.get('tool')}: {item.get('result_summary')}" for item in failed)
        )
    return "\n\n".join(part for part in parts if part).strip() or _fallback_tool_answer(results)


async def _run_agent_turn(
    *,
    provider: LocalModelProvider,
    model: str,
    recent: list[models.AssistantMessage],
    configuration: models.LocalModelConfiguration,
    conversation: models.AssistantConversation,
    current: CurrentUser,
    session: AsyncSession,
) -> tuple[str, list[dict[str, Any]]]:
    latest_text = recent[-1].content if recent else ""
    greeting = _greeting_reply(latest_text)
    if greeting:
        return greeting, []
    fast = _fast_intent(latest_text)
    if fast is not None:
        reply, planned_calls = fast
    else:
        messages = _decision_messages(
            recent=recent,
            custom_prompt=configuration.system_prompt,
            tools_enabled=configuration.tools_enabled or [],
            active_case_id=conversation.case_id,
        )
        raw = await _complete_with_retries(
            provider,
            model=model,
            messages=messages,
            temperature=min(configuration.temperature, 0.3),
            max_tokens=min(configuration.max_tokens, 1_200),
        )
        reply, planned_calls = _parse_agent_decision(raw)
    if not planned_calls:
        fallback = (
            "Estoy aquí. ¿Qué te gustaría investigar?"
            if prefers_spanish(latest_text)
            else "I'm here. What would you like to investigate?"
        )
        return reply or fallback, []

    user_text = latest_text
    executed = []
    for call in planned_calls:
        result = await execute_agent_tool(
            tool_name=call["tool"],
            arguments=call["arguments"],
            user_text=user_text,
            active_case_id=conversation.case_id,
            enabled=configuration.tools_enabled or [],
            current=current,
            session=session,
        )
        executed.append(result.model_record())

    records = [
        {
            "tool": item["tool"],
            "arguments": item["arguments"],
            "result_summary": item["result_summary"],
            "ok": item["ok"],
        }
        for item in executed
    ]
    return _direct_tool_answer(executed, user_text) or reply, records


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
    provider = build_local_provider(
        configuration.provider,
        configuration.endpoint,
        configuration.timeout_seconds,
    )
    model = conversation.model or configuration.role_models.get("chat") or configuration.model

    async def generate() -> AsyncIterator[str]:
        yield _sse(
            {"type": "message", "message": ConversationMessageRead.model_validate(user_message).model_dump(mode="json")}
        )
        try:
            final_content, tool_calls = await _run_agent_turn(
                provider=provider,
                model=model,
                recent=recent,
                configuration=configuration,
                conversation=conversation,
                current=current,
                session=session,
            )
            yield _sse({"type": "delta", "content": final_content})
        except (httpx.HTTPError, KeyError, TypeError, AttributeError, IndexError) as exc:
            yield _sse({"type": "error", "message": f"The local model did not respond ({type(exc).__name__})."})
            return

        assistant_message = models.AssistantMessage(
            conversation_id=conversation.id,
            case_id=conversation.case_id,
            user_id=current.id,
            role="assistant",
            content=final_content.strip() or "The local model returned an empty response.",
            provider=configuration.provider,
            tool_calls=tool_calls,
        )
        session.add(assistant_message)
        if conversation.model != model:
            conversation.model = model
        conversation.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(assistant_message)
        yield _sse(
            {
                "type": "done",
                "user_message": ConversationMessageRead.model_validate(user_message).model_dump(mode="json"),
                "assistant_message": ConversationMessageRead.model_validate(assistant_message).model_dump(mode="json"),
            }
        )

    return StreamingResponse(
        generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
