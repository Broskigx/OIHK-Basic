"""Authentication service for OIHK Basic."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.security import hash_password, verify_password


async def get_user_by_email(session: AsyncSession, email: str) -> models.User | None:
    result = await session.execute(select(models.User).where(models.User.email == email))
    return result.scalar_one_or_none()


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    username: str,
    password: str,
    role: str = "analyst",
) -> models.User:
    existing = await get_user_by_email(session, email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = models.User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(session: AsyncSession, *, email: str, password: str) -> models.User:
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user.last_login_at = models.utcnow()
    return user
