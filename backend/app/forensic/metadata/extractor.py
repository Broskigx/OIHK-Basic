"""Metadata extraction for OIHK Basic."""

import logging
import re

from app.forensic.types import MetadataField, MetadataReport

logger = logging.getLogger(__name__)

# Frame headers that carry the image's true dimensions. C4 (DHT), C8 (JPG) and
# CC (DAC) share the same high nibble but are not frame headers, which is why
# this is an explicit set rather than a range.
_SOF_MARKERS = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
_PROGRESSIVE_SOF_MARKERS = frozenset({0xC2, 0xC6, 0xCA, 0xCE})
# Markers that stand alone: they are not followed by a length field, so the
# walker must step over them by two bytes rather than by a declared size.
_STANDALONE_MARKERS = frozenset({0x01, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9})
_START_OF_SCAN = 0xDA


def extract_metadata(data: bytes, filename: str, content_type: str) -> MetadataReport | None:
    """Extract metadata from file data."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    fields: list[MetadataField] = []
    errors: list[str] = []

    raw = {"filename": filename, "size": len(data), "content_type": content_type}

    if ext == "pdf" or "pdf" in content_type:
        fields.append(MetadataField(key="format", value="PDF", category="document"))
        _extract_pdf_info(data, fields, errors)

    if ext in ("jpg", "jpeg") or "jpeg" in content_type:
        _extract_jpeg_info(data, fields)

    if ext == "png" or "png" in content_type:
        fields.append(MetadataField(key="format", value="PNG", category="image"))
        _extract_png_info(data, fields)

    return MetadataReport(
        format=ext or "unknown",
        fields=fields,
        raw=raw,
        errors=errors,
    )


def _extract_pdf_info(data: bytes, fields: list[MetadataField], errors: list[str]) -> None:
    try:
        text = data.decode("latin-1", errors="replace")
        for match in re.finditer(r"/Title\(([^)]*)\)", text):
            fields.append(MetadataField(key="title", value=match.group(1), category="document"))
        for match in re.finditer(r"/Author\(([^)]*)\)", text):
            fields.append(MetadataField(key="author", value=match.group(1), category="document"))
        for match in re.finditer(r"/Subject\(([^)]*)\)", text):
            fields.append(MetadataField(key="subject", value=match.group(1), category="document"))
    except Exception as e:
        errors.append(f"PDF metadata extraction failed: {e}")


def _find_frame_header(data: bytes) -> tuple[int, int] | None:
    """Return ``(marker, payload_offset)`` for the frame header, or ``None``.

    The dimensions of a JPEG live in a frame header, and a frame header is only
    identifiable by walking the segment chain from the start-of-image: every
    segment declares its own length, and the next marker begins where the
    current one ends.

    Searching the file for the two bytes ``FF C0`` instead — which is what this
    did previously — is wrong in both directions. It misses progressive JPEGs,
    which use ``FF C2`` and contain no ``FF C0`` anywhere. And it accepts those
    bytes wherever they appear, including inside the payload of an earlier
    segment, so a crafted EXIF block could state whatever dimensions it liked
    and have them reported as the image's own.
    """
    if not data.startswith(b"\xff\xd8"):
        return None

    position = 2
    limit = len(data)
    while position + 1 < limit:
        if data[position] != 0xFF:
            # Not at a marker boundary: the segment chain is malformed, and
            # guessing where it resumes is how a scanner picks up decoys.
            return None
        # Any number of 0xFF bytes may pad the run-up to a marker.
        marker_at = position + 1
        while marker_at < limit and data[marker_at] == 0xFF:
            marker_at += 1
        if marker_at >= limit:
            return None
        marker = data[marker_at]

        if marker in _STANDALONE_MARKERS:
            position = marker_at + 1
            continue
        if marker == _START_OF_SCAN:
            # Entropy-coded data follows, in which 0xFF bytes are escaped and
            # carry no marker meaning. A frame header always precedes it.
            return None

        if marker_at + 3 > limit:
            return None
        length = int.from_bytes(data[marker_at + 1 : marker_at + 3], "big")
        if length < 2:
            return None
        payload_start = marker_at + 3
        if marker in _SOF_MARKERS:
            return marker, payload_start
        position = marker_at + 1 + length

    return None


def _extract_jpeg_info(data: bytes, fields: list[MetadataField]) -> None:
    try:
        located = _find_frame_header(data)
        if located is None:
            return
        marker, payload_start = located
        # precision(1) height(2) width(2) — anything shorter is a truncated
        # header, and a truncated header has no dimensions to report.
        if payload_start + 5 > len(data):
            return
        height = int.from_bytes(data[payload_start + 1 : payload_start + 3], "big")
        width = int.from_bytes(data[payload_start + 3 : payload_start + 5], "big")
        if width <= 0 or height <= 0:
            return
        fields.append(MetadataField(key="width", value=str(width), category="image"))
        fields.append(MetadataField(key="height", value=str(height), category="image"))
        fields.append(
            MetadataField(
                key="encoding",
                value="progressive" if marker in _PROGRESSIVE_SOF_MARKERS else "baseline",
                category="image",
            )
        )
    except Exception:
        logger.warning("JPEG metadata extraction failed (malformed image data)", exc_info=True)


def _extract_png_info(data: bytes, fields: list[MetadataField]) -> None:
    """Read dimensions from the IHDR chunk, which PNG fixes at offset 8."""
    try:
        if len(data) < 24 or data[12:16] != b"IHDR":
            return
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        if width <= 0 or height <= 0:
            return
        fields.append(MetadataField(key="width", value=str(width), category="image"))
        fields.append(MetadataField(key="height", value=str(height), category="image"))
    except Exception:
        logger.warning("PNG metadata extraction failed (malformed image data)", exc_info=True)
