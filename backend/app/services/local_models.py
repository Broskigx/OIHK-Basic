"""Local-model adapters and private-endpoint safety validation."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from urllib.parse import urlparse

import httpx

PROVIDER_IDS = {"lmstudio", "ollama", "openai_compatible"}


def validate_local_endpoint(endpoint: str) -> str:
    value = endpoint.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Endpoint must be an HTTP(S) URL without embedded credentials")
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return value
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError as exc:
        raise ValueError("Only localhost or private IP model endpoints are allowed") from exc
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError("Only localhost or private IP model endpoints are allowed")
    return value


def _openai_base(endpoint: str) -> str:
    base = validate_local_endpoint(endpoint)
    return base if base.endswith("/v1") else f"{base}/v1"


def _ollama_base(endpoint: str) -> str:
    base = validate_local_endpoint(endpoint)
    return base[:-3] if base.endswith("/v1") else base


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    name: str
    context_length: int | None = None
    size_bytes: int | None = None


class LocalModelProvider(ABC):
    def __init__(self, endpoint: str, timeout_seconds: int = 60):
        self.endpoint = validate_local_endpoint(endpoint)
        self.timeout = httpx.Timeout(connect=4.0, read=float(timeout_seconds), write=30.0, pool=5.0)

    @abstractmethod
    async def list_models(self) -> list[ModelDescriptor]:
        raise NotImplementedError

    @abstractmethod
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ):
        """Yield incremental text deltas. Must be an async iterator."""
        raise NotImplementedError

    async def stream_complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ) -> str:
        """Convenience: consume ``stream`` and join the deltas."""
        chunks: list[str] = []
        async for chunk in self.stream(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        ):
            chunks.append(chunk)
        return "".join(chunks)


class OpenAICompatibleLocalProvider(LocalModelProvider):
    async def list_models(self) -> list[ModelDescriptor]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{_openai_base(self.endpoint)}/models")
            response.raise_for_status()
            rows = response.json().get("data", [])
        return [
            ModelDescriptor(id=str(row.get("id", "")), name=str(row.get("id", ""))) for row in rows if row.get("id")
        ]

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ) -> str:
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if stop:
            payload["stop"] = stop
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{_openai_base(self.endpoint)}/chat/completions", json=payload)
            response.raise_for_status()
            choices = response.json().get("choices") or []
            if not choices:
                return ""
            return str((choices[0] or {}).get("message", {}).get("content", ""))

    async def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ):
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if stop:
            payload["stop"] = stop
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", f"{_openai_base(self.endpoint)}/chat/completions", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                    except (ValueError, TypeError):
                        continue
                    choices = chunk.get("choices") or [{}]
                    delta = ((choices[0] or {}).get("delta") or {}).get("content")
                    if delta:
                        yield delta


class LMStudioProvider(OpenAICompatibleLocalProvider):
    pass


class OllamaProvider(LocalModelProvider):
    async def list_models(self) -> list[ModelDescriptor]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{_ollama_base(self.endpoint)}/api/tags")
            response.raise_for_status()
            rows = response.json().get("models", [])
        return [
            ModelDescriptor(
                id=str(row.get("name", "")),
                name=str(row.get("name", "")),
                size_bytes=int(row["size"]) if row.get("size") is not None else None,
            )
            for row in rows
            if row.get("name")
        ]

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ) -> str:
        options: dict = {"temperature": temperature, "num_predict": max_tokens}
        if stop:
            options["stop"] = stop
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{_ollama_base(self.endpoint)}/api/chat",
                json={"model": model, "messages": messages, "stream": False, "options": options},
            )
            response.raise_for_status()
            return str(response.json().get("message", {}).get("content", ""))

    async def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        stop: list[str] | None = None,
    ):
        options: dict = {"temperature": temperature, "num_predict": max_tokens}
        if stop:
            options["stop"] = stop
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{_ollama_base(self.endpoint)}/api/chat",
                json={"model": model, "messages": messages, "stream": True, "options": options},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    content = (chunk.get("message") or {}).get("content")
                    if content:
                        yield content
                    if chunk.get("done"):
                        return


def build_local_provider(provider: str, endpoint: str, timeout_seconds: int = 60) -> LocalModelProvider:
    if provider not in PROVIDER_IDS:
        raise ValueError(f"Unsupported local model provider: {provider}")
    if provider == "ollama":
        return OllamaProvider(endpoint, timeout_seconds)
    if provider == "lmstudio":
        return LMStudioProvider(endpoint, timeout_seconds)
    return OpenAICompatibleLocalProvider(endpoint, timeout_seconds)


async def detect_local_services() -> list[dict]:
    candidates = [
        ("lmstudio", os.getenv("OIHK_LM_STUDIO_ENDPOINT", "http://127.0.0.1:1234")),
        ("ollama", os.getenv("OIHK_OLLAMA_ENDPOINT", "http://127.0.0.1:11434")),
    ]

    async def probe(provider_id: str, endpoint: str) -> dict:
        started = perf_counter()
        try:
            models = await build_local_provider(provider_id, endpoint, 4).list_models()
            return {
                "provider": provider_id,
                "endpoint": endpoint,
                "status": "online",
                "models": [model.__dict__ for model in models],
                "latency_ms": round((perf_counter() - started) * 1000),
                "error": "",
            }
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            return {
                "provider": provider_id,
                "endpoint": endpoint,
                "status": "offline",
                "models": [],
                "latency_ms": round((perf_counter() - started) * 1000),
                "error": str(exc)[:240],
            }

    return list(await asyncio.gather(*(probe(provider, endpoint) for provider, endpoint in candidates)))
