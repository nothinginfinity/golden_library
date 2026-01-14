#!/bin/bash
""":" # Bash/Python polyglot header
python3 "$0" "$@"
exit $?
"""
"""
Unarchive Phase Script

Restores an archived phase to CURRENT_PLAN.md:
1. Finds archived phase by handoff ID or phase number
2. Decompresses if V4Z format
3. Copies to CURRENT_PLAN.md
4. Optionally creates new branch for restoration

Usage:
  ./scripts/unarchive-phase.sh <handoff_id_or_phase>
  ./scripts/unarchive-phase.sh 9bca1a7
  ./scripts/unarchive-phase.sh 4.5
  ./scripts/unarchive-phase.sh --list  # List available phases
"""

import sys
import os
import shutil
import argparse
from pathlib import Path
import re

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from v4z_compressor import V4ZCompressor


def list_archived_phases():
    """List all archived phases."""
    archive_dir = Path("archive/plans")

    if not archive_dir.exists():
        print("📭 No archived phases found")
        return

    print("\n📚 Archived Phases:\n")

    archived_files = sorted(archive_dir.glob("*.md"), reverse=True)

    for archive_file in archived_files:
        # Parse filename: YYYY-MM-DD_phaseN_name.md
        match = re.match(r'(\d{4}-\d{2}-\d{2})_phase([\d.]+)_(.*?)\.md', archive_file.name)

        if match:
            date, phase, name = match.groups()
            name_readable = name.replace('-', ' ').title()

            # Check if compressed version exists
            compressed = archive_file.with_suffix('.md.v4z')
            has_compressed = "✅" if compressed.exists() else "  "

            print(f"  {has_compressed} Phase {phase:5s} | {date} | {name_readable}")
            print(f"     File: {archive_file}")
            if compressed.exists():
                print(f"     V4Z:  {compressed}")
            print()


def find_phase(identifier):
    """Find archived phase by handoff ID or phase number."""
    archive_dir = Path("archive/plans")

    if not archive_dir.exists():
        return None

    # Try as phase number first (e.g., "4.5")
    for archive_file in archive_dir.glob("*.md"):
        match = re.match(r'(\d{4}-\d{2}-\d{2})_phase([\d.]+)_(.*?)\.md', archive_file.name)
        if match and match.group(2) == identifier:
            return archive_file

    # Try as handoff ID (look in .golden_library/index.json)
    index_path = Path(".golden_library/index.json")
    if index_path.exists():
        import json
        with open(index_path, 'r') as f:
            index = json.load(f)

        for handoff in index.get("handoffs", []):
            if handoff.get("handoff_id", "").startswith(identifier):
                source_file = handoff.get("source_file")
                if source_file:
                    # If source is in archive, return it
                    if source_file.startswith("archive/"):
                        return Path(source_file)

    return None


def unarchive_phase(identifier, create_branch=False):
    """Unarchive a phase and restore to CURRENT_PLAN.md."""

    # Find phase
    archive_file = find_phase(identifier)

    if not archive_file:
        print(f"❌ Phase not found: {identifier}")
        print(f"\n💡 Try: ./scripts/unarchive-phase.sh --list")
        sys.exit(1)

    print(f"\n📦 Restoring phase from: {archive_file}")

    # Check if current CURRENT_PLAN.md exists and has uncommitted changes
    current_plan = Path("CURRENT_PLAN.md")
    if current_plan.exists():
        import subprocess
        result = subprocess.run(
            ['git', 'diff', '--quiet', 'CURRENT_PLAN.md'],
            capture_output=True
        )
        if result.returncode != 0:
            print("\n⚠️  CURRENT_PLAN.md has uncommitted changes!")
            response = input("   Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("   Aborted.")
                sys.exit(0)

    # Check if compressed version exists
    compressed_file = archive_file.with_suffix('.md.v4z')

    if compressed_file.exists():
        # Decompress from V4Z
        print(f"   Decompressing V4Z...")
        compressor = V4ZCompressor()

        with open(compressed_file, 'r') as f:
            compressed_content = f.read()

        decompressed_content = compressor.decompress(compressed_content)

        # Write to CURRENT_PLAN.md
        with open(current_plan, 'w') as f:
            f.write(decompressed_content)

    else:
        # Just copy the markdown file
        shutil.copy2(archive_file, current_plan)

    print(f"   ✅ Restored to CURRENT_PLAN.md")

    # Optionally create branch
    if create_branch:
        import subprocess
        phase_match = re.match(r'.*_phase([\d.]+)_', archive_file.name)
        if phase_match:
            phase = phase_match.group(1)
            branch_name = f"restore-phase-{phase}"

            subprocess.run(['git', 'checkout', '-b', branch_name])
            print(f"   📍 Created branch: {branch_name}")

    print(f"\n💡 Next steps:")
    print(f"   1. Review CURRENT_PLAN.md")
    print(f"   2. git add CURRENT_PLAN.md")
    print(f"   3. git commit -m \"Restore Phase {identifier}\"")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unarchive a phase")
    parser.add_argument('identifier', nargs='?', help='Handoff ID or phase number')
    parser.add_argument('--list', '-l', action='store_true', help='List archived phases')
    parser.add_argument('--branch', '-b', action='store_true', help='Create new branch for restoration')

    args = parser.parse_args()

    if args.list:
        list_archived_phases()
    elif args.identifier:
        unarchive_phase(args.identifier, create_branch=args.branch)
    else:
        parser.print_help()
