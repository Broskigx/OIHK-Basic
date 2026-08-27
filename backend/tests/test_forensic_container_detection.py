"""Container-format detection must read the format, not a lucky prefix.

Both defects covered here produced a confident *wrong* answer rather than an
unknown one, which is the worse failure mode for a report a reader trusts.
"""

from __future__ import annotations

import io
import struct

import pytest
from PIL import Image

from app.forensic.mime.analyzer import detect_mime_type


def _riff(form: bytes) -> bytes:
    return b"RIFF" + struct.pack("<I", 36) + form + b"\x00" * 24


def test_riff_subtypes_are_distinguished() -> None:
    """RIFF is a container. WAV and WebP are not AVI files.

    ``RIFF`` alone was mapped straight to ``video/avi``, so every WAV recording
    and every WebP image in an exhibit was labelled a video.
    """
    assert detect_mime_type(_riff(b"AVI "), "", "avi")[0] == "video/avi"
    assert detect_mime_type(_riff(b"WAVE"), "", "wav")[0] == "audio/wav"
    assert detect_mime_type(_riff(b"WEBP"), "", "webp")[0] == "image/webp"


def test_real_webp_is_detected_as_an_image() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(buffer, format="WEBP")
    mime, detected, _label = detect_mime_type(buffer.getvalue(), "", "webp")
    assert (mime, detected) == ("image/webp", "webp")


@pytest.mark.parametrize("box_size", [0x14, 0x18, 0x1C, 0x20, 0x24])
def test_mp4_ftyp_is_matched_at_its_offset(box_size: int) -> None:
    """``ftyp`` sits at offset 4; the box length in front of it is not fixed.

    Hard-coding the 24-byte length meant only one of these five encoders was
    recognised and the rest fell through to ``application/octet-stream``.
    """
    payload = struct.pack(">I", box_size) + b"ftypisom" + b"\x00" * 32
    assert detect_mime_type(payload, "", "mp4")[0] == "video/mp4"


def test_unknown_data_still_falls_back_to_the_declared_type() -> None:
    assert detect_mime_type(b"\x00\x01\x02\x03", "application/x-thing", "bin") == (
        "application/x-thing",
        "unknown",
        "Unknown",
    )
