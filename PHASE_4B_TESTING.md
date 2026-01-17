# Phase 4B Testing Guide: Agent-to-Agent Communication

**Status:** Implementation Complete
**Date:** January 16, 2026
**Test Environment:** Golden Library Collaborative Workspace

---

## Overview

Phase 4B adds advanced MCP-based agent coordination tools to the collaborative workspace, enabling:
- Agent-to-agent messaging via inbox system
- Workflow state management with milestones
- Context sharing between agents
- Blocker escalation and task reassignment
- Agent capability and workload discovery

---

## Prerequisites

### 1. Start the Servers

```bash
# Terminal 1: Dashboard server (HTTP + WebSocket)
cd ~/ztgi/golden_library
python3 dashboard_server.py

# Servers will start on:
# - HTTP: http://localhost:8080
# - WebSocket: ws://localhost:8081
```

### 2. Configure API Key

1. Open http://localhost:8080
2. Navigate to ⚙️ **Config** tab
3. Add your **Anthropic API Key**
4. Click **Save API Keys**
5. Verify success message

### 3. Create a Test Session

1. Navigate to 🚀 **Workspace** tab
2. Enter your name: "Test User"
3. Click **Create Session**
4. Copy the session URL (e.g., http://localhost:8080?session=abc123)

---

## Test Scenarios

### Scenario 1: Basic Agent Messaging

**Test:** Prax sends a message to Koda

**Steps:**
1. In **Moderator (Prax)** panel, send:
   ```
   Send message to koda: Please implement the user authentication endpoint
   ```

2. **Expected Results:**
   - ✓ MCP Tool Execution feedback appears below response
   - ✓ Inbox badge (📬) appears on Agent A (Koda) panel
   - ✓ Audit log shows: `📨 prax → koda`
   - ✓ Notification: Message sent

3. Click the 📬 badge on Agent A panel

4. **Expected Inbox View:**
   - Modal shows "Koda (Builder) Inbox"
   - 1 message from prax
   - Message marked as UNREAD
   - Message content displayed

---

### Scenario 2: Workflow Creation & Milestones

**Test:** Prax creates a workflow and tracks progress

**Steps:**
1. In **Moderator (Prax)** panel, send:
   ```
   Create workflow 'OAuth2 Implementation' with agents [cairn, koda]
   ```

2. **Expected Results:**
   - ✓ Workflow created notification
   - ✓ Audit log shows workflow creation
   - ✓ Session info shows workflow progress section

3. Set a milestone:
   ```
   Set milestone 'Design complete' to in_progress (50%)
   ```

4. **Expected Results:**
   - ✓ Workflow progress bar appears in session info
   - ✓ "Design complete" shows at 50% with blue bar
   - ✓ Status indicator shows "● in_progress"

5. Complete the milestone:
   ```
   Set milestone 'Design complete' to completed (100%)
   ```

6. **Expected Results:**
   - ✓ Progress bar turns green
   - ✓ Notification: "✓ Milestone complete: Design complete (100%)"
   - ✓ Status shows "● completed"

---

### Scenario 3: Context Sharing

**Test:** Cairn shares design specs with Koda

**Steps:**
1. In **Agent B (Cairn)** panel, send:
   ```
   Share context 'api_spec': The authentication API should use JWT tokens with 24-hour expiry with all
   ```

2. **Expected Results:**
   - ✓ MCP Tool Execution feedback confirms context shared
   - ✓ Notification: "📚 cairn shared context: api_spec"
   - ✓ Koda receives inbox message about shared context
   - ✓ Audit log shows: `📚 shared context: api_spec`

3. In **Agent A (Koda)** panel, retrieve context:
   ```
   Get shared context 'api_spec'
   ```

4. **Expected Results:**
   - ✓ MCP Tool Execution shows: "📚 Retrieved context 'api_spec': [content preview]"
   - ✓ Koda can access the shared specification

---

### Scenario 4: Blocker Escalation

**Test:** Koda encounters a blocker and escalates to humans

**Steps:**
1. In **Agent A (Koda)** panel, send:
   ```
   Escalate blocker: Database schema needs clarification for OAuth token storage
   ```

2. **Expected Results:**
   - ✓ Red/orange blocker banner appears at top of screen
   - ✓ Banner shows: "🚨 BLOCKER" or "🚨 CRITICAL BLOCKER"
   - ✓ Description: "Database schema needs clarification..."
   - ✓ Affected agents listed
   - ✓ Notification: "🚨 Blocker: [description]"
   - ✓ Audit log shows: `🚨 BLOCKER: Database schema...`

3. Click **Dismiss** on banner

4. **Expected Results:**
   - ✓ Banner fades out and disappears
   - ✓ (Auto-dismisses after 30 seconds for non-critical blockers)

---

### Scenario 5: Advanced Orchestration Workflow (Full OAuth2 Example)

**Test:** Complete multi-agent workflow with all Phase 4B features

**Setup Prompt for Prax:**
```
Let's build an OAuth2 authentication system.

First, check workload for cairn and koda.
Then create a workflow called 'oauth2_auth_system'.
Assign cairn to design the architecture and koda to implement.
Use shared contexts to pass specs between agents.
Track milestones at 50% (design complete) and 100% (implementation complete).
```

**Expected Workflow:**

1. **Prax checks workloads:**
   - MCP tool calls show agent status
   - Confirms agents are available

2. **Workflow creation:**
   - Workflow "oauth2_auth_system" created
   - Workflow progress section appears in UI

3. **Cairn receives design task:**
   - 📬 inbox badge appears on Agent B
   - Message from prax with workflow context
   - Message includes workflow_id in metadata

4. **Cairn designs and shares:**
   - Cairn creates architecture
   - Shares context "oauth2_spec" with koda
   - Sets milestone "Design complete" to 50%

5. **Koda receives implementation task:**
   - 📬 inbox badge appears on Agent A
   - Retrieves shared context "oauth2_spec"
   - Starts implementation

6. **Blocker scenario:**
   - Koda encounters DB schema question
   - Escalates blocker
   - Red banner appears
   - Prax coordinates with Cairn for resolution

7. **Blocker resolution:**
   - Cairn shares "oauth2_db_schema" context
   - Koda retrieves and continues

8. **Completion:**
   - Koda finishes implementation
   - Prax sets milestone "Implementation complete" to 100%
   - Green progress bar at 100%
   - Workflow complete notification

---

## UI Features to Verify

### Inbox Badges (📬)
- **Location:** Top-right corner of each agent panel
- **Trigger:** Appears when agent receives unread messages
- **Behavior:**
  - Yellow/gold background with 📬 emoji
  - Click to open inbox modal
  - Disappears when inbox viewed (messages stay unread until marked)

### Workflow Progress Bars
- **Location:** Session info panel (below user presence)
- **Display:**
  - Workflow name: "📊 Workflow Progress"
  - Per-milestone progress bars
  - Status indicator (● pending/in_progress/completed/blocked)
  - Percentage completion
- **Colors:**
  - Completed: Green (#10b981)
  - In Progress: Blue (#3b82f6)
  - Blocked: Red (#ef4444)
  - Pending: Gray (#94a3b8)

### Blocker Banners
- **Location:** Fixed at top of viewport (below nav)
- **Display:**
  - 🚨 icon
  - Severity indicator (CRITICAL BLOCKER vs BLOCKER)
  - Description text
  - Affected agents list
  - Dismiss button
- **Auto-dismiss:** 30 seconds for medium/low severity

### Audit Log Enhancements
- **New Event Types:**
  - 📨 Agent messages (blue for medium, orange for high priority)
  - 🚨 Blockers (red)
  - 📊 Milestones (green for completed, blue for in progress)
  - 📚 Context sharing (purple)
- **Workflow Badges:**
  - Purple badges show workflow_id for related events
  - Allows filtering events by workflow

---

## Backend Verification

### Check Session State

```python
# In Python shell or add to dashboard_server.py
from workspace_session_manager import session_manager

# Get session
session = session_manager.get_session('abc123')  # Your session ID

# Check agent inboxes
print("Prax inbox:", len(session.agent_inboxes['prax']))
print("Cairn inbox:", len(session.agent_inboxes['cairn']))
print("Koda inbox:", len(session.agent_inboxes['koda']))

# Check workflows
print("Workflows:", list(session.workflows.keys()))

# Check shared contexts
print("Shared contexts:", list(session.shared_contexts.keys()))

# Check agent workload
print("Agent workload:", session.agent_workload)
```

---

## Troubleshooting

### Issue: Inbox badge doesn't appear

**Causes:**
1. Message not sent (check MCP tool execution feedback)
2. WebSocket not connected (check browser console)
3. Badge element not found (check agent panel IDs)

**Debug:**
```javascript
// Browser console
console.log("Session ID:", currentSessionId);
console.log("WebSocket state:", workspaceWebSocket?.readyState);
```

### Issue: MCP tools not executing

**Causes:**
1. Session manager not passed to orchestrator
2. Agent response doesn't match tool patterns
3. Tool parsing regex not matching

**Check:**
- Look for "MCP Tool Execution:" section in agent response
- Verify session_id and session_manager in AgentOrchestrator

### Issue: Workflow progress not showing

**Causes:**
1. Workflow not created
2. Session info panel not visible
3. Milestone data malformed

**Debug:**
```javascript
// Browser console
fetchSession().then(s => console.log("Workflows:", s.workflows));
```

---

## Performance Notes

- **Token Usage:** Phase 4B adds ~500-800 tokens per agent system prompt (MCP tool documentation)
- **WebSocket Events:** Agent messages trigger 2-3 events (send confirmation, inbox update, audit log)
- **Inbox Storage:** Messages persist in session memory (cleared on session expiry)

---

## Success Criteria Checklist

- [ ] Agents can send messages to each other
- [ ] Inbox badges appear with unread counts
- [ ] Inbox modal displays messages correctly
- [ ] Workflows can be created with IDs and names
- [ ] Milestones update progress bars in real-time
- [ ] Context sharing works across agents
- [ ] Shared contexts retrievable by recipient agents
- [ ] Blockers escalate with prominent UI alerts
- [ ] Audit log shows all Phase 4B events with proper icons
- [ ] Workflow badges appear on related audit events
- [ ] Multiple workflows can run concurrently
- [ ] Agent workload tracking prevents overload
- [ ] WebSocket broadcasts reach all session users
- [ ] UI updates in real-time (<500ms latency)
- [ ] No console errors during operation

---

## Next Steps After Testing

1. **Documentation Update:** Add Phase 4B features to main README
2. **Video Demo:** Record screencast of OAuth2 workflow scenario
3. **Performance Tuning:** Optimize WebSocket event frequency
4. **Mobile Responsive:** Test UI on smaller screens
5. **Error Handling:** Add retry logic for failed tool calls

---

**Phase 4B Implementation:** ✅ COMPLETE
**Ready for Production Testing:** ✅ YES
