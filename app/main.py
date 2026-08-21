import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import check_database_connection, engine
from app.redis import check_redis_connection, redis_client
from app.routes.url_routes import redirect_router
from app.routes.url_routes import router as url_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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


def sanitize_request_id(incoming_id: str | None) -> str:
    if (
        incoming_id
        and 1 <= len(incoming_id) <= 64
        and incoming_id.replace("-", "").replace("_", "").isalnum()
    ):
        return incoming_id
    return uuid.uuid4().hex[:12]


if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    raw_id = request.headers.get("X-Request-ID")
    request_id = sanitize_request_id(raw_id)
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"

    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {elapsed_ms:.2f}ms - req_id={request_id}"
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        f"Unhandled exception processing {request.method} {request.url} (req_id={req_id}): {exc}",
        exc_info=exc,
    )

    detail = str(exc) if settings.DEBUG else "Internal server error"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
        headers={
            "X-Request-ID": req_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
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


@app.get("/health/liveness", summary="Liveness probe")
async def liveness_check():
    return {"status": "ok"}


@app.get("/health", summary="Readiness probe")
async def health_check():
    db_ok = await check_database_connection()
    redis_ok = await check_redis_connection()

    is_healthy = db_ok and redis_ok
    status_code = (
        status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )

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
