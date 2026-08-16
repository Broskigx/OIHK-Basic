"""First-run secret generation for OIHK Basic."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path


def _get_config_dir() -> Path:
    import platform as _platform

    system = _platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(base) / "OIHK-Basic" / "config"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "OIHK-Basic" / "config"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        if xdg:
            return Path(xdg) / "OIHK-Basic"
        return Path.home() / ".config" / "OIHK-Basic"


def _default_database_path() -> Path:
    """Return the database this process will actually open.

    The guard in :func:`get_or_create_secret` refuses to mint new keys once a
    database exists, because rotating them silently would leave every custody
    seal in that database unverifiable. That check is only worth anything if it
    looks at the right file, so the packaged data directory — handed to the
    sidecar as ``--data-dir`` and republished as ``OIHK_PACKAGED_DATA_DIR`` —
    wins over the per-platform default whenever it is set.

    The secrets file itself deliberately does *not* follow that directory: keys
    belong in the operating system's configuration location, which on Linux is
    a different root from the data location by convention. Relocating the data
    directory therefore moves the database and leaves the keys where the OS
    expects them, and the guard above is what keeps the pair honest.
    """
    import platform as _platform

    managed = os.environ.get("OIHK_PACKAGED_DATA_DIR", "").strip()
    if managed:
        return Path(managed) / "oihk-basic.db"

    system = _platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        data_dir = Path(base) / "OIHK-Basic"
    elif system == "Darwin":
        data_dir = Path.home() / "Library" / "Application Support" / "OIHK-Basic"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        data_dir = Path(xdg) / "OIHK-Basic" if xdg else Path.home() / ".local" / "share" / "OIHK-Basic"
    return data_dir / "oihk-basic.db"


_CONFIG_DIR = _get_config_dir()
_SECRETS_FILE = _CONFIG_DIR / "secrets.json"


class SecretsFileError(RuntimeError):
    """Raised when persisted secrets cannot be trusted or updated safely."""


def _ensure_config_dir() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def _secrets_lock(timeout_seconds: float = 10.0):
    _ensure_config_dir()
    lock_path = _CONFIG_DIR / ".secrets.lock"
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except (FileExistsError, PermissionError) as exc:
            # Windows can report a transient sharing violation as PermissionError
            # while another thread is closing or unlinking the lock file. Treat it
            # as contention and retain the same bounded timeout/fail-closed path.
            try:
                stale = time.time() - lock_path.stat().st_mtime > 60
            except OSError:
                stale = False
            if stale:
                with suppress(OSError):
                    lock_path.unlink()
                continue
            if time.monotonic() >= deadline:
                raise SecretsFileError("Timed out waiting for the local secrets file lock.") from exc
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(descriptor)
        with suppress(OSError):
            lock_path.unlink()


def _load_secrets() -> dict[str, str]:
    if not _SECRETS_FILE.exists():
        return {}
    try:
        with open(_SECRETS_FILE, encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in payload.items()
        ):
            raise json.JSONDecodeError("Secrets payload must contain string keys and values", "", 0)
        return payload
    except json.JSONDecodeError as exc:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = _SECRETS_FILE.with_name(f"{_SECRETS_FILE.name}.corrupt-{timestamp}")
        with suppress(OSError, PermissionError):
            backup_path.write_bytes(_SECRETS_FILE.read_bytes())
        raise SecretsFileError(
            "The local secrets file is corrupt. A recovery copy was preserved; automatic key rotation was blocked."
        ) from exc
    except (OSError, PermissionError) as exc:
        raise SecretsFileError("The local secrets file could not be read safely.") from exc


def _save_secrets(secrets_dict: dict[str, str]) -> None:
    _ensure_config_dir()
    if os.name != "nt":
        old_umask = os.umask(0o077)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=_CONFIG_DIR,
            prefix="secrets-",
            suffix=".tmp",
            delete=False,
        ) as f:
            json.dump(secrets_dict, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            temporary_path = Path(f.name)
        temporary_path.replace(_SECRETS_FILE)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)
        if os.name != "nt":
            os.umask(old_umask)


def get_or_create_secret(name: str, byte_length: int = 32) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError("Secret names may contain only letters, numbers and underscores")
    if byte_length < 16 or byte_length > 128:
        raise ValueError("Secret length must be between 16 and 128 bytes")
    with _secrets_lock():
        if not _SECRETS_FILE.exists() and _default_database_path().is_file():
            raise SecretsFileError(
                "The local database exists but its secrets file is missing. Automatic key rotation was blocked."
            )
        secrets_dict = _load_secrets()
        if name in secrets_dict and secrets_dict[name]:
            return secrets_dict[name]
        if _default_database_path().is_file():
            raise SecretsFileError(
                f"The local database exists but required secret {name!r} is missing. "
                "Automatic key rotation was blocked."
            )
        new_secret = secrets.token_urlsafe(byte_length)
        secrets_dict[name] = new_secret
        _save_secrets(secrets_dict)
        return new_secret


def get_jwt_secret() -> str:
    return get_or_create_secret("jwt_secret", 32)


def get_custody_signing_key() -> str:
    return get_or_create_secret("custody_signing_key", 32)


def get_custody_key_id() -> str:
    return get_or_create_secret("custody_key_id", 16)


def secrets_exist() -> bool:
    s = _load_secrets()
    return "jwt_secret" in s and "custody_signing_key" in s
