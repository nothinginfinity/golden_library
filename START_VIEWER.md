# 🚀 Quick Start Guide - Golden Library 3D Viewer

## Step 1: Install Dependencies

```bash
cd ~/ztgi/golden_library
pip install flask flask-cors
```

## Step 2: Create Some Test Handoffs (Optional)

If you don't have handoffs yet, create some:

```bash
# Find a conversation JSONL
ls ~/.claude/projects/-Users-*/

# Create a handoff
python3 src/handoff_slim.py compress ~/.claude/projects/.../session.jsonl --level slim_v4z

# List to verify
python3 src/handoff_slim.py list
```

## Step 3: Start the Viewer

```bash
python3 viewer_backend.py
```

You should see:
```
🏆 Golden Library 3D Viewer
============================

Backend running at: http://127.0.0.1:8080
Open in browser:    http://127.0.0.1:8080

Press Ctrl+C to stop
```

## Step 4: Open in Browser

```bash
open http://localhost:8080
```

Or visit: **http://127.0.0.1:8080**

---

## 🎮 What You'll See

### Main Interface (Left Panel)
- **Search**: Find handoffs by name or format
- **Compression Stats**: Real-time statistics
- **View Modes**: Globe, Clusters, Grid, Helix, Scatter
- **Controls**: Auto-orbit, connections, reload

### 3D Visualization (Center)
- **Colored Cubes**: Each handoff is a rotating cube
  - 🔵 Blue = SLIM only (50% compression)
  - 🟡 Gold = SLIM + V4Z (80% compression)
  - 🟣 Purple = SLIM + FSL (85% compression)
  - 🟢 Green = SLIM + ZTPCF (86% compression)
- **Stars**: Background for depth
- **Smooth Orbiting**: Auto-rotate or manual control

### Details Panel (Right - Click a Node)
- Handoff ID and filename
- Compression format and ratio
- Original size → Compressed size
- Savings amount
- Quick actions (decompress, view stats, download)

---

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"

```bash
pip install flask flask-cors
```

### "No handoffs showing in 3D view"

The viewer will show **demo data** automatically if no real handoffs exist. You'll see 20 sample nodes in different colors.

To create real handoffs:
```bash
python3 src/handoff_slim.py compress /path/to/session.jsonl
```

### Port 8080 already in use

Start on a different port:
```bash
python3 viewer_backend.py --port 8081
```

---

## 📸 Expected Result

You should see a dark 3D space with:
- Glowing colored cubes (handoffs) arranged in a sphere
- Sparkling stars in the background
- Left sidebar with golden "GOLDEN LIBRARY 3D" header
- Compression statistics showing your data

**Click any cube** to see its details in the right panel!

---

## ⚡ Quick Actions

| Action | Command |
|--------|---------|
| Toggle auto-orbit | Click "Auto-Orbit: OFF" button |
| Change layout | Click Globe/Clusters/Grid/Helix/Scatter |
| Search handoffs | Type in search box, click Search |
| View details | Click any cube in 3D space |
| Reload data | Click "Reload Data" button |

---

**🏆 Enjoy visualizing your compressed conversations!**
