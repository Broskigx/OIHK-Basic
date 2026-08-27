from __future__ import annotations

import io
import zipfile

import pytest

from app.forensic.extraction import text
from app.forensic.orchestrator import _compute_entropy as core_entropy
from app.services.forensic_evidence import _compute_entropy as evidence_entropy


@pytest.mark.parametrize("calculator", [core_entropy, evidence_entropy])
def test_entropy_is_correct_for_binary_data(calculator) -> None:
    assert calculator(b"") == 0.0
    assert calculator(b"\x00" * 1024) == 0.0
    assert calculator(bytes(range(256))) == pytest.approx(8.0)


def test_ooxml_extraction_rejects_oversized_members(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text, "_MAX_OOXML_MEMBER_BYTES", 32)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "<w:t>" + ("A" * 128) + "</w:t>")

    errors: list[str] = []
    extracted = text._extract_ooxml(payload.getvalue(), errors)
    assert extracted == ""
    assert errors == ["OOXML member word/document.xml exceeds the 32-byte extraction limit"]


def test_pptx_text_extraction_reads_slides() -> None:
    """A .pptx routed to the OOXML extractor must yield its slide text.

    The extractor accepted the extension but only ever opened
    ``word/document.xml`` and ``xl/sharedStrings.xml``, so every presentation
    returned an empty string *and an empty error list*: indistinguishable from
    a genuinely wordless deck.
    """
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", "<p:sld><a:t>CONFIDENTIAL PAYLOAD</a:t></p:sld>")
        archive.writestr("ppt/slides/slide2.xml", "<p:sld><a:t>SECOND SLIDE</a:t></p:sld>")
        archive.writestr("ppt/notesSlides/notesSlide1.xml", "<a:t>speaker note</a:t>")

    extracted = text.extract_text(payload.getvalue(), "deck.pptx", "")
    assert "CONFIDENTIAL PAYLOAD" in extracted.text
    assert "SECOND SLIDE" in extracted.text
    assert "speaker note" in extracted.text
    assert extracted.errors == []


def test_ooxml_slide_members_stay_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """The per-member ceiling must apply to slides too, not just document.xml."""
    monkeypatch.setattr(text, "_MAX_OOXML_MEMBER_BYTES", 32)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ppt/slides/slide1.xml", "<a:t>" + ("A" * 128) + "</a:t>")

    errors: list[str] = []
    assert text._extract_ooxml(payload.getvalue(), errors) == ""
    assert errors == ["OOXML member ppt/slides/slide1.xml exceeds the 32-byte extraction limit"]
