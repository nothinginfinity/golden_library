#!/usr/bin/env python3
"""
Token Reduction Analyzer
Measures actual token savings (not bytes) for various compression strategies.

This is the critical metric for reducing Claude API costs and context usage.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, field

# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    print("⚠️  tiktoken not available, using character approximation (install: pip install tiktoken)")


@dataclass
class TokenPattern:
    """Represents a repeated pattern with token costs."""
    hash: str
    content: Any
    tokens_per_instance: int
    count: int
    first_seen_line: int
    category: str = "unknown"

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed by all instances."""
        return self.tokens_per_instance * self.count

    @property
    def reference_tokens(self) -> int:
        """Tokens for a reference like {'$ref': 'cold#abc123'}."""
        # Approximate: {"$ref":"cold#abc123"} ≈ 8 tokens
        return 8

    @property
    def token_savings(self) -> int:
        """Tokens saved if extracted to index."""
        # Keep original once, replace others with refs
        return (self.tokens_per_instance * (self.count - 1)) - (self.reference_tokens * (self.count - 1))


class TokenAnalyzer:
    """Analyze JSONL files for token-based compression opportunities."""

    def __init__(self):
        if TIKTOKEN_AVAILABLE:
            # Use Claude's tokenizer (cl100k_base is closest to Claude)
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        else:
            self.tokenizer = None

        self.patterns: Dict[str, TokenPattern] = {}
        self.total_tokens = 0
        self.line_count = 0

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Rough approximation: 1 token ≈ 4 characters
            return len(text) // 4

    def analyze_file(self, jsonl_path: str) -> Dict[str, Any]:
        """
        Analyze JSONL file for token reduction opportunities.

        Args:
            jsonl_path: Path to conversation file

        Returns:
            Token analysis report
        """
        path = Path(jsonl_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {jsonl_path}")

        print(f"🔍 Analyzing: {path.name}")
        print(f"📏 Size: {path.stat().st_size:,} bytes")

        if not TIKTOKEN_AVAILABLE:
            print("⚠️  Using character approximation (install tiktoken for accuracy)")
        print()

        # Read and analyze
        lines = []
        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                    lines.append(obj)
                    self.line_count += 1

                    # Count tokens for this line
                    line_tokens = self.count_tokens(line)
                    self.total_tokens += line_tokens

                    # Extract patterns
                    self._analyze_object(obj, line_num)

                except json.JSONDecodeError:
                    continue

        # Calculate SLIM compression
        slim_tokens = self._estimate_slim_tokens(lines)

        # Calculate index-based compression
        index_tokens = self._estimate_index_tokens(lines)

        # Generate report
        return self._generate_report(lines, slim_tokens, index_tokens)

    def _analyze_object(self, obj: Any, line_num: int, path: str = ""):
        """Recursively analyze object for patterns."""
        if isinstance(obj, dict) and obj:
            # Serialize and hash
            serialized = json.dumps(obj, sort_keys=True, separators=(',', ':'))
            obj_hash = hashlib.sha256(serialized.encode()).hexdigest()[:12]
            tokens = self.count_tokens(serialized)

            # Only track significant patterns (>20 tokens)
            if tokens > 20:
                if obj_hash in self.patterns:
                    self.patterns[obj_hash].count += 1
                else:
                    self.patterns[obj_hash] = TokenPattern(
                        hash=obj_hash,
                        content=obj,
                        tokens_per_instance=tokens,
                        count=1,
                        first_seen_line=line_num,
                        category=self._categorize(obj)
                    )

            # Recurse
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                self._analyze_object(value, line_num, new_path)

        elif isinstance(obj, list):
            for item in obj:
                self._analyze_object(item, line_num, path)

    def _categorize(self, obj: Dict) -> str:
        """Categorize pattern type."""
        if "name" in obj and "parameters" in obj:
            return "tool_definition"
        elif "role" in obj:
            role = obj.get("role")
            if role == "system":
                return "system_message"
            return f"{role}_message"
        elif "type" in obj:
            type_val = obj.get("type")
            if type_val == "tool_use":
                return "tool_use_block"
            return f"{type_val}_block"
        elif "$schema" in obj:
            return "json_schema"
        return "generic_object"

    def _estimate_slim_tokens(self, lines: List[Dict]) -> int:
        """Estimate tokens after SLIM compression."""
        # SLIM compression: abbreviate keys
        # role→r, content→c, type→t, text→x, etc.
        # Rough estimate: 40% token reduction on structure

        total = 0
        for obj in lines:
            serialized = json.dumps(obj, separators=(',', ':'))
            tokens = self.count_tokens(serialized)

            # SLIM saves tokens on:
            # 1. Key names (role→r, content→c): ~30% of structural tokens
            # 2. Repeated strings: ~10% additional
            # Content (actual text) is unchanged

            # Rough model: 60% structure, 40% content
            # SLIM saves 40% of structure tokens
            structure_tokens = int(tokens * 0.6)
            content_tokens = int(tokens * 0.4)

            slim_structure = int(structure_tokens * 0.6)  # 40% savings
            total += slim_structure + content_tokens

        return total

    def _estimate_index_tokens(self, lines: List[Dict]) -> int:
        """Estimate tokens with index-based extraction."""
        # Start with current tokens
        total = self.total_tokens

        # Subtract savings from extracted patterns
        duplicates = {k: v for k, v in self.patterns.items() if v.count > 1}

        for pattern in duplicates.values():
            total -= pattern.token_savings

        # Add one-time index overhead (if patterns are extracted)
        if duplicates:
            # Index structure overhead: ~50 tokens per pattern
            index_overhead = len(duplicates) * 50
            total += index_overhead

        return max(total, 0)

    def _generate_report(self, lines: List[Dict], slim_tokens: int, index_tokens: int) -> Dict[str, Any]:
        """Generate comprehensive token analysis report."""
        duplicates = {k: v for k, v in self.patterns.items() if v.count > 1}

        sorted_patterns = sorted(
            duplicates.values(),
            key=lambda x: x.token_savings,
            reverse=True
        )

        total_pattern_savings = sum(p.token_savings for p in sorted_patterns)

        # Combined SLIM + Index
        combined_tokens = int(slim_tokens * 0.9)  # Index reduces SLIM output by ~10%

        # By category
        by_category = defaultdict(list)
        for p in sorted_patterns:
            by_category[p.category].append(p)

        category_stats = {}
        for cat, patterns in by_category.items():
            category_stats[cat] = {
                "pattern_count": len(patterns),
                "total_instances": sum(p.count for p in patterns),
                "total_tokens": sum(p.total_tokens for p in patterns),
                "token_savings": sum(p.token_savings for p in patterns)
            }

        return {
            "overview": {
                "lines": self.line_count,
                "total_tokens": self.total_tokens,
                "tokenizer": "tiktoken (cl100k_base)" if TIKTOKEN_AVAILABLE else "approximation"
            },
            "compression_strategies": {
                "original": {
                    "tokens": self.total_tokens,
                    "percent": 100.0
                },
                "slim_only": {
                    "tokens": slim_tokens,
                    "reduction_tokens": self.total_tokens - slim_tokens,
                    "reduction_percent": round((1 - slim_tokens / self.total_tokens) * 100, 1) if self.total_tokens > 0 else 0
                },
                "index_only": {
                    "tokens": index_tokens,
                    "reduction_tokens": self.total_tokens - index_tokens,
                    "reduction_percent": round((1 - index_tokens / self.total_tokens) * 100, 1) if self.total_tokens > 0 else 0
                },
                "slim_plus_index": {
                    "tokens": combined_tokens,
                    "reduction_tokens": self.total_tokens - combined_tokens,
                    "reduction_percent": round((1 - combined_tokens / self.total_tokens) * 100, 1) if self.total_tokens > 0 else 0
                }
            },
            "pattern_analysis": {
                "unique_patterns": len(self.patterns),
                "repeated_patterns": len(duplicates),
                "total_pattern_tokens": sum(p.total_tokens for p in sorted_patterns),
                "potential_savings": total_pattern_savings
            },
            "by_category": category_stats,
            "top_patterns": sorted_patterns[:20]
        }

    def print_report(self, report: Dict[str, Any]):
        """Print human-readable token analysis."""
        print()
        print("=" * 80)
        print("🎯 TOKEN REDUCTION ANALYSIS")
        print("=" * 80)
        print()

        overview = report["overview"]
        print(f"📊 Overview:")
        print(f"   Lines: {overview['lines']:,}")
        print(f"   Total tokens: {overview['total_tokens']:,}")
        print(f"   Tokenizer: {overview['tokenizer']}")
        print()

        print("💰 COMPRESSION STRATEGIES:")
        print("-" * 80)
        print(f"{'Strategy':<25} {'Tokens':<15} {'Saved':<15} {'Reduction':<12}")
        print("-" * 80)

        strats = report["compression_strategies"]
        orig = strats["original"]["tokens"]

        print(f"{'Original':<25} {orig:,}{'':<15} {'':<15} {'100.0%':<12}")

        for name, data in [
            ("SLIM only", strats["slim_only"]),
            ("Index only", strats["index_only"]),
            ("SLIM + Index", strats["slim_plus_index"])
        ]:
            tokens = data["tokens"]
            saved = data["reduction_tokens"]
            percent = data["reduction_percent"]
            print(f"{name:<25} {tokens:,}{'':<15} {saved:,}{'':<15} {percent}%")

        print()

        # Pattern analysis
        pa = report["pattern_analysis"]
        print("🔍 Pattern Analysis:")
        print(f"   Unique patterns: {pa['unique_patterns']:,}")
        print(f"   Repeated patterns: {pa['repeated_patterns']:,}")
        print(f"   Tokens in repeats: {pa['total_pattern_tokens']:,}")
        print(f"   Extractable savings: {pa['potential_savings']:,}")
        print()

        # By category
        if report["by_category"]:
            print("📦 Token Savings by Category:")
            print("-" * 80)
            print(f"{'Category':<25} {'Patterns':<12} {'Instances':<12} {'Token Savings':<15}")
            print("-" * 80)

            for cat, stats in sorted(
                report["by_category"].items(),
                key=lambda x: x[1]["token_savings"],
                reverse=True
            ):
                print(f"{cat:<25} {stats['pattern_count']:<12} {stats['total_instances']:<12} {stats['token_savings']:,}")
            print()

        # Top patterns
        print("🏆 TOP 10 TOKEN REDUCTION OPPORTUNITIES:")
        print("-" * 80)

        for i, pattern in enumerate(report["top_patterns"][:10], 1):
            print(f"\n{i}. {pattern.category.upper()}")
            print(f"   Hash: {pattern.hash}")
            print(f"   Appears: {pattern.count} times")
            print(f"   Tokens per instance: {pattern.tokens_per_instance}")
            print(f"   Total tokens: {pattern.total_tokens:,}")
            print(f"   Token savings: {pattern.token_savings:,}")

            # Preview
            preview = json.dumps(pattern.content, indent=2)
            if len(preview) > 200:
                preview = preview[:200] + "..."
            print(f"   Preview: {preview}")

        print()
        print("=" * 80)
        print()

        # Recommendations
        print("💡 RECOMMENDATIONS:")
        print()

        slim_pct = strats["slim_only"]["reduction_percent"]
        index_pct = strats["index_only"]["reduction_percent"]
        combined_pct = strats["slim_plus_index"]["reduction_percent"]

        if combined_pct > 50:
            print("   ✅ HIGH compression potential (>50%)")
            print("   → Implement SLIM + Index for maximum savings")
        elif combined_pct > 30:
            print("   ✅ GOOD compression potential (30-50%)")
            print("   → SLIM + Index recommended")
        elif combined_pct > 15:
            print("   ⚠️  MODERATE compression potential (15-30%)")
            print("   → SLIM alone may be sufficient")
        else:
            print("   ℹ️  LOW compression potential (<15%)")
            print("   → Content-heavy conversation, limited structural savings")

        print()
        print(f"   Best strategy: SLIM + Index → {combined_pct}% token reduction")
        print(f"   Estimated API cost savings: ${(self.total_tokens - strats['slim_plus_index']['tokens']) / 1000 * 0.003:.2f} per conversation")
        print("   (Based on $3/M input tokens)")
        print()
        print("=" * 80)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze JSONL conversations for token reduction opportunities"
    )
    parser.add_argument("input", help="Input JSONL file")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()

    # Run analysis
    analyzer = TokenAnalyzer()
    report = analyzer.analyze_file(args.input)

    if args.json:
        # Remove patterns from JSON output (too verbose)
        output = {k: v for k, v in report.items() if k != "top_patterns"}
        print(json.dumps(output, indent=2))
    else:
        analyzer.print_report(report)


if __name__ == "__main__":
    main()
