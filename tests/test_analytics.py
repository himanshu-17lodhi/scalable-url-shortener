import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.models.click import Click
from app.models.url import URL
from app.redis import redis_client


@pytest.mark.asyncio
async def test_redirect_creates_click_record(client: AsyncClient):
    await init_db()
    raw_url = "https://pytest-analytics-single.org"

    create_resp = await client.post("/api/v1/urls", json={"url": raw_url})
    assert create_resp.status_code == 201
    short_code = create_resp.json()["short_code"]

    # Redirect request
    redirect_resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_resp.status_code == 307

    # Give background task a brief tick to finish DB write
    await asyncio.sleep(0.1)

    # Check database clicks table
    async with AsyncSessionLocal() as session:
        url_stmt = select(URL).where(URL.short_code == short_code)
        url_res = await session.execute(url_stmt)
        url_obj = url_res.scalar_one_or_none()
        assert url_obj is not None

        click_stmt = select(Click).where(Click.url_id == url_obj.id)
        click_res = await session.execute(click_stmt)
        clicks = click_res.scalars().all()
        assert len(clicks) == 1

        # Cleanup
        await session.delete(url_obj)
        await session.commit()
    await redis_client.delete(f"url:{short_code}")


@pytest.mark.asyncio
async def test_multiple_redirects_accumulate_clicks(client: AsyncClient):
    await init_db()
    raw_url = "https://pytest-analytics-multiple.org"

    create_resp = await client.post("/api/v1/urls", json={"url": raw_url})
    short_code = create_resp.json()["short_code"]

    # Issue 3 redirect requests
    for _ in range(3):
        redirect_resp = await client.get(f"/{short_code}", follow_redirects=False)
        assert redirect_resp.status_code == 307
        await asyncio.sleep(0.05)

    # Call analytics endpoint
    analytics_resp = await client.get(f"/api/v1/urls/{short_code}/analytics")
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert data["short_code"] == short_code
    assert data["total_clicks"] == 3
    assert data["last_clicked_at"] is not None

    # Cleanup DB and Redis
    async with AsyncSessionLocal() as session:
        url_stmt = select(URL).where(URL.short_code == short_code)
        url_res = await session.execute(url_stmt)
        url_obj = url_res.scalar_one_or_none()
        if url_obj:
            await session.delete(url_obj)
            await session.commit()
    await redis_client.delete(f"url:{short_code}")


@pytest.mark.asyncio
async def test_analytics_endpoint_unknown_short_code(client: AsyncClient):
    await init_db()

    analytics_resp = await client.get("/api/v1/urls/unknown_code_999/analytics")
    assert analytics_resp.status_code == 404
    data = analytics_resp.json()
    assert data["detail"] == "Short URL not found"


@pytest.mark.asyncio
async def test_cache_hit_triggers_analytics(client: AsyncClient):
    await init_db()
    raw_url = "https://pytest-analytics-cachehit.org"

    create_resp = await client.post("/api/v1/urls", json={"url": raw_url})
    short_code = create_resp.json()["short_code"]

    # 1st request -> Cache miss
    await client.get(f"/{short_code}", follow_redirects=False)
    await asyncio.sleep(0.05)

    # 2nd request -> Cache hit (from Redis)
    await client.get(f"/{short_code}", follow_redirects=False)
    await asyncio.sleep(0.05)

    # Verify total clicks is 2
    analytics_resp = await client.get(f"/api/v1/urls/{short_code}/analytics")
    assert analytics_resp.status_code == 200
    assert analytics_resp.json()["total_clicks"] == 2

    # Cleanup
    async with AsyncSessionLocal() as session:
        url_stmt = select(URL).where(URL.short_code == short_code)
        url_res = await session.execute(url_stmt)
        url_obj = url_res.scalar_one_or_none()
        if url_obj:
            await session.delete(url_obj)
            await session.commit()
    await redis_client.delete(f"url:{short_code}")
