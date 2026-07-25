"""First-run secret generation for OIHK Basic."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from contextlib import suppress
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


_CONFIG_DIR = _get_config_dir()
_SECRETS_FILE = _CONFIG_DIR / "secrets.json"


def _ensure_config_dir() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_secrets() -> dict[str, str]:
    if not _SECRETS_FILE.exists():
        return {}
    try:
        with open(_SECRETS_FILE) as f:
            return {k: str(v) for k, v in json.load(f).items()}
    except json.JSONDecodeError:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = _SECRETS_FILE.with_name(f"{_SECRETS_FILE.name}.corrupt-{timestamp}")
        with suppress(OSError, PermissionError):
            backup_path.write_bytes(_SECRETS_FILE.read_bytes())
        return {}
    except (OSError, PermissionError):
        return {}


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
    secrets_dict = _load_secrets()
    if name in secrets_dict and secrets_dict[name]:
        return secrets_dict[name]
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
