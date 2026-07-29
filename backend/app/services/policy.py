"""Policy service for OIHK Basic — scope enforcement and content fetching."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.core.config import get_settings
from app.version import PRODUCT_VERSION

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5


class PublicUrlError(ValueError):
    """A safe, user-facing rejection of a non-public or unreadable URL."""


@dataclass
class FetchedPage:
    url: str
    title: str
    body: str
    robot_compliant: bool = True


def enforce_case_scope(scope_statement: str) -> None:
    """Validate that a case scope statement is meaningful."""
    if not scope_statement or len(scope_statement.strip()) < 12:
        raise ValueError("Scope statement must be at least 12 characters and clearly describe the lawful boundary.")


def _resolve_addresses(hostname: str, port: int) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        rows = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise PublicUrlError("The public URL hostname could not be resolved.") from exc
    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for row in rows:
        try:
            addresses.add(ipaddress.ip_address(row[4][0].split("%", 1)[0]))
        except ValueError as exc:
            raise PublicUrlError("The public URL resolved to an invalid network address.") from exc
    if not addresses:
        raise PublicUrlError("The public URL hostname did not resolve to an address.")
    return addresses


def _validate_public_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PublicUrlError("Only public HTTP or HTTPS URLs can be ingested.")
    if parsed.username or parsed.password:
        raise PublicUrlError("URLs containing embedded credentials are not allowed.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal", ".onion")):
        raise PublicUrlError("Local, private, and onion-network URLs are not allowed.")
    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise PublicUrlError("The URL contains an invalid port.") from exc
    port = explicit_port or (443 if parsed.scheme == "https" else 80)
    try:
        literal = ipaddress.ip_address(hostname.split("%", 1)[0])
        addresses = {literal}
    except ValueError:
        addresses = _resolve_addresses(hostname, port)
    if any(not address.is_global for address in addresses):
        raise PublicUrlError("The URL resolves to a non-public network address.")
    netloc = hostname
    if ":" in hostname:
        netloc = f"[{hostname}]"
    if explicit_port:
        netloc = f"{netloc}:{explicit_port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path or "/", parsed.query, ""))


async def _validated_public_url(url: str) -> str:
    return await asyncio.to_thread(_validate_public_url, url)


def _validate_connected_peer(response, *, required: bool) -> None:
    """Reject DNS rebinding by checking the address of the established socket."""
    stream = response.extensions.get("network_stream")
    if stream is None:
        if required:
            raise PublicUrlError("The public URL connection address could not be verified.")
        return
    try:
        server_addr = stream.get_extra_info("server_addr")
        address = ipaddress.ip_address(str(server_addr[0]).split("%", 1)[0])
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise PublicUrlError("The public URL connection address could not be verified.") from exc
    if not address.is_global:
        raise PublicUrlError("The public URL connected to a non-public network address.")


async def fetch_public_url(url: str, *, transport=None) -> FetchedPage:
    """Fetch a bounded public URL, validating every redirect hop."""
    import httpx

    from app.services.page_reader import extract_body_text

    settings = get_settings()
    max_bytes = settings.max_fetch_bytes

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=False,
        transport=transport,
        trust_env=False,
        headers={"User-Agent": f"OIHK-Basic/{PRODUCT_VERSION} (research tool; contact for takedown)"},
    ) as client:
        current = url
        for redirect_count in range(_MAX_REDIRECTS + 1):
            current = await _validated_public_url(current)
            try:
                async with client.stream("GET", current) as response:
                    _validate_connected_peer(response, required=transport is None)
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location", "").strip()
                        if not location:
                            raise PublicUrlError("The public URL returned an invalid redirect.")
                        if redirect_count >= _MAX_REDIRECTS:
                            raise PublicUrlError("The public URL exceeded the redirect limit.")
                        current = urljoin(str(response.url), location)
                        continue
                    response.raise_for_status()
                    declared_length = response.headers.get("content-length", "")
                    if declared_length.isdigit() and int(declared_length) > max_bytes:
                        raise PublicUrlError(f"The public response exceeds the {max_bytes}-byte read limit.")
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > max_bytes:
                            raise PublicUrlError(f"The public response exceeds the {max_bytes}-byte read limit.")
                    raw = bytes(content)
                    content_type = response.headers.get("content-type", "")
                    body = extract_body_text(raw, content_type=content_type)
                    title = _extract_title(raw) or str(response.url)
                    return FetchedPage(
                        url=str(response.url),
                        title=title,
                        body=body,
                        robot_compliant=True,
                    )
            except PublicUrlError:
                raise
            except httpx.HTTPError as exc:
                raise PublicUrlError("The public URL could not be fetched safely.") from exc
    raise PublicUrlError("The public URL exceeded the redirect limit.")


def _extract_title(html_content: bytes) -> str | None:
    """Extract the <title> from HTML content."""
    import re

    match = re.search(rb"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).decode("utf-8", errors="replace").strip()
        return title[:200]
    return None
