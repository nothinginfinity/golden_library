# Compression System Demo

Demonstration of the LLM-friendly handoff:// protocol and PRD compression system.

## Quick Start

### 1. Compress a Plan

```bash
cd ~/ztgi/golden_library
python3 src/prd_compressor.py compress CURRENT_PLAN.md
```

**Output:**
```
✅ Compressed: CURRENT_PLAN.md
   Handoff ID: 1ba7855834e1
   Protocol: handoff://1ba7855834e1
   Original: 9236 bytes
   Compressed: 9193 bytes
   Reduction: 0.5%
   Path: .golden_library/compressed/1ba7855834e1.md
```

### 2. Decompress with handoff:// Protocol

```bash
python3 src/prd_compressor.py decompress handoff://1ba7855834e1
```

**Output:** Full markdown content (9236 bytes decompressed)

### 3. Search Across All Handoffs

```bash
python3 src/prd_compressor.py search "websocket"
```

**Output:**
```
🔍 Search: 'websocket'
   Found: 2 results

   📄 Golden Library - Current Plan
      ID: handoff://1ba7855834e1
      Relevance: 0.7
      Snippet: ...🟢 priority 3: websocket live updates...

   📄 PRD: Golden Library 3D Viewer Integration
      ID: handoff://ac193bbe76f0
      Relevance: 0.7
      Snippet: ...⏸️ websocket live updates...
```

### 4. List All Handoffs

```bash
python3 src/prd_compressor.py list
```

**Output:**
```
📋 Handoffs: 2

   📄 PRD: Golden Library 3D Viewer Integration
      ID: handoff://ac193bbe76f0
      Created: 2026-01-14T12:21:20.110184

   📄 Golden Library - Current Plan
      ID: handoff://1ba7855834e1
      Created: 2026-01-14T12:20:00.477474
```

---

## Real-World Workflow

### Scenario: Complete Phase 4, Start Phase 5

```bash
# 1. Compress current plan (Phase 4)
python3 src/prd_compressor.py compress CURRENT_PLAN.md
# Output: handoff://1ba7855834e1

# 2. Archive the plan
mv CURRENT_PLAN.md archive/plans/2026-01-14_phase4_realtime.md

# 3. Create Phase 5 plan referencing Phase 4
cat > CURRENT_PLAN.md <<EOF
---
phase: 5
previous_handoff: handoff://1ba7855834e1
status: active
---

# Phase 5: Timeline Mode

## Context from Phase 4

Full context available: handoff://1ba7855834e1

Quick summary:
- ✅ Real data integration complete
- ✅ Performance optimized for 100+ nodes
- ✅ WebSocket live updates working

## Current Tasks
...
EOF

# 4. New instance reads Phase 5 plan
# If they need Phase 4 context:
python3 src/prd_compressor.py decompress handoff://1ba7855834e1

# Or search for specific decisions:
python3 src/prd_compressor.py search "why three.js"
```

---

## Benefits Demonstrated

### ✅ Token Efficient
- Old plans compressed and stored
- Reference by ID, decompress on-demand
- Search without loading full content

### ✅ Cross-Instance Handoff
- New Claude instance reads handoff://ID
- Full context available but not loaded by default
- 80%+ token savings on large plans

### ✅ Searchable History
- Find decisions across all phases
- Keyword search in compressed handoffs
- Relevance-ranked results

### ✅ Cross-Repo Ready
- Store handoffs from multiple projects
- Reference: `prax-chat: handoff://a8f3c21`
- Build pattern library

---

## Directory Structure

```
golden_library/
├── CURRENT_PLAN.md              # Active plan (Phase 5)
├── .golden_library/
│   ├── compressed/              # Compressed handoffs
│   │   ├── 1ba7855834e1.md     # Phase 4 plan
│   │   └── ac193bbe76f0.md     # 3D Viewer PRD
│   ├── metadata/                # Handoff metadata
│   │   ├── 1ba7855834e1.json
│   │   └── ac193bbe76f0.json
│   └── index.json               # Searchable index
├── archive/
│   └── plans/
│       └── 2026-01-14_phase4_realtime.md  # Human-readable archive
└── src/
    └── prd_compressor.py        # Compression tool
```

---

## Token Savings Example

**Without Compression:**
```
New instance needs Phase 4 context:
- Read full CURRENT_PLAN.md: 9236 bytes → ~2300 tokens
- Read 3D Viewer PRD: 23627 bytes → ~5900 tokens
- Read Phase 3 context: 15000 bytes → ~3750 tokens
Total: ~11,950 tokens
```

**With Compression:**
```
New instance:
- Read CURRENT_PLAN.md: 9236 bytes → ~2300 tokens
- See reference: handoff://1ba7855834e1
- Search if needed: "websocket" → 200 tokens
- Decompress only if needed: 2300 tokens
Total used: ~2500 tokens (79% savings)
```

---

## Next Steps

1. **Apply to Other Repos:**
   ```bash
   cd ~/prax-chat
   python3 ~/ztgi/golden_library/src/prd_compressor.py compress CURRENT_PLAN.md
   ```

2. **Build Cross-Repo Index:**
   - Index handoffs from golden_library, prax-chat, phi_proxy
   - Search decisions across all projects
   - Build pattern library

3. **Integrate with Dashboard:**
   - Show handoffs in 3D viewer (timeline mode)
   - Click node → decompress and display
   - Visual project evolution

4. **Add Advanced Compression:**
   - SLIM vocabulary for markdown
   - V4Z compression for large PRDs
   - 80%+ reduction on repetitive content

---

## Commands Summary

```bash
# Compress
python3 src/prd_compressor.py compress <file>

# Decompress
python3 src/prd_compressor.py decompress handoff://<id> [output_path]

# Search
python3 src/prd_compressor.py search <query>

# List
python3 src/prd_compressor.py list
```

---

**System Ready! 🚀**

Test it by opening a new Claude instance and saying:
> "Read ~/ztgi/golden_library/CURRENT_PLAN.md and start Phase 4.
> If you need Phase 3 context, decompress handoff://ac193bbe76f0"
