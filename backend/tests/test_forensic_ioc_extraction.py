"""IOC extraction must not let one chatty indicator type hide the rest."""

from __future__ import annotations

from app.forensic.ioc.extractor import extract_iocs


def test_a_flood_of_one_type_does_not_starve_the_others() -> None:
    """The 200-match ceiling was applied after a global sort by confidence.

    Emails score 0.9, so a document containing more than 200 of them filled the
    entire result set and every URL, hash, CVE and domain in the same document
    was dropped without a word. That is the shape of a mail archive, which is
    exactly the kind of exhibit this runs against.
    """
    noise = " ".join(f"user{index}@example.com" for index in range(400))
    document = f"{noise} CVE-2024-3094 8.8.8.8 https://example.org/payload d41d8cd98f00b204e9800998ecf8427e"

    found = {match.type for match in extract_iocs(document).matches}

    assert {"cve", "ipv4", "url", "md5"} <= found, f"starved indicator types, saw only {sorted(found)}"


def test_ipv4_matches_reject_out_of_range_octets() -> None:
    """``999.999.999.999`` is not an address, and version strings are not hosts."""
    report = extract_iocs("999.999.999.999 256.1.1.1 8.8.8.8 build 1.2.3.4")
    addresses = {match.value for match in report.matches if match.type == "ipv4"}
    assert addresses == {"8.8.8.8", "1.2.3.4"}


def test_total_ceiling_is_still_enforced() -> None:
    document = " ".join(f"user{index}@example.com" for index in range(5_000))
    assert len(extract_iocs(document).matches) <= 200


def test_matches_remain_ordered_by_confidence() -> None:
    report = extract_iocs("contact me at a@b.com or visit https://example.org")
    confidences = [match.confidence for match in report.matches]
    assert confidences == sorted(confidences, reverse=True)
