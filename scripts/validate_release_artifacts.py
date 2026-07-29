#!/usr/bin/env python3
"""Fail a release if any signed Windows updater artifact is absent or inconsistent."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--channel", choices=("alpha", "beta", "stable"), default="alpha"
    )
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        raise SystemExit("Release artifact directory is missing.")
    metadata = root / f"latest-{args.channel}.json"
    manifest_path = root / "release-manifest.json"
    if not metadata.is_file() or not manifest_path.is_file():
        raise SystemExit("Update metadata or release manifest is missing.")
    update = json.loads(metadata.read_text(encoding="utf-8"))
    windows = update.get("platforms", {}).get("windows-x86_64", {})
    if not windows.get("signature") or not str(windows.get("url", "")).startswith(
        "https://"
    ):
        raise SystemExit("Windows update metadata lacks a signature or HTTPS URL.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest.get("version", ""))
    tag = str(manifest.get("tag", ""))
    if (
        manifest.get("product") != "OIHK Basic"
        or manifest.get("channel") != args.channel
        or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version)
        or tag != f"basic-v{version}"
        or update.get("version") != version
        or not update.get("pub_date")
    ):
        raise SystemExit(
            "Release identity, version, tag, channel, or publication date is invalid."
        )

    items = manifest.get("artifacts", [])
    if not isinstance(items, list) or not items:
        raise SystemExit("Release manifest has no artifacts.")
    names = [str(item.get("name", "")) for item in items if isinstance(item, dict)]
    if len(names) != len(items) or len(set(names)) != len(names):
        raise SystemExit("Release manifest artifact names must be unique.")
    if any(
        not name or Path(name).name != name or "/" in name or "\\" in name
        for name in names
    ):
        raise SystemExit("Release manifest contains an unsafe artifact name.")

    installers = [name for name in names if name.endswith("-setup.exe")]
    updaters = [name for name in names if name.endswith(".nsis.zip")]
    signatures = [name for name in names if name.endswith(".nsis.zip.sig")]
    if len(installers) != 1:
        raise SystemExit("NSIS installer is missing.")
    if len(updaters) != 1:
        raise SystemExit("Tauri updater archive is missing.")
    if len(signatures) != 1:
        raise SystemExit("Tauri updater signature is missing.")

    signature_path = root / signatures[0]
    signature = signature_path.read_text(encoding="utf-8").strip()
    expected_url = f"https://github.com/Broskigx/OIHK-Basic/releases/download/{quote(tag)}/{quote(updaters[0])}"
    if len(signature) < 32 or windows["signature"].strip() != signature:
        raise SystemExit("Updater metadata does not match the detached signature.")
    if windows["url"] != expected_url:
        raise SystemExit("Updater metadata URL does not match the signed archive.")

    for item in items:
        artifact = root / item["name"]
        if (
            not artifact.is_file()
            or artifact.stat().st_size != item.get("bytes")
            or digest(artifact) != item.get("sha256")
        ):
            raise SystemExit(f"Artifact checksum mismatch: {item['name']}")
        checksum_path = root / f"{item['name']}.sha256"
        expected_checksum = f"{item['sha256']}  {item['name']}"
        if (
            not checksum_path.is_file()
            or checksum_path.read_text(encoding="ascii").strip() != expected_checksum
        ):
            raise SystemExit(f"Artifact checksum file mismatch: {item['name']}")

    for generated in (metadata, manifest_path):
        checksum_path = root / f"{generated.name}.sha256"
        expected_checksum = f"{digest(generated)}  {generated.name}"
        if (
            not checksum_path.is_file()
            or checksum_path.read_text(encoding="ascii").strip() != expected_checksum
        ):
            raise SystemExit(f"Metadata checksum file mismatch: {generated.name}")
    print("Release artifacts and signed updater metadata are complete.")


if __name__ == "__main__":
    main()
