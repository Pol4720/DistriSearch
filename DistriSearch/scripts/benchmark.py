#!/usr/bin/env python3
"""
DistriSearch Benchmark Script
Performance testing for search operations
"""

import asyncio
import argparse
import json
import random
import statistics
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import aiohttp

# Sample queries for benchmarking
SAMPLE_QUERIES = [
    "distributed systems scalability",
    "machine learning algorithms",
    "database normalization",
    "cloud computing services",
    "software testing practices",
    "API design REST GraphQL",
    "microservices architecture",
    "cybersecurity threats",
    "DevOps CI CD",
    "data structures algorithms",
    "containerization docker",
    "kubernetes orchestration",
    "neural networks deep learning",
    "SQL NoSQL databases",
    "encryption security",
    "load balancing scaling",
    "fault tolerance recovery",
    "caching strategies",
    "message queues events",
    "monitoring observability"
]


@dataclass
class BenchmarkResult:
    """Single benchmark result"""
    query: str
    latency_ms: float
    result_count: int
    success: bool
    error: Optional[str] = None


@dataclass
class BenchmarkSummary:
    """Benchmark summary statistics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time_seconds: float = 0.0
    latencies_ms: List[float] = field(default_factory=list)
    results_per_query: List[int] = field(default_factory=list)
    
    @property
    def avg_latency(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0
    
    @property
    def min_latency(self) -> float:
        return min(self.latencies_ms) if self.latencies_ms else 0.0
    
    @property
    def max_latency(self) -> float:
        return max(self.latencies_ms) if self.latencies_ms else 0.0
    
    @property
    def p50_latency(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        return sorted_latencies[len(sorted_latencies) // 2]
    
    @property
    def p95_latency(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    @property
    def p99_latency(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    @property
    def std_dev_latency(self) -> float:
        return statistics.stdev(self.latencies_ms) if len(self.latencies_ms) > 1 else 0.0
    
    @property
    def requests_per_second(self) -> float:
        return self.total_requests / self.total_time_seconds if self.total_time_seconds > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        return (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0.0


class Benchmarker:
    """DistriSearch benchmark runner"""
    
    def __init__(self, api_url: str, concurrency: int = 10, timeout: int = 30):
        self.api_url = api_url.rstrip('/')
        self.concurrency = concurrency
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self.concurrency * 2)
        self.session = aiohttp.ClientSession(connector=connector)
        self.semaphore = asyncio.Semaphore(self.concurrency)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_health(self) -> bool:
        """Check if API is available"""
        try:
            async with self.session.get(
                f"{self.api_url}/api/v1/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
        except Exception:
            return False
    
    async def search(self, query: str, limit: int = 10) -> BenchmarkResult:
        """Execute a single search query"""
        async with self.semaphore:
            start_time = time.perf_counter()
            
            try:
                async with self.session.post(
                    f"{self.api_url}/api/v1/search",
                    json={"query": query, "limit": limit},
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    end_time = time.perf_counter()
                    latency_ms = (end_time - start_time) * 1000
                    
                    if response.status == 200:
                        data = await response.json()
                        result_count = len(data.get("results", []))
                        return BenchmarkResult(
                            query=query,
                            latency_ms=latency_ms,
                            result_count=result_count,
                            success=True
                        )
                    else:
                        error = await response.text()
                        return BenchmarkResult(
                            query=query,
                            latency_ms=latency_ms,
                            result_count=0,
                            success=False,
                            error=f"HTTP {response.status}: {error[:100]}"
                        )
            except asyncio.TimeoutError:
                return BenchmarkResult(
                    query=query,
                    latency_ms=self.timeout * 1000,
                    result_count=0,
                    success=False,
                    error="Timeout"
                )
            except Exception as e:
                return BenchmarkResult(
                    query=query,
                    latency_ms=0,
                    result_count=0,
                    success=False,
                    error=str(e)
                )
    
    async def run_benchmark(
        self,
        queries: List[str],
        iterations: int = 1,
        progress_callback=None
    ) -> BenchmarkSummary:
        """Run benchmark with given queries"""
        summary = BenchmarkSummary()
        all_queries = queries * iterations
        total = len(all_queries)
        
        start_time = time.perf_counter()
        
        # Create tasks for all queries
        tasks = [self.search(q) for q in all_queries]
        
        # Run with progress tracking
        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1
            
            summary.total_requests += 1
            if result.success:
                summary.successful_requests += 1
                summary.latencies_ms.append(result.latency_ms)
                summary.results_per_query.append(result.result_count)
            else:
                summary.failed_requests += 1
            
            if progress_callback:
                progress_callback(completed, total, result)
        
        end_time = time.perf_counter()
        summary.total_time_seconds = end_time - start_time
        
        return summary
    
    async def run_load_test(
        self,
        queries: List[str],
        duration_seconds: int = 60,
        progress_callback=None
    ) -> BenchmarkSummary:
        """Run load test for a specified duration"""
        summary = BenchmarkSummary()
        start_time = time.perf_counter()
        end_time = start_time + duration_seconds
        
        completed = 0
        
        while time.perf_counter() < end_time:
            # Generate batch of queries
            batch_queries = [random.choice(queries) for _ in range(self.concurrency)]
            tasks = [self.search(q) for q in batch_queries]
            
            results = await asyncio.gather(*tasks)
            
            for result in results:
                completed += 1
                summary.total_requests += 1
                
                if result.success:
                    summary.successful_requests += 1
                    summary.latencies_ms.append(result.latency_ms)
                    summary.results_per_query.append(result.result_count)
                else:
                    summary.failed_requests += 1
                
                if progress_callback:
                    elapsed = time.perf_counter() - start_time
                    progress_callback(elapsed, duration_seconds, result)
        
        summary.total_time_seconds = time.perf_counter() - start_time
        
        return summary


def print_progress(completed: int, total: int, result: BenchmarkResult):
    """Print progress during benchmark"""
    status = "✓" if result.success else "✗"
    print(f"\r[{completed}/{total}] {status} {result.latency_ms:.1f}ms - {result.query[:30]}...", end="", flush=True)


def print_load_progress(elapsed: float, duration: float, result: BenchmarkResult):
    """Print progress during load test"""
    status = "✓" if result.success else "✗"
    remaining = max(0, duration - elapsed)
    print(f"\r[{elapsed:.1f}s/{duration}s] {status} {result.latency_ms:.1f}ms (remaining: {remaining:.1f}s)", end="", flush=True)


def print_summary(summary: BenchmarkSummary, title: str = "Benchmark Results"):
    """Print benchmark summary"""
    print(f"\n\n{'=' * 60}")
    print(f" {title}")
    print(f"{'=' * 60}")
    
    print(f"\n📊 Overview:")
    print(f"   Total Requests:      {summary.total_requests}")
    print(f"   Successful:          {summary.successful_requests}")
    print(f"   Failed:              {summary.failed_requests}")
    print(f"   Success Rate:        {summary.success_rate:.1f}%")
    print(f"   Total Time:          {summary.total_time_seconds:.2f}s")
    print(f"   Requests/Second:     {summary.requests_per_second:.2f}")
    
    print(f"\n⏱️  Latency (ms):")
    print(f"   Min:                 {summary.min_latency:.2f}")
    print(f"   Max:                 {summary.max_latency:.2f}")
    print(f"   Average:             {summary.avg_latency:.2f}")
    print(f"   Std Dev:             {summary.std_dev_latency:.2f}")
    print(f"   P50 (Median):        {summary.p50_latency:.2f}")
    print(f"   P95:                 {summary.p95_latency:.2f}")
    print(f"   P99:                 {summary.p99_latency:.2f}")
    
    if summary.results_per_query:
        avg_results = statistics.mean(summary.results_per_query)
        print(f"\n📄 Results per Query:")
        print(f"   Average:             {avg_results:.1f}")
    
    print(f"{'=' * 60}\n")


def save_results(summary: BenchmarkSummary, filename: str):
    """Save benchmark results to JSON file"""
    data = {
        "total_requests": summary.total_requests,
        "successful_requests": summary.successful_requests,
        "failed_requests": summary.failed_requests,
        "success_rate_percent": summary.success_rate,
        "total_time_seconds": summary.total_time_seconds,
        "requests_per_second": summary.requests_per_second,
        "latency_ms": {
            "min": summary.min_latency,
            "max": summary.max_latency,
            "avg": summary.avg_latency,
            "std_dev": summary.std_dev_latency,
            "p50": summary.p50_latency,
            "p95": summary.p95_latency,
            "p99": summary.p99_latency,
        },
        "raw_latencies_ms": summary.latencies_ms,
        "results_per_query": summary.results_per_query
    }
    
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"Results saved to: {filename}")


async def main():
    parser = argparse.ArgumentParser(description="DistriSearch Benchmark")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API server URL")
    parser.add_argument("--concurrency", "-c", type=int, default=10, help="Concurrent requests")
    parser.add_argument("--iterations", "-i", type=int, default=1, help="Number of iterations per query")
    parser.add_argument("--duration", "-d", type=int, help="Load test duration in seconds")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--queries", "-q", help="File with custom queries (one per line)")
    parser.add_argument("--output", "-o", help="Output file for results (JSON)")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    
    args = parser.parse_args()
    
    # Load queries
    if args.queries:
        with open(args.queries, "r") as f:
            queries = [line.strip() for line in f if line.strip()]
    else:
        queries = SAMPLE_QUERIES
    
    print(f"DistriSearch Benchmark")
    print(f"{'=' * 40}")
    print(f"API URL:       {args.api_url}")
    print(f"Concurrency:   {args.concurrency}")
    print(f"Queries:       {len(queries)}")
    print(f"Iterations:    {args.iterations}")
    print(f"Timeout:       {args.timeout}s")
    if args.duration:
        print(f"Duration:      {args.duration}s")
    print(f"{'=' * 40}\n")
    
    async with Benchmarker(args.api_url, args.concurrency, args.timeout) as bench:
        # Check API health
        print("Checking API availability...")
        if not await bench.check_health():
            print(f"Error: API at {args.api_url} is not available")
            return
        
        print("API is available. Starting benchmark...\n")
        
        progress = None if args.quiet else print_progress
        load_progress = None if args.quiet else print_load_progress
        
        if args.duration:
            # Load test mode
            summary = await bench.run_load_test(
                queries,
                args.duration,
                progress_callback=load_progress
            )
            title = f"Load Test Results ({args.duration}s)"
        else:
            # Standard benchmark mode
            summary = await bench.run_benchmark(
                queries,
                args.iterations,
                progress_callback=progress
            )
            title = "Benchmark Results"
        
        print_summary(summary, title)
        
        if args.output:
            save_results(summary, args.output)


if __name__ == "__main__":
    asyncio.run(main())
