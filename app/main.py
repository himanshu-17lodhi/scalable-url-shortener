from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import check_database_connection, engine, init_db
from app.redis import check_redis_connection, redis_client
from app.routes.url_routes import redirect_router, router as url_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    # Cleanup resources on app shutdown
    await redis_client.close()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="URL Shortener & Link Analytics API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(url_router)


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    db_ok = await check_database_connection()
    redis_ok = await check_redis_connection()

    is_healthy = db_ok and redis_ok
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "unhealthy",
            "environment": settings.ENVIRONMENT,
            "database": "connected" if db_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
        },
    )


app.include_router(redirect_router)

