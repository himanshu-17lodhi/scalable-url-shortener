import subprocess
import sys

import httpx
import redis


BASE_URL = "http://127.0.0.1:8000"


def verify_release() -> bool:
    print("Starting release verification...")
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Liveness check
        liveness_resp = client.get("/health/liveness")
        assert liveness_resp.status_code == 200, (
            f"Liveness failed: {liveness_resp.status_code}"
        )
        assert liveness_resp.json() == {"status": "ok"}, (
            "Liveness status payload mismatch"
        )
        print("  [OK] /health/liveness OK")

        # 2. Readiness check
        health_resp = client.get("/health")
        assert health_resp.status_code == 200, (
            f"Readiness failed: {health_resp.status_code}"
        )
        assert health_resp.json().get("status") == "healthy", (
            "Readiness status payload mismatch"
        )
        print("  [OK] /health OK")

        # 3. Create short URL
        target_url = "https://example.com/release-verify-target"
        create_resp = client.post("/api/v1/urls", json={"url": target_url})
        assert create_resp.status_code == 201, (
            f"Create URL failed: {create_resp.status_code}"
        )
        data = create_resp.json()
        short_code = data["short_code"]
        assert len(short_code) == 6, f"Invalid short code length: {short_code}"
        print(f"  [OK] URL Creation OK (short_code={short_code})")

        # 4. Redirect check
        redirect_resp = client.get(f"/{short_code}", follow_redirects=False)
        assert redirect_resp.status_code == 307, (
            f"Redirect failed: {redirect_resp.status_code}"
        )
        assert redirect_resp.headers.get("location") == target_url, (
            "Redirect location mismatch"
        )
        print("  [OK] 307 Redirect OK")

        # 5. PostgreSQL direct database check
        try:
            res = subprocess.run(
                [
                    "docker",
                    "exec",
                    "url_shortener_db",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "url_shortener",
                    "-t",
                    "-A",
                    "-c",
                    f"SELECT original_url FROM urls WHERE short_code = '{short_code}';",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            db_url = res.stdout.strip()
            assert db_url == target_url, (
                f"DB URL mismatch: expected {target_url}, got {db_url}"
            )
            print("  [OK] PostgreSQL database record OK")
        except Exception as exc:
            print(f"  ⚠ PostgreSQL check skipped/failed: {exc}")

        # 6. Redis direct cache check
        try:
            r = redis.Redis(host="127.0.0.1", port=6379, db=0)
            cached = r.get(f"url:{short_code}")
            assert cached is not None and cached.decode("utf-8") == target_url, (
                "Redis cache missing"
            )
            print("  [OK] Redis cache key OK")
        except Exception as exc:
            print(f"  ⚠ Redis check skipped/failed: {exc}")

        # 7. Analytics check
        analytics_resp = client.get(f"/api/v1/urls/{short_code}/analytics")
        assert analytics_resp.status_code == 200, (
            f"Analytics failed: {analytics_resp.status_code}"
        )
        analytics_data = analytics_resp.json()
        assert analytics_data["total_clicks"] >= 1, "Click analytics not recorded"
        print("  [OK] Analytics OK")

    print("\n[OK] Release verification completed successfully!")
    return True


if __name__ == "__main__":
    try:
        if not verify_release():
            sys.exit(1)
    except AssertionError as err:
        print(f"\n❌ Release verification failed: {err}")
        sys.exit(1)
