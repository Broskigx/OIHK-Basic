from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.deps import CurrentUser
from app.database import Base
from app.routers import assistant
from app.schemas import ConversationCreate, ConversationMessageCreate, ConversationUpdate


class _Provider:
    async def complete(self, **kwargs) -> str:
        assert kwargs["model"] == "local-test-model"
        assert kwargs["messages"][-1]["role"] == "user"
        return "Local draft response"

    async def stream(self, **kwargs):
        assert kwargs["model"] == "local-test-model"
        for chunk in ("Local ", "draft ", "response"):
            yield chunk


class _FriendlyProvider:
    async def complete(self, **kwargs) -> str:
        assert "A greeting is a greeting" in kwargs["messages"][0]["content"]
        return '{"reply":"¡Hola! ¿Qué quieres investigar hoy?","tool_calls":[]}'

    async def stream(self, **kwargs):
        yield "unused"


class _CreateInvestigationProvider:
    def __init__(self, *, force_write: bool = False):
        self.calls = 0
        self.force_write = force_write

    async def complete(self, **kwargs) -> str:
        self.calls += 1
        if self.calls == 1:
            return (
                '{"reply":"","tool_calls":[{"tool":"create_investigation","arguments":'
                '{"title":"Caso creado por Agente","summary":"Prueba del agente",'
                '"legal_basis":"Authorized research","scope_statement":'
                '"Bounded authorized test investigation.","priority":"high","tags":["agent"]}}]}'
            )
        return "Listo, creé la investigación y quedó activa."

    async def stream(self, **kwargs):
        yield "unused"


async def _sessions(tmp_path, db_name: str = "copilot.db", seed: bool = True):
    """Create an engine over a SQLite file, optionally seeding the local user."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / db_name}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    user_id = "user-local"
    current = CurrentUser(
        id=user_id,
        email="analyst@local.test",
        username="analyst",
        role="admin",
    )

    async def _seed(session) -> None:
        existing_user = (
            await session.execute(select(models.User).where(models.User.id == user_id))
        ).scalar_one_or_none()
        existing_config = (
            await session.execute(
                select(models.LocalModelConfiguration).where(models.LocalModelConfiguration.user_id == user_id)
            )
        ).scalar_one_or_none()
        if existing_user is None:
            session.add(
                models.User(
                    id=user_id,
                    email=current.email,
                    username=current.username,
                    hashed_password="local-test-hash",
                    role="admin",
                )
            )
        if existing_config is None:
            session.add(
                models.LocalModelConfiguration(
                    user_id=user_id,
                    provider="ollama",
                    endpoint="http://127.0.0.1:11434",
                    model="local-test-model",
                    streaming=True,
                )
            )
        await session.commit()

    if seed:
        async with sessions() as session:
            await _seed(session)
    return engine, sessions, current


@pytest.mark.asyncio
async def test_create_save_and_open_chat(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _Provider())
    engine, sessions, current = await _sessions(tmp_path)

    async with sessions() as session:
        assert await assistant.list_conversations(None, False, current, session) == []
        conversation = await assistant.create_conversation(
            ConversationCreate(title="Evidence review", model="local-test-model", settings={"temperature": 0.1}),
            current,
            session,
        )
        assert conversation.title == "Evidence review"
        assert conversation.model == "local-test-model"
        assert conversation.settings == {"temperature": 0.1}

        reply = await assistant.send_message(
            conversation.id,
            ConversationMessageCreate(content="Summarize this evidence"),
            current,
            session,
        )
        assert reply.assistant_message.content == "Local draft response"

        opened = await assistant.list_messages(conversation.id, current, session)
        assert [message.role for message in opened] == ["user", "assistant"]
        assert [message.content for message in opened] == [
            "Summarize this evidence",
            "Local draft response",
        ]

    await engine.dispose()


@pytest.mark.asyncio
async def test_greeting_gets_a_natural_reply_instead_of_evidence_boilerplate(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _FriendlyProvider())
    engine, sessions, current = await _sessions(tmp_path, "friendly.db")

    async with sessions() as session:
        conversation = await assistant.create_conversation(
            ConversationCreate(title="New conversation"), current, session
        )
        reply = await assistant.send_message(
            conversation.id,
            ConversationMessageCreate(content="hola"),
            current,
            session,
        )
        assert reply.assistant_message.content.startswith("¡Hola! Soy OIHK Agent.")
        assert reply.assistant_message.tool_calls == []

    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_can_create_an_investigation_with_an_audited_tool_call(tmp_path, monkeypatch):
    provider = _CreateInvestigationProvider()
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: provider)
    engine, sessions, current = await _sessions(tmp_path, "agent-tools.db")

    async with sessions() as session:
        conversation = await assistant.create_conversation(
            ConversationCreate(title="New conversation"), current, session
        )
        reply = await assistant.send_message(
            conversation.id,
            ConversationMessageCreate(
                content="Crea una investigación llamada Caso creado por Agente con prioridad alta"
            ),
            current,
            session,
        )
        created = (await session.execute(select(models.Case))).scalar_one()
        assert created.title == "Caso creado por Agente"
        assert created.priority == "high"
        assert "Creé **Caso creado por Agente**" in reply.assistant_message.content
        assert reply.assistant_message.tool_calls[0]["tool"] == "create_investigation"
        assert reply.assistant_message.tool_calls[0]["ok"] is True

    await engine.dispose()


@pytest.mark.asyncio
async def test_common_list_intent_uses_the_tool_without_waiting_for_model_planning(tmp_path, monkeypatch):
    class _ShouldNotRun:
        async def complete(self, **kwargs):
            raise AssertionError("common investigation listing should not invoke the model")

    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _ShouldNotRun())
    engine, sessions, current = await _sessions(tmp_path, "agent-fast-list.db")

    async with sessions() as session:
        session.add(
            models.Case(
                owner_id=current.id,
                organization_id=current.organization_id,
                title="Fast case",
                summary="",
                legal_basis="Authorized research",
                scope_statement="Bounded authorized test investigation.",
            )
        )
        await session.commit()
        conversation = await assistant.create_conversation(
            ConversationCreate(title="New conversation"), current, session
        )
        reply = await assistant.send_message(
            conversation.id,
            ConversationMessageCreate(content="Lista mis investigaciones"),
            current,
            session,
        )
        assert "Encontré 1 investigaciones" in reply.assistant_message.content
        assert "Fast case" in reply.assistant_message.content
        assert reply.assistant_message.tool_calls[0]["tool"] == "list_investigations"

    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_refuses_unrequested_model_write(tmp_path, monkeypatch):
    provider = _CreateInvestigationProvider(force_write=True)
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: provider)
    engine, sessions, current = await _sessions(tmp_path, "agent-write-gate.db")

    async with sessions() as session:
        conversation = await assistant.create_conversation(
            ConversationCreate(title="New conversation"), current, session
        )
        reply = await assistant.send_message(
            conversation.id,
            ConversationMessageCreate(content="Cuéntame un chiste"),
            current,
            session,
        )
        assert (await session.execute(select(models.Case))).scalars().all() == []
        assert reply.assistant_message.tool_calls[0]["ok"] is False
        assert "did not explicitly request" in reply.assistant_message.tool_calls[0]["result_summary"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_switch_between_chats_keeps_messages_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _Provider())
    engine, sessions, current = await _sessions(tmp_path)

    async with sessions() as session:
        first = await assistant.create_conversation(ConversationCreate(title="Alpha"), current, session)
        second = await assistant.create_conversation(ConversationCreate(title="Beta"), current, session)
        await assistant.send_message(
            first.id, ConversationMessageCreate(content="Summarize this evidence"), current, session
        )
        await assistant.send_message(
            first.id, ConversationMessageCreate(content="Summarize this evidence"), current, session
        )
        await assistant.send_message(
            second.id, ConversationMessageCreate(content="Summarize this evidence"), current, session
        )

        first_messages = await assistant.list_messages(first.id, current, session)
        second_messages = await assistant.list_messages(second.id, current, session)
        assert len(first_messages) == 4  # 2 user + 2 assistant
        assert len(second_messages) == 2  # 1 user + 1 assistant
        assert all(message.conversation_id == first.id for message in first_messages)
        assert all(message.conversation_id == second.id for message in second_messages)

    await engine.dispose()


@pytest.mark.asyncio
async def test_history_survives_app_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _Provider())
    engine, sessions, current = await _sessions(tmp_path, "restart.db")
    conversation_id = ""

    async with sessions() as session:
        conversation = await assistant.create_conversation(
            ConversationCreate(title="Survivor", model="local-test-model"),
            current,
            session,
        )
        conversation_id = conversation.id
        await assistant.send_message(
            conversation_id,
            ConversationMessageCreate(content="Summarize this evidence"),
            current,
            session,
        )
    await engine.dispose()

    # Simulate an application restart: a brand-new engine over the same file.
    # Seeding is idempotent, so the second engine connects to the existing data.
    restarted_engine, restarted_sessions, current = await _sessions(tmp_path, "restart.db")
    async with restarted_sessions() as session:
        conversations = await assistant.list_conversations(None, False, current, session)
        assert len(conversations) == 1
        assert conversations[0].id == conversation_id
        assert conversations[0].title == "Survivor"
        assert conversations[0].message_count == 2
        history = await assistant.list_messages(conversation_id, current, session)
        assert [message.role for message in history] == ["user", "assistant"]

    await restarted_engine.dispose()


@pytest.mark.asyncio
async def test_delete_chat_removes_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _Provider())
    engine, sessions, current = await _sessions(tmp_path)

    async with sessions() as session:
        conversation = await assistant.create_conversation(ConversationCreate(title="Doomed"), current, session)
        await assistant.send_message(
            conversation.id, ConversationMessageCreate(content="Summarize this evidence"), current, session
        )
        assert len(await assistant.list_messages(conversation.id, current, session)) == 2

        await assistant.delete_conversation(conversation.id, current, session)
        assert await assistant.list_conversations(None, True, current, session) == []
        with pytest.raises(HTTPException) as exc_info:
            await assistant.list_messages(conversation.id, current, session)
        assert exc_info.value.status_code == 404

    await engine.dispose()


@pytest.mark.asyncio
async def test_chat_with_many_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _Provider())
    engine, sessions, current = await _sessions(tmp_path)

    async with sessions() as session:
        conversation = await assistant.create_conversation(ConversationCreate(title="Large"), current, session)
        for index in range(40):
            await assistant.send_message(
                conversation.id,
                ConversationMessageCreate(content=f"Summarize this evidence #{index}"),
                current,
                session,
            )
        history = await assistant.list_messages(conversation.id, current, session)
        assert len(history) == 80  # 40 user + 40 assistant, in order
        assert history[0].role == "user"
        assert history[-1].role == "assistant"
        # Conversation title must be derived from the first message.
        updated = await assistant.update_conversation(conversation.id, ConversationUpdate(), current, session)
        assert updated.message_count == 80

    await engine.dispose()


@pytest.mark.asyncio
async def test_blank_content_and_title_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _Provider())
    engine, sessions, current = await _sessions(tmp_path)

    async with sessions() as session:
        with pytest.raises(HTTPException) as title_error:
            await assistant.create_conversation(ConversationCreate(title="   "), current, session)
        assert title_error.value.status_code == 422

        conversation = await assistant.create_conversation(ConversationCreate(title="Valid"), current, session)
        with pytest.raises(HTTPException) as message_error:
            await assistant.send_message(
                conversation.id,
                ConversationMessageCreate(content="   "),
                current,
                session,
            )
        assert message_error.value.status_code == 422
        assert len(await assistant.list_messages(conversation.id, current, session)) == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_stream_endpoint_persists_and_emits_deltas(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _Provider())
    engine, sessions, current = await _sessions(tmp_path)

    async with sessions() as session:
        conversation = await assistant.create_conversation(
            ConversationCreate(title="Streaming", model="local-test-model"),
            current,
            session,
        )
        response = await assistant.stream_message(
            conversation.id,
            ConversationMessageCreate(content="Summarize this evidence"),
            current,
            session,
        )
        assert response.media_type == "text/event-stream"

        body = "".join([chunk async for chunk in response.body_iterator])
        assert '"type": "message"' in body
        assert '"type": "delta"' in body
        assert '"type": "done"' in body
        assert "Local " in body and "draft " in body and "response" in body

        history = await assistant.list_messages(conversation.id, current, session)
        assert [message.role for message in history] == ["user", "assistant"]
        assert history[-1].content == "Local draft response"
        # The model used must be recorded on the conversation.
        row = (
            await session.execute(
                select(models.AssistantConversation).where(models.AssistantConversation.id == conversation.id)
            )
        ).scalar_one()
        assert row.model == "local-test-model"

    await engine.dispose()


@pytest.mark.asyncio
async def test_a_mutating_tool_without_a_registered_intent_pattern_is_refused(tmp_path, monkeypatch):
    """The write gate has to fail closed when its own registry is incomplete.

    The realistic mistake is adding a tool to AGENT_TOOLS and forgetting its
    entry in _WRITE_INTENT. Reading "no pattern registered" as "no restriction"
    would hand that tool unconditional write access, and it would do so
    silently — every other refusal in this codebase fails closed, so this one
    must too.
    """
    from app.services import assistant_tools

    engine, sessions, current = await _sessions(tmp_path, "agent-write-gate-registry.db")
    monkeypatch.setattr(assistant_tools, "_WRITE_INTENT", {})

    async with sessions() as session:
        result = await assistant_tools.execute_agent_tool(
            tool_name="create_investigation",
            arguments={"title": "Investigation the registry gap would have allowed"},
            # Wording the removed pattern would have matched, so the refusal
            # can only be coming from the missing registration.
            user_text="crea una investigación sobre esto",
            active_case_id=None,
            enabled=None,
            current=current,
            session=session,
        )
        assert result.ok is False
        assert (await session.execute(select(models.Case))).scalars().all() == []

    await engine.dispose()
