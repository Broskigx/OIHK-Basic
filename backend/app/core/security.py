"""Dependency-free auth primitives: PBKDF2 password hashing and HS256 JWTs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import get_settings

_PBKDF2_ROUNDS = 240_000
_PBKDF2_ALGO = "sha256"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_{_PBKDF2_ALGO}${_PBKDF2_ROUNDS}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds_raw, salt_b64, digest_b64 = stored.split("$")
        if not scheme.startswith("pbkdf2_"):
            return False
        algo = scheme.split("_", 1)[1]
        rounds = int(rounds_raw)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(candidate, expected)


class TokenError(Exception):
    """Raised when a token is malformed, tampered with, or expired."""


def create_access_token(subject: str, *, role: str = "analyst", extra: dict | None = None) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + settings.access_token_ttl_minutes * 60,
        "iss": "oihk-basic",
    }
    if extra:
        payload.update(extra)
    return _encode_jwt(payload, settings.jwt_secret)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    payload = _decode_jwt(token, settings.jwt_secret)
    if payload.get("exp", 0) < int(time.time()):
        raise TokenError("Token has expired")
    return payload


def _encode_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def _decode_jwt(token: str, secret: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise TokenError("Token structure is invalid") from exc
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        provided = _b64url_decode(signature_b64)
    except Exception as exc:
        raise TokenError("Token signature is not decodable") from exc
    if not hmac.compare_digest(expected, provided):
        raise TokenError("Token signature does not match")
    try:
        return json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise TokenError("Token payload is not valid JSON") from exc
