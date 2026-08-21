# Scalable URL Shortener

An asynchronous URL shortener and link analytics API built with FastAPI, PostgreSQL, Redis, Alembic, and Docker.

## Features

- **URL Shortening & Redirects**: Generates 6-character Base62 short codes and returns HTTP 307 redirects.
- **Cache-Aside Lookups**: Uses Redis to cache short code lookups for faster redirects.
- **Rate Limiting**: Redis token-bucket rate limiting to prevent API abuse.
- **Click Analytics**: Asynchronous click tracking processed out-of-band using FastAPI `BackgroundTasks`.
- **API Hardening**: Request ID middleware, strict path regex validation, CORS configuration, and security headers.
- **Database Migrations**: Schema migrations managed strictly through Alembic.
- **Containerized Deployment**: Runs via Docker Compose with health checks and automatic startup migrations.

## Tech Stack

- **Python 3.11** / **FastAPI**
- **PostgreSQL** / **SQLAlchemy 2.x async** (`asyncpg`)
- **Redis** (caching and rate limiting)
- **Alembic** (database migrations)
- **Docker** & **Docker Compose**
- **GitHub Actions** (CI/CD)
- **pytest** & **Ruff**

## Project Structure

```text
scalable-url-shortener/
├── app/                  # FastAPI routes, models, schemas, services, and middleware
├── alembic/              # Database migration scripts and environment config
├── tests/                # Async test suite (analytics, cache, rate limiting, health, etc.)
├── scripts/              # Release verification and helper scripts
├── load_tests/           # Load benchmarking scripts
├── .github/workflows/    # GitHub Actions CI/CD pipeline
├── Dockerfile            # Container image definition
├── docker-compose.yml    # Main compose file (web, postgres, redis)
└── docker-entrypoint.sh  # Container entrypoint running migrations before Uvicorn
```

## Running Locally

1. **Clone the repository and set up a virtual environment**:
   ```powershell
   git clone https://github.com/himanshu-17lodhi/scalable-url-shortener.git
   cd scalable-url-shortener
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL and Redis**:
   ```powershell
   docker compose up -d postgres redis
   ```

3. **Run database migrations and start the server**:
   ```powershell
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

4. **Access the API**:
   - Interactive API documentation: `http://127.0.0.1:8000/docs`
   - Health endpoint: `http://127.0.0.1:8000/health`

## Using the API

### 1. Create a Short URL
```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/urls" -ContentType "application/json" -Body '{"url": "https://example.com/target-page"}'
```

Sample Response:
```json
{
  "short_code": "BICkLa",
  "short_url": "http://localhost:8000/BICkLa",
  "original_url": "https://example.com/target-page"
}
```

### 2. Access the Short URL (HTTP 307 Redirect)
```powershell
python -c "import httpx; r = httpx.get('http://127.0.0.1:8000/BICkLa', follow_redirects=False); print(r.status_code, r.headers['location'])"
```

### 3. Check Click Analytics
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/urls/BICkLa/analytics"
```

## Testing

Run the test suite:
```powershell
python -m pytest
```

Run linter and formatting checks:
```powershell
pre-commit run --all-files
```

The test suite contains 43 automated tests covering URL creation, Base62 validation, 307 redirects, Redis cache hits and misses, token-bucket rate limiting, security headers, and release/rollback behavior.

## Docker

Start the full application stack with Docker Compose:
```powershell
docker compose up -d --build
```

The container startup script (`docker-entrypoint.sh`) runs `alembic upgrade head` before Uvicorn starts. If migrations fail, the container exits immediately with a non-zero exit code.

To test with staging override configuration:
```powershell
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d --build
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) automatically runs:
- Linting and formatting checks with Ruff
- Test suite execution against PostgreSQL and Redis service containers
- Alembic database migration check
- Docker Compose build and live endpoint smoke test
- Publishing tagged container images to GitHub Container Registry (GHCR) on `main` and release tags (`v*.*.*`)

## Release and Rollback

- Images are tagged by Git commit SHA, `latest`, and semver release tags (e.g., `v1.0.0`).
- Local release verification script:
  ```powershell
  python scripts/verify_release.py
  ```
- Application rollback is done by updating the web image version. Database migrations are managed separately to prevent accidental data loss.