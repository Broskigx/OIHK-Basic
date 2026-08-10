"""Shared bootstrap for backend tests."""

from __future__ import annotations

import os

# System Link tests sign module packages with ephemeral development publisher
# keys. The host only accepts development channel signatures when this flag is
# explicitly enabled, so the backend test session opts in before the first
# Settings instance is cached. Production code defaults to reject (release
# anchors only).
os.environ.setdefault("OIHK_SYSTEM_LINK_ALLOW_DEV_PUBLISHERS", "true")
