# Scalable URL Shortener

A production-ready asynchronous URL shortener and link analytics service built with FastAPI, PostgreSQL, SQLAlchemy 2.x async, Redis, Alembic, and Docker.

## Features

- Fast URL shortening with Base62 short-codes
- Asynchronous cache-aside URL lookup via Redis
- Token-bucket rate limiting backed by Redis Lua scripts
- Out-of-band click analytics via FastAPI BackgroundTasks
- Alembic database schema migrations
- Docker Compose containerized deployment with health checks
- Automatic database migrations on container startup

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | Deployment environment name (`development`, `staging`, `production`) |
| `DEBUG` | `false` | Enable verbose error responses and debug logs |
| `BASE_URL` | `http://localhost:8000` | Public base URL prefix for generated short links |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/url_shortener` | Async PostgreSQL database connection URI |
| `DB_POOL_SIZE` | `5` | SQLAlchemy async connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Maximum overflow connections for DB pool |
| `REDIS_URL` | `redis://redis:6379/0` | Redis client connection string |
| `CACHE_TTL_SECONDS` | `3600` | Redis cache-aside key expiration time in seconds |
| `RATE_LIMIT_ENABLED` | `true` | Enable Redis token-bucket rate limiting |
| `RATE_LIMIT_CAPACITY` | `10` | Maximum token capacity per client IP |
| `RATE_LIMIT_REFILL_RATE` | `1.0` | Token refill rate per second per client IP |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON array of allowed CORS origins |

## Migration & Startup Behavior

1. **Automatic Migrations**: When the Docker container starts, `docker-entrypoint.sh` executes `alembic upgrade head` before Uvicorn starts.
2. **Failure Handling**: If database migration fails, the container exits immediately with a non-zero status code (`set -e`) to prevent Uvicorn from starting on an invalid schema.
3. **Database Schema Authority**: Database migrations are managed strictly through Alembic; runtime `Base.metadata.create_all()` is removed from FastAPI startup.
4. **Rollback Procedure**:
   - To roll back a migration in a running stack:
     ```bash
     docker compose exec web alembic downgrade -1
     ```
   - To revert to a specific migration revision:
     ```bash
     docker compose exec web alembic downgrade <revision_id>
     ```

## Quick Start & Local Production Verification

1. **Start the application stack locally**:
   ```bash
   docker compose up -d --build
   ```

2. **Verify health & startup migrations**:
   ```bash
   curl http://127.0.0.1:8000/health/liveness
   curl http://127.0.0.1:8000/health
   docker compose exec web alembic current
   ```

3. **Staging verification with override config**:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d --build
   ```

4. **Verify API endpoints**:
   ```bash
   # Create URL
   curl -X POST http://127.0.0.1:8000/api/v1/urls \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/target-page"}'

   # Redirect
   curl -i http://127.0.0.1:8000/{short_code}

   # Analytics
   curl http://127.0.0.1:8000/api/v1/urls/{short_code}/analytics
   ```

## Image Build & CI/CD Pipeline

The project uses GitHub Actions (`.github/workflows/ci.yml`) for automated pipeline checks:

1. **Lint & Formatting**: `ruff check app tests` and `ruff format --check app tests`
2. **Pytest Suite**: Complete async test execution against PostgreSQL and Redis service containers
3. **Alembic Migration Check**: Migration execution (`alembic upgrade head`) and head validation (`alembic current`) on a fresh PostgreSQL instance
4. **Docker Smoke Test**: Building Docker image, launching Compose stack, and verifying live API endpoints
5. **Publish to GHCR**: Building and publishing tagged container images (`ghcr.io/himanshu-17lodhi/scalable-url-shortener`) on push to `main` and release tags (`v*.*.*`)

To manually build and tag the Docker image locally:
```bash
docker build -t ghcr.io/himanshu-17lodhi/scalable-url-shortener:latest .
```