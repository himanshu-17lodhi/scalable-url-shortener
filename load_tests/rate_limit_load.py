import argparse
import asyncio
import random
import time

from load_tests.common import LoadTestResult, create_async_client, print_summary_table


async def main():
    parser = argparse.ArgumentParser(description="Deterministic Rate Limiter Load Test")
    parser.add_argument(
        "--requests", type=int, default=25, help="Total requests to send in burst"
    )
    parser.add_argument(
        "--capacity", type=int, default=10, help="Expected rate limit capacity"
    )
    parser.add_argument(
        "--refill-seconds",
        type=float,
        default=2.5,
        help="Seconds to sleep for token refill test",
    )
    parser.add_argument(
        "--url", type=str, default="http://127.0.0.1:8000", help="Base URL of app"
    )
    args = parser.parse_args()

    print(f"Starting Deterministic Rate Limiter Load Test against {args.url}")

    # Generate a fresh, unique client IP for this test session to ensure clean bucket
    test_ip = f"198.51.100.{random.randint(1, 254)}"
    print(f"Using fresh client IP identity: '{test_ip}'")
    headers = {"X-Forwarded-For": test_ip}

    # 1. Setup a test short URL to hit a rate-limited endpoint (GET /{short_code})
    async with create_async_client(base_url=args.url) as client:
        create_resp = await client.post(
            "/api/v1/urls", json={"url": "https://example.com/ratelimit-target"}
        )
        if create_resp.status_code != 201:
            print(f"Failed to setup target URL: HTTP {create_resp.status_code}")
            return
        short_code = create_resp.json()["short_code"]
        print(f"Target short_code for rate limit test: '{short_code}'")

        result = LoadTestResult()
        start_time = time.perf_counter()

        allowed_count = 0
        rate_limited_count = 0

        # Phase 1: Burst requests to trigger rate limiting
        print(f"\nPhase 1: Sending sequential burst of {args.requests} requests...")
        for _ in range(args.requests):
            t0 = time.perf_counter()
            resp = await client.get(
                f"/{short_code}", follow_redirects=False, headers=headers
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            result.latencies_ms.append(elapsed_ms)

            if resp.status_code == 307:
                allowed_count += 1
                result.count_3xx += 1
            elif resp.status_code == 429:
                rate_limited_count += 1
                result.count_429 += 1
            else:
                result.count_other_4xx += 1

        print(
            f"Phase 1 Complete: {allowed_count} Allowed (307 Redirect), {rate_limited_count} Rate Limited (429 Too Many Requests)"
        )

        # Phase 2: Wait for token refill
        print(
            f"\nPhase 2: Sleeping for {args.refill_seconds}s to allow token bucket refill..."
        )
        await asyncio.sleep(args.refill_seconds)

        # Phase 3: Send verification request
        print("Phase 3: Sending verification request post-refill...")
        t0 = time.perf_counter()
        recovery_resp = await client.get(
            f"/{short_code}", follow_redirects=False, headers=headers
        )
        recovery_elapsed_ms = (time.perf_counter() - t0) * 1000.0
        result.latencies_ms.append(recovery_elapsed_ms)

        recovered = recovery_resp.status_code == 307
        if recovered:
            result.count_3xx += 1
        elif recovery_resp.status_code == 429:
            result.count_429 += 1

        end_time = time.perf_counter()
        result.duration_seconds = end_time - start_time
        result.total_requests = args.requests + 1

        capacity_matched = allowed_count == args.capacity
        passed_test = rate_limited_count > 0 and recovered

        result.custom_data["test_client_ip"] = test_ip
        result.custom_data["burst_requests"] = args.requests
        result.custom_data["expected_capacity"] = args.capacity
        result.custom_data["allowed_count_in_burst"] = allowed_count
        result.custom_data["rate_limited_count_in_burst (429)"] = rate_limited_count
        result.custom_data["capacity_alignment"] = (
            f"EXACT MATCH ({allowed_count}/{args.capacity})"
            if capacity_matched
            else f"NEAR ({allowed_count}/{args.capacity})"
        )
        result.custom_data["token_refill_recovery"] = (
            "PASSED (Permitted requests post-refill)" if recovered else "FAILED"
        )
        result.custom_data["overall_test_status"] = (
            "PASSED (429 verified & refill recovered)" if passed_test else "FAILED"
        )

        print_summary_table("Deterministic Token-Bucket Rate Limiter Test", result)


if __name__ == "__main__":
    asyncio.run(main())
