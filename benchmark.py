#!/usr/bin/env python3
"""
Day 6: Performance Benchmarks for Golden Library
Measures WebSocket latency, DB queries, and API response times.

Success Criteria:
- <100ms WebSocket latency
- Fast DB queries
- Consistent API responses
"""

import asyncio
import json
import time
import statistics
import sys
import os
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import websockets
except ImportError:
    print("ERROR: websockets package required")
    sys.exit(1)

try:
    import aiohttp
except ImportError:
    aiohttp = None


@dataclass
class BenchmarkResult:
    """Single benchmark measurement."""
    name: str
    latency_ms: float
    success: bool
    details: Optional[str] = None


class PerformanceBenchmark:
    """Performance benchmarking suite."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.ws_url = "ws://localhost:8081"
        self.http_url = "http://localhost:8080"

    async def benchmark_websocket_latency(self, iterations: int = 50) -> Dict[str, Any]:
        """Measure WebSocket ping/pong latency."""
        print("\n[1/4] WebSocket Latency Benchmark")
        print("─" * 40)

        latencies = []
        errors = 0

        try:
            ws = await asyncio.wait_for(
                websockets.connect(self.ws_url),
                timeout=10.0
            )

            # Wait for connection confirmation
            await ws.recv()

            # Run ping iterations
            for i in range(iterations):
                start = time.perf_counter()
                try:
                    await ws.send(json.dumps({"type": "ping"}))
                    response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    latency = (time.perf_counter() - start) * 1000
                    data = json.loads(response)

                    if data.get('type') == 'pong':
                        latencies.append(latency)
                        self.results.append(BenchmarkResult(
                            name="ws_ping",
                            latency_ms=latency,
                            success=True
                        ))
                    else:
                        errors += 1
                except Exception as e:
                    errors += 1

            await ws.close()

        except Exception as e:
            print(f"  ERROR: {e}")
            return {"error": str(e)}

        if latencies:
            stats = {
                "iterations": iterations,
                "successful": len(latencies),
                "errors": errors,
                "min_ms": round(min(latencies), 2),
                "max_ms": round(max(latencies), 2),
                "avg_ms": round(statistics.mean(latencies), 2),
                "median_ms": round(statistics.median(latencies), 2),
                "p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2) if len(latencies) >= 20 else round(max(latencies), 2),
                "p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 2) if len(latencies) >= 100 else round(max(latencies), 2),
                "pass": statistics.mean(latencies) < 100
            }
            print(f"  Iterations: {stats['iterations']}")
            print(f"  Avg: {stats['avg_ms']}ms | P95: {stats['p95_ms']}ms | Max: {stats['max_ms']}ms")
            print(f"  Result: {'✓ PASS' if stats['pass'] else '✗ FAIL'} (target <100ms)")
            return stats
        else:
            return {"error": "No successful pings", "pass": False}

    def benchmark_db_queries(self) -> Dict[str, Any]:
        """Benchmark database query performance."""
        print("\n[2/4] Database Query Benchmark")
        print("─" * 40)

        # Find the conversation database
        db_paths = [
            Path.home() / ".golden_library" / "conversations.db",
            Path.home() / "ztgi" / "golden_library" / ".golden_library" / "conversations.db",
            Path("conversations.db"),
            Path(".golden_library") / "conversations.db"
        ]

        db_path = None
        for p in db_paths:
            if p.exists():
                db_path = p
                break

        if not db_path:
            print("  SKIP: No database found")
            return {"skip": True, "reason": "No database found"}

        print(f"  Database: {db_path}")

        results = {}

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Benchmark: Count all messages
            start = time.perf_counter()
            cursor.execute("SELECT COUNT(*) FROM messages")
            count = cursor.fetchone()[0]
            latency = (time.perf_counter() - start) * 1000
            results["count_messages"] = {
                "latency_ms": round(latency, 2),
                "result": count
            }
            print(f"  COUNT(*): {latency:.2f}ms ({count} messages)")
            self.results.append(BenchmarkResult("db_count", latency, True))

            # Benchmark: Recent messages query
            start = time.perf_counter()
            cursor.execute("""
                SELECT id, content, timestamp FROM messages
                ORDER BY timestamp DESC LIMIT 100
            """)
            rows = cursor.fetchall()
            latency = (time.perf_counter() - start) * 1000
            results["recent_100"] = {
                "latency_ms": round(latency, 2),
                "result": len(rows)
            }
            print(f"  Recent 100: {latency:.2f}ms")
            self.results.append(BenchmarkResult("db_recent", latency, True))

            # Benchmark: Search (if FTS available)
            start = time.perf_counter()
            try:
                cursor.execute("""
                    SELECT id, content FROM messages
                    WHERE content LIKE '%test%' LIMIT 50
                """)
                rows = cursor.fetchall()
                latency = (time.perf_counter() - start) * 1000
                results["search_like"] = {
                    "latency_ms": round(latency, 2),
                    "result": len(rows)
                }
                print(f"  LIKE search: {latency:.2f}ms ({len(rows)} results)")
                self.results.append(BenchmarkResult("db_search", latency, True))
            except Exception as e:
                print(f"  LIKE search: SKIP ({e})")

            conn.close()

            # Calculate overall DB benchmark
            db_latencies = [r["latency_ms"] for r in results.values() if "latency_ms" in r]
            results["summary"] = {
                "avg_ms": round(statistics.mean(db_latencies), 2) if db_latencies else 0,
                "max_ms": round(max(db_latencies), 2) if db_latencies else 0,
                "pass": all(l < 100 for l in db_latencies)
            }
            print(f"  Result: {'✓ PASS' if results['summary']['pass'] else '✗ FAIL'} (all <100ms)")

        except Exception as e:
            print(f"  ERROR: {e}")
            results["error"] = str(e)
            results["pass"] = False

        return results

    async def benchmark_http_api(self, iterations: int = 20) -> Dict[str, Any]:
        """Benchmark HTTP API endpoints."""
        print("\n[3/4] HTTP API Benchmark")
        print("─" * 40)

        if not aiohttp:
            print("  SKIP: aiohttp not installed")
            return {"skip": True, "reason": "aiohttp not installed"}

        endpoints = [
            ("/api/stats", "GET"),
            ("/api/config/list", "GET"),
            ("/api/daemons/list", "GET"),
        ]

        results = {}

        try:
            async with aiohttp.ClientSession() as session:
                for endpoint, method in endpoints:
                    url = f"{self.http_url}{endpoint}"
                    latencies = []

                    for _ in range(iterations):
                        start = time.perf_counter()
                        try:
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                                await resp.text()
                                latency = (time.perf_counter() - start) * 1000
                                if resp.status == 200:
                                    latencies.append(latency)
                        except Exception:
                            pass

                    if latencies:
                        results[endpoint] = {
                            "avg_ms": round(statistics.mean(latencies), 2),
                            "max_ms": round(max(latencies), 2),
                            "success_rate": len(latencies) / iterations * 100
                        }
                        print(f"  {endpoint}: avg={results[endpoint]['avg_ms']}ms")
                        self.results.append(BenchmarkResult(
                            f"http_{endpoint}",
                            statistics.mean(latencies),
                            True
                        ))
                    else:
                        results[endpoint] = {"error": "All requests failed"}

        except Exception as e:
            print(f"  ERROR: {e}")
            return {"error": str(e)}

        # Summary
        all_avgs = [r["avg_ms"] for r in results.values() if "avg_ms" in r]
        if all_avgs:
            results["summary"] = {
                "avg_ms": round(statistics.mean(all_avgs), 2),
                "pass": all(a < 200 for a in all_avgs)  # 200ms for HTTP
            }
            print(f"  Result: {'✓ PASS' if results['summary']['pass'] else '✗ FAIL'}")

        return results

    async def benchmark_session_operations(self) -> Dict[str, Any]:
        """Benchmark workspace session operations."""
        print("\n[4/4] Session Operations Benchmark")
        print("─" * 40)

        results = {}

        try:
            # Create session
            start = time.perf_counter()
            ws = await asyncio.wait_for(
                websockets.connect(self.ws_url),
                timeout=10.0
            )
            await ws.recv()  # connection confirmation

            await ws.send(json.dumps({
                "type": "join_workspace_session",
                "user_name": "BenchmarkUser"
            }))
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            latency = (time.perf_counter() - start) * 1000
            data = json.loads(response)

            if data.get('event') == 'session_joined':
                results["create_session"] = {
                    "latency_ms": round(latency, 2),
                    "session_id": data.get('session_id')
                }
                print(f"  Create session: {latency:.2f}ms")
                self.results.append(BenchmarkResult("session_create", latency, True))

                session_id = data.get('session_id')

                # Benchmark message broadcast (simulated)
                latencies = []
                for i in range(10):
                    start = time.perf_counter()
                    await ws.send(json.dumps({
                        "type": "user_typing",
                        "is_typing": i % 2 == 0
                    }))
                    latency = (time.perf_counter() - start) * 1000
                    latencies.append(latency)

                results["broadcast"] = {
                    "avg_ms": round(statistics.mean(latencies), 2),
                    "max_ms": round(max(latencies), 2)
                }
                print(f"  Broadcast avg: {results['broadcast']['avg_ms']:.2f}ms")

            await ws.close()

            results["pass"] = results.get("create_session", {}).get("latency_ms", 1000) < 500

        except Exception as e:
            print(f"  ERROR: {e}")
            results["error"] = str(e)
            results["pass"] = False

        print(f"  Result: {'✓ PASS' if results.get('pass') else '✗ FAIL'}")
        return results

    async def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmarks and generate report."""
        start_time = time.perf_counter()

        report = {
            "timestamp": datetime.now().isoformat(),
            "benchmarks": {}
        }

        # Run benchmarks
        report["benchmarks"]["websocket_latency"] = await self.benchmark_websocket_latency()
        report["benchmarks"]["database_queries"] = self.benchmark_db_queries()
        report["benchmarks"]["http_api"] = await self.benchmark_http_api()
        report["benchmarks"]["session_operations"] = await self.benchmark_session_operations()

        duration = time.perf_counter() - start_time

        # Generate summary
        all_pass = all(
            b.get("pass", b.get("summary", {}).get("pass", True))
            for b in report["benchmarks"].values()
            if not b.get("skip")
        )

        report["summary"] = {
            "duration_seconds": round(duration, 2),
            "total_measurements": len(self.results),
            "all_pass": all_pass,
            "success_criteria": {
                "websocket_latency_under_100ms": report["benchmarks"]["websocket_latency"].get("pass", False),
                "db_queries_fast": report["benchmarks"]["database_queries"].get("summary", {}).get("pass", True),
                "session_ops_responsive": report["benchmarks"]["session_operations"].get("pass", False)
            }
        }

        return report


def print_summary(report: Dict[str, Any]):
    """Print benchmark summary."""
    print("\n" + "=" * 60)
    print("  BENCHMARK SUMMARY")
    print("=" * 60)

    s = report["summary"]
    print(f"\nDuration: {s['duration_seconds']}s")
    print(f"Measurements: {s['total_measurements']}")

    print("\nSuccess Criteria:")
    for name, passed in s["success_criteria"].items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  [{status}] {name.replace('_', ' ')}")

    print("\n" + "=" * 60)
    if s["all_pass"]:
        print("  🎉 ALL BENCHMARKS PASSED")
    else:
        print("  ⚠️  SOME BENCHMARKS FAILED")
    print("=" * 60 + "\n")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Golden Library Performance Benchmarks")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument("--output", help="Save report to file")
    args = parser.parse_args()

    benchmark = PerformanceBenchmark()

    try:
        report = await benchmark.run_all_benchmarks()
    except Exception as e:
        print(f"ERROR: Benchmark failed: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_summary(report)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {args.output}")

    sys.exit(0 if report["summary"]["all_pass"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
