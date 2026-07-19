"""Graph import/export for OIHK Basic."""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.services.analyzer import ExtractedEntity, normalize_value
from app.services.custody import seal_source
from app.services.repository import upsert_entity


@dataclass
class CsvImportSummary:
    nodes: int
    edges: int
    errors: list[str]


async def import_entities_csv(
    session: AsyncSession,
    *,
    case_id: str,
    csv_text: str,
    actor: str = "analyst",
) -> CsvImportSummary:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("CSV must have a header row")

    required = {"label", "type"}
    if not required.issubset(reader.fieldnames):
        raise ValueError(f"CSV must have columns: {', '.join(sorted(required))}")

    nodes = 0
    edges = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        try:
            label = row.get("label", "").strip()
            type_ = row.get("type", "").strip().lower().replace(" ", "_")[:40]
            confidence = min(float(row.get("confidence", "0.68")), 1.0)
            connect_to = row.get("connect_to", "").strip()

            if not label or not type_:
                errors.append(f"Row {i}: missing label or type")
                continue

            value = normalize_value(type_, label)
            source = models.Source(
                case_id=case_id,
                title=f"CSV import entity: {label[:210]}",
                kind="csv_import",
                body=f"CSV import\nlabel={label}\ntype={type_}\nconfidence={confidence}",
                citation=f"csv-import-row-{i}",
                license="case-note",
                reliability=confidence,
                robot_compliant=True,
            )
            session.add(source)
            await session.flush()
            await seal_source(session, source)

            entity = await upsert_entity(
                session, case_id, source.id,
                ExtractedEntity(type=type_, value=value, display=label, confidence=confidence),
            )
            nodes += 1

            if connect_to:
                connected = (
                    await session.execute(
                        select(models.Entity).where(
                            models.Entity.case_id == case_id,
                            models.Entity.id == connect_to,
                        )
                    )
                ).scalar_one_or_none()
                if connected and connected.id != entity.id:
                    rel = models.Relationship(
                        case_id=case_id,
                        subject_id=connected.id,
                        predicate=row.get("relation", "connected_to").strip().lower().replace(" ", "_")[:80],
                        object_id=entity.id,
                        confidence=min(confidence, connected.confidence, 0.82),
                        source_ids=[source.id],
                    )
                    session.add(rel)
                    edges += 1

        except (ValueError, KeyError) as exc:
            errors.append(f"Row {i}: {exc}")

    return CsvImportSummary(nodes=nodes, edges=edges, errors=errors)


def export_nodes_csv(entities: list[models.Entity]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "label", "type", "confidence", "source_count"])
    for e in entities:
        writer.writerow([e.id, e.display, e.type, e.confidence, len(e.source_ids or [])])
    return output.getvalue()


def export_edges_csv(relationships: list[models.Relationship], labels: dict[str, str]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "source", "target", "label", "confidence"])
    for r in relationships:
        writer.writerow([r.id, labels.get(r.subject_id, r.subject_id),
                        labels.get(r.object_id, r.object_id), r.predicate, r.confidence])
    return output.getvalue()


def export_graphml(entities: list[models.Entity], relationships: list[models.Relationship]) -> str:
    """Export graph as GraphML."""
    ns = {"graphml": "http://graphml.graphdrawing.org/xmlns"}
    ET.register_namespace("", "http://graphml.graphdrawing.org/xmlns")

    graphml = ET.Element("graphml", ns)
    graph = ET.SubElement(graphml, "graph", edgedefault="directed")

    # Node attributes
    key_type = ET.SubElement(graphml, "key", id="k_type", for_="node", attr_name="type", attr_type="string")
    key_conf = ET.SubElement(graphml, "key", id="k_conf", for_="node", attr_name="confidence", attr_type="double")

    node_elements: dict[str, ET.Element] = {}
    for e in entities:
        n = ET.SubElement(graph, "node", id=e.id)
        ET.SubElement(n, "data", key="k_type").text = e.type
        ET.SubElement(n, "data", key="k_conf").text = str(e.confidence)
        n.text = e.display
        node_elements[e.id] = n

    for r in relationships:
        edge = ET.SubElement(graph, "edge", id=r.id, source=r.subject_id, target=r.object_id)
        edge.text = r.predicate

    return ET.tostring(graphml, encoding="unicode", xml_declaration=True)
