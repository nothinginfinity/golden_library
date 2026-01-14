#!/usr/bin/env python3
"""
Universal Watcher for Claude Storage Locations

Comprehensive compression daemon that watches all 15+ Claude storage locations
with priority-based compression strategies.

Architecture: See UNIVERSAL_WATCHER_ARCHITECTURE.md

Usage:
    python3 daemons/universal_watcher.py

    # Run in background
    nohup python3 daemons/universal_watcher.py > /tmp/universal_watcher.log 2>&1 &
"""

import os
import sys
import json
import time
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from queue import PriorityQueue, Empty
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unified_pipeline import UnifiedCompressionPipeline


@dataclass
class LocationConfig:
    """Configuration for a watched location."""
    id: str
    path: str
    enabled: bool = True
    priority: int = 1  # 1=critical, 2=high, 3=medium, 4=low
    strategy: str = "real-time-incremental"
    recursive: bool = False
    extensions: List[str] = None
    patterns: List[str] = None
    min_size_bytes: int = 100
    max_size_bytes: int = 10485760  # 10 MB
    min_interval_seconds: int = 30
    min_age_hours: float = 0
    output_directory: str = None
    output_format: str = "slim.indexed"
    compression_level: str = "balanced"

    def __post_init__(self):
        if self.extensions is None:
            self.extensions = [".jsonl", ".json"]
        if self.patterns is None:
            self.patterns = ["*"]
        if self.output_directory is None:
            self.output_directory = f"~/.claude/conversation_library/compressed/{self.id}"


@dataclass
class CompressionTask:
    """A compression task to be processed."""
    priority: int
    timestamp: float
    location_id: str
    file_path: Path
    config: LocationConfig

    def __lt__(self, other):
        """Compare by priority (lower number = higher priority)."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class LocationWatcher(FileSystemEventHandler):
    """Watches a single location and queues compression tasks."""

    def __init__(
        self,
        config: LocationConfig,
        queue: PriorityQueue,
        stats_tracker: 'StatsTracker'
    ):
        self.config = config
        self.queue = queue
        self.stats_tracker = stats_tracker
        self.last_processed: Dict[str, float] = {}
        self.file_hashes: Dict[str, str] = {}

    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return
        self._process_file(Path(event.src_path))

    def on_created(self, event):
        """Handle file creation."""
        if event.is_directory:
            return
        # Wait briefly for file to be fully written
        time.sleep(0.5)
        self._process_file(Path(event.src_path))

    def _process_file(self, file_path: Path):
        """Process a file if it matches filters."""
        # Check if file matches filters
        if not self._matches_filters(file_path):
            return

        # Check if file should be processed now
        if not self._should_process(file_path):
            return

        # Queue compression task
        task = CompressionTask(
            priority=self.config.priority,
            timestamp=time.time(),
            location_id=self.config.id,
            file_path=file_path,
            config=self.config
        )
        self.queue.put(task)
        self.stats_tracker.increment_queued(self.config.id)

    def _matches_filters(self, file_path: Path) -> bool:
        """Check if file matches configured filters."""
        # Check extension
        if file_path.suffix not in self.config.extensions:
            return False

        # Check size limits
        try:
            size = file_path.stat().st_size
            if size < self.config.min_size_bytes:
                return False
            if size > self.config.max_size_bytes:
                return False
        except:
            return False

        # Check age (for batch strategies)
        if self.config.min_age_hours > 0:
            try:
                age_hours = (time.time() - file_path.stat().st_mtime) / 3600
                if age_hours < self.config.min_age_hours:
                    return False
            except:
                return False

        return True

    def _should_process(self, file_path: Path) -> bool:
        """Check if file should be processed now."""
        file_key = str(file_path)

        # Check interval
        last_time = self.last_processed.get(file_key, 0)
        if time.time() - last_time < self.config.min_interval_seconds:
            return False

        # Check if content changed
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                current_hash = hashlib.md5(content).hexdigest()

            previous_hash = self.file_hashes.get(file_key)
            if previous_hash == current_hash:
                return False

            self.file_hashes[file_key] = current_hash
            self.last_processed[file_key] = time.time()
            return True

        except Exception as e:
            print(f"⚠️  Error checking {file_path.name}: {e}", flush=True)
            return False


class StatsTracker:
    """Tracks compression statistics per location."""

    def __init__(self, stats_file: Optional[Path] = None):
        self.stats = {}
        self.lock = threading.Lock()
        self.stats_file = stats_file or Path.home() / ".claude" / "conversation_library" / "stats" / "location_stats.json"
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)

    def init_location(self, location_id: str):
        """Initialize stats for a location."""
        with self.lock:
            if location_id not in self.stats:
                self.stats[location_id] = {
                    "queued": 0,
                    "processed": 0,
                    "failed": 0,
                    "original_tokens": 0,
                    "compressed_tokens": 0,
                    "bytes_saved": 0,
                    "last_compression": None
                }

    def increment_queued(self, location_id: str):
        """Increment queued count."""
        with self.lock:
            self.stats[location_id]["queued"] += 1

    def record_compression(
        self,
        location_id: str,
        original_tokens: int,
        compressed_tokens: int,
        bytes_saved: int
    ):
        """Record a successful compression."""
        with self.lock:
            stats = self.stats[location_id]
            stats["queued"] = max(0, stats["queued"] - 1)
            stats["processed"] += 1
            stats["original_tokens"] += original_tokens
            stats["compressed_tokens"] += compressed_tokens
            stats["bytes_saved"] += bytes_saved
            stats["last_compression"] = datetime.now().isoformat()
            self._save_to_disk()

    def record_failure(self, location_id: str):
        """Record a failed compression."""
        with self.lock:
            stats = self.stats[location_id]
            stats["queued"] = max(0, stats["queued"] - 1)
            stats["failed"] += 1

    def get_stats(self, location_id: Optional[str] = None) -> Dict:
        """Get stats for a location or all locations."""
        with self.lock:
            if location_id:
                return self.stats.get(location_id, {})
            return dict(self.stats)

    def _save_to_disk(self):
        """Save stats to disk (called with lock held)."""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"⚠️  Error saving stats: {e}", flush=True)


class UniversalWatcher:
    """Watches all configured Claude storage locations."""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize universal watcher.

        Args:
            config_file: Path to location config JSON file
        """
        self.config_file = config_file or self._default_config_path()
        self.configs = self._load_configs()
        self.queue = PriorityQueue()
        self.stats_tracker = StatsTracker()
        self.observers = {}
        self.watchers = {}
        self.running = False
        self.compression_thread = None
        self.batch_threads = {}

        # Initialize compression pipeline
        self.pipeline = UnifiedCompressionPipeline()

        # Initialize stats for all locations
        for config in self.configs:
            self.stats_tracker.init_location(config.id)

        print(f"🌍 Universal Watcher Initialized", flush=True)
        print(f"   Watching: {len(self.configs)} locations", flush=True)
        print(flush=True)

    def _default_config_path(self) -> str:
        """Get default config file path."""
        return str(Path.home() / ".claude" / "universal_watcher_config.json")

    def _load_configs(self) -> List[LocationConfig]:
        """Load location configurations."""
        config_path = Path(self.config_file).expanduser()

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    return [LocationConfig(**loc) for loc in data.get("locations", [])]
            except Exception as e:
                print(f"⚠️  Error loading config: {e}", flush=True)

        # Return default configs
        return self._default_configs()

    def _default_configs(self) -> List[LocationConfig]:
        """Get default location configurations."""
        return [
            # Priority 1: Critical (Real-time)
            LocationConfig(
                id="history",
                path="~/.claude/history.jsonl",
                priority=1,
                strategy="real-time-incremental",
                extensions=[".jsonl"],
                min_interval_seconds=30
            ),
            LocationConfig(
                id="projects",
                path="~/.claude/projects",
                priority=1,
                strategy="real-time-incremental",
                recursive=True,
                extensions=[".jsonl", ".json"],
                patterns=["agent-*.jsonl", "*.jsonl"],
                min_interval_seconds=30
            ),
            # Priority 2: High (Hourly)
            LocationConfig(
                id="todos",
                path="~/.claude/todos",
                priority=2,
                strategy="batch-hourly",
                recursive=False,
                extensions=[".json", ".jsonl"],
                min_age_hours=1
            ),
            LocationConfig(
                id="plans",
                path="~/.claude/plans",
                priority=2,
                strategy="batch-hourly",
                recursive=False,
                extensions=[".json", ".jsonl", ".md"],
                min_age_hours=1
            ),
            LocationConfig(
                id="debug",
                path="~/.claude/debug",
                priority=2,
                strategy="batch-hourly",
                recursive=False,
                extensions=[".json", ".jsonl", ".log"],
                min_age_hours=1
            ),
            # Priority 3: Medium (Daily)
            LocationConfig(
                id="shell-snapshots",
                path="~/.claude/shell-snapshots",
                priority=3,
                strategy="batch-daily",
                recursive=False,
                extensions=[".json"],
                min_age_hours=24
            ),
            LocationConfig(
                id="file-history",
                path="~/.claude/file-history",
                priority=3,
                strategy="batch-daily",
                recursive=False,
                extensions=[".json"],
                min_age_hours=24
            ),
            LocationConfig(
                id="session-env",
                path="~/.claude/session-env",
                priority=3,
                strategy="batch-daily",
                recursive=False,
                extensions=[".json"],
                min_age_hours=24
            ),
            LocationConfig(
                id="paste-cache",
                path="~/.claude/paste-cache",
                priority=3,
                strategy="batch-daily",
                recursive=False,
                extensions=[".json", ".txt"],
                min_age_hours=24
            ),
        ]

    def save_config(self):
        """Save current configuration to file."""
        config_path = Path(self.config_file).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "locations": [asdict(config) for config in self.configs]
        }

        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def start(self):
        """Start watching all configured locations."""
        if self.running:
            print("⚠️  Already running", flush=True)
            return

        self.running = True

        # Start real-time watchers (Priority 1)
        for config in self.configs:
            if not config.enabled:
                continue

            if config.strategy == "real-time-incremental":
                self._start_realtime_watcher(config)

        # Start compression worker thread
        self.compression_thread = threading.Thread(
            target=self._compression_worker,
            daemon=True
        )
        self.compression_thread.start()

        # Start batch workers
        self._start_batch_workers()

        print("✅ Universal Watcher Started", flush=True)
        print(flush=True)

    def stop(self):
        """Stop all watchers."""
        print("\n🛑 Stopping Universal Watcher...", flush=True)
        self.running = False

        # Stop real-time observers
        for observer in self.observers.values():
            observer.stop()
            observer.join()

        # Wait for compression thread
        if self.compression_thread:
            self.compression_thread.join(timeout=5)

        print("✅ Stopped", flush=True)

    def _start_realtime_watcher(self, config: LocationConfig):
        """Start a real-time file watcher."""
        path = Path(config.path).expanduser()

        if not path.exists():
            print(f"⚠️  Location not found: {path}", flush=True)
            return

        # Create watcher
        watcher = LocationWatcher(config, self.queue, self.stats_tracker)
        self.watchers[config.id] = watcher

        # Create observer
        observer = Observer()
        observer.schedule(
            watcher,
            str(path),
            recursive=config.recursive
        )
        observer.start()
        self.observers[config.id] = observer

        print(f"👀 Watching [{config.id}]: {path}", flush=True)

    def _start_batch_workers(self):
        """Start batch processing workers for hourly/daily strategies."""
        # Start hourly batch worker
        hourly_thread = threading.Thread(
            target=self._batch_worker,
            args=("batch-hourly", 3600),  # 1 hour
            daemon=True
        )
        hourly_thread.start()
        self.batch_threads["hourly"] = hourly_thread

        # Start daily batch worker
        daily_thread = threading.Thread(
            target=self._batch_worker,
            args=("batch-daily", 86400),  # 24 hours
            daemon=True
        )
        daily_thread.start()
        self.batch_threads["daily"] = daily_thread

    def _batch_worker(self, strategy: str, interval_seconds: int):
        """Worker for batch compression strategies."""
        print(f"📦 Started {strategy} worker (interval: {interval_seconds}s)", flush=True)

        while self.running:
            # Process all locations with this strategy
            for config in self.configs:
                if not config.enabled or config.strategy != strategy:
                    continue

                try:
                    self._scan_location(config)
                except Exception as e:
                    print(f"⚠️  Error scanning {config.id}: {e}", flush=True)

            # Sleep until next batch
            time.sleep(interval_seconds)

    def _scan_location(self, config: LocationConfig):
        """Scan a location for files to compress."""
        path = Path(config.path).expanduser()

        if not path.exists():
            return

        # Scan for matching files
        watcher = LocationWatcher(config, self.queue, self.stats_tracker)

        if path.is_file():
            watcher._process_file(path)
        else:
            pattern = "*" + config.extensions[0] if config.extensions else "*"
            for file_path in path.glob(pattern):
                if file_path.is_file():
                    watcher._process_file(file_path)

    def _compression_worker(self):
        """Worker thread that processes compression queue."""
        print("🏗️  Compression worker started", flush=True)

        while self.running:
            try:
                # Get next task (with timeout to check self.running)
                task = self.queue.get(timeout=1)
                self._compress_file(task)
            except Empty:
                continue
            except Exception as e:
                print(f"⚠️  Compression worker error: {e}", flush=True)

    def _compress_file(self, task: CompressionTask):
        """Compress a file."""
        try:
            file_path = task.file_path
            config = task.config

            # Ensure output directory exists
            output_dir = Path(config.output_directory).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            # Use the unified pipeline's compress_conversation method
            result = self.pipeline.compress_conversation(
                jsonl_path=str(file_path),
                output_dir=str(output_dir),
                session_id=f"{config.id}_{file_path.stem}",
                project_id=config.id
            )

            # Calculate bytes saved
            original_size = file_path.stat().st_size
            compressed_file = Path(result.output_path)
            compressed_size = compressed_file.stat().st_size if compressed_file.exists() else 0
            bytes_saved = original_size - compressed_size

            # Record stats
            self.stats_tracker.record_compression(
                config.id,
                result.original_tokens,
                result.final_tokens,
                bytes_saved
            )

            print(f"✅ [{config.id}] {file_path.name}: "
                  f"{result.original_tokens:,} → {result.final_tokens:,} tokens "
                  f"({result.total_reduction_percent:.1f}%)", flush=True)

        except Exception as e:
            print(f"❌ [{task.config.id}] {task.file_path.name}: {e}", flush=True)
            self.stats_tracker.record_failure(task.config.id)

    def get_stats(self) -> Dict:
        """Get compression statistics."""
        stats = {
            "total_locations": len(self.configs),
            "active_locations": sum(1 for c in self.configs if c.enabled),
            "queue_size": self.queue.qsize(),
            "locations": self.stats_tracker.get_stats()
        }

        # Calculate totals
        all_stats = self.stats_tracker.get_stats()
        stats["total_processed"] = sum(s["processed"] for s in all_stats.values())
        stats["total_failed"] = sum(s["failed"] for s in all_stats.values())
        stats["total_tokens_saved"] = sum(
            s["original_tokens"] - s["compressed_tokens"]
            for s in all_stats.values()
        )
        stats["total_bytes_saved"] = sum(s["bytes_saved"] for s in all_stats.values())

        return stats


def main():
    """Run the universal watcher daemon."""
    print("🌍 Starting Universal Watcher", flush=True)
    print(flush=True)

    # Create watcher
    watcher = UniversalWatcher()

    # Save default config if it doesn't exist
    if not Path(watcher.config_file).expanduser().exists():
        watcher.save_config()
        print(f"💾 Saved default config to: {watcher.config_file}", flush=True)

    # Start watching
    watcher.start()

    try:
        while True:
            time.sleep(60)  # Print stats every minute

            stats = watcher.get_stats()
            if stats['total_processed'] > 0:
                print(f"📊 Processed: {stats['total_processed']}, "
                      f"Failed: {stats['total_failed']}, "
                      f"Queue: {stats['queue_size']}, "
                      f"Tokens saved: {stats['total_tokens_saved']:,}", flush=True)

    except KeyboardInterrupt:
        watcher.stop()


if __name__ == "__main__":
    main()
