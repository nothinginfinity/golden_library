# Handoff: Collaborative Multi-Agent Workspace

## Working Directory
```
cd /Users/kanelawaccount/ztgi/golden_library
```

## Current State (Commit: cd5ac62)

**Phase 3 Complete** - Fully functional multiplayer workspace:
- ✅ Real-time presence indicators (avatars, online count, typing)
- ✅ Live cursor sharing with colored labels
- ✅ Agent control system (claim/release agents)
- ✅ Resizable agent panels (drag handle between A/B)
- ✅ Human-to-human chat sidebar (WebSocket-based)
- ✅ All 3 agents working (Koda, Cairn, Prax)
- ✅ WebSocket broadcasting for all events

**Server:** `python3 dashboard_server.py` (HTTP: 8080, WebSocket: 8081)

## Architecture

**Key Files:**
- `PRD_COLLABORATIVE_WORKSPACE.md` - Full product roadmap
- `dashboard_server.py` - HTTP + WebSocket server
- `claude_dashboard.html` - Frontend UI (line ~2440 for workspace tab)
- `src/workspace_session_manager.py` - Session/user management
- `src/agent_orchestrator.py` - Multi-agent Claude integration

**Stack:** Python HTTP server + WebSocket (websockets lib) + Anthropic API + vanilla JS frontend

## Next: Phase 4 (PRD lines 843-868)

**Priority Tasks:**
1. **@Mentions** - Parse @username in chat, send notifications
2. **Permissions** - Owner/Editor/Viewer roles, enforce on agent control
3. **Document locking** - Prevent simultaneous edits, show "X is editing"
4. **Audit log** - Track who did what (agent messages, control changes)
5. **Session settings** - Timeout config, max users, permissions UI

**Not Needed Yet:** Advanced OT/CRDT sync (defer to Phase 5)

## Testing
```bash
# Open http://localhost:8080 → Workspace tab
# Click "+ Create Session" → Copy invite link
# Open incognito window → Paste invite → Join
# Test: resize panels, send messages, claim agent control
```

## API Key Required
Configure via Dashboard → Config tab or `~/.claude/api_keys.json` with `{"claude": "sk-ant-..."}`

## Notes
- All presence features broadcast via WebSocket to all session users
- Agent control is first-come-first-served with visual indicators
- Human chat appears automatically when in a session
- Resize handle constrains between 20%-80% to prevent breaking layout

Continue from Phase 4 in the PRD!
