"""Forensic analysis orchestrator for OIHK Basic."""

from __future__ import annotations

import hashlib
import time

from app.forensic.types import (
    FileAnalysis, ForensicCoreReport, HashResult, IocReport,
    MetadataReport, TextExtraction, TimelineEvent, YaraReport,
)
from app.forensic.hashing.hasher import compute_hashes
from app.forensic.mime.analyzer import detect_mime_type
from app.forensic.metadata.extractor import extract_metadata
from app.forensic.extraction.text import extract_text
from app.forensic.ioc.extractor import extract_iocs
from app.forensic.timeline.builder import build_timeline


def analyze_file(
    data: bytes,
    filename: str = "upload",
    content_type: str = "application/octet-stream",
    run_yara: bool = False,
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
        filename=filename, size_bytes=len(data), extension=ext,
        mime_type=mime_type, magic_bytes=magic,
        detected_type=detected_type, detected_label=detected_label,
        entropy=round(entropy, 2),
        hashes=hashes, timestamps={}, permissions=None,
        discrepancies=[],
    )

    # Metadata
    metadata_report = extract_metadata(data, filename, content_type)

    # Text extraction
    text_report = extract_text(data, filename, content_type)

    # IOC extraction
    ioc_report = None
    if text_report and text_report.text:
        ioc_report = extract_iocs(text_report.text)
    else:
        ioc_report = IocReport(matches=[])

    # Timeline
    timeline = build_timeline(data, filename, sha256)

    # YARA (stub for now)
    yara_report = YaraReport(matches=[], rules_loaded=0, available=False, error="YARA not available in OIHK Basic")

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
        yara=yara_report,
        timeline_events=timeline,
        errors=errors,
    )


def _compute_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    from math import log2

    entropy = 0.0
    for x in range(256):
        p_x = data.count(x) / len(data)
        if p_x > 0:
            entropy += -p_x * log2(p_x)
    return entropy
