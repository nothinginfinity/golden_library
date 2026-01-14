# Claude Control Center Dashboard

**Simple, single-file HTML dashboard to visualize your compressed Claude data.**

---

## 🚀 Quick Start (30 seconds)

```bash
cd ~/ztgi/golden_library

# Start the dashboard
./start_dashboard.sh
```

That's it! The dashboard will open in your browser at `http://localhost:8080`

---

## 📊 What You See

### Dashboard Overview
- **Conversations Compressed** - Total count of compressed conversations
- **Token Savings** - How many tokens saved vs uncompressed
- **Disk Space Saved** - Actual disk space freed up
- **Last Compressed** - Most recently compressed item

### Search
- Search across all compressed conversations
- Filter by category (conversations, history, todos, debug, logs)
- See token costs for each search
- Click results to view details

### Charts
- **Storage by Category** - Visual breakdown of what's using space
- **Recent Activity** - Timeline of recent compressions

---

## 🎛️ How It Works

```
Browser (http://localhost:8080)
    ↓
dashboard_server.py (Python HTTP server)
    ↓
Reads: ~/.claude/conversation_library/index.json
    ↓
Serves: JSON API endpoints
```

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Dashboard HTML |
| `GET /api/stats` | Compression statistics |
| `GET /api/search?q=...` | Search conversations |
| `GET /api/daemon-status` | Check if daemon is running |
| `GET /api/conversation?id=...` | Get conversation details |

---

## 📁 Files

```
~/ztgi/golden_library/
├── claude_dashboard.html      # Single-file dashboard (D3.js)
├── dashboard_server.py        # Python API server
├── start_dashboard.sh         # Start script
├── stop_dashboard.sh          # Stop script
└── DASHBOARD_README.md        # This file
```

---

## 🛠️ Commands

```bash
# Start dashboard
./start_dashboard.sh

# Stop dashboard
./stop_dashboard.sh

# Start on custom port
python3 dashboard_server.py 9000

# Check if running
curl http://localhost:8080/api/stats
```

---

## 🔧 Configuration

The dashboard reads data from:
- `~/.claude/conversation_library/index.json` - Main index
- `~/.claude/conversation_library/compressed/` - Compressed files
- `~/.claude/auto_compress_daemon.pid` - Daemon status

If `index.json` doesn't exist, the dashboard will:
1. Scan compressed directory for files
2. Generate stats from file sizes
3. Show a note that index is missing

---

## 💡 Features

### Current
- ✅ Real-time stats (refreshes every 30s)
- ✅ Search across all compressed data
- ✅ Category filtering
- ✅ Daemon status indicator
- ✅ Storage breakdown chart
- ✅ Recent activity feed

### Coming Soon (in full implementation)
- Config editor (CLAUDE.md, hooks, settings)
- Hook manager with test functionality
- Conversation replay
- Pattern detection
- QA.Stone export from UI
- Integration with phi_proxy/inbox

---

## 🎨 Tech Stack

- **Frontend:** Vanilla HTML/CSS/JavaScript + D3.js v7
- **Backend:** Python 3 (standard library only - no dependencies!)
- **Data:** JSON files (no database needed)
- **Server:** Python http.server (SimpleHTTPRequestHandler)

**Why no dependencies?**
- Works out of the box with Python 3
- No pip install needed
- Fast startup
- Easy to debug

---

## 🐛 Troubleshooting

### Dashboard won't load
```bash
# Check if server is running
curl http://localhost:8080/api/stats

# Check if port is in use
lsof -i :8080

# Start on different port
python3 dashboard_server.py 9000
```

### No data showing
```bash
# Check if compression library exists
ls ~/.claude/conversation_library/

# Check if daemon is running
~/ztgi/golden_library/daemons/status_daemon.sh

# Start daemon if needed
~/ztgi/golden_library/daemons/start_daemon.sh
```

### Daemon shows "Stopped"
```bash
# Start the auto-compress daemon
cd ~/ztgi/golden_library/daemons
./start_daemon.sh
```

---

## 📊 Sample Output

When you open the dashboard, you'll see something like:

```
╔════════════════════════════════════════════╗
║   Claude Control Center                   ║
╠════════════════════════════════════════════╣
║ Conversations: 47                         ║
║ Token Savings: 5.2M (65% reduction)       ║
║ Disk Saved: 1.8 GB                        ║
║ Last: 2m ago - session_auth_bugfix        ║
╠════════════════════════════════════════════╣
║ [Search box]                              ║
║ [Filters: All | Conversations | ...]      ║
╠════════════════════════════════════════════╣
║ [Bar chart: Storage by category]          ║
╠════════════════════════════════════════════╣
║ Recent Activity:                          ║
║ • 2m ago: Compressed session_auth         ║
║ • 5m ago: Compressed todo_list            ║
║ • 10m ago: Compressed debug_output        ║
╚════════════════════════════════════════════╝
```

---

## 🔗 Integration

This dashboard is a **preview** of the full Claude Control Center planned in the architecture doc.

**Current (this dashboard):**
- Simple, single-file HTML
- Works with existing compressed data
- Read-only view

**Future (full system):**
- FastAPI + Svelte
- Config editing (CLAUDE.md, hooks)
- Hook management
- Real-time updates via SSE
- QA.Stone export
- Integration with phi_proxy/inbox/ZTI

---

## 💰 Cost Savings Example

**Your 50-terminal setup:**
- 50 conversations × 200K tokens = 10M tokens
- Compressed: 5M tokens (50% reduction)
- Search cost: 150K tokens (vs 10M uncompressed)
- **Savings: 99% per search**

**Annual savings:** $5-10K with frequent searches

---

## 🚀 Next Steps

1. **Test this dashboard** - Start it and explore your compressed data
2. **Run the daemon** - Ensure auto-compression is working
3. **Search your data** - Try finding conversations by keyword
4. **Review the plan** - See `~/.claude/plans/tidy-purring-minsky.md` for full architecture

---

## 📝 Notes

- Dashboard refreshes stats every 30 seconds automatically
- Search is instant (filters in-memory index)
- Works with any browser (Chrome, Firefox, Safari)
- No internet connection needed (runs locally)
- Safe to run alongside other services (different port)

---

**Built by:** Cairn (Claude Code Architect)
**Date:** 2026-01-13
**Part of:** Golden Library Compression System
