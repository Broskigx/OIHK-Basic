#!/usr/bin/env python3
"""Real E2E smoke: OIHK Basic host <-> OIHK Evidence Lab module over System Link v1.

This is the authoritative proof that System Link v1 works between the two real
products (not mocks). It:

1.  Builds the Evidence Lab runtime executable (PyInstaller).
2.  Builds the Evidence Lab module UI bundle (Vite).
3.  Builds the signed module package with a DEVELOPMENT publisher identity.
4.  Starts a real OIHK Basic backend on a temporary data directory.
5.  Runs the full System Link lifecycle:
    pair/start -> module pairing proof -> approve -> Power On -> real runtime
    spawn -> Ed25519 mutual auth -> health READY -> authorized case/evidence
    queries -> status publish -> Power Off -> Restart -> health -> replay
    rejected -> package tampering rejected -> executable tampering rejected.
6.  Cleans up every temporary process and directory, even on failure.

Usage (from the repository root, with Python >= 3.11 available):

    python scripts/smoke_system_link_e2e.py \
        --evidence-lab C:\\path\\to\\OiHK-evidence-lab \
        [--keep] [--port 8001]

Requirements:
    * a local clone of Broskigx/OiHK-evidence-lab (see --evidence-lab);
    * Node >= 22 for the module UI bundle;
    * network access to PyPI and the npm registry (build-time only).

No cloud service is used at runtime; everything runs on loopback.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_VERSION_FILE = REPO_ROOT / "backend" / "app" / "version.py"

SMOKE_STEPS: list[tuple[str, str]] = [
    ("build-runtime", "Build Evidence Lab runtime executable"),
    ("build-ui", "Build Evidence Lab module UI bundle"),
    ("sign-package", "Sign module package with DEVELOPMENT publisher identity"),
    ("start-basic", "Start OIHK Basic backend"),
    ("pair-start", "pair/start"),
    ("pair-complete", "Evidence Lab submits the signed pairing proof"),
    ("approve", "Approve capabilities"),
    ("power-on", "Power On and spawn the real runtime"),
    ("mutual-auth", "Ed25519 mutual authentication"),
    ("health-ready", "health -> READY"),
    ("case-query", "Authorized case query via module API"),
    ("evidence-query", "Authorized evidence query via module API"),
    ("status-publish", "Module status publish"),
    ("power-off", "Power Off"),
    ("restart", "Restart and health again"),
    ("replay-rejected", "Link Key replay is rejected"),
    ("tamper-package", "Package tampering is rejected"),
    ("tamper-executable", "Executable tampering is rejected"),
]


class SmokeError(RuntimeError):
    pass


def _log(message: str) -> None:
    print(f"[smoke] {message}", flush=True)


def _fail(message: str) -> None:
    raise SmokeError(message)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 900) -> str:
    if os.name == "nt" and command:
        # npm and other Node tooling are .cmd shims on Windows; CreateProcess
        # cannot launch them directly, so route them through cmd.exe /c.
        resolved = shutil.which(command[0])
        if resolved and resolved.lower().endswith((".cmd", ".bat")):
            command = ["cmd.exe", "/c", resolved, *command[1:]]
    _log(f"$ {' '.join(command)}")
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=process_env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        _log(f"  stdout: {result.stdout[-2000:]}")
        _log(f"  stderr: {result.stderr[-3000:]}")
        _fail(f"command failed with exit code {result.returncode}: {' '.join(command)}")
    return result.stdout


class BasicProcess:
    def __init__(self, port: int, data_dir: Path, evidence_data_dir: Path, python: Path) -> None:
        self.port = port
        self.data_dir = data_dir
        self.evidence_data_dir = evidence_data_dir
        self.python = python
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        env = os.environ.copy()
        # Isolate the smoke completely: the backend must never touch the real
        # user database or storage, so point both at the temporary data dir.
        env["OIHK_SYSTEM_LINK_ALLOW_DEV_PUBLISHERS"] = "1"
        env["OIHK_AUTH_ENABLED"] = "0"
        env["OIHK_SERVER_BIND_HOST"] = "127.0.0.1"
        env["OIHK_EVIDENCE_DATA_DIR"] = str(self.evidence_data_dir)
        env["OIHK_DATABASE_URL"] = f"sqlite+aiosqlite:///{(self.data_dir / 'oihk-basic.db').as_posix()}"
        env["OIHK_STORAGE_DIR"] = str(self.data_dir / "storage")
        env.pop("OIHK_DESKTOP_PACKAGED", None)
        env.pop("OIHK_PACKAGED_DATA_DIR", None)
        command = [
            str(self.python),
            str(REPO_ROOT / "backend" / "run.py"),
            "--port",
            str(self.port),
            "--data-dir",
            str(self.data_dir),
            "--log-level",
            "warning",
        ]
        _log(f"$ {' '.join(command)}")
        self.process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def stop(self) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.process = None


def _wait_for_http(port: int, timeout: float = 60.0) -> None:
    import httpx

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2.0)
            if response.status_code < 500:
                return
        except Exception as exc:  # noqa: BLE001 - retry loop
            last_error = exc
        time.sleep(1.0)
    _fail(f"OIHK Basic did not become healthy within {timeout}s: {last_error}")


def _kill_smoke_runtimes(install_root: Path) -> None:
    """Terminate only Evidence Lab runtimes owned by this smoke run.

    Uses the process executable path (which must live under the smoke's
    temporary install root) instead of killing by image name, so a real
    Evidence Lab runtime paired outside the smoke is never touched.
    """
    root_prefix = str(install_root.resolve()).lower()
    powershell = (
        "Get-CimInstance Win32_Process -Filter \"Name='evidence-lab-runtime.exe'\" | "
        "Where-Object { $_.ExecutablePath -and "
        f"$_.ExecutablePath.ToLower().StartsWith('{root_prefix}') }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", powershell],
        capture_output=True,
        timeout=30,
        check=False,
    )


def _read_product_version() -> str:
    namespace: dict[str, object] = {}
    with PRODUCT_VERSION_FILE.open(encoding="utf-8") as source:
        exec(source.read(), namespace)  # noqa: S102 - trusted repository file
    value = namespace.get("PRODUCT_VERSION")
    if not isinstance(value, str):
        _fail("backend/app/version.py does not define PRODUCT_VERSION")
    return value


async def _run_e2e(
    *,
    evidence_lab: Path,
    port: int,
    keep: bool,
    smoke_python: Path,
) -> None:
    # The smoke may be launched from any Python; make the Basic package
    # importable the same way the backend is installed (editable from source).
    if str(REPO_ROOT / "backend") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "backend"))
    import httpx
    from app.system_link.module_auth import module_request_payload

    evidence_lab = evidence_lab.resolve()
    basic_version = _read_product_version()
    tmp_root = Path(tempfile.mkdtemp(prefix="oihk-smoke-e2e-"))
    basic_data = tmp_root / "basic-data"
    basic_data.mkdir()
    evidence_data = tmp_root / "evidence-data"
    evidence_data.mkdir()
    install_root = tmp_root / "install"
    package_root = tmp_root / "package"
    ui_dist = evidence_lab / "ui" / "dist"
    runtime_script = evidence_lab / "scripts" / "build_runtime.py"
    if not runtime_script.is_file():
        _fail(f"Evidence Lab repo does not contain scripts/build_runtime.py: {evidence_lab}")
    executable_name = "evidence-lab-runtime.exe" if os.name == "nt" else "evidence-lab-runtime"
    executable_identity = f"bin/{executable_name}"
    basic = BasicProcess(port, basic_data, evidence_data, smoke_python)
    processes_to_kill: list[subprocess.Popen] = []

    def cleanup() -> None:
        from contextlib import suppress

        for process in processes_to_kill:
            with suppress(Exception):
                process.terminate()
        basic.stop()
        if os.name == "nt":
            # A Basic terminate() cannot propagate to the verified runtime child.
            # Kill ONLY the smoke's own runtimes (executables under the temp
            # install root) — never a user's real Evidence Lab runtime by name.
            with suppress(Exception):
                _kill_smoke_runtimes(install_root)
        if not keep:
            shutil.rmtree(tmp_root, ignore_errors=True)

    client: httpx.AsyncClient | None = None
    try:
        _log(f"Evidence Lab repo: {evidence_lab}")
        _log(f"Basic version: {basic_version}")

        # ── 1. Build the Evidence Lab runtime executable ─────────────────────
        _log("Building Evidence Lab runtime (PyInstaller)...")
        runtime_output = _run(
            [str(smoke_python), str(runtime_script), "--output-root", str(install_root)],
            cwd=evidence_lab,
            timeout=1200,
        )
        built = install_root / "bin" / executable_name
        if not built.is_file():
            _fail(f"runtime build did not produce {built} (output: {runtime_output[-500:]})")

        # ── 2. Build the module UI bundle ────────────────────────────────────
        _log("Building Evidence Lab module UI (npm)...")
        _run(["npm", "ci"], cwd=evidence_lab / "ui", timeout=1200)
        _run(["npm", "run", "build"], cwd=evidence_lab / "ui", timeout=1200)
        if not (ui_dist / "index.js").is_file():
            _fail(f"module UI build did not produce {ui_dist / 'index.js'}")

        # ── 3. Build and sign the module package (DEVELOPMENT publisher) ─────
        _log("Building signed module package with DEVELOPMENT publisher...")
        module_build = _run(
            [
                str(smoke_python),
                "-m",
                "oihk_evidence_lab.cli",
                "module",
                "build",
                "--ui-dist",
                str(ui_dist),
                "--package-root",
                str(package_root),
                "--install-root",
                str(install_root),
                "--executable",
                executable_identity,
                "--basic-version",
                basic_version,
                "--development",
                "--replace",
            ],
            cwd=evidence_lab,
            env={"OIHK_EVIDENCE_DATA_DIR": str(evidence_data)},
            timeout=300,
        )
        _log(f"  package: {module_build.strip().splitlines()[-3:]}")

        # ── 4. Start OIHK Basic ─────────────────────────────────────────────
        _log("Starting OIHK Basic backend...")
        basic.start()
        processes_to_kill.append(basic.process)  # type: ignore[arg-type]
        _wait_for_http(port)

        # ── 5-18. Full System Link lifecycle ────────────────────────────────
        # Lifecycle calls (Power On/Restart) wait for the real runtime startup,
        # which includes a one-file PyInstaller boot, so use a generous timeout.
        base_url = f"http://127.0.0.1:{port}"
        client = httpx.AsyncClient(base_url=base_url, timeout=120.0)

        # 5. pair/start + 6. Evidence Lab pairing proof: the real Evidence Lab
        # pairing coordinator performs begin_pairing itself and submits the
        # signed proof, exactly like the module CLI does.
        sys.path.insert(0, str(evidence_lab / "src"))
        from oihk_evidence_lab.identity import IdentityManager
        from oihk_evidence_lab.secure_store import default_secure_store
        from oihk_evidence_lab.state import StateStore
        from oihk_evidence_lab.system_link.client import BasicSystemLinkClient
        from oihk_evidence_lab.system_link.package import build_manifest
        from oihk_evidence_lab.system_link.pairing import PairingCoordinator

        paths = __import__(
            "oihk_evidence_lab.config", fromlist=["EvidenceLabPaths"]
        ).EvidenceLabPaths.from_data_dir(evidence_data)
        paths.ensure()
        state = StateStore(paths.state_db)
        state.initialize()
        identity_manager = IdentityManager(state, default_secure_store(paths))
        module_identity = identity_manager.load_or_create()

        manifest = build_manifest(
            package_root=package_root,
            install_root=install_root,
            executable=executable_identity,
            compatible_basic_versions=[basic_version],
        )
        coordinator = PairingCoordinator(state, identity_manager)
        outcome = await coordinator.pair(
            client=BasicSystemLinkClient(base_url),
            manifest=manifest,
            package_root=package_root,
        )
        _log(f"  pairing id: {outcome.pending.pairing_id}")
        _log(f"  host link key: {outcome.host_link_key}")

        # 7. Approve capabilities
        _log("approve capabilities")
        pending = (await client.get("/system-link/pair/pending")).json()
        _log(f"  pending pairings: {[item['pairing_id'] for item in pending]}")
        pairing_id = next(item["pairing_id"] for item in pending if item["module_id"] == manifest.module_id)
        approve = await client.post(
            f"/system-link/pair/{pairing_id}/approve",
            json={
                "granted_capabilities": [
                    "case.read",
                    "evidence.read",
                    "ui.navigation.register",
                    "module.status.publish",
                ]
            },
        )
        if approve.status_code >= 400:
            _fail(f"approve failed: {approve.status_code} {approve.text}")
        approved = approve.json()
        _log(f"  state: {approved['state']}")
        if approved["state"] != "LINKED_OFF":
            _fail(f"expected LINKED_OFF after approval, got {approved['state']}")
        if approved.get("publisher", {}).get("channel") != "development":
            _fail("approved module does not carry the development publisher channel")

        # 8. Power On: spawn the real Evidence Lab runtime executable.
        _log("power-on: spawn the real Evidence Lab runtime")
        start_call = await client.post(f"/system-link/modules/{manifest.module_id}/start")
        start_call.raise_for_status()

        # 9-10. Mutual auth + health -> READY
        module_state = "STARTING"
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            status = (await client.get("/system-link/status")).json()
            module_state = next(
                item["state"] for item in status["modules"] if item["module_id"] == manifest.module_id
            )
            if module_state in {"READY", "BUSY"}:
                break
            await asyncio.sleep(1.0)
        _log(f"  module state: {module_state}")
        if module_state != "READY":
            detail = next(
                (item["last_error_detail"] for item in status["modules"] if item["module_id"] == manifest.module_id),
                "",
            )
            _fail(f"runtime did not reach READY (state={module_state}, error={detail})")

        # 11-12. Authorized case/evidence queries via the signed module API.
        _log("authorized case + evidence queries via the signed module API")
        case_create = await client.post(
            "/cases",
            json={
                "title": "E2E Smoke Case",
                "summary": "created by the real Evidence Lab E2E",
                "legal_basis": "local test authorization",
                "scope_statement": "scope of the E2E smoke case",
            },
        )
        case_create.raise_for_status()
        case_id = case_create.json()["id"]

        async def signed_module_request(method: str, path: str, body: bytes = b"") -> httpx.Response:
            nonce = hashlib.sha256(os.urandom(24)).hexdigest()
            timestamp = int(time.time())
            payload = module_request_payload(
                module_id=manifest.module_id,
                method=method,
                path=path,
                nonce=nonce,
                timestamp=timestamp,
                body=body,
            )
            headers = {
                "Content-Type": "application/json",
                "X-OIHK-Module-Id": manifest.module_id,
                "X-OIHK-Nonce": nonce,
                "X-OIHK-Timestamp": str(timestamp),
                "X-OIHK-Signature": module_identity.sign(payload),
            }
            return await client.request(method, path, headers=headers, content=body)

        case_read = await signed_module_request("GET", f"/system-link/module-api/v1/cases/{case_id}")
        if case_read.status_code != 200:
            _fail(f"authorized case query failed: {case_read.status_code} {case_read.text}")
        _log(f"  case read OK: {case_read.json()['title']}")

        evidence_read = await signed_module_request("GET", f"/system-link/module-api/v1/cases/{case_id}/evidence")
        if evidence_read.status_code != 200:
            _fail(f"authorized evidence query failed: {evidence_read.status_code} {evidence_read.text}")
        _log(f"  evidence read OK: {len(evidence_read.json())} items")

        # 13. Module status publish.
        _log("module status publish (BUSY)")
        status_body = json.dumps({"status": "BUSY", "detail": "E2E busy marker"}).encode("utf-8")
        status_publish = await signed_module_request("POST", "/system-link/module-api/v1/status", body=status_body)
        if status_publish.status_code != 200:
            _fail(f"status publish failed: {status_publish.status_code} {status_publish.text}")
        _log(f"  published: {status_publish.json()['state']}")

        # 14. Power Off.
        _log("power-off")
        stop_call = await client.post(f"/system-link/modules/{manifest.module_id}/stop")
        stop_call.raise_for_status()
        if stop_call.json()["state"] != "LINKED_OFF":
            _fail(f"stop did not reach LINKED_OFF: {stop_call.json()}")

        # 15. Restart + health again.
        _log("restart")
        restart_call = await client.post(f"/system-link/modules/{manifest.module_id}/restart")
        restart_call.raise_for_status()
        module_state = restart_call.json()["state"]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            status = (await client.get("/system-link/status")).json()
            module_state = next(
                item["state"] for item in status["modules"] if item["module_id"] == manifest.module_id
            )
            if module_state in {"READY", "BUSY"}:
                break
            await asyncio.sleep(1.0)
        if module_state != "READY":
            _fail(f"restarted runtime did not reach READY (state={module_state})")
        _log("  restarted and healthy")

        # 16. Link Key replay rejected.
        _log("link key replay rejected")
        replay_proof = {
            "pairing_id": outcome.pending.pairing_id,
            "link_key": outcome.host_link_key,
            "module_public_key": module_identity.public_key,
            "manifest": manifest.model_dump(mode="json"),
            # The signature strings are syntactically valid (>= 40 chars) so the
            # request reaches the single-use Link Key check, which must reject
            # the replay before any cryptographic validation is attempted.
            "manifest_signature": "r" * 64,
            "challenge_signature": "r" * 64,
            "package_root": str(package_root),
        }
        replay = await client.post("/system-link/pair/complete", json=replay_proof)
        if replay.status_code != 409 or "pairing_replayed" not in replay.text:
            _fail(f"replayed link key was not rejected: {replay.status_code} {replay.text}")
        _log("  replay rejected with pairing_replayed")

        # 17. Package tampering rejected (supervisor must fail-closed).
        _log("package tampering rejected")
        await client.post(f"/system-link/modules/{manifest.module_id}/stop")
        tampered_entrypoint = package_root / "ui" / "index.js"
        original_ui = tampered_entrypoint.read_bytes()
        tampered_entrypoint.write_bytes(b"tampered module ui")
        tampered_start = await client.post(f"/system-link/modules/{manifest.module_id}/start")
        tampered_entrypoint.write_bytes(original_ui)
        if tampered_start.status_code != 200:
            _fail(f"tampered start did not return 200 (expected supervised failure): {tampered_start.text}")
        status = (await client.get("/system-link/status")).json()
        tampered_state = next(
            item["state"] for item in status["modules"] if item["module_id"] == manifest.module_id
        )
        if tampered_state != "ERROR":
            _fail(f"tampered package was not rejected (state={tampered_state})")
        _log("  tampered package rejected at runtime start")

        # 18. Executable tampering rejected.
        _log("executable tampering rejected")
        original_exe = built.read_bytes()
        built.write_bytes(original_exe + b"\x00")
        tampered_exe_start = await client.post(f"/system-link/modules/{manifest.module_id}/start")
        built.write_bytes(original_exe)
        if tampered_exe_start.status_code != 200:
            _fail(f"tampered executable start did not return 200: {tampered_exe_start.text}")
        status = (await client.get("/system-link/status")).json()
        tampered_exe_state = next(
            item["state"] for item in status["modules"] if item["module_id"] == manifest.module_id
        )
        if tampered_exe_state != "ERROR":
            _fail(f"tampered executable was not rejected (state={tampered_exe_state})")
        _log("  tampered executable rejected at runtime start")

        # ── All steps passed ────────────────────────────────────────────────
        _log("=" * 60)
        _log("E2E SMOKE PASSED - real OIHK Basic <-> OIHK Evidence Lab over System Link v1")
        for step, description in SMOKE_STEPS:
            _log(f"  [PASS] {step}: {description}")
        _log("=" * 60)
    finally:
        if client is not None:
            await client.aclose()
        cleanup()


def _bootstrap_smoke_venv(root: Path, evidence_lab: Path) -> Path:
    """Create a smoke venv with both packages installed (Basic + Evidence Lab)."""
    python = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if python.is_file():
        return python
    _log("Creating smoke venv with Basic and Evidence Lab packages...")
    venv.EnvBuilder(with_pip=True).create(root)
    _run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-e", str(REPO_ROOT / "backend")],
        cwd=REPO_ROOT,
        timeout=900,
    )
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-q",
            "-e",
            f"{evidence_lab}[release]",
        ],
        cwd=evidence_lab,
        timeout=900,
    )
    return python


def main() -> None:
    parser = argparse.ArgumentParser(description="OIHK Basic <-> Evidence Lab System Link v1 E2E smoke")
    parser.add_argument("--evidence-lab", required=True, help="Path to the OiHK-evidence-lab repository clone")
    parser.add_argument("--port", type=int, default=0, help="Port for the Basic backend (default: free port)")
    parser.add_argument("--keep", action="store_true", help="Keep temporary directories on failure")
    args = parser.parse_args()

    evidence_lab = Path(args.evidence_lab).resolve()
    if not (evidence_lab / "pyproject.toml").is_file():
        parser.error(f"--evidence-lab does not look like the OiHK-evidence-lab repository: {evidence_lab}")

    smoke_root = REPO_ROOT / ".smoke" / "e2e-venv"
    smoke_python = _bootstrap_smoke_venv(smoke_root, evidence_lab)
    if Path(sys.executable).resolve() != smoke_python.resolve():
        # The smoke logic needs BOTH packages importable (Basic + Evidence Lab).
        # Re-exec within the smoke venv that installed them, then continue.
        argv = [str(smoke_python), str(Path(__file__).resolve())]
        argv += ["--evidence-lab", str(evidence_lab)]
        if args.keep:
            argv.append("--keep")
        _log(f"Re-executing in smoke venv: {' '.join(argv)}")
        os.execv(str(smoke_python), argv)
    port = args.port or _free_port()
    _log(f"Basic port: {port}")
    asyncio.run(_run_e2e(evidence_lab=evidence_lab, port=port, keep=args.keep, smoke_python=smoke_python))


if __name__ == "__main__":
    main()
