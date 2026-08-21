import redis.asyncio as aioredis
from app.config import settings

redis_client = aioredis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=2.0,
    socket_connect_timeout=2.0,
    retry_on_timeout=True,
)


async def get_redis_client() -> aioredis.Redis:
    return redis_client


async def check_redis_connection() -> bool:
    try:
        return await redis_client.ping()
    except Exception:
        return False
