# Golden Library - Current Plan

---
**Metadata:**
- **Project:** golden_library
- **Phase:** 4
- **Phase Name:** 3D Viewer Enhancement & Real-time Integration
- **Started:** 2026-01-14
- **Estimated Duration:** 3-5 days
- **Status:** active
- **Previous Handoff:** 731a228 (3D Viewer MVP Integration)
- **Dependencies:**
  - dashboard_server.py
  - universal_watcher daemon
  - compression pipeline
- **Related Work:**
  - prax-chat: Tab-based UI pattern
  - phi_proxy: Real-time updates architecture
---

## Context from Previous Phase

**Phase 3: 3D Viewer MVP** (handoff://731a228)
- ✅ Integrated standalone 3D viewer into Control Center dashboard
- ✅ Added 4 backend API endpoints (`/api/3d/*`)
- ✅ Implemented 5 layout modes (Globe, Clusters, Grid, Helix, Scatter)
- ✅ Node interaction with details panel
- ✅ Matched dashboard dark theme styling
- ✅ 60 FPS performance with demo data (20 nodes)

**What's Working:**
- Three.js rendering engine
- Tab integration
- Demo data visualization
- Basic controls

**What's Missing:**
- Real handoff data (currently shows mock data)
- Live updates
- Performance at scale (100+ nodes)
- Advanced features (timeline, export, comparison)

---

## Phase 4 Goals

Transform the 3D viewer from MVP demo to production-ready feature with:
1. Real data pipeline
2. Live updates
3. Optimized performance
4. Foundation for advanced visualizations

---

## Active Tasks - Immediate (This Phase)

### 🔴 Priority 1: Real Data Integration
**Status:** Not Started
**Owner:** Koda
**Estimated:** 4-6 hours

**Objective:** Replace demo data with actual compressed handoffs from the conversation library.

**Tasks:**
- [ ] Verify `~/.claude/conversation_library/` structure
- [ ] Test `/api/3d/handoffs` endpoint with real data
- [ ] Update `infer_compression_format()` to detect formats accurately
- [ ] Add error handling for missing/corrupted files
- [ ] Test with 0 handoffs, 1 handoff, 50+ handoffs
- [ ] Update stats calculations for real data
- [ ] Remove demo data fallback (or make it optional)

**Acceptance Criteria:**
- Viewer loads real handoffs from disk
- Stats panel shows accurate compression metrics
- Graceful handling when no data exists
- Format colors match actual compression types

**Files to Modify:**
- `dashboard_server.py` (serve_3d_handoffs, infer_compression_format)
- `claude_dashboard.html` (loadHandoffs3D function)

---

### 🟡 Priority 2: Performance Optimization
**Status:** Not Started
**Owner:** Koda
**Estimated:** 3-4 hours

**Objective:** Ensure smooth 60 FPS with 100+ nodes, implement Level of Detail (LOD).

**Tasks:**
- [ ] Benchmark current performance (10, 50, 100, 200 nodes)
- [ ] Implement LOD system (simplified geometry for distant nodes)
- [ ] Add frustum culling (hide off-screen nodes)
- [ ] Optimize node rotation (update only visible nodes)
- [ ] Implement pagination for 500+ handoffs
- [ ] Add loading spinner for initial data fetch
- [ ] Test memory usage over time (check for leaks)
- [ ] Profile render loop with Chrome DevTools

**Acceptance Criteria:**
- 60 FPS maintained with 100 nodes
- 30+ FPS with 200 nodes
- Memory stable over 5 minutes
- Smooth camera controls with any node count

**Files to Modify:**
- `claude_dashboard.html` (animate3D, createGraph3D)
- Consider: Three.js InstancedMesh for repeated geometries

**Technical Notes:**
- LOD: Switch from BoxGeometry(2,2,2) to BoxGeometry(1,1,1) when distance > 100
- Frustum culling: Use `camera.frustum.intersectsObject()`
- Rotation: Only rotate nodes within camera view

---

### 🟢 Priority 3: WebSocket Live Updates
**Status:** Not Started
**Owner:** Koda
**Estimated:** 5-6 hours

**Objective:** Show new compressions in real-time as Universal Watcher processes them.

**Tasks:**
- [ ] Add WebSocket server to `dashboard_server.py`
- [ ] Emit event when new handoff compressed
- [ ] Client subscribes to WebSocket on 3D tab open
- [ ] Animate new node appearance (fade in + glow effect)
- [ ] Update stats panel in real-time
- [ ] Add toast notification "New handoff: session_X.jsonl"
- [ ] Handle reconnection on disconnect
- [ ] Test with Universal Watcher running

**Acceptance Criteria:**
- New compressions appear within 1 second
- Stats update automatically
- Smooth animation for new nodes
- No performance degradation
- Works across tab switches

**Files to Modify:**
- `dashboard_server.py` (add websocket_handler)
- `claude_dashboard.html` (add WebSocket client)
- Integration with Universal Watcher

**Technical Notes:**
```python
# dashboard_server.py
import asyncio
from websockets import serve

async def handoff_notifier(websocket):
    # Watch for new files in compressed/
    # Emit: {"event": "new_handoff", "data": {...}}
```

```javascript
// claude_dashboard.html
const ws = new WebSocket('ws://localhost:8080/ws');
ws.onmessage = (event) => {
  const {event, data} = JSON.parse(event.data);
  if (event === 'new_handoff') addNode3D(data);
};
```

---

## Backlog - Future Phases

### Phase 5: Timeline Mode (Q1 2026)
**Estimated:** 2-3 days

Chronological visualization of handoffs over time.

**Tasks:**
- [ ] Add date-based positioning algorithm
- [ ] Timeline scrubber UI (play/pause/seek)
- [ ] Filter by date range
- [ ] Show compression trends over time
- [ ] Animate project evolution (time-lapse mode)

**Use Cases:**
- "Show me all handoffs from last week"
- "Replay project development chronologically"
- "Find when we hit 80% compression rate"

---

### Phase 6: Export Visualization
**Estimated:** 1-2 days

Save 3D view as image or animated GIF.

**Tasks:**
- [ ] Add "Export PNG" button
- [ ] Add "Export GIF" (rotating view)
- [ ] Canvas.toDataURL() for static export
- [ ] CCapture.js for animated export
- [ ] Export stats as JSON/CSV

**Use Cases:**
- Documentation screenshots
- Progress reports
- Presentations

---

### Phase 7: Comparison Mode
**Estimated:** 2-3 days

Side-by-side comparison of two handoffs or time periods.

**Tasks:**
- [ ] Split-screen 3D view
- [ ] Diff visualization (added/removed nodes)
- [ ] Compression metric comparison table
- [ ] "Before vs After" optimization view

**Use Cases:**
- "Compare compression before/after algorithm change"
- "Show impact of new compression format"
- "Diff two project states"

---

### Phase 8: VR Mode (Q3 2026)
**Estimated:** 5-7 days

Immersive VR visualization using WebXR.

**Tasks:**
- [ ] Add WebXR support
- [ ] VR controller integration
- [ ] Teleport navigation
- [ ] Hand-tracking node selection
- [ ] VR UI panels
- [ ] Test on Quest 2/3, Vision Pro

**Use Cases:**
- Immersive data exploration
- Presentations in VR
- Remote collaboration in 3D space

---

## PRD Management System Integration

### Current Phase Archive Plan

When Phase 4 completes:
```bash
# Compress current plan
python3 -m golden_library.compress CURRENT_PLAN.md
# Output: handoff://a3f8e92c

# Archive
mv CURRENT_PLAN.md archive/plans/2026-01-14_phase4_realtime.md

# Create Phase 5 plan
cat > CURRENT_PLAN.md <<EOF
---
phase: 5
previous_handoff: a3f8e92c
...
EOF
```

### Decision Log (Compressed)

**Why Three.js over Babylon.js?**
- Lighter (580KB vs 2MB)
- Better documentation
- Faster startup
- Community size

→ Compress as handoff, reference in future 3D decisions

**Why WebSocket over polling?**
- Lower latency (<100ms vs 1-5s)
- Less server load
- Native browser support
- Better UX for real-time

→ Archive: handoff://future_websocket_decision

---

## Cross-Repository Context

**Related Patterns:**
- `prax-chat`: Tab-based UI (similar structure)
- `phi_proxy`: Real-time updates via WebSocket
- `terminal_library_search`: Hybrid search implementation

**Reusable Components:**
- WebSocket setup (from phi_proxy)
- Loading states (from dashboard tabs)
- Error handling (from arsenal tab)

---

## Success Metrics

**Phase 4 Complete When:**
- ✅ Real data loads from conversation library
- ✅ 60 FPS with 100+ nodes
- ✅ Live updates working with Universal Watcher
- ✅ No console errors
- ✅ Commits pushed with handoff ID
- ✅ CURRENT_PLAN.md archived
- ✅ Phase 5 plan created

**Definition of Done:**
- Manual testing checklist passed
- Performance benchmarks met
- Real-world usage validated
- User feedback incorporated
- Documentation updated

---

## Getting Started (For New Instance)

**Quick Start:**
1. Read this file
2. Check previous handoff: `git show 731a228`
3. Start with Priority 1 (Real Data Integration)
4. Test at http://localhost:8080 (3D View tab)
5. Commit progress, check off tasks
6. When stuck: Review backlog or ask for clarification

**Key Files:**
- `dashboard_server.py` - Backend API
- `claude_dashboard.html` - Frontend (line 2307+ for 3D code)
- `PRD_3D_VIEWER_INTEGRATION.md` - Original MVP spec

**Testing:**
```bash
# Start server
cd ~/ztgi/golden_library
python3 dashboard_server.py 8080

# Open browser
open http://localhost:8080

# Click: 🌐 3D View tab
```

---

## Notes & Decisions

**2026-01-14:** MVP completed ahead of schedule (30min target, 28min actual)
- User feedback: "works pretty good, love it"
- Performance: Smooth with demo data
- Next: Focus on real data integration

---

**Last Updated:** 2026-01-14
**Next Review:** When Priority 1 complete
**Questions/Blockers:** None currently
