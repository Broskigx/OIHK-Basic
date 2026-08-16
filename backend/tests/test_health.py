"""Basic smoke tests for OIHK Basic."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify the health endpoint returns OK."""
    transport = ASGITransport(app=app)
    # A loopback authority, because the Host allowlist now rejects anything else
    # (see app.middleware.origin_guard).
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "oihk-basic-api"


@pytest.mark.asyncio
async def test_app_title():
    """Verify the app has the correct title."""
    assert app.title == "OIHK Basic"
    assert app.version is not None
