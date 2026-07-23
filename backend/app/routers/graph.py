"""Graph router for OIHK Basic."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import (
    CsvImportRequest,
    CsvImportResult,
    DossierConnection,
    DossierSource,
    EntityDetailUpdate,
    EntityDossier,
    EntityLabelUpdate,
    GraphAnalyticsRead,
    GraphBridgeRead,
    GraphComponentRead,
    GraphEdge,
    GraphEntityCreate,
    GraphExpandResult,
    GraphHubRead,
    GraphNode,
    GraphRead,
    GraphRelationshipCreate,
    GraphRelationshipUpdate,
    GraphSnapshotCreate,
    GraphSnapshotRead,
    GraphWorkspaceRead,
    GraphWorkspaceWrite,
)
from app.services.analyzer import ExtractedEntity, normalize_value
from app.services.custody import seal_source
from app.services.graph_analysis import analyze_graph
from app.services.graph_io import export_edges_csv, export_graphml, export_nodes_csv, import_entities_csv
from app.services.pivot import expand_entity
from app.services.repository import audit, upsert_entity

router = APIRouter(prefix="/graph", tags=["graph"])


def _node(entity: models.Entity) -> GraphNode:
    return GraphNode(
        id=entity.id,
        label=entity.display,
        type=entity.type,
        confidence=entity.confidence,
        source_ids=entity.source_ids or [],
        value=entity.value,
        created_at=entity.first_seen,
        updated_at=entity.last_seen,
        properties=entity.properties or {},
        notes=entity.notes or "",
    )


def _edge(relationship: models.Relationship) -> GraphEdge:
    return GraphEdge(
        id=relationship.id,
        source=relationship.subject_id,
        target=relationship.object_id,
        label=relationship.predicate,
        confidence=relationship.confidence,
        source_ids=relationship.source_ids or [],
    )


@router.get("/{case_id}", response_model=GraphRead)
async def get_graph(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphRead:
    await require_case_access(session, case_id, current)
    entity_result = await session.execute(select(models.Entity).where(models.Entity.case_id == case_id))
    relationship_result = await session.execute(
        select(models.Relationship).where(models.Relationship.case_id == case_id)
    )
    nodes = [_node(entity) for entity in entity_result.scalars().all()]
    edges = [
        GraphEdge(
            id=relationship.id,
            source=relationship.subject_id,
            target=relationship.object_id,
            label=relationship.predicate,
            confidence=relationship.confidence,
            source_ids=relationship.source_ids or [],
        )
        for relationship in relationship_result.scalars().all()
    ]
    return GraphRead(nodes=nodes, edges=edges)


async def _case_graph(session: AsyncSession, case_id: str) -> tuple[list[models.Entity], list[models.Relationship]]:
    entities = list(
        (await session.execute(select(models.Entity).where(models.Entity.case_id == case_id))).scalars().all()
    )
    edges = list(
        (await session.execute(select(models.Relationship).where(models.Relationship.case_id == case_id)))
        .scalars()
        .all()
    )
    return entities, edges


def _workspace_read(row: models.GraphWorkspace | None, case_id: str) -> GraphWorkspaceRead:
    if row is None:
        return GraphWorkspaceRead(case_id=case_id)
    return GraphWorkspaceRead(
        id=row.id,
        case_id=row.case_id,
        positions=row.positions or {},
        camera=row.camera or {},
        view_mode=row.view_mode,
        filters=row.filters or {},
        updated_at=row.updated_at,
    )


@router.get("/{case_id}/workspace", response_model=GraphWorkspaceRead)
async def get_graph_workspace(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphWorkspaceRead:
    await require_case_access(session, case_id, current)
    row = (
        await session.execute(select(models.GraphWorkspace).where(models.GraphWorkspace.case_id == case_id))
    ).scalar_one_or_none()
    return _workspace_read(row, case_id)


@router.put("/{case_id}/workspace", response_model=GraphWorkspaceRead)
async def save_graph_workspace(
    case_id: str,
    payload: GraphWorkspaceWrite,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphWorkspaceRead:
    await require_case_access(session, case_id, current)
    valid_ids = set(
        (await session.execute(select(models.Entity.id).where(models.Entity.case_id == case_id))).scalars().all()
    )
    positions = {
        node_id: position.model_dump() for node_id, position in payload.positions.items() if node_id in valid_ids
    }
    row = (
        await session.execute(select(models.GraphWorkspace).where(models.GraphWorkspace.case_id == case_id))
    ).scalar_one_or_none()
    if row is None:
        row = models.GraphWorkspace(case_id=case_id)
        session.add(row)
    row.positions = positions
    row.camera = payload.camera.model_dump()
    row.view_mode = payload.view_mode
    row.filters = payload.filters
    await session.commit()
    await session.refresh(row)
    return _workspace_read(row, case_id)


@router.get("/{case_id}/snapshots", response_model=list[GraphSnapshotRead])
async def list_graph_snapshots(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[GraphSnapshotRead]:
    await require_case_access(session, case_id, current)
    rows = (
        await session.execute(
            select(models.GraphSnapshot)
            .where(models.GraphSnapshot.case_id == case_id)
            .order_by(models.GraphSnapshot.created_at.desc())
            .limit(100)
        )
    ).scalars()
    return [
        GraphSnapshotRead(
            id=row.id,
            case_id=row.case_id,
            name=row.name,
            workspace=GraphWorkspaceWrite.model_validate(row.workspace),
            graph_digest=row.graph_digest,
            node_count=row.node_count,
            edge_count=row.edge_count,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/{case_id}/snapshots", response_model=GraphSnapshotRead, status_code=201)
async def create_graph_snapshot(
    case_id: str,
    payload: GraphSnapshotCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphSnapshotRead:
    await require_case_access(session, case_id, current)
    workspace = (
        await session.execute(select(models.GraphWorkspace).where(models.GraphWorkspace.case_id == case_id))
    ).scalar_one_or_none()
    workspace_payload = GraphWorkspaceWrite(
        positions=workspace.positions if workspace else {},
        camera=workspace.camera if workspace else {},
        view_mode=workspace.view_mode if workspace else "network",
        filters=workspace.filters if workspace else {},
    )
    entities, edges = await _case_graph(session, case_id)
    digest_input = json.dumps(
        {"nodes": sorted(item.id for item in entities), "edges": sorted(item.id for item in edges)},
        separators=(",", ":"),
    )
    row = models.GraphSnapshot(
        case_id=case_id,
        name=payload.name.strip(),
        workspace=workspace_payload.model_dump(),
        graph_digest=hashlib.sha256(digest_input.encode()).hexdigest(),
        node_count=len(entities),
        edge_count=len(edges),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return GraphSnapshotRead(
        id=row.id,
        case_id=row.case_id,
        name=row.name,
        workspace=workspace_payload,
        graph_digest=row.graph_digest,
        node_count=row.node_count,
        edge_count=row.edge_count,
        created_at=row.created_at,
    )


@router.post("/{case_id}/snapshots/{snapshot_id}/restore", response_model=GraphWorkspaceRead)
async def restore_graph_snapshot(
    case_id: str,
    snapshot_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphWorkspaceRead:
    await require_case_access(session, case_id, current)
    snapshot = await session.get(models.GraphSnapshot, snapshot_id)
    if snapshot is None or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="Graph snapshot not found")
    payload = GraphWorkspaceWrite.model_validate(snapshot.workspace)
    row = (
        await session.execute(select(models.GraphWorkspace).where(models.GraphWorkspace.case_id == case_id))
    ).scalar_one_or_none()
    if row is None:
        row = models.GraphWorkspace(case_id=case_id)
        session.add(row)
    row.positions = {node_id: position.model_dump() for node_id, position in payload.positions.items()}
    row.camera = payload.camera.model_dump()
    row.view_mode = payload.view_mode
    row.filters = payload.filters
    await session.commit()
    await session.refresh(row)
    return _workspace_read(row, case_id)


@router.delete("/{case_id}/snapshots/{snapshot_id}")
async def delete_graph_snapshot(
    case_id: str,
    snapshot_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    await require_case_access(session, case_id, current)
    snapshot = await session.get(models.GraphSnapshot, snapshot_id)
    if snapshot is None or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="Graph snapshot not found")
    await session.delete(snapshot)
    await session.commit()
    return {"deleted": True}


@router.post("/{case_id}/import/csv", response_model=CsvImportResult, status_code=201)
async def import_graph_csv(
    case_id: str,
    payload: CsvImportRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CsvImportResult:
    await require_case_access(session, case_id, current)
    try:
        summary = await import_entities_csv(session, case_id=case_id, csv_text=payload.csv, actor=current.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return CsvImportResult(nodes=summary.nodes, edges=summary.edges, errors=summary.errors[:50])


@router.get("/{case_id}/export.graphml")
async def export_graph_graphml(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await require_case_access(session, case_id, current)
    nodes, edges = await _case_graph(session, case_id)
    xml = export_graphml(nodes, edges)
    return Response(
        content=xml,
        media_type="application/graphml+xml",
        headers={"Content-Disposition": f'attachment; filename="oihk-basic-{case_id}.graphml"'},
    )


@router.get("/{case_id}/export.csv")
async def export_graph_csv(
    case_id: str,
    kind: str = Query(default="nodes", pattern="^(nodes|edges)$"),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await require_case_access(session, case_id, current)
    nodes, edges = await _case_graph(session, case_id)
    if kind == "edges":
        labels = {node.id: node.display for node in nodes}
        body = export_edges_csv(edges, labels)
    else:
        body = export_nodes_csv(nodes)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="oihk-basic-{case_id}-{kind}.csv"'},
    )


@router.get("/{case_id}/analytics", response_model=GraphAnalyticsRead)
async def get_graph_analytics(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphAnalyticsRead:
    await require_case_access(session, case_id, current)
    entity_result = await session.execute(select(models.Entity).where(models.Entity.case_id == case_id))
    relationship_result = await session.execute(
        select(models.Relationship).where(models.Relationship.case_id == case_id)
    )
    analytics = analyze_graph(list(entity_result.scalars().all()), list(relationship_result.scalars().all()))
    return GraphAnalyticsRead(
        node_count=analytics.node_count,
        edge_count=analytics.edge_count,
        density=analytics.density,
        component_count=analytics.component_count,
        largest_component_size=analytics.largest_component_size,
        isolated_node_count=analytics.isolated_node_count,
        average_degree=analytics.average_degree,
        type_counts=analytics.type_counts,
        relation_counts=analytics.relation_counts,
        top_hubs=[GraphHubRead(**hub.__dict__) for hub in analytics.top_hubs],
        components=[GraphComponentRead(**component.__dict__) for component in analytics.components],
        bridges=[GraphBridgeRead(**bridge.__dict__) for bridge in analytics.bridges],
    )


@router.post("/entities", response_model=GraphNode, status_code=201)
async def create_graph_entity(
    payload: GraphEntityCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphNode:
    await require_case_access(session, payload.case_id, current)

    entity_type = payload.type.strip().lower().replace(" ", "_")[:40]
    label = " ".join(payload.label.split())
    value = normalize_value(entity_type, label)
    source = models.Source(
        case_id=payload.case_id,
        title=f"Manual graph entity: {label[:210]}",
        kind="manual_graph_entity",
        body=f"Manual graph entity\nlabel={label}\ntype={entity_type}\nconfidence={payload.confidence}",
        citation="analyst-graph-entry",
        license="case-note",
        reliability=payload.confidence,
        robot_compliant=True,
    )
    session.add(source)
    await session.flush()
    await seal_source(session, source)

    entity = await upsert_entity(
        session,
        payload.case_id,
        source.id,
        ExtractedEntity(type=entity_type, value=value, display=label, confidence=payload.confidence),
    )

    if payload.connect_to_id and payload.connect_to_id != entity.id:
        linked = await session.get(models.Entity, payload.connect_to_id)
        if linked is None or linked.case_id != payload.case_id:
            raise HTTPException(status_code=400, detail="connect_to_id is not part of this case")
        relationship = models.Relationship(
            case_id=payload.case_id,
            subject_id=linked.id,
            predicate=payload.relation_label.strip().lower().replace(" ", "_")[:80],
            object_id=entity.id,
            confidence=min(payload.confidence, linked.confidence, 0.82),
            source_ids=[source.id],
        )
        session.add(relationship)

    await audit(
        session,
        "graph.entity.created",
        payload.case_id,
        {"entity_id": entity.id, "type": entity.type, "connected_to": payload.connect_to_id},
        actor="analyst",
    )
    await session.commit()
    return _node(entity)


@router.post("/relationships", response_model=GraphEdge, status_code=201)
async def create_graph_relationship(
    payload: GraphRelationshipCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphEdge:
    await require_case_access(session, payload.case_id, current)
    if payload.source_id == payload.target_id:
        raise HTTPException(status_code=400, detail="A relationship requires two different entities")

    source_entity = await session.get(models.Entity, payload.source_id)
    target_entity = await session.get(models.Entity, payload.target_id)
    if (
        source_entity is None
        or target_entity is None
        or source_entity.case_id != payload.case_id
        or target_entity.case_id != payload.case_id
    ):
        raise HTTPException(status_code=400, detail="Both entities must belong to this case")

    predicate = payload.label.strip().lower().replace(" ", "_")[:80]
    if len(predicate) < 2:
        raise HTTPException(status_code=400, detail="Relationship label is required")

    duplicate = (
        await session.execute(
            select(models.Relationship.id).where(
                models.Relationship.case_id == payload.case_id,
                models.Relationship.subject_id == source_entity.id,
                models.Relationship.predicate == predicate,
                models.Relationship.object_id == target_entity.id,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="This relationship already exists")

    evidence = models.Source(
        case_id=payload.case_id,
        title=f"Manual graph relationship: {source_entity.display[:92]} -> {target_entity.display[:92]}",
        kind="manual_graph_relationship",
        body=f"Manual graph relationship\nsource={source_entity.display}\npredicate={predicate}\ntarget={target_entity.display}\nconfidence={payload.confidence}",
        citation="analyst-graph-entry",
        license="case-note",
        reliability=payload.confidence,
        robot_compliant=True,
    )
    session.add(evidence)
    await session.flush()
    await seal_source(session, evidence)

    relationship = models.Relationship(
        case_id=payload.case_id,
        subject_id=source_entity.id,
        predicate=predicate,
        object_id=target_entity.id,
        confidence=min(payload.confidence, source_entity.confidence, target_entity.confidence),
        source_ids=[evidence.id],
    )
    session.add(relationship)
    await session.flush()
    await audit(
        session,
        "graph.relationship.created",
        payload.case_id,
        {
            "relationship_id": relationship.id,
            "source_id": source_entity.id,
            "target_id": target_entity.id,
            "label": predicate,
        },
        actor=current.username,
    )
    await session.commit()
    return _edge(relationship)


@router.patch("/relationships/{relationship_id}", response_model=GraphEdge)
async def update_graph_relationship(
    relationship_id: str,
    payload: GraphRelationshipUpdate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphEdge:
    relationship = await session.get(models.Relationship, relationship_id)
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    await require_case_access(session, relationship.case_id, current)
    if payload.label is not None:
        relationship.predicate = payload.label.strip().lower().replace(" ", "_")[:80]
    if payload.confidence is not None:
        relationship.confidence = payload.confidence
    await audit(
        session,
        "graph.relationship.updated",
        relationship.case_id,
        {"relationship_id": relationship.id},
        actor=current.username,
    )
    await session.commit()
    return _edge(relationship)


@router.delete("/relationships/{relationship_id}")
async def delete_graph_relationship(
    relationship_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    relationship = await session.get(models.Relationship, relationship_id)
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    await require_case_access(session, relationship.case_id, current)
    case_id = relationship.case_id
    await session.delete(relationship)
    await audit(
        session,
        "graph.relationship.deleted",
        case_id,
        {"relationship_id": relationship_id},
        actor=current.username,
    )
    await session.commit()
    return {"deleted": True}


def _excerpt(body: str, limit: int = 600) -> str:
    text = " ".join((body or "").split())
    return text[:limit] + ("…" if len(text) > limit else "")


async def _merge_entity(
    session: AsyncSession, *, source: models.Entity, into: models.Entity, label: str
) -> models.Entity:
    rels = (
        (
            await session.execute(
                select(models.Relationship).where(
                    (models.Relationship.subject_id == source.id) | (models.Relationship.object_id == source.id)
                )
            )
        )
        .scalars()
        .all()
    )
    seen: set[tuple[str, str, str]] = set()
    existing_edges = (
        (
            await session.execute(
                select(models.Relationship).where(
                    (models.Relationship.subject_id == into.id) | (models.Relationship.object_id == into.id)
                )
            )
        )
        .scalars()
        .all()
    )
    for edge in existing_edges:
        seen.add((edge.subject_id, edge.predicate, edge.object_id))

    for rel in rels:
        if rel.subject_id == source.id:
            rel.subject_id = into.id
        if rel.object_id == source.id:
            rel.object_id = into.id
        key = (rel.subject_id, rel.predicate, rel.object_id)
        if rel.subject_id == rel.object_id or key in seen:
            await session.delete(rel)
            continue
        seen.add(key)

    into.source_ids = sorted(set((into.source_ids or []) + (source.source_ids or [])))
    into.confidence = max(into.confidence, source.confidence)
    into.display = label[:500]
    into.last_seen = models.utcnow()
    await session.delete(source)
    await session.flush()
    return into


@router.patch("/entities/{entity_id}", response_model=GraphNode)
async def rename_graph_entity(
    entity_id: str,
    payload: EntityLabelUpdate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphNode:
    entity = await session.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)

    label = " ".join(payload.label.split())
    if not label:
        raise HTTPException(status_code=400, detail="Label cannot be empty")

    new_value = normalize_value(entity.type, label)
    collision = (
        await session.execute(
            select(models.Entity).where(
                models.Entity.case_id == entity.case_id,
                models.Entity.type == entity.type,
                models.Entity.value == new_value,
                models.Entity.id != entity.id,
            )
        )
    ).scalar_one_or_none()

    if collision is not None:
        result = await _merge_entity(session, source=entity, into=collision, label=label)
    else:
        entity.display = label[:500]
        entity.value = new_value
        entity.last_seen = models.utcnow()
        result = entity

    await audit(
        session, "graph.entity.renamed", result.case_id, {"entity_id": result.id, "label": label[:120]}, actor="analyst"
    )
    await session.commit()
    return _node(result)


@router.patch("/entities/{entity_id}/details", response_model=GraphNode)
async def update_entity_details(
    entity_id: str,
    payload: EntityDetailUpdate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphNode:
    entity = await session.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)

    changed: dict = {}
    if payload.properties is not None:
        cleaned = {
            str(key).strip()[:80]: str(value)[:2000]
            for key, value in payload.properties.items()
            if str(key).strip() and str(value).strip()
        }
        entity.properties = cleaned
        changed["properties"] = len(cleaned)
    if payload.notes is not None:
        entity.notes = payload.notes.strip()
        changed["notes"] = len(entity.notes)
    if payload.type is not None:
        new_type = payload.type.strip().lower().replace(" ", "_")[:40]
        if new_type and new_type != entity.type:
            new_value = normalize_value(new_type, entity.display)
            collision = (
                await session.execute(
                    select(models.Entity.id).where(
                        models.Entity.case_id == entity.case_id,
                        models.Entity.type == new_type,
                        models.Entity.value == new_value,
                        models.Entity.id != entity.id,
                    )
                )
            ).scalar_one_or_none()
            if collision is not None:
                raise HTTPException(status_code=400, detail="Another node of that type already has this value.")
            entity.type = new_type
            entity.value = new_value
            changed["type"] = new_type

    entity.last_seen = models.utcnow()
    await audit(
        session, "graph.entity.details_updated", entity.case_id, {"entity_id": entity.id, **changed}, actor="analyst"
    )
    await session.commit()
    return _node(entity)


@router.post("/entities/{entity_id}/timeline", status_code=201)
async def add_graph_entity_to_timeline(
    entity_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    entity = await session.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)

    event_payload = {
        "entity_id": entity.id,
        "label": entity.display[:500],
        "entity_type": entity.type,
        "confidence": entity.confidence,
        "source_count": len(entity.source_ids or []),
        "first_seen": entity.first_seen.isoformat() if entity.first_seen else None,
        "last_seen": entity.last_seen.isoformat() if entity.last_seen else None,
    }
    await audit(session, "graph.entity.timeline_added", entity.case_id, event_payload, actor=current.username)
    await session.commit()
    return {"added": True, "action": "graph.entity.timeline_added", "case_id": entity.case_id, **event_payload}


@router.delete("/entities/{entity_id}")
async def delete_graph_entity(
    entity_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    entity = await session.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)

    relationship_ids = list(
        (
            await session.execute(
                select(models.Relationship.id).where(
                    (models.Relationship.subject_id == entity_id) | (models.Relationship.object_id == entity_id)
                )
            )
        )
        .scalars()
        .all()
    )
    await session.execute(
        delete(models.Relationship).where(
            (models.Relationship.subject_id == entity_id) | (models.Relationship.object_id == entity_id)
        )
    )
    case_id = entity.case_id
    entity_label = entity.display
    await session.delete(entity)
    await audit(
        session,
        "graph.entity.deleted",
        case_id,
        {"entity_id": entity_id, "label": entity_label[:120], "relationship_count": len(relationship_ids)},
        actor=current.username,
    )
    await session.commit()
    return {"deleted": True, "entity_id": entity_id, "relationship_count": len(relationship_ids)}


@router.get("/entities/{entity_id}/dossier", response_model=EntityDossier)
async def entity_dossier(
    entity_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EntityDossier:
    entity = await session.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)

    source_ids = entity.source_ids or []
    sources: list[DossierSource] = []
    if source_ids:
        rows = (await session.execute(select(models.Source).where(models.Source.id.in_(source_ids)))).scalars().all()
        for src in rows:
            sources.append(
                DossierSource(
                    source_id=src.id,
                    title=src.title,
                    kind=src.kind,
                    url=src.url,
                    citation=src.citation,
                    reliability=src.reliability,
                    excerpt=_excerpt(src.body),
                )
            )

    rel_rows = (
        (
            await session.execute(
                select(models.Relationship).where(
                    (models.Relationship.subject_id == entity_id) | (models.Relationship.object_id == entity_id)
                )
            )
        )
        .scalars()
        .all()
    )
    neighbour_ids = {(rel.object_id if rel.subject_id == entity_id else rel.subject_id) for rel in rel_rows}
    neighbours: dict[str, models.Entity] = {}
    if neighbour_ids:
        for neighbour in (
            (await session.execute(select(models.Entity).where(models.Entity.id.in_(neighbour_ids)))).scalars().all()
        ):
            neighbours[neighbour.id] = neighbour

    connections: list[DossierConnection] = []
    for rel in rel_rows:
        outgoing = rel.subject_id == entity_id
        neighbour_id = rel.object_id if outgoing else rel.subject_id
        neighbour = neighbours.get(neighbour_id)
        if neighbour is None:
            continue
        connections.append(
            DossierConnection(
                relationship_id=rel.id,
                relation=rel.predicate,
                direction="outgoing" if outgoing else "incoming",
                confidence=rel.confidence,
                entity=_node(neighbour),
            )
        )
    connections.sort(key=lambda c: c.confidence, reverse=True)

    return EntityDossier(
        entity=_node(entity),
        first_seen=entity.first_seen,
        last_seen=entity.last_seen,
        sources=sources,
        connections=connections,
    )


@router.post("/entities/{entity_id}/expand", response_model=GraphExpandResult, status_code=201)
async def expand_graph_entity(
    entity_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphExpandResult:
    entity = await session.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)

    result = await expand_entity(session, entity)
    await session.commit()
    return GraphExpandResult(
        entity_id=entity_id,
        strategy=result.strategy,
        summary=result.summary,
        new_nodes=[_node(item) for item in result.new_entities],
        new_edges=[_edge(item) for item in result.new_relationships],
    )
