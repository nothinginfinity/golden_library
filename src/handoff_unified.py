#!/usr/bin/env python3
"""
Unified Handoff Integration

Handles creating and loading handoffs with the unified compression pipeline.
Enables seamless context transfer between Claude instances with maximum token efficiency.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from unified_pipeline import UnifiedCompressionPipeline
from index_extractor import IndexExtractor
from slim_converter import SlimConverter


class HandoffManager:
    """Manage compressed handoffs for seamless instance transfers."""

    def __init__(self, handoff_dir: Optional[str] = None):
        """
        Initialize handoff manager.

        Args:
            handoff_dir: Base directory for handoffs (default: ~/.fsl/handoffs/)
        """
        if handoff_dir is None:
            self.handoff_dir = Path("~/.fsl/handoffs").expanduser()
        else:
            self.handoff_dir = Path(handoff_dir).expanduser()

        self.handoff_dir.mkdir(parents=True, exist_ok=True)

    def create_handoff(
        self,
        conversation_path: str,
        level: str = "balanced",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create compressed handoff package.

        Args:
            conversation_path: Path to JSONL conversation
            level: Compression level (minimal/balanced/maximum)
            notes: Optional notes about the handoff

        Returns:
            Handoff metadata dictionary
        """
        print(f"\n📦 Creating handoff package...")
        print(f"   Conversation: {conversation_path}")
        print(f"   Compression level: {level}")

        # Create pipeline
        pipeline = UnifiedCompressionPipeline(level=level)

        # Compress for handoff
        metadata = pipeline.compress_for_handoff(
            conversation_path,
            handoff_dir=str(self.handoff_dir)
        )

        # Add notes if provided
        if notes:
            metadata["notes"] = notes

        # Re-save metadata with notes
        handoff_id = metadata["handoff_id"]
        handoff_path = self.handoff_dir / handoff_id
        metadata_path = handoff_path / "metadata.json"

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"\n✅ Handoff created: {handoff_id}")
        return metadata

    def list_handoffs(self) -> List[Dict[str, Any]]:
        """
        List all available handoffs.

        Returns:
            List of handoff metadata dictionaries
        """
        handoffs = []

        for handoff_dir in self.handoff_dir.iterdir():
            if handoff_dir.is_dir() and handoff_dir.name.startswith("handoff_"):
                metadata_path = handoff_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        handoffs.append(metadata)

        # Sort by timestamp (newest first)
        handoffs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return handoffs

    def load_handoff(
        self,
        handoff_id: str,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load and decompress a handoff package.

        Args:
            handoff_id: Handoff ID or path to handoff directory
            output_path: Optional output path for decompressed conversation

        Returns:
            Dictionary with decompressed content and metadata
        """
        # Resolve handoff path
        if Path(handoff_id).exists():
            handoff_path = Path(handoff_id)
        else:
            handoff_path = self.handoff_dir / handoff_id

        if not handoff_path.exists():
            raise FileNotFoundError(f"Handoff not found: {handoff_id}")

        print(f"\n📥 Loading handoff: {handoff_path.name}")

        # Load metadata
        metadata_path = handoff_path / "metadata.json"
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        print(f"   Created: {metadata.get('timestamp', 'unknown')}")
        print(f"   Original tokens: {metadata.get('original_tokens', 0):,}")
        print(f"   Compressed tokens: {metadata.get('final_tokens', 0):,}")
        print(f"   Reduction: {metadata.get('reduction_percent', 0)}%")

        # Find compressed file
        compressed_path = handoff_path / Path(metadata["compressed_file"]).name

        if not compressed_path.exists():
            raise FileNotFoundError(f"Compressed file not found: {compressed_path}")

        # Load indexes if they exist
        indexes = metadata.get("indexes", {})
        index_files = []

        for tier, index_path in indexes.items():
            index_path = Path(index_path).expanduser()
            if index_path.exists():
                index_files.append(str(index_path))
                print(f"   Loading {tier} index: {index_path.name}")

        # Read compressed content
        with open(compressed_path, 'r') as f:
            compressed_content = f.read()

        # Decompress if needed (resolve references)
        if index_files:
            print(f"\n🔄 Resolving index references...")
            extractor = IndexExtractor()
            decompressed_content = extractor.resolve_references(
                compressed_content,
                index_files
            )
        else:
            decompressed_content = compressed_content

        # If SLIM format, optionally convert back to JSONL
        if compressed_content.startswith("§SLIM§"):
            print(f"\n🔄 Converting from SLIM format...")
            converter = SlimConverter()
            decompressed_content = converter.slim_to_jsonl(decompressed_content)

        # Write to output if specified
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                f.write(decompressed_content)

            print(f"\n✅ Decompressed to: {output_path}")

        return {
            "metadata": metadata,
            "content": decompressed_content,
            "indexes_loaded": index_files
        }

    def delete_handoff(self, handoff_id: str, confirm: bool = False):
        """
        Delete a handoff package.

        Args:
            handoff_id: Handoff ID to delete
            confirm: If True, skip confirmation prompt
        """
        handoff_path = self.handoff_dir / handoff_id

        if not handoff_path.exists():
            raise FileNotFoundError(f"Handoff not found: {handoff_id}")

        if not confirm:
            response = input(f"Delete handoff {handoff_id}? (y/N): ")
            if response.lower() != 'y':
                print("Cancelled.")
                return

        shutil.rmtree(handoff_path)
        print(f"✅ Deleted handoff: {handoff_id}")

    def get_handoff_info(self, handoff_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a handoff.

        Args:
            handoff_id: Handoff ID

        Returns:
            Detailed handoff information
        """
        handoff_path = self.handoff_dir / handoff_id

        if not handoff_path.exists():
            raise FileNotFoundError(f"Handoff not found: {handoff_id}")

        # Load metadata
        metadata_path = handoff_path / "metadata.json"
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        # Get file sizes
        compressed_path = handoff_path / Path(metadata["compressed_file"]).name
        compressed_size = compressed_path.stat().st_size if compressed_path.exists() else 0

        # Count index files
        index_count = len([f for f in handoff_path.iterdir() if f.suffix == '.json' and f.name != 'metadata.json'])

        info = {
            **metadata,
            "handoff_path": str(handoff_path),
            "compressed_size_bytes": compressed_size,
            "index_files_count": index_count,
            "files": [f.name for f in handoff_path.iterdir()]
        }

        return info


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Unified Handoff Manager"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Create handoff
    create_parser = subparsers.add_parser("create", help="Create compressed handoff")
    create_parser.add_argument("conversation", help="Path to JSONL conversation")
    create_parser.add_argument(
        "--level",
        choices=["minimal", "balanced", "maximum"],
        default="balanced",
        help="Compression level (default: balanced)"
    )
    create_parser.add_argument("--notes", help="Optional notes about handoff")

    # List handoffs
    list_parser = subparsers.add_parser("list", help="List all handoffs")

    # Load handoff
    load_parser = subparsers.add_parser("load", help="Load and decompress handoff")
    load_parser.add_argument("handoff_id", help="Handoff ID to load")
    load_parser.add_argument("--output", help="Output path for decompressed conversation")

    # Info
    info_parser = subparsers.add_parser("info", help="Show handoff details")
    info_parser.add_argument("handoff_id", help="Handoff ID")

    # Delete
    delete_parser = subparsers.add_parser("delete", help="Delete handoff")
    delete_parser.add_argument("handoff_id", help="Handoff ID to delete")
    delete_parser.add_argument("--yes", action="store_true", help="Skip confirmation")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Create manager
    manager = HandoffManager()

    if args.command == "create":
        metadata = manager.create_handoff(
            args.conversation,
            level=args.level,
            notes=args.notes
        )

    elif args.command == "list":
        handoffs = manager.list_handoffs()

        if not handoffs:
            print("No handoffs found.")
            return

        print(f"\n📦 Available Handoffs ({len(handoffs)}):")
        print("=" * 80)

        for handoff in handoffs:
            print(f"\n🔖 {handoff['handoff_id']}")
            print(f"   Created: {handoff.get('timestamp', 'unknown')}")
            print(f"   Level: {handoff.get('compression_level', 'unknown')}")
            print(f"   Tokens: {handoff.get('original_tokens', 0):,} → {handoff.get('final_tokens', 0):,} ({handoff.get('reduction_percent', 0)}%)")
            if "notes" in handoff:
                print(f"   Notes: {handoff['notes']}")

        print("\n" + "=" * 80)

    elif args.command == "load":
        result = manager.load_handoff(
            args.handoff_id,
            output_path=args.output
        )

        if not args.output:
            # Print to stdout if no output file
            print("\n" + "=" * 80)
            print("DECOMPRESSED CONTENT")
            print("=" * 80)
            print(result["content"])

    elif args.command == "info":
        info = manager.get_handoff_info(args.handoff_id)

        print(f"\n📋 Handoff Information")
        print("=" * 80)
        print(f"ID: {info['handoff_id']}")
        print(f"Created: {info.get('timestamp', 'unknown')}")
        print(f"Level: {info.get('compression_level', 'unknown')}")
        print(f"Original tokens: {info.get('original_tokens', 0):,}")
        print(f"Final tokens: {info.get('final_tokens', 0):,}")
        print(f"Reduction: {info.get('reduction_percent', 0)}%")
        print(f"Compressed size: {info.get('compressed_size_bytes', 0):,} bytes")
        print(f"Index files: {info.get('index_files_count', 0)}")
        print(f"Path: {info['handoff_path']}")

        if "notes" in info:
            print(f"Notes: {info['notes']}")

        print(f"\nFiles:")
        for file in info.get('files', []):
            print(f"  - {file}")

        print("=" * 80)

    elif args.command == "delete":
        manager.delete_handoff(args.handoff_id, confirm=args.yes)


if __name__ == "__main__":
    main()
