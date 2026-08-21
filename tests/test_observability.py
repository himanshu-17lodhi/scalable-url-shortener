import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_request_id_generated_and_returned():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/liveness")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0


@pytest.mark.asyncio
async def test_request_id_preserved_when_provided():
    custom_id = "test-req-id-12345"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/health/liveness", headers={"X-Request-ID": custom_id}
        )
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == custom_id


@pytest.mark.asyncio
async def test_security_headers_present():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/liveness")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"


@pytest.mark.asyncio
async def test_liveness_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/liveness")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_short_code_path_validation_cases():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Valid 6-character alphanumeric code -> passes validation (returns 404 because not in DB)
        valid_resp = await client.get("/aB3xZ9", follow_redirects=False)
        assert valid_resp.status_code == 404

        # 2. Too short code (5 chars) -> fails validation (422)
        short_resp = await client.get("/aB3xZ")
        assert short_resp.status_code == 422

        # 3. Too long code (7 chars) -> fails validation (422)
        long_resp = await client.get("/aB3xZ99")
        assert long_resp.status_code == 422

        # 4. Invalid characters (! symbol) -> fails validation (422)
        invalid_char_resp = await client.get("/aB3!Z9")
        assert invalid_char_resp.status_code == 422


@pytest.mark.asyncio
async def test_malformed_or_overly_long_request_id_sanitized():
    overly_long_id = "x" * 100
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/health/liveness", headers={"X-Request-ID": overly_long_id}
        )
        assert response.status_code == 200
        ret_id = response.headers.get("X-Request-ID")
        assert ret_id != overly_long_id
        assert len(ret_id) == 12


@pytest.mark.asyncio
async def test_cors_preflight_headers():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/api/v1/urls",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )
