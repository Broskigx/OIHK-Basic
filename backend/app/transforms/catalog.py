"""Transform catalog for OIHK Basic — defines available transforms."""

import logging

import httpx

from app.core.config import get_settings
from app.services.safe_http import (
    OutboundRequestError,
    get_json_bounded,
    require_hostname,
    require_ipv4,
    resolve_hostname_a_record,
)
from app.transforms.base import TransformSpec

logger = logging.getLogger(__name__)

# A transform only checks that the entity *type* matches its declared inputs.
# The entity *value* is free-form investigation data — it can be typed in, or
# arrive through a CSV import or an ingested source — so every handler
# revalidates it before it reaches a URL or a resolver.


async def _dns_resolve(session, *, entity) -> list[dict]:
    """Resolve domain to IP."""
    try:
        ip = await resolve_hostname_a_record(entity.value)
    except OutboundRequestError:
        return []
    return [{"type": "ip", "value": ip, "display": ip, "confidence": 0.8, "relation": "resolves_to"}]


async def _whois_lookup(session, *, entity) -> list[dict]:
    """Look up domain registration info via RDAP."""
    results = []
    try:
        domain = require_hostname(entity.value)
    except OutboundRequestError:
        return results
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            data = await get_json_bounded(
                client,
                f"https://rdap.verisign.com/com/v1/domain/{domain}",
                max_bytes=get_settings().max_lookup_response_bytes,
            )
            for ent in (data or {}).get("entities", []) or []:
                vcard = ent.get("vcardArray") if isinstance(ent, dict) else None
                if not isinstance(vcard, list) or len(vcard) < 2 or not isinstance(vcard[1], list):
                    continue
                for item in vcard[1]:
                    if isinstance(item, list) and len(item) > 3 and item[0] == "fn":
                        results.append(
                            {
                                "type": "organization",
                                "value": str(item[3]),
                                "display": str(item[3]),
                                "confidence": 0.6,
                                "relation": "registered_to",
                            }
                        )
    except Exception:
        logger.warning("WHOIS/RDAP lookup failed for domain %r", entity.value, exc_info=True)
    return results


async def _cert_search(session, *, entity) -> list[dict]:
    """Search crt.sh for SSL certificates."""
    results = []
    try:
        domain = require_hostname(entity.value)
    except OutboundRequestError:
        return results
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            data = await get_json_bounded(
                client,
                "https://crt.sh/",
                max_bytes=get_settings().max_lookup_response_bytes,
                params={"q": f"%.{domain}", "output": "json"},
            )
            seen: set[str] = set()
            for entry in (data or [])[:10]:
                if not isinstance(entry, dict):
                    continue
                for cn in str(entry.get("name_value", "")).split("\n"):
                    cn = cn.strip()
                    if cn and cn not in seen and cn.endswith("." + domain):
                        seen.add(cn)
                        results.append(
                            {
                                "type": "domain",
                                "value": cn.lower(),
                                "display": cn,
                                "confidence": 0.7,
                                "relation": "has_subdomain",
                            }
                        )
    except Exception:
        logger.warning("Certificate search failed for domain %r", entity.value, exc_info=True)
    return results


async def _shodan_like(session, *, entity) -> list[dict]:
    """Lookup IP info via RDAP."""
    results = []
    try:
        address = require_ipv4(entity.value)
    except OutboundRequestError:
        return results
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            data = await get_json_bounded(
                client,
                f"https://rdap.arin.net/registry/ip/{address}",
                max_bytes=get_settings().max_lookup_response_bytes,
            )
            if isinstance(data, dict) and "name" in data:
                results.append(
                    {
                        "type": "note",
                        "value": str(data["name"]),
                        "display": f"Network: {data['name']}",
                        "confidence": 0.6,
                        "relation": "part_of",
                    }
                )
    except Exception:
        logger.warning("IP RDAP lookup failed for address %r", entity.value, exc_info=True)
    return results


async def _email_to_domain(session, *, entity) -> list[dict]:
    """Deterministically extract the domain portion of an email address."""
    domain = entity.value.split("@")[-1] if "@" in entity.value else ""
    if domain:
        return [
            {
                "type": "domain",
                "value": domain,
                "display": domain,
                "confidence": 0.9,
                "relation": "uses_domain",
            }
        ]
    return []


# Built-in transforms for OIHK Basic
BUILT_IN_TRANSFORMS = [
    TransformSpec(
        id="dns_resolve",
        title="DNS Resolution",
        description="Resolve a domain name to its IPv4 address",
        input_types=["domain"],
        output_types=["ip"],
        category="infrastructure",
        handler=_dns_resolve,
    ),
    TransformSpec(
        id="whois_lookup",
        title="WHOIS/RDAP Lookup",
        description="Look up domain registration information via RDAP",
        input_types=["domain"],
        output_types=["organization"],
        category="registration",
        handler=_whois_lookup,
    ),
    TransformSpec(
        id="cert_search",
        title="Certificate Search (crt.sh)",
        description="Search SSL certificate transparency logs for subdomains",
        input_types=["domain"],
        output_types=["domain"],
        category="infrastructure",
        handler=_cert_search,
    ),
    TransformSpec(
        id="ip_rdap",
        title="IP RDAP Lookup",
        description="Look up IP address registration via ARIN RDAP",
        input_types=["ip"],
        output_types=["note"],
        category="infrastructure",
        handler=_shodan_like,
    ),
    TransformSpec(
        id="email_to_domain",
        title="Extract Domain from Email",
        description="Extract the domain name from an email address",
        input_types=["email"],
        output_types=["domain"],
        category="identity",
        handler=_email_to_domain,
    ),
]
