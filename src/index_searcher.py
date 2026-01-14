#!/usr/bin/env python3
"""
Index Searcher
Search compressed content via indexes without full decompression.

Part of the Unified Token Compression Pipeline - Selective Decompression.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Set
from collections import defaultdict

from search_result import IndexMatch


class IndexSearcher:
    """Search compressed content via indexes."""

    def __init__(self, index_dir: str = "~/.claude/indexes"):
        """
        Initialize index searcher.

        Args:
            index_dir: Base directory for index files
        """
        self.index_dir = Path(index_dir).expanduser()

    def search_indexes(
        self,
        query: str,
        index_files: List[str],
        case_sensitive: bool = False
    ) -> List[IndexMatch]:
        """
        Search indexes for query term.

        Args:
            query: Search term to find in index patterns
            index_files: List of index file paths or tier names
            case_sensitive: Whether to perform case-sensitive search

        Returns:
            List of IndexMatch objects for patterns containing the query

        Example:
            >>> searcher = IndexSearcher()
            >>> matches = searcher.search_indexes(
            ...     "authentication",
            ...     ["cold", "warm"]
            ... )
        """
        matches = []
        search_query = query if case_sensitive else query.lower()

        for index_ref in index_files:
            index_path = self._resolve_index_path(index_ref)
            if not index_path or not index_path.exists():
                continue

            # Load and search index
            with open(index_path, 'r') as f:
                index_data = json.load(f)

            tier = index_data.get("tier", "unknown")

            for ref_id, pattern_data in index_data.get("patterns", {}).items():
                # Convert content to searchable string
                content_str = self._pattern_to_string(pattern_data["content"])
                search_content = content_str if case_sensitive else content_str.lower()

                # Check if query appears in content
                if search_query in search_content:
                    # Find position of match
                    match_pos = search_content.find(search_query)

                    # Extract hash from ref_id (format: "$tier#hash")
                    pattern_hash = ref_id.split('#')[1] if '#' in ref_id else ref_id

                    # Create preview (200 chars around match if possible)
                    preview_start = max(0, match_pos - 50)
                    preview_end = min(len(content_str), match_pos + 150)
                    preview = content_str[preview_start:preview_end]

                    matches.append(IndexMatch(
                        pattern_hash=pattern_hash,
                        tier=tier,
                        ref_id=ref_id,
                        category=pattern_data.get("category", "unknown"),
                        content_preview=preview,
                        occurrences=pattern_data.get("occurrences", 1),
                        size_bytes=pattern_data.get("size_bytes", len(content_str)),
                        match_position=match_pos
                    ))

        return matches

    def find_refs_in_content(
        self,
        compressed_content: str,
        ref_hashes: List[str]
    ) -> Dict[str, List[int]]:
        """
        Find line numbers where specific $refs appear.

        Args:
            compressed_content: Compressed content with $refs
            ref_hashes: List of ref IDs to find (e.g., ["$cold#abc123", "$warm#def456"])

        Returns:
            Dictionary mapping ref_hash to list of line numbers where it appears

        Example:
            >>> searcher.find_refs_in_content(
            ...     content,
            ...     ["$cold#abc123", "$warm#def456"]
            ... )
            {'$cold#abc123': [10, 45, 67], '$warm#def456': [123]}
        """
        ref_locations = defaultdict(list)
        lines = compressed_content.split('\n')

        # Build regex pattern for all refs
        # Refs appear as quoted strings: "$tier#hash"
        for line_num, line in enumerate(lines):
            for ref_hash in ref_hashes:
                # Check if this ref appears in the line
                if f'"{ref_hash}"' in line or f"'{ref_hash}'" in line:
                    ref_locations[ref_hash].append(line_num)

        return dict(ref_locations)

    def find_text_in_content(
        self,
        compressed_content: str,
        query: str,
        case_sensitive: bool = False,
        include_refs: bool = True
    ) -> List[Dict]:
        """
        Find direct text matches in compressed content.

        Args:
            compressed_content: Compressed content (may contain $refs)
            query: Search term
            case_sensitive: Whether to perform case-sensitive search
            include_refs: Whether to search inside $ref strings

        Returns:
            List of match dictionaries with line_number and line_content

        Example:
            >>> searcher.find_text_in_content(content, "error")
            [{'line_number': 42, 'line_content': 'Found error in system'}]
        """
        matches = []
        lines = compressed_content.split('\n')
        search_query = query if case_sensitive else query.lower()

        for line_num, line in enumerate(lines):
            # Skip lines that are only $refs if include_refs is False
            if not include_refs and self._is_ref_line(line):
                continue

            search_line = line if case_sensitive else line.lower()

            if search_query in search_line:
                matches.append({
                    'line_number': line_num,
                    'line_content': line,
                    'column': search_line.find(search_query)
                })

        return matches

    def _pattern_to_string(self, content: any) -> str:
        """
        Convert pattern content to searchable string.

        Args:
            content: Pattern content (can be dict, list, str, etc.)

        Returns:
            String representation for searching
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            # Convert dict to readable string
            # Include both keys and values
            parts = []
            for key, value in content.items():
                parts.append(str(key))
                parts.append(self._pattern_to_string(value))
            return ' '.join(parts)
        elif isinstance(content, list):
            return ' '.join(self._pattern_to_string(item) for item in content)
        else:
            return str(content)

    def _is_ref_line(self, line: str) -> bool:
        """
        Check if a line contains only a $ref reference.

        Args:
            line: Line of content

        Returns:
            True if line is just a $ref, False otherwise
        """
        # Pattern for ref: "$tier#hash" (quoted)
        ref_pattern = r'^\s*["\']?\$\w+#[a-f0-9]+["\']?\s*$'
        return bool(re.match(ref_pattern, line))

    def _resolve_index_path(self, index_ref: str) -> Optional[Path]:
        """
        Resolve index reference to file path.

        Args:
            index_ref: Index reference (file path or tier name)

        Returns:
            Path to index file or None if not found
        """
        # Check if it's already a path
        path = Path(index_ref)
        if path.exists():
            return path

        # Try to resolve from index_dir
        if index_ref == "cold" or index_ref == "global":
            return self.index_dir / "global_cold.json"
        elif index_ref.startswith("session_") or index_ref.endswith("_hot"):
            session_file = f"{index_ref}.json" if not index_ref.endswith('.json') else index_ref
            return self.index_dir / "sessions" / session_file
        elif index_ref.endswith("_warm"):
            project_file = f"{index_ref}.json" if not index_ref.endswith('.json') else index_ref
            return self.index_dir / "projects" / project_file

        return None

    def get_available_indexes(self) -> Dict[str, List[str]]:
        """
        Get list of available index files.

        Returns:
            Dictionary with tier names as keys and list of index files
        """
        available = {
            "hot": [],
            "warm": [],
            "cold": []
        }

        # Check for cold index
        cold_path = self.index_dir / "global_cold.json"
        if cold_path.exists():
            available["cold"].append(str(cold_path))

        # Check for hot indexes
        sessions_dir = self.index_dir / "sessions"
        if sessions_dir.exists():
            for hot_file in sessions_dir.glob("*_hot.json"):
                available["hot"].append(str(hot_file))

        # Check for warm indexes
        projects_dir = self.index_dir / "projects"
        if projects_dir.exists():
            for warm_file in projects_dir.glob("*_warm.json"):
                available["warm"].append(str(warm_file))

        return available

    def load_index_metadata(self, index_file: str) -> Dict:
        """
        Load metadata from an index file without loading all patterns.

        Args:
            index_file: Path to index file or tier name

        Returns:
            Dictionary with metadata (tier, tier_id, pattern_count)
        """
        index_path = self._resolve_index_path(index_file)
        if not index_path or not index_path.exists():
            return {}

        with open(index_path, 'r') as f:
            index_data = json.load(f)

        return {
            "version": index_data.get("version", "unknown"),
            "tier": index_data.get("tier", "unknown"),
            "tier_id": index_data.get("tier_id", "unknown"),
            "pattern_count": len(index_data.get("patterns", {})),
            "file_path": str(index_path)
        }


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Search compressed conversations via indexes"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search indexes command
    search_parser = subparsers.add_parser("search", help="Search index patterns")
    search_parser.add_argument("query", help="Search term")
    search_parser.add_argument(
        "--indexes",
        nargs="+",
        default=["cold", "warm"],
        help="Index files to search (default: cold warm)"
    )
    search_parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Case-sensitive search"
    )

    # Find refs command
    find_parser = subparsers.add_parser("find-refs", help="Find $refs in content")
    find_parser.add_argument("content_file", help="Compressed content file")
    find_parser.add_argument("refs", nargs="+", help="Ref IDs to find")

    # List indexes command
    list_parser = subparsers.add_parser("list", help="List available indexes")

    args = parser.parse_args()

    searcher = IndexSearcher()

    if args.command == "search":
        matches = searcher.search_indexes(
            args.query,
            args.indexes,
            args.case_sensitive
        )

        print(f"\nFound {len(matches)} matches for '{args.query}':\n")
        for i, match in enumerate(matches):
            print(f"[{i}] {match}")
            print()

    elif args.command == "find-refs":
        with open(args.content_file, 'r') as f:
            content = f.read()

        locations = searcher.find_refs_in_content(content, args.refs)

        print(f"\nRef locations in {args.content_file}:\n")
        for ref_id, line_nums in locations.items():
            print(f"{ref_id}: lines {line_nums}")

    elif args.command == "list":
        available = searcher.get_available_indexes()

        print("\nAvailable indexes:\n")
        for tier, files in available.items():
            print(f"{tier.upper()}:")
            if files:
                for f in files:
                    metadata = searcher.load_index_metadata(f)
                    print(f"  - {f}")
                    print(f"    Patterns: {metadata.get('pattern_count', 0)}")
            else:
                print("  (none)")
            print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
