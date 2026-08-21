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

## Quick Start with Docker Compose

1. **Start the application stack**:
   ```bash
   docker compose up -d --build
   ```
   The container startup script automatically runs `alembic upgrade head` to apply database migrations before starting Uvicorn.

2. **Verify application health**:
   ```bash
   curl http://127.0.0.1:8000/health/liveness
   curl http://127.0.0.1:8000/health
   ```

3. **Create a short URL**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/urls \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/target-page"}'
   ```

4. **Test redirect**:
   ```bash
   curl -i http://127.0.0.1:8000/{short_code}
   ```

5. **View click analytics**:
   ```bash
   curl http://127.0.0.1:8000/api/v1/urls/{short_code}/analytics
   ```

## CI/CD Pipeline

The project uses GitHub Actions (`.github/workflows/ci.yml`) to enforce production quality on every commit and pull request:

1. **Lint & Formatting**: `ruff check app tests` and `ruff format --check app tests`
2. **Pytest Suite**: Complete async test execution against PostgreSQL and Redis service containers
3. **Alembic Migration Verification**: Migration execution (`alembic upgrade head`) and head validation (`alembic current`) on a fresh PostgreSQL instance
4. **Docker Build & Smoke Test**: Building Docker image, starting full stack with Docker Compose, verifying health endpoints, URL creation, 307 redirects, and click analytics

## Local Production-Like Verification

To run full production-like verification locally:

```bash
# 1. Code quality & unit tests
python -m pytest
pre-commit run --all-files

# 2. Docker Compose stack build & clean launch
docker compose config
docker compose down -v
docker compose build --no-cache
docker compose up -d

# 3. Verify health & automatic startup migrations
curl http://127.0.0.1:8000/health/liveness
curl http://127.0.0.1:8000/health
docker compose exec web alembic current

# 4. Verify endpoints
curl -X POST http://127.0.0.1:8000/api/v1/urls -H "Content-Type: application/json" -d '{"url":"https://example.com/test"}'
curl -i http://127.0.0.1:8000/{short_code}
curl http://127.0.0.1:8000/api/v1/urls/{short_code}/analytics
```