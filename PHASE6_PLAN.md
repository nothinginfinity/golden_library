# Golden Library - Phase 6 Plan

---
**Metadata:**
- **Project:** golden_library
- **Phase:** 6
- **Phase Name:** Comparison Mode
- **Started:** 2026-01-14
- **Estimated Duration:** 2-3 days
- **Status:** active
- **Previous Phase:** Phase 5 (Timeline Mode & Advanced Visualization)
- **Dependencies:**
  - dashboard_server.py (3D viewer with timeline)
  - claude_dashboard.html (Phase 5 features complete)
  - .golden_library/index.json (1015 handoffs)
- **Related Work:**
  - Phase 5: Timeline, filters, trends, export
  - Phase 4.5: Compression system
---

## Context from Previous Phase

**Phase 5: Timeline Mode & Advanced Visualization** (COMPLETE)
- ✅ Interactive timeline controls (play/pause/seek/speed)
- ✅ Date range filtering with presets
- ✅ Compression trends visualization (charts)
- ✅ Export capabilities (PNG, JSON, CSV)
- ✅ WebGL error handling

**What's Working:**
- 3D visualization with 6 layouts (globe, clusters, grid, helix, scatter, timeline)
- Timeline playback at 60 FPS with 1015 handoffs
- Real-time filtering (<100ms)
- Interactive D3.js charts for trends
- Export system with timestamped files
- Graceful WebGL fallback

**What's Missing:**
- Side-by-side handoff comparison
- Diff view for content changes
- Timeline period comparisons (before/after)
- Compression efficiency comparisons
- Pattern evolution tracking

---

## Phase 6 Goals

**Priority:** MEDIUM-HIGH - Enable comparative analysis

Transform single-view exploration into comparative analysis mode:
1. **Handoff Comparison** - Select and compare two handoffs
2. **Diff View** - Show what changed between handoffs
3. **Timeline Comparison** - Compare time periods (e.g., "Last month vs This month")
4. **Metrics Comparison** - Compare compression ratios, sizes, patterns
5. **Pattern Evolution** - Track how patterns change over time

**Why This Matters:**
- Understand how compression improved over time
- Identify what changed between sessions
- Compare different approaches to same problem
- Track pattern evolution and emergence
- Foundation for predictive analytics (Phase 7)

---

## Active Tasks - Immediate (This Phase)

### 🔴 Priority 1: Handoff Selection & Comparison UI
**Status:** Not Started
**Owner:** Koda
**Estimated:** 0.5 day

**Objective:** Enable selecting two handoffs for comparison.

**Tasks:**
- [ ] Add "Comparison" tab to dashboard
- [ ] Create comparison mode UI
  - Left panel: Handoff A selector
  - Right panel: Handoff B selector
  - Middle: Comparison controls
- [ ] Implement handoff selector dropdown/search
  - Search by ID, date, or filename
  - Filter by category (plan/conversation)
  - Show metadata preview on hover
- [ ] Add "Compare" button
- [ ] Show selected handoffs with metadata

**Acceptance Criteria:**
- Can select any two handoffs from 1015 total
- Search/filter works quickly (<100ms)
- Selected handoffs display clearly
- UI is intuitive and responsive

**Files to Modify:**
- `claude_dashboard.html` (add comparison tab + UI)

**Technical Notes:**
- Reuse existing handoff data from 3D viewer
- Use autocomplete/typeahead for search
- Show compression ratio, size, date in preview

---

### 🟡 Priority 2: Diff View Implementation
**Status:** Not Started
**Owner:** Koda
**Estimated:** 1 day

**Objective:** Show content differences between two handoffs.

**Tasks:**
- [ ] Fetch decompressed content for both handoffs
- [ ] Implement diff algorithm
  - Line-by-line comparison
  - Word-level diff for changed lines
  - Track additions, deletions, modifications
- [ ] Create diff visualization
  - Side-by-side view (Handoff A | Handoff B)
  - Unified diff view (GitHub-style)
  - Color coding: green=added, red=removed, yellow=changed
  - Line numbers
- [ ] Add diff statistics
  - Lines added/removed/changed
  - Percentage changed
  - Character-level changes
- [ ] Add syntax highlighting (if applicable)

**Acceptance Criteria:**
- Diff accurately shows all changes
- Side-by-side and unified views available
- Color coding is clear
- Performance: <500ms for typical handoff diff

**Files to Modify:**
- `claude_dashboard.html` (diff view UI)
- `dashboard_server.py` (add diff endpoint if needed)

**Technical Notes:**
- Use diff library (e.g., diff-match-patch, jsdiff)
- Decompress both handoffs server-side
- Stream large diffs to avoid memory issues
- Consider virtual scrolling for large files

---

### 🟢 Priority 3: Metrics Comparison
**Status:** Not Started
**Owner:** Koda
**Estimated:** 0.5 day

**Objective:** Compare compression and metadata metrics.

**Tasks:**
- [ ] Add metrics comparison panel
  - Compression ratio comparison (A vs B)
  - File size comparison (original, compressed, saved)
  - Date/time comparison
  - Category comparison
- [ ] Visualize metrics differences
  - Bar charts for size comparison
  - Percentage difference indicators
  - Color coding (green=better, red=worse)
- [ ] Add "winner" indicators
  - Which handoff compressed better?
  - Which saved more bytes?
  - Time difference
- [ ] Calculate delta/change metrics
  - Absolute difference
  - Percentage change
  - Improvement score

**Acceptance Criteria:**
- All metrics clearly displayed
- Visual comparison is intuitive
- "Better" handoff is obvious at a glance
- Calculations are accurate

**Files to Modify:**
- `claude_dashboard.html` (metrics comparison UI)

**Technical Notes:**
- Reuse data from handoff metadata
- Use D3.js for comparison charts
- Consider radar/spider chart for multi-metric view

---

### 🔵 Priority 4: Timeline Period Comparison
**Status:** Not Started
**Owner:** Koda
**Estimated:** 0.5 day

**Objective:** Compare statistics across time periods.

**Tasks:**
- [ ] Add period selector
  - "Last 7 days vs Previous 7 days"
  - "This month vs Last month"
  - "This quarter vs Last quarter"
  - Custom date range A vs B
- [ ] Aggregate statistics per period
  - Total handoffs
  - Average compression ratio
  - Total bytes saved
  - Category breakdown
- [ ] Visualize period comparison
  - Side-by-side bar charts
  - Trend lines showing change
  - Percentage improvements
- [ ] Add insights/summary
  - "Compression improved by X%"
  - "Y more handoffs this period"
  - "Most active day: ..."

**Acceptance Criteria:**
- Can compare any two time periods
- Statistics accurately aggregated
- Visual comparison is clear
- Insights are meaningful

**Files to Modify:**
- `claude_dashboard.html` (period comparison UI)

**Technical Notes:**
- Reuse timeline data from Phase 5
- Calculate aggregates client-side
- Consider week-over-week, month-over-month defaults

---

## Backlog - Future Enhancements

### Pattern Evolution Tracking
**Estimated:** 1 day

Track how patterns change between handoffs or over time.

**Tasks:**
- [ ] Compare pattern frequency (A vs B)
- [ ] Show new patterns that emerged
- [ ] Show deprecated patterns
- [ ] Visualize pattern evolution timeline

---

### Multi-Handoff Comparison
**Estimated:** 1 day

Compare more than 2 handoffs at once.

**Tasks:**
- [ ] Support 3-5 handoff comparison
- [ ] Matrix view for multi-comparison
- [ ] Aggregate metrics across all
- [ ] Identify outliers

---

## Success Metrics

**Phase 6 Complete When:**
- [ ] Can select any two handoffs for comparison
- [ ] Diff view shows content changes accurately
- [ ] Metrics comparison is visual and clear
- [ ] Timeline period comparison works
- [ ] Performance remains good (<500ms for diffs)
- [ ] UI is intuitive and responsive
- [ ] Documentation updated
- [ ] Code committed and tested

**Definition of Done:**
- All priority tasks completed
- Comparison features work smoothly
- Diff view handles large files
- Metrics calculations are accurate
- No performance degradation
- Code is committed and documented

---

## Getting Started

**Quick Start:**
1. Read this file
2. Start with Priority 1 (Comparison UI)
3. Test with sample handoffs
4. Move to Priority 2 (Diff View)
5. Commit progress incrementally

**Key Files:**
- `claude_dashboard.html` - Frontend (add comparison tab)
- `dashboard_server.py` - Backend (diff endpoint if needed)
- `.golden_library/index.json` - Handoff metadata

**Testing:**
```bash
# Start dashboard
cd ~/ztgi/golden_library
python3 dashboard_server.py

# Open in browser
open http://localhost:8080

# Test comparison mode
# Select two handoffs, compare metrics, view diff
```

---

## Notes & Decisions

**2026-01-14:** Phase 6 started
- Phase 5 complete with all features working
- 1015 handoffs available for comparison
- WebGL working after fixes

**Architecture Decision: Client-Side vs Server-Side Diff?**
- **Client-side:** Fast for small files, no server load
- **Server-side:** Better for large files, can use robust diff libraries
- **Decision:** Hybrid approach:
  - Fetch decompressed content from server
  - Run diff algorithm client-side (jsdiff library)
  - For very large files (>1MB), use server-side diff endpoint

**UI Design Philosophy:**
- Side-by-side layout for direct comparison
- Clear visual indicators (green/red/yellow)
- Metrics displayed prominently
- "Winner" clearly identified for each metric
- Easy to switch between handoffs

---

**Last Updated:** 2026-01-14
**Next Review:** After Priority 1 complete
**Questions/Blockers:** None currently

**Progress:**
- 🔜 Priority 1: Handoff Selection & Comparison UI (next task)
- ⏸️ Priority 2: Diff View Implementation
- ⏸️ Priority 3: Metrics Comparison
- ⏸️ Priority 4: Timeline Period Comparison
