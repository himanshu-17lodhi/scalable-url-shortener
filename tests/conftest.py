import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import engine
from app.redis import redis_client
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database_engine():
    try:
        await redis_client.flushdb()
    except Exception:
        pass
    yield
    try:
        await redis_client.flushdb()
    except Exception:
        pass
    await redis_client.aclose()
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
