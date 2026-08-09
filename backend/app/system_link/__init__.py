"""OIHK System Link v1 host/control-plane foundation."""

from app.system_link.protocol import (
    MANIFEST_SCHEMA_VERSION,
    SYSTEM_LINK_PROTOCOL_VERSION,
    ModuleState,
)

__all__ = ["MANIFEST_SCHEMA_VERSION", "SYSTEM_LINK_PROTOCOL_VERSION", "ModuleState"]
