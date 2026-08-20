from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "environment" in data
    assert data["health"] == "/health"


@pytest.mark.asyncio
@patch("app.main.check_database_connection", new_callable=AsyncMock)
@patch("app.main.check_redis_connection", new_callable=AsyncMock)
async def test_health_endpoint_healthy(
    mock_redis_check: AsyncMock,
    mock_db_check: AsyncMock,
    client: AsyncClient,
):
    mock_db_check.return_value = True
    mock_redis_check.return_value = True

    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
@patch("app.main.check_database_connection", new_callable=AsyncMock)
@patch("app.main.check_redis_connection", new_callable=AsyncMock)
async def test_health_endpoint_unhealthy(
    mock_redis_check: AsyncMock,
    mock_db_check: AsyncMock,
    client: AsyncClient,
):
    mock_db_check.return_value = False
    mock_redis_check.return_value = True

    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["database"] == "disconnected"
    assert data["redis"] == "connected"
