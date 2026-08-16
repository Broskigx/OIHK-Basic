"""Parsing of third-party lookup answers, which are hostile input by default.

A registry, a certificate-transparency mirror and a resolver are all outside
this application's control, and what they return lands in an investigation as
findings an analyst may promote into the graph. Two failure modes matter and
neither had coverage: a malformed answer that raises instead of degrading, and
a well-formed answer that asserts something about a target it was never asked
about.

No test here touches the network. The bounded-read helper is substituted, so
what is under test is the parsing and the filtering, not httpx.
"""

from __future__ import annotations

import pytest

from app.services import osint_lookups
from app.services.safe_http import OutboundRequestError


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if a code path reaches the network despite the substitutions."""
    calls: dict[str, list] = {"json": [], "resolve": []}

    async def unexpected_resolve(hostname, **kwargs):
        calls["resolve"].append(hostname)
        raise AssertionError(f"unexpected DNS resolution for {hostname!r}")

    async def unexpected_json(client, url, **kwargs):
        calls["json"].append(url)
        raise AssertionError(f"unexpected outbound request to {url!r}")

    monkeypatch.setattr(osint_lookups, "resolve_hostname_a_record", unexpected_resolve)
    monkeypatch.setattr(osint_lookups, "get_json_bounded", unexpected_json)
    return calls


def _crt_response(monkeypatch, payload, *, resolves_to: str | None = "192.0.2.10"):
    async def fake_resolve(hostname, **kwargs):
        if resolves_to is None:
            raise OutboundRequestError("DNS resolution failed")
        return resolves_to

    async def fake_json(client, url, **kwargs):
        return payload

    monkeypatch.setattr(osint_lookups, "resolve_hostname_a_record", fake_resolve)
    monkeypatch.setattr(osint_lookups, "get_json_bounded", fake_json)


# --- Validation happens before the network, not after -------------------------


@pytest.mark.asyncio
async def test_a_malformed_domain_never_reaches_the_network(no_network) -> None:
    """The value is investigation data: typed in, imported, or extracted.

    It is about to be interpolated into a third-party URL, so a value carrying
    a delimiter has to be refused rather than escaped. The substituted helpers
    raise if they are called at all, which is what makes "never reached the
    network" an assertion rather than an assumption.
    """
    result = await osint_lookups.lookup_domain("example.com/../../etc/passwd?x=1")

    assert result.findings == []
    assert result.errors and "not a valid hostname" in result.errors[0]
    assert no_network["json"] == [] and no_network["resolve"] == []


@pytest.mark.asyncio
async def test_a_value_that_is_not_an_ipv4_literal_never_reaches_rdap(no_network) -> None:
    result = await osint_lookups.lookup_ip("999.999.999.999")

    assert result.findings == []
    assert result.errors and "not a valid IPv4" in result.errors[0]
    assert no_network["json"] == []


@pytest.mark.asyncio
async def test_the_loose_kind_regex_is_backed_by_strict_validation() -> None:
    """`identify_kind` is a router, not a validator, and must not be mistaken for one.

    It classifies `999.999.999.999` as an IP because its pattern only counts
    digits. That is fine precisely because `lookup_ip` re-checks with a real
    address parser before building a URL — the test above proves it does.
    """
    assert await osint_lookups.identify_kind("999.999.999.999") == "ip"
    assert await osint_lookups.identify_kind("example.com") == "domain"
    assert await osint_lookups.identify_kind("someone@example.com") == "email"
    assert await osint_lookups.identify_kind("not a value") == "unknown"


# --- A third-party answer must not assert things about other targets ----------


@pytest.mark.asyncio
async def test_certificate_names_outside_the_queried_domain_are_discarded(monkeypatch) -> None:
    """The filter is the control that keeps a mirror from planting foreign names.

    crt.sh is queried with a wildcard and answers with whatever it holds. An
    answer that carries names belonging to another domain — through a poisoned
    mirror or simply a sloppy match — would otherwise become findings that an
    analyst could promote into the graph as subdomains of their target, which
    is a fabricated relationship inside evidence.
    """
    _crt_response(
        monkeypatch,
        [
            {"name_value": "api.example.com"},
            {"name_value": "evil.test"},
            {"name_value": "notexample.com"},
            {"name_value": "example.com.attacker.test"},
        ],
    )

    result = await osint_lookups.lookup_domain("example.com")
    subdomains = {f.value for f in result.findings if f.type == "subdomain"}

    assert subdomains == {"api.example.com"}


@pytest.mark.asyncio
async def test_multi_name_certificate_entries_are_split_and_deduplicated(monkeypatch) -> None:
    _crt_response(
        monkeypatch,
        [
            {"name_value": "a.example.com\nb.example.com"},
            {"name_value": "b.example.com"},
        ],
    )

    result = await osint_lookups.lookup_domain("example.com")
    subdomains = [f.value for f in result.findings if f.type == "subdomain"]

    assert sorted(subdomains) == ["a.example.com", "b.example.com"]
    assert len(subdomains) == len(set(subdomains)), "a repeated name must appear once"


@pytest.mark.asyncio
async def test_a_resolved_address_is_reported_as_its_own_finding(monkeypatch) -> None:
    _crt_response(monkeypatch, [], resolves_to="203.0.113.7")

    result = await osint_lookups.lookup_domain("example.com")

    assert result.ip_address == "203.0.113.7"
    assert any(f.type == "ip" and f.value == "203.0.113.7" for f in result.findings)


@pytest.mark.asyncio
async def test_a_failed_resolution_degrades_instead_of_losing_the_lookup(monkeypatch) -> None:
    """A name that does not resolve is an ordinary result, not an error state."""
    _crt_response(monkeypatch, [{"name_value": "mail.example.com"}], resolves_to=None)

    result = await osint_lookups.lookup_domain("example.com")

    assert result.ip_address is None
    assert result.errors, "the resolution failure has to be reported"
    assert any(f.value == "mail.example.com" for f in result.findings), (
        "one failed source must not discard what the others found"
    )


# --- A malformed answer degrades; it does not raise ---------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"unexpected": "object"}, id="object-instead-of-array"),
        pytest.param(["a bare string", 42], id="entries-that-are-not-objects"),
        pytest.param([{"name_value": None}], id="null-name"),
        pytest.param([{}], id="entry-without-the-field"),
    ],
)
@pytest.mark.asyncio
async def test_a_malformed_certificate_answer_is_reported_not_raised(monkeypatch, payload) -> None:
    """Whatever the mirror returns, the lookup answers rather than propagating.

    The DNS finding still has to survive: a broken second source must not
    discard a good first one.
    """
    _crt_response(monkeypatch, payload)

    result = await osint_lookups.lookup_domain("example.com")

    assert any(f.type == "ip" for f in result.findings)
    assert not any(f.type == "subdomain" for f in result.findings)


@pytest.mark.parametrize(
    "entities",
    [
        pytest.param([{"vcardArray": "not-a-list"}], id="vcard-not-a-list"),
        pytest.param([{"vcardArray": ["vcard"]}], id="vcard-too-short"),
        pytest.param([{"vcardArray": ["vcard", "not-a-list"]}], id="vcard-body-not-a-list"),
        pytest.param([{"vcardArray": ["vcard", [["fn"]]]}], id="fn-entry-too-short"),
        pytest.param(["a bare string"], id="entity-not-an-object"),
        pytest.param(None, id="entities-null"),
    ],
)
def test_malformed_rdap_vcards_yield_nothing_instead_of_raising(entities) -> None:
    """Every level of this structure is attacker-shaped and checked one at a time.

    Indexing `item[3]` without first proving the list is long enough is the
    IndexError this guards against, and it would surface as a failed lookup
    with a stack trace rather than an empty result.
    """
    assert osint_lookups._rdap_org_findings({"entities": entities}, "arin-rdap") == []


def test_a_well_formed_rdap_vcard_yields_the_organization() -> None:
    """Paired with the malformed cases: proves the parser is defensive, not inert."""
    findings = osint_lookups._rdap_org_findings(
        {"entities": [{"vcardArray": ["vcard", [["fn", {}, "text", "Example Networks LLC"]]]}]},
        "arin-rdap",
    )

    assert [f.value for f in findings] == ["Example Networks LLC"]
    assert findings[0].source == "arin-rdap"


@pytest.mark.asyncio
async def test_rdap_falls_back_to_ripe_when_arin_does_not_serve_the_range(monkeypatch) -> None:
    requested: list[str] = []

    async def fake_json(client, url, **kwargs):
        requested.append(url)
        if "arin" in url:
            return None
        return {"entities": [{"vcardArray": ["vcard", [["fn", {}, "text", "RIPE Holder"]]]}]}

    monkeypatch.setattr(osint_lookups, "get_json_bounded", fake_json)

    result = await osint_lookups.lookup_ip("198.51.100.4")

    assert len(requested) == 2 and "ripe" in requested[1]
    assert [f.value for f in result.findings] == ["RIPE Holder"]
    assert [f.source for f in result.findings] == ["ripe-rdap"]


@pytest.mark.asyncio
async def test_an_rdap_transport_failure_is_reported_as_an_error(monkeypatch) -> None:
    async def failing(client, url, **kwargs):
        raise OutboundRequestError("the endpoint returned a malformed JSON response")

    monkeypatch.setattr(osint_lookups, "get_json_bounded", failing)

    result = await osint_lookups.lookup_ip("198.51.100.4")

    assert result.findings == []
    assert result.errors and "RDAP lookup failed" in result.errors[0]
