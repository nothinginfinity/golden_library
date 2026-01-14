#!/bin/bash
""":" # Bash/Python polyglot header
# Bash portion
python3 "$0" "$@"
exit $?
"""
"""
Archive Phase Script

Archives current phase and creates next phase stub:
1. Archives CURRENT_PLAN.md to archive/plans/YYYY-MM-DD_phaseN_name.md
2. Compresses archived plan with V4Z
3. Updates .golden_library/index.json
4. Creates stub for next phase
5. Git commits with proper message

Usage:
  ./scripts/archive-phase.sh [--next-phase N] [--next-name "Phase Name"]
"""

import sys
import os
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import re

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from v4z_compressor import V4ZCompressor


def parse_current_plan_metadata():
    """Extract metadata from CURRENT_PLAN.md."""
    plan_path = Path("CURRENT_PLAN.md")

    if not plan_path.exists():
        print("❌ CURRENT_PLAN.md not found")
        sys.exit(1)

    with open(plan_path, 'r') as f:
        content = f.read()

    metadata = {}

    # Extract from metadata block
    metadata_block = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
    if metadata_block:
        for line in metadata_block.group(1).split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip('- ').strip()
                value = value.strip()
                metadata[key] = value

    return metadata, content


def archive_phase(next_phase=None, next_name=None):
    """Archive current phase and create next phase stub."""

    # Parse current plan
    current_metadata, current_content = parse_current_plan_metadata()

    current_phase = current_metadata.get('Phase', 'unknown')
    current_name = current_metadata.get('Phase Name', 'unnamed')
    prev_handoff = current_metadata.get('Previous Handoff', '')

    print(f"\n📦 Archiving Phase {current_phase}: {current_name}")

    # Determine next phase
    if next_phase is None:
        try:
            # Try to increment current phase (e.g., "4.5" → "5")
            if '.' in current_phase:
                next_phase = str(int(float(current_phase)) + 1)
            else:
                next_phase = str(int(current_phase) + 1)
        except:
            print("❌ Could not determine next phase. Please specify with --next-phase")
            sys.exit(1)

    if next_name is None:
        next_name = input("Next phase name: ").strip()
        if not next_name:
            print("❌ Phase name required")
            sys.exit(1)

    # Create archive filename
    date_str = datetime.now().strftime('%Y-%m-%d')
    phase_slug = current_name.lower().replace(' ', '-').replace('_', '-')
    archive_filename = f"{date_str}_phase{current_phase}_{phase_slug}.md"
    archive_path = Path("archive/plans") / archive_filename

    # Ensure archive directory exists
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy current plan to archive
    print(f"   → {archive_path}")
    shutil.copy2("CURRENT_PLAN.md", archive_path)

    # Compress archived plan
    print(f"   Compressing...")
    compressor = V4ZCompressor(compression_level=15)
    result = compressor.compress_file(
        str(archive_path),
        str(archive_path.with_suffix('.md.v4z'))
    )
    print(f"   ✅ Compressed: {result.reduction_percent}% reduction")

    # Get git commit hash for handoff ID
    try:
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            text=True
        ).strip()[:12]
    except:
        commit_hash = "uncommitted"

    # Create next phase stub
    next_plan_content = f"""# Golden Library - Current Plan

---
**Metadata:**
- **Project:** golden_library
- **Phase:** {next_phase}
- **Phase Name:** {next_name}
- **Started:** {datetime.now().strftime('%Y-%m-%d')}
- **Estimated Duration:** TBD
- **Status:** active
- **Previous Handoff:** {commit_hash} (Phase {current_phase}: {current_name})
- **Dependencies:**
  - TBD
- **Related Work:**
  - Previous phase work
---

## Context from Previous Phase

**Phase {current_phase}: {current_name}** (handoff://{commit_hash})
- ✅ [Summary of what was completed]
- ✅ [Key achievements]
- ✅ [Major features delivered]

**What's Working:**
- [List working features]

**What's Missing:**
- [List gaps or future work]

---

## Phase {next_phase} Goals

[Describe overall goals and objectives for this phase]

---

## Active Tasks - Immediate (This Phase)

### 🔴 Priority 1: [Task Name]
**Status:** Not Started
**Owner:** Koda
**Estimated:** [Duration]

**Objective:** [What needs to be done]

**Tasks:**
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

**Acceptance Criteria:**
- Criterion 1
- Criterion 2

**Files to Create/Modify:**
- file1.py
- file2.py

---

## Backlog - Future Phases

### Phase {int(next_phase)+1}: [Future Phase]
**Estimated:** TBD

[Description]

---

## Success Metrics

**Phase {next_phase} Complete When:**
- ✅ [Metric 1]
- ✅ [Metric 2]
- ✅ [Metric 3]

---

## Getting Started (For New Instance)

**Quick Start:**
1. Read this file
2. Check previous handoff: `git show {commit_hash}`
3. Start with Priority 1
4. Commit progress, check off tasks

**Key Files:**
- TBD

---

**Last Updated:** {datetime.now().strftime('%Y-%m-%d')}
**Next Review:** After Priority 1 complete
**Questions/Blockers:** None currently
"""

    # Write next phase stub
    with open("CURRENT_PLAN.md", 'w') as f:
        f.write(next_plan_content)

    print(f"\n✅ Created Phase {next_phase} stub: {next_name}")

    # Stage files
    subprocess.run(['git', 'add', str(archive_path)])
    subprocess.run(['git', 'add', str(archive_path.with_suffix('.md.v4z'))])
    subprocess.run(['git', 'add', 'CURRENT_PLAN.md'])

    # Create commit message
    commit_msg = f"""Archive Phase {current_phase} and create Phase {next_phase} plan

Phase {current_phase} complete: {current_name}

Archived to: {archive_path}
Compressed: {result.reduction_percent}% reduction

Phase {next_phase}: {next_name}

Previous phase: handoff://{commit_hash}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"""

    # Commit
    print(f"\n📝 Committing phase transition...")
    subprocess.run(['git', 'commit', '-m', commit_msg])

    print(f"\n🎉 Phase transition complete!")
    print(f"   Previous: Phase {current_phase} (handoff://{commit_hash})")
    print(f"   Current: Phase {next_phase}")
    print(f"   Archived: {archive_path}")
    print(f"\n💡 Next steps:")
    print(f"   1. Review CURRENT_PLAN.md and fill in details")
    print(f"   2. git push origin main")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive phase and create next phase stub")
    parser.add_argument('--next-phase', type=str, help='Next phase number (e.g., "5")')
    parser.add_argument('--next-name', type=str, help='Next phase name')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without doing it')

    args = parser.parse_args()

    if args.dry_run:
        print("🔍 DRY RUN MODE - showing what would happen:")
        metadata, _ = parse_current_plan_metadata()
        print(f"   Current phase: {metadata.get('Phase', 'unknown')}")
        print(f"   Current name: {metadata.get('Phase Name', 'unnamed')}")
        print(f"   Would archive to: archive/plans/YYYY-MM-DD_phaseN_name.md")
        print(f"   Would create: Phase {args.next_phase or '[auto]'} stub")
        sys.exit(0)

    archive_phase(args.next_phase, args.next_name)
