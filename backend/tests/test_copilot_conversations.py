from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.deps import CurrentUser
from app.database import Base
from app.routers import assistant
from app.schemas import ConversationCreate, ConversationMessageCreate, ConversationUpdate


class _Provider:
    async def complete(self, **kwargs) -> str:
        assert kwargs["model"] == "local-test-model"
        assert kwargs["messages"][-1] == {"role": "user", "content": "Summarize this evidence"}
        return "Local draft response"


@pytest.mark.asyncio
async def test_conversation_lifecycle_and_incremental_persistence(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'copilot.db'}")
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
    monkeypatch.setattr(assistant, "build_local_provider", lambda *args, **kwargs: _Provider())

    async with sessions() as session:
        session.add(
            models.User(
                id=user_id,
                email=current.email,
                username=current.username,
                hashed_password="local-test-hash",
                role="admin",
            )
        )
        session.add(
            models.LocalModelConfiguration(
                user_id=user_id,
                provider="ollama",
                endpoint="http://127.0.0.1:11434",
                model="local-test-model",
            )
        )
        await session.commit()

        assert await assistant.list_conversations(None, False, current, session) == []
        conversation = await assistant.create_conversation(ConversationCreate(), current, session)
        reply = await assistant.send_message(
            conversation.id,
            ConversationMessageCreate(content="Summarize this evidence"),
            current,
            session,
        )
        assert reply.assistant_message.content == "Local draft response"
        assert [message.role for message in await assistant.list_messages(conversation.id, current, session)] == [
            "user",
            "assistant",
        ]

        renamed = await assistant.update_conversation(
            conversation.id,
            ConversationUpdate(title="Evidence summary", archived=True),
            current,
            session,
        )
        assert renamed.title == "Evidence summary"
        assert renamed.archived is True
        assert renamed.message_count == 2

        await assistant.delete_conversation(conversation.id, current, session)
        assert await assistant.list_conversations(None, True, current, session) == []

    await engine.dispose()
