#!/usr/bin/env python3
"""
Investor Demo Scenario Test

Tests the complete demo flow that an investor would experience:
1. Join session quickly (<30s)
2. See AI agents collaborate
3. Work on a real problem
4. Get a tangible deliverable

Run: python3 demo_scenario_test.py
"""

import asyncio
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

# Add src to path
sys.path.insert(0, 'src')

from demo_templates import list_templates, get_template, TemplateRegistry
# Import all templates to register them
from demo_templates import food_services, software_security, legal, real_estate, construction


@dataclass
class TestResult:
    step: str
    passed: bool
    duration_ms: float
    details: str = ""
    error: Optional[str] = None


@dataclass
class DemoTestReport:
    template_id: str
    template_name: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    total_duration_s: float = 0
    results: List[TestResult] = field(default_factory=list)
    friction_points: List[str] = field(default_factory=list)
    passed: bool = True


class DemoScenarioTester:
    """Tests complete investor demo scenarios."""

    def __init__(self, ws_url="ws://localhost:8081", http_url="http://localhost:8080"):
        self.ws_url = ws_url
        self.http_url = http_url
        self.ws = None
        self.session_id = None
        self.user_id = None

    async def connect(self) -> TestResult:
        """Step 1: Connect to WebSocket."""
        start = time.perf_counter()
        try:
            self.ws = await asyncio.wait_for(
                websockets.connect(self.ws_url),
                timeout=10.0
            )
            response = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
            data = json.loads(response)
            duration = (time.perf_counter() - start) * 1000

            if data.get('event') == 'connected':
                return TestResult(
                    step="1. WebSocket Connect",
                    passed=True,
                    duration_ms=duration,
                    details="Connected successfully"
                )
            else:
                return TestResult(
                    step="1. WebSocket Connect",
                    passed=False,
                    duration_ms=duration,
                    error=f"Unexpected response: {data}"
                )
        except Exception as e:
            return TestResult(
                step="1. WebSocket Connect",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error=str(e)
            )

    async def join_session(self, investor_name: str) -> TestResult:
        """Step 2: Join/create a workspace session."""
        start = time.perf_counter()
        try:
            await self.ws.send(json.dumps({
                "type": "join_workspace_session",
                "user_name": investor_name
            }))

            response = await asyncio.wait_for(self.ws.recv(), timeout=10.0)
            data = json.loads(response)
            duration = (time.perf_counter() - start) * 1000

            if data.get('event') == 'session_joined':
                self.session_id = data.get('session_id')
                self.user_id = data.get('user_id')

                # Check if under 30 seconds (requirement)
                passed = duration < 30000

                return TestResult(
                    step="2. Join Session",
                    passed=passed,
                    duration_ms=duration,
                    details=f"Session: {self.session_id}" + (
                        "" if passed else " [FRICTION: Took >30s]"
                    )
                )
            else:
                return TestResult(
                    step="2. Join Session",
                    passed=False,
                    duration_ms=duration,
                    error=f"Failed: {data}"
                )
        except Exception as e:
            return TestResult(
                step="2. Join Session",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error=str(e)
            )

    async def test_ping_latency(self, count: int = 5) -> TestResult:
        """Step 3: Test real-time responsiveness."""
        start = time.perf_counter()
        latencies = []

        try:
            for _ in range(count):
                ping_start = time.perf_counter()
                await self.ws.send(json.dumps({"type": "ping"}))
                response = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
                latency = (time.perf_counter() - ping_start) * 1000
                latencies.append(latency)

            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            duration = (time.perf_counter() - start) * 1000

            # Requirement: <100ms latency
            passed = avg_latency < 100

            return TestResult(
                step="3. Real-time Latency",
                passed=passed,
                duration_ms=duration,
                details=f"Avg: {avg_latency:.1f}ms, Max: {max_latency:.1f}ms"
            )
        except Exception as e:
            return TestResult(
                step="3. Real-time Latency",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error=str(e)
            )

    async def test_agent_message(self, message: str) -> TestResult:
        """Step 4: Send a message and get agent response."""
        start = time.perf_counter()

        try:
            # Correct format: agent_id + message (not content)
            await self.ws.send(json.dumps({
                "type": "workspace_message",
                "agent_id": "prax",  # Start with Prax (orchestrator)
                "message": message
            }))

            # Wait for response (agent may take time to process with API call)
            responses = []
            deadline = time.perf_counter() + 30  # 30s timeout for API calls

            while time.perf_counter() < deadline:
                try:
                    response = await asyncio.wait_for(self.ws.recv(), timeout=2.0)
                    data = json.loads(response)
                    responses.append(data)

                    # Check for agent response or acknowledgment
                    if data.get('type') in ['agent_message', 'message_received', 'agent_response']:
                        break
                    if data.get('event') in ['message_broadcast', 'agent_thinking']:
                        continue
                except asyncio.TimeoutError:
                    break

            duration = (time.perf_counter() - start) * 1000

            if responses:
                return TestResult(
                    step="4. Agent Interaction",
                    passed=True,
                    duration_ms=duration,
                    details=f"Got {len(responses)} response(s)"
                )
            else:
                return TestResult(
                    step="4. Agent Interaction",
                    passed=False,
                    duration_ms=duration,
                    error="No response from agents"
                )
        except Exception as e:
            return TestResult(
                step="4. Agent Interaction",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error=str(e)
            )

    def test_template_content(self, template_id: str) -> TestResult:
        """Step 5: Verify template has required content."""
        start = time.perf_counter()

        template = get_template(template_id)
        if not template:
            return TestResult(
                step="5. Template Content",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error=f"Template '{template_id}' not found"
            )

        # Check required fields
        issues = []

        if not template.SECTOR_NAME:
            issues.append("Missing SECTOR_NAME")
        if not template.DESCRIPTION:
            issues.append("Missing DESCRIPTION")
        if not template.PAIN_POINTS:
            issues.append("Missing PAIN_POINTS")

        # Check methods exist and return content
        try:
            demo_steps = template.get_demo_steps()
            if not demo_steps:
                issues.append("No demo steps defined")
        except Exception as e:
            issues.append(f"get_demo_steps() failed: {e}")
            demo_steps = []

        try:
            sample_input = template.get_sample_input()
            if not sample_input:
                issues.append("No sample input defined")
        except Exception as e:
            issues.append(f"get_sample_input() failed: {e}")

        duration = (time.perf_counter() - start) * 1000

        if issues:
            return TestResult(
                step="5. Template Content",
                passed=False,
                duration_ms=duration,
                error="; ".join(issues)
            )

        return TestResult(
            step="5. Template Content",
            passed=True,
            duration_ms=duration,
            details=f"{len(template.PAIN_POINTS)} pain points, {len(demo_steps)} demo steps"
        )

    def test_deliverables(self, template_id: str) -> TestResult:
        """Step 6: Verify deliverables are defined."""
        start = time.perf_counter()

        template = get_template(template_id)
        if not template:
            return TestResult(
                step="6. Deliverables Check",
                passed=False,
                duration_ms=0,
                error="Template not found"
            )

        try:
            deliverable = template.get_deliverable()
            if not deliverable:
                return TestResult(
                    step="6. Deliverables Check",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error="No deliverable defined"
                )

            # Check deliverable has required fields
            issues = []
            if not deliverable.title:
                issues.append("Deliverable missing title")
            if not deliverable.format:
                issues.append("Deliverable missing format")
            if not deliverable.description:
                issues.append("Deliverable missing description")

            duration = (time.perf_counter() - start) * 1000

            if issues:
                return TestResult(
                    step="6. Deliverables Check",
                    passed=False,
                    duration_ms=duration,
                    error="; ".join(issues)
                )

            return TestResult(
                step="6. Deliverables Check",
                passed=True,
                duration_ms=duration,
                details=f"'{deliverable.title}' ({deliverable.format})"
            )
        except Exception as e:
            return TestResult(
                step="6. Deliverables Check",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error=str(e)
            )

    async def disconnect(self):
        """Clean up connection."""
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass

    def _print_result(self, result: TestResult):
        """Print a test result."""
        status = "✓" if result.passed else "✗"
        print(f"  [{status}] {result.step}: {result.duration_ms:.0f}ms")
        if result.details:
            print(f"      {result.details}")
        if result.error:
            print(f"      ERROR: {result.error}")

    async def run_scenario(self, template_id: str, investor_name: str = "Demo Investor") -> DemoTestReport:
        """Run complete demo scenario for a template."""

        template = get_template(template_id)
        report = DemoTestReport(
            template_id=template_id,
            template_name=template.SECTOR_NAME if template else "Unknown"
        )

        start_time = time.perf_counter()

        print(f"\n{'='*60}")
        print(f"  DEMO SCENARIO: {report.template_name}")
        print(f"{'='*60}\n")

        # Run test steps
        # Async steps
        result = await self.connect()
        report.results.append(result)
        self._print_result(result)
        if not result.passed:
            report.passed = False

        result = await self.join_session(investor_name)
        report.results.append(result)
        self._print_result(result)
        if not result.passed:
            report.passed = False
            report.friction_points.append(f"{result.step}: {result.error}")

        result = await self.test_ping_latency()
        report.results.append(result)
        self._print_result(result)
        if not result.passed:
            report.passed = False

        result = await self.test_agent_message("Hello, I'm an investor interested in this demo.")
        report.results.append(result)
        self._print_result(result)
        if not result.passed:
            # Agent interaction is informational - may not have agents configured
            report.friction_points.append(f"{result.step}: {result.error}")

        # Sync steps
        result = self.test_template_content(template_id)
        report.results.append(result)
        self._print_result(result)
        if not result.passed:
            report.passed = False
            report.friction_points.append(f"{result.step}: {result.error}")

        result = self.test_deliverables(template_id)
        report.results.append(result)
        self._print_result(result)
        if not result.passed:
            report.passed = False
            report.friction_points.append(f"{result.step}: {result.error}")

        await self.disconnect()

        report.total_duration_s = time.perf_counter() - start_time

        return report


async def run_all_scenarios():
    """Run demo scenarios for all templates."""

    print("\n" + "="*60)
    print("  INVESTOR DEMO SCENARIO TESTS")
    print("="*60)

    templates = list_templates()
    print(f"\nFound {len(templates)} demo templates:")
    for t in templates:
        print(f"  • {t['id']}: {t['name']}")

    reports = []

    for template_info in templates:
        tester = DemoScenarioTester()
        report = await tester.run_scenario(template_info['id'])
        reports.append(report)

    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)

    all_passed = True
    for report in reports:
        status = "✓ PASS" if report.passed else "✗ FAIL"
        print(f"\n  [{status}] {report.template_name}")
        print(f"      Duration: {report.total_duration_s:.2f}s")

        passed_count = sum(1 for r in report.results if r.passed)
        print(f"      Steps: {passed_count}/{len(report.results)} passed")

        if report.friction_points:
            print(f"      Friction points:")
            for fp in report.friction_points:
                print(f"        - {fp}")
            all_passed = False

        if not report.passed:
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("  🎉 ALL DEMO SCENARIOS PASSED")
    else:
        print("  ⚠️  SOME SCENARIOS HAVE ISSUES")
    print("="*60 + "\n")

    # Save report
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "templates_tested": len(reports),
        "all_passed": all_passed,
        "reports": [
            {
                "template_id": r.template_id,
                "template_name": r.template_name,
                "passed": r.passed,
                "duration_s": r.total_duration_s,
                "results": [
                    {"step": res.step, "passed": res.passed, "duration_ms": res.duration_ms, "error": res.error}
                    for res in r.results
                ],
                "friction_points": r.friction_points
            }
            for r in reports
        ]
    }

    with open("demo_scenario_results.json", "w") as f:
        json.dump(report_data, f, indent=2)

    print(f"Report saved to: demo_scenario_results.json")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_scenarios())
    sys.exit(0 if success else 1)
