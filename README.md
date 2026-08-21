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

## Running Tests

Run unit & integration tests:
```bash
python -m pytest
```

Run pre-commit quality checks:
```bash
pre-commit run --all-files
```

Run load tests manually:
```bash
python -m load_tests.redirect_load --total 500 --concurrency 25
```