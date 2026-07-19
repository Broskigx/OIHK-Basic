"""Investigation types for OIHK Basic."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InvestigationNode:
    id: str
    type: str
    value: str
    display: str
    confidence: float
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class InvestigationEdge:
    subject_id: str
    predicate: str
    object_id: str
    confidence: float
    source_ids: list[str] = field(default_factory=list)


@dataclass
class InvestigationResult:
    entities: list[InvestigationNode]
    relationships: list[InvestigationEdge]
    sources: list[dict[str, Any]]
    summary: str
