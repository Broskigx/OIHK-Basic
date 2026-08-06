"""Metadata extraction for OIHK Basic."""

import logging
import re
import struct

from app.forensic.types import MetadataField, MetadataReport

logger = logging.getLogger(__name__)


def extract_metadata(data: bytes, filename: str, content_type: str) -> MetadataReport | None:
    """Extract metadata from file data."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    fields: list[MetadataField] = []
    raw: dict = {}
    errors: list[str] = []

    raw = {"filename": filename, "size": len(data), "content_type": content_type}

    if ext == "pdf" or "pdf" in content_type:
        fields.append(MetadataField(key="format", value="PDF", category="document"))
        _extract_pdf_info(data, fields, errors)

    if ext in ("jpg", "jpeg") or "jpeg" in content_type:
        _extract_jpeg_info(data, fields)

    if ext == "png" or "png" in content_type:
        fields.append(MetadataField(key="format", value="PNG", category="image"))

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


def _extract_jpeg_info(data: bytes, fields: list[MetadataField]) -> None:
    # Read image dimensions from JPEG
    try:
        idx = data.find(b"\xff\xc0")
        if idx != -1 and idx + 7 < len(data):
            height = struct.unpack(">H", data[idx + 5 : idx + 7])[0]
            width = struct.unpack(">H", data[idx + 7 : idx + 9])[0]
            fields.append(MetadataField(key="width", value=str(width), category="image"))
            fields.append(MetadataField(key="height", value=str(height), category="image"))
    except Exception:
        logger.warning("JPEG metadata extraction failed (malformed image data)", exc_info=True)
