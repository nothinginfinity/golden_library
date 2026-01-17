# Phase 4C Architecture - Collaborative Workspace

## Overview

Phase 4C implements a **multi-agent collaborative workspace** where AI agents (Prax, Cairn, Koda) work together with humans in real-time to solve complex problems.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │   Web UI    │  │   CLI       │  │   API       │                  │
│  │  (Browser)  │  │  (Terminal) │  │  (REST)     │                  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │
│         │                │                │                          │
│         └────────────────┼────────────────┘                          │
│                          │                                           │
│                    WebSocket / HTTP                                  │
└──────────────────────────┼───────────────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────────────┐
│                  DASHBOARD SERVER                                    │
│                          │                                           │
│  ┌───────────────────────▼───────────────────────────────────────┐  │
│  │              WorkspaceSessionManager                           │  │
│  │  - Session lifecycle (create, join, leave)                    │  │
│  │  - User presence tracking                                      │  │
│  │  - Message broadcasting                                        │  │
│  │  - WebSocket event queuing                                     │  │
│  └───────────────────────┬───────────────────────────────────────┘  │
│                          │                                           │
│    ┌─────────────────────┼─────────────────────────────┐            │
│    │                     │                             │            │
│    ▼                     ▼                             ▼            │
│ ┌──────────┐      ┌──────────────┐             ┌──────────────┐    │
│ │  Agent   │      │    Canvas    │             │    Tool      │    │
│ │Orchestr. │      │  SyncManager │             │   Gateway    │    │
│ └────┬─────┘      └──────┬───────┘             └──────┬───────┘    │
│      │                   │                            │             │
│      │            ┌──────┴───────┐                   │             │
│      │            │              │                   │             │
│      ▼            ▼              ▼                   ▼             │
│ ┌─────────┐ ┌──────────┐ ┌───────────┐       ┌───────────┐        │
│ │  Task   │ │  CRDT    │ │  Version  │       │  Rate     │        │
│ │Delegat. │ │  Engine  │ │  History  │       │  Limiter  │        │
│ └─────────┘ └──────────┘ └───────────┘       └───────────┘        │
│                                                                     │
│    ┌─────────────────────┬─────────────────────┐                   │
│    │                     │                     │                    │
│    ▼                     ▼                     ▼                    │
│ ┌──────────┐      ┌──────────────┐      ┌──────────────┐           │
│ │  Demo    │      │ Conversation │      │  Workspace   │           │
│ │ Recorder │      │   Database   │      │   Config     │           │
│ └──────────┘      └──────────────┘      └──────────────┘           │
│                          │                                          │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────────┐
│                   PERSISTENCE LAYER                                  │
│                          │                                           │
│  ┌───────────────────────▼───────────────────────────────────────┐  │
│  │              PostgreSQL / SQLite                               │  │
│  │  - Messages table (full-text search)                          │  │
│  │  - Sessions table (summaries, context)                        │  │
│  │  - Recordings table (demo playback)                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. WorkspaceSessionManager (`workspace_session_manager.py`)

**Purpose:** Central hub for session management and message routing.

**Responsibilities:**
- Create/join/leave sessions
- Track user presence (online/away/offline)
- Route messages to appropriate agents
- Queue and broadcast WebSocket events
- Coordinate with all sub-managers

**Key Data Structures:**
```python
@dataclass
class WorkspaceSession:
    id: str
    created_at: str
    owner_id: str
    participants: Dict[str, SessionParticipant]
    messages: List[Message]
    canvas_documents: List[str]
    delegated_tasks: Dict[str, DelegatedTask]
    demo_mode: bool
    demo_recording_id: Optional[str]
```

### 2. AgentOrchestrator (`agent_orchestrator.py`)

**Purpose:** Multi-agent coordination and LLM integration.

**Agent Hierarchy:**
```
         ┌───────────┐
         │   PRAX    │  (Orchestrator)
         │ Strategist│  - Coordinates tasks
         └─────┬─────┘  - Delegates work
               │        - Synthesizes results
       ┌───────┴───────┐
       │               │
 ┌─────▼─────┐   ┌─────▼─────┐
 │   CAIRN   │   │   KODA    │  (Specialists)
 │ Architect │   │  Builder  │
 └───────────┘   └───────────┘
```

**Agent Capabilities:**

| Agent | Role | Tools | Delegates |
|-------|------|-------|-----------|
| Prax | Strategy | deepseek, web_search | Yes (to Cairn, Koda) |
| Cairn | Architecture | deepseek, code_analysis | No |
| Koda | Implementation | all tools | No |

### 3. TaskDelegationManager (`task_delegation_manager.py`)

**Purpose:** Hierarchical task delegation between agents.

**Delegation Flow:**
```
1. User requests complex task
2. Prax analyzes and decomposes
3. Prax delegates subtasks:
   - Research → Cairn
   - Implementation → Koda
4. Agents report completion
5. Prax synthesizes results
```

**Task States:**
```
PENDING → IN_PROGRESS → COMPLETED
                    ↘ BLOCKED
                    ↘ FAILED
```

### 4. CanvasSyncManager (`canvas_sync_manager.py`)

**Purpose:** Real-time collaborative document editing.

**CRDT Implementation:**
- Vector clocks for causality tracking
- Operation-based conflict resolution
- Section-level locking for exclusive edits

**Document Structure:**
```
CanvasDocument
├── id: canvas_abc123
├── title: "Project Analysis"
├── sections:
│   ├── research (markdown) - owned by Cairn
│   ├── implementation (code) - owned by Koda
│   └── summary (markdown) - shared
└── version_history: [...]
```

### 5. ToolGateway (`tool_gateway.py`)

**Purpose:** Agent tool permissions and execution.

**Tool Categories:**
- `llm`: DeepSeek, OpenAI, Claude Haiku
- `web`: Web search, URL fetch
- `code`: Code analysis, syntax checking

**Permission Model:**
```python
TOOL_PERMISSIONS = {
    'prax': ['deepseek', 'web_search'],
    'cairn': ['deepseek', 'code_analysis', 'web_search'],
    'koda': ['*']  # All tools
}
```

### 6. ConversationDatabase (`conversation_database.py`)

**Purpose:** Persistent storage with search and context recovery.

**Features:**
- Full-text search across messages
- Decision tracking (keyword-based)
- Context recovery for new agent instances
- Session summaries with topics/decisions

**Schema:**
```sql
messages (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    user_id TEXT,
    agent_id TEXT,
    role TEXT,
    content TEXT,
    timestamp TIMESTAMPTZ,
    mentions JSONB
)

session_summaries (
    session_id TEXT PRIMARY KEY,
    message_count INTEGER,
    key_topics JSONB,
    decisions JSONB,
    context_snapshot TEXT
)
```

### 7. DemoRecorder (`demo_recorder.py`)

**Purpose:** Live demo recording and playback for investors.

**Recording Events:**
- Messages (user and agent)
- Tool calls with results
- Delegation events
- Canvas edits
- Highlights (user-marked moments)

**Export Formats:**
- HTML (interactive playback)
- JSON (raw data)
- Markdown (transcript)

### 8. WorkspaceConfig (`workspace_config.py`)

**Purpose:** Configuration and hooks from CLAUDE.md.

**Config Sources:**
1. `./CLAUDE.md` (workspace-level)
2. `~/.claude/CLAUDE.md` (user-level)
3. Environment variables
4. Defaults

**Hook System:**
```yaml
hooks:
  on_message: ./hooks/log.sh
  on_task_complete: ./hooks/notify.sh
  on_session_end: ./hooks/summarize.sh
```

## Data Flow

### Message Flow
```
User Input
    │
    ▼
WebSocket Handler
    │
    ▼
SessionManager.add_message()
    │
    ├──► Broadcast to participants
    ├──► Save to ConversationDatabase
    ├──► Record to DemoRecorder (if active)
    └──► Route to AgentOrchestrator
              │
              ▼
         Agent processes
              │
              ▼
         Agent responds (same flow)
```

### Delegation Flow
```
Prax receives task
    │
    ▼
TaskDelegationManager.delegate_task()
    │
    ├──► Create TaskDefinition
    ├──► Assign canvas section
    ├──► Send to target agent
    └──► Track in session
              │
              ▼
Target agent (Cairn/Koda) works
    │
    ├──► Update task progress
    ├──► Write to canvas section
    └──► Report completion
              │
              ▼
Prax receives result
    │
    ▼
Synthesize and respond to user
```

## Error Handling

**Error Code Ranges:**
| Range | Category |
|-------|----------|
| E001-E019 | Session errors |
| E020-E039 | Database errors |
| E040-E059 | Tool errors |
| E060-E079 | Delegation errors |
| E080-E099 | Canvas errors |
| E100-E119 | Config errors |
| E120-E139 | Demo errors |
| E140-E149 | Rate limit errors |
| E900-E999 | Internal errors |

**Retry Strategy:**
- Exponential backoff (1s → 2s → 4s → ...)
- Circuit breaker for external services
- Max 3 retries for transient failures

## Security Considerations

1. **Session Isolation**: Each session has isolated state
2. **Tool Permissions**: Agents can only use allowed tools
3. **Audit Logging**: All actions logged with timestamps
4. **Input Validation**: All WebSocket messages validated
5. **Rate Limiting**: Per-tool and per-agent limits

## Performance

**Targets:**
- WebSocket latency: <100ms
- Canvas sync: <50ms
- Database queries: <10ms
- Concurrent users: 12+ per session

**Optimizations:**
- Connection pooling for database
- Message batching for broadcasts
- Lazy loading of canvas history
- In-memory session cache
