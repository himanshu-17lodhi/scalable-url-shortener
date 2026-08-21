import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.url import URL


@pytest.mark.asyncio
async def test_redirect_success(client: AsyncClient):
    original_url = "https://example.com/target-redirect-page"

    # Create URL via API
    create_resp = await client.post("/api/v1/urls", json={"url": original_url})
    assert create_resp.status_code == 201
    short_code = create_resp.json()["short_code"]

    # Issue GET request with follow_redirects=False to inspect redirect response
    redirect_resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_resp.status_code == 307
    assert redirect_resp.headers["location"] == original_url

    # Cleanup DB
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code == short_code)
        res = await session.execute(stmt)
        obj = res.scalar_one_or_none()
        if obj:
            await session.delete(obj)
            await session.commit()


@pytest.mark.asyncio
async def test_redirect_unknown_short_code(client: AsyncClient):
    response = await client.get("/unk123", follow_redirects=False)
    assert response.status_code == 404

    data = response.json()
    assert data["detail"] == "Short URL not found"


@pytest.mark.asyncio
async def test_redirect_status_and_location_headers(client: AsyncClient):
    original_url = "https://python.org/doc"

    create_resp = await client.post("/api/v1/urls", json={"url": original_url})
    short_code = create_resp.json()["short_code"]

    resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert resp.status_code == 307
    assert "location" in resp.headers
    assert resp.headers["location"] == original_url

    # Cleanup DB
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code == short_code)
        res = await session.execute(stmt)
        obj = res.scalar_one_or_none()
        if obj:
            await session.delete(obj)
            await session.commit()


@pytest.mark.asyncio
async def test_url_creation_and_redirect_workflow(client: AsyncClient):
    original_url = "https://fastapi.tiangolo.com/tutorial"

    # Step 1: Create short URL
    create_resp = await client.post("/api/v1/urls", json={"url": original_url})
    assert create_resp.status_code == 201
    data = create_resp.json()
    short_code = data["short_code"]

    # Step 2: Perform redirect
    redirect_resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_resp.status_code == 307
    assert redirect_resp.headers["location"] == original_url

    # Cleanup
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code == short_code)
        res = await session.execute(stmt)
        obj = res.scalar_one_or_none()
        if obj:
            await session.delete(obj)
            await session.commit()
