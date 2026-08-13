"""Bounded, non-blocking primitives for outbound HTTP used by lookup adapters.

Every OSINT and model adapter in Basic talks to an endpoint that Basic does not
control: a third-party registry, a certificate-transparency mirror, or a model
server the operator configured. Those responses are untrusted input, so the
adapters must never hand an unbounded body to ``response.json()``.

Two properties are enforced here:

* **Bounded reads.** ``httpx`` advertises ``accept-encoding: gzip, deflate, br``
  and transparently decompresses, so a small compressed body can expand into an
  arbitrarily large one in memory. The byte ceiling is applied to the
  *decompressed* stream, which is the allocation that actually matters, and the
  declared ``Content-Length`` is rejected up front when it already exceeds it.
* **Non-blocking name resolution.** ``socket.gethostbyname`` is a blocking call.
  Invoked from an ``async def`` it stalls the whole event loop until the
  resolver answers, and the hostname being resolved is investigation data, so a
  blackholed name would freeze every other request. Resolution is offloaded to a
  worker thread under an explicit timeout.

Hostname and address validation live here too, so adapters interpolate only
values that have been proven to be well-formed names rather than free text.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
from typing import Any

import httpx

# Two labels minimum, 1-63 characters each, no leading or trailing hyphen, an
# alphabetic TLD, and 253 characters overall. Deliberately stricter than the
# DNS grammar: these values are interpolated into third-party URLs, so anything
# carrying a delimiter (``/``, ``?``, ``&``, ``#``, ``@``, ``:``) is rejected
# rather than escaped.
_HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)"
    r"(?!-)[a-z0-9-]{1,63}(?<!-)"
    r"(?:\.(?!-)[a-z0-9-]{1,63}(?<!-))*"
    r"\.[a-z]{2,63}$"
)

DEFAULT_RESOLVE_TIMEOUT_SECONDS = 5.0


class OutboundRequestError(ValueError):
    """A safe, user-facing rejection of an outbound lookup."""


class ResponseTooLargeError(OutboundRequestError):
    """The remote endpoint returned more data than the adapter will buffer."""


def require_hostname(value: str) -> str:
    """Return ``value`` as a validated DNS hostname or raise.

    Adapters call this before interpolating investigation data into a URL. A
    value that is not a syntactically valid hostname never reaches the network.
    """
    candidate = (value or "").strip().rstrip(".").lower()
    if not candidate or not _HOSTNAME_PATTERN.match(candidate):
        raise OutboundRequestError("Value is not a valid hostname.")
    return candidate


def require_ipv4(value: str) -> str:
    """Return ``value`` as a validated IPv4 address string or raise."""
    candidate = (value or "").strip()
    try:
        address = ipaddress.IPv4Address(candidate)
    except ipaddress.AddressValueError as exc:
        raise OutboundRequestError("Value is not a valid IPv4 address.") from exc
    return str(address)


async def resolve_hostname_a_record(
    hostname: str,
    *,
    timeout: float = DEFAULT_RESOLVE_TIMEOUT_SECONDS,
) -> str:
    """Resolve ``hostname`` to one IPv4 address without blocking the event loop.

    Raises :class:`OutboundRequestError` when the name does not resolve or the
    resolver does not answer within ``timeout`` seconds.
    """
    validated = require_hostname(hostname)
    try:
        return await asyncio.wait_for(asyncio.to_thread(socket.gethostbyname, validated), timeout=timeout)
    except TimeoutError as exc:
        raise OutboundRequestError("DNS resolution timed out.") from exc
    except socket.gaierror as exc:
        raise OutboundRequestError(f"DNS resolution failed: {exc}") from exc


async def read_bytes_bounded(response: httpx.Response, *, max_bytes: int) -> bytes:
    """Buffer a streaming response body, refusing to exceed ``max_bytes``.

    ``response`` must come from ``client.stream(...)`` and must not have been
    read yet. The ceiling applies after transparent content decoding, so a
    compressed payload that expands past the limit is rejected mid-stream
    instead of being fully materialised.
    """
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise ResponseTooLargeError(f"Response declares {declared} bytes, over the {max_bytes}-byte limit.")

    buffer = bytearray()
    async for chunk in response.aiter_bytes():
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise ResponseTooLargeError(f"Response exceeded the {max_bytes}-byte read limit.")
    return bytes(buffer)


async def request_json_bounded(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_bytes: int,
    expect_status: int | None = 200,
    **kwargs: Any,
) -> Any:
    """Perform a request and decode a JSON body under a hard byte ceiling.

    Returns ``None`` when ``expect_status`` is set and the response carries a
    different status, so callers keep their existing "only act on 200" shape
    without buffering a body they will discard.
    """
    async with client.stream(method, url, **kwargs) as response:
        if expect_status is not None and response.status_code != expect_status:
            return None
        raw = await read_bytes_bounded(response, max_bytes=max_bytes)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise OutboundRequestError("The endpoint returned a malformed JSON response.") from exc


async def get_json_bounded(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
    expect_status: int | None = 200,
    **kwargs: Any,
) -> Any:
    """Convenience wrapper over :func:`request_json_bounded` for GET requests."""
    return await request_json_bounded(
        client,
        "GET",
        url,
        max_bytes=max_bytes,
        expect_status=expect_status,
        **kwargs,
    )
