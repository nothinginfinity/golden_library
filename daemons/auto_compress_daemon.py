#!/usr/bin/env python3
"""
Auto-Compress Daemon for Claude Code Conversations

Background daemon that automatically:
1. Watches Claude Code session directory
2. Compresses conversations when they update
3. Stores in golden_library
4. Updates searchable index
5. Zero manual intervention required

Runs continuously like phi_inbox_daemon.

Usage:
    python3 daemons/auto_compress_daemon.py

    # Run in background
    nohup python3 daemons/auto_compress_daemon.py > /tmp/auto_compress.log 2>&1 &

Integration:
    # Add to phi_proxy startup
    # Or add to launchd/systemd for auto-start
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unified_pipeline import UnifiedCompressionPipeline


class ConversationWatcher(FileSystemEventHandler):
    """Watch Claude Code sessions and auto-compress."""

    def __init__(
        self,
        session_dir: str,
        library_dir: str = "~/.claude/conversation_library",
        min_interval_seconds: int = 30
    ):
        """
        Initialize watcher.

        Args:
            session_dir: Claude Code session directory
            library_dir: Output library directory
            min_interval_seconds: Min time between compressions of same file
        """
        self.session_dir = Path(session_dir).expanduser()
        self.library_dir = Path(library_dir).expanduser()
        self.compressed_dir = self.library_dir / "compressed"
        self.index_file = self.library_dir / "index.json"

        # Create directories
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self.compressed_dir.mkdir(exist_ok=True)

        # Track last compression time per file
        self.last_compressed: Dict[str, float] = {}
        self.min_interval = min_interval_seconds

        # Track file hashes to avoid recompressing unchanged files
        self.file_hashes: Dict[str, str] = {}

        # Compression pipeline
        self.pipeline = UnifiedCompressionPipeline()

        # Load existing index
        self.index = self._load_index()

        print(f"🤖 Auto-Compress Daemon Started", flush=True)
        print(f"   Watching: {self.session_dir}", flush=True)
        print(f"   Library: {self.library_dir}", flush=True)
        print(f"   Min interval: {self.min_interval}s", flush=True)
        print(flush=True)

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process .json and .jsonl files
        if file_path.suffix not in ['.json', '.jsonl']:
            return

        # Check if it's a conversation file
        if not self._is_conversation_file(file_path):
            return

        # Check if enough time has passed since last compression
        if not self._should_compress(file_path):
            return

        # Compress the conversation
        self._compress_conversation(file_path)

    def on_created(self, event):
        """Handle file creation events."""
        # Wait a bit for file to be fully written
        time.sleep(2)
        self.on_modified(event)

    def _should_compress(self, file_path: Path) -> bool:
        """Check if file should be compressed."""
        file_key = str(file_path)

        # Check interval
        last_time = self.last_compressed.get(file_key, 0)
        if time.time() - last_time < self.min_interval:
            return False

        # Check if file content changed
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                current_hash = hashlib.md5(content).hexdigest()

            previous_hash = self.file_hashes.get(file_key)
            if previous_hash == current_hash:
                # Content unchanged
                return False

            self.file_hashes[file_key] = current_hash
            return True

        except Exception as e:
            print(f"⚠️  Error checking {file_path.name}: {e}", flush=True)
            return False

    def _is_conversation_file(self, file_path: Path) -> bool:
        """Check if file is a valid conversation."""
        try:
            with open(file_path, 'r') as f:
                first_line = f.readline()
                if not first_line.strip():
                    return False

                data = json.loads(first_line)

                # Heuristic: has conversation-like structure
                if isinstance(data, dict):
                    if 'role' in data or 'messages' in data or 'content' in data:
                        return True

                return False
        except:
            return False

    def _compress_conversation(self, file_path: Path):
        """Compress a conversation file."""
        try:
            print(f"📦 Compressing: {file_path.name}", flush=True)

            # Read conversation
            with open(file_path, 'r') as f:
                content = f.read()

            # Generate IDs
            session_id = f"session_{file_path.stem}"
            project_id = self._infer_project(file_path)

            # Compress
            result = self.pipeline.compress(
                content,
                level="balanced",
                session_id=session_id,
                project_id=project_id
            )

            # Save compressed output
            output_file = self.compressed_dir / f"{file_path.stem}.slim.indexed"
            with open(output_file, 'w') as f:
                f.write(result.compressed_content)

            # Extract title
            title = self._extract_title(content)

            # Create metadata
            metadata = {
                "original_file": str(file_path),
                "compressed_file": str(output_file),
                "title": title,
                "original_tokens": result.original_tokens,
                "compressed_tokens": result.final_tokens,
                "reduction_percent": result.total_reduction,
                "session_id": session_id,
                "project_id": project_id,
                "compressed_at": datetime.now().isoformat(),
                "auto_compressed": True,
                "indexes": {
                    "hot": f"{session_id}_hot.json",
                    "warm": f"{project_id}_warm.json",
                    "cold": "global_cold.json"
                }
            }

            # Update index
            self._update_index(metadata)

            # Mark as compressed
            self.last_compressed[str(file_path)] = time.time()

            print(f"   ✅ {result.original_tokens:,} → {result.final_tokens:,} tokens ({result.total_reduction}% reduction)", flush=True)
            print(f"   💾 Saved to: {output_file.name}", flush=True)
            print(flush=True)

        except Exception as e:
            print(f"   ❌ Error: {e}", flush=True)
            print(flush=True)

    def _infer_project(self, file_path: Path) -> str:
        """Infer project from file path or name."""
        # Check if path contains project indicators
        parts = file_path.parts

        # Common project indicators
        for part in parts:
            if part in ['myapp', 'webapp', 'api', 'frontend', 'backend']:
                return part

        # Check filename for project hints
        name_lower = file_path.stem.lower()
        if 'auth' in name_lower:
            return 'authentication'
        elif 'ui' in name_lower or 'frontend' in name_lower:
            return 'frontend'
        elif 'api' in name_lower or 'backend' in name_lower:
            return 'backend'
        elif 'test' in name_lower:
            return 'testing'
        elif 'debug' in name_lower or 'bug' in name_lower:
            return 'debugging'

        return 'general'

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

    def _load_index(self) -> Dict:
        """Load existing index."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except:
                pass

        return {
            "library_version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_conversations": 0,
            "conversations": []
        }

    def _update_index(self, metadata: Dict):
        """Update index with new conversation."""
        # Check if conversation already in index
        existing_idx = None
        for i, conv in enumerate(self.index['conversations']):
            if conv['original_file'] == metadata['original_file']:
                existing_idx = i
                break

        if existing_idx is not None:
            # Update existing
            self.index['conversations'][existing_idx] = metadata
        else:
            # Add new
            self.index['conversations'].append(metadata)

        self.index['total_conversations'] = len(self.index['conversations'])
        self.index['last_updated'] = datetime.now().isoformat()

        # Save index
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)

    def get_stats(self) -> Dict:
        """Get compression statistics."""
        total_original = sum(c['original_tokens'] for c in self.index['conversations'])
        total_compressed = sum(c['compressed_tokens'] for c in self.index['conversations'])

        return {
            "total_conversations": self.index['total_conversations'],
            "total_original_tokens": total_original,
            "total_compressed_tokens": total_compressed,
            "tokens_saved": total_original - total_compressed,
            "average_reduction": round(
                sum(c['reduction_percent'] for c in self.index['conversations']) /
                max(1, self.index['total_conversations']),
                1
            )
        }


def main():
    """Run the auto-compress daemon."""
    # Configuration
    CLAUDE_SESSION_DIR = "~/Library/Application Support/Claude/claude-code-sessions"
    LIBRARY_DIR = "~/.claude/conversation_library"
    MIN_INTERVAL = 30  # seconds between compressions of same file

    # Create watcher
    watcher = ConversationWatcher(
        session_dir=CLAUDE_SESSION_DIR,
        library_dir=LIBRARY_DIR,
        min_interval_seconds=MIN_INTERVAL
    )

    # Set up file system observer
    observer = Observer()
    observer.schedule(
        watcher,
        str(watcher.session_dir),
        recursive=True
    )
    observer.start()

    print("👀 Watching for conversation updates...", flush=True)
    print("   Press Ctrl+C to stop", flush=True)
    print(flush=True)

    try:
        while True:
            time.sleep(60)  # Print stats every minute

            stats = watcher.get_stats()
            if stats['total_conversations'] > 0:
                print(f"📊 Stats: {stats['total_conversations']} conversations, "
                      f"{stats['tokens_saved']:,} tokens saved "
                      f"({stats['average_reduction']}% avg reduction)", flush=True)

    except KeyboardInterrupt:
        print("\n🛑 Stopping daemon...", flush=True)
        observer.stop()

    observer.join()
    print("✅ Daemon stopped", flush=True)


if __name__ == "__main__":
    main()
