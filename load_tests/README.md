# Load & Concurrency Testing Suite

This directory contains a lightweight, bounded load and concurrency testing suite built with Python, `asyncio`, and `httpx`.

These load tests are intentionally kept separate from standard unit/integration tests so they **do not** run automatically during `pytest` or `pre-commit` hooks.

---

## Prerequisites

Before running load tests, ensure PostgreSQL and Redis are running, database migrations are up-to-date, and the FastAPI application server is running.

### 1. Start PostgreSQL and Redis

```powershell
docker compose up -d postgres redis
```

### 2. Apply Alembic Database Migrations

```powershell
alembic upgrade head
```

### 3. Start FastAPI Server

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## Running Load Tests

Run load test modules directly using Python's module execution mode (`python -m load_tests.<script_name>`):

### 1. Redirect Load Test (`redirect_load.py`)

Measures cached URL redirect throughput (GET `/{short_code}`) and validates HTTP 307 headers under concurrent load.
By default, `--simulate-unique-ips` is enabled so distinct virtual clients are assigned unique token buckets, enabling pure application redirect throughput benchmarking without being bottlenecked by a single IP's rate limit.

```powershell
python -m load_tests.redirect_load --total 1000 --concurrency 50
```

- `--total`: Total request count (default: `1000`)
- `--concurrency`: Number of concurrent worker tasks (default: `50`)
- `--simulate-unique-ips`: Assign distinct `X-Forwarded-For` IPs to virtual clients (default: `True`)
- `--no-simulate-unique-ips`: Force all requests to originate from 1 IP to measure single-IP rate limit capping.
- `--url`: Base application URL (default: `http://127.0.0.1:8000`)

### 2. URL Creation Load Test (`create_url_load.py`)

Tests short-code generation throughput, database persistence (POST `/api/v1/urls`), and verifies unique code generation under high concurrency.

```powershell
python -m load_tests.create_url_load --total 200 --concurrency 20
```

- `--total`: Total URLs to create (default: `200`)
- `--concurrency`: Number of concurrent worker tasks (default: `20`)
- `--simulate-unique-ips`: Assign distinct client IPs (default: `True`)

### 3. Deterministic Rate Limiter Load Test (`rate_limit_load.py`)

Tests Redis token-bucket rate limiting against rate-limited application routes.
Uses a fresh, unique client IP for each benchmark run to guarantee an empty starting token bucket. Fires a sequential burst larger than capacity to verify `HTTP 429 Too Many Requests`, sleeps for the refill interval, and verifies recovery.

```powershell
python -m load_tests.rate_limit_load --requests 25 --capacity 10 --refill-seconds 2.5
```

- `--requests`: Burst requests to send (default: `25`)
- `--capacity`: Configured rate limit capacity (default: `10`)
- `--refill-seconds`: Seconds to sleep before testing refill recovery (default: `2.5`)

### 4. Analytics Consistency Load Test (`analytics_load.py`)

Tests click recording accumulation via FastAPI `BackgroundTasks` out-of-band execution.

```powershell
python -m load_tests.analytics_load --clicks 50 --concurrency 10 --drain-sleep 1.5
```

- `--clicks`: Target redirect clicks (default: `50`)
- `--concurrency`: Worker tasks for click burst (default: `10`)
- `--drain-sleep`: Seconds to wait for background tasks queue to flush (default: `1.5`)

---

## Metric Interpretation & Diagnostic Guide

The load test runner outputs a formatted metrics table with detailed status code breakdowns:

- **Throughput (RPS)**: Completed requests / total test duration.
- **Status Breakdown**:
  - `2xx`: Successful API responses (e.g. POST `/api/v1/urls` 201 Created).
  - `3xx`: Successful redirects (GET `/{short_code}` 307 Temporary Redirect).
  - `429`: Rate limited responses (HTTP 429 Too Many Requests).
  - `Other 4xx`: Client errors (e.g. 404 Not Found, 422 Validation Error).
  - `5xx`: Server errors (HTTP 500 Internal Server Error).
- **Latency (ms)**:
  - **Average**: Mean response latency.
  - **Min / Max**: Minimum and maximum recorded request latency.
  - **p50 (Median)**: 50% of requests responded faster than this value.
  - **p95**: 95% of requests responded faster than this value.
  - **p99**: 99% of requests responded faster than this value (captures tail latency).

### Performance Signals: Warning Signs vs. Failures

| Signal | Type | Cause & Resolution |
| :--- | :--- | :--- |
| **p99 Latency > 100ms** | ⚠️ Warning | Python GIL or local OS thread scheduling under heavy concurrency. |
| **Background Queue Lag** | ⚠️ Warning | In-process `BackgroundTasks` take 100–500ms to flush click writes to DB. Normal for in-process async tasks. |
| **HTTP 5xx Server Error** | ❌ Failure | Server crash or unhandled exception. Inspect Uvicorn / application logs. |
| **Missing Location Header** | ❌ Failure | Redirect endpoint failed to output standard HTTP 307 location header. |
| **Short Code Collision** | ❌ Failure | Duplicate `short_code` generated during concurrent POST requests. |
| **Rate Limiter Bypass** | ❌ Failure | Requests exceeding capacity were permitted without returning HTTP 429. |
| **Click Count Mismatch** | ❌ Failure | Recorded click count in `/analytics` does not match completed redirects after queue drain. |

### Architecture Limitation Note on Analytics
FastAPI `BackgroundTasks` execute in-process within the web worker process. This benchmark proves that `BackgroundTasks` completed successfully under controlled test execution.
It does **NOT** prove durable delivery under process crashes, application restarts, or worker termination (`SIGKILL`). A durable queue (e.g. RabbitMQ or Redis Streams with Celery) would be required for zero-loss delivery guarantees.
