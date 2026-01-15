# Golden Library - Unified Content Guide

**Last Updated:** 2026-01-14

## Overview

The Golden Library now serves as a unified view of ALL your Claude content:
- **Plans/PRDs** (22 green nodes)
- **Conversations** (105 blue nodes)
- **Terminal sessions** (coming soon)

## Current State

### Plans (22 entries)
All historical plans from ztgi repos, compressed with V4Z:

**By Project:**
- `phi_proxy`: 4 PRDs (QAstone Enterprise, MCP Hotswap, Prax Mail, Twincode Modes)
- `prax-chat`: 7 plans (Game UI, GitHub Setup, Weekly Sprints, Security)
- `golden_library`: 4 PRDs (3D Viewer, Compression, Selective Decompression)
- `phi_command_center_desktop`: 1 PRD (Parallel Internet Builder)
- `qastone-spec`: 1 PRD (QAstone Protocol)
- `qastone-generator`: 1 PRD (Identity Wallet)
- `simple-stone-temp`: 1 PRD (Identity Wallet)

**Compression Stats:**
- Average reduction: 53%
- Range: 42.5% - 62.7%
- Total space saved: ~138KB
- Format: V4Z (SLIM vocabulary + Zstandard)

### Conversations (105 entries)
From `~/.claude/conversation_library/compressed/`:
- Auto-discovered from filesystem
- Showing as blue nodes in 3D viewer
- Categories: projects, todos, general

### Terminal Sessions (not yet imported)
Location TBD - need to find terminal library location.

## Viewing Unified Content

### 3D Viewer
**URL:** http://localhost:8080 → 3D View tab

**Visual:**
- 🟢 Green nodes = Plans/PRDs
- 🔵 Blue nodes = Conversations
- Size = compression ratio

**Layouts:**
- **Globe** - Spherical distribution (default)
- **Timeline** - Chronological (X=date, Y=compression%)
- **Clusters** - Grouped by similarity
- **Grid** - Cubic arrangement
- **Helix** - Spiral timeline
- **Scatter** - Random distribution

**Interactions:**
- Click green node → Modal with plan content + "Restore to CURRENT_PLAN.md" button
- Click blue node → Details panel with stats
- Drag to orbit, scroll to zoom
- Search box filters all content

### Search & Filter
**Hybrid Search:**
- Local file content search
- Metadata search (title, project, tags)
- Unified results across plans + conversations

## Managing Content

### Import New Plans
```bash
# Import all plans from ztgi repos
python3 scripts/import-all-plans.py

# Dry run to preview
python3 scripts/import-all-plans.py --dry-run

# Import from specific directory
python3 scripts/import-all-plans.py --base-dir ~/other-projects
```

### Compress Current Plan
Happens automatically on `git commit`:
```bash
# Edit CURRENT_PLAN.md
# git add CURRENT_PLAN.md
# git commit -m "update plan"
# → Pre-commit hook compresses to .golden_library/
```

### Archive Phase
When phase complete:
```bash
./scripts/archive-phase.sh
# → Moves CURRENT_PLAN.md to archive/
# → Compresses with V4Z
# → Creates stub for next phase
# → Updates index.json
```

### Restore Archived Plan
```bash
# Via 3D viewer: Click green node → "Restore to CURRENT_PLAN.md"

# Via CLI:
./scripts/unarchive-phase.sh <handoff_id>

# List available:
./scripts/unarchive-phase.sh --list
```

### Decompress Plan
```bash
# To stdout:
python3 src/decompress.py <handoff_id>

# To file:
python3 src/decompress.py <handoff_id> -o output.md

# Via API:
curl -X POST http://localhost:8080/api/3d/handoff/decompress \
  -H "Content-Type: application/json" \
  -d '{"handoff_id": "688e1fc648a5"}'
```

## File Structure

```
golden_library/
├── .golden_library/
│   ├── compressed/          # 21 .v4z files (plans)
│   ├── index.json          # 22 plan entries
│   └── metadata/           # Additional metadata
├── archive/
│   └── plans/              # Archived CURRENT_PLAN.md files
├── scripts/
│   ├── import-all-plans.py  # Import historical plans
│   ├── archive-phase.sh     # Archive current phase
│   └── unarchive-phase.sh   # Restore archived phase
├── src/
│   ├── v4z_compressor.py    # V4Z compression
│   ├── slim_vocabulary.py   # SLIM tokens
│   └── decompress.py        # Decompression CLI
├── docs/
│   └── UNIFIED_LIBRARY_GUIDE.md  # This file
├── CURRENT_PLAN.md          # Active plan
└── dashboard_server.py      # 3D viewer backend
```

## API Reference

### GET /api/3d/handoffs
Returns all handoffs (plans + conversations) for 3D viewer:
```json
{
  "ok": true,
  "count": 127,
  "handoffs": [
    {
      "id": "688e1fc648a5",
      "filename": "CURRENT_PLAN.md",
      "category": "plan",
      "compression_format": "v4z",
      "original_size": 12990,
      "final_size": 6843,
      "reduction_percent": 47.3,
      "created": "2026-01-14T14:57:28",
      "project_id": "golden_library"
    },
    ...
  ]
}
```

### POST /api/3d/handoff/decompress
Decompress a plan:
```json
Request:  {"handoff_id": "688e1fc648a5"}
Response: {"ok": true, "content": "...", "source": "golden_library"}
```

### POST /api/golden/restore
Restore plan to CURRENT_PLAN.md:
```json
Request:  {"handoff_id": "688e1fc648a5"}
Response: {"ok": true, "message": "Restored..."}
```

## Next Steps: Complete Unification

### 1. Find Terminal Library
```bash
# Search for terminal sessions
find ~/ztgi -type f -name "*terminal*" -o -name "*session*"
find ~/.claude -type f -name "*terminal*"
```

### 2. Import Terminal Sessions
Create `scripts/import-terminal-sessions.py` similar to `import-all-plans.py`

### 3. Add Category Colors
- 🟢 Green = Plans/PRDs
- 🔵 Blue = Conversations
- 🟣 Purple = Terminal sessions
- 🟡 Yellow = Code snippets

### 4. Enhanced Search
- Semantic search with embeddings
- Cross-reference detection (handoff:// links)
- Timeline filtering by date range

### 5. Pattern Library
Scan handoffs for common patterns:
- Authentication implementations
- WebSocket setups
- Database schemas
- API designs

## Troubleshooting

### Plans not showing in 3D viewer
1. Check index: `cat .golden_library/index.json | jq '.handoffs | length'`
2. Restart server: `ps aux | grep dashboard | awk '{print $2}' | xargs kill; python3 dashboard_server.py &`
3. Hard refresh browser: Cmd+Shift+R

### Compression failing
1. Check V4Z compressor: `python3 -c "from src.v4z_compressor import V4ZCompressor; print('OK')"`
2. Test compression: `python3 src/decompress.py <handoff_id>`

### "Handoff not found" error
- Old format (.md files): Supported with legacy fallback
- New format (.v4z files): Primary format
- Check file exists: `ls .golden_library/compressed/<handoff_id>.v4z`

## Resources

- **Dashboard:** http://localhost:8080
- **Index:** .golden_library/index.json
- **Compressed files:** .golden_library/compressed/
- **GitHub Issues:** https://github.com/anthropics/claude-code/issues

---

**Questions?** Check console logs or create an issue.
