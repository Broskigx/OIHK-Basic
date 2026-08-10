"""Cryptographic authentication and replay protection for module-to-host calls."""

from __future__ import annotations

import hashlib
import re
import time
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.system_link.protocol import ModuleState, canonical_json
from app.system_link.security import verify_signature
from app.system_link.service import SystemLinkError

_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{24,128}$")


def module_request_payload(
    *,
    module_id: str,
    method: str,
    path: str,
    nonce: str,
    timestamp: int,
    body: bytes,
) -> bytes:
    return canonical_json(
        {
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "method": method.upper(),
            "module_id": module_id,
            "nonce": nonce,
            "path": path,
            "timestamp": timestamp,
        }
    )


async def authenticate_module_request(
    session: AsyncSession,
    *,
    module_id: str,
    method: str,
    path: str,
    nonce: str,
    timestamp: int,
    body: bytes,
    signature: str,
    now: int | None = None,
) -> models.SystemLinkModule:
    current_timestamp = now if now is not None else int(time.time())
    if abs(timestamp - current_timestamp) > 30:
        raise SystemLinkError("module_request_stale", "Signed module request timestamp is outside the 30 second window")
    if not _NONCE_RE.fullmatch(nonce):
        raise SystemLinkError("module_nonce_invalid", "Signed module request nonce is malformed")
    module = await session.get(models.SystemLinkModule, module_id)
    if module is None or module.revoked_at is not None or not module.enabled:
        raise SystemLinkError("module_identity_untrusted", "Module is not linked and enabled")
    if ModuleState(module.state) not in {ModuleState.READY, ModuleState.BUSY}:
        raise SystemLinkError("module_not_ready", "Module-to-host calls require authenticated READY/BUSY state")
    try:
        verify_signature(
            module.module_public_key,
            module_request_payload(
                module_id=module_id,
                method=method,
                path=path,
                nonce=nonce,
                timestamp=timestamp,
                body=body,
            ),
            signature,
        )
    except (InvalidSignature, ValueError) as exc:
        raise SystemLinkError("module_request_signature_invalid", "Signed module request could not be verified") from exc
    await session.execute(
        delete(models.SystemLinkReplayNonce).where(
            models.SystemLinkReplayNonce.expires_at < datetime.now(UTC)
        )
    )
    session.add(
        models.SystemLinkReplayNonce(
            module_id=module_id,
            nonce=nonce,
            expires_at=datetime.now(UTC) + timedelta(minutes=2),
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise SystemLinkError("module_request_replayed", "Signed module request nonce was already used") from exc
    return module
