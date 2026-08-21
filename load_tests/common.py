import asyncio
import statistics
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from httpx import AsyncClient, Limits


@dataclass
class LoadTestResult:
    duration_seconds: float = 0.0
    total_requests: int = 0
    count_2xx: int = 0
    count_3xx: int = 0
    count_429: int = 0
    count_other_4xx: int = 0
    count_5xx: int = 0
    other_error_count: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    custom_data: dict[str, Any] = field(default_factory=dict)

    @property
    def total_4xx(self) -> int:
        return self.count_429 + self.count_other_4xx

    @property
    def total_successful(self) -> int:
        return self.count_2xx + self.count_3xx

    @property
    def rps(self) -> float:
        return (
            self.total_requests / self.duration_seconds
            if self.duration_seconds > 0
            else 0.0
        )

    @property
    def avg_latency_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def min_latency_ms(self) -> float:
        return min(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def max_latency_ms(self) -> float:
        return max(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def p50_ms(self) -> float:
        return calculate_percentile(self.latencies_ms, 50)

    @property
    def p95_ms(self) -> float:
        return calculate_percentile(self.latencies_ms, 95)

    @property
    def p99_ms(self) -> float:
        return calculate_percentile(self.latencies_ms, 99)


def calculate_percentile(data: list[float], percentile: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = (len(sorted_data) - 1) * (percentile / 100.0)
    lower = int(index)
    upper = lower + 1
    weight = index - lower
    if upper >= len(sorted_data):
        return sorted_data[lower]
    return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


def create_async_client(
    base_url: str = "http://127.0.0.1:8000", max_connections: int = 100
) -> AsyncClient:
    return AsyncClient(
        base_url=base_url,
        limits=Limits(
            max_connections=max_connections, max_keepalive_connections=max_connections
        ),
        timeout=10.0,
    )


async def run_worker_pool(
    total_requests: int,
    concurrency: int,
    request_func: Callable[[int, AsyncClient], Coroutine[Any, Any, tuple[int, float]]],
    base_url: str = "http://127.0.0.1:8000",
) -> LoadTestResult:
    semaphore = asyncio.Semaphore(concurrency)
    result = LoadTestResult()

    async with create_async_client(
        base_url=base_url, max_connections=concurrency + 10
    ) as client:

        async def worker(request_index: int):
            async with semaphore:
                start = time.perf_counter()
                try:
                    status_code, elapsed_ms = await request_func(request_index, client)
                    if elapsed_ms == 0.0:
                        elapsed_ms = (time.perf_counter() - start) * 1000.0
                    return status_code, elapsed_ms
                except Exception:  # noqa: BLE001
                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    return 599, elapsed_ms

        start_time = time.perf_counter()
        tasks = [worker(i) for i in range(total_requests)]
        outputs = await asyncio.gather(*tasks)
        end_time = time.perf_counter()

    result.duration_seconds = end_time - start_time
    result.total_requests = len(outputs)

    for status_code, latency_ms in outputs:
        result.latencies_ms.append(latency_ms)
        if 200 <= status_code < 300:
            result.count_2xx += 1
        elif 300 <= status_code < 400:
            result.count_3xx += 1
        elif status_code == 429:
            result.count_429 += 1
        elif 400 <= status_code < 500:
            result.count_other_4xx += 1
        elif 500 <= status_code < 600:
            result.count_5xx += 1
        else:
            result.other_error_count += 1

    return result


def print_summary_table(title: str, result: LoadTestResult):
    print("=" * 60)
    print(f" LOAD TEST SUMMARY: {title}")
    print("=" * 60)
    print(f" Total Duration      : {result.duration_seconds:.2f} s")
    print(f" Total Requests      : {result.total_requests}")
    print(f" Throughput (RPS)    : {result.rps:.2f} req/sec")
    print("-" * 60)
    print(" STATUS CODE BREAKDOWN:")
    print(f"   2xx Successful    : {result.count_2xx}")
    print(f"   3xx Redirects     : {result.count_3xx}")
    print(f"   429 Rate Limited  : {result.count_429}")
    print(f"   Other 4xx Errors  : {result.count_other_4xx}")
    print(f"   5xx Server Errors : {result.count_5xx}")
    print("-" * 60)
    print(" LATENCY METRICS (ms):")
    print(f"   Average           : {result.avg_latency_ms:.2f} ms")
    print(
        f"   Min / Max         : {result.min_latency_ms:.2f} ms / {result.max_latency_ms:.2f} ms"
    )
    print(f"   p50 (Median)      : {result.p50_ms:.2f} ms")
    print(f"   p95               : {result.p95_ms:.2f} ms")
    print(f"   p99               : {result.p99_ms:.2f} ms")
    if result.custom_data:
        print("-" * 60)
        print(" TEST SPECIFIC METRICS & NOTES:")
        for k, v in result.custom_data.items():
            print(f"   {k}: {v}")
    print("=" * 60)
