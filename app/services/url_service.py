import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.url import URL
from app.redis import redis_client
from app.schemas.url import URLCreateResponse
from app.utils.short_code import generate_short_code

logger = logging.getLogger(__name__)


async def create_short_url(
    db: AsyncSession,
    original_url: str,
    base_url: str = "http://localhost:8000",
    max_retries: int = 5,
) -> URLCreateResponse:
    """
    Create a new shortened URL mapping in PostgreSQL.
    Retries short-code generation on database unique constraint collisions.
    """
    attempts = 0
    while attempts < max_retries:
        short_code = generate_short_code()
        url_obj = URL(
            original_url=original_url,
            short_code=short_code,
        )
        db.add(url_obj)
        try:
            await db.commit()
            await db.refresh(url_obj)
            short_url = f"{base_url.rstrip('/')}/{short_code}"
            return URLCreateResponse(
                short_code=short_code,
                short_url=short_url,
                original_url=original_url,
            )
        except IntegrityError:
            await db.rollback()
            attempts += 1

    raise RuntimeError("Failed to generate unique short code after maximum retries")


async def get_original_url(db: AsyncSession, short_code: str) -> str | None:
    """
    Look up original URL by short code using Cache-Aside strategy with Redis.
    Falls back to PostgreSQL if Redis is unavailable or on cache miss.
    """
    cache_key = f"url:{short_code}"

    # 1. Check Redis Cache
    try:
        cached_url = await redis_client.get(cache_key)
        if cached_url is not None:
            return cached_url
    except Exception as exc:
        logger.warning(f"Redis cache lookup failed for {cache_key}: {exc}")

    # 2. Cache Miss or Redis Error -> Query PostgreSQL
    stmt = select(URL.original_url).where(URL.short_code == short_code)
    result = await db.execute(stmt)
    original_url = result.scalar_one_or_none()

    # 3. Populate Cache if found in PostgreSQL
    if original_url is not None:
        try:
            await redis_client.set(
                cache_key,
                original_url,
                ex=settings.CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(f"Redis cache population failed for {cache_key}: {exc}")

    return original_url
