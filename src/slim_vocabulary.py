#!/usr/bin/env python3
"""
SLIM Vocabulary for Markdown Compression

Defines token replacements for common markdown patterns to achieve
high compression ratios on PRDs and documentation.

Strategy:
1. Multi-character sequences → single-char tokens
2. Common phrases → short tokens
3. Reversible (lossless) compression
4. Human-readable for debugging
"""

from typing import Dict, Tuple, List
import re


class SlimVocabulary:
    """
    Vocabulary for compressing markdown documents.

    Uses a two-pass approach:
    1. Structure tokens (headings, lists, code blocks)
    2. Phrase tokens (common words/phrases in PRDs)
    """

    def __init__(self):
        """Initialize vocabulary with markdown-specific patterns."""

        # ==================================================================
        # PASS 1: Structure Tokens (Markdown Syntax)
        # ==================================================================

        # These are applied first to compress markdown structure
        self.structure_tokens = {
            # Headings (most common in PRDs)
            '### ': '§3§',      # H3 heading
            '## ': '§2§',       # H2 heading
            '#### ': '§4§',     # H4 heading
            '##### ': '§5§',    # H5 heading
            '# ': '§1§',        # H1 heading (after longer patterns)

            # Lists and tasks
            '- [ ] ': '¤t¤',    # Unchecked task
            '- [x] ': '¤x¤',    # Checked task
            '- [X] ': '¤X¤',    # Checked task (uppercase)
            '- ': '¤-¤',        # Bullet point
            '* ': '¤*¤',        # Alt bullet
            '1. ': '¤1¤',       # Numbered list

            # Code blocks
            '```bash\n': '«b»',
            '```python\n': '«p»',
            '```javascript\n': '«j»',
            '```json\n': '«J»',
            '```\n': '«c»',
            '```': '«»',

            # Emphasis
            '**': '‡',          # Bold
            '__': '‡‡',         # Alt bold
            '*': '†',           # Italic (after ** to avoid conflict)
            '_': '†_',          # Alt italic

            # Links and references
            '](': '»',          # Link middle part
            '[': '«',           # Link start
            ']': '»]',          # Link end (kept for clarity)

            # Common punctuation sequences
            ': ': ':·',         # Colon-space
            ', ': ',·',         # Comma-space
            '. ': '.·',         # Period-space
        }

        # ==================================================================
        # PASS 2: Phrase Tokens (Common PRD Vocabulary)
        # ==================================================================

        # High-frequency words in PRDs
        self.phrase_tokens = {
            # Status/Priority
            'Priority': 'Ⓟ',
            'Status': 'Ⓢ',
            'Estimated': 'Ⓔ',
            'Owner': 'Ⓞ',
            'Objective': 'Ⓑ',
            'Tasks': 'Ⓣ',
            'Requirements': 'Ⓡ',

            # Time/Dates (use multi-char tokens to avoid collisions)
            ' days': '·d',
            ' hours': '·h',
            ' weeks': '·w',
            ' months': '·m',

            # Common actions
            'Implement': 'impl',
            'implement': 'impl',
            'Create': 'crt',
            'create': 'crt',
            'Build': 'bld',
            'build': 'bld',
            'Add': 'add',
            'Update': 'upd',
            'update': 'upd',
            'Modify': 'mod',
            'modify': 'mod',
            'Design': 'dsgn',
            'design': 'dsgn',
            'Test': 'tst',
            'test': 'tst',
            'Deploy': 'dpl',
            'deploy': 'dpl',

            # Technical terms
            'function': 'fn',
            'Function': 'Fn',
            'component': 'cmp',
            'Component': 'Cmp',
            'database': 'db',
            'Database': 'DB',
            'API': 'api',
            'endpoint': 'ep',
            'Endpoint': 'Ep',
            'authentication': 'auth',
            'Authentication': 'Auth',
            'configuration': 'cfg',
            'Configuration': 'Cfg',
            'compression': 'cmprs',
            'Compression': 'Cmprs',
            'optimization': 'opt',
            'Optimization': 'Opt',
            'performance': 'perf',
            'Performance': 'Perf',

            # File extensions (keep as-is, these are safe with the dot prefix)
            '.py': '.ᵖʸ',
            '.js': '.ʲˢ',
            '.ts': '.ᵗˢ',
            # '.md': '.ᵐᵈ',  # Skip .md to avoid corrupting markdown
            '.json': '.ʲˢⁿ',
            '.yaml': '.ʸᵐˡ',
            '.sh': '.ˢʰ',

            # Common phrases
            'Not Started': 'NS',
            'In Progress': 'IP',
            'Complete': '✓',
            'Pending': 'PND',
            'Blocked': 'BLK',
            'the ': 'θ ',    # Very common word
            'that ': 'ð ',   # Very common word
            'this ': 'ϑ ',   # Very common word
            'with ': 'ω ',   # Very common word
            'from ': 'φ ',   # Very common word
            'will ': 'ψ ',   # Very common word
            'should ': 'ς ',
            'would ': 'ω ',
        }

        # ==================================================================
        # Reverse Mappings (for decompression)
        # ==================================================================

        self.structure_reverse = {v: k for k, v in self.structure_tokens.items()}
        self.phrase_reverse = {v: k for k, v in self.phrase_tokens.items()}

    def compress(self, text: str) -> Tuple[str, Dict[str, int]]:
        """
        Compress text using SLIM vocabulary.

        Args:
            text: Original markdown text

        Returns:
            Tuple of (compressed_text, stats_dict)
        """
        compressed = text
        stats = {
            'structure_replacements': 0,
            'phrase_replacements': 0,
            'original_length': len(text),
            'compressed_length': 0
        }

        # Pass 1: Structure tokens (order matters - longer patterns first)
        for pattern, token in sorted(
            self.structure_tokens.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            count = compressed.count(pattern)
            if count > 0:
                compressed = compressed.replace(pattern, token)
                stats['structure_replacements'] += count

        # Pass 2: Phrase tokens
        for phrase, token in sorted(
            self.phrase_tokens.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            count = compressed.count(phrase)
            if count > 0:
                compressed = compressed.replace(phrase, token)
                stats['phrase_replacements'] += count

        stats['compressed_length'] = len(compressed)
        stats['reduction_bytes'] = stats['original_length'] - stats['compressed_length']
        stats['reduction_percent'] = round(
            (stats['reduction_bytes'] / stats['original_length']) * 100,
            1
        ) if stats['original_length'] > 0 else 0

        return compressed, stats

    def decompress(self, compressed_text: str) -> str:
        """
        Decompress text by reversing SLIM vocabulary replacements.

        Args:
            compressed_text: Compressed markdown text

        Returns:
            Original markdown text
        """
        decompressed = compressed_text

        # Reverse pass 2: Phrase tokens first (reverse order of compression)
        for token, phrase in sorted(
            self.phrase_reverse.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            if token in decompressed:
                decompressed = decompressed.replace(token, phrase)

        # Reverse pass 1: Structure tokens
        for token, pattern in sorted(
            self.structure_reverse.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            if token in decompressed:
                decompressed = decompressed.replace(token, pattern)

        return decompressed

    def analyze_text(self, text: str) -> Dict[str, any]:
        """
        Analyze text to identify compression opportunities.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with pattern frequencies and potential savings
        """
        analysis = {
            'structure_opportunities': {},
            'phrase_opportunities': {},
            'total_potential_savings_bytes': 0
        }

        # Analyze structure patterns
        for pattern, token in self.structure_tokens.items():
            count = text.count(pattern)
            if count > 0:
                savings = (len(pattern) - len(token)) * count
                analysis['structure_opportunities'][pattern] = {
                    'count': count,
                    'token': token,
                    'savings_bytes': savings
                }
                analysis['total_potential_savings_bytes'] += savings

        # Analyze phrase patterns
        for phrase, token in self.phrase_tokens.items():
            count = text.count(phrase)
            if count > 0:
                savings = (len(phrase) - len(token)) * count
                analysis['phrase_opportunities'][phrase] = {
                    'count': count,
                    'token': token,
                    'savings_bytes': savings
                }
                analysis['total_potential_savings_bytes'] += savings

        # Calculate potential reduction
        original_size = len(text.encode('utf-8'))
        analysis['original_bytes'] = original_size
        analysis['potential_reduction_percent'] = round(
            (analysis['total_potential_savings_bytes'] / original_size) * 100,
            1
        ) if original_size > 0 else 0

        return analysis

    def get_vocabulary_size(self) -> Dict[str, int]:
        """Get vocabulary statistics."""
        return {
            'structure_tokens': len(self.structure_tokens),
            'phrase_tokens': len(self.phrase_tokens),
            'total_tokens': len(self.structure_tokens) + len(self.phrase_tokens)
        }


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SLIM Vocabulary Markdown Compressor"
    )
    parser.add_argument('command', choices=['compress', 'decompress', 'analyze'])
    parser.add_argument('input_file', help='Input markdown file')
    parser.add_argument('-o', '--output', help='Output file (default: <input>.slim or <input>.md)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    vocab = SlimVocabulary()

    # Read input
    with open(args.input_file, 'r') as f:
        text = f.read()

    if args.command == 'compress':
        compressed, stats = vocab.compress(text)

        # Determine output path
        if args.output:
            output_path = args.output
        else:
            output_path = args.input_file + '.slim'

        # Write output
        with open(output_path, 'w') as f:
            f.write(compressed)

        print(f"✅ Compressed: {args.input_file} → {output_path}")
        print(f"   Original: {stats['original_length']:,} bytes")
        print(f"   Compressed: {stats['compressed_length']:,} bytes")
        print(f"   Reduction: {stats['reduction_percent']}%")
        print(f"   Structure replacements: {stats['structure_replacements']}")
        print(f"   Phrase replacements: {stats['phrase_replacements']}")

    elif args.command == 'decompress':
        decompressed = vocab.decompress(text)

        # Determine output path
        if args.output:
            output_path = args.output
        else:
            output_path = args.input_file.replace('.slim', '')

        # Write output
        with open(output_path, 'w') as f:
            f.write(decompressed)

        print(f"✅ Decompressed: {args.input_file} → {output_path}")

    elif args.command == 'analyze':
        analysis = vocab.analyze_text(text)

        print(f"\n📊 SLIM Vocabulary Analysis: {args.input_file}")
        print(f"   Original size: {analysis['original_bytes']:,} bytes")
        print(f"   Potential savings: {analysis['total_potential_savings_bytes']:,} bytes ({analysis['potential_reduction_percent']}%)")

        if args.verbose:
            print(f"\n🏗️  Structure Opportunities (top 10):")
            structure_sorted = sorted(
                analysis['structure_opportunities'].items(),
                key=lambda x: x[1]['savings_bytes'],
                reverse=True
            )
            for pattern, data in structure_sorted[:10]:
                print(f"   '{pattern}' → '{data['token']}': {data['count']}x = {data['savings_bytes']} bytes")

            print(f"\n📝 Phrase Opportunities (top 10):")
            phrase_sorted = sorted(
                analysis['phrase_opportunities'].items(),
                key=lambda x: x[1]['savings_bytes'],
                reverse=True
            )
            for phrase, data in phrase_sorted[:10]:
                print(f"   '{phrase}' → '{data['token']}': {data['count']}x = {data['savings_bytes']} bytes")


if __name__ == "__main__":
    main()
