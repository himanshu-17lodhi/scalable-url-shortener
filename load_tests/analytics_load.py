import argparse
import asyncio
import time

from httpx import AsyncClient

from load_tests.common import create_async_client, print_summary_table, run_worker_pool


async def main():
    parser = argparse.ArgumentParser(description="Analytics Load & Consistency Test")
    parser.add_argument(
        "--clicks", type=int, default=50, help="Number of click redirect requests"
    )
    parser.add_argument(
        "--concurrency", type=int, default=10, help="Concurrent workers"
    )
    parser.add_argument(
        "--drain-sleep",
        type=float,
        default=1.5,
        help="Seconds to sleep for BackgroundTasks queue drain",
    )
    parser.add_argument(
        "--url", type=str, default="http://127.0.0.1:8000", help="Base URL of app"
    )
    args = parser.parse_args()

    print(f"Starting Analytics Load Test against {args.url}")
    print(
        f"Target Clicks: {args.clicks}, Concurrency: {args.concurrency}, Drain Wait: {args.drain_sleep}s"
    )

    # 1. Create a dedicated target short URL
    target_url = "https://example.com/analytics-load-test"
    async with create_async_client(base_url=args.url) as client:
        create_resp = await client.post("/api/v1/urls", json={"url": target_url})
        if create_resp.status_code != 201:
            print(
                f"Failed to create target URL: HTTP {create_resp.status_code} - {create_resp.text}"
            )
            return
        short_code = create_resp.json()["short_code"]
        print(f"Created target short_code '{short_code}'")

    # 2. Worker request function to generate clicks (simulate distinct IPs so rate limiter permits burst)
    async def request_click(index: int, client: AsyncClient):
        headers = {
            "X-Forwarded-For": f"10.2.{(index // 250) % 250}.{(index % 250) + 1}"
        }
        start = time.perf_counter()
        resp = await client.get(
            f"/{short_code}", follow_redirects=False, headers=headers
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return resp.status_code, elapsed_ms

    # 3. Execute click burst
    print(f"Executing burst of {args.clicks} redirect requests...")
    result = await run_worker_pool(
        total_requests=args.clicks,
        concurrency=args.concurrency,
        request_func=request_click,
        base_url=args.url,
    )

    # 4. Sleep to allow in-process FastAPI BackgroundTasks queue to finish database writes
    print(
        f"Waiting {args.drain_sleep}s for in-process BackgroundTasks queue to complete DB writes..."
    )
    await asyncio.sleep(args.drain_sleep)

    # 5. Query analytics endpoint
    print("Querying GET /api/v1/urls/{short_code}/analytics...")
    async with create_async_client(base_url=args.url) as client:
        analytics_resp = await client.get(f"/api/v1/urls/{short_code}/analytics")
        if analytics_resp.status_code != 200:
            print(
                f"Failed to fetch analytics: HTTP {analytics_resp.status_code} - {analytics_resp.text}"
            )
            recorded_clicks = -1
        else:
            analytics_data = analytics_resp.json()
            recorded_clicks = analytics_data.get("total_clicks", 0)

    expected_clicks = result.count_3xx
    match = recorded_clicks == expected_clicks

    result.custom_data["short_code"] = short_code
    result.custom_data["redirects_attempted"] = args.clicks
    result.custom_data["successful_redirects (307)"] = expected_clicks
    result.custom_data["analytics_recorded_clicks"] = recorded_clicks
    result.custom_data["click_count_consistency"] = (
        f"PASSED (Exact match: {recorded_clicks}/{expected_clicks})"
        if match
        else f"MISMATCH (Recorded {recorded_clicks}, expected {expected_clicks})"
    )
    result.custom_data["what_this_test_proves"] = (
        "Proves that FastAPI BackgroundTasks completed successfully in this controlled test run."
    )
    result.custom_data["background_task_limitations"] = (
        "FastAPI BackgroundTasks execute in-process out-of-band. They do NOT guarantee durable delivery under "
        "process crashes, application restarts, or worker termination (SIGKILL). A durable queue (e.g. RabbitMQ/Celery) "
        "is required for zero-loss delivery guarantees."
    )

    print_summary_table("Analytics Consistency & Background Task Test", result)


if __name__ == "__main__":
    asyncio.run(main())
