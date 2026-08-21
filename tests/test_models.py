import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import AsyncSessionLocal, init_db
from app.models.url import URL


@pytest.mark.asyncio
async def test_url_model_create_and_read():
    await init_db()

    async with AsyncSessionLocal() as session:
        test_url = URL(
            original_url="https://example.com/test-stage-2", short_code="stg2test"
        )
        session.add(test_url)
        await session.commit()
        await session.refresh(test_url)

        assert test_url.id is not None
        assert test_url.original_url == "https://example.com/test-stage-2"
        assert test_url.short_code == "stg2test"
        assert test_url.created_at is not None
        assert test_url.updated_at is not None

        # Query back
        stmt = select(URL).where(URL.short_code == "stg2test")
        result = await session.execute(stmt)
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.original_url == "https://example.com/test-stage-2"

        # Cleanup
        await session.delete(fetched)
        await session.commit()


@pytest.mark.asyncio
async def test_url_short_code_unique_constraint():
    await init_db()

    async with AsyncSessionLocal() as session:
        url1 = URL(original_url="https://example.com/original-1", short_code="uniqcode")
        session.add(url1)
        await session.commit()

    async with AsyncSessionLocal() as session:
        url2 = URL(original_url="https://example.com/original-2", short_code="uniqcode")
        session.add(url2)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    # Cleanup url1
    async with AsyncSessionLocal() as session:
        stmt = select(URL).where(URL.short_code == "uniqcode")
        result = await session.execute(stmt)
        fetched = result.scalar_one_or_none()
        if fetched:
            await session.delete(fetched)
            await session.commit()
