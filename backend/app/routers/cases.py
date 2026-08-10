"""Local investigation lifecycle routes for OIHK Basic."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, accessible_cases_statement, get_current_user, require_case_access
from app.database import get_session
from app.schemas import CaseCreate, CaseImportDocument, CaseRead, CaseUpdate
from app.services.repository import audit, create_case

router = APIRouter(prefix="/cases", tags=["cases"])


async def _counts(session: AsyncSession, model: type, case_ids: list[str]) -> dict[str, int]:
    if not case_ids:
        return {}
    rows = await session.execute(
        select(model.case_id, func.count()).where(model.case_id.in_(case_ids)).group_by(model.case_id)
    )
    return dict(rows.all())


async def _case_reads(session: AsyncSession, cases: list[models.Case]) -> list[CaseRead]:
    case_ids = [case.id for case in cases]
    entities = await _counts(session, models.Entity, case_ids)
    relationships = await _counts(session, models.Relationship, case_ids)
    sources = await _counts(session, models.Source, case_ids)
    conversations = await _counts(session, models.AssistantConversation, case_ids)
    queries = await _counts(session, models.OsintQuery, case_ids)
    return [
        CaseRead.model_validate(case).model_copy(
            update={
                "entity_count": entities.get(case.id, 0),
                "relationship_count": relationships.get(case.id, 0),
                "source_count": sources.get(case.id, 0),
                "conversation_count": conversations.get(case.id, 0),
                "query_count": queries.get(case.id, 0),
            }
        )
        for case in cases
    ]


@router.get("", response_model=list[CaseRead])
async def list_cases(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CaseRead]:
    statement = select(models.Case).order_by(models.Case.updated_at.desc())
    if not current.is_system:
        statement = statement.where(models.Case.id.in_(accessible_cases_statement(current)))
    cases = list((await session.execute(statement)).scalars().all())
    return await _case_reads(session, cases)


@router.post("", response_model=CaseRead, status_code=201)
async def create_case_endpoint(
    payload: CaseCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CaseRead:
    case = await create_case(
        session,
        title=payload.title,
        summary=payload.summary,
        legal_basis=payload.legal_basis,
        scope_statement=payload.scope_statement,
        owner_id=current.database_user_id,
        organization_id=current.organization_id,
        priority=payload.priority,
        tags=[tag.strip()[:80] for tag in payload.tags if tag.strip()],
        notes=payload.notes,
    )
    await audit(session, "case.created", case_id=case.id, actor=current.username, payload={"title": case.title})
    await session.commit()
    return (await _case_reads(session, [case]))[0]


@router.post("/import", response_model=CaseRead, status_code=201)
async def import_case(
    document: CaseImportDocument,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CaseRead:
    payload = document.case
    case = await create_case(
        session,
        title=payload.title,
        summary=payload.summary,
        legal_basis=payload.legal_basis,
        scope_statement=payload.scope_statement,
        owner_id=current.database_user_id,
        organization_id=current.organization_id,
        priority=payload.priority,
        tags=[tag.strip()[:80] for tag in payload.tags if tag.strip()],
        notes=payload.notes,
    )
    source_map: dict[str, str] = {}
    for source in document.sources:
        copied = models.Source(
            case_id=case.id,
            title=source.title,
            kind=source.kind,
            body=source.body,
            citation=source.citation,
            license=source.license,
            reliability=source.reliability,
        )
        session.add(copied)
        await session.flush()
        source_map[source.id] = copied.id
    entity_map: dict[str, str] = {}
    for entity in document.entities:
        copied = models.Entity(
            case_id=case.id,
            type=entity.type,
            value=entity.value,
            display=entity.display,
            confidence=entity.confidence,
            source_ids=[source_map[item] for item in entity.source_ids if item in source_map],
            properties=entity.properties,
            notes=entity.notes,
        )
        session.add(copied)
        await session.flush()
        entity_map[entity.id] = copied.id
    for relation in document.relationships:
        if relation.subject_id not in entity_map or relation.object_id not in entity_map:
            continue
        session.add(
            models.Relationship(
                case_id=case.id,
                subject_id=entity_map[relation.subject_id],
                predicate=relation.predicate,
                object_id=entity_map[relation.object_id],
                confidence=relation.confidence,
                source_ids=[source_map[item] for item in relation.source_ids if item in source_map],
            )
        )
    await audit(session, "case.imported", case_id=case.id, actor=current.username)
    await session.commit()
    return (await _case_reads(session, [case]))[0]


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CaseRead:
    case = await require_case_access(session, case_id, current)
    return (await _case_reads(session, [case]))[0]


@router.patch("/{case_id}", response_model=CaseRead)
async def update_case(
    case_id: str,
    payload: CaseUpdate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CaseRead:
    case = await require_case_access(session, case_id, current)
    changes = payload.model_dump(exclude_unset=True)
    if "tags" in changes:
        changes["tags"] = [tag.strip()[:80] for tag in (changes["tags"] or []) if tag.strip()]
    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(case, field, value)
    if changes.get("status") == "archived":
        case.archived_at = datetime.now(UTC)
    elif "status" in changes:
        case.archived_at = None
    case.updated_at = datetime.now(UTC)
    await audit(session, "case.updated", case_id=case.id, actor=current.username, payload={"fields": sorted(changes)})
    await session.commit()
    return (await _case_reads(session, [case]))[0]


@router.post("/{case_id}/duplicate", response_model=CaseRead, status_code=201)
async def duplicate_case(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CaseRead:
    original = await require_case_access(session, case_id, current)
    duplicate = await create_case(
        session,
        title=f"{original.title} (copy)"[:200],
        summary=original.summary,
        legal_basis=original.legal_basis,
        scope_statement=original.scope_statement,
        owner_id=current.database_user_id,
        organization_id=current.organization_id,
        priority=original.priority,
        tags=list(original.tags or []),
        notes=original.notes,
    )
    duplicate.graph_config = dict(original.graph_config or {})

    source_map: dict[str, str] = {}
    for source in (await session.execute(select(models.Source).where(models.Source.case_id == case_id))).scalars():
        copied = models.Source(
            case_id=duplicate.id,
            title=source.title,
            kind=source.kind,
            url=source.url,
            body=source.body,
            citation=source.citation,
            license=source.license,
            reliability=source.reliability,
            robot_compliant=source.robot_compliant,
            collected_at=source.collected_at,
        )
        session.add(copied)
        await session.flush()
        source_map[source.id] = copied.id

    entity_map: dict[str, str] = {}
    for entity in (await session.execute(select(models.Entity).where(models.Entity.case_id == case_id))).scalars():
        copied = models.Entity(
            case_id=duplicate.id,
            type=entity.type,
            value=entity.value,
            display=entity.display,
            confidence=entity.confidence,
            source_ids=[source_map[source_id] for source_id in entity.source_ids or [] if source_id in source_map],
            properties=dict(entity.properties or {}),
            notes=entity.notes,
            first_seen=entity.first_seen,
            last_seen=entity.last_seen,
        )
        session.add(copied)
        await session.flush()
        entity_map[entity.id] = copied.id

    for relation in (
        await session.execute(select(models.Relationship).where(models.Relationship.case_id == case_id))
    ).scalars():
        if relation.subject_id not in entity_map or relation.object_id not in entity_map:
            continue
        session.add(
            models.Relationship(
                case_id=duplicate.id,
                subject_id=entity_map[relation.subject_id],
                predicate=relation.predicate,
                object_id=entity_map[relation.object_id],
                confidence=relation.confidence,
                source_ids=[
                    source_map[source_id] for source_id in relation.source_ids or [] if source_id in source_map
                ],
            )
        )
    await audit(
        session,
        "case.duplicated",
        case_id=duplicate.id,
        actor=current.username,
        payload={"source_case_id": original.id},
    )
    await session.commit()
    return (await _case_reads(session, [duplicate]))[0]


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    case = await require_case_access(session, case_id, current)
    await session.execute(delete(models.AuditEvent).where(models.AuditEvent.case_id == case_id))
    await session.delete(case)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
