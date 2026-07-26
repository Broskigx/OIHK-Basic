"""Operations router for OIHK Basic — audit log and case monitoring."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.config import get_settings
from app.core.deps import CurrentUser, get_current_user
from app.database import get_session

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/providers")
async def provider_catalog(_current: CurrentUser = Depends(get_current_user)) -> dict:
    """Return sanitized local/provider readiness without URLs, keys, or credentials."""
    settings = get_settings()
    providers = [
        {
            "id": "sqlite",
            "name": "SQLite local workspace",
            "category": "local",
            "access": "local-only",
            "auth": "none",
            "connector_type": "embedded",
            "capabilities": ["cases", "graph", "evidence metadata", "history"],
            "env_var": "",
            "configured": True,
            "status": "operational",
        },
        {
            "id": "public-infrastructure",
            "name": "Public DNS / RDAP / certificates",
            "category": "public-osint",
            "access": "explicit actions only",
            "auth": "none",
            "connector_type": "https",
            "capabilities": ["dns", "rdap", "certificates"],
            "env_var": "",
            "configured": True,
            "status": "operational",
        },
        {
            "id": "searxng",
            "name": "SearXNG",
            "category": "search",
            "access": "user-configured endpoint",
            "auth": "endpoint policy",
            "connector_type": "https",
            "capabilities": ["public search"],
            "env_var": "OIHK_SEARXNG_URL",
            "configured": bool(settings.searxng_url),
            "status": "configured" if settings.searxng_url else "catalogued",
        },
        {
            "id": "brave",
            "name": "Brave Search",
            "category": "search",
            "access": "user-provided API key",
            "auth": "api-key",
            "connector_type": "https",
            "capabilities": ["public search"],
            "env_var": "OIHK_BRAVE_API_KEY",
            "configured": bool(settings.brave_api_key),
            "status": "configured" if settings.brave_api_key else "catalogued",
        },
        {
            "id": "local-model",
            "name": "Local model endpoint",
            "category": "local-ai",
            "access": "loopback/private network",
            "auth": "optional user credential",
            "connector_type": "openai-compatible",
            "capabilities": ["copilot", "report drafts"],
            "env_var": "OIHK_AI_BASE_URL",
            "configured": settings.ai_configured,
            "status": "configured" if settings.ai_configured else "catalogued",
        },
    ]
    categories: dict[str, int] = {}
    for provider in providers:
        category = str(provider["category"])
        categories[category] = categories.get(category, 0) + 1
    configured = sum(bool(provider["configured"]) for provider in providers)
    operational = sum(provider["status"] == "operational" for provider in providers)
    catalogued = sum(provider["status"] == "catalogued" for provider in providers)
    return {
        "total": len(providers),
        "connected": operational + sum(provider["status"] == "configured" for provider in providers),
        "operational": operational,
        "configured": configured,
        "catalogued": catalogued,
        "keyless": 2,
        "requires_configuration": catalogued,
        "categories": categories,
        "providers": providers,
    }


@router.get("/audit")
async def list_audit_events(
    case_id: str | None = Query(default=None),
    limit: int = Query(default=80, le=200),
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List audit events, optionally filtered by case."""
    statement = select(models.AuditEvent).order_by(models.AuditEvent.created_at.desc()).limit(limit)
    if case_id:
        statement = statement.where(models.AuditEvent.case_id == case_id)
    if not current.is_system:
        statement = statement.where(models.AuditEvent.payload["organization_id"].as_string() == current.organization_id)
    result = await session.execute(statement)
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "case_id": e.case_id,
            "payload": e.payload,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


@router.get("/cases/{case_id}/monitor")
async def get_case_monitor(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get a summary overview of a case's current state."""
    from app.core.deps import require_case_access

    case = await require_case_access(session, case_id, current)

    source_count = (await session.execute(select(models.Source.id).where(models.Source.case_id == case_id))).scalar()
    entity_count = (await session.execute(select(models.Entity.id).where(models.Entity.case_id == case_id))).scalar()
    relationship_count = (
        await session.execute(select(models.Relationship.id).where(models.Relationship.case_id == case_id))
    ).scalar()

    return {
        "case_id": case.id,
        "title": case.title,
        "status": case.status,
        "source_count": source_count or 0,
        "entity_count": entity_count or 0,
        "relationship_count": relationship_count or 0,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }
