"""Entity detectors for OIHK Basic."""

import re

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_URL = re.compile(r"https?://[^\s<>\"']+")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SHA256 = re.compile(r"\b[a-fA-F0-9]{64}\b")


def detect_types(value: str) -> list[str]:
    """Detect the type(s) of a value."""
    types = []
    if _SHA256.fullmatch(value):
        types.append("sha256")
    if _IPV4.fullmatch(value):
        types.append("ip")
    if _EMAIL.fullmatch(value):
        types.append("email")
    if _URL.match(value):
        types.append("url")
    if not types and "." in value and not value.endswith("."):
        types.append("domain")
    if not types:
        types.append("note")
    return types
