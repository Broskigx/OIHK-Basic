"""OSINT lookup services for OIHK Basic — public API lookups (DNS, RDAP, crt.sh, GeoIP)."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.services.safe_http import (
    OutboundRequestError,
    get_json_bounded,
    require_hostname,
    require_ipv4,
    resolve_hostname_a_record,
)


@dataclass
class LookupFinding:
    source: str
    type: str
    value: str
    detail: str


@dataclass
class LookupResult:
    value: str
    kind: str
    findings: list[LookupFinding]
    errors: list[str] = field(default_factory=list)

    # Domain-specific
    ip_address: str | None = None

    # IP-specific
    asn: str | None = None
    country: str | None = None
    org: str | None = None

    def summary(self) -> str:
        lines = [f"Lookup: {self.value} ({self.kind})"]
        for f in self.findings:
            lines.append(f"  [{f.source}] {f.type}: {f.value} — {f.detail}")
        return "\n".join(lines)


async def identify_kind(value: str) -> str:
    """Identify the kind of value: domain, ip, email, or unknown."""
    import re

    value = value.strip().lower()
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", value):
        return "ip"
    if re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value):
        return "email"
    if re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?\.[a-z]{2,}$", value):
        return "domain"
    return "unknown"


async def lookup_domain(domain: str) -> LookupResult:
    findings: list[LookupFinding] = []
    errors: list[str] = []
    ip_address: str | None = None

    # Validate before any network use: the value is investigation data and is
    # about to be interpolated into a third-party URL and passed to a resolver.
    try:
        domain = require_hostname(domain)
    except OutboundRequestError as exc:
        return LookupResult(value=domain, kind="domain", findings=[], errors=[str(exc)])

    max_bytes = get_settings().max_lookup_response_bytes

    # DNS resolution — offloaded to a worker thread so a slow or blackholed
    # resolver cannot stall the event loop for every other request.
    try:
        ip_address = await resolve_hostname_a_record(domain)
        findings.append(LookupFinding(source="dns", type="ip", value=ip_address, detail=f"IPv4 address for {domain}"))
    except OutboundRequestError as e:
        errors.append(str(e))

    # Certificate transparency via crt.sh
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            data = await get_json_bounded(
                client,
                "https://crt.sh/",
                max_bytes=max_bytes,
                params={"q": f"%.{domain}", "output": "json"},
            )
            if data:
                seen_names: set[str] = set()
                for entry in data[:10]:
                    name = entry.get("name_value", "")
                    for cn in name.split("\n"):
                        cn = cn.strip()
                        if cn and cn not in seen_names and cn.endswith("." + domain):
                            seen_names.add(cn)
                            findings.append(
                                LookupFinding(
                                    source="crt.sh",
                                    type="subdomain",
                                    value=cn,
                                    detail="SSL certificate subject alternative name",
                                )
                            )
    except Exception as e:
        errors.append(f"crt.sh lookup failed: {e}")

    return LookupResult(
        value=domain,
        kind="domain",
        findings=findings,
        errors=errors,
        ip_address=ip_address,
    )


def _rdap_org_findings(data: dict, source: str) -> list[LookupFinding]:
    findings: list[LookupFinding] = []
    for entity in data.get("entities", []) or []:
        vcard = entity.get("vcardArray") if isinstance(entity, dict) else None
        if not isinstance(vcard, list) or len(vcard) < 2 or not isinstance(vcard[1], list):
            continue
        for item in vcard[1]:
            if isinstance(item, list) and len(item) > 3 and item[0] == "fn":
                findings.append(
                    LookupFinding(
                        source=source,
                        type="org",
                        value=str(item[3]),
                        detail=f"Organization registered with {source.split('-')[0].upper()}",
                    )
                )
    return findings


async def lookup_ip(ip: str) -> LookupResult:
    findings: list[LookupFinding] = []
    errors: list[str] = []

    # Reject anything that is not a literal IPv4 address before it reaches the
    # RDAP URL path.
    try:
        ip = require_ipv4(ip)
    except OutboundRequestError as exc:
        return LookupResult(value=ip, kind="ip", findings=[], errors=[str(exc)])

    max_bytes = get_settings().max_lookup_response_bytes

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            data = await get_json_bounded(
                client,
                f"https://rdap.arin.net/registry/ip/{ip}",
                max_bytes=max_bytes,
            )
            if isinstance(data, dict):
                if "name" in data:
                    findings.append(
                        LookupFinding(
                            source="arin-rdap",
                            type="net_name",
                            value=str(data["name"]),
                            detail="Network name registered with ARIN",
                        )
                    )
                findings.extend(_rdap_org_findings(data, "arin-rdap"))
            else:
                # ARIN did not serve this range; fall back to the RIPE mirror.
                fallback = await get_json_bounded(
                    client,
                    f"https://rdap.db.ripe.net/ip/{ip}",
                    max_bytes=max_bytes,
                )
                if isinstance(fallback, dict):
                    findings.extend(_rdap_org_findings(fallback, "ripe-rdap"))
    except Exception as e:
        errors.append(f"RDAP lookup failed: {e}")

    return LookupResult(value=ip, kind="ip", findings=findings, errors=errors)


async def lookup_email(email: str) -> LookupResult:
    findings: list[LookupFinding] = []
    errors: list[str] = []

    domain = email.split("@")[-1] if "@" in email else ""
    if domain:
        findings.append(LookupFinding(source="parsed", type="domain", value=domain, detail=f"Email domain: {domain}"))

    return LookupResult(value=email, kind="email", findings=findings, errors=errors)
