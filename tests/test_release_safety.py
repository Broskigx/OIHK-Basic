"""Release automation must fail closed and keep user data outside installers."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_metadata_is_canonical() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "version.py"), "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_release_config_contains_public_material_only() -> None:
    # The generator intentionally requires output inside the repository, so use an ignored test path there.
    output = ROOT / "src-tauri" / "tauri.release.test.conf.json"
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_release_config.py"),
                "--public-key",
                "RWT" + "A" * 64,
                "--output",
                str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        config = json.loads(output.read_text(encoding="utf-8"))
        assert config["bundle"]["createUpdaterArtifacts"] is True
        assert config["plugins"]["updater"]["pubkey"].startswith("RWT")
        assert config["plugins"]["updater"]["endpoints"][0].startswith("https://")
        serialized = json.dumps(config).upper()
        assert "PRIVATE KEY" not in serialized
        assert "TAURI_SIGNING_PRIVATE_KEY" not in serialized
    finally:
        output.unlink(missing_ok=True)


def test_release_config_rejects_private_material() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_release_config.py"),
            "--public-key",
            "-----BEGIN PRIVATE KEY-----" + "A" * 64,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Refusing to place private key material" in result.stdout + result.stderr


def test_signed_metadata_round_trip_and_corruption_rejection(tmp_path: Path) -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    installer = tmp_path / f"OIHK Basic_{version}_x64-setup.exe"
    updater = tmp_path / f"OIHK Basic_{version}_x64-setup.nsis.zip"
    signature = updater.with_suffix(updater.suffix + ".sig")
    installer.write_bytes(b"test installer")
    updater.write_bytes(b"test signed updater archive")
    signature.write_text("RWT" + "A" * 80, encoding="utf-8")
    generated = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_update_metadata.py"),
            "--tag",
            f"basic-v{version}",
            "--channel",
            "alpha",
            "--installer",
            str(installer),
            "--updater",
            str(updater),
            "--signature",
            str(signature),
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr
    metadata = json.loads((tmp_path / "latest-alpha.json").read_text(encoding="utf-8"))
    assert metadata["version"] == version
    assert metadata["platforms"]["windows-x86_64"]["signature"] == signature.read_text(
        encoding="utf-8"
    )
    validator = ROOT / "scripts" / "validate_release_artifacts.py"
    valid = subprocess.run(
        [sys.executable, str(validator), str(tmp_path), "--channel", "alpha"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert valid.returncode == 0, valid.stdout + valid.stderr

    updater.write_bytes(b"corrupted")
    invalid = subprocess.run(
        [sys.executable, str(validator), str(tmp_path), "--channel", "alpha"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid.returncode != 0
    assert "checksum mismatch" in (invalid.stdout + invalid.stderr).lower()


def test_installer_and_data_paths_are_separate() -> None:
    tauri = json.loads(
        (ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )
    assert tauri["bundle"]["windows"]["nsis"]["installMode"] == "currentUser"
    config = (ROOT / "backend" / "app" / "core" / "config.py").read_text(
        encoding="utf-8"
    )
    assert 'Path(base) / "OIHK-Basic"' in config
    build = (ROOT / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")
    assert "%APPDATA%" not in build


def test_release_workflow_never_publishes_candidate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-windows.yml").read_text(
        encoding="utf-8"
    )
    assert "gh release create $tag --draft --prerelease" in workflow
    assert "Release candidate must remain draft and prerelease." in workflow
    assert "--latest" not in workflow


def test_official_updater_is_signature_gated_to_release_builds() -> None:
    cargo = (ROOT / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    rust = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    base_config = (ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    assert 'tauri-plugin-updater = "2"' in cargo
    assert '#[cfg(feature = "updater-release")]' in rust
    assert "TAURI_SIGNING_PRIVATE_KEY" not in base_config
    assert '"pubkey"' not in base_config
    build = (ROOT / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")
    assert "--example verify_update_signature" in build
    assert "$env:TAURI_UPDATER_PUBLIC_KEY" in build
    assert not (
        ROOT / "src-tauri" / "src" / "bin" / "verify_update_signature.rs"
    ).exists()
    assert (ROOT / "src-tauri" / "examples" / "verify_update_signature.rs").is_file()


def test_official_build_smokes_clean_install_restart_and_uninstall() -> None:
    build = (ROOT / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")
    smoke = (ROOT / "scripts" / "smoke-installer.ps1").read_text(encoding="utf-8")
    assert "scripts\\smoke-installer.ps1" in build
    assert "/D=$installDir" in smoke
    assert '$env:PATH = "$env:SystemRoot\\System32;$env:SystemRoot"' in smoke
    assert "Installed data did not survive restart" in smoke
    assert "The NSIS uninstaller removed the user's SQLite database." in smoke
    assert (
        "The NSIS uninstaller removed the user's managed evidence directory." in smoke
    )


def test_packaged_sidecar_ignores_working_directory_configuration_and_tracks_parent() -> (
    None
):
    rust = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    backend = (ROOT / "backend" / "run.py").read_text(encoding="utf-8")
    assert 'env("OIHK_DESKTOP_PACKAGED", "1")' in rust
    assert '"--parent-pid"' in rust
    assert '"--data-dir"' in rust
    assert "current_dir(data_dir)" in rust
    assert "candidates.push(current_dir.join(backend_name))" not in rust
    assert ".eval(" not in rust
    assert "oihk-parent-watchdog" in backend
