"""HTTP DTOs for the Basic-side OIHK System Link v1 control plane."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.system_link.protocol import ModuleManifest, ModuleState, StartupPolicy


class PairingStartRead(BaseModel):
    pairing_id: str
    link_key: str
    expires_at: datetime
    challenge: str
    protocol_version: str
    installation_public_key: str
    installation_fingerprint: str
    basic_signature: str


class PairingCompleteWrite(BaseModel):
    pairing_id: str
    link_key: str = Field(min_length=20, max_length=100)
    module_public_key: str = Field(min_length=40, max_length=120)
    manifest: ModuleManifest
    manifest_signature: str = Field(min_length=40, max_length=160)
    challenge_signature: str = Field(min_length=40, max_length=160)
    package_root: str = Field(min_length=1, max_length=2048)


class PublisherIdentityRead(BaseModel):
    key_id: str
    channel: str


class PairingPendingRead(BaseModel):
    pairing_id: str
    module_id: str
    product_name: str
    module_version: str
    module_fingerprint: str
    requested_capabilities: list[str]
    categories: list[dict]
    expires_at: datetime


class PairingApproveWrite(BaseModel):
    granted_capabilities: list[str] = Field(default_factory=list, max_length=50)


class ModuleCategoryRead(BaseModel):
    id: str
    route_id: str
    label: str
    icon: str
    case_scoped: bool
    order: int
    enabled: bool


class LinkedModuleRead(BaseModel):
    module_id: str
    product_name: str
    module_version: str
    protocol_version: str
    state: ModuleState
    installed: bool
    linked: bool
    enabled: bool
    module_fingerprint: str
    package_sha256: str
    publisher: PublisherIdentityRead
    frontend_entrypoint: str | None = None
    granted_capabilities: list[str]
    requested_capabilities: list[str]
    categories: list[ModuleCategoryRead]
    startup_policy: StartupPolicy
    last_handshake_at: datetime | None
    last_health_at: datetime | None
    last_error_code: str
    last_error_detail: str


class SystemLinkStatusRead(BaseModel):
    protocol_version: str
    installation_public_key: str
    installation_fingerprint: str
    key_storage: str
    modules: list[LinkedModuleRead]


class LifecycleResultRead(BaseModel):
    module_id: str
    state: ModuleState
    action: str
    detail: str = ""


class ModuleEventRead(BaseModel):
    id: int
    module_id: str | None
    action: str
    payload: dict
    created_at: datetime
