# PRD: Golden Library 3D Viewer Integration

**Version:** 1.0
**Date:** 2026-01-14
**Status:** Ready for Implementation
**Complexity:** High (30-45 minutes estimated)

---

## Executive Summary

Integrate the existing standalone Golden Library 3D viewer (`viewer.html`) into the Claude Control Center dashboard as a native tab. This will provide users with an immersive 3D visualization of their compressed conversation library directly within the control center, eliminating the need for a separate viewer application.

---

## Current State

### What Exists
1. **Standalone 3D Viewer** (`viewer.html`)
   - Location: `~/ztgi/golden_library/viewer.html`
   - Size: 26,852 bytes
   - Technology: Three.js for 3D graphics
   - Features:
     - 3D node visualization (handoffs as cubes)
     - 5 layout modes (Globe, Clusters, Cubic Grid, Helix, Scatter)
     - Color-coded by compression format (SLIM, V4Z, FSL, ZTPCF)
     - Interactive controls (orbit, click nodes for details)
     - Hybrid search (local + metadata)
     - Compression statistics panel
     - Node details panel with actions

2. **Standalone Backend** (`viewer_backend.py`)
   - Port: 8080 (conflicts with dashboard)
   - Flask-based API server
   - CORS enabled
   - Endpoints:
     - `GET /` - Serve viewer HTML
     - `GET /api/handoffs` - List all handoffs
     - `GET /api/handoff/<id>` - Get handoff details
     - `POST /api/handoff/<id>/decompress` - Decompress handoff
     - `GET /api/stats` - Overall statistics

3. **Dashboard** (`claude_dashboard.html` + `dashboard_server.py`)
   - Port: 8080 (unified server)
   - Current tabs: Dashboard, Search, Config, Arsenal, MCP, Daemons, Charts
   - Python HTTP server (not Flask)

### The Gap
- 3D viewer runs as separate application on same port
- No integration with Control Center
- Duplicate backend server
- User must switch between applications

---

## Goals

### Primary Goals
1. **Unified Experience:** Single application at `localhost:8080` with 3D viewer as native tab
2. **Feature Parity:** Preserve all existing 3D viewer functionality
3. **No Regressions:** Maintain all current dashboard features
4. **Performance:** 60 FPS 3D rendering, smooth interactions

### Secondary Goals
1. **Code Consolidation:** Merge viewer backend APIs into dashboard server
2. **Consistent Styling:** Match dashboard's dark theme and color palette
3. **Shared State:** Use same compressed conversation data as Search tab

---

## Technical Requirements

### Architecture

#### Frontend Integration
```
claude_dashboard.html
├── Existing tabs (7)
└── NEW: 3D View tab (tab-3dview)
    ├── Three.js library (CDN)
    ├── Canvas container
    ├── UI panels (search, stats, controls, details)
    └── 3D scene management
```

#### Backend Integration
```
dashboard_server.py
├── Existing endpoints
└── NEW: 3D Viewer endpoints
    ├── /api/3d/handoffs - List handoffs for 3D
    ├── /api/3d/stats - 3D-specific stats
    ├── /api/3d/search - Search handoffs
    └── /api/3d/decompress - Decompress actions
```

### Technology Stack

#### Required Libraries
```html
<!-- Three.js (3D rendering) -->
<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>

<!-- OrbitControls (camera control) -->
<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/examples/js/controls/OrbitControls.js"></script>
```

#### Data Source
- Primary: `~/.claude/conversation_library/compressed/`
- Index: `~/.claude/conversation_library/index.json`
- Format: SLIM, V4Z, FSL, ZTPCF compressed handoffs

---

## UI/UX Specifications

### Tab Addition

**Location:** Between Charts and (future) AI Chat tabs

```html
<!-- Navigation -->
<button class="tab-btn" onclick="showTab('3dview')">🌐 3D View</button>

<!-- Content -->
<div id="tab-3dview" class="tab-content">
  <!-- 3D Viewer content here -->
</div>
```

### Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│ 🌐 3D VIEW TAB                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                                          │
│  │              │                                          │
│  │  UI PANEL    │         3D CANVAS                       │
│  │              │      (Full remaining space)             │
│  │  - Search    │                                          │
│  │  - Stats     │                                          │
│  │  - Layouts   │                                          │
│  │  - Controls  │                                          │
│  │              │                                          │
│  └──────────────┘                                          │
│                                                             │
│                          ┌──────────────────┐              │
│                          │  DETAILS PANEL   │              │
│                          │  (Slide-in)      │              │
│                          │  - Node info     │              │
│                          │  - Compression   │              │
│                          │  - Actions       │              │
│                          └──────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Design System

**Colors** (match existing dashboard)
```css
Background: #0f172a (slate-900)
Panels: rgba(30, 41, 59, 0.95) with backdrop-blur
Borders: #334155 (slate-700)
Text Primary: #e2e8f0 (slate-200)
Text Secondary: #94a3b8 (slate-400)
Accent: #6366f1 (indigo-500)
Gold Accent: #f7b731 (matches existing Gold Library branding)
```

**Node Colors** (compression formats)
```javascript
{
  slim_only: 0x6366f1,    // Indigo (SLIM only)
  slim_v4z: 0xf7b731,     // Gold (SLIM + V4Z)
  slim_fsl: 0xaa66cc,     // Purple (SLIM + FSL)
  slim_ztpcf: 0x10b981    // Green (SLIM + ZTPCF)
}
```

### UI Components

#### 1. Left Panel (320px wide, fixed position)
```html
<div class="viewer-panel">
  <div class="panel-header">
    <h3>🌐 GOLDEN LIBRARY 3D</h3>
    <button class="panel-minimize">−</button>
  </div>

  <!-- Search Section -->
  <div class="viewer-section search-section">
    <h4>HYBRID SEARCH</h4>
    <input type="text" class="search-input" placeholder="Search handoffs...">
    <div class="search-options">
      <label><input type="checkbox" checked> Local</label>
      <label><input type="checkbox" checked> Metadata</label>
    </div>
    <button class="search-btn">Search</button>
    <div class="search-status">Ready - N handoffs loaded</div>
  </div>

  <!-- Stats Section -->
  <div class="viewer-section stats-section">
    <h4>COMPRESSION STATS</h4>
    <div class="stat-row">
      <span>Total Handoffs:</span>
      <span id="stat-count">-</span>
    </div>
    <div class="stat-row">
      <span>Original Size:</span>
      <span id="stat-original">-</span>
    </div>
    <div class="stat-row">
      <span>Compressed Size:</span>
      <span id="stat-compressed">-</span>
    </div>
    <div class="stat-row">
      <span>Total Savings:</span>
      <span id="stat-savings" class="stat-highlight">-</span>
    </div>
  </div>

  <!-- View Mode Section -->
  <div class="viewer-section">
    <h4>View Mode</h4>
    <button class="layout-btn active" onclick="changeLayout3D('globe')">Globe</button>
    <button class="layout-btn" onclick="changeLayout3D('clusters')">Clusters</button>
    <button class="layout-btn" onclick="changeLayout3D('grid')">Cubic Grid</button>
    <button class="layout-btn" onclick="changeLayout3D('helix')">Helix</button>
    <button class="layout-btn" onclick="changeLayout3D('scatter')">Scatter</button>
  </div>

  <!-- Controls Section -->
  <div class="viewer-section">
    <h4>Controls</h4>
    <button class="control-btn" onclick="toggleAutoOrbit()">
      <span id="orbit-status">Auto-Orbit: OFF</span>
    </button>
    <button class="control-btn" onclick="toggleConnections()">Toggle Connections</button>
    <button class="control-btn" onclick="reloadData3D()">Reload Data</button>
  </div>

  <div class="viewer-footer">
    Nodes: <span id="node-count">0</span> | Links: <span id="link-count">0</span>
  </div>
</div>
```

#### 2. Details Panel (right side, slide-in)
```html
<div id="details-panel" class="details-panel" style="display: none;">
  <div class="panel-header">
    <h3>Handoff Details</h3>
    <button onclick="closeDetailsPanel()">×</button>
  </div>

  <div class="details-content">
    <div class="detail-title" id="detail-filename">-</div>
    <div class="detail-meta">
      <span>ID: <span id="detail-id">-</span></span>
    </div>

    <div class="detail-section">
      <h4>COMPRESSION</h4>
      <div class="detail-row">
        <span>Format:</span>
        <span id="detail-format" class="badge">-</span>
      </div>
      <div class="detail-row">
        <span>Reduction:</span>
        <span id="detail-reduction">-</span>
        <span id="detail-quality" class="badge">-</span>
      </div>
    </div>

    <div class="detail-section">
      <h4>FILE SIZES</h4>
      <div class="detail-row">
        <span>Original:</span>
        <span id="detail-original-size">-</span>
      </div>
      <div class="detail-row">
        <span>Compressed:</span>
        <span id="detail-compressed-size">-</span>
      </div>
      <div class="detail-row">
        <span>Saved:</span>
        <span id="detail-saved-size" class="text-green">-</span>
      </div>
    </div>

    <div class="detail-section">
      <h4>METADATA</h4>
      <div class="detail-row">
        <span>Created:</span>
        <span id="detail-created">-</span>
      </div>
    </div>

    <div class="detail-actions">
      <button class="action-btn" onclick="decompressHandoff()">Decompress</button>
      <button class="action-btn" onclick="viewStats()">Stats</button>
      <button class="action-btn" onclick="downloadHandoff()">Download</button>
    </div>
  </div>
</div>
```

#### 3. Canvas Container
```html
<div id="canvas-3d" style="position: absolute; top: 0; left: 360px; right: 0; bottom: 0;"></div>
```

---

## API Specifications

### Backend Endpoints

Add to `dashboard_server.py`:

#### 1. GET /api/3d/handoffs
**Purpose:** List all compressed handoffs for 3D visualization

**Response:**
```json
{
  "ok": true,
  "count": 142,
  "handoffs": [
    {
      "id": "10023e8b-2e23-4d07-8112-b7dbe443f204",
      "filename": "session_2026-01-13.jsonl",
      "compression_format": "slim_v4z",
      "original_size": 2654321,
      "final_size": 1450890,
      "reduction_percent": 45.3,
      "created": "2026-01-13T15:30:45",
      "project_id": "golden_library",
      "session_id": "session_001"
    }
  ]
}
```

#### 2. GET /api/3d/stats
**Purpose:** Overall compression statistics

**Response:**
```json
{
  "ok": true,
  "total_handoffs": 142,
  "total_original_bytes": 285672100,
  "total_compressed_bytes": 156820450,
  "avg_reduction_percent": 45.1,
  "formats": {
    "slim_only": 34,
    "slim_v4z": 67,
    "slim_fsl": 28,
    "slim_ztpcf": 13
  }
}
```

#### 3. POST /api/3d/search
**Purpose:** Search handoffs by query

**Request:**
```json
{
  "query": "session",
  "search_local": true,
  "search_metadata": true
}
```

**Response:**
```json
{
  "ok": true,
  "results": [
    {
      "id": "...",
      "filename": "...",
      "match_score": 0.95
    }
  ]
}
```

#### 4. POST /api/3d/handoff/decompress
**Purpose:** Decompress a handoff

**Request:**
```json
{
  "handoff_id": "10023e8b-2e23-4d07-8112-b7dbe443f204"
}
```

**Response:**
```json
{
  "ok": true,
  "output_file": "~/.claude/decompressed/session_2026-01-13.jsonl",
  "size": 2654321
}
```

### Data Source Implementation

```python
def get_3d_handoffs():
    """Get handoffs from conversation library."""
    library_dir = HOME / ".claude" / "conversation_library"
    compressed_dir = library_dir / "compressed"
    index_file = library_dir / "index.json"

    handoffs = []

    # Load index
    if index_file.exists():
        with open(index_file, 'r') as f:
            index = json.load(f)

        for conv in index.get('conversations', []):
            handoffs.append({
                'id': conv.get('session_id', 'unknown'),
                'filename': Path(conv['compressed_file']).name,
                'compression_format': infer_format(conv),
                'original_size': conv.get('original_tokens', 0) * 4,  # Approx
                'final_size': conv.get('compressed_tokens', 0) * 4,
                'reduction_percent': conv.get('reduction_percent', 0),
                'created': conv.get('compressed_at'),
                'project_id': conv.get('project_id', 'unknown'),
                'session_id': conv.get('session_id', 'unknown')
            })

    return {'ok': True, 'count': len(handoffs), 'handoffs': handoffs}

def infer_format(conv):
    """Infer compression format from conversation metadata."""
    # Check file extensions or metadata
    filename = conv.get('compressed_file', '')
    if 'v4z' in filename:
        return 'slim_v4z'
    elif 'fsl' in filename:
        return 'slim_fsl'
    elif 'ztpcf' in filename:
        return 'slim_ztpcf'
    else:
        return 'slim_only'
```

---

## Implementation Steps

### Phase 1: Backend Integration (Dashboard Server)
**Time:** 10-15 minutes

1. **Add 3D API endpoints to `dashboard_server.py`:**
   - Copy relevant code from `viewer_backend.py`
   - Adapt Flask-style code to SimpleHTTPServer style
   - Add routes: `/api/3d/handoffs`, `/api/3d/stats`, `/api/3d/search`, `/api/3d/handoff/decompress`

2. **Implement data loading:**
   - Read from `~/.claude/conversation_library/index.json`
   - Parse compressed files metadata
   - Format for 3D viewer consumption

3. **Test endpoints:**
   ```bash
   curl http://localhost:8080/api/3d/handoffs | jq
   curl http://localhost:8080/api/3d/stats | jq
   ```

### Phase 2: Frontend HTML Structure (Dashboard)
**Time:** 5 minutes

1. **Add tab button:**
   ```html
   <button class="tab-btn" onclick="showTab('3dview')">🌐 3D View</button>
   ```

2. **Add tab content container:**
   ```html
   <div id="tab-3dview" class="tab-content">
     <div class="viewer-panel"><!-- Left panel --></div>
     <div id="canvas-3d"></div>
     <div id="details-panel" class="details-panel"><!-- Details --></div>
   </div>
   ```

3. **Add Three.js library imports:**
   ```html
   <script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>
   <script src="https://cdn.jsdelivr.net/npm/three@0.160.0/examples/js/controls/OrbitControls.js"></script>
   ```

### Phase 3: CSS Styling
**Time:** 5 minutes

1. **Add 3D viewer specific styles:**
   - Canvas positioning
   - Left panel styling (match existing dashboard panels)
   - Details panel slide-in animation
   - Button states and hover effects
   - Stats display

2. **Ensure responsive behavior:**
   - Canvas resizes with window
   - Panels remain fixed/scrollable

### Phase 4: JavaScript 3D Engine
**Time:** 15-20 minutes

1. **Copy and adapt core 3D code from `viewer.html`:**
   - Scene setup (camera, renderer, lights)
   - Node creation and positioning
   - Layout algorithms (globe, clusters, grid, helix, scatter)
   - OrbitControls configuration
   - Animation loop

2. **Implement event handlers:**
   - Node click → show details panel
   - Layout button clicks → change arrangement
   - Auto-orbit toggle
   - Window resize → update camera/renderer

3. **Data loading:**
   - Fetch from `/api/3d/handoffs` on tab load
   - Parse and create 3D nodes
   - Apply colors based on compression format
   - Update stats panel

4. **Search integration:**
   - Filter visible nodes based on query
   - Highlight matching nodes
   - Update stats for filtered view

### Phase 5: Tab Integration
**Time:** 3 minutes

1. **Update `showTab()` function:**
   ```javascript
   if (tabName === '3dview') {
     load3DView();
     init3DScene();
   }
   ```

2. **Implement lazy loading:**
   - Only initialize Three.js when tab first opened
   - Reuse scene on subsequent visits
   - Cleanup on tab close (optional, for performance)

### Phase 6: Testing
**Time:** 5 minutes

1. **Functional testing:**
   - All 5 layouts render correctly
   - Node clicking shows correct details
   - Search filters nodes properly
   - Stats update accurately
   - Auto-orbit works smoothly

2. **Performance testing:**
   - 60 FPS with 100+ nodes
   - Smooth rotation/zoom
   - No memory leaks on tab switching

3. **Integration testing:**
   - Doesn't break existing dashboard tabs
   - API endpoints don't conflict
   - Styling consistent with dashboard

---

## Code Migration Guide

### Key Files to Reference

1. **`viewer.html`** (source for 3D code)
   - Extract JavaScript sections:
     - Three.js scene setup (lines ~600-800)
     - Layout algorithms (lines ~800-1000)
     - Node creation (lines ~400-600)
     - Event handlers (lines ~1000-1200)
   - Extract CSS:
     - Panel styles (lines ~10-200)
     - Button styles (lines ~50-150)

2. **`viewer_backend.py`** (source for API logic)
   - Adapt endpoints to `dashboard_server.py` style
   - Reuse handoff parsing logic

### Style Consistency Rules

**Match existing dashboard styling:**
```css
/* Panels */
background: rgba(30, 41, 59, 0.95);
border: 1px solid #334155;
border-radius: 12px;

/* Buttons */
.search-btn, .filter-btn styles from dashboard

/* Text */
.chart-title, .result-title styles from dashboard

/* Colors */
Use dashboard's slate/indigo palette, add gold for nodes
```

---

## Success Criteria

### Must Have (MVP)
- ✅ 3D View tab visible in dashboard
- ✅ Loads and displays compressed conversations as 3D nodes
- ✅ 5 layout modes functional (Globe, Clusters, Grid, Helix, Scatter)
- ✅ Click node shows details panel
- ✅ Stats panel shows accurate compression data
- ✅ Styling matches dashboard theme
- ✅ No conflicts with existing tabs
- ✅ 60 FPS performance with <100 nodes

### Should Have
- ✅ Search filters visible nodes
- ✅ Auto-orbit mode
- ✅ Color-coded by compression format
- ✅ Details panel shows all metadata
- ✅ Responsive to window resize

### Nice to Have (Future)
- ⏸️ Timeline mode (chronological visualization)
- ⏸️ Comparison mode (side-by-side handoff comparison)
- ⏸️ Export visualization as image
- ⏸️ WebSocket live updates
- ⏸️ VR mode support

---

## Known Challenges

### 1. Three.js Library Size
**Issue:** Large CDN download (~580KB)
**Solution:** Use CDN with caching, lazy load on tab open

### 2. Port Conflict
**Issue:** Viewer backend uses 8080, dashboard uses 8080
**Solution:** Merge into single dashboard server

### 3. Data Format Differences
**Issue:** Viewer expects handoff format, dashboard has conversation index
**Solution:** Adapter function to convert index → handoff format

### 4. Performance with Many Nodes
**Issue:** 500+ nodes may impact FPS
**Solution:**
- LOD (Level of Detail) - simplify distant nodes
- Culling - hide off-screen nodes
- Limit initial load to 200 nodes, paginate rest

---

## Testing Plan

### Unit Tests
```javascript
// Test layout algorithms
testGlobeLayout() // Nodes arranged in sphere
testClusterLayout() // Nodes grouped by format
testGridLayout() // Nodes in cubic grid

// Test data loading
testHandoffParsing() // Correct metadata extraction
testStatsCalculation() // Accurate compression stats
```

### Integration Tests
```javascript
// Test API integration
testHandoffsEndpoint() // Returns valid JSON
testStatsEndpoint() // Accurate statistics
testSearchEndpoint() // Filters correctly

// Test UI integration
testTabSwitching() // 3D scene initializes/cleans up
testDetailsPanel() // Shows on node click
testLayoutSwitch() // Transitions smoothly
```

### Manual Testing Checklist
```
[ ] Open dashboard at localhost:8080
[ ] Click 3D View tab
[ ] Verify nodes appear in 3D space
[ ] Click each layout button, verify different arrangements
[ ] Click a node, verify details panel opens
[ ] Verify stats panel shows correct totals
[ ] Search for "session", verify filtering
[ ] Toggle auto-orbit, verify rotation
[ ] Resize window, verify canvas adapts
[ ] Switch to another tab and back, verify scene persists
[ ] Check browser console for errors
[ ] Test in Chrome, Firefox, Safari
```

---

## Rollout Plan

### Phase 1: Development
1. Implement backend endpoints
2. Add frontend structure
3. Integrate 3D engine
4. Basic styling

### Phase 2: Testing
1. Internal testing (100 handoffs)
2. Performance profiling
3. Cross-browser testing
4. Bug fixes

### Phase 3: Documentation
1. Update CONTROL_CENTER_ARCHITECTURE.md
2. Add 3D View section to README
3. Screenshot/GIF of feature

### Phase 4: Deployment
1. Commit to git
2. Push to remote
3. User announcement

---

## Future Enhancements

### Q1 2026
- Timeline mode (chronological visualization)
- Export visualization as PNG/GIF
- Filters by date range, size, format

### Q2 2026
- Comparison mode (compare 2 handoffs side-by-side)
- WebSocket live updates (new compressions appear in real-time)
- Graph view (show conversation relationships)

### Q3 2026
- VR mode (WebXR support)
- Collaborative viewing (multi-user)
- AI insights (cluster analysis, pattern detection)

---

## References

### Existing Code
- **3D Viewer:** `~/ztgi/golden_library/viewer.html`
- **Backend:** `~/ztgi/golden_library/viewer_backend.py`
- **Dashboard:** `~/ztgi/golden_library/claude_dashboard.html`
- **Server:** `~/ztgi/golden_library/dashboard_server.py`
- **Docs:** `~/ztgi/golden_library/VIEWER_README.md`

### Libraries
- **Three.js:** https://threejs.org/docs/
- **OrbitControls:** https://threejs.org/docs/#examples/en/controls/OrbitControls

### Design References
- Screenshots provided show desired UI layout
- Match Terminal Library 3D aesthetic but with gold/amber theme
- Maintain dashboard's dark slate color scheme

---

## Acceptance Criteria

**Ready to Ship When:**
1. ✅ 3D View tab functional in dashboard
2. ✅ All 5 layouts working
3. ✅ Node interaction (click, details) working
4. ✅ Stats accurate
5. ✅ Search functional
6. ✅ No regressions in other tabs
7. ✅ Performance ≥60 FPS with 100 nodes
8. ✅ Code committed to git
9. ✅ Documentation updated
10. ✅ Manual testing checklist complete

---

## Questions for Implementation

1. **Should we keep viewer_backend.py for standalone use?**
   - Recommendation: Yes, keep for backwards compatibility

2. **Should 3D view auto-load on dashboard open?**
   - Recommendation: No, lazy load when tab first clicked (performance)

3. **Maximum nodes to display?**
   - Recommendation: 500 max, with pagination/filtering

4. **Should we show Universal Watcher compressions in real-time?**
   - Recommendation: Phase 2 feature (WebSocket integration)

---

**This PRD is implementation-ready. Another Claude instance can use this to build the feature end-to-end.**
