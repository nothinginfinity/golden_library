# HANDOFF: Canvas UX Improvements

**Date:** 2026-01-19
**Role:** KODA (Builder)
**Project:** Golden Library - Collaborative Document System

---

## Project Location

```
/Users/kanelawaccount/ztgi/golden_library/
```

**Production URL:** https://golden-library-production.up.railway.app/

---

## Key Files to Reference

| File | Purpose |
|------|---------|
| `claude_dashboard.html` | Main frontend - ALL UI code is here (large file ~15K+ lines) |
| `dashboard_server.py` | Backend - API endpoints, WebSocket, file handling |

### Important Functions in `claude_dashboard.html`

| Function | Line ~ | Purpose |
|----------|--------|---------|
| `renderCanvasSections()` | 13833 | Renders section list in sidebar |
| `selectCanvasSection()` | 13879 | Handles section selection, shows editor |
| `deleteCanvasSection()` | 13914 | Deletes a section |
| `saveCanvasSection()` | ~13950 | Saves section content |
| `addFileToCanvasDirectly()` | 15497 | Adds uploaded file content to canvas |
| `updateCanvasPreview()` | ~14000 | Updates markdown preview pane |

### Canvas HTML Structure (in `claude_dashboard.html`)

- `#canvas-sections-list` - Container for section cards
- `#canvas-editor-container` - Editor + preview split view
- `#canvas-editor-textarea` - The text editor
- `#canvas-preview-content` - Preview pane

---

## Current State (What Works)

- File upload extracts content during upload (bypasses Railway ephemeral storage)
- Sections display with title, type badge, owner, version
- Delete button (red ×) on each section
- Split editor/preview view
- Auto-save with debounce
- localStorage persistence for local documents
- WebSocket sync for multiplayer sessions

---

## Tasks to Implement (Priority Order)

### 1. Drag & Drop Section Reordering (HIGH PRIORITY)

**Goal:** Users can drag sections to reorder them

**Approach:**
- Add `draggable="true"` to section cards in `renderCanvasSections()`
- Add drag handle (grip icon) on left side of each section
- Implement `ondragstart`, `ondragover`, `ondrop` handlers
- Update `doc.section_order` array on drop
- Save to localStorage after reorder
- Broadcast reorder via WebSocket for multiplayer

**Reference implementation pattern:**
```javascript
// In renderCanvasSections(), add to each section div:
draggable="true"
ondragstart="handleDragStart(event, '${sectionName}')"
ondragover="handleDragOver(event)"
ondrop="handleDrop(event, '${sectionName}')"

// New functions needed:
function handleDragStart(e, sectionName) { ... }
function handleDragOver(e) { e.preventDefault(); }
function handleDrop(e, targetSection) { ... }
```

### 2. Keyboard Shortcuts (MEDIUM PRIORITY)

**Goal:** Power user shortcuts for common actions

| Shortcut | Action |
|----------|--------|
| Cmd/Ctrl + S | Save section |
| Cmd/Ctrl + Enter | Toggle preview mode |
| Escape | Deselect section |
| Cmd/Ctrl + N | New section |

**Approach:**
- Add `keydown` event listener to document
- Check for modifier keys + key combo
- Call appropriate functions

### 3. Section Collapse/Expand (LOW-MEDIUM)

**Goal:** Collapse sections to just show title (hide preview text)

**Approach:**
- Add collapse icon button next to delete button
- Track collapsed state in section object or separate Set
- In `renderCanvasSections()`, conditionally hide preview div
- Persist collapsed state in localStorage

### 4. Better Visual Feedback (LOW)

**Goal:** Polish hover states, transitions, selection indicators

**Improvements:**
- Hover effect on section cards (subtle lift/glow)
- Smooth transitions for selection state
- Drag preview styling
- Active drop zone indicator

### 5. Section Colors/Tags (FUTURE)

**Goal:** Visual grouping of related sections

---

## Code Patterns to Follow

### Adding new functions:
1. Define function in the main script block
2. Expose to window: `window.myFunction = myFunction;`
3. Use `window.canvasDocument` for document access (not local `canvasDocument`)

### Saving changes:
```javascript
window.canvasDocument = doc;
localStorage.setItem('local_canvas_document', JSON.stringify(doc));
renderCanvasSections();
```

### WebSocket broadcast (for multiplayer):
```javascript
if (workspaceWs && workspaceWs.readyState === WebSocket.OPEN) {
  workspaceWs.send(JSON.stringify({
    type: 'canvas_update',
    // ... data
  }));
}
```

---

## Testing

1. Go to https://golden-library-production.up.railway.app/
2. Click "Focus Mode" layout
3. Upload a file or create sections manually
4. Test the feature you implemented
5. Check browser console for errors

**Local testing:** The files can be served locally but WebSocket/API features need the Railway backend.

---

## Deployment

```bash
cd /Users/kanelawaccount/ztgi/golden_library
git add -A
git commit -m "Your commit message"
git push origin main
railway up  # Manual deploy if auto-deploy doesn't trigger
```

---

## Notes

- The HTML file is very large (~580KB). Use grep/search to find functions.
- Canvas state is stored in `window.canvasDocument` (global scope)
- `activeSectionName` tracks which section is selected
- Railway has ephemeral storage - don't rely on server filesystem for persistence

---

## Start Command

```
Be KODA. Implement drag & drop section reordering in the canvas UI.
Reference HANDOFF_CANVAS_UX.md for context.
Start with renderCanvasSections() at line ~13833 in claude_dashboard.html.
```
