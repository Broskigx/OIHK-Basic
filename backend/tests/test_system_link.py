from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import ValidationError
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.database import Base
from app.database_migrations import run_migrations
from app.system_link import lifecycle as lifecycle_module
from app.system_link.capabilities import CapabilityDenied, require_capability
from app.system_link.lifecycle import (
    AuthenticatedRuntimeClient,
    RuntimeAuthenticationError,
    RuntimeHealthError,
    RuntimeSupervisor,
)
from app.system_link.module_auth import authenticate_module_request, module_request_payload
from app.system_link.package_verification import calculate_package_sha256, verify_executable, verify_package
from app.system_link.protocol import (
    ModuleLifecycleDescriptor,
    ModuleManifest,
    ModuleState,
    canonical_json,
    require_transition,
)
from app.system_link.security import InstallationIdentityStore, b64encode
from app.system_link.service import SystemLinkError, SystemLinkService, pairing_proof_payload
from app.version import PRODUCT_VERSION


@pytest_asyncio.fixture
async def system_link_session(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'system-link.db').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def migrated_system_link_session(tmp_path: Path):
    """Mirror Basic startup with its real migrations and SQLite FK enforcement."""
    database = tmp_path / "system-link-migrated.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        assert await run_migrations(connection) == 8
        enabled = await connection.exec_driver_sql("PRAGMA foreign_keys")
        assert enabled.scalar_one() == 1
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _write_publisher_metadata(
    package_root: Path,
    *,
    module_id: str,
    version: str,
    channel: str = "development",
    key: Ed25519PrivateKey | None = None,
) -> Ed25519PrivateKey:
    """Write a signed metadata/publisher.json mirroring the Evidence Lab v1 contract."""
    from app.system_link.security import b64decode

    key = key or Ed25519PrivateKey.generate()
    metadata_dir = package_root / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    content_hash = calculate_package_sha256(package_root, extra_ignored=frozenset({"metadata/publisher.json"}))
    publisher_public_key = _public_key(key)
    payload = {
        "algorithm": "Ed25519",
        "channel": channel,
        "content_sha256": content_hash,
        "module_id": module_id,
        "publisher": "OIHK",
        "publisher_fingerprint": hashlib.sha256(b64decode(publisher_public_key)).hexdigest(),
        "publisher_public_key": publisher_public_key,
        "version": version,
    }
    signature = b64encode(key.sign(canonical_json(payload)))
    (metadata_dir / "publisher.json").write_text(
        json.dumps({**payload, "signature": signature}, sort_keys=True) + "\n", encoding="utf-8"
    )
    return key


def _module_fixture(tmp_path: Path) -> tuple[ModuleManifest, Ed25519PrivateKey, Path]:
    package_root = tmp_path / "module-package"
    package_root.mkdir()
    (package_root / "ui").mkdir()
    (package_root / "ui" / "index.js").write_text("export const module = 'evidence-lab';", encoding="utf-8")
    # The publisher-signed metadata must exist before the manifest is computed
    # so manifest.package_sha256 and the publisher content hash stay consistent
    # with the Evidence Lab build pipeline.
    _write_publisher_metadata(package_root, module_id="oihk.evidence-lab", version="0.1.0")
    install_root = tmp_path / "evidence-lab"
    install_root.mkdir()
    executable_name = "evidence-lab-runtime.exe" if os.name == "nt" else "evidence-lab-runtime"
    executable = install_root / executable_name
    executable.write_bytes(b"verified runtime fixture")
    manifest = ModuleManifest(
        module_id="oihk.evidence-lab",
        name="OIHK Evidence Lab Basic",
        version="0.1.0",
        compatible_basic_versions=[PRODUCT_VERSION],
        requested_capabilities=["case.read", "evidence.read", "ui.navigation.register"],
        categories=[
            {
                "id": "overview",
                "label": "Evidence Lab",
                "icon": "microscope",
                "case_scoped": True,
                "required_capabilities": ["ui.navigation.register"],
            }
        ],
        package_sha256=calculate_package_sha256(package_root),
        frontend_entrypoint="ui/index.js",
        lifecycle={
            "entrypoint_id": "evidence-lab-runtime",
            "install_root": str(install_root.resolve()),
            "executable": executable_name,
            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "base_url": "http://127.0.0.1:43119",
        },
    )
    return manifest, Ed25519PrivateKey.generate(), package_root


def _public_key(private_key: Ed25519PrivateKey) -> str:
    return b64encode(private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def test_state_machine_keeps_off_distinct_from_unlinked_and_rejects_invalid_transitions() -> None:
    require_transition(ModuleState.LINKED_OFF, ModuleState.STARTING)
    require_transition(ModuleState.STOPPING, ModuleState.LINKED_OFF)
    assert ModuleState.LINKED_OFF != ModuleState.UNLINKED
    with pytest.raises(ValueError, match="not allowed"):
        require_transition(ModuleState.LINKED_OFF, ModuleState.READY)
    with pytest.raises(ValueError, match="not allowed"):
        require_transition(ModuleState.REVOKED, ModuleState.STARTING)


@pytest.mark.parametrize(
    ("executable", "message"),
    [
        ("cmd.exe", "shell"),
        ("powershell.exe", "shell"),
        ("runtime.ps1", "shell"),
        ("../runtime.exe", "inside"),
        ("C:/Windows/System32/cmd.exe", "drive"),
    ],
)
def test_lifecycle_descriptor_rejects_shells_scripts_and_arbitrary_paths(
    tmp_path: Path, executable: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        ModuleLifecycleDescriptor(
            entrypoint_id="evidence-lab-runtime",
            install_root=str(tmp_path.resolve()),
            executable=executable,
            executable_sha256="0" * 64,
            base_url="http://127.0.0.1:43119",
        )


def test_manifest_rejects_unknown_capability_incompatible_protocol_and_navigation_without_grant(
    tmp_path: Path,
) -> None:
    manifest, _, _ = _module_fixture(tmp_path)
    payload = manifest.model_dump()
    payload["requested_capabilities"] = ["database.raw"]
    with pytest.raises(ValidationError, match="Forbidden"):
        ModuleManifest.model_validate(payload)
    payload = manifest.model_dump()
    payload["protocol_version"] = "2.0"
    with pytest.raises(ValidationError, match="Unsupported"):
        ModuleManifest.model_validate(payload)
    payload = manifest.model_dump()
    payload["requested_capabilities"] = ["case.read"]
    with pytest.raises(ValidationError, match="ui.navigation.register"):
        ModuleManifest.model_validate(payload)


def test_installation_identity_private_key_is_sealed_not_plaintext(tmp_path: Path) -> None:
    path = tmp_path / "identity.key"
    identity = InstallationIdentityStore(path).load_or_create()
    stored = path.read_bytes()
    assert len(stored) > 32
    assert b64encode(identity.private_key.private_bytes_raw()).encode() not in stored
    assert InstallationIdentityStore(path).load_or_create().fingerprint == identity.fingerprint


@pytest.mark.asyncio
async def test_pairing_is_signed_single_use_persistent_and_off_is_not_unlinked(
    tmp_path: Path, system_link_session
) -> None:
    identity_store = InstallationIdentityStore(tmp_path / "basic-identity.key")
    service = SystemLinkService(system_link_session, identity_store)
    manifest, module_key, package_root = _module_fixture(tmp_path)
    pairing, link_key, _, _ = await service.begin_pairing(ttl_seconds=60)
    module_public_key = _public_key(module_key)
    manifest_sha256 = hashlib.sha256(canonical_json(manifest)).hexdigest()
    pending = await service.submit_pairing(
        pairing_id=pairing.id,
        link_key=link_key,
        module_public_key=module_public_key,
        manifest=manifest,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        challenge_signature=b64encode(
            module_key.sign(
                pairing_proof_payload(
                    pairing_id=pairing.id,
                    challenge=pairing.challenge,
                    module_id=manifest.module_id,
                    module_public_key=module_public_key,
                    manifest_sha256=manifest_sha256,
                )
            )
        ),
        package_root=str(package_root),
    )
    assert pending.used_at is not None
    with pytest.raises(SystemLinkError) as replay:
        await service.submit_pairing(
            pairing_id=pairing.id,
            link_key=link_key,
            module_public_key=module_public_key,
            manifest=manifest,
            manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
            challenge_signature="unused-after-replay-check",
            package_root=str(package_root),
        )
    assert replay.value.code == "pairing_replayed"

    with pytest.raises(SystemLinkError) as escalation:
        await service.approve_pairing(pairing.id, ["report.read"])
    assert escalation.value.code == "capability_not_requested"
    module = await service.approve_pairing(pairing.id, ["evidence.read", "ui.navigation.register"])
    assert module.state == ModuleState.LINKED_OFF.value
    assert module.module_public_key == module_public_key
    view = await service.module_view(module)
    assert view.linked is True
    assert view.categories[0].enabled is False
    await service.revoke(module)
    assert module.state == ModuleState.REVOKED.value
    with pytest.raises(CapabilityDenied, match="not linked"):
        await require_capability(system_link_session, module.module_id, "ui.navigation.register", require_ready=False)
    assert await system_link_session.get(models.SystemLinkModule, manifest.module_id) is not None


@pytest.mark.asyncio
async def test_migrated_sqlite_pairing_approval_flushes_parent_before_grants_and_rolls_back(
    tmp_path: Path,
    migrated_system_link_session,
    monkeypatch,
) -> None:
    session = migrated_system_link_session
    service = SystemLinkService(session, InstallationIdentityStore(tmp_path / "migrated-basic-identity.key"))
    manifest, module_key, package_root = _module_fixture(tmp_path)
    pairing, link_key, _, _ = await service.begin_pairing(ttl_seconds=60)
    pairing_id = pairing.id
    module_public_key = _public_key(module_key)
    manifest_sha256 = hashlib.sha256(canonical_json(manifest)).hexdigest()
    pending = await service.submit_pairing(
        pairing_id=pairing_id,
        link_key=link_key,
        module_public_key=module_public_key,
        manifest=manifest,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        challenge_signature=b64encode(
            module_key.sign(
                pairing_proof_payload(
                    pairing_id=pairing_id,
                    challenge=pairing.challenge,
                    module_id=manifest.module_id,
                    module_public_key=module_public_key,
                    manifest_sha256=manifest_sha256,
                )
            )
        ),
        package_root=str(package_root),
    )
    assert pending.used_at is not None
    assert await session.get(models.SystemLinkModule, manifest.module_id) is None
    assert list((await session.execute(select(models.SystemLinkCapabilityGrant))).scalars()) == []

    original_event = service._event

    async def fail_before_commit(module_id: str | None, action: str, payload: dict) -> None:
        if action == "module_pair_completed":
            raise RuntimeError("injected approval failure")
        await original_event(module_id, action, payload)

    monkeypatch.setattr(service, "_event", fail_before_commit)
    with pytest.raises(RuntimeError, match="injected approval failure"):
        await service.approve_pairing(pairing_id, ["evidence.read", "ui.navigation.register"])

    assert await session.get(models.SystemLinkModule, manifest.module_id) is None
    assert list((await session.execute(select(models.SystemLinkCapabilityGrant))).scalars()) == []
    pairing_after_failure = await session.get(models.SystemLinkPairingNonce, pairing_id)
    assert pairing_after_failure is not None
    assert pairing_after_failure.approved_at is None

    monkeypatch.setattr(service, "_event", original_event)
    module = await service.approve_pairing(pairing_id, ["evidence.read", "ui.navigation.register"])
    assert module.state == ModuleState.LINKED_OFF.value
    grants = list((await session.execute(select(models.SystemLinkCapabilityGrant))).scalars())
    assert {grant.capability for grant in grants} == {"evidence.read", "ui.navigation.register"}
    assert {grant.module_id for grant in grants} == {module.module_id}
    connection = await session.connection()
    violations = await connection.exec_driver_sql("PRAGMA foreign_key_check")
    assert violations.all() == []

    with pytest.raises(SystemLinkError) as repeated:
        await service.approve_pairing(pairing_id, ["evidence.read"])
    assert repeated.value.code == "pairing_already_approved"
    assert len(list((await session.execute(select(models.SystemLinkCapabilityGrant))).scalars())) == 2


@pytest.mark.asyncio
async def test_pairing_rejects_a_forged_manifest_signature(tmp_path: Path, system_link_session) -> None:
    service = SystemLinkService(system_link_session, InstallationIdentityStore(tmp_path / "identity.key"))
    manifest, module_key, package_root = _module_fixture(tmp_path)
    pairing, link_key, _, _ = await service.begin_pairing()
    public = _public_key(module_key)
    attacker = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(canonical_json(manifest)).hexdigest()
    with pytest.raises(SystemLinkError) as failure:
        await service.submit_pairing(
            pairing_id=pairing.id,
            link_key=link_key,
            module_public_key=public,
            manifest=manifest,
            manifest_signature=b64encode(attacker.sign(canonical_json(manifest))),
            challenge_signature=b64encode(
                attacker.sign(
                    pairing_proof_payload(
                        pairing_id=pairing.id,
                        challenge=pairing.challenge,
                        module_id=manifest.module_id,
                        module_public_key=public,
                        manifest_sha256=digest,
                    )
                )
            ),
            package_root=str(package_root),
        )
    assert failure.value.code == "pairing_signature_invalid"
    assert pairing.used_at is None


@pytest.mark.asyncio
async def test_capability_denial_and_ready_navigation_gate(tmp_path: Path, system_link_session) -> None:
    service = SystemLinkService(system_link_session, InstallationIdentityStore(tmp_path / "identity.key"))
    manifest, module_key, package_root = _module_fixture(tmp_path)
    pairing, link_key, _, _ = await service.begin_pairing()
    public = _public_key(module_key)
    digest = hashlib.sha256(canonical_json(manifest)).hexdigest()
    await service.submit_pairing(
        pairing_id=pairing.id,
        link_key=link_key,
        module_public_key=public,
        manifest=manifest,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        challenge_signature=b64encode(
            module_key.sign(
                pairing_proof_payload(
                    pairing_id=pairing.id,
                    challenge=pairing.challenge,
                    module_id=manifest.module_id,
                    module_public_key=public,
                    manifest_sha256=digest,
                )
            )
        ),
        package_root=str(package_root),
    )
    module = await service.approve_pairing(pairing.id, ["ui.navigation.register"])
    with pytest.raises(CapabilityDenied, match="READY"):
        await require_capability(system_link_session, module.module_id, "ui.navigation.register")
    with pytest.raises(CapabilityDenied, match="not granted"):
        await require_capability(system_link_session, module.module_id, "evidence.write", require_ready=False)
    module.state = ModuleState.READY.value
    await system_link_session.commit()
    assert (await require_capability(system_link_session, module.module_id, "ui.navigation.register")).module_id == module.module_id
    assert (await service.module_view(module)).categories[0].enabled is True
    await service.transition(module, ModuleState.STOPPING)
    await service.transition(module, ModuleState.LINKED_OFF)
    view = await service.module_view(module)
    assert view.linked is True
    assert view.granted_capabilities == ["ui.navigation.register"]
    assert view.categories[0].enabled is False


@pytest.mark.asyncio
async def test_basic_catalog_works_without_evidence_installed(system_link_session) -> None:
    modules = await SystemLinkService(system_link_session).list_modules()
    evidence = next(module for module in modules if module.module_id == "oihk.evidence-lab")
    assert evidence.state == ModuleState.NOT_INSTALLED
    assert evidence.installed is False
    assert evidence.categories == []


@pytest.mark.asyncio
async def test_runtime_client_requires_signed_authentication_and_healthy_ready(tmp_path: Path) -> None:
    manifest, module_key, package_root = _module_fixture(tmp_path)
    module = models.SystemLinkModule(
        module_id=manifest.module_id,
        product_name=manifest.name,
        module_version=manifest.version,
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature="signature",
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.AUTHENTICATING.value,
        enabled=True,
    )
    identity = InstallationIdentityStore(tmp_path / "basic.key").load_or_create()

    async def handler(request: httpx.Request) -> httpx.Response:
        proof = json.loads(request.content or b"{}")
        payload = {
            "module_id": module.module_id,
            "protocol_version": module.protocol_version,
            "nonce": proof["nonce"],
            "timestamp": proof["timestamp"],
        }
        if request.url.path.endswith("handshake"):
            payload["authenticated"] = True
        else:
            payload.update({"healthy": True, "status": "READY"})
        signature = b64encode(module_key.sign(canonical_json(payload)))
        return httpx.Response(200, json={**payload, "signature": signature})

    client = AuthenticatedRuntimeClient(module, identity, transport=httpx.MockTransport(handler))
    await client.handshake(1)
    assert await client.health(1) == "READY"

    async def bad_handler(request: httpx.Request) -> httpx.Response:
        proof = json.loads(request.content or b"{}")
        return httpx.Response(
            200,
            json={
                "module_id": module.module_id,
                "protocol_version": module.protocol_version,
                "nonce": proof["nonce"],
                "timestamp": proof["timestamp"],
                "authenticated": True,
                "signature": b64encode(Ed25519PrivateKey.generate().sign(b"wrong")),
            },
        )

    with pytest.raises(RuntimeAuthenticationError):
        await AuthenticatedRuntimeClient(module, identity, transport=httpx.MockTransport(bad_handler)).handshake(1)

    async def unhealthy_handler(request: httpx.Request) -> httpx.Response:
        proof = json.loads(request.content or b"{}")
        payload = {
            "module_id": module.module_id,
            "protocol_version": module.protocol_version,
            "nonce": proof["nonce"],
            "timestamp": proof["timestamp"],
            "healthy": False,
            "status": "ERROR",
        }
        return httpx.Response(200, json={**payload, "signature": b64encode(module_key.sign(canonical_json(payload)))})

    with pytest.raises(RuntimeHealthError):
        await AuthenticatedRuntimeClient(module, identity, transport=httpx.MockTransport(unhealthy_handler)).health(1)


def test_verified_executable_hash_is_enforced(tmp_path: Path) -> None:
    manifest, _, package_root = _module_fixture(tmp_path)
    assert verify_executable(manifest.lifecycle).is_file()
    (package_root / "ui" / "index.js").write_text("tampered package", encoding="utf-8")
    with pytest.raises(ValueError, match="package hash"):
        verify_package(package_root, manifest.package_sha256)
    manifest.lifecycle.resolve_executable().write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        verify_executable(manifest.lifecycle)


@pytest.mark.asyncio
async def test_system_link_migrations_upgrade_a_pre_feature_database(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    async with engine.begin() as connection:
        await connection.exec_driver_sql("CREATE TABLE legacy_case_data (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        await connection.exec_driver_sql("INSERT INTO legacy_case_data(id, value) VALUES ('preserved', 'yes')")
        await connection.run_sync(Base.metadata.create_all)
        version = await run_migrations(connection)
        rows = await connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'system_link_%'"
        )
        tables = {str(row[0]) for row in rows}
        preserved = await connection.exec_driver_sql("SELECT value FROM legacy_case_data WHERE id='preserved'")
        preserved_value = preserved.scalar_one()
    await engine.dispose()
    assert version == 8
    assert preserved_value == "yes"
    assert {
        "system_link_installations",
        "system_link_modules",
        "system_link_capability_grants",
        "system_link_pairing_nonces",
        "system_link_events",
        "system_link_replay_nonces",
    }.issubset(tables)


@pytest.mark.asyncio
async def test_signed_module_requests_reject_replay_stale_and_offline_modules(
    tmp_path: Path, system_link_session
) -> None:
    manifest, module_key, package_root = _module_fixture(tmp_path)
    module = models.SystemLinkModule(
        module_id=manifest.module_id,
        product_name=manifest.name,
        module_version=manifest.version,
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature="signature",
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.READY.value,
        enabled=True,
    )
    system_link_session.add(module)
    await system_link_session.commit()
    module_id = module.module_id
    nonce = "n" * 32
    timestamp = int(time.time())
    payload = module_request_payload(
        module_id=module_id,
        method="GET",
        path="/system-link/module-api/v1/cases/case-1",
        nonce=nonce,
        timestamp=timestamp,
        body=b"",
    )
    signature = b64encode(module_key.sign(payload))
    assert (
        await authenticate_module_request(
            system_link_session,
            module_id=module_id,
            method="GET",
            path="/system-link/module-api/v1/cases/case-1",
            nonce=nonce,
            timestamp=timestamp,
            body=b"",
            signature=signature,
            now=timestamp,
        )
    ).module_id == module_id
    with pytest.raises(SystemLinkError) as replay:
        await authenticate_module_request(
            system_link_session,
            module_id=module_id,
            method="GET",
            path="/system-link/module-api/v1/cases/case-1",
            nonce=nonce,
            timestamp=timestamp,
            body=b"",
            signature=signature,
            now=timestamp,
        )
    assert replay.value.code == "module_request_replayed"
    with pytest.raises(SystemLinkError) as stale:
        await authenticate_module_request(
            system_link_session,
            module_id=module_id,
            method="GET",
            path="/system-link/module-api/v1/cases/case-1",
            nonce="s" * 32,
            timestamp=timestamp - 31,
            body=b"",
            signature=signature,
            now=timestamp,
        )
    assert stale.value.code == "module_request_stale"
    module = await system_link_session.get(models.SystemLinkModule, module_id)
    assert module is not None
    module.state = ModuleState.LINKED_OFF.value
    await system_link_session.commit()
    with pytest.raises(SystemLinkError) as offline:
        await authenticate_module_request(
            system_link_session,
            module_id=module_id,
            method="GET",
            path="/system-link/module-api/v1/cases/case-1",
            nonce="o" * 32,
            timestamp=timestamp,
            body=b"",
            signature=signature,
            now=timestamp,
        )
    assert offline.value.code == "module_not_ready"


@pytest.mark.asyncio
async def test_failed_runtime_start_is_bounded_and_crash_loop_quarantines(
    tmp_path: Path, system_link_session
) -> None:
    manifest, module_key, package_root = _module_fixture(tmp_path)
    module = models.SystemLinkModule(
        module_id=manifest.module_id,
        product_name=manifest.name,
        module_version=manifest.version,
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.LINKED_OFF.value,
        enabled=True,
    )
    system_link_session.add(module)
    await system_link_session.commit()
    supervisor = RuntimeSupervisor(InstallationIdentityStore(tmp_path / "supervisor-identity.key"))
    assert await supervisor.start(system_link_session, module) == ModuleState.ERROR
    assert module.last_error_code == "runtime_start_failed"
    assert await supervisor.start(system_link_session, module) == ModuleState.ERROR
    assert await supervisor.start(system_link_session, module) == ModuleState.QUARANTINED
    assert module.crash_count == 3


@pytest.mark.asyncio
async def test_runtime_authentication_timeout_is_bounded(tmp_path: Path, system_link_session, monkeypatch) -> None:
    manifest, module_key, package_root = _module_fixture(tmp_path)
    manifest.lifecycle.startup_timeout_seconds = 1
    module = models.SystemLinkModule(
        module_id=manifest.module_id,
        product_name=manifest.name,
        module_version=manifest.version,
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.LINKED_OFF.value,
        enabled=True,
    )
    system_link_session.add(module)
    await system_link_session.commit()

    class WaitingProcess:
        def __init__(self) -> None:
            self.returncode: int | None = None
            self.exited = asyncio.Event()

        async def wait(self) -> int:
            await self.exited.wait()
            return self.returncode or 0

        def terminate(self) -> None:
            self.returncode = 0
            self.exited.set()

        def kill(self) -> None:
            self.terminate()

    process = WaitingProcess()

    async def launch(*_args, **_kwargs):
        return process

    async def unavailable(_client, _timeout):
        raise httpx.ConnectError("runtime unavailable", request=httpx.Request("POST", "http://127.0.0.1"))

    monkeypatch.setattr(lifecycle_module.asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(AuthenticatedRuntimeClient, "handshake", unavailable)
    supervisor = RuntimeSupervisor(InstallationIdentityStore(tmp_path / "timeout-identity.key"))
    started = time.monotonic()
    result = await supervisor.start(system_link_session, module)
    elapsed = time.monotonic() - started
    assert result == ModuleState.ERROR
    assert module.last_error_code == "runtime_authentication_failed"
    assert 0.8 <= elapsed < 2.5


@pytest_asyncio.fixture
async def system_link_factory(tmp_path: Path):
    """Session factory for genuine multi-connection concurrency tests."""
    from sqlalchemy import event as sa_event

    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'system-link-race.db').as_posix()}")

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _enable_wal(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _submit_kwargs(
    pairing: models.SystemLinkPairingNonce,
    link_key: str,
    module_key: Ed25519PrivateKey,
    module_public_key: str,
    manifest: ModuleManifest,
    package_root: Path,
) -> dict:
    manifest_sha256 = hashlib.sha256(canonical_json(manifest)).hexdigest()
    return {
        "pairing_id": pairing.id,
        "link_key": link_key,
        "module_public_key": module_public_key,
        "manifest": manifest,
        "manifest_signature": b64encode(module_key.sign(canonical_json(manifest))),
        "challenge_signature": b64encode(
            module_key.sign(
                pairing_proof_payload(
                    pairing_id=pairing.id,
                    challenge=pairing.challenge,
                    module_id=manifest.module_id,
                    module_public_key=module_public_key,
                    manifest_sha256=manifest_sha256,
                )
            )
        ),
        "package_root": str(package_root),
    }


@pytest.mark.asyncio
async def test_link_key_is_consumed_exactly_once_under_concurrent_pairing(
    tmp_path: Path, system_link_factory
) -> None:
    identity_store = InstallationIdentityStore(tmp_path / "race-identity.key")
    manifest, module_key, package_root = _module_fixture(tmp_path)
    module_public_key = _public_key(module_key)

    async with system_link_factory() as bootstrap:
        service = SystemLinkService(bootstrap, identity_store)
        pairing, link_key, _, _ = await service.begin_pairing(ttl_seconds=60)
    kwargs = await _submit_kwargs(pairing, link_key, module_key, module_public_key, manifest, package_root)

    async def attempt(session) -> str:
        try:
            await SystemLinkService(session, identity_store).submit_pairing(**kwargs)
            return "ok"
        except SystemLinkError as exc:
            await session.rollback()
            return exc.code

    async with system_link_factory() as first, system_link_factory() as second:
        outcomes = await asyncio.gather(attempt(first), attempt(second))

    # Exactly one concurrent consumer may claim the single-use credential.
    assert sorted(outcomes) == ["ok", "pairing_replayed"]
    async with system_link_factory() as check:
        row = await check.get(models.SystemLinkPairingNonce, pairing.id)
        assert row is not None
        assert row.used_at is not None
        # The winner's payload is the only one persisted; pending_module is never overwritten.
        assert row.pending_module.get("module_public_key") == module_public_key


@pytest.mark.asyncio
async def test_failure_after_atomic_claim_rolls_the_key_back_for_legitimate_retry(
    tmp_path: Path, system_link_session, monkeypatch
) -> None:
    identity_store = InstallationIdentityStore(tmp_path / "rollback-identity.key")
    service = SystemLinkService(system_link_session, identity_store)
    manifest, module_key, package_root = _module_fixture(tmp_path)
    pairing, link_key, _, _ = await service.begin_pairing(ttl_seconds=60)
    pairing_id = pairing.id  # keep the key before the identity map is cleared
    module_public_key = _public_key(module_key)
    kwargs = await _submit_kwargs(pairing, link_key, module_key, module_public_key, manifest, package_root)

    original_event = service._event

    async def fail_after_claim(module_id: str | None, action: str, payload: dict) -> None:
        if action == "module_pair_proof_verified":
            raise RuntimeError("injected post-claim failure")
        await original_event(module_id, action, payload)

    monkeypatch.setattr(service, "_event", fail_after_claim)
    with pytest.raises(RuntimeError, match="injected post-claim failure"):
        await service.submit_pairing(**kwargs)

    # The whole transaction rolled back, so the single-use key was NOT burned.
    # The rollback expired the identity-map copy; read the row through a fresh
    # query instead of touching the expired object.
    system_link_session.expunge_all()
    row = (
        await system_link_session.execute(
            select(models.SystemLinkPairingNonce).where(models.SystemLinkPairingNonce.id == pairing_id)
        )
    ).scalar_one()
    assert row.used_at is None
    assert row.pending_module == {}

    monkeypatch.setattr(service, "_event", original_event)
    pending = await service.submit_pairing(**kwargs)
    assert pending.used_at is not None
    assert pending.pending_module["publisher_channel"] == "development"
    assert pending.pending_module["publisher_key_id"] == "development"


@pytest.mark.asyncio
async def test_pairing_rejects_untrusted_publisher_fail_closed(
    tmp_path: Path, system_link_session, monkeypatch
) -> None:
    service = SystemLinkService(system_link_session, InstallationIdentityStore(tmp_path / "strict-identity.key"))
    manifest, module_key, package_root = _module_fixture(tmp_path)
    pairing, link_key, _, _ = await service.begin_pairing(ttl_seconds=60)
    module_public_key = _public_key(module_key)
    kwargs = await _submit_kwargs(pairing, link_key, module_key, module_public_key, manifest, package_root)

    class _StrictSettings:
        system_link_allow_development_publishers = False

    monkeypatch.setattr("app.system_link.service.get_settings", lambda: _StrictSettings())
    with pytest.raises(SystemLinkError) as failure:
        await service.submit_pairing(**kwargs)
    assert failure.value.code == "publisher_untrusted"
    row = await system_link_session.get(models.SystemLinkPairingNonce, pairing.id)
    assert row.used_at is None  # the key was never consumed


async def _linked_off_module(
    tmp_path: Path, *, startup_timeout_seconds: float | None = None
) -> tuple[models.SystemLinkModule, ModuleManifest]:
    manifest, module_key, package_root = _module_fixture(tmp_path)
    if startup_timeout_seconds is not None:
        # The lifecycle descriptor is part of the signed manifest: mutate it
        # before signing so the signature stays valid.
        manifest.lifecycle.startup_timeout_seconds = startup_timeout_seconds
    module = models.SystemLinkModule(
        module_id=manifest.module_id,
        product_name=manifest.name,
        module_version=manifest.version,
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.LINKED_OFF.value,
        enabled=True,
    )
    return module, manifest


class _FakeRuntimeProcess:
    """Stand-in subprocess that stays alive until explicitly terminated."""

    def __init__(self) -> None:
        self.returncode: int | None = None

    async def wait(self) -> int:
        return self.returncode or 0

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = 0


@pytest.mark.asyncio
async def test_crash_counter_tracks_consecutive_failures_only(
    tmp_path: Path, system_link_session, monkeypatch
) -> None:
    module, manifest = await _linked_off_module(tmp_path, startup_timeout_seconds=1)
    system_link_session.add(module)
    await system_link_session.commit()

    async def _noop_watch(self, module_id: str, process) -> None:
        return None

    monkeypatch.setattr(RuntimeSupervisor, "_watch_process", _noop_watch)

    async def launch(*_args, **_kwargs):
        return _FakeRuntimeProcess()

    async def handshake(_client, _timeout) -> None:
        if failure_mode["fail"]:
            raise RuntimeAuthenticationError("injected startup failure")

    async def health(_client, _timeout) -> str:
        return "READY"

    async def shutdown(_client, _timeout) -> None:
        return None

    failure_mode = {"fail": True}
    monkeypatch.setattr(lifecycle_module.asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(AuthenticatedRuntimeClient, "handshake", handshake)
    monkeypatch.setattr(AuthenticatedRuntimeClient, "health", health)
    monkeypatch.setattr(AuthenticatedRuntimeClient, "shutdown", shutdown)
    supervisor = RuntimeSupervisor(InstallationIdentityStore(tmp_path / "reset-identity.key"))

    # failure -> READY -> failure -> READY -> failure must NOT quarantine.
    failure_mode["fail"] = True
    assert await supervisor.start(system_link_session, module) == ModuleState.ERROR
    assert module.crash_count == 1

    failure_mode["fail"] = False
    assert await supervisor.start(system_link_session, module) == ModuleState.READY
    assert module.crash_count == 0
    assert await supervisor.stop(system_link_session, module) == ModuleState.LINKED_OFF

    failure_mode["fail"] = True
    assert await supervisor.start(system_link_session, module) == ModuleState.ERROR
    assert module.crash_count == 1

    failure_mode["fail"] = False
    assert await supervisor.start(system_link_session, module) == ModuleState.READY
    assert module.crash_count == 0
    assert await supervisor.stop(system_link_session, module) == ModuleState.LINKED_OFF

    failure_mode["fail"] = True
    assert await supervisor.start(system_link_session, module) == ModuleState.ERROR
    assert module.crash_count == 1
    assert ModuleState(module.state) != ModuleState.QUARANTINED

    # Three consecutive failures still quarantine.
    assert await supervisor.start(system_link_session, module) == ModuleState.ERROR
    assert await supervisor.start(system_link_session, module) == ModuleState.QUARANTINED
    assert module.crash_count == 3


@pytest.mark.asyncio
async def test_module_ui_surface_serves_only_verified_package_files(tmp_path: Path, system_link_session) -> None:
    from fastapi import HTTPException as FastAPIHTTPException

    from app.system_link.router import module_ui_file

    manifest, module_key, package_root = _module_fixture(tmp_path)
    module = models.SystemLinkModule(
        module_id=manifest.module_id,
        product_name=manifest.name,
        module_version=manifest.version,
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.READY.value,
        enabled=True,
    )
    system_link_session.add(module)
    system_link_session.add(
        models.SystemLinkCapabilityGrant(
            module_id=manifest.module_id,
            capability="ui.navigation.register",
            manifest_sha256="a" * 64,
        )
    )
    await system_link_session.commit()

    response = await module_ui_file(manifest.module_id, "ui/index.js", system_link_session)
    assert response.status_code == 200
    assert b"evidence-lab" in response.body
    assert "Content-Security-Policy" in response.headers
    assert "connect-src 'none'" in response.headers["Content-Security-Policy"]

    with pytest.raises(FastAPIHTTPException) as traversal:
        await module_ui_file(manifest.module_id, "../outside.js", system_link_session)
    assert traversal.value.status_code == 404

    (package_root / "ui" / "readme.txt").write_text("not served", encoding="utf-8")
    with pytest.raises(FastAPIHTTPException) as content_type:
        await module_ui_file(manifest.module_id, "ui/readme.txt", system_link_session)
    assert content_type.value.status_code == 404

    module.state = ModuleState.LINKED_OFF.value
    await system_link_session.commit()
    with pytest.raises(FastAPIHTTPException) as inactive:
        await module_ui_file(manifest.module_id, "ui/index.js", system_link_session)
    assert inactive.value.status_code == 404

    module.state = ModuleState.READY.value
    await system_link_session.commit()
    with pytest.raises(FastAPIHTTPException) as ungranted:
        await module_ui_file(manifest.module_id + "-other", "ui/index.js", system_link_session)
    assert ungranted.value.status_code == 404


@pytest.mark.asyncio
async def test_reconcile_existing_runtime_requires_full_verification(
    tmp_path: Path, system_link_session, monkeypatch
) -> None:
    """A surviving runtime is only adopted after package/executable/identity
    re-verification AND a signed handshake against the pinned base URL."""
    manifest, module_key, package_root = _module_fixture(tmp_path)
    module = models.SystemLinkModule(
        module_id=manifest.module_id,
        product_name=manifest.name,
        module_version=manifest.version,
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.READY.value,
        enabled=True,
    )
    system_link_session.add(module)
    await system_link_session.commit()

    async def healthy_handshake(_client, _timeout) -> None:
        return None

    async def healthy_health(_client, _timeout) -> str:
        return "READY"

    monkeypatch.setattr(AuthenticatedRuntimeClient, "handshake", healthy_handshake)
    monkeypatch.setattr(AuthenticatedRuntimeClient, "health", healthy_health)
    supervisor = RuntimeSupervisor(InstallationIdentityStore(tmp_path / "reconcile-identity.key"))
    result = await supervisor.reconcile_existing_runtime(system_link_session, module)
    assert result == ModuleState.READY
    assert module.crash_count == 0

    # Tampering with the package must fail-closed: no handshake is even attempted.
    module.state = ModuleState.READY.value
    module.crash_count = 2
    await system_link_session.commit()
    (package_root / "ui" / "index.js").write_text("tampered", encoding="utf-8")
    result = await supervisor.reconcile_existing_runtime(system_link_session, module)
    assert result == ModuleState.ERROR
    assert module.last_error_code == "runtime_reconciliation_failed"
    assert module.crash_count == 2  # package failures do not count as runtime crashes

    # Restore the package before testing the authentication-failure path.
    (package_root / "ui" / "index.js").write_text("export const module = 'evidence-lab';", encoding="utf-8")

    # A signed-authentication failure (e.g. the endpoint does not own the
    # pinned module identity) must never adopt the process.
    module.state = ModuleState.READY.value
    module.crash_count = 0
    await system_link_session.commit()

    async def rejecting_handshake(_client, _timeout) -> None:
        raise RuntimeAuthenticationError("runtime does not own the pinned module identity")

    monkeypatch.setattr(AuthenticatedRuntimeClient, "handshake", rejecting_handshake)
    result = await supervisor.reconcile_existing_runtime(system_link_session, module)
    assert result == ModuleState.ERROR
    assert module.crash_count == 1


@pytest.mark.asyncio
async def test_reconcile_existing_runtime_returns_the_final_persisted_state(
    tmp_path: Path, system_link_session, monkeypatch
) -> None:
    """Repeated reconciliation failures must report the state that was actually
    persisted: ERROR per failure and QUARANTINED on the third consecutive one.
    A healthy recovery afterwards clears the consecutive-failure streak."""
    module, _ = await _linked_off_module(tmp_path)
    module.state = ModuleState.READY.value
    system_link_session.add(module)
    await system_link_session.commit()

    async def rejecting_handshake(_client, _timeout) -> None:
        raise RuntimeAuthenticationError("runtime does not own the pinned module identity")

    async def healthy_handshake(_client, _timeout) -> None:
        return None

    async def healthy_health(_client, _timeout) -> str:
        return "READY"

    monkeypatch.setattr(AuthenticatedRuntimeClient, "handshake", rejecting_handshake)
    supervisor = RuntimeSupervisor(InstallationIdentityStore(tmp_path / "final-state-identity.key"))

    # First reconciliation failure -> ERROR, returned and persisted consistently.
    result = await supervisor.reconcile_existing_runtime(system_link_session, module)
    assert result == ModuleState.ERROR
    assert ModuleState(module.state) == ModuleState.ERROR
    assert module.crash_count == 1

    # Basic re-attempts reconciliation only against survivors (READY/BUSY), so
    # each restart puts the module back in that state before the next attempt.
    module.state = ModuleState.READY.value
    await system_link_session.commit()

    # Second failure -> still ERROR, never quarantined.
    result = await supervisor.reconcile_existing_runtime(system_link_session, module)
    assert result == ModuleState.ERROR
    assert ModuleState(module.state) == ModuleState.ERROR
    assert module.crash_count == 2

    module.state = ModuleState.READY.value
    await system_link_session.commit()

    # Third consecutive failure -> QUARANTINED; the returned value must match
    # the persisted state (regression for the ERROR-vs-QUARANTINED gap).
    result = await supervisor.reconcile_existing_runtime(system_link_session, module)
    assert result == ModuleState.QUARANTINED
    assert ModuleState(module.state) == ModuleState.QUARANTINED
    assert module.crash_count == 3
    assert module.last_error_code == "runtime_crash_loop"

    # A later healthy reconciliation clears the consecutive-failure streak.
    module.state = ModuleState.READY.value
    await system_link_session.commit()
    monkeypatch.setattr(AuthenticatedRuntimeClient, "handshake", healthy_handshake)
    monkeypatch.setattr(AuthenticatedRuntimeClient, "health", healthy_health)
    result = await supervisor.reconcile_existing_runtime(system_link_session, module)
    assert result == ModuleState.READY
    assert ModuleState(module.state) == ModuleState.READY
    assert module.crash_count == 0


@pytest.mark.asyncio
async def test_reconcile_existing_runtime_non_consecutive_failures_do_not_quarantine(
    tmp_path: Path, system_link_session, monkeypatch
) -> None:
    """failure -> READY -> failure -> READY -> failure must NOT quarantine:
    only consecutive failures accumulate toward the crash-loop limit."""
    module, _ = await _linked_off_module(tmp_path)
    module.state = ModuleState.READY.value
    system_link_session.add(module)
    await system_link_session.commit()

    async def rejecting_handshake(_client, _timeout) -> None:
        raise RuntimeAuthenticationError("runtime does not own the pinned module identity")

    async def healthy_handshake(_client, _timeout) -> None:
        return None

    async def healthy_health(_client, _timeout) -> str:
        return "READY"

    supervisor = RuntimeSupervisor(InstallationIdentityStore(tmp_path / "non-consecutive-identity.key"))
    for failing in (True, False, True, False, True):
        module.state = ModuleState.READY.value
        await system_link_session.commit()
        monkeypatch.setattr(
            AuthenticatedRuntimeClient,
            "handshake",
            rejecting_handshake if failing else healthy_handshake,
        )
        if not failing:
            monkeypatch.setattr(AuthenticatedRuntimeClient, "health", healthy_health)
        result = await supervisor.reconcile_existing_runtime(system_link_session, module)
        expected = ModuleState.ERROR if failing else ModuleState.READY
        assert result == expected
        assert ModuleState(module.state) == expected
        # Every healthy reconciliation resets the streak back to zero.
        assert module.crash_count == (1 if failing else 0)
    assert ModuleState(module.state) != ModuleState.QUARANTINED


@pytest.mark.asyncio
async def test_reconcile_startup_marks_in_flight_error_and_returns_survivors(
    tmp_path: Path, system_link_session
) -> None:
    service = SystemLinkService(system_link_session, InstallationIdentityStore(tmp_path / "startup-identity.key"))
    manifest, module_key, package_root = _module_fixture(tmp_path)
    module = models.SystemLinkModule(
        module_id=manifest.module_id,
        product_name=manifest.name,
        module_version=manifest.version,
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.STARTING.value,
        enabled=True,
    )
    system_link_session.add(module)
    await system_link_session.commit()
    module.state = ModuleState.READY.value
    await system_link_session.commit()
    # Two modules: one READY (survivor), one STARTING (in-flight, untrustworthy).
    in_flight = models.SystemLinkModule(
        module_id="oihk.pentesting-fixture",
        product_name="Fixture",
        module_version="0.1.0",
        protocol_version=manifest.protocol_version,
        manifest_schema_version=manifest.schema_version,
        module_public_key=_public_key(module_key),
        module_fingerprint="f" * 64,
        manifest=manifest.model_dump(mode="json"),
        manifest_sha256="a" * 64,
        manifest_signature=b64encode(module_key.sign(canonical_json(manifest))),
        package_root=str(package_root),
        package_sha256=manifest.package_sha256,
        lifecycle=manifest.lifecycle.model_dump(mode="json"),
        state=ModuleState.STARTING.value,
        enabled=True,
    )
    system_link_session.add(in_flight)
    await system_link_session.commit()

    survivors = await service.reconcile_startup_states()
    survivor_ids = {item.module_id for item in survivors}
    assert survivor_ids == {manifest.module_id}
    in_flight = await system_link_session.get(models.SystemLinkModule, "oihk.pentesting-fixture")
    assert in_flight is not None
    assert in_flight.state == ModuleState.ERROR.value
    assert in_flight.last_error_code == "host_restart_requires_reauthentication"


@pytest.mark.asyncio
async def test_reconcile_resets_crash_counter_on_healthy_runtime(
    tmp_path: Path, system_link_session, monkeypatch
) -> None:
    module, _ = await _linked_off_module(tmp_path)
    module.state = ModuleState.READY.value
    module.crash_count = 5
    system_link_session.add(module)
    await system_link_session.commit()

    async def health(_client, _timeout) -> str:
        return "READY"

    monkeypatch.setattr(AuthenticatedRuntimeClient, "health", health)
    supervisor = RuntimeSupervisor(InstallationIdentityStore(tmp_path / "reconcile-identity.key"))
    await supervisor.reconcile(system_link_session, module)
    assert module.state == ModuleState.READY.value
    assert module.crash_count == 0
