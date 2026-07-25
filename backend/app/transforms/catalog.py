"""Transform catalog for OIHK Basic — defines available transforms."""

import httpx

from app.transforms.base import TransformSpec


async def _dns_resolve(session, *, entity) -> list[dict]:
    """Resolve domain to IP."""
    import socket

    try:
        ip = socket.gethostbyname(entity.value)
        return [{"type": "ip", "value": ip, "display": ip, "confidence": 0.8, "relation": "resolves_to"}]
    except Exception:
        return []


async def _whois_lookup(session, *, entity) -> list[dict]:
    """Look up domain registration info via RDAP."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://rdap.verisign.com/com/v1/domain/{entity.value}")
            if resp.status_code == 200:
                data = resp.json()
                for ent in data.get("entities", []):
                    for vcard in ent.get("vcardArray", [[]])[1:]:
                        for item in vcard:
                            if item[0] == "fn" and len(item) > 3:
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
        pass
    return results


async def _cert_search(session, *, entity) -> list[dict]:
    """Search crt.sh for SSL certificates."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"https://crt.sh/?q=%25.{entity.value}&output=json")
            if resp.status_code == 200:
                data = resp.json()
                seen: set[str] = set()
                for entry in data[:10]:
                    for cn in entry.get("name_value", "").split("\n"):
                        cn = cn.strip()
                        if cn and cn not in seen and cn.endswith("." + entity.value):
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
        pass
    return results


async def _shodan_like(session, *, entity) -> list[dict]:
    """Lookup IP info via RDAP."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://rdap.arin.net/registry/ip/{entity.value}")
            if resp.status_code == 200:
                data = resp.json()
                if "name" in data:
                    results.append(
                        {
                            "type": "note",
                            "value": data["name"],
                            "display": f"Network: {data['name']}",
                            "confidence": 0.6,
                            "relation": "part_of",
                        }
                    )
    except Exception:
        pass
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
