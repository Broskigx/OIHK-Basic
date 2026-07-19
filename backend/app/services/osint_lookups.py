"""OSINT lookup services for OIHK Basic — public API lookups (DNS, RDAP, crt.sh, GeoIP)."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import List

import httpx


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

    # DNS resolution
    try:
        ip_address = socket.gethostbyname(domain)
        findings.append(LookupFinding(source="dns", type="ip", value=ip_address, detail=f"IPv4 address for {domain}"))
    except socket.gaierror as e:
        errors.append(f"DNS resolution failed: {e}")

    # RDAP/WHOIS via crt.sh for certificates
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://crt.sh/?q=%25.{domain}&output=json")
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    seen_names: set[str] = set()
                    for entry in data[:10]:
                        name = entry.get("name_value", "")
                        for cn in name.split("\n"):
                            cn = cn.strip()
                            if cn and cn not in seen_names and cn.endswith("." + domain):
                                seen_names.add(cn)
                                findings.append(
                                    LookupFinding(source="crt.sh", type="subdomain", value=cn, detail=f"SSL certificate subject alternative name")
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


async def lookup_ip(ip: str) -> LookupResult:
    findings: list[LookupFinding] = []
    errors: list[str] = []

    # RDAP/WHOIS
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://rdap.arin.net/registry/ip/{ip}")
            if resp.status_code == 200:
                data = resp.json()
                if "name" in data:
                    findings.append(LookupFinding(source="arin-rdap", type="net_name", value=data["name"],
                                                   detail="Network name registered with ARIN"))
                for entity in data.get("entities", []):
                    if "vcardArray" in entity:
                        for item in entity["vcardArray"][1]:
                            if item[0] == "fn":
                                findings.append(
                                    LookupFinding(source="arin-rdap", type="org", value=item[3],
                                                   detail="Organization registered with ARIN"))
            elif resp.status_code in (404, 422):
                # Try RDAP from other RIRs
                resp2 = await client.get(f"https://rdap.db.ripe.net/ip/{ip}")
                if resp2.status_code == 200:
                    data = resp2.json()
                    for entity in data.get("entities", []):
                        if "vcardArray" in entity:
                            for item in entity["vcardArray"][1]:
                                if item[0] == "fn":
                                    findings.append(
                                        LookupFinding(source="ripe-rdap", type="org", value=item[3],
                                                       detail="Organization registered with RIPE"))
    except Exception as e:
        errors.append(f"RDAP lookup failed: {e}")

    return LookupResult(value=ip, kind="ip", findings=findings, errors=errors)


async def lookup_email(email: str) -> LookupResult:
    findings: list[LookupFinding] = []
    errors: list[str] = []

    domain = email.split("@")[-1] if "@" in email else ""
    if domain:
        findings.append(LookupFinding(source="parsed", type="domain", value=domain,
                                       detail=f"Email domain: {domain}"))

    return LookupResult(value=email, kind="email", findings=findings, errors=errors)
