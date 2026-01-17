#!/usr/bin/env python3
"""
Master Test Runner for Phase 4C
Runs all 54 tests across 6 sub-phases and generates reports.

Usage:
    python3 run_all_tests.py              # Run all tests
    python3 run_all_tests.py --html       # Generate HTML report
    python3 run_all_tests.py --coverage   # Run with coverage
    python3 run_all_tests.py --verbose    # Detailed output
"""

import sys
import os
import subprocess
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

# Test file inventory
TEST_FILES = [
    ("Phase 4C.1", "test_phase4c1_delegation.py", "Hierarchical Delegation"),
    ("Phase 4C.2", "test_phase4c2_canvas.py", "Canvas Sync"),
    ("Phase 4C.3", "test_phase4c3_tools.py", "Tool Gateway"),
    ("Phase 4C.4", "test_phase4c4_database.py", "Conversation Database"),
    ("Phase 4C.5", "test_phase4c5_demo.py", "Demo Mode"),
    ("Phase 4C.6", "test_phase4c6_config.py", "Configuration"),
    ("Edge Cases", "test_edge_cases.py", "Error Handling & Edge Cases"),
]


class TestResult:
    """Stores result for a single test file."""
    def __init__(self, phase: str, file: str, description: str):
        self.phase = phase
        self.file = file
        self.description = description
        self.passed = False
        self.duration = 0.0
        self.output = ""
        self.error = ""
        self.tests_passed = 0
        self.tests_failed = 0


def run_test_file(test_file: str, verbose: bool = False) -> tuple:
    """
    Run a single test file and capture results.
    Returns (passed, duration, output, error, tests_passed, tests_failed)
    """
    script_dir = Path(__file__).parent
    test_path = script_dir / test_file

    if not test_path.exists():
        return (False, 0.0, "", f"File not found: {test_file}", 0, 0)

    start = time.time()

    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout per test file
            cwd=str(script_dir)
        )
        duration = time.time() - start
        output = result.stdout
        error = result.stderr
        passed = result.returncode == 0

        # Parse test counts from output
        tests_passed = output.count("✓") - 1  # Subtract summary line
        tests_failed = output.count("❌")

        # More accurate count from RESULTS line
        for line in output.split("\n"):
            if "RESULTS:" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed," and i > 0:
                        try:
                            tests_passed = int(parts[i-1])
                        except ValueError:
                            pass
                    if part == "failed" and i > 0:
                        try:
                            tests_failed = int(parts[i-1])
                        except ValueError:
                            pass

        return (passed, duration, output, error, tests_passed, tests_failed)

    except subprocess.TimeoutExpired:
        return (False, 120.0, "", "Test timed out after 120 seconds", 0, 0)
    except Exception as e:
        return (False, 0.0, "", str(e), 0, 0)


def generate_html_report(results: list, total_duration: float) -> str:
    """Generate HTML test report."""

    total_passed = sum(r.tests_passed for r in results)
    total_failed = sum(r.tests_failed for r in results)
    all_passed = all(r.passed for r in results)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Phase 4C Test Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               margin: 40px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                   color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .summary {{ display: flex; gap: 20px; margin-top: 20px; }}
        .stat {{ background: rgba(255,255,255,0.2); padding: 15px 25px; border-radius: 8px; }}
        .stat-value {{ font-size: 32px; font-weight: bold; }}
        .stat-label {{ font-size: 12px; opacity: 0.9; }}
        .phase {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 15px;
                  box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .phase-header {{ display: flex; justify-content: space-between; align-items: center;
                        border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 15px; }}
        .phase-title {{ font-size: 18px; font-weight: 600; }}
        .phase-status {{ padding: 5px 15px; border-radius: 20px; font-weight: 500; }}
        .status-pass {{ background: #d4edda; color: #155724; }}
        .status-fail {{ background: #f8d7da; color: #721c24; }}
        .phase-details {{ display: flex; gap: 30px; color: #666; font-size: 14px; }}
        .output {{ background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 5px;
                   font-family: monospace; font-size: 12px; max-height: 300px; overflow: auto;
                   white-space: pre-wrap; margin-top: 15px; display: none; }}
        .toggle {{ cursor: pointer; color: #667eea; font-size: 14px; }}
        .timestamp {{ color: #999; font-size: 12px; margin-top: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 Phase 4C Test Report</h1>
        <p>Golden Library - Collaborative Workspace</p>
        <div class="summary">
            <div class="stat">
                <div class="stat-value">{total_passed + total_failed}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #90EE90;">{total_passed}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: {'#FFB6C1' if total_failed > 0 else '#90EE90'};">{total_failed}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_duration:.1f}s</div>
                <div class="stat-label">Duration</div>
            </div>
        </div>
    </div>
"""

    for r in results:
        status_class = "status-pass" if r.passed else "status-fail"
        status_text = "PASSED" if r.passed else "FAILED"

        html += f"""
    <div class="phase">
        <div class="phase-header">
            <div class="phase-title">{r.phase}: {r.description}</div>
            <div class="phase-status {status_class}">{status_text}</div>
        </div>
        <div class="phase-details">
            <span>📄 {r.file}</span>
            <span>✓ {r.tests_passed} passed</span>
            <span>✗ {r.tests_failed} failed</span>
            <span>⏱ {r.duration:.2f}s</span>
            <span class="toggle" onclick="this.parentElement.nextElementSibling.style.display = this.parentElement.nextElementSibling.style.display === 'none' ? 'block' : 'none'">
                [Show Output]
            </span>
        </div>
        <pre class="output">{r.output.replace('<', '&lt;').replace('>', '&gt;')}</pre>
    </div>
"""

    html += f"""
    <div class="timestamp">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
</body>
</html>
"""
    return html


def generate_json_report(results: list, total_duration: float) -> dict:
    """Generate JSON test report."""
    return {
        "timestamp": datetime.now().isoformat(),
        "total_duration": total_duration,
        "summary": {
            "total_tests": sum(r.tests_passed + r.tests_failed for r in results),
            "passed": sum(r.tests_passed for r in results),
            "failed": sum(r.tests_failed for r in results),
            "all_phases_passed": all(r.passed for r in results)
        },
        "phases": [
            {
                "phase": r.phase,
                "file": r.file,
                "description": r.description,
                "passed": r.passed,
                "duration": r.duration,
                "tests_passed": r.tests_passed,
                "tests_failed": r.tests_failed
            }
            for r in results
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Run Phase 4C test suite")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--json", action="store_true", help="Generate JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage (requires coverage package)")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("  PHASE 4C MASTER TEST RUNNER")
    print("  Golden Library - Collaborative Workspace")
    print("="*70 + "\n")

    results = []
    total_start = time.time()

    for phase, file, desc in TEST_FILES:
        print(f"Running {phase}: {desc}...")

        result = TestResult(phase, file, desc)
        passed, duration, output, error, tests_passed, tests_failed = run_test_file(file, args.verbose)

        result.passed = passed
        result.duration = duration
        result.output = output
        result.error = error
        result.tests_passed = tests_passed
        result.tests_failed = tests_failed
        results.append(result)

        status = "✓" if passed else "✗"
        print(f"  {status} {tests_passed} passed, {tests_failed} failed ({duration:.2f}s)")

        if args.verbose and not passed:
            print(f"  Error: {error[:200]}..." if len(error) > 200 else f"  Error: {error}")

    total_duration = time.time() - total_start

    # Summary
    total_passed = sum(r.tests_passed for r in results)
    total_failed = sum(r.tests_failed for r in results)
    all_passed = all(r.passed for r in results)

    print("\n" + "="*70)
    print("  SUMMARY")
    print("="*70)
    print(f"  Total Tests: {total_passed + total_failed}")
    print(f"  Passed:      {total_passed}")
    print(f"  Failed:      {total_failed}")
    print(f"  Duration:    {total_duration:.2f}s")
    print("="*70)

    if all_passed:
        print("\n🎉 ALL PHASE 4C TESTS PASSED!")
    else:
        print("\n❌ Some tests failed. See details above.")
        for r in results:
            if not r.passed:
                print(f"  - {r.phase}: {r.file}")

    # Generate reports
    script_dir = Path(__file__).parent

    if args.html:
        html = generate_html_report(results, total_duration)
        report_path = script_dir / "test_report.html"
        report_path.write_text(html)
        print(f"\n📄 HTML report: {report_path}")

    if args.json:
        report = generate_json_report(results, total_duration)
        report_path = script_dir / "test_report.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"\n📄 JSON report: {report_path}")

    # Always generate JSON for tracking
    report = generate_json_report(results, total_duration)
    report_path = script_dir / "test_results_latest.json"
    report_path.write_text(json.dumps(report, indent=2))

    print()
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
