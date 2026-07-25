"""Correlation logic for OIHK Basic."""

from app.investigation.types import InvestigationEdge, InvestigationNode


def correlate_findings(
    nodes: list[InvestigationNode],
    edges: list[InvestigationEdge],
    min_confidence: float = 0.2,
) -> tuple[list[InvestigationNode], list[InvestigationEdge]]:
    """Correlate findings by linking nodes that share the same value."""
    value_index: dict[str, list[str]] = {}
    for node in nodes:
        if node.value:
            key = node.value.lower()
            if key not in value_index:
                value_index[key] = []
            value_index[key].append(node.id)

    new_edges: list[InvestigationEdge] = []
    for _key, ids in value_index.items():
        if len(ids) > 1:
            for i in range(len(ids) - 1):
                edge = InvestigationEdge(
                    subject_id=ids[i],
                    predicate="same_as",
                    object_id=ids[i + 1],
                    confidence=0.9,
                )
                if edge not in edges and edge not in new_edges:
                    new_edges.append(edge)

    return nodes, edges + new_edges
