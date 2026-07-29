from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.services import policy
from app.services.policy import PublicUrlError


def _public_dns(_hostname: str, _port: int):
    return {policy.ipaddress.ip_address("93.184.216.34")}


class _NetworkStream:
    def __init__(self, address: str) -> None:
        self.address = address

    def get_extra_info(self, name: str):
        return (self.address, 443) if name == "server_addr" else None


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.4/",
        "http://user:secret@example.com/",
        "http://hiddenservice.onion/",
    ],
)
def test_public_url_policy_rejects_private_credentials_and_onion(url: str) -> None:
    with pytest.raises(PublicUrlError):
        policy._validate_public_url(url)


@pytest.mark.asyncio
async def test_public_fetch_revalidates_redirect_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "_resolve_addresses", _public_dns)
    monkeypatch.setattr(policy, "get_settings", lambda: SimpleNamespace(max_fetch_bytes=1024))
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    with pytest.raises(PublicUrlError, match="non-public"):
        await policy.fetch_public_url("https://example.test/start", transport=httpx.MockTransport(handler))
    assert requests == ["https://example.test/start"]


@pytest.mark.asyncio
async def test_public_fetch_enforces_streamed_response_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "_resolve_addresses", _public_dns)
    monkeypatch.setattr(policy, "get_settings", lambda: SimpleNamespace(max_fetch_bytes=4))
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=b"12345"))

    with pytest.raises(PublicUrlError, match="4-byte"):
        await policy.fetch_public_url("https://example.test/", transport=transport)


@pytest.mark.asyncio
async def test_public_fetch_rejects_private_connected_peer_after_public_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(policy, "_resolve_addresses", _public_dns)
    monkeypatch.setattr(policy, "get_settings", lambda: SimpleNamespace(max_fetch_bytes=4096))
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            content=b"not reachable",
            extensions={"network_stream": _NetworkStream("127.0.0.1")},
        )
    )

    with pytest.raises(PublicUrlError, match="connected to a non-public"):
        await policy.fetch_public_url("https://example.test/", transport=transport)


@pytest.mark.asyncio
async def test_public_fetch_returns_sanitized_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "_resolve_addresses", _public_dns)
    monkeypatch.setattr(policy, "get_settings", lambda: SimpleNamespace(max_fetch_bytes=4096))
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<title>Public record</title><script>secret()</script><p>Evidence</p>",
        )
    )

    result = await policy.fetch_public_url("https://example.test/", transport=transport)
    assert result.title == "Public record"
    assert result.body == "Public record Evidence"
    assert result.url == "https://example.test/"
