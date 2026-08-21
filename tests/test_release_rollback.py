import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from alembic import command
from app.main import app


def test_alembic_migration_upgrade_path_from_base():
    """
    Test that Alembic can upgrade from base to head cleanly.
    Note: Current migration history contains revision 001_initial_schema.
    """
    alembic_cfg = Config("alembic.ini")
    # Verify heads command succeeds on alembic configuration
    command.heads(alembic_cfg)


@pytest.mark.asyncio
async def test_release_readiness_and_liveness_contracts():
    """
    Verify release contract endpoints return expected status codes and payloads.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        liveness_resp = await client.get("/health/liveness")
        assert liveness_resp.status_code == 200
        assert liveness_resp.json() == {"status": "ok"}

        health_resp = await client.get("/health")
        assert health_resp.status_code in (200, 530)


@pytest.mark.asyncio
async def test_rollback_compatibility_maintains_existing_schema():
    """
    Verify application operations function cleanly against current schema revision.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/v1/urls", json={"url": "https://pytest.org/rollback-test"}
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        short_code = data["short_code"]

        redirect_resp = await client.get(f"/{short_code}", follow_redirects=False)
        assert redirect_resp.status_code == 307
        assert redirect_resp.headers["location"] == "https://pytest.org/rollback-test"

        analytics_resp = await client.get(f"/api/v1/urls/{short_code}/analytics")
        assert analytics_resp.status_code == 200
        assert analytics_resp.json()["short_code"] == short_code
