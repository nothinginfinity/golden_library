#!/usr/bin/env python3
"""
SLIM Conversation Converter
Schema-once lossless format for JSONL conversations.

Converts Claude Code JSONL files to SLIM format (~50% size reduction).
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import OrderedDict


class SlimConverter:
    """Convert between JSONL and SLIM formats."""

    def __init__(self):
        self.version = "1.0"

    def jsonl_to_slim(self, jsonl_path_or_content: str) -> str:
        """
        Convert JSONL file or content to SLIM format.

        Args:
            jsonl_path_or_content: Path to .jsonl file or JSONL content string

        Returns:
            SLIM formatted string
        """
        # Check if it's a file path or content
        content = None
        try:
            path = Path(jsonl_path_or_content)
            if path.exists() and path.is_file():
                # It's a file path
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
        except (OSError, ValueError):
            # Path is invalid (too long, etc.) - must be content
            pass

        if content is None:
            # It's content
            content = jsonl_path_or_content

        # Parse all lines
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # Skip malformed lines

        if not lines:
            return self._empty_slim()

        # Extract schema from all lines
        schema = self._extract_schema(lines)

        # Build SLIM format
        slim_parts = []
        slim_parts.append("§SLIM§ v1")
        slim_parts.append("[SCHEMA]")
        slim_parts.append("|".join(schema["fields"]))
        slim_parts.append("|".join(schema["types"]))
        slim_parts.append("---")
        slim_parts.append("[DATA]")

        # Convert each line to data row
        for obj in lines:
            row = self._object_to_row(obj, schema["fields"])
            slim_parts.append("|".join(row))

        slim_parts.append("---")
        slim_parts.append("[META]")
        slim_parts.append(f"lines:{len(lines)}")
        slim_parts.append(f"original_file:{path.name}")
        slim_parts.append("§/SLIM§")

        return "\n".join(slim_parts)

    def slim_to_jsonl(self, slim_content: str) -> str:
        """
        Convert SLIM format back to JSONL.

        Args:
            slim_content: SLIM formatted string

        Returns:
            JSONL formatted string (one JSON object per line)
        """
        # Parse SLIM sections
        sections = self._parse_slim(slim_content)

        if not sections:
            return ""

        schema_fields = sections["schema"]["fields"]
        schema_types = sections["schema"]["types"]
        data_rows = sections["data"]

        # Reconstruct JSONL
        jsonl_lines = []
        for row in data_rows:
            obj = self._row_to_object(row, schema_fields, schema_types)
            jsonl_lines.append(json.dumps(obj, separators=(',', ':')))

        return "\n".join(jsonl_lines)

    def _extract_schema(self, objects: List[Dict]) -> Dict[str, List[str]]:
        """
        Extract unified schema from all objects.
        Returns fields and their types.
        """
        # Collect all fields (flattened)
        all_fields = OrderedDict()

        for obj in objects:
            flattened = self._flatten_object(obj)
            for key, value in flattened.items():
                if key not in all_fields:
                    all_fields[key] = self._infer_type(value)

        return {
            "fields": list(all_fields.keys()),
            "types": list(all_fields.values())
        }

    def _flatten_object(self, obj: Dict, prefix: str = "") -> Dict[str, Any]:
        """
        Flatten nested object with dot notation.

        Example:
            {"message": {"role": "user", "content": "hi"}}
            →
            {"message.role": "user", "message.content": "hi"}
        """
        result = {}

        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict) and value:
                # Recurse for nested dicts
                result.update(self._flatten_object(value, full_key))
            elif isinstance(value, list) and len(value) > 0:
                # For lists, check if all items are dicts (like message.content array)
                if all(isinstance(item, dict) for item in value):
                    # Store as JSON
                    result[full_key] = value
                else:
                    # Simple array
                    result[full_key] = value
            else:
                result[full_key] = value

        return result

    def _infer_type(self, value: Any) -> str:
        """Infer SLIM type code from value."""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, str):
            # Check if ISO timestamp
            if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', value):
                return "iso"
            return "str"
        elif isinstance(value, (list, dict)):
            return "json"
        else:
            return "str"

    def _object_to_row(self, obj: Dict, schema_fields: List[str]) -> List[str]:
        """Convert object to SLIM row based on schema."""
        flattened = self._flatten_object(obj)
        row = []

        for field in schema_fields:
            value = flattened.get(field)
            row.append(self._encode_value(value))

        return row

    def _encode_value(self, value: Any) -> str:
        """Encode value for SLIM row."""
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            # Escape pipes
            escaped = value.replace("|", "\\|")
            # If contains newlines or special chars, consider JSON encoding
            if "\n" in escaped or len(escaped) > 500:
                return json.dumps(value)
            return escaped
        elif isinstance(value, (list, dict)):
            return json.dumps(value, separators=(',', ':'))
        else:
            return str(value)

    def _parse_slim(self, content: str) -> Dict[str, Any]:
        """Parse SLIM format into sections."""
        if not content.startswith("§SLIM§"):
            raise ValueError("Invalid SLIM format: missing header")

        # Split into sections
        sections = {
            "schema": {"fields": [], "types": []},
            "data": [],
            "meta": {}
        }

        current_section = None
        schema_lines = []

        for line in content.split("\n"):
            line = line.strip()

            if line == "[SCHEMA]":
                current_section = "schema"
                continue
            elif line == "[DATA]":
                current_section = "data"
                continue
            elif line == "[META]":
                current_section = "meta"
                continue
            elif line in ("---", "§SLIM§ v1", "§/SLIM§", ""):
                continue

            if current_section == "schema":
                schema_lines.append(line)
            elif current_section == "data":
                sections["data"].append(line.split("|"))
            elif current_section == "meta":
                if ":" in line:
                    key, value = line.split(":", 1)
                    sections["meta"][key] = value

        # Parse schema
        if len(schema_lines) >= 2:
            sections["schema"]["fields"] = schema_lines[0].split("|")
            sections["schema"]["types"] = schema_lines[1].split("|")

        return sections

    def _row_to_object(self, row: List[str], fields: List[str], types: List[str]) -> Dict[str, Any]:
        """Convert SLIM row back to nested object."""
        # Build flattened dict
        flattened = {}
        for field, value_str, type_code in zip(fields, row, types):
            value = self._decode_value(value_str, type_code)
            if value is not None or value_str == "null":
                flattened[field] = value

        # Unflatten to nested structure
        return self._unflatten_object(flattened)

    def _decode_value(self, value_str: str, type_code: str) -> Any:
        """Decode SLIM value back to Python type."""
        if value_str == "null":
            return None
        elif value_str == "":
            return None
        elif type_code == "bool":
            return value_str.lower() == "true"
        elif type_code == "int":
            return int(value_str) if value_str else 0
        elif type_code == "float":
            return float(value_str) if value_str else 0.0
        elif type_code == "json":
            if not value_str or value_str.strip() == "":
                return None
            return json.loads(value_str)
        elif type_code in ("str", "iso"):
            # Unescape pipes
            if value_str.startswith('"') and value_str.endswith('"'):
                return json.loads(value_str)
            return value_str.replace("\\|", "|")
        else:
            return value_str

    def _unflatten_object(self, flattened: Dict[str, Any]) -> Dict[str, Any]:
        """Convert flattened dict back to nested structure."""
        result = {}

        for key, value in flattened.items():
            parts = key.split(".")
            current = result

            # Navigate to the right nesting level
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    # If value exists but isn't a dict, skip this key
                    continue
                current = current[part]

            # Set the final value only if current is a dict
            if isinstance(current, dict):
                current[parts[-1]] = value

        return result

    def _empty_slim(self) -> str:
        """Return empty SLIM format."""
        return """§SLIM§ v1
[SCHEMA]

---
[DATA]
---
[META]
lines:0
§/SLIM§"""

    def get_compression_stats(self, jsonl_path: str, slim_content: str) -> Dict[str, Any]:
        """Calculate compression statistics."""
        original_size = Path(jsonl_path).stat().st_size
        slim_size = len(slim_content.encode('utf-8'))

        return {
            "original_bytes": original_size,
            "slim_bytes": slim_size,
            "reduction_bytes": original_size - slim_size,
            "reduction_percent": round((1 - slim_size / original_size) * 100, 1) if original_size > 0 else 0,
            "compression_ratio": round(original_size / slim_size, 2) if slim_size > 0 else 0
        }


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Convert JSONL ↔ SLIM formats")
    parser.add_argument("command", choices=["compress", "decompress", "stats"], help="Operation to perform")
    parser.add_argument("input", help="Input file path")
    parser.add_argument("-o", "--output", help="Output file path (optional)")

    args = parser.parse_args()

    converter = SlimConverter()

    if args.command == "compress":
        # JSONL → SLIM
        slim_content = converter.jsonl_to_slim(args.input)

        if args.output:
            Path(args.output).write_text(slim_content)
            print(f"✅ Compressed to {args.output}")
        else:
            print(slim_content)

        # Show stats
        stats = converter.get_compression_stats(args.input, slim_content)
        print(f"\n📊 Stats:")
        print(f"  Original: {stats['original_bytes']:,} bytes")
        print(f"  SLIM: {stats['slim_bytes']:,} bytes")
        print(f"  Reduction: {stats['reduction_percent']}% ({stats['reduction_bytes']:,} bytes)")

    elif args.command == "decompress":
        # SLIM → JSONL
        slim_content = Path(args.input).read_text()
        jsonl_content = converter.slim_to_jsonl(slim_content)

        if args.output:
            Path(args.output).write_text(jsonl_content)
            print(f"✅ Decompressed to {args.output}")
        else:
            print(jsonl_content)

    elif args.command == "stats":
        # Just show stats
        slim_content = converter.jsonl_to_slim(args.input)
        stats = converter.get_compression_stats(args.input, slim_content)

        print(f"📊 Compression Statistics:")
        print(f"  Original: {stats['original_bytes']:,} bytes")
        print(f"  SLIM: {stats['slim_bytes']:,} bytes")
        print(f"  Saved: {stats['reduction_bytes']:,} bytes ({stats['reduction_percent']}%)")
        print(f"  Ratio: {stats['compression_ratio']}:1")


if __name__ == "__main__":
    main()
