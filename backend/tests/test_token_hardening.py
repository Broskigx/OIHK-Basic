"""Claim validation for the dependency-free HS256 tokens.

The signature check already makes header substitution useless — the HMAC covers
the header — so these assert the *explicit* rejections layered on top of it, the
ones that keep a later refactor from quietly trusting an unvalidated claim.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from app.core.config import get_settings
from app.core.security import TokenError, create_access_token, decode_access_token


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _forge(header: dict, payload: object) -> str:
    """Mint a correctly signed token with arbitrary contents.

    This models the strongest realistic attacker only if the signing key has
    already leaked; used here it isolates the claim checks from the signature
    check, so a failure points at one specific rule.
    """
    secret = get_settings().jwt_secret
    segments = [
        _b64(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(_b64(signature))
    return ".".join(segments)


def _claims(**overrides) -> dict:
    now = int(time.time())
    payload = {"sub": "user-1", "role": "admin", "iat": now, "exp": now + 600, "iss": "oihk-basic"}
    payload.update(overrides)
    return payload


def test_round_trip_accepts_a_freshly_minted_token() -> None:
    payload = decode_access_token(create_access_token("user-1", role="admin"))
    assert payload["sub"] == "user-1"
    assert payload["role"] == "admin"
    assert payload["iss"] == "oihk-basic"


def test_tampered_payload_is_rejected() -> None:
    header, payload, signature = create_access_token("user-1", role="analyst").split(".")
    escalated = _b64(json.dumps(_claims(role="admin")).encode("utf-8"))
    with pytest.raises(TokenError):
        decode_access_token(f"{header}.{escalated}.{signature}")


def test_unsigned_algorithm_is_rejected() -> None:
    token = _forge({"alg": "none", "typ": "JWT"}, _claims())
    with pytest.raises(TokenError, match="algorithm"):
        decode_access_token(token)


def test_asymmetric_algorithm_claim_is_rejected() -> None:
    token = _forge({"alg": "RS256", "typ": "JWT"}, _claims())
    with pytest.raises(TokenError, match="algorithm"):
        decode_access_token(token)


def test_foreign_issuer_is_rejected() -> None:
    token = _forge({"alg": "HS256", "typ": "JWT"}, _claims(iss="some-other-service"))
    with pytest.raises(TokenError, match="issuer"):
        decode_access_token(token)


def test_missing_issuer_is_rejected() -> None:
    claims = _claims()
    del claims["iss"]
    with pytest.raises(TokenError, match="issuer"):
        decode_access_token(_forge({"alg": "HS256", "typ": "JWT"}, claims))


def test_expired_token_is_rejected() -> None:
    token = _forge({"alg": "HS256", "typ": "JWT"}, _claims(exp=int(time.time()) - 1))
    with pytest.raises(TokenError, match="expired"):
        decode_access_token(token)


def test_token_without_an_expiry_is_rejected() -> None:
    """An absent lifetime must not read as an unlimited one."""
    claims = _claims()
    del claims["exp"]
    with pytest.raises(TokenError, match="expired"):
        decode_access_token(_forge({"alg": "HS256", "typ": "JWT"}, claims))


def test_non_object_payload_is_rejected() -> None:
    token = _forge({"alg": "HS256", "typ": "JWT"}, ["not", "an", "object"])
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_structurally_invalid_token_is_rejected() -> None:
    with pytest.raises(TokenError, match="structure"):
        decode_access_token("not-a-jwt")


def test_a_corrupt_password_record_verifies_false_instead_of_raising() -> None:
    """The algorithm name and round count are read back out of the stored hash.

    A row that was truncated, hand-edited or written by an older scheme must
    answer "this password does not verify". Letting the hash primitive raise on
    it turns an unreadable credential into a 500 on the login route, which is a
    worse answer to the same question.
    """
    from app.core.security import hash_password, verify_password

    stored = hash_password("correct horse battery")
    assert verify_password("correct horse battery", stored) is True

    scheme, rounds, salt, digest = stored.split("$")
    assert verify_password("correct horse battery", f"pbkdf2_nonesuch${rounds}${salt}${digest}") is False
    assert verify_password("correct horse battery", f"{scheme}$not-a-number${salt}${digest}") is False
    assert verify_password("correct horse battery", "pbkdf2_sha256$240000$only-three-parts") is False
    assert verify_password("correct horse battery", "") is False
