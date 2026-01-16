# Testing Guide: Collaborative Workspace Phase 2

**Last Updated:** January 15, 2026
**Phase:** 2 - WebSocket Infrastructure + Agent Broadcasting
**Status:** Ready for Testing (requires API key)

---

## Prerequisites

### 1. API Key Configuration

The collaborative workspace requires an Anthropic API key to power the AI agents.

**Option A: Via Dashboard (Recommended)**
```bash
# 1. Start the server
cd ~/ztgi/golden_library
python3 dashboard_server.py

# 2. Open browser to http://localhost:8080
# 3. Click "Config" tab
# 4. Add your Anthropic API key
# 5. Save configuration
```

**Option B: Environment Variable**
```bash
export ANTHROPIC_API_KEY='your-key-here'
cd ~/ztgi/golden_library
python3 dashboard_server.py
```

**Option C: API Keys File**
```bash
mkdir -p ~/.claude
cat > ~/.claude/api_keys.json << EOF
{
  "claude": "your-key-here"
}
EOF
```

### 2. Verify Server is Running

```bash
# Check if server processes are running
ps aux | grep dashboard_server.py

# Verify ports are listening
lsof -ti:8080  # HTTP server
lsof -ti:8081  # WebSocket server

# Should see both ports in use
```

---

## Test Scenarios

### Test 1: Single User Session

**Goal:** Verify basic agent interaction works

1. Open browser to `http://localhost:8080`
2. Click **Workspace** tab
3. You should see:
   - Session ID (e.g., `abc123`)
   - "Copy Invite Link" button
   - Three agent panels (Agent A, Agent B, Moderator)
4. Type a message to Agent A: "Hello, who are you?"
5. Click Send
6. **Expected Result:**
   - Agent A responds with streaming text
   - Response appears in real-time
   - Full response is stored in chat history

**Success:** ✅ Agent responds and streaming works

---

### Test 2: Multiplayer Session (2 Users)

**Goal:** Verify real-time broadcasting across users

**Setup:**
1. Open **Browser Window 1** (User A)
   - Go to `http://localhost:8080`
   - Click Workspace tab
   - Copy the session invite link (button appears after joining)

2. Open **Browser Window 2** (User B) - **Different browser or incognito**
   - Paste the invite link
   - You should join the same session

**Expected Initial State:**
- Both windows show the same session ID
- User A sees "User B joined" notification
- User B sees existing chat history from User A

**Test Steps:**

**Step A: User A sends message to Agent A**
1. In Window 1, User A types: "Analyze the weather patterns"
2. Click Send
3. **Expected in Window 1:** Agent A responds with streaming text
4. **Expected in Window 2:** User B sees the SAME streaming response in real-time

**Step B: User B sends message to Agent B**
1. In Window 2, User B types: "What's the temperature?"
2. Click Send
3. **Expected in Window 2:** Agent B responds with streaming text
4. **Expected in Window 1:** User A sees the SAME streaming response in real-time

**Success Criteria:**
- ✅ Both users see each other join the session
- ✅ Messages from User A appear in User B's window
- ✅ Agent responses stream to BOTH users simultaneously
- ✅ Chat history is synchronized across both windows

---

### Test 3: Presence Indicators

**Goal:** Verify user presence tracking

1. With 2 browser windows in same session
2. In Window 1, start typing in the message box
3. **Expected in Window 2:** See "User A is typing..." indicator
4. Close Window 1
5. **Expected in Window 2:** See "User A left the session" notification

**Success:** ✅ Presence indicators work correctly

---

### Test 4: Session Persistence

**Goal:** Verify session state is maintained

1. User A creates session, sends messages to Agent A
2. Copy invite link
3. Close User A's browser
4. User B opens invite link
5. **Expected:** Session still exists with full chat history
6. User B can continue conversation
7. **Expected:** Agent responses work normally

**Success:** ✅ Session persists across user disconnects

---

## WebSocket Event Flow

For debugging, here's the complete event flow:

```
1. User A: join_workspace_session
   ↓
   Server: Creates WorkspaceSession with AgentOrchestrator
   ↓
   User A: Receives session_joined event

2. User B: join_workspace_session (same session_id)
   ↓
   Server: Adds User B to existing session
   ↓
   User A: Receives user_joined event (User B joined)
   User B: Receives session_joined event

3. User A: workspace_message (to Agent A)
   ↓
   Server: Stores user message
   ↓
   All Users: Receive user_message event
   ↓
   Server: Calls orchestrator.send_message()
   ↓
   All Users: Receive agent_thinking event
   ↓
   Server: Streams chunks from agent
   ↓
   All Users: Receive agent_response_chunk events (real-time)
   ↓
   Server: Stores complete response
   ↓
   All Users: Receive agent_response_complete event
```

---

## Troubleshooting

### Issue: "No orchestrator available for session"

**Cause:** API key not configured or invalid

**Fix:**
```bash
# Check if API key is set
cat ~/.claude/api_keys.json

# Or check environment variable
echo $ANTHROPIC_API_KEY

# Restart server after adding key
```

### Issue: Agent doesn't respond

**Cause:** Orchestrator initialization failed

**Debug:**
```bash
# Check server logs
tail -f /tmp/dashboard_server.log

# Look for:
# "[SessionManager] Initialized AgentOrchestrator for session XXX"
# If missing, API key issue
```

### Issue: Messages don't sync between windows

**Cause:** WebSocket connection issue

**Debug:**
```bash
# In browser console (F12):
console.log(ws.readyState)  # Should be 1 (OPEN)

# Check WebSocket server
lsof -ti:8081  # Should return process ID
```

### Issue: Session not found when joining

**Cause:** Session expired (24 hour TTL)

**Fix:**
- Create a new session
- Or increase session duration in `workspace_session_manager.py`:
  ```python
  def __init__(self, session_duration_hours: int = 24):  # Change to 48, etc.
  ```

---

## Architecture Verification

### Files Modified in Phase 2

1. **src/workspace_session_manager.py**
   - Line 85: Added `orchestrator: Any = None`
   - Line 145-151: Initialize orchestrator on session creation
   - Line 22-26: Import AgentOrchestrator

2. **dashboard_server.py**
   - Line 4368-4429: Replaced TODO with full agent broadcast implementation
   - Streams chunks → broadcasts to all users
   - Syncs agent context after response

### Data Flow

```
User Message
    ↓
Session Storage (workspace_session_manager)
    ↓
AgentOrchestrator (per-session instance)
    ↓
Claude API (streaming response)
    ↓
WebSocket Broadcast (all session users)
    ↓
Agent Context Sync (session.agent_contexts)
```

---

## Next Steps (Phase 3)

After Phase 2 testing is complete:

- [ ] Document sync (Operational Transform)
- [ ] Live cursor sharing
- [ ] Presence avatars
- [ ] Agent → Agent communication
- [ ] Moderator coordination UI
- [ ] Polish animations and transitions

---

## Quick Test Commands

```bash
# Start server
cd ~/ztgi/golden_library
python3 dashboard_server.py

# Check if running
curl http://localhost:8080/api/workspace/sessions/stats

# Test WebSocket (in browser console)
const ws = new WebSocket('ws://localhost:8081');
ws.onopen = () => console.log('Connected');
ws.send(JSON.stringify({type: 'ping'}));
```

---

**Phase 2 Implementation Complete ✅**
**Ready for multiplayer testing with API key configured**
