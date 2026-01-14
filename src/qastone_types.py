#!/usr/bin/env python3
"""
QA.Stone Data Types

Data classes and type definitions for the QA.Stone compression integration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class CompressedStone:
    """
    A QA.Stone containing compressed conversation.

    QA.Stone format wraps compressed content with progressive LOD layers
    and cryptographic verification (border hash).
    """

    # Border (QA.Stone metadata)
    hash: str                       # Border hash for verification
    author: str                     # author@wallet_hash
    created: str                    # ISO 8601 timestamp
    title: str                      # Human-readable title
    chain: Optional[str] = None     # Previous stone hash (for chaining)
    signature: Optional[str] = None # Ed25519 signature (optional)

    # Layers (Progressive LOD)
    lod5: str = ""                  # 50 tokens - summary
    lod4: str = ""                  # 200 tokens - key points
    lod3: str = ""                  # 500 tokens - outline
    lod2: Dict[str, Any] = field(default_factory=dict)  # Full compressed content + indexes

    # Wormholes (related stones)
    related: List[str] = field(default_factory=list)    # Related stone hashes
    parent: Optional[str] = None                        # Parent stone (for threads)

    # Compression metadata
    original_tokens: int = 0
    compressed_tokens: int = 0
    reduction_percent: float = 0.0

    # Index references
    indexes: Dict[str, str] = field(default_factory=dict)  # Index file paths

    # Session/Project metadata
    session_id: Optional[str] = None
    project_id: Optional[str] = None

    # Storage paths
    stone_path: Optional[str] = None      # Path to .qastone.json
    content_path: Optional[str] = None    # Path to .slim.indexed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "border": {
                "hash": self.hash,
                "author": self.author,
                "created": self.created,
                "title": self.title,
                "chain": self.chain,
                "signature": self.signature
            },
            "layers": {
                "lod5": self.lod5,
                "lod4": self.lod4,
                "lod3": self.lod3,
                "lod2": self.lod2
            },
            "wormholes": {
                "related": self.related,
                "parent": self.parent
            },
            "compression": {
                "original_tokens": self.original_tokens,
                "compressed_tokens": self.compressed_tokens,
                "reduction_percent": self.reduction_percent
            },
            "metadata": {
                "indexes": self.indexes,
                "session_id": self.session_id,
                "project_id": self.project_id
            },
            "storage": {
                "stone_path": self.stone_path,
                "content_path": self.content_path
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CompressedStone':
        """Create from dictionary."""
        border = data.get("border", {})
        layers = data.get("layers", {})
        wormholes = data.get("wormholes", {})
        compression = data.get("compression", {})
        metadata = data.get("metadata", {})
        storage = data.get("storage", {})

        return cls(
            hash=border.get("hash", ""),
            author=border.get("author", ""),
            created=border.get("created", ""),
            title=border.get("title", ""),
            chain=border.get("chain"),
            signature=border.get("signature"),
            lod5=layers.get("lod5", ""),
            lod4=layers.get("lod4", ""),
            lod3=layers.get("lod3", ""),
            lod2=layers.get("lod2", {}),
            related=wormholes.get("related", []),
            parent=wormholes.get("parent"),
            original_tokens=compression.get("original_tokens", 0),
            compressed_tokens=compression.get("compressed_tokens", 0),
            reduction_percent=compression.get("reduction_percent", 0.0),
            indexes=metadata.get("indexes", {}),
            session_id=metadata.get("session_id"),
            project_id=metadata.get("project_id"),
            stone_path=storage.get("stone_path"),
            content_path=storage.get("content_path")
        )


@dataclass
class SearchMatch:
    """A single search match within a stone."""
    line_number: int
    match_text: str
    context_before: str
    context_after: str
    relevance_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "line": self.line_number,
            "text": self.match_text,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "relevance": self.relevance_score
        }


@dataclass
class SearchResult:
    """
    Result from searching a compressed stone.

    Uses selective decompression to search without full load.
    """
    stone_hash: str
    query: str
    total_matches: int
    matches: List[SearchMatch] = field(default_factory=list)
    tokens_used: int = 0
    tokens_saved: int = 0
    savings_percent: float = 0.0
    search_time_seconds: float = 0.0

    def expand_match(self, index: int, context_lines: int = 10) -> SearchMatch:
        """
        Expand a specific match with more context.

        This would trigger selective decompression of the surrounding area.
        For now, returns the existing match.
        """
        if 0 <= index < len(self.matches):
            return self.matches[index]
        raise IndexError(f"Match index {index} out of range (0-{len(self.matches)-1})")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stone_hash": self.stone_hash,
            "query": self.query,
            "total_matches": self.total_matches,
            "matches": [m.to_dict() for m in self.matches],
            "tokens_used": self.tokens_used,
            "tokens_saved": self.tokens_saved,
            "savings_percent": self.savings_percent,
            "search_time_seconds": self.search_time_seconds
        }


@dataclass
class LODGenerationResult:
    """Result from generating LOD layers."""
    lod5: str  # 50 tokens - summary
    lod4: str  # 200 tokens - key points
    lod3: str  # 500 tokens - outline
    generation_method: str = "auto"  # auto, manual, fallback
    tokens_used: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "lod5": self.lod5,
            "lod4": self.lod4,
            "lod3": self.lod3,
            "generation_method": self.generation_method,
            "tokens_used": self.tokens_used
        }


@dataclass
class StoneVerificationResult:
    """Result from verifying a stone's integrity."""
    is_valid: bool
    stone_hash: str
    computed_hash: str
    issues: List[str] = field(default_factory=list)
    chain_verified: bool = False
    signature_verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "stone_hash": self.stone_hash,
            "computed_hash": self.computed_hash,
            "issues": self.issues,
            "chain_verified": self.chain_verified,
            "signature_verified": self.signature_verified
        }
