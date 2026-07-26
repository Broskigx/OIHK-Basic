#!/usr/bin/env python3
"""Validate or synchronize every build manifest with the canonical VERSION."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
CHANNEL = "alpha"


def canonical_version() -> str:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        raise SystemExit(f"VERSION is not valid SemVer: {version!r}")
    return version


def _replace_toml_version(path: Path, version: str) -> str:
    source = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^(version\s*=\s*")[^"]+(")',
        rf"\g<1>{version}\g<2>",
        source,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"Could not locate package version in {path}")
    return updated


def _replace_cargo_lock_version(path: Path, version: str) -> str:
    source = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?ms)(\[\[package\]\]\r?\nname = "oihk-basic-desktop"\r?\nversion = ")[^"]+(")',
        rf"\g<1>{version}\g<2>",
        source,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"Could not locate OIHK Basic package version in {path}")
    return updated


def expected_files(version: str) -> dict[Path, str]:
    tauri_config_path = ROOT / "src-tauri" / "tauri.conf.json"
    tauri_config = json.loads(tauri_config_path.read_text(encoding="utf-8"))
    tauri_config["version"] = version

    package_path = ROOT / "frontend" / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = version

    package_lock_path = ROOT / "frontend" / "package-lock.json"
    package_lock = json.loads(package_lock_path.read_text(encoding="utf-8"))
    package_lock["version"] = version
    package_lock["packages"][""]["version"] = version

    return {
        ROOT / "src-tauri" / "Cargo.toml": _replace_toml_version(
            ROOT / "src-tauri" / "Cargo.toml", version
        ),
        ROOT / "backend" / "pyproject.toml": _replace_toml_version(
            ROOT / "backend" / "pyproject.toml", version
        ),
        ROOT / "src-tauri" / "Cargo.lock": _replace_cargo_lock_version(
            ROOT / "src-tauri" / "Cargo.lock", version
        ),
        tauri_config_path: json.dumps(tauri_config, indent=2, ensure_ascii=False)
        + "\n",
        package_path: json.dumps(package, indent=2, ensure_ascii=False) + "\n",
        package_lock_path: json.dumps(package_lock, indent=2, ensure_ascii=False)
        + "\n",
        ROOT / "backend" / "app" / "version.py": (
            '"""Generated product version.\n\n'
            "The canonical value lives in the repository-root VERSION file. Run\n"
            "``python scripts/version.py sync`` after changing it.\n"
            '"""\n\n'
            f'PRODUCT_VERSION = "{version}"\n'
            f'UPDATE_CHANNEL = "{CHANNEL}"\n'
        ),
        ROOT / "frontend" / "src" / "version.ts": (
            "// Generated from the repository-root VERSION file by scripts/version.py.\n"
            f'export const PRODUCT_VERSION = "{version}";\n'
            f'export const UPDATE_CHANNEL = "{CHANNEL}";\n'
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "sync"))
    args = parser.parse_args()
    version = canonical_version()

    mismatches: list[str] = []
    for path, expected in expected_files(version).items():
        actual = path.read_text(encoding="utf-8") if path.exists() else ""
        if actual == expected:
            continue
        if args.command == "sync":
            path.write_text(expected, encoding="utf-8", newline="\n")
        else:
            mismatches.append(str(path.relative_to(ROOT)))

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"(?m)^## \[?{re.escape(version)}\]?", changelog):
        mismatches.append("CHANGELOG.md (missing current version heading)")

    if mismatches:
        raise SystemExit(
            "Version mismatch. Run `python scripts/version.py sync`:\n- "
            + "\n- ".join(mismatches)
        )
    print(f"Version metadata is synchronized: {version} ({CHANNEL})")


if __name__ == "__main__":
    main()
