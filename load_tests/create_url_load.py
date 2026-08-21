import argparse
import asyncio
import time

from httpx import AsyncClient

from load_tests.common import print_summary_table, run_worker_pool


async def main():
    parser = argparse.ArgumentParser(description="URL Creation Load Test")
    parser.add_argument("--total", type=int, default=200, help="Total URLs to create")
    parser.add_argument(
        "--concurrency", type=int, default=20, help="Concurrent workers"
    )
    parser.add_argument(
        "--simulate-unique-ips",
        action="store_true",
        default=True,
        help="Simulate distinct client IPs via X-Forwarded-For",
    )
    parser.add_argument(
        "--no-simulate-unique-ips",
        action="store_false",
        dest="simulate_unique_ips",
        help="Do not simulate distinct client IPs",
    )
    parser.add_argument(
        "--url", type=str, default="http://127.0.0.1:8000", help="Base URL of app"
    )
    args = parser.parse_args()

    print(f"Starting URL Creation Load Test against {args.url}")
    print(
        f"Total Requests: {args.total}, Concurrency: {args.concurrency}, Simulate Unique IPs: {args.simulate_unique_ips}"
    )

    created_codes: list[str] = []
    validation_error_count = 0
    lock = asyncio.Lock()

    async def request_create_url(index: int, client: AsyncClient):
        nonlocal validation_error_count
        headers = {}
        if args.simulate_unique_ips:
            ip_suffix_1 = (index // 250) % 250
            ip_suffix_2 = (index % 250) + 1
            headers["X-Forwarded-For"] = f"10.1.{ip_suffix_1}.{ip_suffix_2}"

        payload = {"url": f"https://example.com/load-bench-page-{index}"}
        start = time.perf_counter()
        resp = await client.post("/api/v1/urls", json=payload, headers=headers)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if resp.status_code == 201:
            data = resp.json()
            code = data.get("short_code")
            if code:
                async with lock:
                    created_codes.append(code)
            return 201, elapsed_ms
        elif resp.status_code == 422:
            async with lock:
                validation_error_count += 1
            return 422, elapsed_ms
        else:
            return resp.status_code, elapsed_ms

    result = await run_worker_pool(
        total_requests=args.total,
        concurrency=args.concurrency,
        request_func=request_create_url,
        base_url=args.url,
    )

    unique_codes = set(created_codes)
    duplicates = len(created_codes) - len(unique_codes)

    result.custom_data["successful_creations (201)"] = result.count_2xx
    result.custom_data["rate_limited_requests (429)"] = result.count_429
    result.custom_data["validation_errors (422)"] = validation_error_count
    result.custom_data["server_errors (5xx)"] = result.count_5xx
    result.custom_data["total_created_codes"] = len(created_codes)
    result.custom_data["unique_short_codes"] = len(unique_codes)
    result.custom_data["duplicate_short_codes"] = duplicates
    result.custom_data["uniqueness_check"] = (
        "PASSED (All codes unique)"
        if duplicates == 0
        else f"FAILED ({duplicates} collisions)"
    )

    print_summary_table("URL Creation Performance (POST /api/v1/urls)", result)


if __name__ == "__main__":
    asyncio.run(main())
