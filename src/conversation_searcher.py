#!/usr/bin/env python3
"""
Conversation Searcher
High-level API for searching compressed conversations efficiently.

Part of the Unified Token Compression Pipeline - Selective Decompression.
"""

import time
from pathlib import Path
from typing import List, Optional, Dict
from collections import defaultdict

from index_searcher import IndexSearcher
from index_extractor import IndexExtractor
from search_result import SearchResult, SearchMatch


class ConversationSearcher:
    """Search compressed conversations efficiently."""

    def __init__(self, index_dir: str = "~/.claude/indexes"):
        """
        Initialize conversation searcher.

        Args:
            index_dir: Base directory for index files
        """
        self.index_searcher = IndexSearcher(index_dir)
        self.index_extractor = IndexExtractor()
        self.index_dir = Path(index_dir).expanduser()

    def search(
        self,
        query: str,
        files: List[str],
        preview_context: int = 3,
        auto_expand: bool = False,
        case_sensitive: bool = False,
        indexes: Optional[List[str]] = None
    ) -> SearchResult:
        """
        Search compressed conversations for query.

        Args:
            query: Search term to find
            files: List of compressed files to search
            preview_context: Lines of context around matches (default: 3)
            auto_expand: If True, resolve all matches immediately (default: False)
            case_sensitive: Whether to perform case-sensitive search (default: False)
            indexes: Index files to use (default: ["cold", "warm"])

        Returns:
            SearchResult with matches (unexpanded unless auto_expand=True)

        Example:
            >>> searcher = ConversationSearcher()
            >>> result = searcher.search(
            ...     "authentication",
            ...     ["handoff1.slim.indexed", "handoff2.slim.indexed"],
            ...     preview_context=5
            ... )
            >>> print(f"Found {result.total_matches} matches")
        """
        start_time = time.time()

        if indexes is None:
            indexes = ["cold", "warm"]

        all_matches = []
        files_with_matches = 0
        tokens_used = 0
        full_decompress_tokens = 0

        # Step 1: Search indexes for patterns containing query
        index_matches = self.index_searcher.search_indexes(
            query,
            indexes,
            case_sensitive
        )

        # Extract ref IDs from index matches
        matched_ref_ids = [match.ref_id for match in index_matches]

        # Estimate tokens for index search
        tokens_used += len(index_matches) * 100  # ~100 tokens per index pattern

        # Step 2: Search each file
        for file_path in files:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                continue

            # Load compressed content
            with open(file_path_obj, 'r') as f:
                compressed_content = f.read()

            file_tokens = len(compressed_content.split())
            full_decompress_tokens += file_tokens

            # Find matches in this file
            file_matches = self._search_file(
                str(file_path_obj),
                compressed_content,
                query,
                matched_ref_ids,
                preview_context,
                case_sensitive,
                auto_expand,
                indexes
            )

            if file_matches:
                all_matches.extend(file_matches)
                files_with_matches += 1

            # Estimate tokens used (scanning compressed file)
            tokens_used += min(file_tokens // 10, 5000)  # Scanning is cheap

        # Step 3: Calculate final metrics
        search_time_ms = (time.time() - start_time) * 1000

        # Add tokens for expanded matches if auto_expand
        if auto_expand:
            tokens_used += len(all_matches) * preview_context * 20  # ~20 tokens per context line

        return SearchResult(
            query=query,
            total_matches=len(all_matches),
            files_searched=len(files),
            tokens_used=tokens_used,
            matches=all_matches,
            full_decompress_tokens=full_decompress_tokens,
            search_time_ms=search_time_ms,
            indexes_loaded=indexes
        )

    def search_directory(
        self,
        query: str,
        directory: str,
        pattern: str = "*.slim.indexed",
        limit: int = 100,
        preview_context: int = 3,
        auto_expand: bool = False,
        indexes: Optional[List[str]] = None
    ) -> SearchResult:
        """
        Search all compressed files in directory.

        Args:
            query: Search term
            directory: Directory containing compressed files
            pattern: File pattern to match (default: "*.slim.indexed")
            limit: Maximum number of files to search (default: 100)
            preview_context: Lines of context around matches
            auto_expand: Whether to resolve refs immediately
            indexes: Index files to use

        Returns:
            SearchResult with matches from all files

        Example:
            >>> searcher = ConversationSearcher()
            >>> result = searcher.search_directory(
            ...     "error",
            ...     "~/.fsl/handoffs",
            ...     limit=50
            ... )
        """
        dir_path = Path(directory).expanduser()
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        # Find matching files
        files = list(dir_path.glob(pattern))[:limit]
        file_paths = [str(f) for f in files]

        # Perform search
        return self.search(
            query,
            file_paths,
            preview_context,
            auto_expand,
            indexes=indexes
        )

    def preview_file(
        self,
        file_path: str,
        start_line: int = 0,
        end_line: Optional[int] = None,
        num_lines: int = 20,
        resolve_refs: bool = False,
        indexes: Optional[List[str]] = None
    ) -> str:
        """
        Preview a compressed file without full decompression.

        Args:
            file_path: Path to compressed file
            start_line: Starting line (default: 0)
            end_line: Ending line (default: start_line + num_lines)
            num_lines: Number of lines to show if end_line not specified
            resolve_refs: Whether to resolve $refs in preview
            indexes: Index files to use if resolve_refs=True

        Returns:
            Preview content (potentially with refs resolved)

        Example:
            >>> # Preview first 20 lines without resolving
            >>> preview = searcher.preview_file("handoff.slim.indexed")
            >>>
            >>> # Preview lines 50-70 with refs resolved
            >>> preview = searcher.preview_file(
            ...     "handoff.slim.indexed",
            ...     start_line=50,
            ...     end_line=70,
            ...     resolve_refs=True,
            ...     indexes=["cold", "warm"]
            ... )
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path_obj, 'r') as f:
            content = f.read()

        # Determine end_line
        if end_line is None:
            end_line = start_line + num_lines

        # Extract section
        return self.index_extractor.get_section(
            content,
            start_line,
            end_line,
            resolve_refs=resolve_refs,
            indexes=indexes or ["cold", "warm"]
        )

    def _search_file(
        self,
        file_path: str,
        compressed_content: str,
        query: str,
        matched_ref_ids: List[str],
        context_lines: int,
        case_sensitive: bool,
        auto_expand: bool,
        indexes: List[str]
    ) -> List[SearchMatch]:
        """
        Search a single file for matches.

        Returns:
            List of SearchMatch objects
        """
        matches = []

        # Search for direct text matches (not in $refs)
        text_matches = self.index_searcher.find_text_in_content(
            compressed_content,
            query,
            case_sensitive,
            include_refs=False
        )

        # Find where matched $refs appear
        ref_locations = self.index_searcher.find_refs_in_content(
            compressed_content,
            matched_ref_ids
        )

        # Process text matches
        for text_match in text_matches:
            match = self._create_match_from_line(
                file_path,
                compressed_content,
                text_match['line_number'],
                None,  # No ref_id for direct text match
                context_lines,
                auto_expand,
                indexes
            )
            matches.append(match)

        # Process ref matches
        for ref_id, line_nums in ref_locations.items():
            for line_num in line_nums:
                match = self._create_match_from_line(
                    file_path,
                    compressed_content,
                    line_num,
                    ref_id,
                    context_lines,
                    auto_expand,
                    indexes
                )
                matches.append(match)

        return matches

    def _create_match_from_line(
        self,
        file_path: str,
        content: str,
        line_num: int,
        ref_id: Optional[str],
        context_lines: int,
        resolve: bool,
        indexes: List[str]
    ) -> SearchMatch:
        """
        Create a SearchMatch from a line number.

        Args:
            file_path: Path to file
            content: Compressed content
            line_num: Line number of match
            ref_id: Ref ID if match is in a $ref
            context_lines: Number of context lines
            resolve: Whether to resolve refs
            indexes: Index files to use

        Returns:
            SearchMatch object
        """
        lines = content.split('\n')
        total_lines = len(lines)

        # Extract context
        start = max(0, line_num - context_lines)
        end = min(total_lines, line_num + context_lines + 1)

        context_before = '\n'.join(lines[start:line_num]) if line_num > start else ""
        match_text = lines[line_num] if line_num < total_lines else ""
        context_after = '\n'.join(lines[line_num + 1:end]) if line_num + 1 < end else ""

        # Optionally resolve refs
        resolved = False
        if resolve:
            # Get section and resolve
            section = self.index_extractor.get_section(
                content,
                start,
                end,
                resolve_refs=True,
                indexes=indexes
            )
            section_lines = section.split('\n')
            offset = line_num - start

            if offset < len(section_lines):
                context_before = '\n'.join(section_lines[:offset]) if offset > 0 else ""
                match_text = section_lines[offset]
                context_after = '\n'.join(section_lines[offset + 1:]) if offset + 1 < len(section_lines) else ""
                resolved = True

        return SearchMatch(
            file_path=file_path,
            line_number=line_num,
            ref_id=ref_id,
            match_text=match_text,
            context_before=context_before,
            context_after=context_after,
            resolved=resolved
        )


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Search compressed conversations"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search compressed files")
    search_parser.add_argument("query", help="Search term")
    search_parser.add_argument(
        "--files",
        nargs="+",
        help="Files to search"
    )
    search_parser.add_argument(
        "--directory",
        help="Directory to search"
    )
    search_parser.add_argument(
        "--pattern",
        default="*.slim.indexed",
        help="File pattern (default: *.slim.indexed)"
    )
    search_parser.add_argument(
        "--context",
        type=int,
        default=3,
        help="Context lines (default: 3)"
    )
    search_parser.add_argument(
        "--expand",
        action="store_true",
        help="Auto-expand matches"
    )
    search_parser.add_argument(
        "--indexes",
        nargs="+",
        default=["cold", "warm"],
        help="Index files to use"
    )

    # Preview command
    preview_parser = subparsers.add_parser("preview", help="Preview compressed file")
    preview_parser.add_argument("file", help="File to preview")
    preview_parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start line (default: 0)"
    )
    preview_parser.add_argument(
        "--lines",
        type=int,
        default=20,
        help="Number of lines (default: 20)"
    )
    preview_parser.add_argument(
        "--resolve",
        action="store_true",
        help="Resolve $refs"
    )

    args = parser.parse_args()

    searcher = ConversationSearcher()

    if args.command == "search":
        if args.directory:
            result = searcher.search_directory(
                args.query,
                args.directory,
                pattern=args.pattern,
                preview_context=args.context,
                auto_expand=args.expand,
                indexes=args.indexes
            )
        elif args.files:
            result = searcher.search(
                args.query,
                args.files,
                preview_context=args.context,
                auto_expand=args.expand,
                indexes=args.indexes
            )
        else:
            print("Error: Must specify --files or --directory")
            return

        print(result)

    elif args.command == "preview":
        preview = searcher.preview_file(
            args.file,
            start_line=args.start,
            num_lines=args.lines,
            resolve_refs=args.resolve
        )
        print(preview)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
