#!/usr/bin/env python3
"""
PRD Compressor - LLM-Friendly Plan Management

Compresses markdown PRD files (CURRENT_PLAN.md, specs) for token-efficient handoffs.
Implements the handoff:// protocol for cross-instance context sharing.

Usage:
    python3 -m golden_library.prd_compressor compress CURRENT_PLAN.md
    python3 -m golden_library.prd_compressor decompress handoff://8e3556e
    python3 -m golden_library.prd_compressor search "websocket"
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import re


class PRDCompressor:
    """
    Compress PRD markdown files for efficient LLM handoffs.

    Features:
    - SLIM-like compression for markdown
    - handoff:// protocol
    - Searchable index
    - Cross-repo references
    """

    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize PRD compressor.

        Args:
            repo_path: Path to repository root (auto-detect if None)
        """
        self.repo_path = repo_path or self._find_repo_root()
        self.golden_dir = self.repo_path / ".golden_library"
        self.compressed_dir = self.golden_dir / "compressed"
        self.metadata_dir = self.golden_dir / "metadata"
        self.index_file = self.golden_dir / "index.json"

        # Ensure directories exist
        self.compressed_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # Load or create index
        self.index = self._load_index()

    def _find_repo_root(self) -> Path:
        """Find repository root by looking for .golden_library or .git."""
        current = Path.cwd()

        while current != current.parent:
            if (current / ".golden_library").exists() or (current / ".git").exists():
                return current
            current = current.parent

        # Fallback to cwd
        return Path.cwd()

    def _load_index(self) -> Dict[str, Any]:
        """Load index from disk."""
        if self.index_file.exists():
            return json.loads(self.index_file.read_text())
        else:
            return {
                "version": "1.0",
                "repository": str(self.repo_path),
                "created": datetime.now().isoformat(),
                "handoffs": []
            }

    def _save_index(self):
        """Save index to disk."""
        self.index["last_updated"] = datetime.now().isoformat()
        self.index_file.write_text(json.dumps(self.index, indent=2))

    def _generate_handoff_id(self, content: str) -> str:
        """Generate handoff ID from content hash."""
        hash_obj = hashlib.sha256(content.encode())
        return hash_obj.hexdigest()[:12]

    def _compress_markdown(self, content: str) -> str:
        """
        Compress markdown using SLIM-like techniques.

        Strategies:
        1. Remove excessive whitespace
        2. Compress repeated patterns
        3. Store metadata separately
        4. Tokenize common phrases
        """
        compressed = content

        # Remove excessive blank lines (3+ → 2)
        compressed = re.sub(r'\n{3,}', '\n\n', compressed)

        # Compress horizontal rules
        compressed = re.sub(r'-{3,}', '---', compressed)

        # Compress checkbox syntax
        compressed = compressed.replace('- [ ]', '-[ ]')
        compressed = compressed.replace('- [x]', '-[x]')
        compressed = compressed.replace('- [X]', '-[X]')

        # Store common phrases as tokens (basic version)
        # TODO: Implement full SLIM vocabulary

        return compressed

    def _decompress_markdown(self, compressed: str, metadata: Dict[str, Any]) -> str:
        """
        Decompress markdown.

        Args:
            compressed: Compressed markdown content
            metadata: Handoff metadata

        Returns:
            Original markdown content
        """
        # For now, compression is light, so decompression is simple
        decompressed = compressed

        # Restore checkbox syntax
        decompressed = decompressed.replace('-[ ]', '- [ ]')
        decompressed = decompressed.replace('-[x]', '- [x]')
        decompressed = decompressed.replace('-[X]', '- [X]')

        return decompressed

    def compress(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compress a markdown file.

        Args:
            file_path: Path to markdown file
            metadata: Optional metadata (phase, tags, etc.)

        Returns:
            {
                "ok": True,
                "handoff_id": "8e3556e",
                "original_size": 15000,
                "compressed_size": 12000,
                "reduction_percent": 20,
                "handoff_path": ".golden_library/compressed/8e3556e.md",
                "metadata_path": ".golden_library/metadata/8e3556e.json"
            }
        """
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}

        # Resolve absolute path
        path = path.resolve()

        # Read original
        original_content = path.read_text()
        original_size = len(original_content.encode())

        # Generate handoff ID
        handoff_id = self._generate_handoff_id(original_content)

        # Check if already compressed
        compressed_path = self.compressed_dir / f"{handoff_id}.md"
        if compressed_path.exists():
            return {
                "ok": True,
                "handoff_id": handoff_id,
                "message": "Already compressed",
                "handoff_path": str(compressed_path.relative_to(self.repo_path)),
                "protocol": f"handoff://{handoff_id}"
            }

        # Compress
        compressed_content = self._compress_markdown(original_content)
        compressed_size = len(compressed_content.encode())

        # Calculate reduction
        reduction_percent = round((1 - compressed_size / original_size) * 100, 1)

        # Write compressed file
        compressed_path.write_text(compressed_content)

        # Extract metadata from markdown
        extracted_metadata = self._extract_metadata(original_content, path)

        # Calculate relative path (or use absolute if outside repo)
        try:
            relative_path = str(path.relative_to(self.repo_path))
        except ValueError:
            relative_path = str(path)

        # Merge with provided metadata
        full_metadata = {
            "handoff_id": handoff_id,
            "original_file": relative_path,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "reduction_percent": reduction_percent,
            "created": datetime.now().isoformat(),
            "compression_format": "markdown_slim",
            **(metadata or {}),
            **extracted_metadata
        }

        # Write metadata
        metadata_path = self.metadata_dir / f"{handoff_id}.json"
        metadata_path.write_text(json.dumps(full_metadata, indent=2))

        # Update index
        self.index["handoffs"].append(full_metadata)
        self._save_index()

        return {
            "ok": True,
            "handoff_id": handoff_id,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "reduction_percent": reduction_percent,
            "handoff_path": str(compressed_path.relative_to(self.repo_path)),
            "metadata_path": str(metadata_path.relative_to(self.repo_path)),
            "protocol": f"handoff://{handoff_id}"
        }

    def _extract_metadata(self, content: str, path: Path) -> Dict[str, Any]:
        """
        Extract metadata from markdown front matter.

        Looks for YAML front matter:
        ---
        phase: 4
        status: active
        ---
        """
        metadata = {}

        # Check for YAML front matter
        lines = content.split('\n')
        if lines[0].strip() == '---':
            # Find closing ---
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == '---':
                    # Parse YAML-like front matter
                    front_matter = '\n'.join(lines[1:i])
                    for fm_line in front_matter.split('\n'):
                        if ':' in fm_line:
                            key, value = fm_line.split(':', 1)
                            key = key.strip().replace('**', '').replace('*', '')
                            value = value.strip()

                            # Parse common keys
                            if key.lower() in ['phase', 'phase name', 'status', 'started',
                                              'estimated duration', 'previous handoff', 'dependencies']:
                                metadata[key.lower().replace(' ', '_')] = value
                    break

        # Extract title from first H1
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata['title'] = title_match.group(1)

        # Extract file type
        metadata['file_type'] = path.suffix.lstrip('.')
        metadata['filename'] = path.name

        return metadata

    def decompress(
        self,
        handoff_id: str,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Decompress a handoff.

        Args:
            handoff_id: Handoff ID (with or without handoff:// prefix)
            output_path: Where to write decompressed file (optional)

        Returns:
            {
                "ok": True,
                "handoff_id": "8e3556e",
                "content": "...",
                "metadata": {...},
                "output_path": "..."
            }
        """
        # Strip handoff:// prefix if present
        handoff_id = handoff_id.replace('handoff://', '')

        # Find compressed file
        compressed_path = self.compressed_dir / f"{handoff_id}.md"
        if not compressed_path.exists():
            return {"ok": False, "error": f"Handoff not found: {handoff_id}"}

        # Load metadata
        metadata_path = self.metadata_dir / f"{handoff_id}.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
        else:
            metadata = {}

        # Read compressed content
        compressed_content = compressed_path.read_text()

        # Decompress
        decompressed_content = self._decompress_markdown(compressed_content, metadata)

        # Write to output if requested
        if output_path:
            out_path = Path(output_path)
            out_path.write_text(decompressed_content)
        else:
            out_path = None

        return {
            "ok": True,
            "handoff_id": handoff_id,
            "content": decompressed_content,
            "metadata": metadata,
            "output_path": str(out_path) if out_path else None,
            "size": len(decompressed_content.encode())
        }

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search handoffs by query.

        Args:
            query: Search query
            filters: Optional filters (phase, status, file_type, etc.)

        Returns:
            {
                "ok": True,
                "query": "websocket",
                "results": [
                    {
                        "handoff_id": "...",
                        "title": "...",
                        "relevance": 0.95,
                        "snippet": "..."
                    }
                ]
            }
        """
        query_lower = query.lower()
        results = []

        for handoff_meta in self.index["handoffs"]:
            handoff_id = handoff_meta["handoff_id"]

            # Apply filters
            if filters:
                if 'phase' in filters and handoff_meta.get('phase') != filters['phase']:
                    continue
                if 'status' in filters and handoff_meta.get('status') != filters['status']:
                    continue
                if 'file_type' in filters and handoff_meta.get('file_type') != filters['file_type']:
                    continue

            # Search in metadata
            relevance = 0
            snippet = ""

            # Check title
            title = handoff_meta.get('title', '')
            if query_lower in title.lower():
                relevance += 0.5
                snippet = title

            # Check filename
            filename = handoff_meta.get('filename', '')
            if query_lower in filename.lower():
                relevance += 0.3

            # Search in content
            compressed_path = self.compressed_dir / f"{handoff_id}.md"
            if compressed_path.exists():
                content = compressed_path.read_text().lower()
                if query_lower in content:
                    relevance += 0.7

                    # Extract snippet
                    idx = content.index(query_lower)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query_lower) + 50)
                    snippet = "..." + content[start:end] + "..."

            if relevance > 0:
                results.append({
                    "handoff_id": handoff_id,
                    "protocol": f"handoff://{handoff_id}",
                    "title": title,
                    "filename": filename,
                    "relevance": round(relevance, 2),
                    "snippet": snippet[:200],
                    "metadata": handoff_meta
                })

        # Sort by relevance
        results.sort(key=lambda r: r['relevance'], reverse=True)

        return {
            "ok": True,
            "query": query,
            "count": len(results),
            "results": results
        }

    def list_handoffs(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List all handoffs.

        Args:
            filters: Optional filters

        Returns:
            {
                "ok": True,
                "count": 5,
                "handoffs": [...]
            }
        """
        handoffs = self.index["handoffs"]

        # Apply filters
        if filters:
            filtered = []
            for h in handoffs:
                matches = True
                for key, value in filters.items():
                    if h.get(key) != value:
                        matches = False
                        break
                if matches:
                    filtered.append(h)
            handoffs = filtered

        # Sort by created date (newest first)
        handoffs.sort(key=lambda h: h.get('created', ''), reverse=True)

        return {
            "ok": True,
            "count": len(handoffs),
            "handoffs": handoffs
        }

    def get_handoff(self, handoff_id: str) -> Dict[str, Any]:
        """
        Get handoff metadata.

        Args:
            handoff_id: Handoff ID

        Returns:
            Metadata dict or error
        """
        handoff_id = handoff_id.replace('handoff://', '')

        for handoff in self.index["handoffs"]:
            if handoff["handoff_id"] == handoff_id:
                return {
                    "ok": True,
                    **handoff
                }

        return {"ok": False, "error": f"Handoff not found: {handoff_id}"}


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    compressor = PRDCompressor()

    if command == "compress":
        if len(sys.argv) < 3:
            print("Usage: python3 -m golden_library.prd_compressor compress <file>")
            sys.exit(1)

        file_path = sys.argv[2]
        result = compressor.compress(file_path)

        if result["ok"]:
            print(f"✅ Compressed: {file_path}")
            print(f"   Handoff ID: {result['handoff_id']}")
            print(f"   Protocol: {result['protocol']}")
            if 'message' in result:
                print(f"   Status: {result['message']}")
            if 'original_size' in result:
                print(f"   Original: {result['original_size']} bytes")
                print(f"   Compressed: {result['compressed_size']} bytes")
                print(f"   Reduction: {result['reduction_percent']}%")
            print(f"   Path: {result['handoff_path']}")
        else:
            print(f"❌ Error: {result['error']}")
            sys.exit(1)

    elif command == "decompress":
        if len(sys.argv) < 3:
            print("Usage: python3 -m golden_library.prd_compressor decompress <handoff_id> [output_path]")
            sys.exit(1)

        handoff_id = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None

        result = compressor.decompress(handoff_id, output_path)

        if result["ok"]:
            print(f"✅ Decompressed: handoff://{result['handoff_id']}")
            print(f"   Size: {result['size']} bytes")
            if result['output_path']:
                print(f"   Output: {result['output_path']}")
            else:
                print(f"\n{result['content']}")
        else:
            print(f"❌ Error: {result['error']}")
            sys.exit(1)

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python3 -m golden_library.prd_compressor search <query>")
            sys.exit(1)

        query = sys.argv[2]
        result = compressor.search(query)

        if result["ok"]:
            print(f"🔍 Search: '{result['query']}'")
            print(f"   Found: {result['count']} results\n")

            for r in result["results"][:10]:  # Limit to top 10
                print(f"   📄 {r['title'] or r['filename']}")
                print(f"      ID: {r['protocol']}")
                print(f"      Relevance: {r['relevance']}")
                if r['snippet']:
                    print(f"      Snippet: {r['snippet']}")
                print()
        else:
            print(f"❌ Error: {result['error']}")
            sys.exit(1)

    elif command == "list":
        result = compressor.list_handoffs()

        if result["ok"]:
            print(f"📋 Handoffs: {result['count']}\n")

            for h in result["handoffs"]:
                print(f"   📄 {h.get('title') or h.get('filename', 'Untitled')}")
                print(f"      ID: handoff://{h['handoff_id']}")
                print(f"      Created: {h['created']}")
                if 'phase' in h:
                    print(f"      Phase: {h['phase']}")
                print()
        else:
            print(f"❌ Error: {result['error']}")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
