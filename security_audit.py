#!/usr/bin/env python3
"""
Day 6: Basic Security Audit for Golden Library
Checks for common vulnerabilities and security best practices.

Checks:
- Input validation
- SQL injection protection
- XSS prevention
- Path traversal prevention
- Sensitive data exposure
- Authentication/Authorization patterns
"""

import os
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
from datetime import datetime


@dataclass
class SecurityFinding:
    """A security finding."""
    severity: str  # HIGH, MEDIUM, LOW, INFO
    category: str
    file: str
    line: int
    description: str
    code_snippet: str = ""
    recommendation: str = ""


class SecurityAuditor:
    """Basic security auditor for Python codebase."""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.findings: List[SecurityFinding] = []
        self.files_scanned = 0

    def scan_file(self, file_path: Path) -> List[SecurityFinding]:
        """Scan a single Python file for security issues."""
        findings = []

        # Skip self (security audit script) and test files with intentional security issues
        if 'security_audit' in str(file_path):
            return findings

        # Skip test files (intentional security test cases)
        if 'test_' in str(file_path.name) and 'phase4c3' in str(file_path):
            return findings

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
        except Exception:
            return findings

        rel_path = str(file_path.relative_to(self.root_dir))

        for i, line in enumerate(lines, 1):
            # Check for SQL injection patterns
            findings.extend(self._check_sql_injection(rel_path, i, line))

            # Check for command injection patterns
            findings.extend(self._check_command_injection(rel_path, i, line))

            # Check for path traversal
            findings.extend(self._check_path_traversal(rel_path, i, line))

            # Check for hardcoded secrets
            findings.extend(self._check_hardcoded_secrets(rel_path, i, line))

            # Check for unsafe deserialization
            findings.extend(self._check_unsafe_deserialization(rel_path, i, line))

            # Check for debug/verbose modes
            findings.extend(self._check_debug_mode(rel_path, i, line))

        return findings

    def _check_sql_injection(self, file: str, line: int, code: str) -> List[SecurityFinding]:
        """Check for potential SQL injection vulnerabilities."""
        findings = []

        # Pattern: String formatting in SQL queries
        sql_format_patterns = [
            (r'execute\s*\(\s*["\'].*%s.*["\']', "String formatting in SQL execute"),
            (r'execute\s*\(\s*f["\']', "f-string in SQL execute"),
            (r'execute\s*\(\s*["\'].*\+', "String concatenation in SQL"),
            (r'executemany\s*\(\s*f["\']', "f-string in SQL executemany"),
        ]

        for pattern, desc in sql_format_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                # Check if it's using parameterized queries
                if '?' not in code and ':' not in code:
                    findings.append(SecurityFinding(
                        severity="HIGH",
                        category="SQL Injection",
                        file=file,
                        line=line,
                        description=desc,
                        code_snippet=code.strip()[:100],
                        recommendation="Use parameterized queries with ? or :param placeholders"
                    ))

        return findings

    def _check_command_injection(self, file: str, line: int, code: str) -> List[SecurityFinding]:
        """Check for potential command injection vulnerabilities."""
        findings = []

        # Dangerous patterns
        patterns = [
            (r'os\.system\s*\(', "os.system() is vulnerable to command injection"),
            (r'subprocess\..*shell\s*=\s*True', "shell=True enables command injection"),
            (r'eval\s*\(', "eval() can execute arbitrary code"),
            (r'exec\s*\(', "exec() can execute arbitrary code"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, code):
                # Skip if it's in a comment
                stripped = code.lstrip()
                if stripped.startswith('#'):
                    continue

                # Skip if it's a security check LOOKING for these patterns (not using them)
                if "'eval(" in code or '"eval(' in code or "in code" in code:
                    continue
                if "'exec(" in code or '"exec(' in code:
                    continue
                if "security" in code.lower() or "risk" in code.lower():
                    continue

                findings.append(SecurityFinding(
                    severity="HIGH" if "eval" in pattern or "exec" in pattern else "MEDIUM",
                    category="Command Injection",
                    file=file,
                    line=line,
                    description=desc,
                    code_snippet=code.strip()[:100],
                    recommendation="Use subprocess.run() with shell=False and argument list"
                ))

        return findings

    def _check_path_traversal(self, file: str, line: int, code: str) -> List[SecurityFinding]:
        """Check for potential path traversal vulnerabilities."""
        findings = []

        # Patterns that might indicate path traversal risk
        patterns = [
            (r'open\s*\([^)]*\+', "String concatenation in file open"),
            (r'open\s*\(.*request\.|open\s*\(.*data\[', "User input in file path"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                findings.append(SecurityFinding(
                    severity="MEDIUM",
                    category="Path Traversal",
                    file=file,
                    line=line,
                    description=desc,
                    code_snippet=code.strip()[:100],
                    recommendation="Validate and sanitize file paths, use os.path.realpath()"
                ))

        return findings

    def _check_hardcoded_secrets(self, file: str, line: int, code: str) -> List[SecurityFinding]:
        """Check for hardcoded secrets."""
        findings = []

        # Skip if in a comment
        if code.lstrip().startswith('#'):
            return findings

        # Patterns for hardcoded secrets
        patterns = [
            (r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'(?:api_key|apikey|api-key)\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r'(?:secret|token)\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', "Hardcoded secret/token"),
            (r'(?:sk-|pk_live_|sk_live_)[a-zA-Z0-9]{20,}', "Hardcoded Stripe/OpenAI key"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                # Exclude example/placeholder/documentation values
                if any(x in code.lower() for x in ['example', 'placeholder', 'your_', 'your-', 'xxx', 'changeme', 'export ', 'set it with']):
                    continue
                # Exclude docstrings and print statements with instructions
                if code.strip().startswith('"') or code.strip().startswith("print("):
                    continue

                findings.append(SecurityFinding(
                    severity="HIGH",
                    category="Hardcoded Secrets",
                    file=file,
                    line=line,
                    description=desc,
                    code_snippet=code.strip()[:60] + "...",  # Truncate to avoid exposing
                    recommendation="Use environment variables or secure secret management"
                ))

        return findings

    def _check_unsafe_deserialization(self, file: str, line: int, code: str) -> List[SecurityFinding]:
        """Check for unsafe deserialization."""
        findings = []

        patterns = [
            (r'pickle\.loads?\s*\(', "pickle can execute arbitrary code during deserialization"),
            (r'yaml\.load\s*\([^)]*\)', "yaml.load() without Loader is unsafe"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, code):
                # Check for safe usage
                if 'yaml.load' in pattern and 'Loader=' in code:
                    continue
                if 'yaml.load' in pattern and 'safe_load' in code:
                    continue

                findings.append(SecurityFinding(
                    severity="HIGH",
                    category="Unsafe Deserialization",
                    file=file,
                    line=line,
                    description=desc,
                    code_snippet=code.strip()[:100],
                    recommendation="Use yaml.safe_load() or specify Loader=yaml.SafeLoader"
                ))

        return findings

    def _check_debug_mode(self, file: str, line: int, code: str) -> List[SecurityFinding]:
        """Check for debug mode enabled in production."""
        findings = []

        patterns = [
            (r'debug\s*=\s*True', "Debug mode enabled"),
            (r'DEBUG\s*=\s*True', "DEBUG flag set to True"),
        ]

        for pattern, desc in patterns:
            if re.search(pattern, code):
                findings.append(SecurityFinding(
                    severity="LOW",
                    category="Debug Mode",
                    file=file,
                    line=line,
                    description=desc,
                    code_snippet=code.strip()[:100],
                    recommendation="Ensure debug mode is disabled in production"
                ))

        return findings

    def check_input_validation(self) -> List[SecurityFinding]:
        """Check for input validation patterns in WebSocket handlers."""
        findings = []

        # Look for WebSocket handlers
        ws_files = list(self.root_dir.glob("**/*.py"))

        for file_path in ws_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue

            rel_path = str(file_path.relative_to(self.root_dir))

            # Check for validation patterns
            if 'websocket' in content.lower() or 'ws_handler' in content:
                # Good: has validation
                has_validation = any([
                    'validate' in content,
                    'required_fields' in content,
                    'if not data.get' in content,
                    'missing' in content.lower() and 'field' in content.lower()
                ])

                if not has_validation and 'async def handle' in content:
                    findings.append(SecurityFinding(
                        severity="MEDIUM",
                        category="Input Validation",
                        file=rel_path,
                        line=0,
                        description="WebSocket handler may lack input validation",
                        recommendation="Add validation for all incoming message fields"
                    ))

        return findings

    def check_authentication(self) -> List[SecurityFinding]:
        """Check for authentication patterns."""
        findings = []

        # Look for session/auth patterns
        auth_patterns_found = False

        for file_path in self.root_dir.glob("**/*.py"):
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue

            if any(p in content for p in ['check_auth', 'authenticate', 'is_authenticated', 'require_login']):
                auth_patterns_found = True
                break

        if not auth_patterns_found:
            findings.append(SecurityFinding(
                severity="INFO",
                category="Authentication",
                file="(project-wide)",
                line=0,
                description="No authentication patterns found",
                recommendation="Consider adding authentication for sensitive operations"
            ))

        return findings

    def run_audit(self) -> Dict[str, Any]:
        """Run the complete security audit."""
        print("\n" + "=" * 60)
        print("  SECURITY AUDIT")
        print("=" * 60 + "\n")

        # Scan all Python files
        py_files = list(self.root_dir.glob("**/*.py"))
        py_files = [f for f in py_files if '__pycache__' not in str(f)]

        print(f"Scanning {len(py_files)} Python files...\n")

        for file_path in py_files:
            self.files_scanned += 1
            file_findings = self.scan_file(file_path)
            self.findings.extend(file_findings)

        # Additional checks
        self.findings.extend(self.check_input_validation())
        self.findings.extend(self.check_authentication())

        # Generate report
        return self._generate_report()

    def _generate_report(self) -> Dict[str, Any]:
        """Generate audit report."""
        # Count by severity
        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        for f in self.findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        # Count by category
        category_counts = {}
        for f in self.findings:
            category_counts[f.category] = category_counts.get(f.category, 0) + 1

        report = {
            "timestamp": datetime.now().isoformat(),
            "files_scanned": self.files_scanned,
            "summary": {
                "total_findings": len(self.findings),
                "by_severity": severity_counts,
                "by_category": category_counts,
                "high_severity": severity_counts["HIGH"],
                "pass": severity_counts["HIGH"] == 0  # Pass if no HIGH severity issues
            },
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "file": f.file,
                    "line": f.line,
                    "description": f.description,
                    "code_snippet": f.code_snippet,
                    "recommendation": f.recommendation
                }
                for f in sorted(self.findings, key=lambda x: ["HIGH", "MEDIUM", "LOW", "INFO"].index(x.severity))
            ]
        }

        return report


def print_report(report: Dict[str, Any]):
    """Print formatted audit report."""
    print("─" * 60)
    print("  SUMMARY")
    print("─" * 60)

    s = report["summary"]
    print(f"\nFiles scanned: {report['files_scanned']}")
    print(f"Total findings: {s['total_findings']}")

    print("\nBy Severity:")
    for sev in ["HIGH", "MEDIUM", "LOW", "INFO"]:
        count = s["by_severity"].get(sev, 0)
        if count > 0:
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "ℹ️"}.get(sev, "")
            print(f"  {icon} {sev}: {count}")

    if s["by_category"]:
        print("\nBy Category:")
        for cat, count in s["by_category"].items():
            print(f"  • {cat}: {count}")

    # Print findings
    if report["findings"]:
        print("\n" + "─" * 60)
        print("  FINDINGS")
        print("─" * 60)

        for f in report["findings"]:
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "ℹ️"}.get(f["severity"], "")
            print(f"\n{icon} [{f['severity']}] {f['category']}")
            print(f"   File: {f['file']}:{f['line']}")
            print(f"   {f['description']}")
            if f["code_snippet"]:
                print(f"   Code: {f['code_snippet']}")
            if f["recommendation"]:
                print(f"   Fix: {f['recommendation']}")

    print("\n" + "=" * 60)
    if s["pass"]:
        print("  ✓ AUDIT PASSED (No high-severity issues)")
    else:
        print(f"  ✗ AUDIT FAILED ({s['high_severity']} high-severity issues)")
    print("=" * 60 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Golden Library Security Audit")
    parser.add_argument("--path", default=".", help="Path to scan")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument("--output", help="Save report to file")
    args = parser.parse_args()

    auditor = SecurityAuditor(args.path)

    try:
        report = auditor.run_audit()
    except Exception as e:
        print(f"ERROR: Audit failed: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {args.output}")

    sys.exit(0 if report["summary"]["pass"] else 1)


if __name__ == "__main__":
    main()
