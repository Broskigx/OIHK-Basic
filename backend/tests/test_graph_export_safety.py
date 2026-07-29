from __future__ import annotations

from types import SimpleNamespace

from app.services.graph_io import export_edges_csv, export_nodes_csv


def test_graph_csv_exports_neutralize_spreadsheet_formulas() -> None:
    nodes = [
        SimpleNamespace(
            id="node-1",
            display='=HYPERLINK("https://example.invalid")',
            type="@danger",
            confidence=0.9,
            source_ids=[],
        )
    ]
    relationships = [
        SimpleNamespace(
            id="edge-1",
            subject_id="node-1",
            object_id="node-2",
            predicate="+cmd",
            confidence=0.8,
        )
    ]

    node_csv = export_nodes_csv(nodes)
    edge_csv = export_edges_csv(relationships, {"node-1": "=source", "node-2": "-target"})
    assert "'=HYPERLINK" in node_csv
    assert "'@danger" in node_csv
    assert "'=source" in edge_csv
    assert "'-target" in edge_csv
    assert "'+cmd" in edge_csv
