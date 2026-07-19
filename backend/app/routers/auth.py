"""Authentication router for OIHK Basic."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import CurrentUser, get_current_user
from app.core.security import create_access_token
from app.database import get_session
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserRead
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user) -> TokenResponse:
    settings = get_settings()
    token = create_access_token(
        user.id,
        role=user.role,
        extra={"email": user.email, "organization_id": user.organization_id},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_ttl_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: UserCreate, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    if not get_settings().public_registration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled. Ask an administrator to provision the account.",
        )
    user = await register_user(
        session,
        email=payload.email,
        username=payload.username,
        password=payload.password,
    )
    await session.commit()
    await session.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    settings = get_settings()
    if (
        settings.temporary_basic_login
        and not settings.is_production
        and payload.email == "admin"
        and payload.password == "admin"
    ):
        from app import models

        user = (
            await session.execute(
                select(models.User)
                .where(models.User.username == "admin", models.User.role == "admin", models.User.is_active.is_(True))
                .order_by(models.User.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Temporary local admin login is enabled, but no active administrator is provisioned.",
            )
        user.last_login_at = models.utcnow()
    else:
        user = await authenticate_user(session, email=payload.email, password=payload.password)
    await session.commit()
    await session.refresh(user)
    return _token_response(user)


@router.get("/me", response_model=UserRead)
async def me(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    from app import models

    user = await session.get(models.User, current.id)
    if user is not None:
        return UserRead.model_validate(user)
    return UserRead(
        id=current.id,
        email=current.email,
        username=current.username,
        role=current.role,
        organization_id=current.organization_id,
        is_active=True,
        created_at=models.utcnow(),
    )
