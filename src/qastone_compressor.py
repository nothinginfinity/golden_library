#!/usr/bin/env python3
"""
QA.Stone Compressor

Wraps golden_library compression with QA.Stone format for verified,
progressive, federated context sharing.

Key features:
- Compress conversations as verified QA.Stones
- Progressive LOD layers (5→4→3→2)
- Border hash verification
- Selective decompression integration
- Cross-terminal sharing via inbox
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from unified_pipeline import UnifiedCompressionPipeline, CompressionResult
from conversation_searcher import ConversationSearcher
from token_analyzer import TokenAnalyzer
from qastone_types import (
    CompressedStone,
    SearchResult,
    SearchMatch,
    LODGenerationResult,
    StoneVerificationResult
)


class QAStoneCompressor:
    """
    Compress conversations as verified QA.Stones.

    Integrates golden_library compression with QA.Stone protocol for
    token-efficient context sharing with cryptographic verification.
    """

    def __init__(
        self,
        compression_level: str = "balanced",
        stones_dir: Optional[str] = None
    ):
        """
        Initialize QA.Stone compressor.

        Args:
            compression_level: "minimal", "balanced", or "maximum"
            stones_dir: Directory for storing stones (default: ~/.fsl/stones/)
        """
        self.compression_level = compression_level
        self.pipeline = UnifiedCompressionPipeline(level=compression_level)
        self.token_analyzer = TokenAnalyzer()
        self.searcher = ConversationSearcher()

        # Set stones directory
        if stones_dir is None:
            self.stones_dir = Path("~/.fsl/stones").expanduser()
        else:
            self.stones_dir = Path(stones_dir).expanduser()

        # Create directory if it doesn't exist
        self.stones_dir.mkdir(parents=True, exist_ok=True)

    def compress_as_stone(
        self,
        conversation_jsonl: str,
        author: str,
        title: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        chain_prev: Optional[str] = None,
        parent: Optional[str] = None,
        related: Optional[List[str]] = None
    ) -> CompressedStone:
        """
        Compress conversation and wrap as QA.Stone.

        Flow:
        1. Compress with UnifiedCompressionPipeline
        2. Generate progressive LOD layers (5→4→3→2)
        3. Compute border hash
        4. Save to filesystem

        Args:
            conversation_jsonl: JSONL conversation content (string or path)
            author: Author identifier (e.g., "koda@wallet_hash")
            title: Human-readable title
            session_id: Session ID for hot index
            project_id: Project ID for warm index
            chain_prev: Previous stone hash (for chaining)
            parent: Parent stone hash (for threading)
            related: List of related stone hashes

        Returns:
            CompressedStone object with all metadata
        """
        print(f"\n🪨 Compressing as QA.Stone: {title}")
        print(f"   Author: {author}")

        # Handle input - check if it's a path or content
        if Path(conversation_jsonl).exists():
            jsonl_path = conversation_jsonl
            with open(jsonl_path, 'r') as f:
                jsonl_content = f.read()
        else:
            # It's content, write to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp:
                tmp.write(conversation_jsonl)
                jsonl_path = tmp.name
                jsonl_content = conversation_jsonl

        # Step 1: Compress with pipeline
        print("\n📦 Step 1: Compressing with golden_library pipeline...")
        compression_result = self.pipeline.compress_conversation(
            jsonl_path,
            output_dir=str(self.stones_dir),
            session_id=session_id,
            project_id=project_id
        )

        # Read compressed content
        with open(compression_result.output_path, 'r') as f:
            compressed_content = f.read()

        # Step 2: Generate LOD layers
        print("\n🔍 Step 2: Generating LOD layers...")
        lod_result = self._generate_lod_layers(
            jsonl_content,
            compressed_content,
            title,
            compression_result
        )

        # Step 3: Create stone object
        print("\n🏗️  Step 3: Creating stone object...")
        created_timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        stone = CompressedStone(
            hash="",  # Will be computed
            author=author,
            created=created_timestamp,
            title=title,
            chain=chain_prev,
            signature=None,  # Phase 2
            lod5=lod_result.lod5,
            lod4=lod_result.lod4,
            lod3=lod_result.lod3,
            lod2={
                "compressed_content": compressed_content,
                "compression_level": self.compression_level,
                "original_path": compression_result.original_path,
                "output_path": compression_result.output_path
            },
            related=related or [],
            parent=parent,
            original_tokens=compression_result.original_tokens,
            compressed_tokens=compression_result.final_tokens,
            reduction_percent=compression_result.total_reduction_percent,
            indexes=compression_result.indexes_created,
            session_id=session_id,
            project_id=project_id
        )

        # Step 4: Compute border hash
        print("\n🔐 Step 4: Computing border hash...")
        stone.hash = self._compute_border_hash(stone)

        # Step 5: Save to filesystem
        print("\n💾 Step 5: Saving to filesystem...")
        self._save_stone(stone, compression_result.output_path)

        print(f"\n✅ Stone created successfully!")
        print(f"   Hash: {stone.hash}")
        print(f"   Reduction: {stone.reduction_percent}%")
        print(f"   Original: {stone.original_tokens:,} tokens")
        print(f"   Compressed: {stone.compressed_tokens:,} tokens")

        return stone

    def _generate_lod_layers(
        self,
        original_content: str,
        compressed_content: str,
        title: str,
        compression_result: CompressionResult
    ) -> LODGenerationResult:
        """
        Generate progressive LOD layers.

        LOD5: 50 tokens - summary
        LOD4: 200 tokens - key points
        LOD3: 500 tokens - outline

        For Phase 1, uses simple extraction from original content.
        Phase 2 could use LLM for better summaries.
        """
        lines = original_content.strip().split('\n')

        # LOD5: Title + basic stats (50 tokens)
        lod5 = f"{title} - {compression_result.original_tokens:,} tokens compressed to {compression_result.final_tokens:,} ({compression_result.total_reduction_percent}% reduction)"

        # LOD4: Title + stats + stage breakdown (200 tokens)
        stage_summary = ", ".join([
            f"{stage.stage_name}: {stage.reduction_percent}%"
            for stage in compression_result.stages
        ])
        lod4 = f"{lod5}\n\nCompression stages: {stage_summary}"

        # Count actual tokens
        lod5_tokens = self.token_analyzer.count_tokens(lod5)
        lod4_tokens = self.token_analyzer.count_tokens(lod4)

        # LOD3: More detailed outline (500 tokens)
        # Extract first few message summaries
        lod3_parts = [lod4, "\n\nConversation outline:"]

        message_count = 0
        for line in lines[:20]:  # First 20 lines
            if line.strip():
                try:
                    msg = json.loads(line)
                    role = msg.get('role', 'unknown')
                    content_preview = str(msg.get('content', ''))[:100]
                    lod3_parts.append(f"- {role}: {content_preview}...")
                    message_count += 1
                except:
                    continue

        lod3 = "\n".join(lod3_parts)
        lod3_tokens = self.token_analyzer.count_tokens(lod3)

        # Truncate if needed to stay within limits
        if lod5_tokens > 60:
            lod5 = title[:100]  # Fallback to just title
        if lod4_tokens > 220:
            lod4 = f"{title} - Compression: {compression_result.total_reduction_percent}%"
        if lod3_tokens > 550:
            lod3 = lod4 + "\n\nDetailed outline available in LOD2"

        print(f"   LOD5: ~{self.token_analyzer.count_tokens(lod5)} tokens")
        print(f"   LOD4: ~{self.token_analyzer.count_tokens(lod4)} tokens")
        print(f"   LOD3: ~{self.token_analyzer.count_tokens(lod3)} tokens")

        return LODGenerationResult(
            lod5=lod5,
            lod4=lod4,
            lod3=lod3,
            generation_method="auto",
            tokens_used={
                "lod5": self.token_analyzer.count_tokens(lod5),
                "lod4": self.token_analyzer.count_tokens(lod4),
                "lod3": self.token_analyzer.count_tokens(lod3)
            }
        )

    def _compute_border_hash(self, stone: CompressedStone) -> str:
        """
        Compute SHA-256 hash of canonical border data.

        Border data includes:
        - author
        - created timestamp
        - title
        - lod5 content
        - chain (previous stone hash)

        Returns first 16 characters of hex digest.
        """
        border_data = {
            "author": stone.author,
            "created": stone.created,
            "title": stone.title,
            "lod5": stone.lod5,
            "chain": stone.chain
        }

        # Create canonical JSON (sorted keys)
        canonical = json.dumps(border_data, sort_keys=True)

        # Compute SHA-256
        hash_digest = hashlib.sha256(canonical.encode()).hexdigest()

        # Return first 16 characters (64 bits)
        return hash_digest[:16]

    def _save_stone(self, stone: CompressedStone, compressed_file_path: str):
        """
        Save stone to filesystem.

        Creates:
        - {hash}.qastone.json - Stone metadata
        - {hash}.slim.indexed - Compressed content (copy of existing)
        """
        stone_hash = stone.hash

        # Paths
        metadata_path = self.stones_dir / f"{stone_hash}.qastone.json"
        content_path = self.stones_dir / f"{stone_hash}.slim.indexed"

        # Update stone with paths
        stone.stone_path = str(metadata_path)
        stone.content_path = str(content_path)

        # Save metadata
        with open(metadata_path, 'w') as f:
            json.dump(stone.to_dict(), f, indent=2)

        # Copy compressed content
        import shutil
        shutil.copy2(compressed_file_path, content_path)

        print(f"   Metadata: {metadata_path}")
        print(f"   Content: {content_path}")

    def get_stone(
        self,
        stone_hash: str,
        lod: int = 5
    ) -> str:
        """
        Get stone content at specific LOD level.

        Args:
            stone_hash: Stone hash identifier
            lod: LOD level (5, 4, 3, or 2)

        Returns:
            Content at specified LOD level
        """
        if lod not in [5, 4, 3, 2]:
            raise ValueError(f"Invalid LOD level: {lod}. Must be 2, 3, 4, or 5")

        # Load stone metadata
        stone = self._load_stone(stone_hash)

        # Return appropriate LOD
        if lod == 5:
            return stone.lod5
        elif lod == 4:
            return stone.lod4
        elif lod == 3:
            return stone.lod3
        elif lod == 2:
            # Load compressed content
            with open(stone.content_path, 'r') as f:
                return f.read()

    def verify_stone(self, stone_hash: str) -> StoneVerificationResult:
        """
        Verify stone border hash integrity.

        Args:
            stone_hash: Stone hash to verify

        Returns:
            StoneVerificationResult with verification status
        """
        try:
            # Load stone
            stone = self._load_stone(stone_hash)

            # Compute hash
            computed_hash = self._compute_border_hash(stone)

            # Verify
            is_valid = computed_hash == stone.hash

            issues = []
            if not is_valid:
                issues.append(f"Hash mismatch: expected {stone.hash}, got {computed_hash}")

            return StoneVerificationResult(
                is_valid=is_valid,
                stone_hash=stone_hash,
                computed_hash=computed_hash,
                issues=issues,
                chain_verified=False,  # Phase 2
                signature_verified=False  # Phase 2
            )

        except Exception as e:
            return StoneVerificationResult(
                is_valid=False,
                stone_hash=stone_hash,
                computed_hash="",
                issues=[f"Verification failed: {str(e)}"]
            )

    def search_stone(
        self,
        stone_hash: str,
        query: str,
        preview_context: int = 5,
        auto_expand: bool = False
    ) -> SearchResult:
        """
        Search compressed stone without full decompression.

        Uses ConversationSearcher for selective decompression with 95%+ token savings.

        Args:
            stone_hash: Stone hash to search
            query: Search query
            preview_context: Number of context lines around matches
            auto_expand: If True, resolve $refs in matches immediately

        Returns:
            SearchResult with matches and token savings
        """
        start_time = datetime.now()

        # Load stone
        stone = self._load_stone(stone_hash)

        # Use ConversationSearcher for efficient selective decompression
        search_result = self.searcher.search(
            query=query,
            files=[stone.content_path],
            preview_context=preview_context,
            auto_expand=auto_expand,
            case_sensitive=False,
            indexes=["cold", "warm", "hot"]
        )

        # Convert ConversationSearcher SearchMatch to our SearchMatch
        our_matches = []
        for match in search_result.matches:
            our_match = SearchMatch(
                line_number=match.line_number,
                match_text=match.match_text,
                context_before=match.context_before,
                context_after=match.context_after,
                relevance_score=1.0 if match.resolved else 0.8
            )
            our_matches.append(our_match)

        # Calculate actual token savings vs full decompression
        tokens_used = search_result.tokens_used
        tokens_saved = stone.original_tokens - tokens_used
        savings_percent = round((tokens_saved / stone.original_tokens) * 100, 1) if stone.original_tokens > 0 else 0

        search_time = (datetime.now() - start_time).total_seconds()

        return SearchResult(
            stone_hash=stone_hash,
            query=query,
            total_matches=len(our_matches),
            matches=our_matches,
            tokens_used=tokens_used,
            tokens_saved=tokens_saved,
            savings_percent=savings_percent,
            search_time_seconds=search_time
        )

    def expand_stone_section(
        self,
        stone_hash: str,
        start_line: int,
        end_line: int,
        resolve_refs: bool = True
    ) -> str:
        """
        Expand specific section of stone with selective decompression.

        Resolves $refs on-demand using indexes for token-efficient expansion.

        Args:
            stone_hash: Stone hash
            start_line: Start line number (1-indexed)
            end_line: End line number (1-indexed)
            resolve_refs: Whether to resolve $refs in this section (default: True)

        Returns:
            Expanded section content with $refs resolved if requested
        """
        # Load stone
        stone = self._load_stone(stone_hash)

        # Use ConversationSearcher's preview_file for selective section expansion
        expanded_section = self.searcher.preview_file(
            stone.content_path,
            start_line=start_line - 1,  # Convert to 0-indexed
            end_line=end_line,
            resolve_refs=resolve_refs,
            indexes=["cold", "warm", "hot"]
        )

        return expanded_section

    def send_to_inbox(
        self,
        stone_hash: str,
        target_terminal: str,
        objective: str,
        priority: str = "M",
        sender: str = "K"
    ) -> str:
        """
        Send stone reference to terminal's inbox.

        Creates nano-format message: §T:TARGET§o:objective§p:priority§stone:hash§from:SENDER§

        Args:
            stone_hash: Stone hash to send
            target_terminal: Target terminal ID (A, B, D, H)
            objective: Objective description
            priority: Priority level (H, M, L)
            sender: Sender terminal ID

        Returns:
            Nano-format message string
        """
        # Create nano-format message
        message = f"§T:{target_terminal}§o:{objective}§p:{priority}§stone:{stone_hash}§from:{sender}§"

        # Write to inbox file
        inbox_path = Path(f"~/.fsl/collab/inbox_{target_terminal.lower()}.fsl").expanduser()
        inbox_path.parent.mkdir(parents=True, exist_ok=True)

        # Append message
        with open(inbox_path, 'a') as f:
            f.write(message + '\n')

        print(f"\n📬 Message sent to {target_terminal}'s inbox")
        print(f"   {message}")

        return message

    def list_stones(
        self,
        author: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[CompressedStone]:
        """
        List all stones in the stones directory.

        Args:
            author: Filter by author
            project_id: Filter by project

        Returns:
            List of CompressedStone objects
        """
        stones = []

        for metadata_file in self.stones_dir.glob("*.qastone.json"):
            try:
                with open(metadata_file, 'r') as f:
                    data = json.load(f)

                stone = CompressedStone.from_dict(data)

                # Apply filters
                if author and stone.author != author:
                    continue
                if project_id and stone.project_id != project_id:
                    continue

                stones.append(stone)

            except Exception as e:
                print(f"⚠️  Failed to load {metadata_file}: {e}")

        # Sort by creation time (newest first)
        stones.sort(key=lambda s: s.created, reverse=True)

        return stones

    def verify_chain(self, stone_hash: str) -> bool:
        """
        Verify entire stone chain integrity.

        Traverses chain field backwards, verifying each stone's border hash.

        Args:
            stone_hash: Starting stone hash

        Returns:
            True if entire chain is valid, False otherwise
        """
        current_hash = stone_hash

        while current_hash:
            # Verify this stone
            result = self.verify_stone(current_hash)
            if not result.is_valid:
                return False

            # Load stone to get chain reference
            try:
                stone = self._load_stone(current_hash)
                current_hash = stone.chain  # Move to previous stone
            except FileNotFoundError:
                # Chain reference points to non-existent stone
                if current_hash:
                    return False
                break

        return True

    def get_chain(self, stone_hash: str) -> List[CompressedStone]:
        """
        Get full chain of stones.

        Traverses chain field backwards, returning all stones in order
        from newest (given hash) to oldest (first stone).

        Args:
            stone_hash: Starting stone hash

        Returns:
            List of CompressedStone objects in chain order (newest first)
        """
        chain = []
        current_hash = stone_hash

        while current_hash:
            try:
                stone = self._load_stone(current_hash)
                chain.append(stone)
                current_hash = stone.chain
            except FileNotFoundError:
                # Chain broken - return what we have
                break

        return chain

    def search_chain(
        self,
        stone_hash: str,
        query: str,
        preview_context: int = 5
    ) -> List[SearchResult]:
        """
        Search entire stone chain.

        Args:
            stone_hash: Starting stone hash
            query: Search query
            preview_context: Context lines around matches

        Returns:
            List of SearchResult objects, one per stone in chain
        """
        chain = self.get_chain(stone_hash)
        results = []

        for stone in chain:
            result = self.search_stone(stone.hash, query, preview_context)
            if result.total_matches > 0:
                results.append(result)

        return results

    def _load_stone(self, stone_hash: str) -> CompressedStone:
        """Load stone from filesystem."""
        metadata_path = self.stones_dir / f"{stone_hash}.qastone.json"

        if not metadata_path.exists():
            raise FileNotFoundError(f"Stone not found: {stone_hash}")

        with open(metadata_path, 'r') as f:
            data = json.load(f)

        return CompressedStone.from_dict(data)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="QA.Stone Compression CLI"
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Compress command
    compress_parser = subparsers.add_parser('compress', help='Compress conversation as stone')
    compress_parser.add_argument('input', help='Input JSONL file')
    compress_parser.add_argument('--author', required=True, help='Author (e.g., koda@wallet)')
    compress_parser.add_argument('--title', required=True, help='Stone title')
    compress_parser.add_argument('--session-id', help='Session ID')
    compress_parser.add_argument('--project-id', help='Project ID')
    compress_parser.add_argument('--level', default='balanced', choices=['minimal', 'balanced', 'maximum'])

    # Get command
    get_parser = subparsers.add_parser('get', help='Get stone at LOD level')
    get_parser.add_argument('hash', help='Stone hash')
    get_parser.add_argument('--lod', type=int, default=5, choices=[2, 3, 4, 5])

    # Search command
    search_parser = subparsers.add_parser('search', help='Search stone')
    search_parser.add_argument('hash', help='Stone hash')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--context', type=int, default=5, help='Context lines')

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify stone integrity')
    verify_parser.add_argument('hash', help='Stone hash')

    # List command
    list_parser = subparsers.add_parser('list', help='List stones')
    list_parser.add_argument('--author', help='Filter by author')
    list_parser.add_argument('--project', help='Filter by project')

    # Send command
    send_parser = subparsers.add_parser('send', help='Send stone to inbox')
    send_parser.add_argument('hash', help='Stone hash')
    send_parser.add_argument('--target', required=True, help='Target terminal (A/B/D/H)')
    send_parser.add_argument('--objective', required=True, help='Objective description')
    send_parser.add_argument('--priority', default='M', choices=['H', 'M', 'L'])

    # Expand command
    expand_parser = subparsers.add_parser('expand', help='Expand stone section')
    expand_parser.add_argument('hash', help='Stone hash')
    expand_parser.add_argument('start', type=int, help='Start line')
    expand_parser.add_argument('end', type=int, help='End line')
    expand_parser.add_argument('--no-resolve', action='store_true', help='Do not resolve $refs')

    # Verify chain command
    verify_chain_parser = subparsers.add_parser('verify-chain', help='Verify stone chain')
    verify_chain_parser.add_argument('hash', help='Stone hash')

    # Get chain command
    get_chain_parser = subparsers.add_parser('get-chain', help='Get stone chain')
    get_chain_parser.add_argument('hash', help='Stone hash')

    # Search chain command
    search_chain_parser = subparsers.add_parser('search-chain', help='Search stone chain')
    search_chain_parser.add_argument('hash', help='Stone hash')
    search_chain_parser.add_argument('query', help='Search query')
    search_chain_parser.add_argument('--context', type=int, default=5, help='Context lines')

    args = parser.parse_args()

    compressor = QAStoneCompressor(compression_level=getattr(args, 'level', 'balanced'))

    if args.command == 'compress':
        stone = compressor.compress_as_stone(
            args.input,
            author=args.author,
            title=args.title,
            session_id=args.session_id,
            project_id=args.project_id
        )
        print(f"\n✅ Stone hash: {stone.hash}")

    elif args.command == 'get':
        content = compressor.get_stone(args.hash, lod=args.lod)
        print(content)

    elif args.command == 'search':
        result = compressor.search_stone(args.hash, args.query, preview_context=args.context)
        print(f"\n🔍 Search Results")
        print(f"   Query: {result.query}")
        print(f"   Matches: {result.total_matches}")
        print(f"   Tokens used: {result.tokens_used:,} (saved {result.savings_percent}%)")
        for i, match in enumerate(result.matches):
            print(f"\n   Match {i+1} (line {match.line_number}):")
            print(f"   {match.match_text}")

    elif args.command == 'verify':
        result = compressor.verify_stone(args.hash)
        if result.is_valid:
            print(f"✅ Stone verified: {args.hash}")
        else:
            print(f"❌ Verification failed:")
            for issue in result.issues:
                print(f"   - {issue}")

    elif args.command == 'list':
        stones = compressor.list_stones(author=args.author, project_id=args.project)
        print(f"\n📚 Stones ({len(stones)} found)")
        for stone in stones:
            print(f"\n   {stone.hash}")
            print(f"   Title: {stone.title}")
            print(f"   Author: {stone.author}")
            print(f"   Created: {stone.created}")
            print(f"   Reduction: {stone.reduction_percent}%")

    elif args.command == 'send':
        message = compressor.send_to_inbox(
            args.hash,
            target_terminal=args.target,
            objective=args.objective,
            priority=args.priority
        )

    elif args.command == 'expand':
        section = compressor.expand_stone_section(
            args.hash,
            start_line=args.start,
            end_line=args.end,
            resolve_refs=not args.no_resolve
        )
        print(section)

    elif args.command == 'verify-chain':
        is_valid = compressor.verify_chain(args.hash)
        if is_valid:
            print(f"✅ Chain verified: {args.hash}")
        else:
            print(f"❌ Chain verification failed: {args.hash}")

    elif args.command == 'get-chain':
        chain = compressor.get_chain(args.hash)
        print(f"\n🔗 Chain ({len(chain)} stones)")
        for i, stone in enumerate(chain):
            print(f"\n   {i+1}. {stone.hash}")
            print(f"      Title: {stone.title}")
            print(f"      Author: {stone.author}")
            print(f"      Created: {stone.created}")

    elif args.command == 'search-chain':
        results = compressor.search_chain(args.hash, args.query, preview_context=args.context)
        print(f"\n🔍 Chain Search Results")
        print(f"   Query: {args.query}")
        print(f"   Stones with matches: {len(results)}")
        for result in results:
            print(f"\n   Stone: {result.stone_hash}")
            print(f"   Matches: {result.total_matches}")
            print(f"   Token savings: {result.savings_percent}%")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
