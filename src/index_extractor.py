#!/usr/bin/env python3
"""
Index Extractor
Extract repeated patterns from compressed conversations and store in index files.

Part of the Unified Token Compression Pipeline.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from index_analyzer import IndexAnalyzer


@dataclass
class IndexPattern:
    """A pattern extracted to an index."""
    hash: str
    content: Any
    category: str
    occurrences: int
    size_bytes: int
    tier: str  # "hot", "warm", or "cold"


@dataclass
class ExtractionResult:
    """Result of pattern extraction."""
    content_with_refs: str
    hot_index: Dict[str, Any]
    warm_index: Dict[str, Any]
    cold_index: Dict[str, Any]
    original_size: int
    compressed_size: int
    reduction_percent: float
    patterns_extracted: int


class IndexExtractor:
    """Extract repeated patterns to hot/warm/cold index files."""

    def __init__(self):
        self.analyzer = IndexAnalyzer()

    def extract_patterns(
        self,
        content: str,
        threshold: int = 3,
        output_dir: Optional[str] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract repeated patterns from content and create index files.

        Args:
            content: SLIM-formatted content or JSONL
            threshold: Minimum occurrences for extraction (default: 3)
            output_dir: Directory for index files (default: ~/.claude/indexes/)
            session_id: Session identifier for hot index
            project_id: Project identifier for warm index

        Returns:
            ExtractionResult with content and indexes
        """
        # Parse content to find patterns
        patterns = self._analyze_content(content, threshold)

        # Classify patterns into hot/warm/cold
        classified = self._classify_patterns(patterns)

        # Build indexes
        hot_index = self._build_index(classified["hot"], "hot", session_id)
        warm_index = self._build_index(classified["warm"], "warm", project_id)
        cold_index = self._build_index(classified["cold"], "cold", None)

        # Rewrite content with references
        content_with_refs = self._rewrite_with_refs(
            content,
            classified,
            hot_index,
            warm_index,
            cold_index
        )

        # Calculate metrics
        original_size = len(content.encode('utf-8'))
        compressed_size = len(content_with_refs.encode('utf-8'))
        reduction = round((1 - compressed_size / original_size) * 100, 1) if original_size > 0 else 0

        # Write indexes to files if output_dir specified
        if output_dir:
            self._write_indexes(output_dir, hot_index, warm_index, cold_index, session_id, project_id)

        return ExtractionResult(
            content_with_refs=content_with_refs,
            hot_index=hot_index,
            warm_index=warm_index,
            cold_index=cold_index,
            original_size=original_size,
            compressed_size=compressed_size,
            reduction_percent=reduction,
            patterns_extracted=len(classified["hot"]) + len(classified["warm"]) + len(classified["cold"])
        )

    def _analyze_content(self, content: str, threshold: int) -> List[IndexPattern]:
        """Analyze content to find repeated patterns."""
        patterns = []

        try:
            # Try parsing as JSON lines
            lines = []
            for line in content.split('\n'):
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        lines.append(obj)
                    except json.JSONDecodeError:
                        # Not JSONL, might be SLIM or other format
                        pass

            if lines:
                # JSONL content - analyze objects
                patterns = self._analyze_jsonl(lines, threshold)
            else:
                # SLIM or other format - analyze as text patterns
                patterns = self._analyze_text(content, threshold)

        except Exception as e:
            print(f"Warning: Analysis error: {e}")
            # Fall back to text analysis
            patterns = self._analyze_text(content, threshold)

        return patterns

    def _analyze_jsonl(self, lines: List[Dict], threshold: int) -> List[IndexPattern]:
        """Analyze JSONL objects for patterns."""
        patterns = []
        pattern_counts = defaultdict(list)

        # Find all objects
        for line_num, obj in enumerate(lines):
            self._extract_objects(obj, pattern_counts, line_num)

        # Filter by threshold
        for obj_hash, occurrences in pattern_counts.items():
            if len(occurrences) >= threshold:
                # Get first occurrence for content
                first_line, content, category = occurrences[0]
                serialized = json.dumps(content, separators=(',', ':'))

                patterns.append(IndexPattern(
                    hash=obj_hash,
                    content=content,
                    category=category,
                    occurrences=len(occurrences),
                    size_bytes=len(serialized.encode('utf-8')),
                    tier=""  # Will be classified later
                ))

        return patterns

    def _extract_objects(self, obj: Any, pattern_counts: Dict, line_num: int, category: str = ""):
        """Recursively extract objects from data structure."""
        if isinstance(obj, dict) and obj:
            # Hash this dict
            obj_hash = self._hash_object(obj)
            size = len(json.dumps(obj, separators=(',', ':')).encode('utf-8'))

            # Only track significant objects (>50 bytes)
            if size > 50:
                cat = category or self._categorize_object(obj)
                pattern_counts[obj_hash].append((line_num, obj, cat))

            # Recurse
            for key, value in obj.items():
                self._extract_objects(value, pattern_counts, line_num, category)

        elif isinstance(obj, list):
            for item in obj:
                self._extract_objects(item, pattern_counts, line_num, category)

    def _analyze_text(self, content: str, threshold: int) -> List[IndexPattern]:
        """Analyze text for repeated patterns."""
        patterns = []
        # Look for repeated multi-line sections or large repeated strings

        # Simple approach: find repeated substrings >100 chars
        pattern_counts = defaultdict(int)
        content_list = content.split('\n')

        # Look for repeated lines
        for line in content_list:
            if len(line) > 100:
                pattern_counts[line] += 1

        # Filter by threshold
        for pattern, count in pattern_counts.items():
            if count >= threshold:
                patterns.append(IndexPattern(
                    hash=self._hash_string(pattern),
                    content=pattern,
                    category="text_block",
                    occurrences=count,
                    size_bytes=len(pattern.encode('utf-8')),
                    tier=""
                ))

        return patterns

    def _hash_object(self, obj: Any) -> str:
        """Create stable hash of object."""
        serialized = json.dumps(obj, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:12]

    def _hash_string(self, s: str) -> str:
        """Create stable hash of string."""
        return hashlib.sha256(s.encode('utf-8')).hexdigest()[:12]

    def _categorize_object(self, obj: Dict) -> str:
        """Categorize an object."""
        if "name" in obj and "parameters" in obj:
            return "tool_definition"
        elif "role" in obj:
            role = obj.get("role")
            if role == "system":
                return "system_message"
            return f"{role}_message"
        elif "type" in obj:
            return f"{obj.get('type')}_block"
        elif "$schema" in obj:
            return "json_schema"
        return "generic_object"

    def _classify_patterns(self, patterns: List[IndexPattern]) -> Dict[str, List[IndexPattern]]:
        """Classify patterns into hot/warm/cold tiers."""
        classified = {
            "hot": [],
            "warm": [],
            "cold": []
        }

        for pattern in patterns:
            # Classification logic:
            # Hot: High frequency in this session (5+ occurrences)
            # Cold: Universal patterns (tools, system messages, schemas)
            # Warm: Everything else

            if pattern.category in ["tool_definition", "json_schema", "system_message"]:
                pattern.tier = "cold"
                classified["cold"].append(pattern)
            elif pattern.occurrences >= 5:
                pattern.tier = "hot"
                classified["hot"].append(pattern)
            else:
                pattern.tier = "warm"
                classified["warm"].append(pattern)

        return classified

    def _build_index(self, patterns: List[IndexPattern], tier: str, tier_id: Optional[str]) -> Dict[str, Any]:
        """Build index dictionary from patterns."""
        index = {
            "version": "1.0",
            "tier": tier,
            "tier_id": tier_id or "global",
            "patterns": {}
        }

        for pattern in patterns:
            ref_id = f"{tier}#{pattern.hash}"
            index["patterns"][ref_id] = {
                "content": pattern.content,
                "category": pattern.category,
                "occurrences": pattern.occurrences,
                "size_bytes": pattern.size_bytes
            }

        return index

    def _rewrite_with_refs(
        self,
        content: str,
        classified: Dict[str, List[IndexPattern]],
        hot_index: Dict,
        warm_index: Dict,
        cold_index: Dict
    ) -> str:
        """Rewrite content replacing patterns with $ref references."""
        result = content

        # Build lookup from content to ref
        content_to_ref = {}

        for tier, patterns in classified.items():
            for pattern in patterns:
                ref_id = f"${tier}#{pattern.hash}"
                serialized = json.dumps(pattern.content, separators=(',', ':'))
                content_to_ref[serialized] = ref_id

        # Replace patterns in content
        # This is a simple string replacement approach
        # More sophisticated: parse JSON and replace at object level
        for pattern_str, ref_id in content_to_ref.items():
            result = result.replace(pattern_str, f'"{ref_id}"')

        return result

    def _write_indexes(
        self,
        output_dir: str,
        hot_index: Dict,
        warm_index: Dict,
        cold_index: Dict,
        session_id: Optional[str],
        project_id: Optional[str]
    ):
        """Write index files to disk."""
        base_dir = Path(output_dir).expanduser()
        base_dir.mkdir(parents=True, exist_ok=True)

        # Write hot index (session-specific)
        if session_id and hot_index["patterns"]:
            hot_dir = base_dir / "sessions"
            hot_dir.mkdir(exist_ok=True)
            hot_path = hot_dir / f"{session_id}_hot.json"
            with open(hot_path, 'w') as f:
                json.dump(hot_index, f, indent=2)
            print(f"✅ Hot index: {hot_path}")

        # Write warm index (project-specific)
        if project_id and warm_index["patterns"]:
            warm_dir = base_dir / "projects"
            warm_dir.mkdir(exist_ok=True)
            warm_path = warm_dir / f"{project_id}_warm.json"
            with open(warm_path, 'w') as f:
                json.dump(warm_index, f, indent=2)
            print(f"✅ Warm index: {warm_path}")

        # Write cold index (global)
        if cold_index["patterns"]:
            cold_path = base_dir / "global_cold.json"

            # If global index exists, merge patterns
            if cold_path.exists():
                with open(cold_path, 'r') as f:
                    existing = json.load(f)
                    existing["patterns"].update(cold_index["patterns"])
                    cold_index = existing

            with open(cold_path, 'w') as f:
                json.dump(cold_index, f, indent=2)
            print(f"✅ Cold index: {cold_path}")

    def resolve_references(
        self,
        compressed: str,
        indexes: List[str],
        index_dir: Optional[str] = None
    ) -> str:
        """
        Resolve $ref references back to original content.

        Args:
            compressed: Content with $ref references
            indexes: List of index file paths or tier names
            index_dir: Base directory for indexes (default: ~/.claude/indexes/)

        Returns:
            Decompressed content with references resolved
        """
        base_dir = Path(index_dir or "~/.claude/indexes").expanduser()

        # Load all indexes
        all_patterns = {}
        for index_ref in indexes:
            index_path = self._resolve_index_path(index_ref, base_dir)
            if index_path and index_path.exists():
                with open(index_path, 'r') as f:
                    index_data = json.load(f)
                    all_patterns.update(index_data["patterns"])

        # Replace references with content
        result = compressed
        for ref_id, pattern_data in all_patterns.items():
            # References in format: "$tier#hash"
            ref_str = f'"{ref_id}"'
            content_str = json.dumps(pattern_data["content"], separators=(',', ':'))
            result = result.replace(ref_str, content_str)

        return result

    def _resolve_index_path(self, index_ref: str, base_dir: Path) -> Optional[Path]:
        """Resolve index reference to file path."""
        if Path(index_ref).exists():
            # Direct file path
            return Path(index_ref)

        # Try to resolve from base_dir
        if index_ref == "cold" or index_ref == "global":
            return base_dir / "global_cold.json"
        elif index_ref.startswith("session_") or index_ref.endswith("_hot"):
            return base_dir / "sessions" / f"{index_ref}.json"
        elif index_ref.endswith("_warm"):
            return base_dir / "projects" / f"{index_ref}.json"

        return None


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract repeated patterns to index files"
    )
    parser.add_argument("input", help="Input file (JSONL or SLIM)")
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Minimum occurrences for extraction (default: 3)"
    )
    parser.add_argument(
        "--output-dir",
        default="~/.claude/indexes",
        help="Output directory for indexes"
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
        "--decompress",
        action="store_true",
        help="Decompress (resolve references)"
    )
    parser.add_argument(
        "--indexes",
        nargs="+",
        help="Index files to use for decompression"
    )

    args = parser.parse_args()

    extractor = IndexExtractor()

    if args.decompress:
        # Decompress mode
        with open(args.input, 'r') as f:
            compressed = f.read()

        decompressed = extractor.resolve_references(
            compressed,
            args.indexes or [],
            args.output_dir
        )

        print(decompressed)

    else:
        # Compress mode
        with open(args.input, 'r') as f:
            content = f.read()

        result = extractor.extract_patterns(
            content,
            threshold=args.threshold,
            output_dir=args.output_dir,
            session_id=args.session_id,
            project_id=args.project_id
        )

        print()
        print("=" * 80)
        print("📦 INDEX EXTRACTION COMPLETE")
        print("=" * 80)
        print(f"Original size: {result.original_size:,} bytes")
        print(f"Compressed size: {result.compressed_size:,} bytes")
        print(f"Reduction: {result.reduction_percent}%")
        print(f"Patterns extracted: {result.patterns_extracted}")
        print()
        print(f"Hot patterns: {len(result.hot_index['patterns'])}")
        print(f"Warm patterns: {len(result.warm_index['patterns'])}")
        print(f"Cold patterns: {len(result.cold_index['patterns'])}")
        print("=" * 80)

        # Write compressed output
        output_path = Path(args.input).with_suffix('.indexed')
        with open(output_path, 'w') as f:
            f.write(result.content_with_refs)
        print(f"\n✅ Compressed output: {output_path}")


if __name__ == "__main__":
    main()
