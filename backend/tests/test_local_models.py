from __future__ import annotations

import httpx
import pytest

from app.services.local_models import LMStudioProvider, OllamaProvider, build_local_provider, validate_local_endpoint


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _Client:
    def __init__(self, *args, **kwargs):
        self.last_url = ""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def get(self, url: str):
        self.last_url = url
        if url.endswith("/api/tags"):
            return _Response({"models": [{"name": "qwen-local", "size": 1024}]})
        return _Response({"data": [{"id": "lmstudio-local"}]})

    async def post(self, url: str, json: dict):
        self.last_url = url
        if url.endswith("/api/chat"):
            return _Response({"message": {"content": "ollama ready"}})
        return _Response({"choices": [{"message": {"content": "lm studio ready"}}]})


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
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
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
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
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
