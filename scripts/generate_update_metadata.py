#!/usr/bin/env python3
"""Generate signed-updater metadata and a checksum-rich release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_notes(version: str) -> str:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^## \[?{re.escape(version)}\]?[^\n]*\n(?P<body>.*?)(?=^## |\Z)",
        changelog,
    )
    if not match:
        raise SystemExit(f"CHANGELOG.md has no release notes for {version}")
    return match.group("body").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--channel", choices=("alpha", "beta", "stable"), default="alpha"
    )
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--updater", type=Path, required=True)
    parser.add_argument("--signature", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    expected_tag = f"basic-v{version}"
    if args.tag != expected_tag:
        raise SystemExit(
            f"Tag {args.tag!r} does not match canonical version ({expected_tag})"
        )
    artifacts = (
        args.installer.resolve(),
        args.updater.resolve(),
        args.signature.resolve(),
    )
    for artifact in artifacts:
        if not artifact.is_file() or artifact.stat().st_size == 0:
            raise SystemExit(
                f"Required release artifact is missing or empty: {artifact}"
            )

    signature = args.signature.read_text(encoding="utf-8").strip()
    if len(signature) < 32:
        raise SystemExit("The updater signature is missing or invalid.")
    base_url = (
        f"https://github.com/Broskigx/OIHK-Basic/releases/download/{quote(args.tag)}"
    )
    published = (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    updater_metadata = {
        "version": version,
        "notes": release_notes(version),
        "pub_date": published,
        "platforms": {
            "windows-x86_64": {
                "signature": signature,
                "url": f"{base_url}/{quote(args.updater.name)}",
            }
        },
    }
    manifest = {
        "product": "OIHK Basic",
        "version": version,
        "tag": args.tag,
        "channel": args.channel,
        "published_at": published,
        "artifacts": [
            {
                "name": artifact.name,
                "bytes": artifact.stat().st_size,
                "sha256": sha256(artifact),
            }
            for artifact in artifacts
        ],
    }

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    update_path = output / f"latest-{args.channel}.json"
    manifest_path = output / "release-manifest.json"
    update_path.write_text(
        json.dumps(updater_metadata, indent=2) + "\n", encoding="utf-8"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for artifact in (*artifacts, update_path, manifest_path):
        checksum_path = output / f"{artifact.name}.sha256"
        checksum_path.write_text(
            f"{sha256(artifact)}  {artifact.name}\n", encoding="ascii"
        )
    print(f"Generated signed update metadata for {version} ({args.channel})")


if __name__ == "__main__":
    main()
