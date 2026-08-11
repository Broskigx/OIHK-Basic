"""Key storage provider tests — DPAPI (Windows), OS keyring, and AES-GCM fallback.

The OS keyring provider is exercised through a fake in-memory keyring module so
the tests stay hermetic on every platform (CI Linux has no Secret Service
daemon, and the repository runs on Windows locally).
"""

from __future__ import annotations

import os

import pytest

from app.system_link import security
from app.system_link.security import (
    EncryptedFileProvider,
    InstallationIdentityStore,
    OsKeyringProvider,
    WindowsDpapiProvider,
)


class _FakeKeyring:
    """In-memory stand-in for the keyring package's public API."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)

    def get_keyring(self) -> object:
        return self


class _NoBackendKeyring:
    """Keyring module whose backend probe fails, forcing the fallback provider."""

    def get_keyring(self) -> object:
        from keyring.errors import NoKeyringError

        raise NoKeyringError("no backend configured")


class _FailBackendKeyring:
    """Keyring module that installs a no-op *fail* backend, exactly like a
    headless CI host: ``get_keyring()`` succeeds but every real read/write
    raises :class:`NoKeyringError`."""

    def get_keyring(self) -> object:
        return _FailBackend()

    def get_password(self, service: str, username: str) -> str | None:
        from keyring.errors import NoKeyringError

        raise NoKeyringError("no recommended backend was available")

    def set_password(self, service: str, username: str, password: str) -> None:
        from keyring.errors import NoKeyringError

        raise NoKeyringError("no recommended backend was available")


class _FailBackend:
    pass

def _install_fake_keyring(monkeypatch: pytest.MonkeyPatch, module: object) -> None:
    monkeypatch.setitem(__import__("sys").modules, "keyring", module)
    monkeypatch.setitem(__import__("sys").modules, "keyring.errors", _FakeKeyringErrors())


class _FakeKeyringErrors:
    class KeyringError(RuntimeError):
        pass

    class NoKeyringError(KeyringError):
        pass


def test_windows_dpapi_provider_round_trip_or_rejects_on_other_platforms(tmp_path: pytest.TempPathFactory) -> None:
    provider = WindowsDpapiProvider()
    secret = b"sensitive-system-link-private-key"
    if os.name == "nt":
        sealed = provider.protect(secret)
        assert sealed.startswith(security._DPAPI_PREFIX)
        assert provider.unprotect(sealed) == secret
        assert provider.storage_kind == "windows-dpapi"
    else:
        with pytest.raises(OSError, match="not available"):
            provider.protect(secret)


def test_encrypted_file_provider_round_trip(tmp_path: pytest.TempPathFactory) -> None:
    provider = EncryptedFileProvider()
    secret = b"fallback-protected-private-key"
    sealed = provider.protect(secret)
    assert sealed.startswith(security._AES_PREFIX)
    assert provider.unprotect(sealed) == secret
    assert provider.storage_kind == "encrypted-file"
    with pytest.raises(ValueError):
        provider.unprotect(b"tampered-garbage")


def test_os_keyring_provider_round_trip_with_fake_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeKeyring()
    _install_fake_keyring(monkeypatch, fake)
    provider = OsKeyringProvider()
    provider.probe()  # must not raise with a usable backend
    secret = b"keyring-protected-private-key"
    sealed = provider.protect(secret)
    assert sealed.startswith(security._KEYRING_PREFIX)
    assert provider.unprotect(sealed) == secret
    assert provider.storage_kind == "os-keyring"
    # The secret must never be persisted inside the reference file itself.
    assert secret not in sealed


def test_os_keyring_provider_rejects_missing_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeKeyring()
    _install_fake_keyring(monkeypatch, fake)
    provider = OsKeyringProvider()
    with pytest.raises(OSError, match="no longer contains"):
        provider.unprotect(security._KEYRING_PREFIX + b"missing-entry")


def test_default_provider_prefers_keyring_and_falls_back_when_no_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        pytest.skip("DPAPI is always preferred on Windows")

    fake = _FakeKeyring()
    _install_fake_keyring(monkeypatch, fake)
    provider = security._default_provider()
    assert isinstance(provider, OsKeyringProvider)

    _install_fake_keyring(monkeypatch, _NoBackendKeyring())
    fallback = security._default_provider()
    assert isinstance(fallback, EncryptedFileProvider)

    # Regression: a host where get_keyring() succeeds but the backend is a
    # no-op *fail* (headless Linux CI, no Secret Service daemon). The read
    # probe must detect it and degrade to the file fallback.
    _install_fake_keyring(monkeypatch, _FailBackendKeyring())
    degraded = security._default_provider()
    assert isinstance(degraded, EncryptedFileProvider)


def test_identity_store_reports_selected_provider_kind(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    fake = _FakeKeyring()
    _install_fake_keyring(monkeypatch, fake)
    path = tmp_path / "identity.key"
    store = InstallationIdentityStore(path)
    if os.name == "nt":
        assert store._default().storage_kind == "windows-dpapi"
    else:
        assert store._default().storage_kind == "os-keyring"
    identity = store.load_or_create()
    assert identity.storage_kind in {"windows-dpapi", "os-keyring", "encrypted-file"}
    assert InstallationIdentityStore(path).load_or_create().fingerprint == identity.fingerprint
