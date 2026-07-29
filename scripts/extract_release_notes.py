#!/usr/bin/env python3
"""Extract the canonical VERSION section from CHANGELOG.md."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^## \[?{re.escape(version)}\]?[^\n]*\n(?P<body>.*?)(?=^## |\Z)",
        changelog,
    )
    if not match:
        raise SystemExit(f"Missing CHANGELOG.md section for {version}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(match.group("body").strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
