import logging
import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import settings
from app.redis import redis_client

logger = logging.getLogger(__name__)

# Atomic Token-Bucket Lua Script
TOKEN_BUCKET_LUA_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local data = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_updated = now
else
    local delta = math.max(0, now - last_updated)
    tokens = math.min(capacity, tokens + delta * refill_rate)
    last_updated = now
end

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    redis.call('EXPIRE', key, ttl)
    return {1, math.floor(tokens)}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    redis.call('EXPIRE', key, ttl)
    return {0, math.floor(tokens)}
end
"""


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address safely.
    Only parses X-Forwarded-For header if TRUST_PROXY_HEADERS is True and the direct connection
    comes from a trusted proxy IP in TRUSTED_PROXIES.
    Otherwise, uses request.client.host directly to prevent header spoofing.
    """
    direct_ip = (
        request.client.host if request.client and request.client.host else "127.0.0.1"
    )

    if settings.TRUST_PROXY_HEADERS and direct_ip in settings.TRUSTED_PROXIES:
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

    return direct_ip


async def check_rate_limit(
    client_ip: str,
    capacity: int | None = None,
    refill_rate: float | None = None,
) -> tuple[bool, int]:
    """
    Executes atomic Token-Bucket check in Redis for client_ip.
    Returns (allowed: bool, remaining_tokens: int).
    """
    if not settings.RATE_LIMIT_ENABLED:
        return True, 999

    cap = capacity if capacity is not None else settings.RATE_LIMIT_CAPACITY
    rate = refill_rate if refill_rate is not None else settings.RATE_LIMIT_REFILL_RATE
    now = time.time()
    key = f"ratelimit:{client_ip}"
    ttl = int(cap / rate) + 60 if rate > 0 else 3600

    try:
        res = await redis_client.eval(
            TOKEN_BUCKET_LUA_SCRIPT,
            1,  # number of keys
            key,
            cap,
            rate,
            now,
            1,  # requested 1 token
            ttl,
        )
        allowed = bool(res[0])
        remaining = int(res[1])
        return allowed, remaining
    except aioredis.RedisError as exc:
        logger.warning(
            f"Redis rate limit check failed for '{key}': {exc}. Failing open."
        )
        return True, cap


async def rate_limiter_dependency(request: Request) -> None:
    """
    FastAPI dependency enforcing token-bucket rate limits per client IP.
    Raises HTTP 429 when limit is exceeded.
    """
    client_ip = get_client_ip(request)
    allowed, _ = await check_rate_limit(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
