"""Graph analysis service for OIHK Basic."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict

from app import models


@dataclass
class GraphHub:
    entity_id: str
    label: str
    type: str
    degree: int
    score: float


@dataclass
class GraphComponent:
    index: int
    size: int
    sample_node_ids: list[str]


@dataclass
class GraphBridge:
    source_id: str
    target_id: str
    label: str


@dataclass
class GraphAnalyticsResult:
    node_count: int
    edge_count: int
    density: float
    component_count: int
    largest_component_size: int
    isolated_node_count: int
    average_degree: float
    type_counts: dict[str, int]
    relation_counts: dict[str, int]
    top_hubs: list[GraphHub]
    components: list[GraphComponent]
    bridges: list[GraphBridge]


def analyze_graph(
    entities: list[models.Entity],
    relationships: list[models.Relationship],
) -> GraphAnalyticsResult:
    n = len(entities)
    m = len(relationships)

    degree: dict[str, int] = defaultdict(int)
    type_counts: dict[str, int] = defaultdict(int)
    relation_counts: dict[str, int] = defaultdict(int)

    entity_map = {e.id: e for e in entities}
    adjacency: dict[str, set[str]] = defaultdict(set)

    for rel in relationships:
        degree[rel.subject_id] += 1
        degree[rel.object_id] += 1
        relation_counts[rel.predicate] += 1
        adjacency[rel.subject_id].add(rel.object_id)
        adjacency[rel.object_id].add(rel.subject_id)

    for e in entities:
        type_counts[e.type] += 1

    # Connected components via BFS
    visited: set[str] = set()
    components: list[GraphComponent] = []
    isolated_count = 0

    for e in entities:
        if e.id in visited:
            continue
        component_nodes: list[str] = []
        stack = [e.id]
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            component_nodes.append(node_id)
            for neighbor in adjacency.get(node_id, set()):
                if neighbor not in visited:
                    stack.append(neighbor)

        if len(component_nodes) == 1 and not adjacency.get(e.id):
            isolated_count += 1

        components.append(GraphComponent(
            index=len(components),
            size=len(component_nodes),
            sample_node_ids=component_nodes[:5],
        ))

    # Hubs (sorted by degree)
    hubs = []
    for entity_id, deg in degree.items():
        entity = entity_map.get(entity_id)
        if entity:
            hubs.append(GraphHub(
                entity_id=entity_id,
                label=entity.display,
                type=entity.type,
                degree=deg,
                score=deg / max(m, 1),
            ))
    hubs.sort(key=lambda h: h.score, reverse=True)

    # Density
    density = (2 * m) / (n * (n - 1)) if n > 1 else 0.0

    # Bridges — edges that connect different components
    bridges: list[GraphBridge] = []

    largest_size = max((c.size for c in components), default=0)

    return GraphAnalyticsResult(
        node_count=n,
        edge_count=m,
        density=round(density, 4),
        component_count=len(components),
        largest_component_size=largest_size,
        isolated_node_count=isolated_count,
        average_degree=round((2 * m) / n, 2) if n > 0 else 0.0,
        type_counts=dict(type_counts),
        relation_counts=dict(relation_counts),
        top_hubs=hubs[:10],
        components=components,
        bridges=bridges,
    )
