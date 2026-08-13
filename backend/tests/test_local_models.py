from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.deps import CurrentUser
from app.database import Base
from app.routers.local_models import runtime_status
from app.services.local_models import (
    LMStudioProvider,
    ModelDescriptor,
    OllamaProvider,
    build_local_provider,
    detect_local_services,
    validate_local_endpoint,
)

# Bound before any monkeypatch so the factory below builds a real client
# instead of recursing into its own replacement.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _adapter_handler(request: httpx.Request) -> httpx.Response:
    """Answer the four endpoints the local-model adapters actually call."""
    path = request.url.path
    if path.endswith("/api/tags"):
        return httpx.Response(200, json={"models": [{"name": "qwen-local", "size": 1024}]})
    if path.endswith("/api/chat"):
        return httpx.Response(200, json={"message": {"content": "ollama ready"}})
    if path.endswith("/chat/completions"):
        return httpx.Response(200, json={"choices": [{"message": {"content": "lm studio ready"}}]})
    return httpx.Response(200, json={"data": [{"id": "lmstudio-local"}]})


def _client_factory(handler=_adapter_handler):
    """Build a drop-in ``httpx.AsyncClient`` replacement backed by a mock transport.

    Using a real client over ``MockTransport`` rather than a hand-rolled stub
    keeps the adapters' streaming, status handling, and JSON decoding on the
    real httpx code path, so the response-size ceilings are genuinely exercised.
    """

    def _factory(*_args, **kwargs):
        return _REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(handler),
            timeout=kwargs.get("timeout"),
        )

    return _factory


def test_local_endpoint_policy_accepts_private_and_rejects_public():
    assert validate_local_endpoint("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert validate_local_endpoint("http://192.168.1.20:1234") == "http://192.168.1.20:1234"
    with pytest.raises(ValueError):
        validate_local_endpoint("https://example.com/v1")
    with pytest.raises(ValueError):
        validate_local_endpoint("http://user:secret@localhost:1234")
    with pytest.raises(ValueError):
        validate_local_endpoint("file:///tmp/model")


def test_provider_factory_returns_explicit_adapters():
    assert isinstance(build_local_provider("lmstudio", "http://localhost:1234"), LMStudioProvider)
    assert isinstance(build_local_provider("ollama", "http://localhost:11434"), OllamaProvider)


@pytest.mark.asyncio
async def test_lm_studio_listing_and_inference(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory())
    provider = LMStudioProvider("http://127.0.0.1:1234", 10)
    assert [model.id for model in await provider.list_models()] == ["lmstudio-local"]
    reply = await provider.complete(
        model="lmstudio-local",
        messages=[{"role": "user", "content": "test"}],
        temperature=0.1,
        max_tokens=20,
    )
    assert reply == "lm studio ready"


@pytest.mark.asyncio
async def test_ollama_listing_and_inference(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory())
    provider = OllamaProvider("http://127.0.0.1:11434", 10)
    models = await provider.list_models()
    assert models[0].id == "qwen-local"
    reply = await provider.complete(
        model="qwen-local",
        messages=[{"role": "user", "content": "test"}],
        temperature=0.1,
        max_tokens=20,
    )
    assert reply == "ollama ready"


@pytest.mark.asyncio
async def test_detection_probes_lm_studio_and_ollama_independently(monkeypatch):
    class _DetectedProvider:
        def __init__(self, provider: str):
            self.provider = provider

        async def list_models(self):
            if self.provider == "ollama":
                raise httpx.ConnectError("ollama is not running")
            return [ModelDescriptor(id="lmstudio-local", name="lmstudio-local", context_length=16384)]

    monkeypatch.setattr(
        "app.services.local_models.build_local_provider",
        lambda provider, _endpoint, _timeout: _DetectedProvider(provider),
    )

    services = await detect_local_services()

    assert [service["provider"] for service in services] == ["lmstudio", "ollama"]
    assert services[0]["status"] == "online"
    assert services[0]["models"] == [
        {"id": "lmstudio-local", "name": "lmstudio-local", "context_length": 16384, "size_bytes": None}
    ]
    assert services[1]["status"] == "offline"
    assert services[1]["models"] == []
    assert "not running" in services[1]["error"]


@pytest.mark.asyncio
async def test_saved_model_runtime_status_reports_connected_and_selected_model(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "AsyncClient", _client_factory())
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'models.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        user = models.User(
            email="model@example.test",
            username="model-user",
            hashed_password="not-used",
            role="analyst",
        )
        session.add(user)
        await session.flush()
        session.add(
            models.LocalModelConfiguration(
                user_id=user.id,
                provider="lmstudio",
                endpoint="http://127.0.0.1:1234",
                model="lmstudio-local",
            )
        )
        await session.commit()
        current = CurrentUser(id=user.id, email=user.email, username=user.username, role=user.role)
        status = await runtime_status(current, session)
        assert status.configured is True
        assert status.connected is True
        assert status.model_available is True
        assert status.model_count == 1
        assert status.context_length == 8192
        assert status.max_tokens == 900
    await engine.dispose()


@pytest.mark.asyncio
async def test_saved_model_runtime_status_reports_offline(monkeypatch, tmp_path):
    class _OfflineProvider:
        async def list_models(self):
            raise httpx.ConnectTimeout("offline")

    monkeypatch.setattr("app.routers.local_models.build_local_provider", lambda *_args: _OfflineProvider())
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'models-offline.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        user = models.User(
            email="offline@example.test",
            username="offline-user",
            hashed_password="not-used",
            role="analyst",
        )
        session.add(user)
        await session.flush()
        session.add(
            models.LocalModelConfiguration(
                user_id=user.id,
                provider="ollama",
                endpoint="http://127.0.0.1:11434",
                model="qwen-local",
            )
        )
        await session.commit()
        current = CurrentUser(id=user.id, email=user.email, username=user.username, role=user.role)
        status = await runtime_status(current, session)
        assert status.configured is True
        assert status.connected is False
        assert status.error == "ConnectTimeout"
        assert status.context_length == 8192
        assert status.max_tokens == 900
    await engine.dispose()
