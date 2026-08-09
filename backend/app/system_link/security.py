"""Installation identities and Ed25519 signature helpers for System Link."""

from __future__ import annotations

import base64
import ctypes
import hashlib
import os
import tempfile
from ctypes import wintypes
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from app.core.config import get_settings

_DPAPI_PREFIX = b"OIHK-DPAPI-1\x00"
_AES_PREFIX = b"OIHK-AESGCM-1\x00"


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


def _seal(data: bytes) -> tuple[bytes, str]:
    if os.name == "nt":
        return _DPAPI_PREFIX + _dpapi_protect(data), "windows-dpapi"
    nonce = os.urandom(12)
    return _AES_PREFIX + nonce + AESGCM(_fallback_key()).encrypt(nonce, data, _AES_PREFIX), "encrypted-file"


def _unseal(data: bytes) -> bytes:
    if data.startswith(_DPAPI_PREFIX):
        if os.name != "nt":
            raise OSError("A DPAPI-bound System Link identity cannot be used on another platform")
        return _dpapi_unprotect(data[len(_DPAPI_PREFIX) :])
    if data.startswith(_AES_PREFIX):
        payload = data[len(_AES_PREFIX) :]
        nonce, ciphertext = payload[:12], payload[12:]
        return AESGCM(_fallback_key()).decrypt(nonce, ciphertext, _AES_PREFIX)
    raise OSError("The System Link identity file has an unknown or plaintext format")


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
    """Stores the private key outside SQLite, bound to the OS user on Windows."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (get_settings()._default_data_dir() / "config" / "system-link-identity.key")

    def load_or_create(self) -> InstallationIdentity:
        if self.path.exists():
            raw = _unseal(self.path.read_bytes())
            return InstallationIdentity(Ed25519PrivateKey.from_private_bytes(raw), self._storage_kind())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        private_key = Ed25519PrivateKey.generate()
        raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        sealed, storage_kind = _seal(raw)
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
        return InstallationIdentity(private_key, storage_kind)

    def _storage_kind(self) -> str:
        prefix = self.path.read_bytes()[: len(_DPAPI_PREFIX)]
        return "windows-dpapi" if prefix == _DPAPI_PREFIX else "encrypted-file"
