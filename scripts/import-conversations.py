#!/usr/bin/env python3
"""
Import Claude Code Conversations

Scans ~/.claude/projects/*.jsonl conversations,
compresses them with V4Z, and imports to golden library.

Usage:
  python3 import-conversations.py [--dry-run] [--limit N]
"""

import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from v4z_compressor import V4ZCompressor
except ImportError:
    print("❌ v4z_compressor not found. Run from golden_library root.")
    sys.exit(1)


def compute_handoff_id(content):
    """Generate handoff ID from content hash."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]


def parse_jsonl_conversation(jsonl_path):
    """Parse JSONL conversation file into readable text."""
    try:
        messages = []
        with open(jsonl_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError:
                    continue

        if not messages:
            return None

        # Extract conversation metadata
        first_msg = messages[0]
        last_msg = messages[-1]

        session_id = first_msg.get('sessionId', 'unknown')
        project = first_msg.get('cwd', 'unknown')
        if project != 'unknown':
            project = Path(project).name

        created = first_msg.get('timestamp', datetime.now().isoformat())
        agent_id = first_msg.get('agentId', '')

        # Build readable conversation text
        text_parts = [
            f"# Claude Code Conversation",
            f"**Session ID:** {session_id}",
            f"**Project:** {project}",
            f"**Created:** {created}",
            f"**Messages:** {len(messages)}",
            ""
        ]

        # Add messages
        for msg in messages:
            msg_type = msg.get('type', 'unknown')
            timestamp = msg.get('timestamp', '')

            if msg_type == 'user':
                content = msg.get('message', {}).get('content', '')
                text_parts.append(f"## User ({timestamp})")
                text_parts.append(content)
                text_parts.append("")

            elif msg_type == 'assistant':
                content = msg.get('message', {}).get('content', '')
                # Handle text content or content blocks
                if isinstance(content, list):
                    for block in content:
                        if block.get('type') == 'text':
                            text_parts.append(f"## Assistant ({timestamp})")
                            text_parts.append(block.get('text', ''))
                            text_parts.append("")
                elif isinstance(content, str):
                    text_parts.append(f"## Assistant ({timestamp})")
                    text_parts.append(content)
                    text_parts.append("")

        conversation_text = '\n'.join(text_parts)

        return {
            'text': conversation_text,
            'session_id': session_id,
            'project': project,
            'created': created,
            'agent_id': agent_id,
            'message_count': len(messages)
        }

    except Exception as e:
        return None


def scan_conversations(base_dir):
    """Scan for all JSONL conversation files."""
    base = Path(base_dir).expanduser()
    found = []

    if not base.exists():
        return found

    for jsonl_file in base.rglob('*.jsonl'):
        # Skip if in tool-results
        if 'tool-results' in jsonl_file.parts:
            continue

        found.append(jsonl_file)

    return sorted(found)


def import_conversation(file_path, golden_lib_dir, compressor, dry_run=False):
    """Import a single conversation."""
    try:
        # Parse JSONL
        parsed = parse_jsonl_conversation(file_path)
        if not parsed:
            return None

        content = parsed['text']

        # Skip if too small
        if len(content.strip()) < 100:
            return None

        # Generate handoff ID
        handoff_id = compute_handoff_id(content)

        # Check if already exists
        compressed_file = golden_lib_dir / 'compressed' / f'{handoff_id}.v4z'
        if compressed_file.exists():
            return None  # Already imported

        # Compress
        result = compressor.compress(content)

        # Get compressed content
        compressed_content = result.compressed_base64

        # Stats
        original_size = result.original_size_bytes
        compressed_size = result.compressed_size_bytes
        reduction = result.reduction_percent
        original_tokens = result.original_tokens
        compressed_tokens = result.compressed_tokens

        if not dry_run:
            # Write compressed file
            compressed_file.parent.mkdir(parents=True, exist_ok=True)
            with open(compressed_file, 'w', encoding='utf-8') as f:
                f.write(compressed_content)

        # Create index entry
        entry = {
            'handoff_id': handoff_id,
            'created': parsed['created'],
            'source_file': str(file_path),
            'compressed_file': f'.golden_library/compressed/{handoff_id}.v4z',
            'session_id': parsed['session_id'],
            'project': parsed['project'],
            'agent_id': parsed['agent_id'],
            'message_count': parsed['message_count'],
            'original_size_bytes': original_size,
            'compressed_size_bytes': compressed_size,
            'reduction_percent': round(reduction, 1),
            'original_tokens': original_tokens,
            'compressed_tokens': compressed_tokens,
            'format': 'v4z',
            'compression_level': 15,
            'category': 'conversation',
            'imported_from': 'claude_code_projects'
        }

        status = "📥" if not dry_run else "🔍"
        print(f"  {status} {parsed['project']}/{file_path.name[:30]}... ({parsed['message_count']} msgs, {reduction:.1f}%)")

        return entry

    except Exception as e:
        print(f"  ❌ {file_path.name}: {e}")
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import Claude Code conversations')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be imported')
    parser.add_argument('--limit', type=int, help='Limit number of conversations to import')
    parser.add_argument('--projects-dir', default='~/.claude/projects', help='Claude projects directory')

    args = parser.parse_args()

    # Setup paths
    golden_lib_dir = Path(__file__).parent.parent / '.golden_library'
    index_file = golden_lib_dir / 'index.json'

    # Load existing index
    if index_file.exists():
        with open(index_file, 'r') as f:
            index = json.load(f)
    else:
        index = {
            'version': '1.0',
            'repository': str(Path(__file__).parent.parent),
            'created': datetime.now().isoformat(),
            'handoffs': [],
            'last_updated': datetime.now().isoformat()
        }

    # Scan for conversations
    print(f"🔍 Scanning {args.projects_dir} for conversations...")
    conversations = scan_conversations(args.projects_dir)
    print(f"   Found {len(conversations)} JSONL files\n")

    if not conversations:
        print("❌ No conversations found")
        return

    # Apply limit if specified
    if args.limit:
        conversations = conversations[:args.limit]
        print(f"   Limiting to {args.limit} conversations\n")

    # Import each conversation
    compressor = V4ZCompressor()
    imported = []
    skipped = 0

    for i, conv_file in enumerate(conversations, 1):
        if i % 100 == 0:
            print(f"\n  Progress: {i}/{len(conversations)}\n")

        entry = import_conversation(conv_file, golden_lib_dir, compressor, dry_run=args.dry_run)
        if entry:
            imported.append(entry)
        else:
            skipped += 1

    # Update index
    if imported and not args.dry_run:
        # Add new entries (avoid duplicates by handoff_id)
        existing_ids = {h['handoff_id'] for h in index['handoffs']}
        new_entries = [e for e in imported if e['handoff_id'] not in existing_ids]

        index['handoffs'].extend(new_entries)
        index['last_updated'] = datetime.now().isoformat()

        # Write index
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)

        print(f"\n✅ Imported {len(new_entries)} new conversations")
        print(f"   Skipped: {skipped} (empty or already imported)")
        print(f"   Total in library: {len(index['handoffs'])}")
        print(f"   Index updated: {index_file}")
    elif args.dry_run:
        print(f"\n🔍 Dry run complete. Would import {len(imported)} conversations")
        print(f"   Skipped: {skipped}")
        print(f"   Run without --dry-run to actually import")
    else:
        print(f"\n⏭️  All conversations already imported or skipped")
        print(f"   Skipped: {skipped}")


if __name__ == '__main__':
    main()
