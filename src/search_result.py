#!/usr/bin/env python3
"""
Search Result Data Classes
Define data structures for search results in compressed conversations.

Part of the Unified Token Compression Pipeline - Selective Decompression.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class SearchMatch:
    """A single search match in compressed content."""

    file_path: str
    """Path to the file containing the match"""

    line_number: int
    """Line number where match occurs (0-indexed)"""

    ref_id: Optional[str] = None
    """If match is in a $ref pattern, the ref ID (e.g., "$cold#abc123")"""

    match_text: str = ""
    """The text that matched the search query"""

    context_before: str = ""
    """Lines before the match for context"""

    context_after: str = ""
    """Lines after the match for context"""

    resolved: bool = False
    """Whether $refs in this match have been resolved"""

    category: Optional[str] = None
    """Pattern category if match is in an index pattern"""

    def __str__(self) -> str:
        """String representation of match."""
        result = f"Match in {self.file_path}:{self.line_number}\n"
        if self.ref_id:
            result += f"  Ref: {self.ref_id}\n"
        if self.category:
            result += f"  Category: {self.category}\n"
        result += f"  Resolved: {self.resolved}\n"
        if self.context_before:
            result += f"  Context before:\n{self.context_before}\n"
        result += f"  >>> {self.match_text}\n"
        if self.context_after:
            result += f"  Context after:\n{self.context_after}\n"
        return result


@dataclass
class SearchResult:
    """Result from searching compressed conversations."""

    query: str
    """The search query string"""

    total_matches: int
    """Total number of matches found"""

    files_searched: int
    """Number of files searched"""

    tokens_used: int
    """Tokens used for search (not full content decompression)"""

    matches: List[SearchMatch] = field(default_factory=list)
    """List of search matches"""

    full_decompress_tokens: Optional[int] = None
    """Estimated tokens if fully decompressed (for comparison)"""

    search_time_ms: Optional[float] = None
    """Time taken for search in milliseconds"""

    indexes_loaded: List[str] = field(default_factory=list)
    """Index files that were loaded for this search"""

    @property
    def tokens_saved(self) -> int:
        """Calculate tokens saved vs full decompression."""
        if self.full_decompress_tokens:
            return self.full_decompress_tokens - self.tokens_used
        return 0

    @property
    def savings_percent(self) -> float:
        """Calculate percentage of tokens saved."""
        if self.full_decompress_tokens and self.full_decompress_tokens > 0:
            return round((1 - self.tokens_used / self.full_decompress_tokens) * 100, 1)
        return 0.0

    def expand_match(
        self,
        match_index: int,
        indexes: List[str],
        extractor: Optional[Any] = None,
        context_lines: int = 10
    ) -> SearchMatch:
        """
        Resolve refs for a specific match and expand context.

        Args:
            match_index: Index of match to expand
            indexes: Index files to use for resolution
            extractor: IndexExtractor instance (will create if not provided)
            context_lines: Number of additional context lines to add

        Returns:
            Expanded SearchMatch with resolved references
        """
        if match_index < 0 or match_index >= len(self.matches):
            raise IndexError(f"Match index {match_index} out of range")

        match = self.matches[match_index]

        # If already resolved, return as-is
        if match.resolved:
            return match

        # Load file content
        file_path = Path(match.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'r') as f:
            compressed_content = f.read()

        # Get extractor if not provided
        if extractor is None:
            from index_extractor import IndexExtractor
            extractor = IndexExtractor()

        # Get expanded section
        start_line = max(0, match.line_number - context_lines)
        end_line = match.line_number + context_lines + 1

        expanded_content = extractor.get_section(
            compressed_content,
            start_line,
            end_line,
            resolve_refs=True,
            indexes=indexes
        )

        # Split into before/match/after
        expanded_lines = expanded_content.split('\n')
        mid_index = min(context_lines, match.line_number)

        # Create expanded match
        expanded_match = SearchMatch(
            file_path=match.file_path,
            line_number=match.line_number,
            ref_id=match.ref_id,
            match_text=expanded_lines[mid_index] if mid_index < len(expanded_lines) else match.match_text,
            context_before='\n'.join(expanded_lines[:mid_index]) if mid_index > 0 else "",
            context_after='\n'.join(expanded_lines[mid_index+1:]) if mid_index < len(expanded_lines)-1 else "",
            resolved=True,
            category=match.category
        )

        # Update the match in our list
        self.matches[match_index] = expanded_match

        return expanded_match

    def __str__(self) -> str:
        """String representation of search result."""
        result = f"Search Results for '{self.query}'\n"
        result += "=" * 60 + "\n"
        result += f"Total matches: {self.total_matches}\n"
        result += f"Files searched: {self.files_searched}\n"
        result += f"Tokens used: {self.tokens_used:,}\n"

        if self.full_decompress_tokens:
            result += f"Full decompress tokens: {self.full_decompress_tokens:,}\n"
            result += f"Tokens saved: {self.tokens_saved:,} ({self.savings_percent}%)\n"

        if self.search_time_ms:
            result += f"Search time: {self.search_time_ms:.1f}ms\n"

        result += "\n"

        for i, match in enumerate(self.matches):
            result += f"\n[{i}] " + str(match)

        return result


@dataclass
class IndexMatch:
    """A match found in an index pattern."""

    pattern_hash: str
    """Hash of the pattern (e.g., "abc123" from "$cold#abc123")"""

    tier: str
    """Tier of the pattern (hot/warm/cold)"""

    ref_id: str
    """Full reference ID (e.g., "$cold#abc123")"""

    category: str
    """Pattern category (e.g., "tool_definition", "system_message")"""

    content_preview: str
    """Preview of pattern content (first 200 chars)"""

    occurrences: int
    """Number of times this pattern occurs"""

    size_bytes: int
    """Size of the pattern in bytes"""

    match_position: Optional[int] = None
    """Position within content where match was found"""

    def __str__(self) -> str:
        """String representation."""
        preview = self.content_preview[:100] + "..." if len(self.content_preview) > 100 else self.content_preview
        return (f"IndexMatch({self.ref_id}, category={self.category}, "
                f"occurrences={self.occurrences}, preview='{preview}')")
