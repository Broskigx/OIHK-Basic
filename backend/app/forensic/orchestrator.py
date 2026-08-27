"""Forensic analysis orchestrator for OIHK Basic."""

from __future__ import annotations

import time
from collections import Counter
from math import log2

from app.forensic.discrepancies import detect_discrepancies
from app.forensic.extraction.text import extract_text
from app.forensic.hashing.hasher import compute_hashes
from app.forensic.ioc.extractor import extract_iocs
from app.forensic.metadata.extractor import extract_metadata
from app.forensic.mime.analyzer import detect_mime_type
from app.forensic.timeline.builder import build_timeline
from app.forensic.types import (
    FileAnalysis,
    ForensicCoreReport,
    HashResult,
    IocReport,
)


def analyze_file(
    data: bytes,
    filename: str = "upload",
    content_type: str = "application/octet-stream",
) -> ForensicCoreReport:
    """Run the full forensic analysis pipeline on a file."""
    errors: list[str] = []
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    start = time.monotonic()

    # Hashing
    hashes = compute_hashes(data)
    sha256 = hashes.get("sha256", "")

    # MIME detection
    mime_type, detected_type, detected_label = detect_mime_type(data, content_type, ext)
    magic = data[:16].hex()[:32]

    # File analysis
    entropy = _compute_entropy(data)
    file_analysis = FileAnalysis(
        filename=filename,
        size_bytes=len(data),
        extension=ext,
        mime_type=mime_type,
        magic_bytes=magic,
        detected_type=detected_type,
        detected_label=detected_label,
        entropy=round(entropy, 2),
        hashes=hashes,
        timestamps={},
        permissions=None,
        discrepancies=detect_discrepancies(
            filename=filename,
            extension=ext,
            detected_type=detected_type,
            mime_type=mime_type,
            declared_content_type=content_type,
        ),
    )

    # Metadata
    metadata_report = extract_metadata(data, filename, content_type)

    # Text extraction
    text_report = extract_text(data, filename, content_type)

    # IOC extraction
    ioc_report = extract_iocs(text_report.text) if text_report and text_report.text else IocReport(matches=[])

    # Timeline
    timeline = build_timeline(data, filename, sha256)

    elapsed = int((time.monotonic() - start) * 1000)

    hash_results = [
        HashResult(algorithm=algo, digest=digest, size_bytes=len(data), elapsed_ms=elapsed, target=filename)
        for algo, digest in hashes.items()
    ]

    return ForensicCoreReport(
        filename=filename,
        hashes=hash_results,
        file_analysis=file_analysis,
        metadata=metadata_report,
        text_extraction=text_report,
        iocs=ioc_report,
        timeline_events=timeline,
        errors=errors,
    )


def _compute_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    size = len(data)
    return -sum((count / size) * log2(count / size) for count in Counter(data).values())
