"""Content-versus-name discrepancy detection.

The forensic workspace has always had a "Discrepancies" panel and the text
report has always had a Discrepancies section, but the orchestrator passed a
hard-coded empty list into both. Every file analysed — including an executable
wearing an image extension — was presented as having no discrepancies, which is
a clean bill of health the product never actually computed.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.forensic.orchestrator import analyze_file


def _png(width: int = 8, height: int = 8) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def _findings(data: bytes, filename: str, content_type: str = "application/octet-stream") -> list[str]:
    return analyze_file(data, filename=filename, content_type=content_type).file_analysis.discrepancies


def test_a_matching_file_reports_nothing() -> None:
    assert _findings(_png(), "photo.png", "image/png") == []


def test_executable_wearing_an_image_extension_is_flagged() -> None:
    """The masquerade this panel exists to catch."""
    payload = b"MZ\x90\x00" + b"\x00" * 128
    findings = _findings(payload, "holiday-photo.jpg", "image/jpeg")
    assert findings, "a PE executable named .jpg must not analyse clean"
    assert any("executable" in item.lower() for item in findings)


def test_content_contradicting_the_extension_is_flagged() -> None:
    findings = _findings(_png(), "report.pdf", "application/pdf")
    assert any("png" in item.lower() for item in findings)


def test_declared_content_type_contradicting_the_bytes_is_flagged() -> None:
    findings = _findings(_png(), "photo.png", "application/pdf")
    assert any("declared" in item.lower() for item in findings)


def test_double_extension_is_flagged() -> None:
    payload = b"MZ\x90\x00" + b"\x00" * 128
    assert any("double extension" in item.lower() for item in _findings(payload, "invoice.pdf.exe"))


@pytest.mark.parametrize("filename", ["notes.txt", "data.csv", "unknown-blob", "archive.zip"])
def test_ordinary_files_do_not_produce_noise(filename: str) -> None:
    """A detector that cries wolf on routine exhibits is worse than none."""
    assert _findings(b"plain text content, nothing unusual here\n", filename) == []
