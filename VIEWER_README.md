# 🏆 Golden Library 3D Viewer

Beautiful 3D visualization of your compressed conversation handoffs.

---

## 🎨 Features

- **3D Node Visualization**: Each handoff appears as a glowing cube in 3D space
- **Color-Coded Formats**:
  - 🔵 Blue: SLIM only
  - 🟡 Gold: SLIM + V4Z
  - 🟣 Purple: SLIM + FSL
  - 🟢 Green: SLIM + ZTPCF
- **Multiple Layouts**:
  - Globe (sphere)
  - Clusters
  - Cubic Grid
  - Helix
  - Scatter
- **Interactive Controls**:
  - Auto-orbit mode
  - Click nodes to view details
  - Search across handoffs
  - Real-time compression stats
- **Detailed Panels**:
  - Compression ratio
  - File sizes (original → compressed)
  - Metadata and timestamps
  - Quick actions (decompress, download, stats)

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd golden_library
pip install flask flask-cors
```

### 2. Start the Backend

```bash
python3 viewer_backend.py
```

The server will start at `http://127.0.0.1:8080`

### 3. Open in Browser

```bash
open http://127.0.0.1:8080
```

Or visit: **http://localhost:8080**

---

## 📸 Screenshots

Your screenshots show the Terminal Library version. Golden Library follows the same design with:
- Gold/amber color scheme (instead of blue)
- Compression stats (instead of token usage)
- Handoff nodes (instead of terminal files)

---

## 🎮 Controls

### Mouse/Trackpad
- **Left Click + Drag**: Rotate view
- **Right Click + Drag**: Pan view
- **Scroll**: Zoom in/out
- **Click Node**: Show details

### Keyboard
- **Space**: Toggle auto-orbit
- **R**: Reload data
- **Esc**: Close side panel

---

## 🗂️ View Modes

### Globe (Sphere)
Handoffs arranged in a spherical pattern - great for overview

### Clusters
Groups handoffs by format - easy to compare compression types

### Cubic Grid
Organized grid layout - systematic browsing

### Helix
Spiral arrangement - shows chronological order

### Scatter
Random positions - explore connections

---

## 🔍 Search

The hybrid search supports:
- **Local**: Search handoff filenames and IDs
- **Metadata**: Search by format, dates, compression stats

Example searches:
- `session` - Find all session handoffs
- `v4z` - Find V4Z compressed handoffs
- `80%` - Find high compression ratio handoffs

---

## 📊 Compression Stats Panel

Real-time statistics:
- **Total Handoffs**: Count of compressed conversations
- **Original Size**: Sum of all original JSONL files
- **Compressed Size**: Sum of all compressed files
- **Total Savings**: Average compression percentage

---

## 🎯 Node Details Panel

Click any node to see:
- **Handoff ID** and original filename
- **Compression Format** (SLIM, V4Z, FSL, ZTPCF)
- **Reduction Percentage** with quality badge
- **File Sizes** (original, compressed, saved)
- **Creation Date**
- **Quick Actions**:
  - Decompress to JSONL
  - View detailed stats
  - Download metadata

---

## 🛠️ API Endpoints

The backend exposes:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve 3D viewer HTML |
| `/api/handoffs` | GET | List all handoffs |
| `/api/handoff/<id>` | GET | Get handoff details |
| `/api/handoff/<id>/decompress` | POST | Decompress handoff |
| `/api/stats` | GET | Overall statistics |

---

## 🎨 Customization

### Change Colors

Edit `viewer.html`, find the color definitions:

```javascript
const colors = {
    slim_only: 0x4facfe,    // Blue
    slim_v4z: 0xf7b731,     // Gold
    slim_fsl: 0xaa66cc,     // Purple
    slim_ztpcf: 0x00C851    // Green
};
```

### Change Layout

Default layout is `sphere`. To change:

```javascript
// In init() function, after createGraph()
changeLayout('grid');  // or 'helix', 'clusters', 'scatter'
```

### Adjust View Distance

```javascript
camera.position.set(0, 30, 80);  // Increase Z for farther view
controls.minDistance = 20;
controls.maxDistance = 200;
```

---

## 🐛 Troubleshooting

### No handoffs showing?

1. Check if handoffs exist:
   ```bash
   python3 src/handoff_slim.py list
   ```

2. Create demo handoffs:
   ```bash
   python3 src/handoff_slim.py compress /path/to/session.jsonl
   ```

### Backend not starting?

1. Install dependencies:
   ```bash
   pip install flask flask-cors
   ```

2. Check port availability:
   ```bash
   lsof -i :8080
   ```

### Viewer shows "Failed to load handoffs"?

The viewer will automatically switch to demo mode and show 20 sample handoffs for testing the interface.

---

## 🔗 Integration

### Embed in Another App

```html
<iframe src="http://localhost:8080" width="100%" height="800px"></iframe>
```

### Use with Phi Server

Add to `phi_proxy/server.py`:

```python
@app.route('/viewer')
def golden_viewer():
    return redirect('http://localhost:8080')
```

### Integrate with QA.Stone App

The viewer can be embedded in the qastone-mcp-twin app as a new page.

---

## 📝 TODO

- [ ] Add filters (by format, date range, size)
- [ ] Export visualization as image/video
- [ ] Timeline mode (show handoffs chronologically)
- [ ] Comparison mode (compare 2 handoffs side-by-side)
- [ ] WebSocket live updates
- [ ] VR mode support

---

## 🙏 Credits

Based on the Terminal Library 3D visualization design.

Built with:
- Three.js - 3D graphics
- Flask - Backend API
- Modern CSS - UI styling

---

**🏆 Visualize your compression. Make your handoffs golden.**
