#!/usr/bin/env python3
"""
Handoff SLIM Integration
Compress Claude Code conversation JSONL files for efficient handoffs.

Flow:
1. User triggers: phi("prepare handoff")
2. Find current session JSONL
3. Convert to SLIM (50% reduction)
4. Optionally apply V4Z/FSL/ZTPCF compression
5. Package for next session
6. New session auto-decompresses on load
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib

from slim_converter import SlimConverter

# Try to import compression modules
try:
    import sys
    sys.path.append(str(Path.home() / "ztgi"))
    from v4z_encoder import compress_to_v4z
    HAS_V4Z = True
except ImportError:
    HAS_V4Z = False

try:
    from fsl_v7_ultimate import compress_to_fsl_v7
    HAS_FSL = False  # Not implemented yet
except ImportError:
    HAS_FSL = False

try:
    from ztpcf_pipeline import compress_to_ztpcf
    HAS_ZTPCF = False  # Not implemented yet
except ImportError:
    HAS_ZTPCF = False


class HandoffCompressor:
    """
    Compress conversation JSONL for handoffs.

    Compression stages:
    1. SLIM (schema-once) - ~50% reduction, lossless
    2. [Optional] V4Z/FSL/ZTPCF - additional 60-85% reduction
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.slim = SlimConverter()
        self.config = config or {
            "compression_level": "slim_only",  # slim_only, slim_v4z, slim_fsl, slim_ztpcf
            "preserve_original": True,  # Keep original JSONL as backup
            "compression_threshold": 1024,  # Only compress if >1KB
        }

        # Handoff storage
        self.handoff_dir = Path.home() / ".fsl" / "handoffs"
        self.handoff_dir.mkdir(parents=True, exist_ok=True)

    def compress_conversation(
        self,
        jsonl_path: str,
        compression_level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compress conversation JSONL.

        Args:
            jsonl_path: Path to conversation .jsonl file
            compression_level: Override config compression level

        Returns:
            {
                "handoff_id": "abc123",
                "original_size": 150000,
                "slim_size": 75000,
                "final_size": 30000,
                "compression_format": "slim_v4z",
                "reduction_percent": 80,
                "slim_path": "/path/to/handoff.slim",
                "compressed_path": "/path/to/handoff.slim.v4z",
                "original_preserved": true
            }
        """
        path = Path(jsonl_path)
        if not path.exists():
            return {"ok": False, "error": f"JSONL not found: {jsonl_path}"}

        original_size = path.stat().st_size

        # Check threshold
        if original_size < self.config["compression_threshold"]:
            return {
                "ok": False,
                "skipped": True,
                "reason": f"File too small ({original_size} bytes < {self.config['compression_threshold']})"
            }

        # Generate handoff ID
        handoff_id = self._generate_handoff_id(jsonl_path)

        # Stage 1: SLIM compression
        slim_content = self.slim.jsonl_to_slim(str(path))
        slim_size = len(slim_content.encode('utf-8'))

        # Save SLIM
        slim_path = self.handoff_dir / f"{handoff_id}.slim"
        slim_path.write_text(slim_content)

        # Preserve original if configured
        if self.config["preserve_original"]:
            original_backup = self.handoff_dir / f"{handoff_id}.jsonl.bak"
            shutil.copy(path, original_backup)

        # Stage 2: Additional compression (optional)
        compression_format = compression_level or self.config["compression_level"]
        final_path = slim_path
        final_size = slim_size

        if compression_format == "slim_v4z" and HAS_V4Z:
            compressed = compress_to_v4z(slim_content)
            v4z_path = self.handoff_dir / f"{handoff_id}.slim.v4z"
            v4z_path.write_text(compressed)
            final_path = v4z_path
            final_size = len(compressed.encode('utf-8'))

        elif compression_format == "slim_fsl" and HAS_FSL:
            compressed = compress_to_fsl_v7(slim_content)
            fsl_path = self.handoff_dir / f"{handoff_id}.slim.fsl"
            fsl_path.write_text(compressed)
            final_path = fsl_path
            final_size = len(compressed.encode('utf-8'))

        elif compression_format == "slim_ztpcf" and HAS_ZTPCF:
            compressed = compress_to_ztpcf(slim_content)
            ztpcf_path = self.handoff_dir / f"{handoff_id}.slim.ztpcf"
            ztpcf_path.write_bytes(compressed)
            final_path = ztpcf_path
            final_size = len(compressed)

        # Calculate stats
        reduction_percent = round((1 - final_size / original_size) * 100, 1) if original_size > 0 else 0

        # Save metadata
        metadata = {
            "handoff_id": handoff_id,
            "original_file": path.name,
            "original_size": original_size,
            "slim_size": slim_size,
            "final_size": final_size,
            "compression_format": compression_format,
            "reduction_percent": reduction_percent,
            "compression_ratio": round(original_size / final_size, 2) if final_size > 0 else 0,
            "created": datetime.now().isoformat(),
            "slim_path": str(slim_path),
            "final_path": str(final_path),
            "original_preserved": self.config["preserve_original"]
        }

        metadata_path = self.handoff_dir / f"{handoff_id}.meta.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))

        return {
            "ok": True,
            **metadata
        }

    def decompress_handoff(self, handoff_id: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Decompress handoff back to JSONL.

        Args:
            handoff_id: Handoff ID to decompress
            output_path: Where to write JSONL (optional)

        Returns:
            {
                "ok": true,
                "jsonl_path": "/path/to/output.jsonl",
                "decompression_ms": 250
            }
        """
        import time
        start = time.time()

        # Load metadata
        metadata_path = self.handoff_dir / f"{handoff_id}.meta.json"
        if not metadata_path.exists():
            return {"ok": False, "error": f"Handoff not found: {handoff_id}"}

        metadata = json.loads(metadata_path.read_text())
        compression_format = metadata["compression_format"]

        # Stage 1: Decompress to SLIM (if needed)
        if compression_format == "slim_only":
            slim_path = Path(metadata["slim_path"])
            slim_content = slim_path.read_text()

        elif compression_format == "slim_v4z":
            v4z_path = Path(metadata["final_path"])
            # TODO: Implement V4Z decompression
            slim_content = v4z_path.read_text()  # Placeholder

        elif compression_format == "slim_fsl":
            fsl_path = Path(metadata["final_path"])
            # TODO: Implement FSL decompression
            slim_content = fsl_path.read_text()  # Placeholder

        elif compression_format == "slim_ztpcf":
            ztpcf_path = Path(metadata["final_path"])
            # TODO: Implement ZTPCF decompression
            slim_content = ""  # Placeholder

        else:
            return {"ok": False, "error": f"Unknown compression format: {compression_format}"}

        # Stage 2: SLIM → JSONL
        jsonl_content = self.slim.slim_to_jsonl(slim_content)

        # Write output
        if output_path:
            out_path = Path(output_path)
        else:
            out_path = self.handoff_dir / f"{handoff_id}.restored.jsonl"

        out_path.write_text(jsonl_content)

        elapsed_ms = round((time.time() - start) * 1000)

        return {
            "ok": True,
            "handoff_id": handoff_id,
            "jsonl_path": str(out_path),
            "decompression_ms": elapsed_ms,
            "lines": len(jsonl_content.split("\n"))
        }

    def list_handoffs(self) -> Dict[str, Any]:
        """List all available handoffs."""
        handoffs = []

        for meta_file in self.handoff_dir.glob("*.meta.json"):
            metadata = json.loads(meta_file.read_text())
            handoffs.append(metadata)

        # Sort by creation time (newest first)
        handoffs.sort(key=lambda h: h.get("created", ""), reverse=True)

        return {
            "ok": True,
            "count": len(handoffs),
            "handoffs": handoffs
        }

    def get_handoff_stats(self, handoff_id: str) -> Dict[str, Any]:
        """Get detailed stats for a handoff."""
        metadata_path = self.handoff_dir / f"{handoff_id}.meta.json"
        if not metadata_path.exists():
            return {"ok": False, "error": f"Handoff not found: {handoff_id}"}

        metadata = json.loads(metadata_path.read_text())

        # Check file existence
        slim_exists = Path(metadata["slim_path"]).exists()
        final_exists = Path(metadata["final_path"]).exists()

        return {
            "ok": True,
            **metadata,
            "files": {
                "slim_exists": slim_exists,
                "final_exists": final_exists
            }
        }

    def _generate_handoff_id(self, jsonl_path: str) -> str:
        """Generate unique handoff ID from JSONL path and timestamp."""
        timestamp = datetime.now().isoformat()
        content = f"{jsonl_path}{timestamp}"
        hash_obj = hashlib.sha256(content.encode())
        return hash_obj.hexdigest()[:12]


# =============================================================================
# PHI INTEGRATION
# =============================================================================

def handle_handoff_slim_command(task: str, context: str = None) -> Dict[str, Any]:
    """
    Handle phi commands for SLIM handoffs.

    Commands:
        phi("handoff compress <jsonl_path>")
        phi("handoff compress <jsonl_path> level=slim_v4z")
        phi("handoff decompress <handoff_id>")
        phi("handoff list")
        phi("handoff stats <handoff_id>")
    """
    task_lower = task.lower().strip()
    compressor = HandoffCompressor()

    # Compress
    if "handoff compress" in task_lower:
        parts = task.split()
        if len(parts) < 3:
            return {"ok": False, "error": "Usage: handoff compress <jsonl_path> [level=slim_v4z]"}

        jsonl_path = parts[2]

        # Check for level parameter
        compression_level = None
        for part in parts[3:]:
            if part.startswith("level="):
                compression_level = part.split("=")[1]

        return compressor.compress_conversation(jsonl_path, compression_level)

    # Decompress
    if "handoff decompress" in task_lower:
        parts = task.split()
        if len(parts) < 3:
            return {"ok": False, "error": "Usage: handoff decompress <handoff_id>"}

        handoff_id = parts[2]
        return compressor.decompress_handoff(handoff_id)

    # List
    if "handoff list" in task_lower:
        return compressor.list_handoffs()

    # Stats
    if "handoff stats" in task_lower:
        parts = task.split()
        if len(parts) < 3:
            return {"ok": False, "error": "Usage: handoff stats <handoff_id>"}

        handoff_id = parts[2]
        return compressor.get_handoff_stats(handoff_id)

    return {"ok": False, "error": "Unknown handoff command"}


# =============================================================================
# CLI
# =============================================================================

def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Handoff SLIM compression")
    parser.add_argument("command", choices=["compress", "decompress", "list", "stats"], help="Command")
    parser.add_argument("args", nargs="*", help="Command arguments")
    parser.add_argument("--level", choices=["slim_only", "slim_v4z", "slim_fsl", "slim_ztpcf"],
                        default="slim_only", help="Compression level")

    args = parser.parse_args()

    compressor = HandoffCompressor()

    if args.command == "compress":
        if not args.args:
            print("Error: Missing JSONL path")
            return

        result = compressor.compress_conversation(args.args[0], args.level)

        if result.get("ok"):
            print(f"✅ Handoff created: {result['handoff_id']}")
            print(f"📊 Compression: {result['original_size']:,} → {result['final_size']:,} bytes ({result['reduction_percent']}% saved)")
            print(f"📦 Format: {result['compression_format']}")
            print(f"💾 Saved to: {result['final_path']}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")

    elif args.command == "decompress":
        if not args.args:
            print("Error: Missing handoff ID")
            return

        result = compressor.decompress_handoff(args.args[0])

        if result.get("ok"):
            print(f"✅ Decompressed: {result['handoff_id']}")
            print(f"⚡ Time: {result['decompression_ms']}ms")
            print(f"📄 Output: {result['jsonl_path']}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")

    elif args.command == "list":
        result = compressor.list_handoffs()
        print(f"📋 Handoffs: {result['count']}")
        for h in result['handoffs']:
            print(f"  {h['handoff_id']}: {h['original_file']} ({h['reduction_percent']}% reduction)")

    elif args.command == "stats":
        if not args.args:
            print("Error: Missing handoff ID")
            return

        result = compressor.get_handoff_stats(args.args[0])

        if result.get("ok"):
            print(f"📊 Handoff Stats: {result['handoff_id']}")
            print(f"  Original: {result['original_size']:,} bytes")
            print(f"  SLIM: {result['slim_size']:,} bytes")
            print(f"  Final: {result['final_size']:,} bytes")
            print(f"  Reduction: {result['reduction_percent']}%")
            print(f"  Format: {result['compression_format']}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
