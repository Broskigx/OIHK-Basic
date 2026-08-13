"""Developer entrypoints must resolve the repository's real configuration."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_desktop_scripts_pin_the_external_tauri_config() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]

    assert scripts["desktop:dev"].endswith("--config ../src-tauri/tauri.conf.json")
    assert scripts["desktop:build"].endswith("--config ../src-tauri/tauri.local.conf.json")


def test_windows_web_dev_uses_the_documented_virtual_environment() -> None:
    script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")

    assert 'backendDir ".venv\\Scripts\\python.exe"' in script
    assert "& $python -m uvicorn" in script
    assert "$jobs += $backendJob" in script
    assert "$jobs += $frontendJob" in script


def test_unix_builders_use_the_canonical_lint_and_tauri_paths() -> None:
    linux = (ROOT / "scripts" / "build-linux.sh").read_text(encoding="utf-8")
    macos = (ROOT / "scripts" / "build-macos.sh").read_text(encoding="utf-8")

    assert '--config "$BACKEND_DIR/pyproject.toml"' in linux
    assert '--config "$BACKEND_DIR/pyproject.toml"' in macos
    assert 'cd "$PROJECT_ROOT"' in linux
    assert '--config "src-tauri/tauri.sidecar.conf.json"' in linux
