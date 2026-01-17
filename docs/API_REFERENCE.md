# WebSocket API Reference

## Connection

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
```

## Message Format

All messages use JSON with this structure:

**Request:**
```json
{
  "type": "message_type",
  "request_id": "optional_tracking_id",
  ...fields
}
```

**Response:**
```json
{
  "type": "response_type",
  "success": true,
  "request_id": "echoed_if_provided",
  ...data
}
```

**Error Response:**
```json
{
  "type": "error",
  "error": true,
  "code": "E001_SESSION_NOT_FOUND",
  "message": "Session not found",
  "category": "SESSION",
  "retryable": false,
  "request_id": "abc123"
}
```

---

## Session Management

### create_session

Create a new collaborative session.

**Request:**
```json
{
  "type": "create_session",
  "user_id": "user123",
  "display_name": "Alice",
  "workspace_id": "optional_workspace"
}
```

**Response:**
```json
{
  "type": "session_created",
  "session_id": "abc123",
  "created_at": "2025-01-17T10:00:00Z",
  "owner_id": "user123"
}
```

### join_session

Join an existing session.

**Request:**
```json
{
  "type": "join_session",
  "session_id": "abc123",
  "user_id": "user456",
  "display_name": "Bob"
}
```

**Response:**
```json
{
  "type": "session_joined",
  "session_id": "abc123",
  "participants": {
    "user123": {"display_name": "Alice", "role": "owner"},
    "user456": {"display_name": "Bob", "role": "editor"}
  },
  "message_count": 42
}
```

### leave_session

Leave a session.

**Request:**
```json
{
  "type": "leave_session",
  "session_id": "abc123",
  "user_id": "user456"
}
```

**Response:**
```json
{
  "type": "session_left",
  "session_id": "abc123"
}
```

---

## Messages

### send_message

Send a message to the session.

**Request:**
```json
{
  "type": "send_message",
  "session_id": "abc123",
  "user_id": "user123",
  "content": "Let's analyze the HIPAA requirements",
  "mentions": ["@cairn"]
}
```

**Response:**
```json
{
  "type": "message_sent",
  "message_id": "msg_xyz",
  "timestamp": "2025-01-17T10:05:00Z"
}
```

**Broadcast to all participants:**
```json
{
  "type": "new_message",
  "message": {
    "id": "msg_xyz",
    "session_id": "abc123",
    "user_id": "user123",
    "role": "user",
    "content": "Let's analyze the HIPAA requirements",
    "mentions": ["@cairn"],
    "timestamp": "2025-01-17T10:05:00Z"
  }
}
```

### agent_message

Agent response (broadcast only).

```json
{
  "type": "agent_message",
  "message": {
    "id": "msg_abc",
    "session_id": "abc123",
    "agent_id": "cairn",
    "role": "assistant",
    "content": "I'll research the HIPAA compliance requirements...",
    "timestamp": "2025-01-17T10:05:30Z"
  }
}
```

---

## Task Delegation

### delegate_task

Delegate a task from Prax to another agent.

**Request:**
```json
{
  "type": "delegate_task",
  "session_id": "abc123",
  "from_agent": "prax",
  "to_agent": "cairn",
  "task": {
    "description": "Research HIPAA compliance requirements",
    "success_criteria": "Comprehensive list with sources",
    "tools_allowed": ["web_search", "deepseek"],
    "canvas_section": "compliance_research",
    "priority": "high"
  }
}
```

**Response:**
```json
{
  "type": "task_delegated",
  "task_id": "task_def456",
  "from_agent": "prax",
  "to_agent": "cairn",
  "status": "pending"
}
```

**Broadcast:**
```json
{
  "type": "task_delegation",
  "task_id": "task_def456",
  "from_agent": "prax",
  "to_agent": "cairn",
  "description": "Research HIPAA compliance requirements"
}
```

### update_task_status

Update task progress.

**Request:**
```json
{
  "type": "update_task_status",
  "session_id": "abc123",
  "task_id": "task_def456",
  "status": "in_progress",
  "progress_note": "Found 12 relevant regulations"
}
```

### complete_task

Mark task as completed.

**Request:**
```json
{
  "type": "complete_task",
  "session_id": "abc123",
  "task_id": "task_def456",
  "result": "Completed HIPAA research with 47 requirements identified",
  "canvas_content": "## HIPAA Requirements\n..."
}
```

---

## Canvas Operations

### create_canvas

Create a new canvas document.

**Request:**
```json
{
  "type": "create_canvas",
  "session_id": "abc123",
  "title": "Project Analysis",
  "initial_sections": [
    {"name": "research", "type": "markdown"},
    {"name": "implementation", "type": "code", "owner": "koda"}
  ]
}
```

**Response:**
```json
{
  "type": "canvas_created",
  "document_id": "canvas_xyz",
  "title": "Project Analysis",
  "sections": ["research", "implementation"]
}
```

### edit_canvas

Edit a canvas section.

**Request:**
```json
{
  "type": "edit_canvas",
  "session_id": "abc123",
  "document_id": "canvas_xyz",
  "section_name": "research",
  "author_id": "cairn",
  "author_name": "Cairn",
  "content": "## HIPAA Requirements\n\n1. Privacy Rule...",
  "operation": "replace"
}
```

**Broadcast:**
```json
{
  "type": "canvas_edit",
  "document_id": "canvas_xyz",
  "section_name": "research",
  "edit": {
    "id": "edit_123",
    "author_id": "cairn",
    "content": "## HIPAA Requirements\n...",
    "operation": "replace",
    "timestamp": "2025-01-17T10:10:00Z"
  },
  "new_content": "## HIPAA Requirements\n...",
  "version": 5
}
```

### lock_section

Lock a canvas section for exclusive editing.

**Request:**
```json
{
  "type": "lock_section",
  "session_id": "abc123",
  "document_id": "canvas_xyz",
  "section_name": "research",
  "user_id": "cairn",
  "duration_seconds": 300
}
```

**Response:**
```json
{
  "type": "section_locked",
  "section_name": "research",
  "locked_by": "cairn",
  "expires_at": "2025-01-17T10:15:00Z"
}
```

### unlock_section

Release a section lock.

**Request:**
```json
{
  "type": "unlock_section",
  "document_id": "canvas_xyz",
  "section_name": "research",
  "user_id": "cairn"
}
```

---

## Demo Mode

### start_demo

Start recording a demo session.

**Request:**
```json
{
  "type": "start_demo",
  "session_id": "abc123",
  "title": "HIPAA Compliance Demo",
  "description": "Demonstrating multi-agent collaboration",
  "branding": {
    "company_name": "Acme Corp",
    "logo_url": "https://example.com/logo.png"
  }
}
```

**Response:**
```json
{
  "type": "demo_started",
  "recording_id": "rec_abc",
  "title": "HIPAA Compliance Demo",
  "started_at": "2025-01-17T10:00:00Z"
}
```

### stop_demo

Stop recording.

**Request:**
```json
{
  "type": "stop_demo",
  "session_id": "abc123"
}
```

**Response:**
```json
{
  "type": "demo_stopped",
  "recording_id": "rec_abc",
  "duration_ms": 600000,
  "event_count": 47,
  "highlight_count": 3
}
```

### add_highlight

Mark a moment in the recording.

**Request:**
```json
{
  "type": "add_highlight",
  "session_id": "abc123",
  "label": "Key Decision",
  "description": "Team decided to use PostgreSQL"
}
```

### export_demo

Export recording to various formats.

**Request:**
```json
{
  "type": "export_demo",
  "recording_id": "rec_abc",
  "format": "html"
}
```

**Response:**
```json
{
  "type": "demo_exported",
  "recording_id": "rec_abc",
  "format": "html",
  "url": "/exports/rec_abc.html",
  "size_bytes": 245000
}
```

---

## Tool Execution

### execute_tool

Execute a tool on behalf of an agent.

**Request:**
```json
{
  "type": "execute_tool",
  "session_id": "abc123",
  "tool_name": "web_search",
  "requesting_agent": "cairn",
  "params": {
    "query": "HIPAA compliance requirements 2025"
  }
}
```

**Response:**
```json
{
  "type": "tool_result",
  "tool_name": "web_search",
  "success": true,
  "result": {
    "results": [
      {"title": "HIPAA Overview", "url": "...", "snippet": "..."}
    ]
  },
  "duration_ms": 1250
}
```

**Error Response:**
```json
{
  "type": "tool_error",
  "tool_name": "web_search",
  "error": true,
  "code": "E041_TOOL_PERMISSION_DENIED",
  "message": "Agent 'koda' cannot use 'restricted_tool'"
}
```

---

## Search & Context

### search_history

Search conversation history.

**Request:**
```json
{
  "type": "search_history",
  "query": "database decision",
  "session_id": "abc123",
  "agent_id": "cairn",
  "limit": 10
}
```

**Response:**
```json
{
  "type": "search_results",
  "query": "database decision",
  "results": [
    {
      "id": "msg_xyz",
      "content": "I've decided we should use PostgreSQL...",
      "agent_id": "cairn",
      "timestamp": "2025-01-17T09:30:00Z",
      "relevance": 0.95
    }
  ],
  "total_count": 3
}
```

### get_context

Get context for agent recovery.

**Request:**
```json
{
  "type": "get_context",
  "session_id": "abc123",
  "agent_id": "prax"
}
```

**Response:**
```json
{
  "type": "context",
  "session_id": "abc123",
  "messages": [...],
  "summary": {
    "message_count": 47,
    "key_topics": ["HIPAA", "compliance", "database"],
    "decisions": ["Use PostgreSQL", "Implement audit logging"]
  },
  "recovery_instructions": [
    "Continue coordinating the HIPAA compliance analysis",
    "Cairn is researching privacy requirements",
    "Koda is implementing the database schema"
  ]
}
```

---

## Events (Server → Client)

### user_joined

```json
{
  "type": "user_joined",
  "session_id": "abc123",
  "user_id": "user456",
  "display_name": "Bob",
  "timestamp": "2025-01-17T10:00:00Z"
}
```

### user_left

```json
{
  "type": "user_left",
  "session_id": "abc123",
  "user_id": "user456",
  "timestamp": "2025-01-17T11:00:00Z"
}
```

### presence_update

```json
{
  "type": "presence_update",
  "session_id": "abc123",
  "user_id": "user123",
  "status": "away",
  "last_active": "2025-01-17T10:55:00Z"
}
```

### typing_indicator

```json
{
  "type": "typing",
  "session_id": "abc123",
  "user_id": "user123",
  "is_typing": true
}
```

---

## Error Codes

| Code | Description | Retryable |
|------|-------------|-----------|
| E001_SESSION_NOT_FOUND | Session does not exist | No |
| E002_SESSION_EXPIRED | Session has expired | No |
| E003_SESSION_FULL | Maximum participants reached | No |
| E020_DB_NOT_INITIALIZED | Database not ready | Yes |
| E021_DB_CONNECTION_FAILED | Database connection error | Yes |
| E040_TOOL_NOT_FOUND | Unknown tool name | No |
| E041_TOOL_PERMISSION_DENIED | Agent cannot use tool | No |
| E042_TOOL_RATE_LIMITED | Rate limit exceeded | Yes |
| E060_DELEGATION_FAILED | Task delegation error | No |
| E062_CIRCULAR_DELEGATION | Circular dependency detected | No |
| E081_SECTION_LOCKED | Canvas section locked | Yes |
| E120_DEMO_NOT_AVAILABLE | Demo recorder unavailable | No |
| E121_DEMO_ALREADY_ACTIVE | Demo already recording | No |

---

## Rate Limits

| Resource | Limit |
|----------|-------|
| Messages per minute | 60 |
| Tool calls per minute | 30 |
| Canvas edits per minute | 120 |
| Search queries per minute | 20 |

When rate limited, response includes:
```json
{
  "error": true,
  "code": "E140_RATE_LIMITED",
  "retry_after": 30
}
```
