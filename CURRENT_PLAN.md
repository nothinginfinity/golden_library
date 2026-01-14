# Golden Library - Current Plan

---
**Metadata:**
- **Project:** golden_library
- **Phase:** 4.5
- **Phase Name:** Compression System Enhancement
- **Started:** 2026-01-14
- **Estimated Duration:** 3-4 days
- **Status:** active
- **Previous Handoff:** 5a4d5ca (Phase 4: 3D Viewer Performance & Real-time)
- **Dependencies:**
  - dashboard_server.py (3D viewer)
  - compression pipeline (existing)
  - git hooks system
- **Related Work:**
  - Phase 4: 3D viewer with WebSocket updates
  - Existing SLIM compression format
  - handoff:// protocol foundation
---

## Context from Previous Phase

**Phase 4: 3D Viewer Enhancement & Real-time Integration** (handoff://5a4d5ca)
- ✅ Integrated real data from conversation library (99 handoffs)
- ✅ Performance optimization: LOD, frustum culling, 60 FPS with 100+ nodes
- ✅ WebSocket live updates with fade-in animations
- ✅ Toast notifications for new compressions
- ✅ FPS counter and performance monitoring

**What's Working:**
- 3D visualization of compressed handoffs
- Real-time updates when new compressions happen
- Smooth 60 FPS performance with 100+ nodes
- WebSocket server broadcasting file system events

**What's Missing:**
- Effective compression (current: 0-0.5% reduction)
- Automated archival and handoff ID generation
- Cross-repository handoff indexing
- Pattern library for reusable solutions

---

## Phase 4.5 Goals

**Priority:** HIGH - Foundation for all future phases

Transform compression system from basic format detection to production-ready token-efficient handoff:// protocol with:
1. Advanced compression (80%+ reduction vs current 0-0.5%)
2. Automated workflows (git hooks, archival)
3. 3D visualization integration
4. Cross-repo pattern library

**Why This Matters:**
- Current: 100KB PRD = ~25,000 tokens
- Target: 100KB PRD → 20KB compressed = ~5,000 tokens (80% savings)
- Makes handoff:// protocol actually useful for token efficiency
- Foundation for Timeline Mode (Phase 5) and advanced features

---

## Active Tasks - Immediate (This Phase)

### 🔴 Priority 1: Advanced Compression
**Status:** Not Started
**Owner:** Koda
**Estimated:** 1-2 days

**Objective:** Implement SLIM vocabulary and V4Z compression for 80%+ reduction on large PRDs.

**Tasks:**
- [ ] Analyze existing compression formats (SLIM, V4Z, FSL, ZTPCF)
- [ ] Design SLIM vocabulary for markdown
  - Common markdown patterns → tokens
  - Task list syntax compression
  - Code block header optimization
  - Repeated phrases dictionary
- [ ] Implement V4Z compression layer
  - Zstandard-based compression
  - Dictionary training on PRD corpus
  - Backward compatible decompression
- [ ] Build compression benchmark suite
  - Test with CURRENT_PLAN.md (~11KB)
  - Test with large PRDs (100KB+)
  - Measure: ratio, speed, token savings
- [ ] Optimize decompression speed
  - Target: <100ms for 100KB file
  - Cache decompressed results

**Acceptance Criteria:**
- 80%+ compression on repetitive content
- Backward compatible with existing formats
- Decompression < 100ms
- No data loss on round-trip

**Files to Create/Modify:**
- `src/qastone_compressor.py` (already exists, enhance)
- `src/qastone_types.py` (already exists, enhance)
- `src/slim_vocabulary.py` (new)
- `src/v4z_compressor.py` (new)
- `tests/test_compression_benchmarks.py` (new)

**Technical Notes:**
- Use Zstandard (zstd) for V4Z base compression
- Train dictionary on corpus of PRDs for better ratios
- SLIM vocabulary should be human-readable for debugging
- Consider: LZ4 for speed vs zstd for ratio tradeoff

---

### 🟡 Priority 2: Automation & Git Hooks
**Status:** Not Started
**Owner:** Koda
**Estimated:** 1 day

**Objective:** Automate compression on git commit and phase archival.

**Tasks:**
- [ ] Create git pre-commit hook
  - Detect changes to CURRENT_PLAN.md
  - Auto-compress to `.golden_library/compressed/`
  - Generate handoff ID (first 8 chars of hash)
  - Update `previous_handoff` references
  - Validate handoff:// references resolve
- [ ] Build archive-phase.sh script
  - Move CURRENT_PLAN.md to archive/plans/YYYY-MM-DD_phaseN_name.md
  - Compress archived plan
  - Generate index entry
  - Create stub for next phase
  - Git commit with proper message
- [ ] Add unarchive/decompress utilities
  - `unarchive-phase.sh <handoff_id>` → restore to working dir
  - `decompress.py <handoff_id>` → stdout decompressed content

**Acceptance Criteria:**
- Pre-commit hook runs automatically
- archive-phase.sh works without manual steps
- Handoff IDs are stable and unique
- Can restore any previous phase

**Files to Create:**
- `.git/hooks/pre-commit` (or `.githooks/pre-commit`)
- `scripts/archive-phase.sh`
- `scripts/unarchive-phase.sh`
- `src/decompress.py`

**Technical Notes:**
- Hook should fail gracefully if compression errors
- Store handoff ID in commit message for traceability
- Archive script should update `.golden_library/index.json`

---

### 🟢 Priority 3: 3D Viewer Integration
**Status:** Not Started
**Owner:** Koda
**Estimated:** 1 day

**Objective:** Visualize compressed handoffs in 3D viewer, click to decompress and view.

**Tasks:**
- [ ] Add `.golden_library/index.json` format
  - Schema: handoff_id, phase, date, size_original, size_compressed, tags
- [ ] Update `/api/3d/handoffs` to include archived handoffs
  - Current: only conversation_library handoffs
  - New: merge with .golden_library handoffs
  - Color by type: conversation (blue), plan (green)
- [ ] Add click handler for plan handoffs
  - Show decompressed content in modal
  - Display metadata: phase, date, reduction %
  - Add "Restore to CURRENT_PLAN.md" button
- [ ] Implement timeline layout mode
  - Position nodes chronologically on timeline
  - X-axis = time, Y-axis = compression ratio
  - Scrubber to navigate time range

**Acceptance Criteria:**
- Archived plans appear in 3D viewer
- Click → modal shows decompressed content
- Timeline mode shows project evolution
- Can restore archived plan to working directory

**Files to Modify:**
- `dashboard_server.py` (add index.json read, merge handoffs)
- `claude_dashboard.html` (timeline layout, modal)
- `.golden_library/index.json` (new)

**Technical Notes:**
- Timeline X-axis: `Date.parse(created)`
- Timeline Y-axis: `100 - reduction_percent`
- Use different node shapes: sphere=conversation, cube=plan

---

### 🟣 Priority 4: Cross-Repo Pattern Library
**Status:** Not Started
**Owner:** Koda
**Estimated:** 1 day

**Objective:** Build searchable pattern library across multiple repositories.

**Tasks:**
- [ ] Design pattern extraction system
  - Scan handoffs for common solutions
  - Tag by category: auth, websocket, 3D, database, etc.
  - Extract code snippets + context
- [ ] Build cross-repo index
  - Script: `scan-repos.py --repos ~/ztgi/*`
  - Output: `~/.golden_library/cross_repo_index.json`
  - Schema: repo, handoff_id, pattern_tags, snippet
- [ ] Add pattern search API
  - `/api/patterns/search?q=websocket+auth`
  - Return: matching handoffs with context
- [ ] UI for pattern browser
  - New tab in dashboard: "Patterns"
  - Tag cloud for categories
  - Click tag → show matching patterns
  - Click pattern → view full handoff

**Acceptance Criteria:**
- Can search across 5+ repos
- Pattern extraction finds 10+ reusable patterns
- Search returns relevant results
- UI makes patterns discoverable

**Files to Create:**
- `scripts/scan-repos.py`
- `scripts/extract-patterns.py`
- Add pattern search to `dashboard_server.py`
- Add Patterns tab to `claude_dashboard.html`

**Technical Notes:**
- Use simple keyword matching for v1
- Later: embeddings + semantic search
- Store snippets with ±10 lines context
- Dedup similar patterns across repos

---

## Backlog - Future Phases

### Phase 5: Timeline Mode (Q1 2026)
**Estimated:** 2-3 days

Chronological visualization of handoffs (builds on 4.5 timeline layout).

**Tasks:**
- [ ] Enhanced timeline with play/pause/seek
- [ ] Filter by date range, repo, category
- [ ] Show compression trends over time
- [ ] Animate project evolution (time-lapse)

---

### Phase 6: Export Visualization
**Estimated:** 1-2 days

Save 3D views as images/GIFs for documentation.

**Tasks:**
- [ ] Export PNG (static snapshot)
- [ ] Export GIF (rotating view)
- [ ] Export stats as JSON/CSV

---

### Phase 7: Comparison Mode
**Estimated:** 2-3 days

Side-by-side diff of two handoffs or time periods.

---

### Phase 8: VR Mode
**Estimated:** 5-7 days

Immersive VR visualization (WebXR).

---

## Success Metrics

**Phase 4.5 Complete When:**
- ✅ 80%+ compression ratio on large PRDs
- ✅ Git pre-commit hook auto-compresses plans
- ✅ Archived handoffs visible in 3D viewer
- ✅ Cross-repo pattern search functional
- ✅ Timeline mode shows project evolution
- ✅ Pattern library has 10+ entries
- ✅ Commits pushed with handoff references
- ✅ CURRENT_PLAN.md archived for Phase 5
- ✅ Phase 5 plan created

**Definition of Done:**
- Compression benchmarks pass
- Git hooks tested on real commits
- 3D viewer loads archived plans
- Pattern search returns relevant results
- Documentation updated
- User can navigate project history in 3D

---

## Getting Started (For New Instance)

**Quick Start:**
1. Read this file
2. Check previous handoff: `git show 5a4d5ca`
3. Start with Priority 1 (Advanced Compression)
4. Benchmark current compression vs target
5. Commit progress, check off tasks
6. When stuck: Review backlog or ask for clarification

**Key Files:**
- `src/qastone_compressor.py` - Main compression logic
- `src/qastone_types.py` - Type definitions
- `dashboard_server.py` - Backend API (includes 3D viewer)
- `claude_dashboard.html` - Frontend UI
- `.golden_library/` - Compressed handoff storage

**Testing:**
```bash
# Benchmark compression
python3 -m pytest tests/test_compression_benchmarks.py -v

# Test git hook
git add CURRENT_PLAN.md
git commit -m "test: verify pre-commit hook"

# View in 3D
open http://localhost:8080 → 3D View tab

# Search patterns
curl http://localhost:8080/api/patterns/search?q=websocket
```

---

## Notes & Decisions

**2026-01-14:** Phase 4 completed successfully
- 3D viewer with real-time updates working
- 60 FPS performance confirmed
- WebSocket infrastructure ready
- Ready for compression enhancement

**Current Compression Status:**
- SLIM only: ~60% reduction (mostly whitespace)
- Need: 80%+ reduction on actual content
- Problem: Repetitive markdown patterns not compressed
- Solution: SLIM vocabulary + V4Z layer

**Architecture Decision: Why V4Z?**
- Zstandard provides 70-80% compression on text
- Dictionary training learns project-specific patterns
- Faster decompression than gzip/bzip2
- Widely supported, battle-tested

---

**Last Updated:** 2026-01-14
**Next Review:** After Priority 1 complete
**Questions/Blockers:** None currently
