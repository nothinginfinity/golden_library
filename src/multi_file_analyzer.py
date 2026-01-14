#!/usr/bin/env python3
"""
Multi-File Index Analyzer
Analyzes multiple JSONL conversations to find cross-file deduplication opportunities.

This shows the true power of global indexes - patterns that appear across many conversations.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class CrossFilePattern:
    """Pattern that appears across multiple files."""
    hash: str
    content: Any
    size_bytes: int
    total_count: int
    file_count: int
    files: Dict[str, int] = field(default_factory=dict)  # filename -> count
    category: str = "unknown"

    @property
    def avg_per_file(self) -> float:
        return self.total_count / self.file_count if self.file_count > 0 else 0

    @property
    def cross_file_savings(self) -> int:
        """Savings if stored in global index vs per-file."""
        # Keep one copy in global index, all instances use 20-byte reference
        reference_size = 20
        return (self.size_bytes * self.total_count) - self.size_bytes - (reference_size * self.total_count)


class MultiFileAnalyzer:
    """Analyze multiple JSONL files for cross-file deduplication."""

    def __init__(self):
        self.patterns: Dict[str, CrossFilePattern] = {}
        self.file_stats: Dict[str, Dict] = {}
        self.total_files = 0
        self.total_bytes = 0

    def analyze_directory(self, dir_path: str, pattern: str = "*.jsonl") -> Dict[str, Any]:
        """
        Analyze all JSONL files in directory.

        Args:
            dir_path: Directory to scan
            pattern: File glob pattern

        Returns:
            Cross-file analysis report
        """
        path = Path(dir_path).expanduser()
        files = list(path.rglob(pattern))

        if not files:
            raise FileNotFoundError(f"No {pattern} files found in {dir_path}")

        print(f"🔍 Scanning {len(files)} files in {path}")
        print()

        for file_path in files:
            try:
                self._analyze_file(file_path)
            except Exception as e:
                print(f"⚠️  Skipped {file_path.name}: {e}")

        return self._generate_report()

    def _analyze_file(self, file_path: Path):
        """Analyze single file and update cross-file patterns."""
        file_name = file_path.name
        file_size = file_path.stat().st_size

        # Skip very large files
        if file_size > 100 * 1024 * 1024:  # 100MB
            print(f"⚠️  Skipping {file_name} (too large: {file_size:,} bytes)")
            return

        local_patterns = {}  # Hash -> count in this file
        line_count = 0

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                    line_count += 1
                    self._extract_patterns(obj, local_patterns)
                except json.JSONDecodeError:
                    continue

        # Update global patterns
        for obj_hash, (content, size) in local_patterns.items():
            if obj_hash not in self.patterns:
                self.patterns[obj_hash] = CrossFilePattern(
                    hash=obj_hash,
                    content=content,
                    size_bytes=size,
                    total_count=0,
                    file_count=0
                )

            pattern = self.patterns[obj_hash]
            pattern.total_count += 1
            pattern.file_count += 1
            pattern.files[file_name] = pattern.files.get(file_name, 0) + 1

        self.file_stats[file_name] = {
            "size_bytes": file_size,
            "line_count": line_count,
            "unique_patterns": len(local_patterns)
        }

        self.total_files += 1
        self.total_bytes += file_size

        print(f"✅ {file_name}: {line_count} lines, {len(local_patterns)} unique patterns")

    def _extract_patterns(self, obj: Any, patterns: Dict):
        """Extract patterns from object."""
        if isinstance(obj, dict) and obj:
            obj_hash = self._hash_object(obj)
            size = len(json.dumps(obj, separators=(',', ':')).encode('utf-8'))

            # Only track significant objects (>50 bytes)
            if size > 50:
                if obj_hash not in patterns:
                    patterns[obj_hash] = (obj, size)

            # Recurse
            for value in obj.values():
                self._extract_patterns(value, patterns)

        elif isinstance(obj, list):
            for item in obj:
                self._extract_patterns(item, patterns)

    def _hash_object(self, obj: Any) -> str:
        """Create stable hash."""
        serialized = json.dumps(obj, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:12]

    def _categorize_pattern(self, content: Any) -> str:
        """Categorize pattern."""
        if not isinstance(content, dict):
            return "unknown"

        if "name" in content and "parameters" in content:
            return "tool_definition"
        elif "role" in content:
            role = content.get("role")
            if role == "system":
                return "system_message"
            elif role in ["user", "assistant"]:
                return f"{role}_message"
        elif "type" in content and content.get("type") == "tool_use":
            return "tool_use_block"
        elif "$schema" in content:
            return "json_schema"

        return "generic_object"

    def _generate_report(self) -> Dict[str, Any]:
        """Generate cross-file analysis report."""
        # Filter to only cross-file patterns (appears in 2+ files)
        cross_file = {k: v for k, v in self.patterns.items() if v.file_count >= 2}

        # Categorize
        for pattern in cross_file.values():
            pattern.category = self._categorize_pattern(pattern.content)

        # Sort by savings
        sorted_patterns = sorted(
            cross_file.values(),
            key=lambda x: x.cross_file_savings,
            reverse=True
        )

        # Total savings
        total_savings = sum(p.cross_file_savings for p in sorted_patterns)

        # By category
        by_category = defaultdict(list)
        for p in sorted_patterns:
            by_category[p.category].append(p)

        category_stats = {}
        for cat, patterns in by_category.items():
            category_stats[cat] = {
                "pattern_count": len(patterns),
                "total_instances": sum(p.total_count for p in patterns),
                "file_coverage": sum(p.file_count for p in patterns),
                "total_savings": sum(p.cross_file_savings for p in patterns)
            }

        return {
            "overview": {
                "total_files": self.total_files,
                "total_bytes": self.total_bytes,
                "patterns_found": len(self.patterns),
                "cross_file_patterns": len(cross_file)
            },
            "savings": {
                "current_size": self.total_bytes,
                "potential_savings": total_savings,
                "savings_percent": round((total_savings / self.total_bytes) * 100, 1) if self.total_bytes > 0 else 0,
                "after_indexing": self.total_bytes - total_savings
            },
            "by_category": category_stats,
            "top_patterns": sorted_patterns[:30],
            "file_stats": self.file_stats
        }

    def print_report(self, report: Dict[str, Any]):
        """Print human-readable report."""
        print()
        print("=" * 80)
        print("📊 CROSS-FILE INDEX ANALYSIS")
        print("=" * 80)
        print()

        overview = report["overview"]
        print(f"📁 Analyzed Files: {overview['total_files']}")
        print(f"📏 Total Size: {overview['total_bytes']:,} bytes")
        print(f"🔍 Unique Patterns: {overview['patterns_found']:,}")
        print(f"🔗 Cross-File Patterns: {overview['cross_file_patterns']:,}")
        print()

        savings = report["savings"]
        print("💰 GLOBAL INDEX POTENTIAL:")
        print(f"   Current total: {savings['current_size']:,} bytes")
        print(f"   With global index: {savings['after_indexing']:,} bytes")
        print(f"   Savings: {savings['potential_savings']:,} bytes ({savings['savings_percent']}%)")
        print()

        print("📦 Cross-File Patterns by Category:")
        print("-" * 80)
        print(f"{'Category':<25} {'Patterns':<12} {'Instances':<12} {'Savings':<15}")
        print("-" * 80)

        for cat, stats in sorted(
            report["by_category"].items(),
            key=lambda x: x[1]["total_savings"],
            reverse=True
        ):
            print(f"{cat:<25} {stats['pattern_count']:<12} {stats['total_instances']:<12} {stats['total_savings']:,} bytes")
        print()

        print("🏆 TOP 15 CROSS-FILE PATTERNS:")
        print("-" * 80)

        for i, pattern in enumerate(report["top_patterns"][:15], 1):
            print(f"\n{i}. {pattern.category.upper()}")
            print(f"   Hash: {pattern.hash}")
            print(f"   Appears in: {pattern.file_count} files")
            print(f"   Total instances: {pattern.total_count}")
            print(f"   Size: {pattern.size_bytes} bytes each")
            print(f"   Savings: {pattern.cross_file_savings:,} bytes")

            # Show which files
            if len(pattern.files) <= 5:
                files_str = ", ".join(f"{f}({c})" for f, c in pattern.files.items())
                print(f"   Files: {files_str}")

            # Preview
            preview = json.dumps(pattern.content, indent=2)
            if len(preview) > 150:
                preview = preview[:150] + "..."
            print(f"   Preview: {preview}")

        print()
        print("=" * 80)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze multiple JSONL files for cross-file deduplication"
    )
    parser.add_argument("directory", help="Directory containing JSONL files")
    parser.add_argument(
        "--pattern",
        default="*.jsonl",
        help="File pattern to match (default: *.jsonl)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()

    analyzer = MultiFileAnalyzer()
    report = analyzer.analyze_directory(args.directory, args.pattern)

    if args.json:
        # Remove top_patterns from JSON output (too verbose)
        output = {k: v for k, v in report.items() if k != "top_patterns"}
        print(json.dumps(output, indent=2))
    else:
        analyzer.print_report(report)


if __name__ == "__main__":
    main()
