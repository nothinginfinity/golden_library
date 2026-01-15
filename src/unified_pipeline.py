#!/usr/bin/env python3
"""
Unified Token Compression Pipeline

Combines multiple compression strategies:
1. V4Z Compression - SLIM vocabulary + Zstandard (75-85% token reduction)
2. Index Extraction - Pattern deduplication (3-5% additional) [OPTIONAL]
3. De-tokenization - Multi-token → single-token symbols (5-10% additional) [OPTIONAL]

Total Expected Reduction: 75-90% depending on level
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from slim_converter import SlimConverter
from index_extractor import IndexExtractor
from token_analyzer import TokenAnalyzer
from v4z_compressor import V4ZCompressor


@dataclass
class CompressionStageResult:
    """Result from a single compression stage."""
    stage_name: str
    tokens_before: int
    tokens_after: int
    reduction_percent: float
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompressionResult:
    """Final result from full pipeline."""
    original_path: str
    output_path: str
    original_tokens: int
    final_tokens: int
    total_reduction_percent: float
    stages: List[CompressionStageResult]
    indexes_created: Dict[str, str]
    processing_time_seconds: float
    level: str


class UnifiedCompressionPipeline:
    """
    Multi-stage token reduction pipeline.

    Compression Levels:
    - "minimal": V4Z only (fast, ~75-85% reduction)
    - "balanced": V4Z + Index (moderate, ~80% reduction)
    - "maximum": V4Z + Index + CairnESL (slow, ~85% reduction)
    """

    def __init__(self, level: str = "balanced"):
        """
        Initialize pipeline with compression level.

        Args:
            level: "minimal", "balanced", or "maximum"
        """
        if level not in ["minimal", "balanced", "maximum"]:
            raise ValueError(f"Invalid level: {level}. Must be minimal/balanced/maximum")

        self.level = level
        self.slim_converter = SlimConverter()
        self.index_extractor = IndexExtractor()
        self.token_analyzer = TokenAnalyzer()
        self.v4z_compressor = V4ZCompressor()  # Always available

        # Optional integrations
        self.cairn_esl = None
        self.fsl_compressor = None
        self.v4_compressor = None

        # Try to load optional components for "maximum" level
        if level == "maximum":
            self._load_optional_components()

    def _load_optional_components(self):
        """Attempt to load CairnESL, FSL, and V4 components."""
        try:
            # Try to import CairnESL
            cairn_path = Path("~/ztgi/ztp/pidgin/translation_agents").expanduser()
            if cairn_path.exists():
                sys.path.insert(0, str(cairn_path))
                from cairn_esl import CairnESLAgent
                self.cairn_esl = CairnESLAgent()
                print("✅ CairnESL integration loaded")
        except Exception as e:
            print(f"⚠️  CairnESL not available: {e}")

        try:
            # Try to import V4 compressor
            v4_path = Path("~/ztgi").expanduser()
            if (v4_path / "adaptive_compress_pipeline_v4.py").exists():
                sys.path.insert(0, str(v4_path))
                # Note: V4 is a script, not a module - would need refactoring
                print("⚠️  V4 integration available but requires refactoring")
        except Exception as e:
            print(f"⚠️  V4 not available: {e}")

    def compress_conversation(
        self,
        jsonl_path: str,
        output_dir: Optional[str] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> CompressionResult:
        """
        Compress JSONL conversation through pipeline.

        Args:
            jsonl_path: Path to JSONL conversation file
            output_dir: Output directory (default: same as input)
            session_id: Session ID for hot index
            project_id: Project ID for warm index

        Returns:
            CompressionResult with metrics and output path
        """
        start_time = datetime.now()

        input_path = Path(jsonl_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {jsonl_path}")

        # Set output directory
        if output_dir is None:
            output_dir = input_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        # Generate IDs if not provided
        if session_id is None:
            session_id = input_path.stem
        if project_id is None:
            project_id = input_path.parent.name or "default"

        # Read original content
        with open(input_path, 'r') as f:
            original_content = f.read()

        # Analyze original tokens
        print(f"\n🔍 Analyzing original file: {input_path.name}")
        original_tokens = self.token_analyzer.count_tokens(original_content)
        print(f"   Original tokens: {original_tokens:,}")

        stages = []
        current_content = original_content
        current_tokens = original_tokens
        indexes_created = {}

        # Stage 1: V4Z Compression (always runs)
        print("\n📦 Stage 1: V4Z Compression (SLIM + Zstandard)")
        v4z_result = self._stage_v4z(current_content, current_tokens)
        stages.append(v4z_result)
        current_content = v4z_result.content
        current_tokens = v4z_result.tokens_after

        # Stage 2: Index Extraction (balanced and maximum levels)
        if self.level in ["balanced", "maximum"]:
            print("\n🗂️  Stage 2: Index Extraction")
            index_result = self._stage_index(
                current_content,
                current_tokens,
                session_id,
                project_id
            )
            stages.append(index_result)
            current_content = index_result.content
            current_tokens = index_result.tokens_after
            indexes_created = index_result.metadata.get("indexes", {})

        # Stage 3: De-tokenization (maximum level only, if available)
        if self.level == "maximum" and self.cairn_esl:
            print("\n🔤 Stage 3: De-tokenization (CairnESL)")
            detok_result = self._stage_detokenize(current_content, current_tokens)
            stages.append(detok_result)
            current_content = detok_result.content
            current_tokens = detok_result.tokens_after

        # Stage 4: Vault Deduplication (maximum level, if available)
        if self.level == "maximum" and self.fsl_compressor:
            print("\n🏦 Stage 4: Vault Deduplication")
            vault_result = self._stage_vault(current_content, current_tokens)
            stages.append(vault_result)
            current_content = vault_result.content
            current_tokens = vault_result.tokens_after

        # Stage 5: V4 Dash-Codex (maximum level, if available)
        if self.level == "maximum" and self.v4_compressor:
            print("\n🗜️  Stage 5: V4 Dash-Codex")
            v4_result = self._stage_v4(current_content, current_tokens)
            stages.append(v4_result)
            current_content = v4_result.content
            current_tokens = v4_result.tokens_after

        # Write output
        output_suffix = {
            "minimal": ".v4z",
            "balanced": ".v4z",
            "maximum": ".v4z"
        }
        output_path = output_dir / f"{input_path.stem}{output_suffix[self.level]}"

        with open(output_path, 'w') as f:
            f.write(current_content)

        # Calculate total reduction
        total_reduction = round((1 - current_tokens / original_tokens) * 100, 1) if original_tokens > 0 else 0

        processing_time = (datetime.now() - start_time).total_seconds()

        result = CompressionResult(
            original_path=str(input_path),
            output_path=str(output_path),
            original_tokens=original_tokens,
            final_tokens=current_tokens,
            total_reduction_percent=total_reduction,
            stages=stages,
            indexes_created=indexes_created,
            processing_time_seconds=processing_time,
            level=self.level
        )

        # Print summary
        self._print_summary(result)

        return result

    def _stage_v4z(self, content: str, current_tokens: int) -> CompressionStageResult:
        """Stage 1: Compress with V4Z (SLIM + Zstandard)."""
        # Compress with V4Z
        result = self.v4z_compressor.compress(content, add_header=True)

        # V4Z result includes token estimation
        v4z_tokens = result.compressed_tokens
        reduction = result.token_reduction_percent

        print(f"   Tokens after V4Z: {v4z_tokens:,} ({reduction}% reduction)")
        print(f"   Size: {result.original_size_bytes:,} → {result.compressed_size_bytes:,} bytes")

        return CompressionStageResult(
            stage_name="V4Z Compression",
            tokens_before=current_tokens,
            tokens_after=v4z_tokens,
            reduction_percent=reduction,
            content=result.compressed_base64
        )

    def _stage_index(
        self,
        content: str,
        current_tokens: int,
        session_id: str,
        project_id: str
    ) -> CompressionStageResult:
        """Stage 2: Extract patterns to indexes."""
        # Extract patterns
        result = self.index_extractor.extract_patterns(
            content,
            threshold=3,
            output_dir="~/.claude/indexes",
            session_id=session_id,
            project_id=project_id
        )

        # Count tokens
        indexed_tokens = self.token_analyzer.count_tokens(result.content_with_refs)
        reduction = round((1 - indexed_tokens / current_tokens) * 100, 1) if current_tokens > 0 else 0

        print(f"   Patterns extracted: {result.patterns_extracted}")
        print(f"   Tokens after indexing: {indexed_tokens:,} ({reduction}% reduction)")

        return CompressionStageResult(
            stage_name="Index Extraction",
            tokens_before=current_tokens,
            tokens_after=indexed_tokens,
            reduction_percent=reduction,
            content=result.content_with_refs,
            metadata={
                "patterns_extracted": result.patterns_extracted,
                "indexes": {
                    "hot": f"~/.claude/indexes/sessions/{session_id}_hot.json",
                    "warm": f"~/.claude/indexes/projects/{project_id}_warm.json",
                    "cold": "~/.claude/indexes/global_cold.json"
                }
            }
        )

    def _stage_detokenize(self, content: str, current_tokens: int) -> CompressionStageResult:
        """Stage 3: De-tokenize (CairnESL symbols)."""
        # Apply CairnESL compression
        detok_result = self.cairn_esl.compress(
            content,
            apply_suffixes=True,
            apply_clusters=True,
            apply_operators=True
        )

        detok_tokens = self.token_analyzer.count_tokens(detok_result.compressed)
        reduction = round((1 - detok_tokens / current_tokens) * 100, 1) if current_tokens > 0 else 0

        print(f"   Tokens after de-tokenization: {detok_tokens:,} ({reduction}% reduction)")

        return CompressionStageResult(
            stage_name="De-tokenization",
            tokens_before=current_tokens,
            tokens_after=detok_tokens,
            reduction_percent=reduction,
            content=detok_result.compressed
        )

    def _stage_vault(self, content: str, current_tokens: int) -> CompressionStageResult:
        """Stage 4: Vault deduplication."""
        # Placeholder - would integrate with FSL vault system
        print("   Vault deduplication not yet integrated")

        return CompressionStageResult(
            stage_name="Vault Deduplication",
            tokens_before=current_tokens,
            tokens_after=current_tokens,
            reduction_percent=0.0,
            content=content
        )

    def _stage_v4(self, content: str, current_tokens: int) -> CompressionStageResult:
        """Stage 5: V4 dash-codex."""
        # Placeholder - would integrate with V4 system
        print("   V4 dash-codex not yet integrated")

        return CompressionStageResult(
            stage_name="V4 Dash-Codex",
            tokens_before=current_tokens,
            tokens_after=current_tokens,
            reduction_percent=0.0,
            content=content
        )

    def _print_summary(self, result: CompressionResult):
        """Print compression summary."""
        print("\n" + "=" * 80)
        print("✅ COMPRESSION COMPLETE")
        print("=" * 80)
        print(f"\n📊 Summary:")
        print(f"   Level: {result.level}")
        print(f"   Original: {result.original_tokens:,} tokens")
        print(f"   Final: {result.final_tokens:,} tokens")
        print(f"   Total reduction: {result.total_reduction_percent}%")
        print(f"   Processing time: {result.processing_time_seconds:.2f}s")

        print(f"\n📁 Output: {result.output_path}")

        if result.indexes_created:
            print(f"\n🗂️  Indexes created:")
            for tier, path in result.indexes_created.items():
                print(f"   {tier}: {path}")

        print(f"\n📈 Stage-by-Stage Breakdown:")
        for stage in result.stages:
            print(f"   {stage.stage_name}: {stage.tokens_before:,} → {stage.tokens_after:,} ({stage.reduction_percent}%)")

        # Cost savings
        cost_per_1m = 3.0  # $3 per 1M input tokens
        tokens_saved = result.original_tokens - result.final_tokens
        cost_saved = (tokens_saved / 1_000_000) * cost_per_1m

        print(f"\n💰 Cost Savings:")
        print(f"   Tokens saved: {tokens_saved:,}")
        print(f"   Cost saved per load: ${cost_saved:.3f}")
        print(f"   (Based on $3/M input tokens)")

        print("\n" + "=" * 80)

    def compress_for_handoff(
        self,
        jsonl_path: str,
        handoff_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compress conversation for handoff to new Claude instance.

        Args:
            jsonl_path: Path to conversation file
            handoff_dir: Directory for handoff package (default: ~/.fsl/handoffs/)

        Returns:
            Handoff package metadata
        """
        if handoff_dir is None:
            handoff_dir = Path("~/.fsl/handoffs").expanduser()
        else:
            handoff_dir = Path(handoff_dir)

        handoff_dir.mkdir(parents=True, exist_ok=True)

        # Generate handoff ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        handoff_id = f"handoff_{timestamp}"
        handoff_path = handoff_dir / handoff_id
        handoff_path.mkdir(exist_ok=True)

        # Compress conversation
        result = self.compress_conversation(
            jsonl_path,
            output_dir=str(handoff_path),
            session_id=handoff_id,
            project_id="handoff"
        )

        # Create handoff metadata
        metadata = {
            "handoff_id": handoff_id,
            "timestamp": timestamp,
            "original_file": result.original_path,
            "compressed_file": result.output_path,
            "original_tokens": result.original_tokens,
            "final_tokens": result.final_tokens,
            "reduction_percent": result.total_reduction_percent,
            "compression_level": result.level,
            "indexes": result.indexes_created
        }

        # Write metadata
        metadata_path = handoff_path / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"\n📦 Handoff package created: {handoff_path}")
        print(f"   Metadata: {metadata_path}")

        return metadata


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Unified Token Compression Pipeline"
    )
    parser.add_argument("input", help="Input JSONL conversation file")
    parser.add_argument(
        "--level",
        choices=["minimal", "balanced", "maximum"],
        default="balanced",
        help="Compression level (default: balanced)"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (default: same as input)"
    )
    parser.add_argument(
        "--session-id",
        help="Session ID for hot index"
    )
    parser.add_argument(
        "--project-id",
        help="Project ID for warm index"
    )
    parser.add_argument(
        "--handoff",
        action="store_true",
        help="Create handoff package"
    )

    args = parser.parse_args()

    # Create pipeline
    pipeline = UnifiedCompressionPipeline(level=args.level)

    if args.handoff:
        # Handoff mode
        metadata = pipeline.compress_for_handoff(args.input)
    else:
        # Normal compression
        result = pipeline.compress_conversation(
            args.input,
            output_dir=args.output_dir,
            session_id=args.session_id,
            project_id=args.project_id
        )


if __name__ == "__main__":
    main()
