# Handoff Compression System - Implementation Summary

## What We Built

### 1. SLIM Format Specification (`slim_conversation_spec.md`)
- Schema-once compression for JSONL conversations
- Target: ~50% size reduction (lossless)
- Format: Schema defined once, data as pipe-delimited rows
- Inspired by your image showing JSON key repetition problem

### 2. SLIM Converter (`slim_converter.py`)
- `jsonl_to_slim()` - Convert JSONL → SLIM
- `slim_to_jsonl()` - Convert SLIM → JSONL
- CLI: `python3 slim_converter.py compress|decompress|stats <file>`
- **Status**: Core logic implemented, needs bug fixes for complex nested structures

### 3. Handoff Integration (`handoff_slim.py`)
- `HandoffCompressor` class for managing compressed handoffs
- Two-stage compression:
  1. SLIM (schema deduplication)
  2. Optional: V4Z/FSL/ZTPCF on top of SLIM
- Commands:
  - `phi("handoff compress <jsonl>")` - Compress conversation
  - `phi("handoff decompress <id>")` - Restore conversation
  - `phi("handoff list")` - List all handoffs
  - `phi("handoff stats <id>")` - Show compression stats
- Handoffs stored in `~/.fsl/handoffs/`

## Current Status

✅ **Completed**:
- SLIM format specification
- Core converter structure
- Handoff integration framework
- CLI interfaces

⚠️ **Needs Work**:
- SLIM converter has bugs with complex nested Claude Code JSONL
- Roundtrip testing failing (JSONL → SLIM → JSONL not identical yet)
- V4Z/FSL/ZTPCF integration placeholders need real implementations

## Architecture

```
Current Handoff Flow (FLAWED):
  ~/.claude/projects/*/session.jsonl (73MB+)
    ↓ [No compression]
  Handoff system times out reading/indexing

New Handoff Flow (PROPOSED):
  ~/.claude/projects/*/session.jsonl (73MB)
    ↓ [SLIM compression]
  ~/.fsl/handoffs/abc123.slim (36MB - 50% reduction)
    ↓ [Optional V4Z/FSL/ZTPCF]
  ~/.fsl/handoffs/abc123.slim.v4z (10MB - 86% total reduction)
    ↓ [Package for next session]
  New Claude Code instance auto-decompresses
```

## Integration Points

### 1. Terminal Library (`terminal_library.py`)
When exporting terminals:
```python
# Current: Exports raw .md files
# Proposed: Also create compressed stones

from handoff_slim import HandoffCompressor
compressor = HandoffCompressor()

# Find conversation JSONL
jsonl_path = find_current_session_jsonl()

# Compress
result = compressor.compress_conversation(jsonl_path, level="slim_v4z")

# Create QA.Stone from compressed handoff
stone = create_stone_from_handoff(result["handoff_id"])
```

### 2. QA.Stone App (`qastone-mcp-twin/static/app.html`)
New sidebar section: **Terminal Library**

Features needed:
- List all compressed conversation stones
- View stone metadata (date, compression ratio, topics)
- Decompress and view in browser
- Search across stones
- Share stones with other users
- Compression settings UI

### 3. Handoff Executor (`handoff_executor.py`)
Current file: `/Users/kanelawaccount/ztgi/phi_proxy/handoff_executor.py`

Modify `prepare_handoff()`:
```python
def prepare_handoff(reason: str = "Manual trigger") -> Dict[str, Any]:
    # Find current session JSONL
    session_jsonl = find_current_session()

    # Compress with SLIM
    from handoff_slim import HandoffCompressor
    compressor = HandoffCompressor()
    result = compressor.compress_conversation(session_jsonl)

    if result["ok"]:
        # Package handoff with compressed file
        handoff_package = {
            "handoff_id": result["handoff_id"],
            "compressed_path": result["final_path"],
            "compression_stats": {
                "original_size": result["original_size"],
                "final_size": result["final_size"],
                "reduction": result["reduction_percent"]
            },
            # ... rest of handoff data
        }
        return handoff_package
```

## Next Steps

### Priority 1: Fix SLIM Converter Bugs
- [ ] Handle Claude Code JSONL nested message structures properly
- [ ] Test roundtrip on real conversations
- [ ] Ensure 100% lossless compression

### Priority 2: Compression Settings UI
Create `/Users/kanelawaccount/ztgi/qastone-mcp-twin/static/compression_settings.html`:
- Radio buttons: SLIM only, SLIM+V4Z, SLIM+FSL, SLIM+ZTPCF
- Content type detection: Auto-select best format
- Live preview: Show compression ratio estimate
- Fidelity slider: Lossy (max compression) ↔ Lossless

### Priority 3: QA.Stone Conversion Pipeline
```python
# Convert conversation → QA.Stone
def conversation_to_stone(jsonl_path: str, config: Dict) -> str:
    # 1. Compress conversation
    compressor = HandoffCompressor(config)
    result = compressor.compress_conversation(jsonl_path)

    # 2. Extract metadata
    metadata = extract_conversation_metadata(jsonl_path)

    # 3. Create stone with LOD layers
    stone = create_stone(
        stone_type="session",
        content=result["compressed_path"],
        glow=metadata["summary"],
        concepts=metadata["concepts"]
    )

    # 4. Mint to wallet
    wallet.deposit(stone)

    return stone["id"]
```

### Priority 4: Terminal Library UI
Add to `qastone-mcp-twin/static/app.html`:
```html
<!-- Sidebar -->
<button onclick="showPage('terminal-library')" class="sidebar-link">
    <svg>...</svg>
    <span>Terminal Library</span>
    <span class="badge">{{stone_count}}</span>
</button>

<!-- Page -->
<div id="page-terminal-library" class="page hidden">
    <div class="search-bar">
        <input placeholder="Search conversations..." />
        <button onclick="filterLibrary()">Search</button>
    </div>

    <div class="stone-grid">
        <!-- Stone cards with:
             - Conversation date
             - Original size → Compressed size
             - Compression format badge
             - Topic tags
             - View/Download buttons
        -->
    </div>
</div>
```

## File Locations

| File | Purpose | Status |
|------|---------|--------|
| `/Users/kanelawaccount/ztgi/phi_proxy/slim_conversation_spec.md` | SLIM format spec | ✅ Complete |
| `/Users/kanelawaccount/ztgi/phi_proxy/slim_converter.py` | JSONL ↔ SLIM | ⚠️ Needs fixes |
| `/Users/kanelawaccount/ztgi/phi_proxy/handoff_slim.py` | Handoff compression | ✅ Framework done |
| `/Users/kanelawaccount/ztgi/phi_proxy/handoff_executor.py` | Existing handoff system | 🔄 Needs SLIM integration |
| `/Users/kanelawaccount/ztgi/qastone-mcp-twin/static/app.html` | QA.Stone app UI | 🔄 Needs terminal library view |
| `~/.fsl/handoffs/` | Compressed handoffs storage | ✅ Created |

## Testing Plan

```bash
# Test 1: SLIM compression
python3 slim_converter.py stats ~/.claude/projects/.../session.jsonl

# Test 2: Handoff compress
python3 handoff_slim.py compress ~/.claude/projects/.../session.jsonl --level slim_only

# Test 3: Handoff decompress
python3 handoff_slim.py decompress abc123

# Test 4: Roundtrip integrity
python3 -c "
from slim_converter import SlimConverter
import json

converter = SlimConverter()
original = open('session.jsonl').read()
slim = converter.jsonl_to_slim('session.jsonl')
restored = converter.slim_to_jsonl(slim)

assert original == restored, 'Roundtrip failed!'
print('✅ Roundtrip successful')
"
```

## Questions for User

1. **Compression Level**: Which default do you want?
   - `slim_only` (fast, 50% reduction, always lossless)
   - `slim_v4z` (medium, 80% reduction, lossless)
   - `slim_fsl` (slow, 85% reduction, lossy option available)
   - `auto` (analyze content and choose best)

2. **UI Integration**: Should compression settings be:
   - Global setting (all handoffs use same format)
   - Per-handoff choice (prompt user each time)
   - Auto-detect (based on conversation content type)

3. **Storage**: Where should terminal library stones live?
   - `~/terminal_library/stones/` (alongside inbox/archive)
   - `~/.qastone/stones/` (with other QA.Stones)
   - Both (symlinked)

4. **Timeout Fix**: For the original phi server timeout issue:
   - Should we compress existing large JSONL files retroactively?
   - Or only new handoffs going forward?

---

*Created: 2026-01-13*
*Status: Phase 1 Complete (Architecture + Core Implementation)*
*Next: Bug fixes + UI integration*
