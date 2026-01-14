#!/usr/bin/env python3
"""
Index-Based Compression Analyzer
Analyzes JSONL conversations to find repeated structures that could be extracted to indexes.

This tool identifies:
1. Repeated objects (tool definitions, system messages, etc.)
2. Frequency and size of duplicates
3. Potential compression savings with index-based references
4. Recommended index structure (hot/warm/cold)
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, field


@dataclass
class DuplicatePattern:
    """Represents a repeated structure in the conversation."""
    hash: str
    content: Any
    size_bytes: int
    count: int
    first_seen_line: int
    category: str = "unknown"
    locations: List[Tuple[int, str]] = field(default_factory=list)  # (line_num, json_path)

    @property
    def total_size(self) -> int:
        """Total bytes consumed by all instances."""
        return self.size_bytes * self.count

    @property
    def potential_savings(self) -> int:
        """Bytes saved if extracted to index (keeping one reference)."""
        # Keep original in index, replace others with ~20 byte reference
        reference_size = 20
        return (self.size_bytes * (self.count - 1)) - (reference_size * (self.count - 1))


class IndexAnalyzer:
    """Analyze JSONL files for index-based compression opportunities."""

    def __init__(self):
        self.duplicates: Dict[str, DuplicatePattern] = {}
        self.total_bytes = 0
        self.line_count = 0

    def analyze_file(self, jsonl_path: str) -> Dict[str, Any]:
        """
        Analyze a JSONL file for repeated structures.

        Args:
            jsonl_path: Path to .jsonl conversation file

        Returns:
            Analysis report with compression opportunities
        """
        path = Path(jsonl_path)
        if not path.exists():
            raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

        print(f"🔍 Analyzing: {path.name}")
        print(f"📏 Size: {path.stat().st_size:,} bytes\n")

        # Parse and analyze
        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                    self.line_count += 1
                    self.total_bytes += len(line.encode('utf-8'))
                    self._analyze_object(obj, line_num, root_path="")
                except json.JSONDecodeError:
                    continue

        # Categorize duplicates
        self._categorize_duplicates()

        # Generate report
        return self._generate_report()

    def _analyze_object(self, obj: Any, line_num: int, root_path: str, parent_key: str = ""):
        """Recursively analyze object for repeated structures."""
        if isinstance(obj, dict):
            # Hash the entire dict
            obj_hash = self._hash_object(obj)
            obj_size = len(json.dumps(obj, separators=(',', ':')).encode('utf-8'))

            # Track if this is a significant object (>50 bytes)
            if obj_size > 50:
                if obj_hash in self.duplicates:
                    self.duplicates[obj_hash].count += 1
                    self.duplicates[obj_hash].locations.append((line_num, root_path))
                else:
                    self.duplicates[obj_hash] = DuplicatePattern(
                        hash=obj_hash,
                        content=obj,
                        size_bytes=obj_size,
                        count=1,
                        first_seen_line=line_num,
                        locations=[(line_num, root_path)]
                    )

            # Recurse into nested structures
            for key, value in obj.items():
                new_path = f"{root_path}.{key}" if root_path else key
                self._analyze_object(value, line_num, new_path, key)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{root_path}[{i}]"
                self._analyze_object(item, line_num, new_path, parent_key)

    def _hash_object(self, obj: Any) -> str:
        """Create stable hash of object."""
        # Sort keys for consistent hashing
        serialized = json.dumps(obj, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:12]

    def _categorize_duplicates(self):
        """Categorize duplicates by type (tool, system message, etc.)."""
        for dup in self.duplicates.values():
            if not isinstance(dup.content, dict):
                continue

            # Identify category based on content structure
            if "name" in dup.content and "parameters" in dup.content:
                dup.category = "tool_definition"
            elif "role" in dup.content and dup.content.get("role") == "system":
                dup.category = "system_message"
            elif "role" in dup.content and dup.content.get("role") == "user":
                dup.category = "user_message"
            elif "role" in dup.content and dup.content.get("role") == "assistant":
                dup.category = "assistant_message"
            elif "type" in dup.content and dup.content.get("type") == "function":
                dup.category = "function_call"
            elif "content" in dup.content and isinstance(dup.content["content"], list):
                dup.category = "message_content_block"
            elif "$schema" in dup.content:
                dup.category = "json_schema"
            else:
                # Check for common patterns
                keys = set(dup.content.keys())
                if keys & {"id", "name", "type"}:
                    dup.category = "entity_definition"
                elif keys & {"error", "message", "code"}:
                    dup.category = "error_object"
                else:
                    dup.category = "generic_object"

    def _generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report."""
        # Filter to only show duplicates (count > 1)
        actual_duplicates = {k: v for k, v in self.duplicates.items() if v.count > 1}

        # Sort by potential savings
        sorted_dups = sorted(
            actual_duplicates.values(),
            key=lambda x: x.potential_savings,
            reverse=True
        )

        # Calculate total potential savings
        total_savings = sum(d.potential_savings for d in sorted_dups)

        # Category breakdown
        by_category = defaultdict(list)
        for dup in sorted_dups:
            by_category[dup.category].append(dup)

        category_stats = {}
        for category, dups in by_category.items():
            category_stats[category] = {
                "count": len(dups),
                "instances": sum(d.count for d in dups),
                "total_size": sum(d.total_size for d in dups),
                "potential_savings": sum(d.potential_savings for d in dups)
            }

        return {
            "file_stats": {
                "total_bytes": self.total_bytes,
                "line_count": self.line_count,
            },
            "duplicate_stats": {
                "unique_patterns": len(actual_duplicates),
                "total_instances": sum(d.count for d in sorted_dups),
                "total_duplicate_bytes": sum(d.total_size for d in sorted_dups),
                "potential_savings_bytes": total_savings,
                "potential_savings_percent": round((total_savings / self.total_bytes) * 100, 1) if self.total_bytes > 0 else 0
            },
            "by_category": category_stats,
            "top_patterns": sorted_dups[:20]  # Top 20 biggest savings
        }

    def print_report(self, report: Dict[str, Any]):
        """Print human-readable report."""
        fs = report["file_stats"]
        ds = report["duplicate_stats"]

        print("=" * 80)
        print("📊 INDEX-BASED COMPRESSION ANALYSIS")
        print("=" * 80)
        print()

        # File stats
        print("📁 File Statistics:")
        print(f"   Lines: {fs['line_count']:,}")
        print(f"   Total size: {fs['total_bytes']:,} bytes")
        print()

        # Duplicate stats
        print("🔁 Duplicate Patterns Found:")
        print(f"   Unique patterns: {ds['unique_patterns']:,}")
        print(f"   Total instances: {ds['total_instances']:,}")
        print(f"   Bytes in duplicates: {ds['total_duplicate_bytes']:,}")
        print()

        # Potential savings
        print("💰 INDEX-BASED COMPRESSION POTENTIAL:")
        print(f"   Current size: {fs['total_bytes']:,} bytes")
        print(f"   Potential savings: {ds['potential_savings_bytes']:,} bytes ({ds['potential_savings_percent']}%)")
        print(f"   After indexing: {fs['total_bytes'] - ds['potential_savings_bytes']:,} bytes")
        print()

        # Comparison with SLIM
        print("📊 COMPARISON:")
        print(f"   SLIM compression: ~10-15% savings (key abbreviation)")
        print(f"   Index compression: ~{ds['potential_savings_percent']}% savings (structure deduplication)")
        print(f"   Combined potential: ~{min(ds['potential_savings_percent'] + 12, 70)}% savings")
        print()

        # Category breakdown
        print("📦 By Category:")
        print("-" * 80)
        print(f"{'Category':<25} {'Patterns':<12} {'Instances':<12} {'Savings':<15}")
        print("-" * 80)

        for category, stats in sorted(
            report["by_category"].items(),
            key=lambda x: x[1]["potential_savings"],
            reverse=True
        ):
            print(f"{category:<25} {stats['count']:<12} {stats['instances']:<12} {stats['potential_savings']:,} bytes")
        print()

        # Top patterns
        print("🏆 TOP 10 COMPRESSION OPPORTUNITIES:")
        print("-" * 80)

        for i, dup in enumerate(report["top_patterns"][:10], 1):
            print(f"\n{i}. {dup.category.upper()}")
            print(f"   Hash: {dup.hash}")
            print(f"   Appears: {dup.count} times")
            print(f"   Size: {dup.size_bytes} bytes each")
            print(f"   Savings: {dup.potential_savings:,} bytes")
            print(f"   First seen: line {dup.first_seen_line}")

            # Show preview of content
            preview = json.dumps(dup.content, indent=2)
            if len(preview) > 200:
                preview = preview[:200] + "..."
            print(f"   Preview: {preview}")

        print()
        print("=" * 80)

    def generate_index_recommendations(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations for index structure."""
        by_cat = report["by_category"]

        # Determine hot/warm/cold classification
        hot_index = []  # Per-session, high frequency
        warm_index = []  # Per-project, moderate frequency
        cold_index = []  # Global, universal structures

        for category, stats in by_cat.items():
            avg_instances = stats["instances"] / max(stats["count"], 1)

            if avg_instances >= 5:
                hot_index.append(category)
            elif category in ["tool_definition", "json_schema"]:
                cold_index.append(category)
            else:
                warm_index.append(category)

        return {
            "recommended_structure": {
                "hot": {
                    "categories": hot_index,
                    "description": "High-frequency patterns in this conversation",
                    "location": "~/.claude/indexes/sessions/{session_id}_hot.json"
                },
                "warm": {
                    "categories": warm_index,
                    "description": "Project-specific patterns",
                    "location": "~/.claude/indexes/projects/{project_id}_warm.json"
                },
                "cold": {
                    "categories": cold_index,
                    "description": "Universal patterns (tools, schemas)",
                    "location": "~/.claude/indexes/global_cold.json"
                }
            },
            "extraction_threshold": {
                "min_occurrences": 2,
                "min_size_bytes": 50,
                "recommended": "Extract patterns appearing 3+ times, >100 bytes"
            }
        }

    def print_recommendations(self, recommendations: Dict[str, Any]):
        """Print index structure recommendations."""
        print("=" * 80)
        print("🏗️  RECOMMENDED INDEX ARCHITECTURE")
        print("=" * 80)
        print()

        for tier, config in recommendations["recommended_structure"].items():
            print(f"📦 {tier.upper()} INDEX:")
            print(f"   Categories: {', '.join(config['categories']) if config['categories'] else 'None'}")
            print(f"   Purpose: {config['description']}")
            print(f"   Location: {config['location']}")
            print()

        print("⚙️  EXTRACTION SETTINGS:")
        thresh = recommendations["extraction_threshold"]
        print(f"   Minimum occurrences: {thresh['min_occurrences']}")
        print(f"   Minimum size: {thresh['min_size_bytes']} bytes")
        print(f"   Recommended: {thresh['recommended']}")
        print()
        print("=" * 80)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze JSONL conversations for index-based compression opportunities"
    )
    parser.add_argument("input", help="Input JSONL file path")
    parser.add_argument(
        "--recommendations",
        action="store_true",
        help="Show index structure recommendations"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of human-readable"
    )

    args = parser.parse_args()

    # Run analysis
    analyzer = IndexAnalyzer()
    report = analyzer.analyze_file(args.input)

    if args.json:
        # JSON output
        output = {"analysis": report}
        if args.recommendations:
            output["recommendations"] = analyzer.generate_index_recommendations(report)
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        analyzer.print_report(report)

        if args.recommendations:
            print()
            recommendations = analyzer.generate_index_recommendations(report)
            analyzer.print_recommendations(recommendations)


if __name__ == "__main__":
    main()
