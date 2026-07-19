"""OIHK Basic — Local-first investigation and OSINT platform."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.logging import configure_logging
from app.database import SessionLocal, init_db
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import (
    auth,
    cases,
    custody,
    exports,
    forensics,
    forensic_core,
    graph,
    health,
    osint,
    operations,
    reports,
    sources,
    targets,
    transforms,
)

logger = logging.getLogger(__name__)

VERSION = "0.1.0"


def _startup_banner() -> str:
    settings = get_settings()
    return (
        "\n"
        "============================================================\n"
        "  OIHK Basic  |  Local-first investigation platform\n"
        "  Secure - Offline-capable - Evidence-aware\n"
        "------------------------------------------------------------\n"
        f"  v{VERSION}  |  env: {settings.environment}\n"
        "  API docs: /docs\n"
        "============================================================"
    )


def _enforce_hardening() -> None:
    settings = get_settings()
    if not settings.is_production:
        if settings.custody_signing_key_is_default:
            logger.warning("OIHK_CUSTODY_SIGNING_KEY is the built-in dev default; set a separate key before production.")
        if settings.auth_enabled and settings.jwt_secret_is_default:
            logger.warning("OIHK_JWT_SECRET is the built-in dev default — set a strong secret before production.")
        if not settings.auth_enabled:
            logger.warning("OIHK_AUTH_ENABLED=false — data routers are UNAUTHENTICATED. Never do this outside local dev.")
        return
    if not settings.auth_enabled:
        raise RuntimeError("Refusing to start in production with OIHK_AUTH_ENABLED=false.")
    if settings.jwt_secret_is_default:
        raise RuntimeError(
            "Refusing to start in production with the default OIHK_JWT_SECRET. "
            'Set a strong OIHK_JWT_SECRET.'
        )
    if settings.custody_signing_key_is_default:
        raise RuntimeError("Refusing to start in production with the default OIHK_CUSTODY_SIGNING_KEY.")
    if "*" in settings.cors_origin_list:
        raise RuntimeError("Refusing to start in production with wildcard CORS origins.")
    if settings.public_registration_enabled:
        raise RuntimeError("Refusing to start in production with public self-registration enabled.")
    if settings.temporary_basic_login:
        raise RuntimeError("Refusing to start in production with OIHK_TEMPORARY_BASIC_LOGIN=true.")


async def _bootstrap_admin() -> None:
    settings = get_settings()
    from sqlalchemy import select

    from app import models
    from app.services.auth_service import get_user_by_email, register_user

    async with SessionLocal() as session:
        existing_admin = (
            await session.execute(select(models.User.id).where(models.User.role == "admin").limit(1))
        ).scalar_one_or_none()
        has_email = bool(settings.bootstrap_admin_email)
        has_password = bool(settings.bootstrap_admin_password)
        if has_email != has_password:
            raise RuntimeError("OIHK_BOOTSTRAP_ADMIN_EMAIL and OIHK_BOOTSTRAP_ADMIN_PASSWORD must be configured together.")
        if not has_email:
            if settings.is_production and existing_admin is None:
                raise RuntimeError(
                    "Production has no administrator. Configure both OIHK_BOOTSTRAP_ADMIN_EMAIL "
                    "and OIHK_BOOTSTRAP_ADMIN_PASSWORD for first startup."
                )
            return
        existing_user = await get_user_by_email(session, settings.bootstrap_admin_email)
        if existing_user:
            if existing_user.role != "admin":
                raise RuntimeError(
                    "The configured bootstrap email already belongs to a non-administrator account."
                )
            return
        await register_user(
            session,
            email=settings.bootstrap_admin_email,
            username="admin",
            password=settings.bootstrap_admin_password,
            role="admin",
        )
        await session.commit()
        logger.info("Bootstrapped admin account %s", settings.bootstrap_admin_email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    print(_startup_banner(), flush=True)
    _enforce_hardening()
    await init_db()
    await _bootstrap_admin()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=VERSION,
    description="OIHK Basic — Local-first investigation and OSINT platform.",
    lifespan=lifespan,
)

if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

app.add_middleware(CSRFMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routers
app.include_router(health.router)
app.include_router(auth.router)

# Authenticated routers
_auth = [Depends(get_current_user)]
app.include_router(cases.router, dependencies=_auth)
app.include_router(sources.router, dependencies=_auth)
app.include_router(targets.router, dependencies=_auth)
app.include_router(graph.router, dependencies=_auth)
app.include_router(reports.router, dependencies=_auth)
app.include_router(exports.router, dependencies=_auth)
app.include_router(osint.router, dependencies=_auth)
app.include_router(transforms.router, dependencies=_auth)
app.include_router(custody.router, dependencies=_auth)
app.include_router(forensics.router, dependencies=_auth)
app.include_router(forensic_core.router, dependencies=_auth)
app.include_router(operations.router, dependencies=_auth)
