"""Data types for forensic analysis in OIHK Basic."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FileAnalysis:
    filename: str
    size_bytes: int
    extension: str
    mime_type: str
    magic_bytes: str
    detected_type: str
    detected_label: str
    entropy: float
    hashes: dict[str, str]
    timestamps: dict[str, str | None]
    permissions: str | None
    discrepancies: list[str]


@dataclass
class HashResult:
    algorithm: str
    digest: str
    size_bytes: int
    elapsed_ms: int
    target: str


@dataclass
class MetadataField:
    key: str
    value: str
    category: str


@dataclass
class MetadataReport:
    format: str
    fields: list[MetadataField]
    raw: dict[str, Any]
    errors: list[str]


@dataclass
class TextExtraction:
    format: str
    text: str
    char_count: int
    word_count: int
    errors: list[str]


@dataclass
class IocMatch:
    type: str
    value: str
    display: str
    confidence: float
    offset: int | None = None
    context: str = ""


@dataclass
class IocReport:
    matches: list[IocMatch]
    asn_lookups: list[dict[str, str]] = field(default_factory=list)


@dataclass
class TimelineEvent:
    event_id: str
    source_id: str | None
    title: str
    event_type: str
    timestamp: str
    detail: str
    metadata: dict[str, Any]


@dataclass
class ForensicCoreReport:
    filename: str
    hashes: list[HashResult]
    file_analysis: FileAnalysis | None
    metadata: MetadataReport | None
    text_extraction: TextExtraction | None
    iocs: IocReport | None
    timeline_events: list[TimelineEvent]
    errors: list[str]
