#!/usr/bin/env python3
"""
V4Z Compressor - Advanced Compression Layer

Combines SLIM vocabulary with Zstandard compression for 80%+ reduction.

Architecture:
1. SLIM vocabulary (6-10% reduction on markdown)
2. Zstandard with dictionary training (70-80% on remaining)
3. Base64 encoding for safe storage

Total expected: 75-85% reduction on PRDs
"""

import zstandard as zstd
import base64
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from slim_vocabulary import SlimVocabulary
from token_analyzer import TokenAnalyzer


@dataclass
class V4ZCompressionResult:
    """Result from V4Z compression."""
    original_text: str
    compressed_bytes: bytes
    compressed_base64: str
    original_size_bytes: int
    compressed_size_bytes: int
    reduction_percent: float
    original_tokens: int
    compressed_tokens: int
    token_reduction_percent: float
    slim_stats: Dict[str, Any]
    zstd_dict_id: Optional[int] = None


class V4ZCompressor:
    """
    V4Z Compressor combining SLIM vocabulary and Zstandard.

    V4Z Format:
    - Header: §V4Z§ <version> <dict_id>\n
    - Body: Base64-encoded Zstandard compressed data
    - Footer: §/V4Z§

    Compression levels:
    - 1-3: Fast (lower compression)
    - 4-9: Balanced (default: 6)
    - 10-22: Maximum (slower, better compression)
    """

    def __init__(
        self,
        compression_level: int = 6,
        dictionary_path: Optional[str] = None
    ):
        """
        Initialize V4Z compressor.

        Args:
            compression_level: Zstandard compression level (1-22, default: 6)
            dictionary_path: Path to trained dictionary (optional)
        """
        if not 1 <= compression_level <= 22:
            raise ValueError("Compression level must be between 1 and 22")

        self.compression_level = compression_level
        self.vocabulary = SlimVocabulary()
        self.token_analyzer = TokenAnalyzer()
        self.dictionary = None
        self.dictionary_id = None

        # Load dictionary if provided
        if dictionary_path:
            self._load_dictionary(dictionary_path)

        # Create Zstandard compressor
        if self.dictionary:
            self.compressor = zstd.ZstdCompressor(
                level=compression_level,
                dict_data=self.dictionary
            )
        else:
            self.compressor = zstd.ZstdCompressor(level=compression_level)

    def compress(self, text: str, add_header: bool = True) -> V4ZCompressionResult:
        """
        Compress text using V4Z (SLIM + Zstandard).

        Args:
            text: Original text to compress
            add_header: Whether to add V4Z header/footer (default: True)

        Returns:
            V4ZCompressionResult with compression metrics
        """
        original_size = len(text.encode('utf-8'))
        original_tokens = self.token_analyzer.count_tokens(text)

        # Step 1: Apply SLIM vocabulary
        slim_compressed, slim_stats = self.vocabulary.compress(text)

        # Step 2: Apply Zstandard compression
        compressed_bytes = self.compressor.compress(slim_compressed.encode('utf-8'))

        # Step 3: Base64 encode for safe storage
        compressed_base64 = base64.b64encode(compressed_bytes).decode('ascii')

        # Step 4: Add header if requested
        if add_header:
            version = "1.0"
            dict_id = self.dictionary_id or 0
            final_output = f"§V4Z§ {version} {dict_id}\n{compressed_base64}\n§/V4Z§"
        else:
            final_output = compressed_base64

        # Calculate metrics
        final_size = len(final_output.encode('utf-8'))
        reduction_percent = round((1 - final_size / original_size) * 100, 1) if original_size > 0 else 0

        # Estimate compressed tokens (much lower than uncompressed)
        # V4Z is binary, so token count is ~30% of byte count
        compressed_tokens = int(final_size * 0.3)
        token_reduction = round((1 - compressed_tokens / original_tokens) * 100, 1) if original_tokens > 0 else 0

        return V4ZCompressionResult(
            original_text=text,
            compressed_bytes=compressed_bytes,
            compressed_base64=final_output,
            original_size_bytes=original_size,
            compressed_size_bytes=final_size,
            reduction_percent=reduction_percent,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            token_reduction_percent=token_reduction,
            slim_stats=slim_stats,
            zstd_dict_id=self.dictionary_id
        )

    def decompress(self, compressed_text: str) -> str:
        """
        Decompress V4Z compressed text.

        Args:
            compressed_text: V4Z compressed text (with or without header)

        Returns:
            Original decompressed text
        """
        # Remove header if present
        if compressed_text.startswith('§V4Z§'):
            lines = compressed_text.strip().split('\n')
            if len(lines) < 3:
                raise ValueError("Invalid V4Z format: missing body")

            # Parse header
            header_parts = lines[0].split()
            if len(header_parts) != 3:
                raise ValueError(f"Invalid V4Z header: {lines[0]}")

            version = header_parts[1]
            dict_id = int(header_parts[2])

            # Extract body (everything between header and footer)
            body_lines = []
            for line in lines[1:]:
                if line == '§/V4Z§':
                    break
                body_lines.append(line)

            compressed_base64 = ''.join(body_lines)
        else:
            compressed_base64 = compressed_text.strip()

        # Step 1: Base64 decode
        compressed_bytes = base64.b64decode(compressed_base64)

        # Step 2: Zstandard decompress
        if self.dictionary:
            decompressor = zstd.ZstdDecompressor(dict_data=self.dictionary)
        else:
            decompressor = zstd.ZstdDecompressor()

        slim_compressed = decompressor.decompress(compressed_bytes).decode('utf-8')

        # Step 3: Reverse SLIM vocabulary
        original_text = self.vocabulary.decompress(slim_compressed)

        return original_text

    def compress_file(self, input_path: str, output_path: Optional[str] = None) -> V4ZCompressionResult:
        """
        Compress a file using V4Z.

        Args:
            input_path: Path to input file
            output_path: Path to output file (default: <input>.v4z)

        Returns:
            V4ZCompressionResult
        """
        # Read input
        with open(input_path, 'r') as f:
            text = f.read()

        # Compress
        result = self.compress(text)

        # Determine output path
        if output_path is None:
            output_path = input_path + '.v4z'

        # Write output
        with open(output_path, 'w') as f:
            f.write(result.compressed_base64)

        return result

    def decompress_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Decompress a V4Z file.

        Args:
            input_path: Path to V4Z compressed file
            output_path: Path to output file (default: <input> without .v4z)

        Returns:
            Decompressed text
        """
        # Read compressed file
        with open(input_path, 'r') as f:
            compressed_text = f.read()

        # Decompress
        decompressed_text = self.decompress(compressed_text)

        # Determine output path
        if output_path is None:
            if input_path.endswith('.v4z'):
                output_path = input_path[:-4]
            else:
                output_path = input_path + '.decompressed'

        # Write output
        with open(output_path, 'w') as f:
            f.write(decompressed_text)

        return decompressed_text

    def train_dictionary(
        self,
        training_files: list,
        dict_size: int = 110 * 1024,
        output_path: Optional[str] = None
    ) -> bytes:
        """
        Train a Zstandard dictionary on sample files for better compression.

        Args:
            training_files: List of file paths to train on
            dict_size: Dictionary size in bytes (default: 110KB)
            output_path: Where to save dictionary (optional)

        Returns:
            Trained dictionary bytes
        """
        print(f"\n📚 Training Zstandard dictionary...")
        print(f"   Training files: {len(training_files)}")

        # Read all training data
        training_data = []
        total_size = 0
        for file_path in training_files:
            with open(file_path, 'r') as f:
                text = f.read()

            # Apply SLIM vocabulary first
            slim_compressed, _ = self.vocabulary.compress(text)
            compressed_bytes = slim_compressed.encode('utf-8')
            training_data.append(compressed_bytes)
            total_size += len(compressed_bytes)

        print(f"   Total training data: {total_size:,} bytes")

        # Adjust dictionary size if needed (must be < total training data)
        # Zstandard requires dict_size <= training data size
        if dict_size >= total_size:
            dict_size = max(1024, total_size // 2)  # Use half of training data size
            print(f"   Adjusted dictionary size: {dict_size:,} bytes (50% of training data)")
        else:
            print(f"   Dictionary size: {dict_size:,} bytes")

        # Train dictionary
        dict_data = zstd.train_dictionary(dict_size, training_data)
        self.dictionary = zstd.ZstdCompressionDict(dict_data)
        self.dictionary_id = self.dictionary.dict_id()

        print(f"   ✅ Dictionary trained! ID: {self.dictionary_id}")

        # Save if path provided
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(dict_data)
            print(f"   💾 Saved to: {output_path}")

        return dict_data

    def _load_dictionary(self, dictionary_path: str):
        """Load pre-trained dictionary from file."""
        with open(dictionary_path, 'rb') as f:
            dict_data = f.read()

        self.dictionary = zstd.ZstdCompressionDict(dict_data)
        self.dictionary_id = self.dictionary.dict_id()

        print(f"📚 Loaded dictionary: {dictionary_path} (ID: {self.dictionary_id})")

    def verify_round_trip(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Verify compression/decompression round-trip is lossless.

        Args:
            text: Text to test

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Compress
            result = self.compress(text)

            # Decompress
            decompressed = self.decompress(result.compressed_base64)

            # Compare
            if text == decompressed:
                return (True, None)
            else:
                return (False, "Round-trip mismatch: decompressed text differs from original")

        except Exception as e:
            return (False, f"Round-trip failed: {str(e)}")


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="V4Z Compressor - SLIM + Zstandard"
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Compress command
    compress_parser = subparsers.add_parser('compress', help='Compress file')
    compress_parser.add_argument('input', help='Input file')
    compress_parser.add_argument('-o', '--output', help='Output file')
    compress_parser.add_argument('-l', '--level', type=int, default=6, help='Compression level (1-22)')
    compress_parser.add_argument('-d', '--dictionary', help='Dictionary file')

    # Decompress command
    decompress_parser = subparsers.add_parser('decompress', help='Decompress file')
    decompress_parser.add_argument('input', help='Input V4Z file')
    decompress_parser.add_argument('-o', '--output', help='Output file')
    decompress_parser.add_argument('-d', '--dictionary', help='Dictionary file')

    # Train dictionary command
    train_parser = subparsers.add_parser('train', help='Train dictionary')
    train_parser.add_argument('files', nargs='+', help='Training files')
    train_parser.add_argument('-o', '--output', required=True, help='Output dictionary file')
    train_parser.add_argument('-s', '--size', type=int, default=110*1024, help='Dictionary size in bytes')

    # Benchmark command
    benchmark_parser = subparsers.add_parser('benchmark', help='Benchmark compression')
    benchmark_parser.add_argument('input', help='Input file to benchmark')
    benchmark_parser.add_argument('-d', '--dictionary', help='Dictionary file')

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify round-trip')
    verify_parser.add_argument('input', help='Input file')
    verify_parser.add_argument('-d', '--dictionary', help='Dictionary file')

    args = parser.parse_args()

    if args.command == 'compress':
        compressor = V4ZCompressor(
            compression_level=args.level,
            dictionary_path=args.dictionary
        )

        result = compressor.compress_file(args.input, args.output)

        print(f"\n✅ Compressed: {args.input}")
        print(f"   Output: {args.output or args.input + '.v4z'}")
        print(f"   Original: {result.original_size_bytes:,} bytes")
        print(f"   Compressed: {result.compressed_size_bytes:,} bytes")
        print(f"   Reduction: {result.reduction_percent}%")
        print(f"   Original tokens: {result.original_tokens:,}")
        print(f"   Compressed tokens: {result.compressed_tokens:,}")
        print(f"   Token reduction: {result.token_reduction_percent}%")
        print(f"\n   SLIM stats:")
        print(f"   • Structure: {result.slim_stats['structure_replacements']} replacements")
        print(f"   • Phrases: {result.slim_stats['phrase_replacements']} replacements")

    elif args.command == 'decompress':
        compressor = V4ZCompressor(dictionary_path=args.dictionary)

        decompressed = compressor.decompress_file(args.input, args.output)

        print(f"\n✅ Decompressed: {args.input}")
        print(f"   Output: {args.output or args.input.replace('.v4z', '')}")
        print(f"   Size: {len(decompressed):,} bytes")

    elif args.command == 'train':
        compressor = V4ZCompressor()

        dict_data = compressor.train_dictionary(
            args.files,
            dict_size=args.size,
            output_path=args.output
        )

    elif args.command == 'benchmark':
        # Test with and without dictionary
        print(f"\n📊 BENCHMARK: {args.input}\n")

        with open(args.input, 'r') as f:
            text = f.read()

        original_size = len(text.encode('utf-8'))
        print(f"Original size: {original_size:,} bytes")

        # Without dictionary
        print(f"\n🔹 Without dictionary:")
        compressor_no_dict = V4ZCompressor(compression_level=6)
        result_no_dict = compressor_no_dict.compress(text)
        print(f"   Compressed: {result_no_dict.compressed_size_bytes:,} bytes ({result_no_dict.reduction_percent}% reduction)")
        print(f"   Token reduction: {result_no_dict.token_reduction_percent}%")

        # With dictionary (if provided)
        if args.dictionary:
            print(f"\n🔹 With dictionary:")
            compressor_with_dict = V4ZCompressor(
                compression_level=6,
                dictionary_path=args.dictionary
            )
            result_with_dict = compressor_with_dict.compress(text)
            print(f"   Compressed: {result_with_dict.compressed_size_bytes:,} bytes ({result_with_dict.reduction_percent}% reduction)")
            print(f"   Token reduction: {result_with_dict.token_reduction_percent}%")
            print(f"   Improvement: {result_with_dict.reduction_percent - result_no_dict.reduction_percent:.1f}% better")

    elif args.command == 'verify':
        compressor = V4ZCompressor(dictionary_path=args.dictionary)

        with open(args.input, 'r') as f:
            text = f.read()

        is_valid, error = compressor.verify_round_trip(text)

        if is_valid:
            print(f"✅ Round-trip verification passed: {args.input}")
        else:
            print(f"❌ Round-trip verification failed: {error}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
