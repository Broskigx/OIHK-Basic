"""Versioned, capability-oriented OIHK System Link protocol contracts."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

SYSTEM_LINK_PROTOCOL_VERSION = "1.0"
MANIFEST_SCHEMA_VERSION = 1
MODULE_SDK_VERSION = 1

MODULE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{1,78}[a-z0-9])?$")
CATEGORY_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
ENTRYPOINT_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class ModuleState(StrEnum):
    NOT_INSTALLED = "NOT_INSTALLED"
    UNLINKED = "UNLINKED"
    PAIRING = "PAIRING"
    LINKED_OFF = "LINKED_OFF"
    STARTING = "STARTING"
    AUTHENTICATING = "AUTHENTICATING"
    READY = "READY"
    BUSY = "BUSY"
    STOPPING = "STOPPING"
    ERROR = "ERROR"
    INCOMPATIBLE = "INCOMPATIBLE"
    REVOKED = "REVOKED"
    DISABLED = "DISABLED"
    QUARANTINED = "QUARANTINED"


class LifecycleAction(StrEnum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"
    CANCEL = "cancel"


class StartupPolicy(StrEnum):
    MANUAL = "manual"
    START_WITH_BASIC = "start-with-basic"
    RESTORE_LAST_STATE = "restore-last-state"


KNOWN_CAPABILITIES = frozenset(
    {
        "case.read",
        "case.write",
        "case.metadata.read",
        "entity.read",
        "entity.write",
        "source.read",
        "evidence.read",
        "evidence.write",
        "evidence.import",
        "evidence.metadata.write",
        "report.read",
        "report.section.write",
        "ui.navigation.register",
        "ui.notification",
        "module.status.publish",
    }
)

FORBIDDEN_CAPABILITIES = frozenset(
    {"basic.all", "database.raw", "filesystem.all", "filesystem.write", "shell.execute"}
)

ALLOWED_TRANSITIONS: dict[ModuleState, frozenset[ModuleState]] = {
    ModuleState.NOT_INSTALLED: frozenset({ModuleState.UNLINKED}),
    ModuleState.UNLINKED: frozenset({ModuleState.PAIRING}),
    ModuleState.PAIRING: frozenset({ModuleState.LINKED_OFF, ModuleState.UNLINKED, ModuleState.ERROR}),
    ModuleState.LINKED_OFF: frozenset(
        {
            ModuleState.STARTING,
            ModuleState.DISABLED,
            ModuleState.REVOKED,
            ModuleState.INCOMPATIBLE,
            ModuleState.ERROR,
        }
    ),
    ModuleState.STARTING: frozenset(
        {ModuleState.AUTHENTICATING, ModuleState.STOPPING, ModuleState.ERROR}
    ),
    ModuleState.AUTHENTICATING: frozenset(
        {ModuleState.READY, ModuleState.STOPPING, ModuleState.ERROR, ModuleState.INCOMPATIBLE}
    ),
    ModuleState.READY: frozenset(
        {ModuleState.BUSY, ModuleState.STOPPING, ModuleState.ERROR, ModuleState.DISABLED, ModuleState.REVOKED}
    ),
    ModuleState.BUSY: frozenset({ModuleState.READY, ModuleState.STOPPING, ModuleState.ERROR}),
    ModuleState.STOPPING: frozenset({ModuleState.LINKED_OFF, ModuleState.ERROR}),
    ModuleState.ERROR: frozenset(
        {
            ModuleState.STARTING,
            ModuleState.STOPPING,
            ModuleState.LINKED_OFF,
            ModuleState.DISABLED,
            ModuleState.REVOKED,
            ModuleState.QUARANTINED,
            ModuleState.INCOMPATIBLE,
        }
    ),
    ModuleState.INCOMPATIBLE: frozenset({ModuleState.LINKED_OFF, ModuleState.REVOKED}),
    ModuleState.DISABLED: frozenset({ModuleState.LINKED_OFF, ModuleState.REVOKED}),
    ModuleState.QUARANTINED: frozenset({ModuleState.LINKED_OFF, ModuleState.REVOKED}),
    ModuleState.REVOKED: frozenset(),
}


class InvalidStateTransition(ValueError):
    pass


def require_transition(current: ModuleState, target: ModuleState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStateTransition(f"System Link transition {current.value} -> {target.value} is not allowed")


def canonical_json(payload: BaseModel | dict) -> bytes:
    value = payload.model_dump(mode="json", exclude_none=True) if isinstance(payload, BaseModel) else payload
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def validate_capabilities(values: list[str]) -> list[str]:
    normalized = sorted(set(values))
    forbidden = sorted(set(normalized) & FORBIDDEN_CAPABILITIES)
    unknown = sorted(set(normalized) - KNOWN_CAPABILITIES)
    if forbidden:
        raise ValueError(f"Forbidden System Link capabilities requested: {', '.join(forbidden)}")
    if unknown:
        raise ValueError(f"Unknown System Link capabilities requested: {', '.join(unknown)}")
    return normalized


def _safe_relative_path(value: str, *, field_name: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise ValueError(f"{field_name} must be a normalized relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{field_name} must stay inside its declared root")
    if ":" in path.parts[0]:
        raise ValueError(f"{field_name} must not contain a drive or URI scheme")
    return path.as_posix()


class ModuleCategory(BaseModel):
    id: str
    label: str = Field(min_length=1, max_length=80)
    icon: str = Field(default="module", pattern=r"^[a-z0-9-]{1,40}$")
    case_scoped: bool = True
    order: int = Field(default=100, ge=0, le=10_000)
    required_capabilities: list[str] = Field(default_factory=lambda: ["ui.navigation.register"])

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not CATEGORY_ID_RE.fullmatch(value):
            raise ValueError("Category id must be a lowercase kebab-case identifier")
        return value

    @field_validator("required_capabilities")
    @classmethod
    def valid_capabilities(cls, value: list[str]) -> list[str]:
        return validate_capabilities(value)


class ModuleLifecycleDescriptor(BaseModel):
    kind: Literal["managed-process"] = "managed-process"
    entrypoint_id: str
    install_root: str = Field(min_length=1, max_length=2048)
    executable: str = Field(min_length=1, max_length=500)
    executable_sha256: str
    base_url: str = Field(min_length=1, max_length=500)
    supports: list[LifecycleAction] = Field(
        default_factory=lambda: [LifecycleAction.START, LifecycleAction.STOP, LifecycleAction.RESTART, LifecycleAction.STATUS]
    )
    startup_timeout_seconds: float = Field(default=30, ge=1, le=120)
    stop_timeout_seconds: float = Field(default=15, ge=1, le=60)

    @field_validator("entrypoint_id")
    @classmethod
    def valid_entrypoint_id(cls, value: str) -> str:
        if not ENTRYPOINT_ID_RE.fullmatch(value):
            raise ValueError("Lifecycle entrypoint_id must be a lowercase kebab-case identifier")
        return value

    @field_validator("install_root")
    @classmethod
    def absolute_install_root(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("Lifecycle install_root must be an absolute installer-registered directory")
        return value

    @field_validator("executable")
    @classmethod
    def safe_executable(cls, value: str) -> str:
        normalized = _safe_relative_path(value, field_name="Lifecycle executable")
        name = PurePosixPath(normalized).name.lower()
        forbidden_names = {
            "cmd.exe",
            "powershell.exe",
            "pwsh.exe",
            "bash",
            "sh",
            "zsh",
            "python",
            "python3",
            "python.exe",
            "node",
            "node.exe",
            "wscript.exe",
            "cscript.exe",
        }
        forbidden_suffixes = {".bat", ".cmd", ".ps1", ".sh", ".py", ".js", ".vbs"}
        if name in forbidden_names or PurePosixPath(name).suffix in forbidden_suffixes:
            raise ValueError("Lifecycle executable may not be a shell, interpreter, or script")
        return normalized

    @field_validator("executable_sha256")
    @classmethod
    def valid_executable_hash(cls, value: str) -> str:
        value = value.lower()
        if not SHA256_RE.fullmatch(value):
            raise ValueError("Lifecycle executable_sha256 must be a lowercase SHA-256 digest")
        return value

    @field_validator("base_url")
    @classmethod
    def loopback_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("Lifecycle base_url must use loopback HTTP")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Lifecycle base_url may not contain credentials, a query, or a fragment")
        if not parsed.port:
            raise ValueError("Lifecycle base_url must declare a fixed installer-registered port")
        return value.rstrip("/")

    @field_validator("supports")
    @classmethod
    def valid_supports(cls, value: list[LifecycleAction]) -> list[LifecycleAction]:
        normalized = list(dict.fromkeys(value))
        required = {LifecycleAction.START, LifecycleAction.STOP, LifecycleAction.STATUS}
        if not required.issubset(normalized):
            raise ValueError("Lifecycle descriptor must support start, stop, and status")
        if LifecycleAction.CANCEL in normalized:
            raise ValueError("Cancellation is host-owned and may not be declared by a module")
        return normalized

    def resolve_executable(self) -> Path:
        declared_root = Path(self.install_root)
        if declared_root.is_symlink():
            raise ValueError("Lifecycle installation root may not be a symlink")
        root = declared_root.resolve(strict=True)
        declared_candidate = root.joinpath(*PurePosixPath(self.executable).parts)
        if declared_candidate.is_symlink():
            raise ValueError("Lifecycle executable may not be a symlink")
        candidate = declared_candidate.resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Lifecycle executable escapes the registered installation root") from exc
        if not candidate.is_file():
            raise ValueError("Lifecycle executable must be a regular non-symlink file")
        return candidate


class ModuleManifest(BaseModel):
    schema_version: Literal[1] = MANIFEST_SCHEMA_VERSION
    protocol_version: str = SYSTEM_LINK_PROTOCOL_VERSION
    sdk_version: Literal[1] = MODULE_SDK_VERSION
    module_id: str
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    compatible_basic_versions: list[str] = Field(min_length=1, max_length=20)
    categories: list[ModuleCategory] = Field(default_factory=list, max_length=50)
    requested_capabilities: list[str] = Field(default_factory=list, max_length=50)
    package_sha256: str
    frontend_entrypoint: str | None = Field(default=None, max_length=500)
    lifecycle: ModuleLifecycleDescriptor

    @field_validator("module_id")
    @classmethod
    def valid_module_id(cls, value: str) -> str:
        if not MODULE_ID_RE.fullmatch(value):
            raise ValueError("Module id must be a lowercase reverse-DNS-style identifier")
        return value

    @field_validator("requested_capabilities")
    @classmethod
    def valid_requested_capabilities(cls, value: list[str]) -> list[str]:
        return validate_capabilities(value)

    @field_validator("package_sha256")
    @classmethod
    def valid_package_hash(cls, value: str) -> str:
        value = value.lower()
        if not SHA256_RE.fullmatch(value):
            raise ValueError("package_sha256 must be a lowercase SHA-256 digest")
        return value

    @field_validator("frontend_entrypoint")
    @classmethod
    def valid_frontend_entrypoint(cls, value: str | None) -> str | None:
        return _safe_relative_path(value, field_name="Frontend entrypoint") if value else None

    @model_validator(mode="after")
    def internally_consistent(self) -> ModuleManifest:
        if self.protocol_version != SYSTEM_LINK_PROTOCOL_VERSION:
            raise ValueError(f"Unsupported System Link protocol version {self.protocol_version!r}")
        if self.lifecycle.entrypoint_id != f"{self.module_id.rsplit('.', 1)[-1]}-runtime":
            raise ValueError("Lifecycle entrypoint_id must be derived from the declared module id")
        category_ids = [category.id for category in self.categories]
        if len(category_ids) != len(set(category_ids)):
            raise ValueError("Module category ids must be unique")
        if self.categories and "ui.navigation.register" not in self.requested_capabilities:
            raise ValueError("Modules declaring categories must request ui.navigation.register")
        requested = set(self.requested_capabilities)
        for category in self.categories:
            if not set(category.required_capabilities).issubset(requested):
                raise ValueError(f"Category {category.id!r} requires capabilities absent from the manifest")
        return self


def module_route_id(module_id: str, category_id: str) -> str:
    if not MODULE_ID_RE.fullmatch(module_id) or not CATEGORY_ID_RE.fullmatch(category_id):
        raise ValueError("Invalid module route components")
    return f"module:{module_id}:{category_id}"
