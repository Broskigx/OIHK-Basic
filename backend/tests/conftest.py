"""Shared bootstrap for backend tests."""

from __future__ import annotations

import os
import shutil

# System Link tests sign module packages with ephemeral development publisher
# keys. The host only accepts development channel signatures when this flag is
# explicitly enabled, so the backend test session opts in before the first
# Settings instance is cached. Production code defaults to reject (release
# anchors only).
os.environ.setdefault("OIHK_SYSTEM_LINK_ALLOW_DEV_PUBLISHERS", "true")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.deps import CurrentUser, get_current_user  # noqa: E402
from app.database import Base, get_session  # noqa: E402

# The loopback single-user identity the desktop edition runs as. Routes reach it
# through get_current_user, which returns this same value when authentication is
# disabled, so overriding the dependency keeps HTTP tests on the real code path
# rather than a test-only one.
SYSTEM_USER = CurrentUser(
    id="system",
    email="system@oihk-basic.local",
    username="system",
    role="admin",
    organization_id="system",
)


@pytest.fixture(scope="session")
def schema_template(tmp_path_factory):
    """Build the full schema once per session as a file to copy from.

    Emitting the DDL for every table costs a few seconds, and paying that per
    test dominated the run time of the suite. Building it once and copying the
    resulting file gives each test the same isolated database for the price of
    a file copy. A synchronous engine is used deliberately: a session-scoped
    async fixture would outlive the function-scoped event loop.
    """
    from sqlalchemy import create_engine

    from app import models  # noqa: F401  (registers the tables on Base.metadata)

    path = tmp_path_factory.mktemp("schema") / "template.db"
    engine = create_engine(f"sqlite:///{path}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    return path


@pytest.fixture
async def engine(tmp_path, schema_template):
    """An isolated on-disk SQLite database with the production PRAGMA applied.

    On disk rather than in memory, and with `foreign_keys=ON`, because the
    behaviour worth testing includes cascade and RESTRICT enforcement — an
    in-memory database with the default PRAGMA would silently accept deletes
    the real one refuses.
    """
    database_path = tmp_path / "oihk-test.db"
    shutil.copyfile(schema_template, database_path)
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def sessions(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def session(sessions):
    """A session for arranging fixtures or asserting on state directly."""
    async with sessions() as opened:
        yield opened


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    """Point managed evidence storage at a per-test directory."""
    directory = tmp_path / "managed-storage"
    monkeypatch.setenv("OIHK_STORAGE_DIR", str(directory))
    get_settings.cache_clear()
    try:
        yield directory
    finally:
        get_settings.cache_clear()


def reset_rate_limiter(application) -> None:
    """Clear the sliding-window state held by the live limiter instance.

    The limiter is in-process and the application object is a module-level
    singleton, so without this every test would spend from a budget the
    previous ones had already drawn down. Clearing the state keeps the
    middleware itself on the request path — the limiter is still exercised,
    it just starts each test from zero, the way a fresh process would.
    """
    from app.middleware.rate_limit import RateLimitMiddleware

    if application.middleware_stack is None:
        application.middleware_stack = application.build_middleware_stack()
    node = application.middleware_stack
    while node is not None:
        if isinstance(node, RateLimitMiddleware):
            node._hits.clear()
            node._last_sweep = 0.0
            return
        node = getattr(node, "app", None)


@pytest.fixture
async def client(sessions, storage_dir, tmp_path, monkeypatch):
    """An HTTP client bound to the real application, middleware included.

    Only the session factory and the authenticated identity are substituted.
    Everything a request passes through on the way to a route — the Host and
    Origin guards, rate limiting, validation, serialisation — is the code that
    ships.

    ``OIHK_DATABASE_URL`` is pointed at the same temporary file the session
    fixture uses. A few routes (storage diagnostics, the SQLite backup) resolve
    the database from settings rather than from the injected session, and
    without this they would read the developer's real application database.

    The per-minute ceiling is raised well above what any single test issues.
    A functional test that tripped the limiter would be measuring the limiter,
    not the route; the limiter has its own tests in test_request_hardening.
    """
    from app.main import app

    monkeypatch.setenv("OIHK_DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'oihk-test.db').as_posix()}")
    monkeypatch.setenv("OIHK_RATE_LIMIT_PER_MINUTE", "100000")
    get_settings.cache_clear()
    reset_rate_limiter(app)

    async def _session_override():
        async with sessions() as opened:
            yield opened

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = lambda: SYSTEM_USER
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as opened:
            yield opened
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def case(client):
    """A committed case, returned as the parsed API representation."""
    response = await client.post(
        "/cases",
        json={
            "title": "Reference investigation",
            "legal_basis": "Authorized test",
            "scope_statement": "Bounded scope for the integration suite.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
