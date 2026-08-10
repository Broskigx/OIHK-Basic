"""Persistent registry, installation identity, and single-use pairing service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.config import get_settings
from app.system_link.capabilities import granted_capabilities
from app.system_link.modules.evidence_lab import EVIDENCE_LAB_ADAPTER
from app.system_link.package_verification import verify_package
from app.system_link.protocol import (
    SYSTEM_LINK_PROTOCOL_VERSION,
    ModuleManifest,
    ModuleState,
    StartupPolicy,
    canonical_json,
    module_route_id,
    require_transition,
    validate_capabilities,
)
from app.system_link.publisher_trust import PublisherTrustError, verify_publisher_trust
from app.system_link.schemas import LinkedModuleRead, ModuleCategoryRead, PairingPendingRead, PublisherIdentityRead
from app.system_link.security import (
    InstallationIdentity,
    InstallationIdentityStore,
    public_key_fingerprint,
    verify_signature,
)
from app.version import PRODUCT_VERSION

# Static host catalog entries are presentation/control adapters, not embedded product runtimes.
EVIDENCE_LAB_MODULE_ID = EVIDENCE_LAB_ADAPTER.module_id
EVIDENCE_LAB_PRODUCT_NAME = EVIDENCE_LAB_ADAPTER.product_name


class SystemLinkError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _link_key_hash(value: str) -> str:
    normalized = value.strip().upper().encode("ascii", errors="ignore")
    return hashlib.sha256(normalized).hexdigest()


def _manifest_sha256(manifest: ModuleManifest) -> str:
    return hashlib.sha256(canonical_json(manifest)).hexdigest()


def pairing_proof_payload(
    *,
    pairing_id: str,
    challenge: str,
    module_id: str,
    module_public_key: str,
    manifest_sha256: str,
) -> bytes:
    return canonical_json(
        {
            "challenge": challenge,
            "manifest_sha256": manifest_sha256,
            "module_id": module_id,
            "module_public_key": module_public_key,
            "pairing_id": pairing_id,
            "protocol_version": SYSTEM_LINK_PROTOCOL_VERSION,
        }
    )


class SystemLinkService:
    def __init__(self, session: AsyncSession, identity_store: InstallationIdentityStore | None = None) -> None:
        self.session = session
        self.identity_store = identity_store or InstallationIdentityStore()

    async def installation_identity(self) -> InstallationIdentity:
        identity = self.identity_store.load_or_create()
        row = await self.session.get(models.SystemLinkInstallation, "basic")
        if row is None:
            row = models.SystemLinkInstallation(
                id="basic",
                protocol_version=SYSTEM_LINK_PROTOCOL_VERSION,
                public_key=identity.public_key,
                fingerprint=identity.fingerprint,
                key_storage=identity.storage_kind,
            )
            self.session.add(row)
            await self.session.commit()
        elif row.public_key != identity.public_key or row.fingerprint != identity.fingerprint:
            raise SystemLinkError(
                "installation_identity_mismatch",
                "Stored System Link public identity does not match the protected private key; re-pairing is required.",
            )
        return identity

    async def begin_pairing(self, ttl_seconds: int = 300) -> tuple[models.SystemLinkPairingNonce, str, InstallationIdentity, str]:
        identity = await self.installation_identity()
        raw_key = base64.b32encode(secrets.token_bytes(16)).decode("ascii").rstrip("=")
        link_key = "OIHK-" + "-".join(raw_key[index : index + 4] for index in range(0, len(raw_key), 4))
        challenge = secrets.token_urlsafe(32)
        row = models.SystemLinkPairingNonce(
            id=models.new_id(),
            link_key_hash=_link_key_hash(link_key),
            challenge=challenge,
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )
        self.session.add(row)
        await self._event(None, "module_pair_started", {"pairing_id": row.id, "expires_in_seconds": ttl_seconds})
        await self.session.commit()
        proof = canonical_json(
            {
                "challenge": challenge,
                "installation_fingerprint": identity.fingerprint,
                "pairing_id": row.id,
                "protocol_version": SYSTEM_LINK_PROTOCOL_VERSION,
            }
        )
        return row, link_key, identity, identity.sign(proof)

    async def submit_pairing(
        self,
        *,
        pairing_id: str,
        link_key: str,
        module_public_key: str,
        manifest: ModuleManifest,
        manifest_signature: str,
        challenge_signature: str,
        package_root: str,
    ) -> models.SystemLinkPairingNonce:
        row = await self.session.get(models.SystemLinkPairingNonce, pairing_id)
        if row is None:
            raise SystemLinkError("pairing_not_found", "Pairing challenge does not exist")
        now = datetime.now(UTC)
        if row.used_at is not None:
            raise SystemLinkError("pairing_replayed", "OIHK Link Key has already been used")
        if _utc(row.expires_at) <= now:
            raise SystemLinkError("pairing_expired", "OIHK Link Key has expired")
        if not hmac.compare_digest(row.link_key_hash, _link_key_hash(link_key)):
            raise SystemLinkError("pairing_key_invalid", "OIHK Link Key is invalid")
        if PRODUCT_VERSION not in manifest.compatible_basic_versions:
            raise SystemLinkError("basic_version_incompatible", "Module manifest does not support this Basic version")
        try:
            EVIDENCE_LAB_ADAPTER.validate_identity(
                module_id=manifest.module_id,
                product_name=manifest.name,
                entrypoint_id=manifest.lifecycle.entrypoint_id,
            )
        except ValueError as exc:
            raise SystemLinkError("module_not_first_party", str(exc)) from exc
        try:
            fingerprint = public_key_fingerprint(module_public_key)
        except Exception as exc:
            raise SystemLinkError("module_identity_invalid", "Module public identity is malformed") from exc
        manifest_hash = _manifest_sha256(manifest)
        try:
            verify_signature(module_public_key, canonical_json(manifest), manifest_signature)
            verify_signature(
                module_public_key,
                pairing_proof_payload(
                    pairing_id=row.id,
                    challenge=row.challenge,
                    module_id=manifest.module_id,
                    module_public_key=module_public_key,
                    manifest_sha256=manifest_hash,
                ),
                challenge_signature,
            )
        except (InvalidSignature, ValueError) as exc:
            await self._event(manifest.module_id, "module_pair_failed", {"reason": "signature_invalid"})
            await self.session.commit()
            raise SystemLinkError("pairing_signature_invalid", "Module pairing proof or manifest signature is invalid") from exc
        try:
            verify_package(package_root, manifest.package_sha256)
            verified_root = str(Path(package_root).resolve(strict=True))
            if manifest.frontend_entrypoint:
                declared_entrypoint = Path(verified_root).joinpath(*manifest.frontend_entrypoint.split("/"))
                if declared_entrypoint.is_symlink():
                    raise ValueError("Module frontend entrypoint may not be a symlink")
                entrypoint = declared_entrypoint.resolve(strict=True)
                entrypoint.relative_to(Path(verified_root))
                if not entrypoint.is_file() or entrypoint.is_symlink():
                    raise ValueError("Module frontend entrypoint is not a regular package file")
        except (OSError, ValueError) as exc:
            raise SystemLinkError("package_verification_failed", str(exc)) from exc
        try:
            publisher = verify_publisher_trust(
                verified_root,
                manifest,
                allow_development=get_settings().system_link_allow_development_publishers,
            )
        except PublisherTrustError as exc:
            raise SystemLinkError("publisher_untrusted", str(exc)) from exc
        # Claim the Link Key atomically so two concurrent pairings with the same
        # key can never both succeed. All cryptographic and package validation
        # happens BEFORE the claim, so presenting a correct key together with an
        # invalid signature can never burn the key (no trivially induced DoS).
        try:
            claimed = await self.session.execute(
                update(models.SystemLinkPairingNonce)
                .where(
                    models.SystemLinkPairingNonce.id == pairing_id,
                    models.SystemLinkPairingNonce.used_at.is_(None),
                    models.SystemLinkPairingNonce.expires_at > now,
                    models.SystemLinkPairingNonce.link_key_hash == row.link_key_hash,
                )
                .values(used_at=now)
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:
                # A concurrent pairing already claimed this single-use credential.
                raise SystemLinkError(
                    "pairing_replayed",
                    "OIHK Link Key was already consumed or expired before the pairing proof could be claimed",
                )
            row.used_at = now
            row.pending_module = {
                "module_public_key": module_public_key,
                "module_fingerprint": fingerprint,
                "manifest": manifest.model_dump(mode="json"),
                "manifest_sha256": manifest_hash,
                "manifest_signature": manifest_signature,
                "package_root": verified_root,
                "publisher_key_id": publisher["key_id"],
                "publisher_channel": publisher["channel"],
            }
            await self._event(
                manifest.module_id,
                "module_pair_proof_verified",
                {"pairing_id": row.id, "module_fingerprint": fingerprint, "manifest_sha256": manifest_hash},
            )
            await self.session.commit()
        except BaseException:
            # Never persist a claimed-but-incomplete pairing: roll the whole
            # transaction back so the single-use key is not burned and the
            # legitimate module can retry after the failure is resolved.
            await self.session.rollback()
            raise
        return row

    async def approve_pairing(self, pairing_id: str, grants: list[str]) -> models.SystemLinkModule:
        row = await self.session.get(models.SystemLinkPairingNonce, pairing_id)
        if row is None or row.used_at is None or not row.pending_module:
            raise SystemLinkError("pairing_not_ready", "No verified module pairing is awaiting approval")
        if row.approved_at is not None:
            raise SystemLinkError("pairing_already_approved", "Pairing was already approved")
        pending = row.pending_module
        manifest = ModuleManifest.model_validate(pending["manifest"])
        requested = set(manifest.requested_capabilities)
        normalized_grants = validate_capabilities(grants)
        if not set(normalized_grants).issubset(requested):
            raise SystemLinkError("capability_not_requested", "A grant may only contain capabilities requested by the manifest")
        existing = await self.session.get(models.SystemLinkModule, manifest.module_id)
        if existing is not None and ModuleState(existing.state) != ModuleState.REVOKED:
            raise SystemLinkError("module_id_collision", "A linked module already owns this module id")
        try:
            if existing is None:
                module = models.SystemLinkModule(module_id=manifest.module_id)
                self.session.add(module)
            else:
                module = existing
                await self.session.execute(
                    delete(models.SystemLinkCapabilityGrant).where(
                        models.SystemLinkCapabilityGrant.module_id == manifest.module_id
                    )
                )
            module.product_name = manifest.name
            module.module_version = manifest.version
            module.protocol_version = manifest.protocol_version
            module.manifest_schema_version = manifest.schema_version
            module.module_public_key = pending["module_public_key"]
            module.module_fingerprint = pending["module_fingerprint"]
            module.manifest = manifest.model_dump(mode="json")
            module.manifest_sha256 = pending["manifest_sha256"]
            module.manifest_signature = pending["manifest_signature"]
            module.publisher_key_id = pending.get("publisher_key_id", "")
            module.publisher_channel = pending.get("publisher_channel", "")
            module.package_root = pending["package_root"]
            module.package_sha256 = manifest.package_sha256
            module.lifecycle = manifest.lifecycle.model_dump(mode="json")
            module.state = ModuleState.LINKED_OFF.value
            module.enabled = True
            module.startup_policy = StartupPolicy.MANUAL.value
            module.last_error_code = ""
            module.last_error_detail = ""
            module.revoked_at = None
            module.paired_at = datetime.now(UTC)

            # Module and grant models intentionally have no ORM relationship.
            # Materialize the parent row before adding FK-dependent grants while
            # keeping both writes inside this one uncommitted transaction.
            await self.session.flush([module])
            for capability in normalized_grants:
                self.session.add(
                    models.SystemLinkCapabilityGrant(
                        module_id=manifest.module_id,
                        capability=capability,
                        manifest_sha256=module.manifest_sha256,
                    )
                )
            row.approved_at = datetime.now(UTC)
            await self._event(
                manifest.module_id,
                "module_pair_completed",
                {"manifest_sha256": module.manifest_sha256, "granted_capabilities": normalized_grants},
            )
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise
        await self.session.refresh(module)
        return module

    async def pending_pairings(self) -> list[PairingPendingRead]:
        now = datetime.now(UTC)
        rows = list(
            (
                await self.session.execute(
                    select(models.SystemLinkPairingNonce).where(
                        models.SystemLinkPairingNonce.used_at.is_not(None),
                        models.SystemLinkPairingNonce.approved_at.is_(None),
                    )
                )
            ).scalars()
        )
        pending: list[PairingPendingRead] = []
        for row in rows:
            if _utc(row.expires_at) <= now or not row.pending_module:
                continue
            manifest = ModuleManifest.model_validate(row.pending_module["manifest"])
            pending.append(
                PairingPendingRead(
                    pairing_id=row.id,
                    module_id=manifest.module_id,
                    product_name=manifest.name,
                    module_version=manifest.version,
                    module_fingerprint=row.pending_module["module_fingerprint"],
                    requested_capabilities=manifest.requested_capabilities,
                    categories=[category.model_dump(mode="json") for category in manifest.categories],
                    expires_at=row.expires_at,
                )
            )
        return pending

    async def transition(
        self,
        module: models.SystemLinkModule,
        target: ModuleState,
        *,
        error_code: str = "",
        error_detail: str = "",
        event: str | None = None,
    ) -> None:
        current = ModuleState(module.state)
        require_transition(current, target)
        module.state = target.value
        module.last_error_code = error_code
        module.last_error_detail = error_detail[:500]
        module.updated_at = datetime.now(UTC)
        if event:
            await self._event(module.module_id, event, {"from": current.value, "to": target.value, "error_code": error_code})
        await self.session.commit()

    async def module_view(self, module: models.SystemLinkModule) -> LinkedModuleRead:
        manifest = ModuleManifest.model_validate(module.manifest)
        grants = await granted_capabilities(self.session, module.module_id)
        state = ModuleState(module.state)
        active = state in {ModuleState.READY, ModuleState.BUSY} and module.enabled and module.revoked_at is None
        categories = [
            ModuleCategoryRead(
                id=category.id,
                route_id=module_route_id(module.module_id, category.id),
                label=category.label,
                icon=category.icon,
                case_scoped=category.case_scoped,
                order=category.order,
                enabled=active and set(category.required_capabilities).issubset(grants),
            )
            for category in manifest.categories
        ]
        return LinkedModuleRead(
            module_id=module.module_id,
            product_name=module.product_name,
            module_version=module.module_version,
            protocol_version=module.protocol_version,
            state=state,
            installed=True,
            linked=state != ModuleState.REVOKED,
            enabled=module.enabled,
            module_fingerprint=module.module_fingerprint,
            package_sha256=module.package_sha256,
            publisher=PublisherIdentityRead(key_id=module.publisher_key_id, channel=module.publisher_channel),
            frontend_entrypoint=manifest.frontend_entrypoint,
            granted_capabilities=sorted(grants),
            requested_capabilities=manifest.requested_capabilities,
            categories=categories,
            startup_policy=StartupPolicy(module.startup_policy),
            last_handshake_at=module.last_handshake_at,
            last_health_at=module.last_health_at,
            last_error_code=module.last_error_code,
            last_error_detail=module.last_error_detail,
        )

    async def list_modules(self) -> list[LinkedModuleRead]:
        rows = list((await self.session.execute(select(models.SystemLinkModule))).scalars())
        modules = [await self.module_view(row) for row in rows]
        if not any(module.module_id == EVIDENCE_LAB_MODULE_ID for module in modules):
            modules.append(
                LinkedModuleRead(
                    module_id=EVIDENCE_LAB_MODULE_ID,
                    product_name=EVIDENCE_LAB_PRODUCT_NAME,
                    module_version="",
                    protocol_version=SYSTEM_LINK_PROTOCOL_VERSION,
                    state=ModuleState.NOT_INSTALLED,
                    installed=False,
                    linked=False,
                    enabled=False,
                    module_fingerprint="",
                    package_sha256="",
                    publisher=PublisherIdentityRead(key_id="", channel=""),
                    frontend_entrypoint=None,
                    granted_capabilities=[],
                    requested_capabilities=[],
                    categories=[],
                    startup_policy=StartupPolicy.MANUAL,
                    last_handshake_at=None,
                    last_health_at=None,
                    last_error_code="",
                    last_error_detail="",
                )
            )
        return sorted(modules, key=lambda module: module.product_name.lower())

    async def disable(self, module: models.SystemLinkModule) -> None:
        if ModuleState(module.state) in {ModuleState.READY, ModuleState.BUSY, ModuleState.STARTING, ModuleState.AUTHENTICATING}:
            raise SystemLinkError("module_running", "Stop the module before disabling it")
        await self.transition(module, ModuleState.DISABLED, event="module_disabled")
        module.enabled = False
        await self.session.commit()

    async def enable(self, module: models.SystemLinkModule) -> None:
        if ModuleState(module.state) != ModuleState.DISABLED:
            raise SystemLinkError("module_not_disabled", "Only a disabled module can be enabled")
        module.enabled = True
        await self.transition(module, ModuleState.LINKED_OFF, event="module_enabled")

    async def revoke(self, module: models.SystemLinkModule) -> None:
        if ModuleState(module.state) in {ModuleState.READY, ModuleState.BUSY, ModuleState.STARTING, ModuleState.AUTHENTICATING}:
            raise SystemLinkError("module_running", "Stop the module before revoking it")
        await self.transition(module, ModuleState.REVOKED, event="module_revoked")
        now = datetime.now(UTC)
        module.enabled = False
        module.revoked_at = now
        grants = list(
            (
                await self.session.execute(
                    select(models.SystemLinkCapabilityGrant).where(
                        models.SystemLinkCapabilityGrant.module_id == module.module_id,
                        models.SystemLinkCapabilityGrant.revoked_at.is_(None),
                    )
                )
            ).scalars()
        )
        for grant in grants:
            grant.revoked_at = now
        await self.session.commit()

    async def reconcile_startup_states(self) -> list[models.SystemLinkModule]:
        """Classify runtime states after a Basic restart.

        In-flight transitions (STARTING/AUTHENTICATING/STOPPING) can never be
        trusted again and are forced to ERROR. Modules that reached READY/BUSY
        are returned so the supervisor can attempt a *verified* re-adoption
        (pinned identity + signed challenge + expected executable hash); they
        are never adopted merely because a process listens on the loopback port.
        """
        in_flight = [
            ModuleState.STARTING.value,
            ModuleState.AUTHENTICATING.value,
            ModuleState.STOPPING.value,
        ]
        survivors = [ModuleState.READY.value, ModuleState.BUSY.value]
        rows = list(
            (
                await self.session.execute(
                    select(models.SystemLinkModule).where(
                        models.SystemLinkModule.state.in_(in_flight + survivors)
                    )
                )
            ).scalars()
        )
        needs_reconciliation: list[models.SystemLinkModule] = []
        for module in rows:
            if ModuleState(module.state) in {ModuleState.READY, ModuleState.BUSY}:
                needs_reconciliation.append(module)
                continue
            module.state = ModuleState.ERROR.value
            module.last_error_code = "host_restart_requires_reauthentication"
            module.last_error_detail = "Runtime state must be authenticated again after Basic restarts."
            await self._event(module.module_id, "module_runtime_reconciliation_required", {})
        if rows:
            await self.session.commit()
        return needs_reconciliation

    async def _event(self, module_id: str | None, action: str, payload: dict) -> None:
        self.session.add(models.SystemLinkEvent(module_id=module_id, action=action, payload=payload))
