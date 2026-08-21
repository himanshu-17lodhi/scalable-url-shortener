from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.url import URL
from app.redis import redis_client


@pytest.mark.asyncio
async def test_cache_miss_queries_postgres_and_populates_redis(client: AsyncClient):
    raw_url = "https://pytest-cache-miss.org"

    # Create URL via API
    create_resp = await client.post("/api/v1/urls", json={"url": raw_url})
    assert create_resp.status_code == 201
    data = create_resp.json()
    short_code = data["short_code"]
    expected_url = data["original_url"]
    cache_key = f"url:{short_code}"

    # Ensure Redis key does not exist before first request
    await redis_client.delete(cache_key)
    val_before = await redis_client.get(cache_key)
    assert val_before is None

    # First request: Cache miss -> queries DB -> populates Redis
    redirect_resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_resp.status_code == 307
    assert redirect_resp.headers["location"] == expected_url

    # Check that Redis now contains the value
    val_after = await redis_client.get(cache_key)
    assert val_after == expected_url

    # Cleanup DB and Redis
    await redis_client.delete(cache_key)
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code == short_code)
        res = await session.execute(stmt)
        obj = res.scalar_one_or_none()
        if obj:
            await session.delete(obj)
            await session.commit()


@pytest.mark.asyncio
async def test_cache_hit_bypasses_postgres_lookup(client: AsyncClient):
    short_code = "cach01"
    original_url = "https://pytest-cache-hit.org/"

    cache_key = f"url:{short_code}"

    # Pre-populate Redis cache directly
    await redis_client.set(cache_key, original_url, ex=settings.CACHE_TTL_SECONDS)

    # Mock record_click background task so DB isn't called by analytics,
    # and patch AsyncSession.execute to verify get_original_url does NOT query DB
    with (
        patch("app.routes.url_routes.record_click"),
        patch.object(AsyncSession, "execute", new_callable=AsyncMock) as mock_execute,
    ):
        redirect_resp = await client.get(f"/{short_code}", follow_redirects=False)
        assert redirect_resp.status_code == 307
        assert redirect_resp.headers["location"] == original_url
        mock_execute.assert_not_called()

    # Cleanup Redis
    await redis_client.delete(cache_key)


@pytest.mark.asyncio
async def test_cache_ttl_configuration(client: AsyncClient):
    raw_url = "https://pytest-cache-ttl.org"

    create_resp = await client.post("/api/v1/urls", json={"url": raw_url})
    data = create_resp.json()
    short_code = data["short_code"]
    cache_key = f"url:{short_code}"

    # Perform redirect to populate cache
    await client.get(f"/{short_code}", follow_redirects=False)

    # Check TTL in Redis
    ttl = await redis_client.ttl(cache_key)
    assert 0 < ttl <= settings.CACHE_TTL_SECONDS

    # Cleanup DB and Redis
    await redis_client.delete(cache_key)
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code == short_code)
        res = await session.execute(stmt)
        obj = res.scalar_one_or_none()
        if obj:
            await session.delete(obj)
            await session.commit()


@pytest.mark.asyncio
async def test_redis_failure_fallback(client: AsyncClient):
    raw_url = "https://pytest-redis-failure.org"

    create_resp = await client.post("/api/v1/urls", json={"url": raw_url})
    data = create_resp.json()
    short_code = data["short_code"]
    expected_url = data["original_url"]

    # Mock redis_client.get to raise Exception simulating Redis downtime
    with patch.object(
        redis_client, "get", side_effect=Exception("Redis connection error")
    ):
        redirect_resp = await client.get(f"/{short_code}", follow_redirects=False)
        assert redirect_resp.status_code == 307
        assert redirect_resp.headers["location"] == expected_url

    # Cleanup DB
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code == short_code)
        res = await session.execute(stmt)
        obj = res.scalar_one_or_none()
        if obj:
            await session.delete(obj)
            await session.commit()
