#!/usr/bin/env python3
"""
Golden Library - Basic Usage Example

Shows how to compress and decompress Claude Code conversations.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from slim_converter import SlimConverter
from handoff_slim import HandoffCompressor


def example_1_basic_compression():
    """Example 1: Basic SLIM compression"""
    print("=" * 60)
    print("Example 1: Basic SLIM Compression")
    print("=" * 60)

    # Create converter
    converter = SlimConverter()

    # Path to your conversation JSONL
    jsonl_path = "path/to/your/session.jsonl"

    # Compress to SLIM
    print(f"Compressing: {jsonl_path}")
    slim_content = converter.jsonl_to_slim(jsonl_path)

    # Save SLIM file
    output_path = "conversation.slim"
    Path(output_path).write_text(slim_content)
    print(f"✅ Saved to: {output_path}")

    # Get compression stats
    stats = converter.get_compression_stats(jsonl_path, slim_content)
    print(f"\n📊 Stats:")
    print(f"  Original: {stats['original_bytes']:,} bytes")
    print(f"  SLIM: {stats['slim_bytes']:,} bytes")
    print(f"  Saved: {stats['reduction_percent']}%")


def example_2_handoff_compression():
    """Example 2: Handoff with advanced compression"""
    print("\n" + "=" * 60)
    print("Example 2: Handoff Compression (SLIM + V4Z)")
    print("=" * 60)

    # Create compressor
    compressor = HandoffCompressor({
        "compression_level": "slim_v4z",  # Use SLIM + V4Z
        "preserve_original": True
    })

    # Compress conversation for handoff
    jsonl_path = "path/to/your/session.jsonl"

    print(f"Creating handoff from: {jsonl_path}")
    result = compressor.compress_conversation(jsonl_path)

    if result.get("ok"):
        print(f"✅ Handoff created: {result['handoff_id']}")
        print(f"\n📦 Compression:")
        print(f"  Original: {result['original_size']:,} bytes")
        print(f"  SLIM: {result['slim_size']:,} bytes")
        print(f"  Final: {result['final_size']:,} bytes")
        print(f"  Total reduction: {result['reduction_percent']}%")
        print(f"\n💾 Saved to:")
        print(f"  {result['final_path']}")
    else:
        print(f"❌ Error: {result.get('error')}")


def example_3_decompress_handoff():
    """Example 3: Decompress a handoff"""
    print("\n" + "=" * 60)
    print("Example 3: Decompress Handoff")
    print("=" * 60)

    compressor = HandoffCompressor()

    # List available handoffs
    handoffs = compressor.list_handoffs()
    print(f"📋 Available handoffs: {handoffs['count']}")

    if handoffs['count'] > 0:
        # Get the most recent handoff
        latest = handoffs['handoffs'][0]
        handoff_id = latest['handoff_id']

        print(f"\nDecompressing: {handoff_id}")

        # Decompress
        result = compressor.decompress_handoff(handoff_id)

        if result.get("ok"):
            print(f"✅ Decompressed to: {result['jsonl_path']}")
            print(f"⚡ Time: {result['decompression_ms']}ms")
            print(f"📄 Lines: {result['lines']}")
        else:
            print(f"❌ Error: {result.get('error')}")


def example_4_cli_usage():
    """Example 4: CLI usage"""
    print("\n" + "=" * 60)
    print("Example 4: CLI Usage")
    print("=" * 60)

    print("""
# Compress a conversation to SLIM
python src/slim_converter.py compress session.jsonl -o compressed.slim

# See compression stats
python src/slim_converter.py stats session.jsonl

# Decompress SLIM back to JSONL
python src/slim_converter.py decompress compressed.slim -o restored.jsonl

# Create a handoff
python src/handoff_slim.py compress session.jsonl --level slim_v4z

# List all handoffs
python src/handoff_slim.py list

# Decompress a handoff
python src/handoff_slim.py decompress abc123def456

# Get handoff stats
python src/handoff_slim.py stats abc123def456
    """)


if __name__ == "__main__":
    print("🏆 Golden Library - Examples\n")

    # Run examples
    # example_1_basic_compression()
    # example_2_handoff_compression()
    # example_3_decompress_handoff()
    example_4_cli_usage()

    print("\n" + "=" * 60)
    print("💡 Tip: Edit this file and uncomment examples to run them")
    print("=" * 60)
