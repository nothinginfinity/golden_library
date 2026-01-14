#!/usr/bin/env python3
"""
Search Compressed Conversation Library

Search across all your compressed Claude Code conversations with
95%+ token savings compared to loading all conversations.

Usage:
    python3 scripts/search_library.py "authentication"
    python3 scripts/search_library.py "bug fix" --project myapp
    python3 scripts/search_library.py "error handling" --limit 5
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from conversation_searcher import ConversationSearcher
from search_result import SearchResult


class LibrarySearcher:
    """Search across compressed conversation library."""

    def __init__(self, library_dir: str = "~/.claude/conversation_library"):
        self.library_dir = Path(library_dir).expanduser()
        self.index_file = self.library_dir / "index.json"
        self.compressed_dir = self.library_dir / "compressed"
        self.searcher = ConversationSearcher()

    def load_index(self) -> Dict:
        """Load library index."""
        if not self.index_file.exists():
            raise FileNotFoundError(
                f"Library index not found at {self.index_file}\n"
                f"Run: python3 scripts/compress_all_conversations.py"
            )

        with open(self.index_file, 'r') as f:
            return json.load(f)

    def search(
        self,
        query: str,
        project: str = None,
        session: str = None,
        limit: int = 20,
        context: int = 5
    ) -> SearchResult:
        """
        Search across all compressed conversations.

        Args:
            query: Search term
            project: Filter by project_id
            session: Filter by session_id
            limit: Max conversations to search
            context: Lines of context around matches

        Returns:
            SearchResult with matches across all conversations
        """
        # Load index
        index = self.load_index()

        # Filter conversations
        conversations = index['conversations']

        if project:
            conversations = [c for c in conversations if c['project_id'] == project]

        if session:
            conversations = [c for c in conversations if c['session_id'] == session]

        # Limit
        conversations = conversations[:limit]

        if not conversations:
            print(f"No conversations found matching filters")
            return None

        # Get compressed files
        files = [c['compressed_file'] for c in conversations]

        print(f"🔍 Searching {len(files)} compressed conversations for '{query}'...")
        print(f"   (This would cost {len(files) * 200000:,} tokens if fully decompressed)")
        print()

        # Search
        result = self.searcher.search(
            query,
            files,
            preview_context=context,
            auto_expand=False
        )

        return result, conversations

    def display_results(
        self,
        result: SearchResult,
        conversations: List[Dict],
        detailed: bool = False
    ):
        """Display search results."""
        if result.total_matches == 0:
            print(f"❌ No matches found for '{result.query}'")
            return

        # Map files to conversation metadata
        file_to_meta = {c['compressed_file']: c for c in conversations}

        print("="*60)
        print(f"Search Results: '{result.query}'")
        print("="*60)
        print()
        print(f"📊 Summary:")
        print(f"  Matches found: {result.total_matches}")
        print(f"  Conversations searched: {result.files_searched}")
        print(f"  Tokens used: {result.tokens_used:,}")
        print(f"  Tokens saved: {result.tokens_saved:,} ({result.savings_percent}%)")
        print()

        # Group matches by file
        matches_by_file = {}
        for match in result.matches:
            if match.file_path not in matches_by_file:
                matches_by_file[match.file_path] = []
            matches_by_file[match.file_path].append(match)

        # Display by conversation
        print("🎯 Matches by Conversation:")
        print()

        for file_path, matches in matches_by_file.items():
            meta = file_to_meta.get(file_path, {})

            print(f"📄 {meta.get('title', Path(file_path).stem)}")
            print(f"   File: {Path(file_path).name}")
            print(f"   Project: {meta.get('project_id', 'unknown')}")
            print(f"   Tokens: {meta.get('original_tokens', 0):,} → {meta.get('compressed_tokens', 0):,} ({meta.get('reduction_percent', 0)}% reduction)")
            print(f"   Matches: {len(matches)}")
            print()

            if detailed:
                for i, match in enumerate(matches[:3]):  # Show first 3
                    print(f"   [{i+1}] Line {match.line_number}")
                    if match.context_before:
                        print(f"       {match.context_before[:80]}")
                    print(f"       >>> {match.match_text[:100]}")
                    if match.context_after:
                        print(f"       {match.context_after[:80]}")
                    print()

                if len(matches) > 3:
                    print(f"   ... and {len(matches) - 3} more matches")
                    print()

        print("="*60)
        print()
        print("💡 Next steps:")
        print(f"  1. View full conversation: cat {list(matches_by_file.keys())[0]}")
        print(f"  2. Expand specific match: use search_cli.py expand")
        print(f"  3. Refine search: add --project or --session filter")

    def list_projects(self):
        """List all projects in library."""
        index = self.load_index()

        projects = {}
        for conv in index['conversations']:
            project = conv['project_id']
            if project not in projects:
                projects[project] = {
                    'count': 0,
                    'total_tokens': 0,
                    'compressed_tokens': 0
                }
            projects[project]['count'] += 1
            projects[project]['total_tokens'] += conv['original_tokens']
            projects[project]['compressed_tokens'] += conv['compressed_tokens']

        print("\n📁 Projects in Library")
        print("="*60)
        print()

        for project, stats in sorted(projects.items()):
            reduction = ((stats['total_tokens'] - stats['compressed_tokens']) / stats['total_tokens'] * 100)
            print(f"• {project}")
            print(f"  Conversations: {stats['count']}")
            print(f"  Tokens: {stats['total_tokens']:,} → {stats['compressed_tokens']:,} ({reduction:.1f}% reduction)")
            print()

    def recent(self, limit: int = 10):
        """Show recent conversations."""
        index = self.load_index()

        # Sort by compressed_at
        conversations = sorted(
            index['conversations'],
            key=lambda c: c.get('compressed_at', ''),
            reverse=True
        )[:limit]

        print(f"\n📅 Recent Conversations (last {limit})")
        print("="*60)
        print()

        for i, conv in enumerate(conversations, 1):
            print(f"{i}. {conv['title'][:60]}")
            print(f"   Project: {conv['project_id']} | Tokens: {conv['compressed_tokens']:,}")
            print(f"   File: {Path(conv['compressed_file']).name}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Search compressed conversation library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for authentication
  python3 scripts/search_library.py "authentication"

  # Search specific project
  python3 scripts/search_library.py "bug fix" --project myapp

  # Detailed results
  python3 scripts/search_library.py "error" --detailed

  # List projects
  python3 scripts/search_library.py --list-projects

  # Show recent conversations
  python3 scripts/search_library.py --recent
        """
    )

    parser.add_argument(
        "query",
        nargs="?",
        help="Search query"
    )
    parser.add_argument(
        "--project",
        help="Filter by project"
    )
    parser.add_argument(
        "--session",
        help="Filter by session"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max conversations to search (default: 20)"
    )
    parser.add_argument(
        "--context",
        type=int,
        default=5,
        help="Context lines around matches (default: 5)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed match context"
    )
    parser.add_argument(
        "--list-projects",
        action="store_true",
        help="List all projects"
    )
    parser.add_argument(
        "--recent",
        type=int,
        nargs="?",
        const=10,
        help="Show recent conversations"
    )
    parser.add_argument(
        "--library-dir",
        default="~/.claude/conversation_library",
        help="Library directory"
    )

    args = parser.parse_args()

    searcher = LibrarySearcher(args.library_dir)

    try:
        if args.list_projects:
            searcher.list_projects()
        elif args.recent is not None:
            searcher.recent(args.recent)
        elif args.query:
            result, conversations = searcher.search(
                args.query,
                project=args.project,
                session=args.session,
                limit=args.limit,
                context=args.context
            )
            searcher.display_results(result, conversations, args.detailed)
        else:
            parser.print_help()

    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
