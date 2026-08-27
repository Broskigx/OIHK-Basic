"""JPEG dimensions must come from a parsed frame header.

``data.find(b"\xff\xc0")`` scans the whole file for two bytes that carry no
structural guarantee. Two consequences, both reproduced below: progressive
JPEGs (which use SOF2 and contain no SOF0 at all) reported no dimensions, and a
file with those bytes inside an earlier segment reported that segment's
contents as the image size.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.forensic.metadata.extractor import extract_metadata


def _jpeg(width: int, height: int, *, progressive: bool) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="JPEG", progressive=progressive)
    return buffer.getvalue()


def _dimensions(payload: bytes, filename: str = "exhibit.jpg") -> dict[str, str]:
    report = extract_metadata(payload, filename, "image/jpeg")
    assert report is not None
    return {field.key: field.value for field in report.fields if field.key in {"width", "height"}}


@pytest.mark.parametrize("progressive", [False, True])
def test_dimensions_are_reported_for_both_jpeg_encodings(progressive: bool) -> None:
    assert _dimensions(_jpeg(321, 123, progressive=progressive)) == {"width": "321", "height": "123"}


def test_decoy_frame_marker_in_an_earlier_segment_is_ignored() -> None:
    """A crafted APP1 segment must not be able to restate the image's size.

    The decoy below is well-formed: an APP1 segment whose *payload* contains
    the SOF0 marker and a 2457x2457 frame header. A scan-for-bytes reader finds
    it first and reports it; a reader that walks segment lengths never looks
    inside a segment's payload at all.
    """
    baseline = _jpeg(321, 123, progressive=False)
    decoy_frame = b"\xff\xc0\x00\x11\x08" + (2457).to_bytes(2, "big") + (2457).to_bytes(2, "big")
    segment = b"Exif\x00\x00" + decoy_frame
    app1 = b"\xff\xe1" + (len(segment) + 2).to_bytes(2, "big") + segment
    tampered = baseline[:2] + app1 + baseline[2:]

    assert _dimensions(tampered) == {"width": "321", "height": "123"}


def test_truncated_frame_header_does_not_invent_dimensions() -> None:
    baseline = _jpeg(64, 64, progressive=False)
    marker = baseline.index(b"\xff\xc0")
    assert _dimensions(baseline[: marker + 6]) == {}
