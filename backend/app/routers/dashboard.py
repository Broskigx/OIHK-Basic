"""Permission-aware aggregates for the local dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, accessible_cases_statement, get_current_user
from app.database import get_session
from app.schemas import (
    DashboardActivityRead,
    DashboardCountsRead,
    DashboardModuleRead,
    DashboardRecentCaseRead,
    DashboardSummaryRead,
)
from app.system_link.protocol import ModuleState

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_CONNECTED_MODULE_STATES = {ModuleState.READY.value, ModuleState.BUSY.value}


def _latest(*values: datetime | None) -> datetime | None:
    available = [value for value in values if value is not None]
    return max(available) if available else None


def _audit_detail(event: models.AuditEvent, case_title: str | None) -> str:
    payload = event.payload or {}
    subject = case_title or "Local workspace"
    if event.action == "case.created":
        return str(payload.get("title") or subject)[:240]
    if event.action.startswith("evidence."):
        return f"Evidence activity in {subject}"
    if event.action.startswith("graph."):
        return f"Graph activity in {subject}"
    if event.action.startswith("report."):
        return f"Report activity in {subject}"
    if event.action.startswith("transform."):
        return f"Transform activity in {subject}"
    return subject


@router.get("/summary", response_model=DashboardSummaryRead)
async def dashboard_summary(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardSummaryRead:
    """Return only aggregates and activity for cases the caller may read."""

    case_statement = select(models.Case).order_by(models.Case.updated_at.desc())
    if not current.is_system:
        case_statement = case_statement.where(models.Case.id.in_(accessible_cases_statement(current)))
    cases = list((await session.execute(case_statement)).scalars().all())
    case_ids = [case.id for case in cases]
    case_titles = {case.id: case.title for case in cases}

    evidence_by_case: dict[str, int] = {}
    if case_ids:
        evidence_rows = await session.execute(
            select(models.EvidenceItem.case_id, func.count(models.EvidenceItem.id))
            .where(models.EvidenceItem.case_id.in_(case_ids))
            .group_by(models.EvidenceItem.case_id)
        )
        evidence_by_case = dict(evidence_rows.all())
    evidence_count = sum(evidence_by_case.values())

    module_rows = list((await session.execute(select(models.SystemLinkModule))).scalars().all())
    registered_modules = [module for module in module_rows if module.revoked_at is None]
    connected_modules = [
        module for module in registered_modules if module.enabled and module.state in _CONNECTED_MODULE_STATES
    ]

    audit_events: list[models.AuditEvent] = []
    if case_ids:
        audit_events = list(
            (
                await session.execute(
                    select(models.AuditEvent)
                    .where(models.AuditEvent.case_id.in_(case_ids))
                    .order_by(models.AuditEvent.created_at.desc())
                    .limit(20)
                )
            ).scalars()
        )
    system_events = list(
        (
            await session.execute(
                select(models.SystemLinkEvent).order_by(models.SystemLinkEvent.created_at.desc()).limit(20)
            )
        ).scalars()
    )
    module_names = {module.module_id: module.product_name for module in module_rows}

    activity: list[DashboardActivityRead] = [
        DashboardActivityRead(
            id=f"audit-{event.id}",
            kind="audit",
            action=event.action,
            actor=event.actor,
            detail=_audit_detail(event, case_titles.get(event.case_id or "")),
            case_id=event.case_id,
            case_title=case_titles.get(event.case_id or ""),
            created_at=event.created_at,
        )
        for event in audit_events
    ]
    activity.extend(
        DashboardActivityRead(
            id=f"system-link-{event.id}",
            kind="system_link",
            action=event.action,
            actor="System Link",
            detail=module_names.get(event.module_id or "", "System Link runtime"),
            module_id=event.module_id,
            created_at=event.created_at,
        )
        for event in system_events
    )
    activity.sort(key=lambda item: item.created_at, reverse=True)

    return DashboardSummaryRead(
        generated_at=datetime.now(UTC),
        counts=DashboardCountsRead(
            active_investigations=sum(case.status == "active" for case in cases),
            registered_evidence=evidence_count,
            pending_tasks=None,
            tasks_available=False,
            connected_modules=len(connected_modules),
            registered_modules=len(registered_modules),
        ),
        recent_investigations=[
            DashboardRecentCaseRead(
                id=case.id,
                title=case.title,
                status=case.status,
                priority=case.priority,
                evidence_count=evidence_by_case.get(case.id, 0),
                updated_at=case.updated_at,
            )
            for case in cases[:6]
        ],
        recent_activity=activity[:12],
        modules=[
            DashboardModuleRead(
                module_id=module.module_id,
                product_name=module.product_name,
                module_version=module.module_version,
                state=module.state,
                enabled=module.enabled,
                last_activity_at=_latest(module.last_health_at, module.last_handshake_at, module.updated_at),
            )
            for module in registered_modules
        ],
    )
