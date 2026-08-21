import argparse
import asyncio
import time

from httpx import AsyncClient

from load_tests.common import create_async_client, print_summary_table, run_worker_pool


async def main():
    parser = argparse.ArgumentParser(description="Redirect Endpoint Load Test")
    parser.add_argument(
        "--total", type=int, default=1000, help="Total requests to make"
    )
    parser.add_argument(
        "--concurrency", type=int, default=50, help="Concurrent workers"
    )
    parser.add_argument(
        "--simulate-unique-ips",
        action="store_true",
        default=True,
        help="Simulate distinct client IPs via X-Forwarded-For so rate limiting evaluates distinct clients",
    )
    parser.add_argument(
        "--no-simulate-unique-ips",
        action="store_false",
        dest="simulate_unique_ips",
        help="Do not simulate distinct client IPs (all requests share 1 IP rate limit)",
    )
    parser.add_argument(
        "--url", type=str, default="http://127.0.0.1:8000", help="Base URL of app"
    )
    args = parser.parse_args()

    print(f"Starting Redirect Load Test against {args.url}")
    print(
        f"Total Requests: {args.total}, Concurrency: {args.concurrency}, Simulate Unique IPs: {args.simulate_unique_ips}"
    )

    # 1. Setup test URL via API
    target_url = "https://example.com/load-test-target"
    async with create_async_client(base_url=args.url) as client:
        create_resp = await client.post("/api/v1/urls", json={"url": target_url})
        if create_resp.status_code != 201:
            print(
                f"Failed to setup test URL: HTTP {create_resp.status_code} - {create_resp.text}"
            )
            return
        data = create_resp.json()
        short_code = data["short_code"]
        print(f"Created target short_code: '{short_code}' for '{target_url}'")

        # 2. Warm the Redis cache
        warm_resp = await client.get(f"/{short_code}", follow_redirects=False)
        if warm_resp.status_code != 307:
            print(
                f"Failed to warm cache: HTTP {warm_resp.status_code} - {warm_resp.text}"
            )
            return
        print("Redis cache warmed successfully.")

    # 3. Request function for workers
    async def request_redirect(index: int, client: AsyncClient):
        headers = {}
        if args.simulate_unique_ips:
            # Generate distinct IP per virtual client bucket (e.g. 10.0.x.y)
            ip_suffix_1 = (index // 250) % 250
            ip_suffix_2 = (index % 250) + 1
            headers["X-Forwarded-For"] = f"10.0.{ip_suffix_1}.{ip_suffix_2}"

        start = time.perf_counter()
        resp = await client.get(
            f"/{short_code}", follow_redirects=False, headers=headers
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if resp.status_code == 307 and resp.headers.get("location") == target_url:
            return 307, elapsed_ms
        else:
            return resp.status_code, elapsed_ms

    # 4. Run load test workers
    result = await run_worker_pool(
        total_requests=args.total,
        concurrency=args.concurrency,
        request_func=request_redirect,
        base_url=args.url,
    )

    result.custom_data["short_code"] = short_code
    result.custom_data["target_url"] = target_url
    result.custom_data["simulate_unique_ips"] = args.simulate_unique_ips
    result.custom_data["successful_redirects (307)"] = result.count_3xx
    result.custom_data["rate_limited_requests (429)"] = result.count_429
    result.custom_data["other_client_errors (4xx)"] = result.count_other_4xx
    result.custom_data["server_errors (5xx)"] = result.count_5xx

    print_summary_table("Redirect Performance (GET /{short_code})", result)


if __name__ == "__main__":
    asyncio.run(main())
