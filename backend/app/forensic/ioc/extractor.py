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

_LOWERCASED_TYPES = frozenset({"email", "url", "domain"})
_MAX_MATCHES = 200


def _is_routable_ipv4(value: str) -> bool:
    """Reject dotted quads whose octets are out of range.

    ``\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b`` is a shape, not an address: it accepts
    ``999.999.999.999`` and reports it at the same 0.9 confidence as a real
    address. Range-checking here keeps a malformed string from entering an
    exhibit as a high-confidence indicator.
    """
    parts = value.split(".")
    if len(parts) != 4:
        return False
    return all(part.isdigit() and len(part) <= 3 and int(part) <= 255 for part in parts)


_VALIDATORS = {"ipv4": _is_routable_ipv4}


def _fair_share(by_type: dict[str, list[IocMatch]], ceiling: int) -> list[IocMatch]:
    """Fill ``ceiling`` slots by rotating across indicator types.

    A single global sort truncated at 200 lets the highest-confidence type
    consume every slot: an archive with more than 200 email addresses in it
    reported *only* email addresses, and the hashes, CVEs and URLs beside them
    were dropped with no indication that anything had been discarded. Rotating
    means each type present keeps its highest-confidence findings, and a chatty
    type only spends the capacity nobody else claims.
    """
    remaining = {
        ioc_type: list(matches)
        for ioc_type, matches in sorted(by_type.items(), key=lambda item: -item[1][0].confidence)
        if matches
    }
    selected: list[IocMatch] = []
    while remaining and len(selected) < ceiling:
        for ioc_type in list(remaining):
            if len(selected) >= ceiling:
                break
            selected.append(remaining[ioc_type].pop(0))
            if not remaining[ioc_type]:
                del remaining[ioc_type]
    selected.sort(key=lambda match: match.confidence, reverse=True)
    return selected


def extract_iocs(text: str) -> IocReport:
    """Extract IOCs from text content."""
    by_type: dict[str, list[IocMatch]] = {}
    seen: set[tuple[str, str]] = set()

    for ioc_type, _label, pattern in _IOC_PATTERNS:
        validator = _VALIDATORS.get(ioc_type)
        for match in pattern.finditer(text):
            raw = match.group().strip()
            value = raw.lower() if ioc_type in _LOWERCASED_TYPES else raw
            if validator is not None and not validator(value):
                continue
            key = (ioc_type, value)
            if key in seen:
                continue
            seen.add(key)
            by_type.setdefault(ioc_type, []).append(
                IocMatch(
                    type=ioc_type,
                    value=value,
                    display=raw,
                    confidence=_confidence(ioc_type),
                    offset=match.start(),
                )
            )

    return IocReport(matches=_fair_share(by_type, _MAX_MATCHES), asn_lookups=[])


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
