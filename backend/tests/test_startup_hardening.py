"""Boot-time refusals.

``_enforce_hardening`` is the one place that decides whether an unsafe
configuration is allowed to serve traffic at all. Every rule in it is a
deliberate "refuse to start" that nothing else re-checks at runtime, so each one
is asserted here rather than trusted to stay correct by inspection.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.main import _enforce_hardening

STRONG_SECRET = "a-real-secret-value-not-the-development-placeholder"
STRONG_CUSTODY_KEY = "a-real-custody-signing-key-not-the-placeholder"


def _production(**overrides) -> Settings:
    base = {
        "environment": "production",
        "auth_enabled": True,
        "jwt_secret": STRONG_SECRET,
        "custody_signing_key": STRONG_CUSTODY_KEY,
        "cors_origins": "https://oihk.example.com",
        "server_bind_host": "127.0.0.1",
        "allowed_hosts": "",
        "temporary_basic_login": False,
    }
    base.update(overrides)
    return Settings(**base)


def _development(**overrides) -> Settings:
    base = {
        "environment": "development",
        "auth_enabled": False,
        "server_bind_host": "127.0.0.1",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def enforce(monkeypatch):
    def _run(settings: Settings) -> None:
        monkeypatch.setattr("app.main.get_settings", lambda: settings)
        _enforce_hardening()

    return _run


# --- Production refusals ------------------------------------------------------


def test_production_accepts_a_fully_configured_deployment(enforce) -> None:
    enforce(_production())


def test_production_refuses_disabled_authentication(enforce) -> None:
    with pytest.raises(RuntimeError, match="OIHK_AUTH_ENABLED=false"):
        enforce(_production(auth_enabled=False))


def test_production_refuses_the_default_jwt_secret(enforce) -> None:
    with pytest.raises(RuntimeError, match="OIHK_JWT_SECRET"):
        enforce(_production(jwt_secret="change-me-please"))


def test_production_refuses_the_default_custody_key(enforce) -> None:
    with pytest.raises(RuntimeError, match="OIHK_CUSTODY_SIGNING_KEY"):
        enforce(_production(custody_signing_key="change-me-please"))


def test_production_refuses_wildcard_cors(enforce) -> None:
    with pytest.raises(RuntimeError, match="wildcard CORS"):
        enforce(_production(cors_origins="*"))


def test_production_refuses_public_registration(enforce) -> None:
    with pytest.raises(RuntimeError, match="self-registration"):
        enforce(_production(public_registration=True))


def test_production_refuses_temporary_basic_login(enforce) -> None:
    with pytest.raises(RuntimeError, match="TEMPORARY_BASIC_LOGIN"):
        enforce(_production(temporary_basic_login=True))


def test_production_refuses_a_public_bind_without_a_host_allowlist(enforce) -> None:
    """Off loopback the Host allowlist cannot be derived, so it must be stated."""
    with pytest.raises(RuntimeError, match="OIHK_ALLOWED_HOSTS"):
        enforce(_production(server_bind_host="0.0.0.0"))


def test_production_accepts_a_public_bind_with_a_host_allowlist(enforce) -> None:
    enforce(_production(server_bind_host="0.0.0.0", allowed_hosts="oihk.example.com"))


# --- Single-user desktop refusals ---------------------------------------------


def test_loopback_single_user_mode_starts(enforce) -> None:
    enforce(_development())


def test_unauthenticated_mode_refuses_a_public_bind(enforce) -> None:
    """Without auth the CSRF layer stands down, so the port must stay local."""
    with pytest.raises(RuntimeError, match="loopback"):
        enforce(_development(server_bind_host="0.0.0.0"))


def test_authenticated_development_may_bind_publicly(enforce) -> None:
    enforce(_development(auth_enabled=True, server_bind_host="0.0.0.0"))
