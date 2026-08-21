from unittest.mock import patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.url import URL
from app.services.url_service import create_short_url
from app.utils.short_code import generate_short_code


def test_generate_short_code():
    code1 = generate_short_code()
    assert len(code1) == 6
    assert code1.isalnum()

    code2 = generate_short_code(8)
    assert len(code2) == 8
    assert code2.isalnum()


@pytest.mark.asyncio
async def test_create_url_endpoint_success(client: AsyncClient):
    target_url = "https://example.com/stage3-test-url"

    response = await client.post("/api/v1/urls", json={"url": target_url})
    assert response.status_code == 201

    data = response.json()
    assert "short_code" in data
    assert "short_url" in data
    assert data["original_url"] == target_url
    assert data["short_url"] == f"http://localhost:8000/{data['short_code']}"

    # Verify persistence in database
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code == data["short_code"])
        result = await session.execute(stmt)
        url_obj = result.scalar_one_or_none()
        assert url_obj is not None
        assert url_obj.original_url == target_url

        # Cleanup
        await session.delete(url_obj)
        await session.commit()


@pytest.mark.asyncio
async def test_create_url_endpoint_invalid_url(client: AsyncClient):
    # Test invalid string URL
    response = await client.post("/api/v1/urls", json={"url": "not-a-valid-url"})
    assert response.status_code == 422

    # Test missing payload
    response = await client.post("/api/v1/urls", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_url_collision_handling():
    target_url = "https://example.com/collision-test"

    # Pre-insert a URL with a known short code "collision1"
    async with AsyncSessionLocal() as session:
        existing_url = URL(
            original_url="https://example.com/existing", short_code="collision1"
        )
        session.add(existing_url)
        await session.commit()

    # Patch generate_short_code to return "collision1" on first call, and "unique2" on second call
    mock_codes = ["collision1", "unique2"]
    with patch("app.services.url_service.generate_short_code", side_effect=mock_codes):
        async with AsyncSessionLocal() as session:
            result = await create_short_url(session, target_url)
            assert result.short_code == "unique2"
            assert result.original_url == target_url

    # Cleanup both created records
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code.in_(["collision1", "unique2"]))
        res = await session.execute(stmt)
        for obj in res.scalars().all():
            await session.delete(obj)
        await session.commit()
