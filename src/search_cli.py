#!/usr/bin/env python3
"""
Search CLI
Command-line interface for searching compressed conversations.

Part of the Unified Token Compression Pipeline - Selective Decompression.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from conversation_searcher import ConversationSearcher
from search_result import SearchResult


class SearchCLI:
    """CLI for searching compressed conversations."""

    def __init__(self, index_dir: str = "~/.claude/indexes"):
        self.searcher = ConversationSearcher(index_dir)

    def search(self, args) -> Optional[SearchResult]:
        """Execute search command."""
        print(f"🔍 Searching for '{args.query}'...")
        print()

        try:
            if args.directory:
                result = self.searcher.search_directory(
                    args.query,
                    args.directory,
                    pattern=args.pattern,
                    limit=args.limit,
                    preview_context=args.context,
                    auto_expand=args.expand,
                    indexes=args.indexes
                )
            elif args.files:
                result = self.searcher.search(
                    args.query,
                    args.files,
                    preview_context=args.context,
                    auto_expand=args.expand,
                    indexes=args.indexes
                )
            else:
                print("❌ Error: Must specify --files or --directory")
                return None

            # Display results
            self._display_result(result, args.format)

            # Optionally save to file
            if args.output:
                self._save_result(result, args.output)
                print(f"\n✅ Results saved to {args.output}")

            return result

        except Exception as e:
            print(f"❌ Error during search: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return None

    def expand(self, args):
        """Expand a saved search result."""
        try:
            # Load saved result
            with open(args.result_file, 'r') as f:
                data = json.load(f)

            result = self._deserialize_result(data)

            if args.match < 0 or args.match >= len(result.matches):
                print(f"❌ Error: Match index {args.match} out of range (0-{len(result.matches)-1})")
                return

            print(f"🔍 Expanding match #{args.match}...")
            print()

            # Expand the match
            expanded = result.expand_match(
                args.match,
                args.indexes
            )

            # Display expanded match
            print("=" * 60)
            print(f"Match #{args.match} (Expanded)")
            print("=" * 60)
            print(expanded)

            # Update saved file if requested
            if args.save:
                data['matches'][args.match] = self._serialize_match(expanded)
                with open(args.result_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"\n✅ Updated {args.result_file}")

        except FileNotFoundError:
            print(f"❌ Error: Result file not found: {args.result_file}")
        except Exception as e:
            print(f"❌ Error expanding match: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    def preview(self, args):
        """Preview a compressed file."""
        try:
            print(f"📄 Previewing {args.file}...")
            print()

            preview = self.searcher.preview_file(
                args.file,
                start_line=args.start,
                num_lines=args.lines,
                resolve_refs=args.resolve,
                indexes=args.indexes
            )

            print("=" * 60)
            print(f"Lines {args.start}-{args.start + args.lines}")
            if args.resolve:
                print("(with $refs resolved)")
            print("=" * 60)
            print(preview)

        except FileNotFoundError:
            print(f"❌ Error: File not found: {args.file}")
        except Exception as e:
            print(f"❌ Error previewing file: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    def list_indexes(self, args):
        """List available index files."""
        available = self.searcher.index_searcher.get_available_indexes()

        print("📚 Available Indexes")
        print("=" * 60)
        print()

        for tier in ["cold", "warm", "hot"]:
            files = available.get(tier, [])
            print(f"{tier.upper()} Tier:")
            if files:
                for file_path in files:
                    metadata = self.searcher.index_searcher.load_index_metadata(file_path)
                    print(f"  • {Path(file_path).name}")
                    print(f"    Patterns: {metadata.get('pattern_count', 0):,}")
                    print(f"    Tier ID: {metadata.get('tier_id', 'unknown')}")
                    print()
            else:
                print("  (none)")
                print()

    def _display_result(self, result: SearchResult, format: str):
        """Display search result in specified format."""
        if format == "json":
            print(json.dumps(self._serialize_result(result), indent=2))
            return

        # Default: human-readable format
        print("=" * 60)
        print(f"Search Results: '{result.query}'")
        print("=" * 60)
        print()
        print(f"📊 Summary:")
        print(f"  Total matches: {result.total_matches}")
        print(f"  Files searched: {result.files_searched}")
        print(f"  Tokens used: {result.tokens_used:,}")

        if result.full_decompress_tokens:
            print(f"  Full decompress: {result.full_decompress_tokens:,} tokens")
            print(f"  Tokens saved: {result.tokens_saved:,} ({result.savings_percent}%)")

        if result.search_time_ms:
            print(f"  Search time: {result.search_time_ms:.1f}ms")

        print()

        # Display matches
        if result.matches:
            print(f"🎯 Matches:")
            print()
            for i, match in enumerate(result.matches[:20]):  # Limit to first 20
                print(f"[{i}] {Path(match.file_path).name}:{match.line_number}")
                if match.ref_id:
                    print(f"    Ref: {match.ref_id}")
                if match.context_before:
                    for line in match.context_before.split('\n')[-2:]:  # Last 2 lines
                        print(f"        {line}")
                print(f"    >>> {match.match_text}")
                if match.context_after:
                    for line in match.context_after.split('\n')[:2]:  # First 2 lines
                        print(f"        {line}")
                print()

            if len(result.matches) > 20:
                print(f"... and {len(result.matches) - 20} more matches")
                print()

        print("=" * 60)

    def _serialize_result(self, result: SearchResult) -> dict:
        """Serialize SearchResult to JSON-compatible dict."""
        return {
            "query": result.query,
            "total_matches": result.total_matches,
            "files_searched": result.files_searched,
            "tokens_used": result.tokens_used,
            "full_decompress_tokens": result.full_decompress_tokens,
            "search_time_ms": result.search_time_ms,
            "indexes_loaded": result.indexes_loaded,
            "matches": [self._serialize_match(m) for m in result.matches]
        }

    def _serialize_match(self, match) -> dict:
        """Serialize SearchMatch to JSON-compatible dict."""
        return {
            "file_path": match.file_path,
            "line_number": match.line_number,
            "ref_id": match.ref_id,
            "match_text": match.match_text,
            "context_before": match.context_before,
            "context_after": match.context_after,
            "resolved": match.resolved,
            "category": match.category
        }

    def _deserialize_result(self, data: dict) -> SearchResult:
        """Deserialize SearchResult from JSON dict."""
        from search_result import SearchMatch

        matches = []
        for m_data in data.get("matches", []):
            matches.append(SearchMatch(
                file_path=m_data["file_path"],
                line_number=m_data["line_number"],
                ref_id=m_data.get("ref_id"),
                match_text=m_data["match_text"],
                context_before=m_data.get("context_before", ""),
                context_after=m_data.get("context_after", ""),
                resolved=m_data.get("resolved", False),
                category=m_data.get("category")
            ))

        return SearchResult(
            query=data["query"],
            total_matches=data["total_matches"],
            files_searched=data["files_searched"],
            tokens_used=data["tokens_used"],
            matches=matches,
            full_decompress_tokens=data.get("full_decompress_tokens"),
            search_time_ms=data.get("search_time_ms"),
            indexes_loaded=data.get("indexes_loaded", [])
        )

    def _save_result(self, result: SearchResult, output_file: str):
        """Save result to JSON file."""
        with open(output_file, 'w') as f:
            json.dump(self._serialize_result(result), f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Search compressed conversations efficiently",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for "authentication" in a directory
  %(prog)s search "authentication" --directory ~/.fsl/handoffs

  # Search specific files with more context
  %(prog)s search "error" --files file1.slim.indexed file2.slim.indexed --context 10

  # Save results for later
  %(prog)s search "bug" --directory ~/conversations --output results.json

  # Expand a specific match
  %(prog)s expand results.json --match 0

  # Preview a file
  %(prog)s preview handoff.slim.indexed --start 50 --lines 30 --resolve
        """
    )

    parser.add_argument(
        "--index-dir",
        default="~/.claude/indexes",
        help="Index directory (default: ~/.claude/indexes)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search command
    search_parser = subparsers.add_parser(
        "search",
        help="Search compressed conversations"
    )
    search_parser.add_argument("query", help="Search term")
    search_parser.add_argument(
        "--files",
        nargs="+",
        help="Specific files to search"
    )
    search_parser.add_argument(
        "--directory",
        help="Directory containing compressed files"
    )
    search_parser.add_argument(
        "--pattern",
        default="*.slim.indexed",
        help="File pattern for directory search (default: *.slim.indexed)"
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum files to search (default: 100)"
    )
    search_parser.add_argument(
        "--context",
        type=int,
        default=3,
        help="Context lines around matches (default: 3)"
    )
    search_parser.add_argument(
        "--expand",
        action="store_true",
        help="Auto-expand all matches (resolve refs immediately)"
    )
    search_parser.add_argument(
        "--indexes",
        nargs="+",
        default=["cold", "warm"],
        help="Index files to use (default: cold warm)"
    )
    search_parser.add_argument(
        "--output",
        help="Save results to JSON file"
    )
    search_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )

    # Expand command
    expand_parser = subparsers.add_parser(
        "expand",
        help="Expand a match from saved results"
    )
    expand_parser.add_argument(
        "result_file",
        help="JSON file with saved search results"
    )
    expand_parser.add_argument(
        "--match",
        type=int,
        required=True,
        help="Match index to expand"
    )
    expand_parser.add_argument(
        "--indexes",
        nargs="+",
        default=["cold", "warm"],
        help="Index files to use (default: cold warm)"
    )
    expand_parser.add_argument(
        "--save",
        action="store_true",
        help="Update the result file with expanded match"
    )

    # Preview command
    preview_parser = subparsers.add_parser(
        "preview",
        help="Preview compressed file without full decompression"
    )
    preview_parser.add_argument("file", help="Compressed file to preview")
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
        help="Number of lines to show (default: 20)"
    )
    preview_parser.add_argument(
        "--resolve",
        action="store_true",
        help="Resolve $refs in preview"
    )
    preview_parser.add_argument(
        "--indexes",
        nargs="+",
        default=["cold", "warm"],
        help="Index files to use if --resolve (default: cold warm)"
    )

    # List indexes command
    list_parser = subparsers.add_parser(
        "list-indexes",
        help="List available index files"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = SearchCLI(args.index_dir)

    if args.command == "search":
        cli.search(args)
    elif args.command == "expand":
        cli.expand(args)
    elif args.command == "preview":
        cli.preview(args)
    elif args.command == "list-indexes":
        cli.list_indexes(args)


if __name__ == "__main__":
    main()
