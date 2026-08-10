"""Test bootstrap for repository-level portability and first-run checks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# System Link tests sign module packages with ephemeral development publisher
# keys. The host only accepts development channel signatures when this flag is
# explicitly enabled, so the test session opts in. Production code defaults to
# reject (release anchors only).
os.environ.setdefault("OIHK_SYSTEM_LINK_ALLOW_DEV_PUBLISHERS", "true")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
