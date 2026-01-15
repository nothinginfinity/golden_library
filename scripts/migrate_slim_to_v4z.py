#!/usr/bin/env python3
"""
Migrate existing SLIM files to V4Z format.

This script:
1. Finds all .slim.indexed files in conversation library
2. Decompresses using SlimConverter
3. Recompresses using V4ZCompressor
4. Saves as .v4z files
5. Keeps old .slim.indexed files as backup

Usage:
    python3 scripts/migrate_slim_to_v4z.py [--dry-run] [--delete-old]
"""

import sys
from pathlib import Path
import json
from datetime import datetime
from typing import List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from slim_converter import SlimConverter
from v4z_compressor import V4ZCompressor


class SlimToV4ZMigrator:
    """Migrates SLIM files to V4Z format."""

    def __init__(self, dry_run: bool = False, delete_old: bool = False):
        """
        Initialize migrator.

        Args:
            dry_run: If True, only simulate migration without writing files
            delete_old: If True, delete old .slim.indexed files after successful migration
        """
        self.dry_run = dry_run
        self.delete_old = delete_old
        self.slim_converter = SlimConverter()
        self.v4z_compressor = V4ZCompressor()

        # Stats
        self.total_files = 0
        self.migrated_files = 0
        self.failed_files = 0
        self.skipped_files = 0
        self.total_tokens_before = 0
        self.total_tokens_after = 0
        self.errors: List[Tuple[str, str]] = []

    def migrate_file(self, slim_file: Path) -> bool:
        """
        Migrate a single SLIM file to V4Z.

        Args:
            slim_file: Path to .slim.indexed file

        Returns:
            True if successful, False otherwise
        """
        try:
            self.total_files += 1
            print(f"\n📦 Processing: {slim_file.name}")

            # Check if V4Z file already exists
            v4z_file = slim_file.with_suffix('.v4z')
            if v4z_file.exists():
                print(f"   ⏭️  Skipped: V4Z file already exists")
                self.skipped_files += 1
                return True

            # Read SLIM file
            with open(slim_file, 'r', encoding='utf-8') as f:
                slim_content = f.read()

            print(f"   📖 Read {len(slim_content):,} bytes (SLIM)")

            # Decompress SLIM to JSONL
            try:
                jsonl_content = self.slim_converter.slim_to_jsonl(slim_content)
                print(f"   ✅ Decompressed SLIM → {len(jsonl_content):,} bytes (JSONL)")
            except Exception as e:
                print(f"   ❌ SLIM decompression failed: {e}")
                self.failed_files += 1
                self.errors.append((slim_file.name, f"SLIM decompression: {e}"))
                return False

            # Compress with V4Z
            try:
                result = self.v4z_compressor.compress(jsonl_content, add_header=True)
                print(f"   ✅ Compressed V4Z → {result.compressed_size_bytes:,} bytes")
                print(f"   📊 Tokens: {result.original_tokens:,} → {result.compressed_tokens:,} ({result.token_reduction_percent}% reduction)")

                self.total_tokens_before += result.original_tokens
                self.total_tokens_after += result.compressed_tokens
            except Exception as e:
                print(f"   ❌ V4Z compression failed: {e}")
                self.failed_files += 1
                self.errors.append((slim_file.name, f"V4Z compression: {e}"))
                return False

            # Write V4Z file
            if not self.dry_run:
                try:
                    with open(v4z_file, 'w', encoding='utf-8') as f:
                        f.write(result.compressed_base64)
                    print(f"   💾 Saved: {v4z_file.name}")
                except Exception as e:
                    print(f"   ❌ Failed to write V4Z file: {e}")
                    self.failed_files += 1
                    self.errors.append((slim_file.name, f"Write V4Z: {e}"))
                    return False

                # Delete old file if requested
                if self.delete_old:
                    try:
                        slim_file.unlink()
                        print(f"   🗑️  Deleted: {slim_file.name}")
                    except Exception as e:
                        print(f"   ⚠️  Failed to delete old file: {e}")
            else:
                print(f"   🔍 DRY RUN: Would save to {v4z_file.name}")
                if self.delete_old:
                    print(f"   🔍 DRY RUN: Would delete {slim_file.name}")

            self.migrated_files += 1
            return True

        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            self.failed_files += 1
            self.errors.append((slim_file.name, f"Unexpected: {e}"))
            return False

    def migrate_directory(self, directory: Path) -> None:
        """
        Migrate all SLIM files in a directory.

        Args:
            directory: Directory to search for .slim.indexed files
        """
        if not directory.exists():
            print(f"⚠️  Directory does not exist: {directory}")
            return

        print(f"\n📂 Searching: {directory}")

        # Find all .slim.indexed files
        slim_files = list(directory.glob("*.slim.indexed"))

        if not slim_files:
            print(f"   No .slim.indexed files found")
            return

        print(f"   Found {len(slim_files)} SLIM files")

        # Migrate each file
        for slim_file in slim_files:
            self.migrate_file(slim_file)

    def migrate_conversation_library(self) -> None:
        """Migrate conversation library SLIM files."""
        conv_library = Path.home() / ".claude/conversation_library/compressed"

        print("\n" + "=" * 80)
        print("🚀 SLIM → V4Z MIGRATION")
        print("=" * 80)

        if self.dry_run:
            print("\n⚠️  DRY RUN MODE - No files will be modified")

        if self.delete_old:
            print("\n⚠️  DELETE MODE - Old .slim.indexed files will be deleted")

        # Migrate subdirectories
        subdirs = [
            conv_library / "projects",
            conv_library / "todos",
            conv_library  # Root level
        ]

        for subdir in subdirs:
            self.migrate_directory(subdir)

        # Print summary
        self.print_summary()

    def print_summary(self) -> None:
        """Print migration summary."""
        print("\n" + "=" * 80)
        print("📊 MIGRATION SUMMARY")
        print("=" * 80)

        print(f"\n📁 Files:")
        print(f"   Total: {self.total_files}")
        print(f"   Migrated: {self.migrated_files}")
        print(f"   Skipped: {self.skipped_files}")
        print(f"   Failed: {self.failed_files}")

        if self.total_tokens_before > 0:
            overall_reduction = round((1 - self.total_tokens_after / self.total_tokens_before) * 100, 1)
            tokens_saved = self.total_tokens_before - self.total_tokens_after

            print(f"\n📊 Tokens:")
            print(f"   Before: {self.total_tokens_before:,}")
            print(f"   After: {self.total_tokens_after:,}")
            print(f"   Saved: {tokens_saved:,} ({overall_reduction}% reduction)")

            # Cost savings (at $3/M input tokens)
            cost_saved_per_load = (tokens_saved / 1_000_000) * 3.0
            print(f"\n💰 Cost Savings:")
            print(f"   Per load: ${cost_saved_per_load:.3f}")

        if self.errors:
            print(f"\n❌ Errors:")
            for filename, error in self.errors[:10]:  # Show first 10 errors
                print(f"   • {filename}: {error}")
            if len(self.errors) > 10:
                print(f"   ... and {len(self.errors) - 10} more errors")

        print("\n" + "=" * 80)

        if self.dry_run:
            print("\n⚠️  This was a DRY RUN - no files were modified")
            print("   Run without --dry-run to perform actual migration")

        if not self.dry_run and self.migrated_files > 0:
            print(f"\n✅ Migration complete!")
            if not self.delete_old:
                print(f"   Old .slim.indexed files kept as backup")
                print(f"   Delete them manually if V4Z files work correctly")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate SLIM files to V4Z format"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate migration without writing files'
    )
    parser.add_argument(
        '--delete-old',
        action='store_true',
        help='Delete old .slim.indexed files after successful migration'
    )

    args = parser.parse_args()

    # Create migrator
    migrator = SlimToV4ZMigrator(
        dry_run=args.dry_run,
        delete_old=args.delete_old
    )

    # Run migration
    migrator.migrate_conversation_library()


if __name__ == "__main__":
    main()
