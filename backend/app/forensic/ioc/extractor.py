"""IOC extraction for OIHK Basic."""

import re

from app.forensic.types import IocMatch, IocReport

_IOC_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("email", "Email address", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("url", "URL", re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+")),
    ("ipv4", "IPv4 address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("md5", "MD5 hash", re.compile(r"\b[a-fA-F0-9]{32}\b")),
    ("sha1", "SHA-1 hash", re.compile(r"\b[a-fA-F0-9]{40}\b")),
    ("sha256", "SHA-256 hash", re.compile(r"\b[a-fA-F0-9]{64}\b")),
    ("domain", "Domain name", re.compile(r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}")),
    ("cve", "CVE identifier", re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)),
    ("btc", "Bitcoin address", re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")),
    ("eth", "Ethereum address", re.compile(r"\b0x[a-fA-F0-9]{40}\b")),
]


def extract_iocs(text: str) -> IocReport:
    """Extract IOCs from text content."""
    matches: list[IocMatch] = []
    seen: set[tuple[str, str]] = set()
    asn_lookups: list[dict[str, str]] = []

    for ioc_type, _label, pattern in _IOC_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group().strip().lower() if ioc_type in ("email", "url", "domain") else match.group().strip()
            key = (ioc_type, value)
            if key not in seen:
                seen.add(key)
                matches.append(
                    IocMatch(
                        type=ioc_type,
                        value=value,
                        display=match.group().strip(),
                        confidence=_confidence(ioc_type),
                        offset=match.start(),
                    )
                )

    matches.sort(key=lambda m: m.confidence, reverse=True)
    return IocReport(matches=matches[:200], asn_lookups=asn_lookups)


def _confidence(ioc_type: str) -> float:
    return {
        "email": 0.9,
        "ipv4": 0.9,
        "md5": 0.85,
        "sha1": 0.85,
        "sha256": 0.85,
        "cve": 0.85,
        "btc": 0.8,
        "eth": 0.8,
        "url": 0.7,
        "domain": 0.6,
    }.get(ioc_type, 0.5)
