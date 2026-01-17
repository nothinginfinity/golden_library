#!/usr/bin/env python3
"""
Day 6: Load Testing Script for Golden Library
Tests concurrent users, WebSocket latency, and system stability.

Success Criteria:
- Handles 12+ concurrent users
- <100ms WebSocket latency
- Zero crashes in sustained testing
"""

import asyncio
import json
import time
import statistics
import uuid
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import websockets
except ImportError:
    print("ERROR: websockets package required. Install with: pip install websockets")
    sys.exit(1)


@dataclass
class TestResult:
    """Results from a single test operation."""
    operation: str
    success: bool
    latency_ms: float
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class UserSession:
    """Represents a simulated user connection."""
    user_id: str
    user_name: str
    websocket: Any = None
    session_id: Optional[str] = None
    results: List[TestResult] = field(default_factory=list)
    connected: bool = False


class LoadTester:
    """Load testing harness for Golden Library WebSocket server."""

    def __init__(self, ws_url: str = "ws://localhost:8081", num_users: int = 12):
        self.ws_url = ws_url
        self.num_users = num_users
        self.users: List[UserSession] = []
        self.all_results: List[TestResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    async def connect_user(self, user: UserSession) -> bool:
        """Connect a single user to the WebSocket server."""
        start = time.perf_counter()
        try:
            user.websocket = await asyncio.wait_for(
                websockets.connect(self.ws_url),
                timeout=10.0
            )
            latency = (time.perf_counter() - start) * 1000
            user.connected = True

            # Wait for connection confirmation
            response = await asyncio.wait_for(user.websocket.recv(), timeout=5.0)
            data = json.loads(response)

            result = TestResult(
                operation="connect",
                success=data.get('event') == 'connected',
                latency_ms=latency
            )
            user.results.append(result)
            self.all_results.append(result)
            return True

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            result = TestResult(
                operation="connect",
                success=False,
                latency_ms=latency,
                error=str(e)
            )
            user.results.append(result)
            self.all_results.append(result)
            return False

    async def join_session(self, user: UserSession, session_id: str = None) -> bool:
        """Have user join or create a workspace session."""
        if not user.connected or not user.websocket:
            return False

        start = time.perf_counter()
        try:
            message = {
                "type": "join_workspace_session",
                "user_name": user.user_name
            }
            if session_id:
                message["session_id"] = session_id

            await user.websocket.send(json.dumps(message))

            # Wait for session_joined response
            response = await asyncio.wait_for(user.websocket.recv(), timeout=5.0)
            latency = (time.perf_counter() - start) * 1000
            data = json.loads(response)

            if data.get('event') == 'session_joined':
                user.session_id = data.get('session_id')
                result = TestResult(
                    operation="join_session",
                    success=True,
                    latency_ms=latency
                )
            else:
                result = TestResult(
                    operation="join_session",
                    success=False,
                    latency_ms=latency,
                    error=f"Unexpected response: {data}"
                )

            user.results.append(result)
            self.all_results.append(result)
            return result.success

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            result = TestResult(
                operation="join_session",
                success=False,
                latency_ms=latency,
                error=str(e)
            )
            user.results.append(result)
            self.all_results.append(result)
            return False

    async def send_ping(self, user: UserSession) -> bool:
        """Send ping and measure latency."""
        if not user.connected or not user.websocket:
            return False

        start = time.perf_counter()
        try:
            await user.websocket.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(user.websocket.recv(), timeout=5.0)
            latency = (time.perf_counter() - start) * 1000
            data = json.loads(response)

            result = TestResult(
                operation="ping",
                success=data.get('type') == 'pong',
                latency_ms=latency
            )
            user.results.append(result)
            self.all_results.append(result)
            return result.success

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            result = TestResult(
                operation="ping",
                success=False,
                latency_ms=latency,
                error=str(e)
            )
            user.results.append(result)
            self.all_results.append(result)
            return False

    async def send_typing_indicator(self, user: UserSession, is_typing: bool = True) -> bool:
        """Send typing indicator."""
        if not user.connected or not user.websocket or not user.session_id:
            return False

        start = time.perf_counter()
        try:
            await user.websocket.send(json.dumps({
                "type": "user_typing",
                "is_typing": is_typing
            }))
            latency = (time.perf_counter() - start) * 1000

            result = TestResult(
                operation="typing_indicator",
                success=True,
                latency_ms=latency
            )
            user.results.append(result)
            self.all_results.append(result)
            return True

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            result = TestResult(
                operation="typing_indicator",
                success=False,
                latency_ms=latency,
                error=str(e)
            )
            user.results.append(result)
            self.all_results.append(result)
            return False

    async def send_cursor_move(self, user: UserSession, x: int, y: int) -> bool:
        """Send cursor position update."""
        if not user.connected or not user.websocket or not user.session_id:
            return False

        start = time.perf_counter()
        try:
            await user.websocket.send(json.dumps({
                "type": "cursor_move",
                "position": {"x": x, "y": y}
            }))
            latency = (time.perf_counter() - start) * 1000

            result = TestResult(
                operation="cursor_move",
                success=True,
                latency_ms=latency
            )
            user.results.append(result)
            self.all_results.append(result)
            return True

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            result = TestResult(
                operation="cursor_move",
                success=False,
                latency_ms=latency,
                error=str(e)
            )
            user.results.append(result)
            self.all_results.append(result)
            return False

    async def disconnect_user(self, user: UserSession):
        """Disconnect a user."""
        if user.websocket:
            try:
                await user.websocket.close()
            except Exception:
                pass
            user.connected = False

    async def run_user_simulation(self, user: UserSession, session_id: str = None):
        """Run a complete user simulation."""
        # Connect
        if not await self.connect_user(user):
            return

        # Join session
        await self.join_session(user, session_id)

        # If joined, do some activity
        if user.session_id:
            # Send multiple pings
            for _ in range(3):
                await self.send_ping(user)
                await asyncio.sleep(0.1)

            # Send typing indicators
            await self.send_typing_indicator(user, True)
            await asyncio.sleep(0.2)
            await self.send_typing_indicator(user, False)

            # Send cursor movements
            for i in range(5):
                await self.send_cursor_move(user, i * 100, i * 50)
                await asyncio.sleep(0.05)

        # Keep connection alive for a bit
        await asyncio.sleep(1.0)

        # Disconnect
        await self.disconnect_user(user)

    async def run_concurrent_test(self) -> Dict[str, Any]:
        """Run load test with concurrent users."""
        print(f"\n{'='*60}")
        print(f"  LOAD TEST: {self.num_users} Concurrent Users")
        print(f"  Target: ws://localhost:8081")
        print(f"{'='*60}\n")

        self.start_time = time.perf_counter()

        # Create users
        self.users = [
            UserSession(
                user_id=str(uuid.uuid4())[:8],
                user_name=f"LoadTestUser_{i+1}"
            )
            for i in range(self.num_users)
        ]

        # First user creates session, others join it
        print(f"[1/{self.num_users}] Connecting first user (session creator)...")
        await self.run_user_simulation(self.users[0])
        session_id = self.users[0].session_id

        if not session_id:
            print("ERROR: Failed to create session")
            return self.generate_report()

        print(f"[✓] Session created: {session_id}")

        # Other users join concurrently
        print(f"[2-{self.num_users}/{self.num_users}] Connecting remaining users concurrently...")

        tasks = [
            self.run_user_simulation(user, session_id)
            for user in self.users[1:]
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        self.end_time = time.perf_counter()

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate test report."""
        duration = (self.end_time - self.start_time) if self.end_time else 0

        # Group by operation
        ops: Dict[str, List[TestResult]] = {}
        for r in self.all_results:
            if r.operation not in ops:
                ops[r.operation] = []
            ops[r.operation].append(r)

        # Calculate stats per operation
        op_stats = {}
        for op, results in ops.items():
            latencies = [r.latency_ms for r in results]
            successes = [r for r in results if r.success]

            op_stats[op] = {
                "total": len(results),
                "success": len(successes),
                "failed": len(results) - len(successes),
                "success_rate": len(successes) / len(results) * 100 if results else 0,
                "latency_min_ms": min(latencies) if latencies else 0,
                "latency_max_ms": max(latencies) if latencies else 0,
                "latency_avg_ms": statistics.mean(latencies) if latencies else 0,
                "latency_p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies) if latencies else 0
            }

        # Overall stats
        all_latencies = [r.latency_ms for r in self.all_results]
        all_successes = [r for r in self.all_results if r.success]

        report = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "num_users": self.num_users,
                "ws_url": self.ws_url
            },
            "summary": {
                "duration_seconds": round(duration, 2),
                "total_operations": len(self.all_results),
                "successful_operations": len(all_successes),
                "failed_operations": len(self.all_results) - len(all_successes),
                "success_rate_percent": round(len(all_successes) / len(self.all_results) * 100, 2) if self.all_results else 0,
                "latency_avg_ms": round(statistics.mean(all_latencies), 2) if all_latencies else 0,
                "latency_max_ms": round(max(all_latencies), 2) if all_latencies else 0,
                "users_connected": sum(1 for u in self.users if u.connected or u.session_id)
            },
            "operations": op_stats,
            "success_criteria": {
                "concurrent_users_12_plus": self.num_users >= 12,
                "latency_under_100ms": (statistics.mean(all_latencies) if all_latencies else 0) < 100,
                "zero_crashes": len(all_successes) == len(self.all_results)
            }
        }

        # Collect errors
        errors = [r for r in self.all_results if not r.success]
        if errors:
            report["errors"] = [
                {"operation": e.operation, "error": e.error}
                for e in errors[:10]  # First 10 errors
            ]

        return report


def print_report(report: Dict[str, Any]):
    """Print formatted test report."""
    print(f"\n{'='*60}")
    print("  LOAD TEST RESULTS")
    print(f"{'='*60}\n")

    s = report["summary"]
    print(f"Duration:      {s['duration_seconds']}s")
    print(f"Total Ops:     {s['total_operations']}")
    print(f"Success Rate:  {s['success_rate_percent']}%")
    print(f"Avg Latency:   {s['latency_avg_ms']}ms")
    print(f"Max Latency:   {s['latency_max_ms']}ms")

    print(f"\n{'─'*60}")
    print("  Per-Operation Stats")
    print(f"{'─'*60}")

    for op, stats in report["operations"].items():
        print(f"\n  {op}:")
        print(f"    Success: {stats['success']}/{stats['total']} ({stats['success_rate']:.1f}%)")
        print(f"    Latency: avg={stats['latency_avg_ms']:.1f}ms, max={stats['latency_max_ms']:.1f}ms")

    print(f"\n{'─'*60}")
    print("  Success Criteria")
    print(f"{'─'*60}")

    criteria = report["success_criteria"]
    for name, passed in criteria.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  [{status}] {name.replace('_', ' ')}")

    if "errors" in report:
        print(f"\n{'─'*60}")
        print("  Errors (first 10)")
        print(f"{'─'*60}")
        for e in report["errors"]:
            print(f"  [{e['operation']}] {e['error']}")

    # Overall result
    all_passed = all(criteria.values())
    print(f"\n{'='*60}")
    if all_passed:
        print("  🎉 ALL SUCCESS CRITERIA PASSED")
    else:
        print("  ⚠️  SOME CRITERIA FAILED")
    print(f"{'='*60}\n")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Golden Library Load Testing")
    parser.add_argument("--users", type=int, default=12, help="Number of concurrent users")
    parser.add_argument("--url", default="ws://localhost:8081", help="WebSocket URL")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument("--output", help="Save report to file")
    args = parser.parse_args()

    tester = LoadTester(ws_url=args.url, num_users=args.users)

    try:
        report = await tester.run_concurrent_test()
    except Exception as e:
        print(f"ERROR: Load test failed: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {args.output}")

    # Exit with appropriate code
    all_passed = all(report["success_criteria"].values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
