"""Central least-privilege grant enforcement for linked modules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.system_link.protocol import KNOWN_CAPABILITIES, ModuleState


class CapabilityDenied(PermissionError):
    pass


async def granted_capabilities(session: AsyncSession, module_id: str) -> set[str]:
    result = await session.execute(
        select(models.SystemLinkCapabilityGrant.capability).where(
            models.SystemLinkCapabilityGrant.module_id == module_id,
            models.SystemLinkCapabilityGrant.revoked_at.is_(None),
        )
    )
    return {str(value) for value in result.scalars()}


async def require_capability(
    session: AsyncSession,
    module_id: str,
    capability: str,
    *,
    require_ready: bool = True,
) -> models.SystemLinkModule:
    if capability not in KNOWN_CAPABILITIES:
        raise CapabilityDenied("Unknown capabilities are denied by default")
    module = await session.get(models.SystemLinkModule, module_id)
    if module is None or module.revoked_at is not None or not module.enabled:
        raise CapabilityDenied("Module is not linked and enabled")
    if require_ready and ModuleState(module.state) not in {ModuleState.READY, ModuleState.BUSY}:
        raise CapabilityDenied("Module capabilities are inactive until authenticated READY state")
    grants = await granted_capabilities(session, module_id)
    if capability not in grants:
        raise CapabilityDenied(f"Capability {capability!r} was not granted")
    return module
