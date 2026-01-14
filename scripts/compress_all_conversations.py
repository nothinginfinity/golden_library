#!/usr/bin/env python3
"""
Compress All Claude Code Conversations

Finds all Claude Code conversation files, compresses them with the
golden_library pipeline, and builds a searchable index.

Usage:
    python3 scripts/compress_all_conversations.py
    python3 scripts/compress_all_conversations.py --session-dir ~/custom/sessions
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unified_pipeline import UnifiedCompressionPipeline
from conversation_searcher import ConversationSearcher


class ConversationLibrary:
    """Build and manage a library of compressed conversations."""

    def __init__(self, library_dir: str = "~/.claude/conversation_library"):
        self.library_dir = Path(library_dir).expanduser()
        self.library_dir.mkdir(parents=True, exist_ok=True)

        self.compressed_dir = self.library_dir / "compressed"
        self.compressed_dir.mkdir(exist_ok=True)

        self.index_file = self.library_dir / "index.json"
        self.pipeline = UnifiedCompressionPipeline()

    def find_conversations(self, session_dir: str = None) -> List[Path]:
        """
        Find all Claude Code conversation files.

        Claude Code stores conversations in various formats:
        - ~/.config/Claude Code/conversations/*.json
        - ~/.cache/claude-code/sessions/*.jsonl
        - Working directory session files
        """
        conversations = []

        # Common locations
        search_paths = []

        if session_dir:
            search_paths.append(Path(session_dir).expanduser())
        else:
            # Default search locations
            search_paths.extend([
                Path("~/.config/Claude Code/conversations").expanduser(),
                Path("~/.cache/claude-code/sessions").expanduser(),
                Path("~/.claude/sessions").expanduser(),
                Path.cwd(),  # Current directory
            ])

        for path in search_paths:
            if path.exists():
                # Find .json and .jsonl files
                conversations.extend(path.glob("*.json"))
                conversations.extend(path.glob("*.jsonl"))
                conversations.extend(path.glob("**/*.json"))
                conversations.extend(path.glob("**/*.jsonl"))

        # Deduplicate
        conversations = list(set(conversations))

        # Filter out non-conversation files
        valid_conversations = []
        for conv_file in conversations:
            if self._is_conversation_file(conv_file):
                valid_conversations.append(conv_file)

        return valid_conversations

    def _is_conversation_file(self, file_path: Path) -> bool:
        """Check if file is a valid conversation."""
        try:
            with open(file_path, 'r') as f:
                # Try to parse first line
                first_line = f.readline()
                if not first_line.strip():
                    return False

                # Check if it's JSON
                data = json.loads(first_line)

                # Heuristic: has 'role' or 'messages' field
                if isinstance(data, dict):
                    if 'role' in data or 'messages' in data or 'content' in data:
                        return True

                return False
        except (json.JSONDecodeError, Exception):
            return False

    def compress_conversation(
        self,
        conv_file: Path,
        session_id: str = None,
        project_id: str = None
    ) -> Dict[str, Any]:
        """
        Compress a single conversation.

        Returns metadata about the compressed conversation.
        """
        print(f"\n📦 Compressing: {conv_file.name}")

        # Read conversation
        with open(conv_file, 'r') as f:
            content = f.read()

        # Generate session/project IDs if not provided
        if not session_id:
            session_id = f"session_{conv_file.stem}"
        if not project_id:
            # Try to infer from path
            project_id = conv_file.parent.name if conv_file.parent.name != "conversations" else "general"

        # Compress
        try:
            result = self.pipeline.compress(
                content,
                level="balanced",
                session_id=session_id,
                project_id=project_id
            )

            # Save compressed output
            output_file = self.compressed_dir / f"{conv_file.stem}.slim.indexed"
            with open(output_file, 'w') as f:
                f.write(result.compressed_content)

            # Extract title/summary (first user message)
            title = self._extract_title(content)

            metadata = {
                "original_file": str(conv_file),
                "compressed_file": str(output_file),
                "title": title,
                "original_tokens": result.original_tokens,
                "compressed_tokens": result.final_tokens,
                "reduction_percent": result.total_reduction,
                "session_id": session_id,
                "project_id": project_id,
                "compressed_at": datetime.now().isoformat(),
                "indexes": {
                    "hot": f"{session_id}_hot.json",
                    "warm": f"{project_id}_warm.json",
                    "cold": "global_cold.json"
                }
            }

            print(f"  ✅ {result.original_tokens:,} → {result.final_tokens:,} tokens ({result.total_reduction}% reduction)")
            print(f"  📄 Saved to: {output_file.name}")

            return metadata

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None

    def _extract_title(self, content: str) -> str:
        """Extract conversation title from first user message."""
        try:
            lines = content.split('\n')
            for line in lines:
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    if isinstance(msg, dict) and msg.get('role') == 'user':
                        content_text = msg.get('content', '')
                        # Take first 100 chars
                        return content_text[:100].strip()
                except:
                    continue
            return "Untitled conversation"
        except:
            return "Untitled conversation"

    def build_index(self, conversations_metadata: List[Dict]) -> None:
        """Build searchable index of all conversations."""
        index = {
            "library_version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_conversations": len(conversations_metadata),
            "conversations": conversations_metadata
        }

        with open(self.index_file, 'w') as f:
            json.dump(index, f, indent=2)

        print(f"\n📚 Index built: {self.index_file}")
        print(f"   Total conversations: {len(conversations_metadata)}")

    def compress_all(self, session_dir: str = None) -> None:
        """Compress all conversations and build index."""
        print("🔍 Finding conversations...")

        conversations = self.find_conversations(session_dir)

        if not conversations:
            print("❌ No conversations found!")
            print("\nSearched in:")
            print("  - ~/.config/Claude Code/conversations/")
            print("  - ~/.cache/claude-code/sessions/")
            print("  - ~/.claude/sessions/")
            print("  - Current directory")
            return

        print(f"✅ Found {len(conversations)} conversation files")

        # Compress each
        metadata_list = []
        success_count = 0

        for conv_file in conversations:
            metadata = self.compress_conversation(conv_file)
            if metadata:
                metadata_list.append(metadata)
                success_count += 1

        # Build index
        if metadata_list:
            self.build_index(metadata_list)

            print(f"\n{'='*60}")
            print(f"✅ COMPRESSION COMPLETE")
            print(f"{'='*60}")
            print(f"Conversations compressed: {success_count}/{len(conversations)}")
            print(f"Library location: {self.library_dir}")
            print(f"\nNext steps:")
            print(f"  1. Search: python3 scripts/search_library.py 'your query'")
            print(f"  2. View index: cat {self.index_file}")
            print(f"  3. Browse compressed: ls {self.compressed_dir}")

    def get_stats(self) -> Dict:
        """Get library statistics."""
        if not self.index_file.exists():
            return {"error": "No index found. Run compress_all first."}

        with open(self.index_file, 'r') as f:
            index = json.load(f)

        total_original = sum(c['original_tokens'] for c in index['conversations'])
        total_compressed = sum(c['compressed_tokens'] for c in index['conversations'])
        avg_reduction = sum(c['reduction_percent'] for c in index['conversations']) / len(index['conversations'])

        return {
            "total_conversations": index['total_conversations'],
            "total_original_tokens": total_original,
            "total_compressed_tokens": total_compressed,
            "total_tokens_saved": total_original - total_compressed,
            "average_reduction": round(avg_reduction, 1),
            "library_dir": str(self.library_dir),
            "created_at": index['created_at']
        }


def main():
    parser = argparse.ArgumentParser(
        description="Compress all Claude Code conversations"
    )
    parser.add_argument(
        "--session-dir",
        help="Directory containing conversation files"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show library statistics"
    )
    parser.add_argument(
        "--library-dir",
        default="~/.claude/conversation_library",
        help="Library directory (default: ~/.claude/conversation_library)"
    )

    args = parser.parse_args()

    library = ConversationLibrary(args.library_dir)

    if args.stats:
        stats = library.get_stats()
        print("\n📊 Library Statistics")
        print("="*60)
        for key, value in stats.items():
            print(f"{key}: {value}")
    else:
        library.compress_all(args.session_dir)


if __name__ == "__main__":
    main()
