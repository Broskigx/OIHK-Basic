#!/usr/bin/env python3
"""Generate the ignored Tauri release overlay from a public updater key."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "src-tauri" / "tauri.release.conf.json"
CHANNEL_ENDPOINTS = {
    "alpha": "https://github.com/Broskigx/OIHK-Basic/releases/download/basic-alpha/latest-alpha.json",
    "beta": "https://github.com/Broskigx/OIHK-Basic/releases/download/basic-beta/latest-beta.json",
    "stable": "https://github.com/Broskigx/OIHK-Basic/releases/download/basic-stable/latest-stable.json",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=CHANNEL_ENDPOINTS, default="alpha")
    parser.add_argument(
        "--public-key", default=os.environ.get("TAURI_UPDATER_PUBLIC_KEY", "")
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    public_key = args.public_key.strip()
    if len(public_key) < 32:
        raise SystemExit(
            "TAURI_UPDATER_PUBLIC_KEY is required. Store the public key as a GitHub repository variable."
        )
    if "PRIVATE" in public_key.upper() or "SECRET" in public_key.upper():
        raise SystemExit(
            "Refusing to place private key material in a Tauri configuration."
        )

    config = {
        "bundle": {
            "createUpdaterArtifacts": True,
            "externalBin": ["../dist/sidecar/oihk-basic-backend"],
        },
        "plugins": {
            "updater": {
                "pubkey": public_key,
                "endpoints": [CHANNEL_ENDPOINTS[args.channel]],
                "windows": {"installMode": "passive"},
            }
        },
    }
    output = args.output.resolve()
    if ROOT not in output.parents:
        raise SystemExit("The release configuration must remain inside the repository.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output.relative_to(ROOT)} for the {args.channel} channel")


if __name__ == "__main__":
    main()
