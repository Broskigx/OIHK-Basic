"""Narrow verified-process lifecycle supervisor for first-party System Link modules."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from datetime import UTC, datetime

import httpx
from cryptography.exceptions import InvalidSignature
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import SessionLocal
from app.system_link.package_verification import verify_executable, verify_package
from app.system_link.protocol import ModuleManifest, ModuleState, canonical_json
from app.system_link.security import InstallationIdentity, InstallationIdentityStore, verify_signature
from app.system_link.service import SystemLinkError, SystemLinkService
from app.version import PRODUCT_VERSION


class RuntimeAuthenticationError(RuntimeError):
    pass


class RuntimeHealthError(RuntimeError):
    pass


class AuthenticatedRuntimeClient:
    """Mutually authenticated loopback client for a paired module runtime."""

    def __init__(
        self,
        module: models.SystemLinkModule,
        identity: InstallationIdentity,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.module = module
        self.identity = identity
        self.base_url = str(module.lifecycle["base_url"]).rstrip("/")
        self.transport = transport

    async def _request(self, method: str, path: str, *, timeout: float) -> dict:
        nonce = os.urandom(24).hex()
        timestamp = int(time.time())
        proof = {
            "method": method.upper(),
            "module_id": self.module.module_id,
            "nonce": nonce,
            "path": path,
            "timestamp": timestamp,
        }
        headers = {
            "X-OIHK-Basic-Identity": self.identity.fingerprint,
            "X-OIHK-Nonce": nonce,
            "X-OIHK-Timestamp": str(timestamp),
            "X-OIHK-Signature": self.identity.sign(canonical_json(proof)),
            "X-OIHK-System-Link-Version": self.module.protocol_version,
        }
        async with httpx.AsyncClient(transport=self.transport, timeout=timeout) as client:
            response = await client.request(method, f"{self.base_url}{path}", headers=headers, json=proof)
            response.raise_for_status()
            payload = response.json()
        signature = payload.pop("signature", "") if isinstance(payload, dict) else ""
        if (
            not isinstance(payload, dict)
            or payload.get("module_id") != self.module.module_id
            or payload.get("protocol_version") != self.module.protocol_version
            or payload.get("nonce") != nonce
            or abs(int(payload.get("timestamp", 0)) - int(time.time())) > 30
        ):
            raise RuntimeAuthenticationError("Runtime response identity, protocol, nonce, or timestamp is invalid")
        try:
            verify_signature(self.module.module_public_key, canonical_json(payload), signature)
        except (InvalidSignature, ValueError) as exc:
            raise RuntimeAuthenticationError("Runtime response signature is invalid") from exc
        return payload

    async def handshake(self, timeout: float) -> None:
        payload = await self._request("POST", "/system-link/v1/handshake", timeout=timeout)
        if payload.get("authenticated") is not True:
            raise RuntimeAuthenticationError("Runtime did not confirm mutual authentication")

    async def health(self, timeout: float) -> str:
        payload = await self._request("GET", "/system-link/v1/health", timeout=timeout)
        if payload.get("healthy") is not True or payload.get("status") not in {"READY", "BUSY"}:
            raise RuntimeHealthError("Authenticated runtime health check did not report READY/BUSY")
        return str(payload["status"])

    async def shutdown(self, timeout: float) -> None:
        payload = await self._request("POST", "/system-link/v1/shutdown", timeout=timeout)
        if payload.get("shutting_down") is not True:
            raise RuntimeHealthError("Runtime did not accept graceful shutdown")


class RuntimeSupervisor:
    """Owns only exact child handles created from verified registered descriptors."""

    def __init__(self, identity_store: InstallationIdentityStore | None = None) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._cancellations: dict[str, asyncio.Event] = {}
        self._watchers: dict[str, asyncio.Task[None]] = {}
        self._identity_store = identity_store

    def _service(self, session: AsyncSession) -> SystemLinkService:
        return SystemLinkService(session, self._identity_store)

    def _lock(self, module_id: str) -> asyncio.Lock:
        return self._locks.setdefault(module_id, asyncio.Lock())

    async def start(self, session: AsyncSession, module: models.SystemLinkModule) -> ModuleState:
        async with self._lock(module.module_id):
            service = self._service(session)
            state = ModuleState(module.state)
            if state not in {ModuleState.LINKED_OFF, ModuleState.ERROR}:
                raise SystemLinkError("invalid_lifecycle_state", f"Cannot start a module in {state.value}")
            if not module.enabled or module.revoked_at is not None:
                raise SystemLinkError("module_not_startable", "Disabled or revoked modules cannot be started")
            manifest = ModuleManifest.model_validate(module.manifest)
            if PRODUCT_VERSION not in manifest.compatible_basic_versions:
                await service.transition(
                    module,
                    ModuleState.INCOMPATIBLE,
                    error_code="basic_version_incompatible",
                    error_detail="The linked module does not support this Basic version.",
                    event="module_runtime_start_failed",
                )
                return ModuleState.INCOMPATIBLE
            cancellation = asyncio.Event()
            self._cancellations[module.module_id] = cancellation
            await service.transition(module, ModuleState.STARTING, event="module_runtime_start_requested")
            process: asyncio.subprocess.Process | None = None
            try:
                verify_signature(module.module_public_key, canonical_json(manifest), module.manifest_signature)
                verify_package(module.package_root, module.package_sha256)
                executable = verify_executable(manifest.lifecycle)
                if cancellation.is_set():
                    raise asyncio.CancelledError
                creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                process = await asyncio.create_subprocess_exec(
                    str(executable),
                    cwd=manifest.lifecycle.install_root,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    creationflags=creation_flags,
                )
                self._processes[module.module_id] = process
                self._watchers[module.module_id] = asyncio.create_task(
                    self._watch_process(module.module_id, process)
                )
                await service.transition(module, ModuleState.AUTHENTICATING, event="module_runtime_started")
                identity = await service.installation_identity()
                client = AuthenticatedRuntimeClient(module, identity)
                deadline = time.monotonic() + manifest.lifecycle.startup_timeout_seconds
                authenticated = False
                last_error: Exception | None = None
                while time.monotonic() < deadline:
                    if cancellation.is_set():
                        raise asyncio.CancelledError
                    if process.returncode is not None:
                        raise RuntimeError("Verified runtime exited before authentication")
                    remaining = max(0.2, min(2.0, deadline - time.monotonic()))
                    try:
                        await client.handshake(remaining)
                        authenticated = True
                        await client.health(remaining)
                        module.last_handshake_at = datetime.now(UTC)
                        module.last_health_at = datetime.now(UTC)
                        # A fully healthy authenticated start clears the consecutive-failure counter.
                        module.crash_count = 0
                        await service.transition(module, ModuleState.READY, event="module_runtime_ready")
                        return ModuleState(module.state)
                    except (httpx.HTTPError, RuntimeAuthenticationError, RuntimeHealthError) as exc:
                        last_error = exc
                        await asyncio.sleep(0.25)
                code = "runtime_health_failed" if authenticated else "runtime_authentication_failed"
                raise SystemLinkError(code, str(last_error or "Runtime startup timed out"))
            except asyncio.CancelledError:
                await self._terminate_exact(module.module_id, process)
                await self._record_failure(service, module, "runtime_start_cancelled", "Runtime startup was cancelled")
                return ModuleState(module.state)
            except Exception as exc:
                await self._terminate_exact(module.module_id, process)
                code = exc.code if isinstance(exc, SystemLinkError) else "runtime_start_failed"
                await self._record_failure(service, module, code, str(exc))
                return ModuleState(module.state)
            finally:
                self._cancellations.pop(module.module_id, None)

    async def stop(self, session: AsyncSession, module: models.SystemLinkModule) -> ModuleState:
        async with self._lock(module.module_id):
            state = ModuleState(module.state)
            if state == ModuleState.LINKED_OFF:
                return state
            if state not in {
                ModuleState.READY,
                ModuleState.BUSY,
                ModuleState.ERROR,
                ModuleState.STARTING,
                ModuleState.AUTHENTICATING,
            }:
                raise SystemLinkError("invalid_lifecycle_state", f"Cannot stop a module in {state.value}")
            service = self._service(session)
            await service.transition(module, ModuleState.STOPPING, event="module_runtime_stop_requested")
            descriptor = ModuleManifest.model_validate(module.manifest).lifecycle
            process = self._processes.get(module.module_id)
            graceful_error: Exception | None = None
            try:
                identity = await service.installation_identity()
                await AuthenticatedRuntimeClient(module, identity).shutdown(descriptor.stop_timeout_seconds)
            except Exception as exc:
                graceful_error = exc
            confirmed = False
            if process is not None:
                try:
                    await asyncio.wait_for(process.wait(), timeout=descriptor.stop_timeout_seconds)
                    confirmed = True
                except TimeoutError:
                    await self._terminate_exact(module.module_id, process)
                    confirmed = process.returncode is not None
            elif graceful_error is None:
                confirmed = await self._wait_until_offline(module, descriptor.stop_timeout_seconds)
            if not confirmed:
                await service.transition(
                    module,
                    ModuleState.ERROR,
                    error_code="runtime_stop_failed",
                    error_detail=str(graceful_error or "Runtime offline state could not be confirmed"),
                    event="module_runtime_stop_failed",
                )
                return ModuleState.ERROR
            await service.transition(module, ModuleState.LINKED_OFF, event="module_runtime_stopped")
            return ModuleState.LINKED_OFF

    async def restart(self, session: AsyncSession, module: models.SystemLinkModule) -> ModuleState:
        state = await self.stop(session, module)
        if state != ModuleState.LINKED_OFF:
            return state
        module = await session.get(models.SystemLinkModule, module.module_id)
        if module is None:
            raise SystemLinkError("module_not_found", "Linked module disappeared during restart")
        result = await self.start(session, module)
        service = self._service(session)
        await service._event(module.module_id, "module_runtime_restarted", {"state": result.value})
        await session.commit()
        return result

    def cancel(self, module_id: str) -> bool:
        event = self._cancellations.get(module_id)
        if event is None:
            return False
        event.set()
        return True

    async def reconcile(self, session: AsyncSession, module: models.SystemLinkModule) -> None:
        if ModuleState(module.state) not in {ModuleState.READY, ModuleState.BUSY}:
            return
        service = self._service(session)
        process = self._processes.get(module.module_id)
        try:
            if process is not None and process.returncode is not None:
                raise RuntimeHealthError("Managed runtime process exited unexpectedly")
            identity = await service.installation_identity()
            status = await AuthenticatedRuntimeClient(module, identity).health(2.0)
            module.last_health_at = datetime.now(UTC)
            # A verified healthy runtime breaks any consecutive-failure streak.
            module.crash_count = 0
            target = ModuleState.READY if status == "READY" else ModuleState.BUSY
            if target != ModuleState(module.state):
                await service.transition(module, target, event="module_runtime_status_changed")
            else:
                await session.commit()
        except Exception as exc:
            module.crash_count += 1
            await service.transition(
                module,
                ModuleState.ERROR,
                error_code="runtime_health_failed",
                error_detail=str(exc),
                event="module_runtime_health_failed",
            )
            if module.crash_count >= 3:
                await service.transition(
                    module,
                    ModuleState.QUARANTINED,
                    error_code="runtime_crash_loop",
                    error_detail="Repeated runtime health failures require explicit user recovery.",
                    event="module_runtime_quarantined",
                )

    async def reconcile_existing_runtime(
        self,
        session: AsyncSession,
        module: models.SystemLinkModule,
    ) -> ModuleState:
        """Safely re-adopt a runtime that survived a Basic restart.

        A process is never adopted just because something listens on the pinned
        loopback URL. Recovery requires every check below to pass:

        * pinned module identity (manifest signature under the stored key);
        * package integrity (signed package SHA-256);
        * expected executable identity (signed lifecycle hash on disk);
        * protocol compatibility; and
        * a signed mutually-authenticated handshake + health against the exact
          pinned base URL (never a port scan).

        Any failure is fail-closed: the module is left in ERROR (or
        QUARANTINED once the consecutive-failure limit is reached).
        """
        service = self._service(session)
        state = ModuleState(module.state)
        if state not in {ModuleState.READY, ModuleState.BUSY}:
            return state
        try:
            manifest = ModuleManifest.model_validate(module.manifest)
            verify_signature(module.module_public_key, canonical_json(manifest), module.manifest_signature)
            verify_package(module.package_root, module.package_sha256)
            verify_executable(manifest.lifecycle)
            if PRODUCT_VERSION not in manifest.compatible_basic_versions:
                raise SystemLinkError(
                    "basic_version_incompatible", "The linked module does not support this Basic version."
                )
        except (InvalidSignature, ValueError, OSError, SystemLinkError) as exc:
            code = getattr(exc, "code", "runtime_reconciliation_failed")
            await service.transition(
                module,
                ModuleState.ERROR,
                error_code=code,
                error_detail=f"Existing runtime failed re-verification: {exc}",
                event="module_runtime_reconciliation_failed",
            )
            return ModuleState.ERROR
        identity = await service.installation_identity()
        try:
            client = AuthenticatedRuntimeClient(module, identity)
            await client.handshake(2.0)
            status = await client.health(2.0)
        except (httpx.HTTPError, RuntimeAuthenticationError, RuntimeHealthError) as exc:
            # Do not adopt the endpoint: its process identity could not be
            # proven cryptographically (or the pinned URL is not responding).
            module.crash_count += 1
            await service.transition(
                module,
                ModuleState.ERROR,
                error_code="runtime_reconciliation_failed",
                error_detail=f"Existing runtime failed signed authentication: {exc}",
                event="module_runtime_reconciliation_failed",
            )
            if module.crash_count >= 3:
                await service.transition(
                    module,
                    ModuleState.QUARANTINED,
                    error_code="runtime_crash_loop",
                    error_detail="Repeated reconciliation failures require explicit user recovery.",
                    event="module_runtime_quarantined",
                )
            # The returned value must always represent the final persisted state
            # (ERROR, or QUARANTINED once the consecutive-failure limit is hit).
            return ModuleState(module.state)
        # Fully verified: the surviving runtime owns the pinned module identity.
        module.crash_count = 0
        module.last_handshake_at = datetime.now(UTC)
        module.last_health_at = datetime.now(UTC)
        target = ModuleState.READY if status == "READY" else ModuleState.BUSY
        if target != state:
            await service.transition(module, target, event="module_runtime_reconciled")
        else:
            await session.commit()
        return ModuleState(module.state)

    async def _record_failure(
        self,
        service: SystemLinkService,
        module: models.SystemLinkModule,
        code: str,
        detail: str,
    ) -> None:
        module.crash_count += 1
        await service.transition(
            module,
            ModuleState.ERROR,
            error_code=code,
            error_detail=detail,
            event="module_runtime_start_failed",
        )
        if module.crash_count >= 3:
            await service.transition(
                module,
                ModuleState.QUARANTINED,
                error_code="runtime_crash_loop",
                error_detail="Three consecutive startup failures require explicit user recovery.",
                event="module_runtime_quarantined",
            )

    async def _terminate_exact(
        self,
        module_id: str,
        process: asyncio.subprocess.Process | None,
    ) -> None:
        child = process or self._processes.get(module_id)
        if child is None:
            return
        if self._processes.get(module_id) is child:
            self._processes.pop(module_id, None)
        if child.returncode is None:
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), timeout=3)
            except TimeoutError:
                child.kill()
                await child.wait()

    async def _wait_until_offline(self, module: models.SystemLinkModule, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                async with httpx.AsyncClient(timeout=0.5) as client:
                    await client.get(f"{str(module.lifecycle['base_url']).rstrip('/')}/system-link/v1/health")
            except httpx.HTTPError:
                return True
            await asyncio.sleep(0.2)
        return False

    async def _watch_process(self, module_id: str, process: asyncio.subprocess.Process) -> None:
        try:
            await process.wait()
            await asyncio.sleep(0)
            if self._processes.get(module_id) is not process:
                return
            self._processes.pop(module_id, None)
            async with SessionLocal() as session:
                module = await session.get(models.SystemLinkModule, module_id)
                if module is None or ModuleState(module.state) not in {ModuleState.READY, ModuleState.BUSY}:
                    return
                service = self._service(session)
                module.crash_count += 1
                await service.transition(
                    module,
                    ModuleState.ERROR,
                    error_code="runtime_crashed",
                    error_detail="The verified module runtime exited unexpectedly.",
                    event="module_runtime_crashed",
                )
                if module.crash_count >= 3:
                    await service.transition(
                        module,
                        ModuleState.QUARANTINED,
                        error_code="runtime_crash_loop",
                        error_detail="Repeated runtime crashes require explicit user recovery.",
                        event="module_runtime_quarantined",
                    )
        finally:
            if self._watchers.get(module_id) is asyncio.current_task():
                self._watchers.pop(module_id, None)


runtime_supervisor = RuntimeSupervisor()
