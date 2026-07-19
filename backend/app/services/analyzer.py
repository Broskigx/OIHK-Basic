"""Text analysis and entity extraction for OIHK Basic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+")
_DOMAIN_PATTERN = re.compile(r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}")
_IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HASH_PATTERN = re.compile(r"\b[a-fA-F0-9]{32}\b|\b[a-fA-F0-9]{40}\b|\b[a-fA-F0-9]{64}\b")


@dataclass
class ExtractedEntity:
    type: str
    value: str
    display: str
    confidence: float
    properties: dict = field(default_factory=dict)


def normalize_value(entity_type: str, label: str) -> str:
    """Normalize an entity value for deduplication."""
    if entity_type in ("email", "url", "domain", "ip"):
        return label.strip().lower()
    if entity_type in ("sha256", "sha1", "md5"):
        return label.strip().lower()
    return " ".join(label.strip().split())


def analyze_text(text: str) -> list[ExtractedEntity]:
    """Extract entities from free text."""
    entities: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()

    # Emails
    for match in _EMAIL_PATTERN.finditer(text):
        value = match.group().lower()
        key = ("email", value)
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(type="email", value=value, display=match.group(), confidence=0.9))

    # URLs
    for match in _URL_PATTERN.finditer(text):
        value = match.group().lower()
        key = ("url", value)
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(type="url", value=value, display=match.group(), confidence=0.85))

    # IPs
    for match in _IPV4_PATTERN.finditer(text):
        value = match.group()
        key = ("ip", value)
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(type="ip", value=value, display=value, confidence=0.8))

    # Hashes
    for match in _HASH_PATTERN.finditer(text):
        h = match.group().lower()
        if len(h) == 64:
            key = ("sha256", h)
            confidence = 0.85
        elif len(h) == 40:
            key = ("sha1", h)
            confidence = 0.85
        else:
            key = ("md5", h)
            confidence = 0.85
        if key not in seen:
            seen.add(key)
            entities.append(ExtractedEntity(type=key[0], value=h, display=match.group(), confidence=confidence))

    # Domains (catch broader, filter out emails and IPs)
    for match in _DOMAIN_PATTERN.finditer(text):
        value = match.group().lower()
        if not _EMAIL_PATTERN.fullmatch(match.group()) and not _IPV4_PATTERN.fullmatch(match.group()):
            key = ("domain", value)
            if key not in seen:
                seen.add(key)
                entities.append(ExtractedEntity(type="domain", value=value, display=match.group(), confidence=0.7))

    return entities
