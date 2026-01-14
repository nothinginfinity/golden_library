#!/usr/bin/env python3
"""
Compression Benchmark Suite

Tests compression performance on various document types to measure:
- Compression ratio (%)
- Speed (docs/second)
- Token savings
- Round-trip fidelity
"""

import pytest
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unified_pipeline import UnifiedCompressionPipeline, CompressionResult
from token_analyzer import TokenAnalyzer


class TestCompressionBenchmarks:
    """Benchmark compression on different document types."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.token_analyzer = TokenAnalyzer()
        self.test_data_dir = Path(__file__).parent / "test_data"
        self.test_data_dir.mkdir(exist_ok=True)

    def test_benchmark_current_plan(self):
        """
        Benchmark: CURRENT_PLAN.md (11KB markdown PRD)

        Target: 80%+ reduction
        Current: ~30-50% reduction (SLIM + Index)
        """
        plan_path = Path(__file__).parent.parent / "CURRENT_PLAN.md"

        if not plan_path.exists():
            pytest.skip("CURRENT_PLAN.md not found")

        # Read original
        with open(plan_path, 'r') as f:
            original_content = f.read()

        original_tokens = self.token_analyzer.count_tokens(original_content)
        original_bytes = len(original_content.encode('utf-8'))

        print(f"\n📊 BENCHMARK: CURRENT_PLAN.md")
        print(f"   Original size: {original_bytes:,} bytes ({original_bytes/1024:.1f}KB)")
        print(f"   Original tokens: {original_tokens:,}")

        # Test at different compression levels
        levels = ["minimal", "balanced", "maximum"]
        results = {}

        for level in levels:
            print(f"\n🔍 Testing level: {level}")
            pipeline = UnifiedCompressionPipeline(level=level)

            # Create temp JSONL (wrap markdown as user message)
            temp_jsonl = self.test_data_dir / "temp_plan.jsonl"
            with open(temp_jsonl, 'w') as f:
                import json
                f.write(json.dumps({
                    "role": "user",
                    "content": original_content
                }) + '\n')

            # Compress
            start_time = time.time()
            result = pipeline.compress_conversation(
                str(temp_jsonl),
                output_dir=str(self.test_data_dir),
                session_id="benchmark_plan",
                project_id="golden_library"
            )
            compression_time = time.time() - start_time

            # Calculate metrics
            with open(result.output_path, 'r') as f:
                compressed_content = f.read()

            compressed_bytes = len(compressed_content.encode('utf-8'))
            compressed_tokens = result.final_tokens

            byte_reduction = round((1 - compressed_bytes / original_bytes) * 100, 1)
            token_reduction = result.total_reduction_percent

            results[level] = {
                "compressed_bytes": compressed_bytes,
                "compressed_tokens": compressed_tokens,
                "byte_reduction_pct": byte_reduction,
                "token_reduction_pct": token_reduction,
                "compression_time": compression_time,
                "output_path": result.output_path
            }

            print(f"\n   Results for {level}:")
            print(f"   • Compressed: {compressed_bytes:,} bytes ({compressed_bytes/1024:.1f}KB)")
            print(f"   • Byte reduction: {byte_reduction}%")
            print(f"   • Token reduction: {token_reduction}%")
            print(f"   • Compression time: {compression_time:.2f}s")
            print(f"   • Tokens saved: {original_tokens - compressed_tokens:,}")

        # Assert minimum targets
        print(f"\n🎯 Target Analysis:")

        # Current target (Phase 1): 50%+ with balanced
        balanced_reduction = results["balanced"]["token_reduction_pct"]
        print(f"   Balanced compression: {balanced_reduction}% (target: 50%+)")

        if balanced_reduction < 50:
            print(f"   ⚠️  Below target! Need improvement.")
        else:
            print(f"   ✅ Meeting current target")

        # Future target (Phase 4.5): 80%+ with maximum
        print(f"\n   Future target: 80%+ reduction")
        print(f"   Gap to close: {max(0, 80 - balanced_reduction)}%")

        # Cleanup
        temp_jsonl.unlink()
        for level_results in results.values():
            Path(level_results["output_path"]).unlink(missing_ok=True)

        # Store results for later analysis
        self._store_benchmark_results("current_plan", results)

    def test_benchmark_small_prd(self):
        """
        Benchmark: Small PRD (1-2KB)

        Tests compression on smaller documents to ensure we don't
        over-compress and lose readability.
        """
        small_prd = """# Project: User Authentication

## Overview
Add user authentication to the web app.

## Requirements
- Email/password login
- JWT tokens
- Password reset flow

## Tasks
- [ ] Design auth schema
- [ ] Implement login endpoint
- [ ] Add JWT middleware
- [ ] Build password reset

## Timeline
2-3 days
"""

        tokens = self.token_analyzer.count_tokens(small_prd)
        print(f"\n📊 BENCHMARK: Small PRD")
        print(f"   Tokens: {tokens}")

        # Small documents should use minimal compression
        pipeline = UnifiedCompressionPipeline(level="minimal")

        # Create temp file
        temp_jsonl = self.test_data_dir / "temp_small.jsonl"
        with open(temp_jsonl, 'w') as f:
            import json
            f.write(json.dumps({"role": "user", "content": small_prd}) + '\n')

        result = pipeline.compress_conversation(
            str(temp_jsonl),
            output_dir=str(self.test_data_dir)
        )

        reduction = result.total_reduction_percent
        print(f"   Reduction: {reduction}%")

        # Cleanup
        temp_jsonl.unlink()
        Path(result.output_path).unlink(missing_ok=True)

        # Small docs should still get 20%+ reduction
        assert reduction >= 20, f"Small PRD compression too low: {reduction}%"

    def test_benchmark_large_prd(self):
        """
        Benchmark: Large PRD (100KB+)

        Target: 80%+ reduction on repetitive content using V4Z
        """
        # Import V4Z compressor
        from v4z_compressor import V4ZCompressor

        # Generate large repetitive PRD
        large_prd_parts = []

        # Header
        large_prd_parts.append("# Large Project PRD\n\n")

        # Repeated sections
        for i in range(50):
            large_prd_parts.append(f"""## Feature {i+1}: User Management

### Requirements
- [ ] Implement user CRUD operations
- [ ] Add validation for user inputs
- [ ] Create database migrations
- [ ] Write unit tests
- [ ] Update API documentation

### Technical Notes
- Use PostgreSQL for data storage
- Implement JWT authentication
- Add rate limiting
- Follow REST best practices

### Acceptance Criteria
- All tests passing
- Code review approved
- Documentation updated

---

""")

        large_prd = "".join(large_prd_parts)
        tokens = self.token_analyzer.count_tokens(large_prd)
        size_kb = len(large_prd.encode('utf-8')) / 1024

        print(f"\n📊 BENCHMARK: Large PRD (V4Z Direct)")
        print(f"   Size: {size_kb:.1f}KB")
        print(f"   Tokens: {tokens:,}")

        # Test V4Z compression (maximum compression level)
        compressor = V4ZCompressor(compression_level=22)
        result = compressor.compress(large_prd)

        print(f"   Compressed: {result.compressed_size_bytes:,} bytes")
        print(f"   Byte reduction: {result.reduction_percent}%")
        print(f"   Token reduction: {result.token_reduction_percent}%")
        print(f"   Target: 80%+ (gap: {max(0, 80 - result.reduction_percent):.1f}%)")

        # Large repetitive docs should hit 80%+ with V4Z
        assert result.reduction_percent >= 80, f"Large PRD compression below target: {result.reduction_percent}%"

        print(f"   ✅ Target achieved! {result.reduction_percent}% >= 80%")

    def test_benchmark_speed(self):
        """
        Benchmark: Compression speed

        Target: <100ms for small docs, <1s for large docs
        """
        test_cases = [
            ("Small (1KB)", "x" * 1000),
            ("Medium (10KB)", "x" * 10000),
            ("Large (100KB)", "x" * 100000)
        ]

        print(f"\n📊 BENCHMARK: Compression Speed")

        pipeline = UnifiedCompressionPipeline(level="balanced")

        for name, content in test_cases:
            temp_jsonl = self.test_data_dir / "temp_speed.jsonl"
            with open(temp_jsonl, 'w') as f:
                import json
                f.write(json.dumps({"role": "user", "content": content}) + '\n')

            start = time.time()
            result = pipeline.compress_conversation(
                str(temp_jsonl),
                output_dir=str(self.test_data_dir)
            )
            elapsed = time.time() - start

            print(f"   {name}: {elapsed*1000:.1f}ms")

            # Cleanup
            temp_jsonl.unlink()
            Path(result.output_path).unlink(missing_ok=True)

    def _store_benchmark_results(self, benchmark_name: str, results: dict):
        """Store benchmark results for tracking over time."""
        results_file = Path(__file__).parent / "benchmark_results.json"

        import json
        from datetime import datetime

        # Load existing results
        if results_file.exists():
            with open(results_file, 'r') as f:
                all_results = json.load(f)
        else:
            all_results = {}

        # Add new results
        timestamp = datetime.now().isoformat()
        if benchmark_name not in all_results:
            all_results[benchmark_name] = []

        all_results[benchmark_name].append({
            "timestamp": timestamp,
            "results": results
        })

        # Save
        with open(results_file, 'w') as f:
            json.dump(all_results, f, indent=2)

        print(f"\n💾 Results saved to: {results_file}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
