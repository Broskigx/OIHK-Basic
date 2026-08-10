"""Installation identities and Ed25519 signature helpers for System Link.

Private keys are protected by a pluggable storage provider:

* Windows  -> DPAPI (bound to the interactive user session).
* macOS / Linux -> the operating-system keyring (Keychain / Secret Service)
  through the standard ``keyring`` package, matching Evidence Lab.
* Fallback -> AES-GCM file with mode 0600, used only when the OS keyring is
  unavailable, with an explicit storage kind so operators can tell which
  provider actually protects the key.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import os
import tempfile
from ctypes import wintypes
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from app.core.config import get_settings

_DPAPI_PREFIX = b"OIHK-DPAPI-1\x00"
_AES_PREFIX = b"OIHK-AESGCM-1\x00"
_KEYRING_PREFIX = b"OIHK-KEYRING-1\x00"
_KEYRING_SERVICE = "oihk-basic"
_KEYRING_USERNAME = "system-link-installation-identity"


def b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def public_key_text(key: Ed25519PublicKey) -> str:
    return b64encode(key.public_bytes(Encoding.Raw, PublicFormat.Raw))


def public_key_fingerprint(public_key: str) -> str:
    return hashlib.sha256(b64decode(public_key)).hexdigest()


def verify_signature(public_key: str, message: bytes, signature: str) -> None:
    Ed25519PublicKey.from_public_bytes(b64decode(public_key)).verify(b64decode(signature), message)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _dpapi_protect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    output = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "OIHK System Link installation identity",
        None,
        None,
        None,
        0x01,
        ctypes.byref(output),
    ):
        raise OSError("Windows DPAPI could not protect the System Link identity")
    try:
        return bytes(ctypes.string_at(output.pbData, output.cbData))
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer


def _dpapi_unprotect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    output = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0x01, ctypes.byref(output)
    ):
        raise OSError("Windows DPAPI could not unlock the System Link identity")
    try:
        return bytes(ctypes.string_at(output.pbData, output.cbData))
    finally:
        kernel32.LocalFree(output.pbData)
        del source_buffer


def _fallback_key() -> bytes:
    secret = get_settings().custody_signing_key.encode("utf-8")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"oihk-system-link-identity-v1").derive(secret)


class KeyStorageProvider(Protocol):
    """Protects the installation identity private key outside SQLite."""

    storage_kind: str

    def protect(self, data: bytes) -> bytes: ...
    def unprotect(self, sealed: bytes) -> bytes: ...


class WindowsDpapiProvider:
    """DPAPI-bound identity storage (Windows interactive session)."""

    storage_kind = "windows-dpapi"

    def protect(self, data: bytes) -> bytes:
        if os.name != "nt":
            raise OSError("Windows DPAPI is not available on this platform")
        return _DPAPI_PREFIX + _dpapi_protect(data)

    def unprotect(self, sealed: bytes) -> bytes:
        if os.name != "nt":
            raise OSError("A DPAPI-bound System Link identity cannot be used on another platform")
        return _dpapi_unprotect(sealed[len(_DPAPI_PREFIX) :])


class OsKeyringProvider:
    """OS keyring-backed storage (macOS Keychain / Linux Secret Service)."""

    storage_kind = "os-keyring"

    def __init__(self, service: str = _KEYRING_SERVICE, username: str = _KEYRING_USERNAME) -> None:
        self.service = service
        self.username = username

    def probe(self) -> None:
        """Verify a real OS keyring backend is available without touching stored secrets."""
        import keyring
        from keyring.errors import KeyringError

        try:
            keyring.get_keyring()
        except KeyringError as exc:
            raise OSError("The operating-system keyring has no usable backend on this host") from exc

    def protect(self, data: bytes) -> bytes:
        self._store(data)
        return _KEYRING_PREFIX + self.username.encode("ascii")

    def unprotect(self, sealed: bytes) -> bytes:
        if not sealed.startswith(_KEYRING_PREFIX):
            raise OSError("The System Link identity file is not an OS keyring reference")
        # The entry name is embedded in the reference file itself, mirroring the
        # dispatch-by-prefix pattern of the other providers: whoever wrote the
        # file decides which keyring entry it points at.
        username = sealed[len(_KEYRING_PREFIX) :].decode("ascii", errors="strict")
        value = self._load(username)
        if value is None:
            raise OSError(
                "The OS keyring no longer contains the System Link identity entry; "
                "restore it or re-pair the module installation"
            )
        return value

    def _store(self, data: bytes) -> None:
        import keyring
        from keyring.errors import KeyringError

        try:
            keyring.set_password(self.service, self.username, b64encode(data))
        except KeyringError as exc:
            raise OSError("The operating-system keyring rejected the System Link identity") from exc

    def _load(self, username: str | None = None) -> bytes | None:
        import keyring
        from keyring.errors import KeyringError

        try:
            value = keyring.get_password(self.service, username or self.username)
        except KeyringError as exc:
            raise OSError("The operating-system keyring is unavailable") from exc
        return b64decode(value) if value else None


class EncryptedFileProvider:
    """Explicit fallback: AES-GCM sealed file with mode 0600."""

    storage_kind = "encrypted-file"

    def protect(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        return _AES_PREFIX + nonce + AESGCM(_fallback_key()).encrypt(nonce, data, _AES_PREFIX)

    def unprotect(self, sealed: bytes) -> bytes:
        payload = sealed[len(_AES_PREFIX) :]
        nonce, ciphertext = payload[:12], payload[12:]
        return AESGCM(_fallback_key()).decrypt(nonce, ciphertext, _AES_PREFIX)


def _provider_for_storage(sealed: bytes) -> KeyStorageProvider:
    if sealed.startswith(_DPAPI_PREFIX):
        return WindowsDpapiProvider()
    if sealed.startswith(_KEYRING_PREFIX):
        return OsKeyringProvider()
    if sealed.startswith(_AES_PREFIX):
        return EncryptedFileProvider()
    raise OSError("The System Link identity file has an unknown or plaintext format")


def _default_provider() -> KeyStorageProvider:
    """Pick the strongest provider available on this platform.

    Windows always uses DPAPI. Elsewhere the OS keyring is preferred; when it
    is not installed or has no usable backend, we fall back to the AES-GCM
    file provider instead of failing the identity entirely.
    """
    if os.name == "nt":
        return WindowsDpapiProvider()
    try:
        provider = OsKeyringProvider()
        provider.probe()
        return provider
    except Exception:  # noqa: BLE001 - any keyring failure degrades to the file fallback
        return EncryptedFileProvider()


def _seal(data: bytes) -> tuple[bytes, str]:
    provider = _default_provider()
    return provider.protect(data), provider.storage_kind


def _unseal(data: bytes) -> bytes:
    return _provider_for_storage(data).unprotect(data)


class InstallationIdentity:
    def __init__(self, private_key: Ed25519PrivateKey, storage_kind: str) -> None:
        self.private_key = private_key
        self.storage_kind = storage_kind

    @property
    def public_key(self) -> str:
        return public_key_text(self.private_key.public_key())

    @property
    def fingerprint(self) -> str:
        return public_key_fingerprint(self.public_key)

    def sign(self, message: bytes) -> str:
        return b64encode(self.private_key.sign(message))


class InstallationIdentityStore:
    """Stores the private key outside SQLite behind a selected storage provider."""

    def __init__(self, path: Path | None = None, provider: KeyStorageProvider | None = None) -> None:
        self.path = path or (get_settings()._default_data_dir() / "config" / "system-link-identity.key")
        self._provider = provider

    def _default(self) -> KeyStorageProvider:
        return self._provider or _default_provider()

    def load_or_create(self) -> InstallationIdentity:
        if self.path.exists():
            raw = _unseal(self.path.read_bytes())
            return InstallationIdentity(Ed25519PrivateKey.from_private_bytes(raw), self._storage_kind())
        provider = self._default()
        private_key = Ed25519PrivateKey.generate()
        raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        sealed = provider.protect(raw)
        descriptor, temporary_name = tempfile.mkstemp(prefix="system-link-identity-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "wb") as destination:
                destination.write(sealed)
                destination.flush()
                os.fsync(destination.fileno())
            if os.name != "nt":
                os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, self.path)
        finally:
            Path(temporary_name).unlink(missing_ok=True)
        return InstallationIdentity(private_key, provider.storage_kind)

    def _storage_kind(self) -> str:
        return _provider_for_storage(self.path.read_bytes()).storage_kind
