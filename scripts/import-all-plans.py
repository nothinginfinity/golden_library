#!/usr/bin/env python3
"""
Import All Plans Script

Scans all ztgi repos for PRDs, plans, and important docs,
compresses them with V4Z, and imports to golden_library.

Usage:
  python3 import-all-plans.py [--dry-run]
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


def scan_for_plans(base_dir):
    """Scan for all plan/PRD files in ztgi repos."""
    base = Path(base_dir).expanduser()

    patterns = [
        "**/PRD_*.md",
        "**/PLAN_*.md",
        "**/CURRENT_PLAN.md",
        "**/archive/plans/*.md",
        "**/docs/PRD*.md",
    ]

    found = []
    seen = set()

    for pattern in patterns:
        for path in base.glob(pattern):
            # Skip if already seen (avoid duplicates)
            if path in seen:
                continue

            # Skip if in node_modules, .git, etc
            if any(part.startswith('.') for part in path.parts):
                continue
            if 'node_modules' in path.parts:
                continue

            # Skip README files
            if path.name == 'README.md':
                continue

            seen.add(path)
            found.append(path)

    return sorted(found)


def extract_metadata(file_path, content):
    """Extract metadata from plan file."""
    lines = content.split('\n')

    # Try to find title (first # heading)
    title = file_path.stem
    for line in lines[:20]:
        if line.startswith('# '):
            title = line[2:].strip()
            break

    # Infer phase from file path
    phase = "unknown"
    if 'phase' in file_path.stem.lower():
        parts = file_path.stem.lower().split('phase')
        if len(parts) > 1:
            phase = parts[1].split('_')[0].split('-')[0]

    # Extract project from directory
    project = "unknown"
    if '/ztgi/' in str(file_path):
        parts = str(file_path).split('/ztgi/')
        if len(parts) > 1:
            project = parts[1].split('/')[0]

    return {
        'title': title,
        'phase': phase,
        'project': project,
        'filename': file_path.name
    }


def import_plan(file_path, golden_lib_dir, compressor, dry_run=False):
    """Import a single plan file."""
    try:
        # Read content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Skip if empty
        if len(content.strip()) < 100:
            return None

        # Generate handoff ID
        handoff_id = compute_handoff_id(content)

        # Check if already exists
        compressed_file = golden_lib_dir / 'compressed' / f'{handoff_id}.v4z'
        if compressed_file.exists():
            print(f"  ⏭️  {file_path.name} (already imported)")
            return None

        # Compress
        result = compressor.compress(content)

        # Get compressed content (includes header/footer)
        compressed_content = result.compressed_base64

        # Calculate stats from result
        original_size = result.original_size_bytes
        compressed_size = result.compressed_size_bytes
        reduction = result.reduction_percent
        original_tokens = result.original_tokens
        compressed_tokens = result.compressed_tokens

        # Extract metadata
        metadata = extract_metadata(file_path, content)

        # Get file modified time as creation date
        created = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()

        if not dry_run:
            # Write compressed file
            compressed_file.parent.mkdir(parents=True, exist_ok=True)
            with open(compressed_file, 'w', encoding='utf-8') as f:
                f.write(compressed_content)

        # Create index entry
        entry = {
            'handoff_id': handoff_id,
            'created': created,
            'source_file': str(file_path),
            'compressed_file': f'.golden_library/compressed/{handoff_id}.v4z',
            'phase': metadata['phase'],
            'phase_name': metadata['title'],
            'project': metadata['project'],
            'original_size_bytes': original_size,
            'compressed_size_bytes': compressed_size,
            'reduction_percent': round(reduction, 1),
            'original_tokens': original_tokens,
            'compressed_tokens': compressed_tokens,
            'format': 'v4z',
            'compression_level': 15,
            'imported_from': 'scan'
        }

        status = "📥" if not dry_run else "🔍"
        print(f"  {status} {metadata['project']}/{file_path.name}")
        print(f"     {reduction:.1f}% reduction ({original_size} → {compressed_size} bytes)")

        return entry

    except Exception as e:
        print(f"  ❌ {file_path.name}: {e}")
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import all plans into golden library')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without actually importing')
    parser.add_argument('--base-dir', default='~/ztgi', help='Base directory to scan (default: ~/ztgi)')

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

    # Scan for plans
    print(f"🔍 Scanning {args.base_dir} for plans and PRDs...")
    plans = scan_for_plans(args.base_dir)
    print(f"   Found {len(plans)} files\n")

    if not plans:
        print("❌ No plans found")
        return

    # Import each plan
    compressor = V4ZCompressor()
    imported = []

    for plan_file in plans:
        entry = import_plan(plan_file, golden_lib_dir, compressor, dry_run=args.dry_run)
        if entry:
            imported.append(entry)

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

        print(f"\n✅ Imported {len(new_entries)} new plans")
        print(f"   Total in library: {len(index['handoffs'])}")
        print(f"   Index updated: {index_file}")
    elif args.dry_run:
        print(f"\n🔍 Dry run complete. Would import {len(imported)} plans")
        print(f"   Run without --dry-run to actually import")
    else:
        print(f"\n⏭️  All plans already imported")


if __name__ == '__main__':
    main()
