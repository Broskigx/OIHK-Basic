"""Cases router for OIHK Basic."""

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.deps import CurrentUser, get_current_user, require_case_access
from app.database import get_session
from app.schemas import CaseCreate, CaseRead
from app.services.repository import create_case

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseRead])
async def list_cases(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[models.Case]:
    statement = select(models.Case).order_by(models.Case.created_at.desc())
    if not current.is_system:
        statement = statement.where(models.Case.organization_id == current.organization_id)
        if not current.is_admin:
            member_case_ids = select(models.CaseMembership.case_id).where(models.CaseMembership.user_id == current.id)
            statement = statement.where(or_(models.Case.owner_id == current.id, models.Case.id.in_(member_case_ids)))
    result = await session.execute(statement)
    return list(result.scalars().all())


@router.post("", response_model=CaseRead, status_code=201)
async def create_case_endpoint(
    payload: CaseCreate,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> models.Case:
    case = await create_case(
        session,
        title=payload.title,
        summary=payload.summary,
        legal_basis=payload.legal_basis,
        scope_statement=payload.scope_statement,
        owner_id=current.id,
        organization_id=current.organization_id,
    )
    await session.commit()
    return case


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> models.Case:
    return await require_case_access(session, case_id, current)
