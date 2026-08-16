"""Shared FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from sqlalchemy import Select

from app import models
from app.core.config import get_settings
from app.core.security import TokenError, decode_access_token
from app.database import get_session

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    username: str
    role: str
    organization_id: str = "default"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_system(self) -> bool:
        return self.id == "system"

    @property
    def database_user_id(self) -> str | None:
        """Return a real FK-safe user id, or no owner in loopback single-user mode."""
        return None if self.is_system else self.id


_SYSTEM_USER = CurrentUser(
    id="system", email="system@oihk-basic.local", username="system", role="admin", organization_id="system"
)


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    settings = get_settings()
    if not settings.auth_enabled:
        return _SYSTEM_USER

    token = _extract_bearer(request)
    if not token:
        raise _UNAUTHENTICATED
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await session.get(models.User, payload.get("sub", ""))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or missing")
    return CurrentUser(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        organization_id=user.organization_id or "default",
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return user


def accessible_cases_statement(user: CurrentUser) -> Select[tuple[str]]:
    """Single source of truth for the set of cases a user may access.

    Mirrors the exact organization/owner/membership rules applied when listing
    cases so that cross-resource queries (e.g. transform history) never diverge
    from the case access model. The system loopback user bypasses the filter.
    """
    statement = select(models.Case.id)
    if user.is_system:
        return statement
    # COALESCE, not a bare equality: organization_id is nullable, and the
    # per-case checks below read a NULL as "default". In SQL a NULL never
    # equals anything, so a bare comparison would hide a NULL-org case from
    # every listing while require_case_access still granted it by direct id.
    # The two rules have to normalise a missing organization the same way.
    statement = statement.where(
        func.coalesce(models.Case.organization_id, "default") == user.organization_id
    )
    if not user.is_admin:
        member_case_ids = select(models.CaseMembership.case_id).where(
            models.CaseMembership.user_id == user.id
        )
        statement = statement.where(
            or_(models.Case.owner_id == user.id, models.Case.id.in_(member_case_ids))
        )
    return statement


async def user_can_access_case(session: AsyncSession, case_id: str, user: CurrentUser) -> bool:
    case = await session.get(models.Case, case_id)
    if case is None:
        return False
    if user.is_system:
        return True
    if (case.organization_id or "default") != user.organization_id:
        return False
    if user.is_admin or case.owner_id == user.id:
        return True
    result = await session.execute(
        select(models.CaseMembership.id).where(
            models.CaseMembership.case_id == case_id,
            models.CaseMembership.user_id == user.id,
        )
    )
    return result.scalar_one_or_none() is not None


async def require_case_access(session: AsyncSession, case_id: str, user: CurrentUser) -> models.Case:
    case = await session.get(models.Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if user.is_system:
        return case
    if (case.organization_id or "default") != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case access denied")
    if user.is_admin or case.owner_id == user.id:
        return case
    result = await session.execute(
        select(models.CaseMembership.id).where(
            models.CaseMembership.case_id == case_id,
            models.CaseMembership.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case access denied")
    return case


async def require_target_access(session: AsyncSession, target_id: str, user: CurrentUser) -> models.TargetProfile:
    target = await session.get(models.TargetProfile, target_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    await require_case_access(session, target.case_id, user)
    return target


async def require_search_run_access(session: AsyncSession, run_id: str, user: CurrentUser) -> models.SearchRun:
    run = await session.get(models.SearchRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search run not found")
    await require_case_access(session, run.case_id, user)
    return run
