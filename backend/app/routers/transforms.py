"""OSINT transform catalog + per-node transform runner for OIHK Basic."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import (
    GraphEdge, GraphExpandResult, GraphNode,
    MachineAdhocRun, MachineCreate, MachineRead, MachineRunResult,
    MachineSkip, MachineStep, TransformRunRequest,
)
from app.services.transform_runner import TransformError, run_transform_on_entity
from app.transforms import registry

router = APIRouter(prefix="/transforms", tags=["transforms"])


def _node(entity: models.Entity) -> GraphNode:
    return GraphNode(
        id=entity.id, label=entity.display, type=entity.type,
        confidence=entity.confidence, source_ids=entity.source_ids or [],
        properties=entity.properties or {}, notes=entity.notes or "",
    )


def _edge(relationship: models.Relationship) -> GraphEdge:
    return GraphEdge(
        id=relationship.id, source=relationship.subject_id, target=relationship.object_id,
        label=relationship.predicate, confidence=relationship.confidence,
        source_ids=relationship.source_ids or [],
    )


@router.get("")
async def list_transforms(
    input: str | None = Query(default=None, description="Filter by input entity type, e.g. 'domain'."),
    enabled_only: bool = Query(default=False, description="Only transforms wired into the live pipeline."),
) -> dict:
    specs = registry.for_input(input) if input else registry.all()
    if enabled_only:
        specs = [spec for spec in specs if spec.enabled]
    return {
        "count": len(specs),
        "categories": registry.categories(),
        "transforms": [spec.as_dict() for spec in specs],
    }


@router.post("/{transform_id}/run", response_model=GraphExpandResult, status_code=201)
async def run_transform(
    transform_id: str,
    payload: TransformRunRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GraphExpandResult:
    entity = await session.get(models.Entity, payload.entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)

    try:
        result = await run_transform_on_entity(
            session, transform_id=transform_id, entity=entity, actor=current.username
        )
    except TransformError as exc:
        raise HTTPException(status_code=404 if exc.not_found else 400, detail=str(exc)) from exc

    await session.commit()
    spec = registry.get(transform_id)
    return GraphExpandResult(
        entity_id=entity.id,
        strategy=result.strategy,
        summary=f"{spec.title if spec else transform_id}: {result.summary}",
        new_nodes=[_node(item) for item in result.new_entities],
        new_edges=[_edge(item) for item in result.new_relationships],
        transform=transform_id,
    )


@router.post("/machines", response_model=MachineRead, status_code=201)
async def create_machine(
    payload: MachineCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> models.Machine:
    transform_ids = [t for t in payload.transform_ids if registry.get(t) is not None]
    if not transform_ids:
        raise HTTPException(status_code=400, detail="No known transforms in the chain.")
    machine = models.Machine(
        organization_id=current.organization_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        transform_ids=transform_ids,
        input_type=payload.input_type.strip().lower(),
        created_by=current.id,
    )
    session.add(machine)
    await session.commit()
    return machine


@router.get("/machines", response_model=list[MachineRead])
async def list_machines(
    input: str | None = Query(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.Machine]:
    statement = select(models.Machine).order_by(models.Machine.created_at.desc())
    if not current.is_system:
        statement = statement.where(models.Machine.organization_id == current.organization_id)
    machines = list((await session.execute(statement)).scalars().all())
    if input:
        machines = [m for m in machines if not m.input_type or m.input_type == input]
    return machines


async def _run_chain(
    session: AsyncSession, *, entity: models.Entity, transform_ids: list[str], actor: str
) -> MachineRunResult:
    case = await session.get(models.Case, entity.case_id)
    ran: list[MachineStep] = []
    skipped: list[MachineSkip] = []
    nodes: dict[str, models.Entity] = {}
    edges: dict[str, models.Relationship] = {}
    for transform_id in transform_ids:
        try:
            result = await run_transform_on_entity(
                session, transform_id=transform_id, entity=entity, actor=actor, case=case
            )
        except TransformError as exc:
            skipped.append(MachineSkip(transform=transform_id, reason=str(exc)))
            continue
        for item in result.new_entities:
            nodes[item.id] = item
        for rel in result.new_relationships:
            edges[rel.id] = rel
        ran.append(MachineStep(transform=transform_id, strategy=result.strategy, new_nodes=len(result.new_entities)))
    summary = f"{len(ran)} transform(s) · +{len(nodes)} nodes · +{len(edges)} edges" + (
        f" · {len(skipped)} skipped" if skipped else ""
    )
    return MachineRunResult(
        entity_id=entity.id, summary=summary, ran=ran, skipped=skipped,
        new_nodes=[_node(item) for item in nodes.values()],
        new_edges=[_edge(item) for item in edges.values()],
    )


@router.post("/machines/run/{entity_id}", response_model=MachineRunResult, status_code=201)
async def run_adhoc_machine(
    entity_id: str,
    payload: MachineAdhocRun,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MachineRunResult:
    entity = await session.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)
    result = await _run_chain(session, entity=entity, transform_ids=payload.transform_ids, actor=current.username)
    await session.commit()
    return result


@router.post("/machines/{machine_id}/run/{entity_id}", response_model=MachineRunResult, status_code=201)
async def run_machine(
    machine_id: str,
    entity_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MachineRunResult:
    machine = await session.get(models.Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found")
    if not current.is_system and machine.organization_id != current.organization_id:
        raise HTTPException(status_code=403, detail="Machine access denied")
    entity = await session.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    await require_case_access(session, entity.case_id, current)
    result = await _run_chain(session, entity=entity, transform_ids=list(machine.transform_ids), actor=current.username)
    await session.commit()
    return result
