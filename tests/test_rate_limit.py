import asyncio
from unittest.mock import patch
import pytest
from httpx import AsyncClient
import redis.asyncio as aioredis

from app.config import settings
from app.database import init_db
from app.rate_limiter import check_rate_limit
from app.redis import redis_client


@pytest.mark.asyncio
async def test_requests_within_limit_succeed(client: AsyncClient):
    await init_db()
    ip = "192.168.1.1"
    await redis_client.delete(f"ratelimit:{ip}")

    # Capacity is settings.RATE_LIMIT_CAPACITY (10)
    for _ in range(settings.RATE_LIMIT_CAPACITY):
        resp = await client.get("/health", headers={"X-Forwarded-For": ip})
        assert resp.status_code == 200

    await redis_client.delete(f"ratelimit:{ip}")


@pytest.mark.asyncio
async def test_requests_exceeding_limit_return_429(client: AsyncClient):
    await init_db()
    ip = "192.168.1.2"
    cache_key = f"ratelimit:{ip}"
    await redis_client.delete(cache_key)

    headers = {"X-Forwarded-For": ip}

    # Create a short URL to test API endpoint
    create_resp = await client.post(
        "/api/v1/urls", json={"url": "https://pytest-ratelimit.org"}, headers=headers
    )
    assert create_resp.status_code == 201

    # Exhaust remaining capacity
    for _ in range(settings.RATE_LIMIT_CAPACITY - 1):
        resp = await client.post(
            "/api/v1/urls",
            json={"url": "https://pytest-ratelimit.org"},
            headers=headers,
        )
        assert resp.status_code == 201

    # 11th request exceeds limit -> HTTP 429
    exceeded_resp = await client.post(
        "/api/v1/urls", json={"url": "https://pytest-ratelimit.org"}, headers=headers
    )
    assert exceeded_resp.status_code == 429
    assert exceeded_resp.json()["detail"] == "Rate limit exceeded"

    await redis_client.delete(cache_key)


@pytest.mark.asyncio
async def test_tokens_refill_over_time(client: AsyncClient):
    await init_db()
    ip = "192.168.1.3"
    cache_key = f"ratelimit:{ip}"
    await redis_client.delete(cache_key)

    # Use small capacity (2 tokens) and fast refill (2 tokens/sec)
    allowed1, _ = await check_rate_limit(ip, capacity=2, refill_rate=2.0)
    assert allowed1 is True

    allowed2, _ = await check_rate_limit(ip, capacity=2, refill_rate=2.0)
    assert allowed2 is True

    # 3rd request exhausted
    allowed3, _ = await check_rate_limit(ip, capacity=2, refill_rate=2.0)
    assert allowed3 is False

    # Sleep 1 second to refill ~2 tokens
    await asyncio.sleep(1.1)

    # Now allowed again
    allowed4, _ = await check_rate_limit(ip, capacity=2, refill_rate=2.0)
    assert allowed4 is True

    await redis_client.delete(cache_key)


@pytest.mark.asyncio
async def test_separate_clients_have_separate_limits(client: AsyncClient):
    await init_db()
    client_a = "10.0.0.1"
    client_b = "10.0.0.2"
    await redis_client.delete(f"ratelimit:{client_a}")
    await redis_client.delete(f"ratelimit:{client_b}")

    headers_a = {"X-Forwarded-For": client_a}
    headers_b = {"X-Forwarded-For": client_b}

    # Exhaust client A
    for _ in range(settings.RATE_LIMIT_CAPACITY):
        res_a = await client.post(
            "/api/v1/urls", json={"url": "https://client-a.com"}, headers=headers_a
        )
        assert res_a.status_code == 201

    res_a_exceeded = await client.post(
        "/api/v1/urls", json={"url": "https://client-a.com"}, headers=headers_a
    )
    assert res_a_exceeded.status_code == 429

    # Client B should still succeed
    res_b = await client.post(
        "/api/v1/urls", json={"url": "https://client-b.com"}, headers=headers_b
    )
    assert res_b.status_code == 201

    await redis_client.delete(f"ratelimit:{client_a}")
    await redis_client.delete(f"ratelimit:{client_b}")


@pytest.mark.asyncio
async def test_concurrent_requests_rate_limiting(client: AsyncClient):
    await init_db()
    ip = "192.168.1.4"
    cache_key = f"ratelimit:{ip}"
    await redis_client.delete(cache_key)

    headers = {"X-Forwarded-For": ip}

    # Issue 15 concurrent requests
    async def make_req():
        return await client.post(
            "/api/v1/urls", json={"url": "https://concurrent.org"}, headers=headers
        )

    tasks = [make_req() for _ in range(15)]
    responses = await asyncio.gather(*tasks)

    status_codes = [r.status_code for r in responses]
    success_count = status_codes.count(201)
    rate_limited_count = status_codes.count(429)

    assert success_count == settings.RATE_LIMIT_CAPACITY
    assert rate_limited_count == 5

    await redis_client.delete(cache_key)


@pytest.mark.asyncio
async def test_rate_limit_redis_failure_behavior(client: AsyncClient):
    await init_db()
    ip = "192.168.1.5"
    headers = {"X-Forwarded-For": ip}

    # Mock redis_client.eval to raise aioredis.RedisError simulating Redis error during rate limiting
    with patch.object(
        redis_client,
        "eval",
        side_effect=aioredis.RedisError("Redis connection failure"),
    ):
        resp = await client.post(
            "/api/v1/urls", json={"url": "https://failopen.org"}, headers=headers
        )
        assert resp.status_code == 201
