#!/usr/bin/env python3
"""
Decompress Utility

Decompresses V4Z files and outputs to stdout or file.

Usage:
  python3 decompress.py <file.v4z>
  python3 decompress.py <file.v4z> -o output.md
  python3 decompress.py <handoff_id>  # Looks in .golden_library/compressed/
"""

import sys
import argparse
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from v4z_compressor import V4ZCompressor


def find_compressed_file(identifier):
    """Find compressed file by handoff ID or path."""
    # Try as direct path first
    path = Path(identifier)
    if path.exists():
        return path

    # Try adding .v4z extension
    if not identifier.endswith('.v4z'):
        path = Path(identifier + '.v4z')
        if path.exists():
            return path

    # Try in .golden_library/compressed/
    compressed_dir = Path(".golden_library/compressed")
    if compressed_dir.exists():
        path = compressed_dir / identifier
        if path.exists():
            return path

        path = compressed_dir / (identifier + '.v4z')
        if path.exists():
            return path

    return None


def decompress_file(input_file, output_file=None):
    """Decompress V4Z file."""
    # Find file
    file_path = find_compressed_file(input_file)

    if not file_path:
        print(f"❌ File not found: {input_file}", file=sys.stderr)
        print(f"\n💡 Tried:", file=sys.stderr)
        print(f"   - {input_file}", file=sys.stderr)
        print(f"   - {input_file}.v4z", file=sys.stderr)
        print(f"   - .golden_library/compressed/{input_file}", file=sys.stderr)
        sys.exit(1)

    # Decompress
    compressor = V4ZCompressor()

    try:
        with open(file_path, 'r') as f:
            compressed_content = f.read()

        decompressed_content = compressor.decompress(compressed_content)

        # Output
        if output_file:
            with open(output_file, 'w') as f:
                f.write(decompressed_content)
            print(f"✅ Decompressed: {file_path} → {output_file}", file=sys.stderr)
        else:
            # Output to stdout
            print(decompressed_content)

    except Exception as e:
        print(f"❌ Decompression failed: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Decompress V4Z files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Decompress to stdout
  python3 decompress.py handoff.v4z

  # Decompress to file
  python3 decompress.py handoff.v4z -o output.md

  # Decompress by handoff ID
  python3 decompress.py 9bca1a7

  # Pipe to other tools
  python3 decompress.py handoff.v4z | grep "Priority"
        """
    )

    parser.add_argument('input', help='Input V4Z file or handoff ID')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')

    args = parser.parse_args()

    decompress_file(args.input, args.output)


if __name__ == "__main__":
    main()
