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
