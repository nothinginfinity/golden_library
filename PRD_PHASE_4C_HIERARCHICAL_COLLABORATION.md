# PRD: Phase 4C - Hierarchical Delegation & Canvas Collaboration

**Project:** Golden Library - Collaborative Workspace Expansion
**Version:** Phase 4C
**Date:** January 16, 2026
**Status:** Planning
**Owner:** Koda (Builder)
**Prerequisites:** Phase 4B Complete (Agent-to-Agent Communication)

---

## Executive Summary

Phase 4C transforms the collaborative workspace from a flat multi-agent system into a **hierarchical delegation architecture** where Prax (orchestrator) coordinates human collaboration while delegating execution to specialized agents (Cairn/Koda) who can access external LLMs, APIs, and tools. This creates a scalable "delegation pyramid" enabling teams of 12+ people to collaborate with AI without generating content slop or losing attribution.

**Key Innovation:** Real-time canvas collaboration + hierarchical agent delegation + conversation database = institutional memory with coordinated AI workforce.

---

## Problem Statement

### Current State (Post-Phase 4B)
- ✅ Agents can message each other
- ✅ Workflow orchestration works
- ✅ Multiple humans can collaborate in sessions
- ❌ All agents use same tools (limited specialization)
- ❌ Prax's context gets bloated with implementation details
- ❌ No shared document editing
- ❌ No conversation persistence across sessions
- ❌ Each session is isolated (no institutional memory)

### Pain Points Addressed

**For Teams Using AI:**
1. **Content Slop Explosion** - Everyone generates AI content in silos, no quality control
2. **Attribution Loss** - "Who thought of this?" becomes impossible to answer
3. **Context Loss** - Sessions end, knowledge disappears
4. **Tool Fragmentation** - Everyone uses different AI tools independently
5. **Coordination Overhead** - Humans manually consolidate AI outputs

**For Businesses:**
6. **Onboarding Complexity** - Hard to demonstrate value without custom features
7. **Scalability Limits** - Can't coordinate 12+ people with AI effectively
8. **Knowledge Silos** - Team learnings don't compound

---

## Solution Overview

### Core Concept: The Delegation Pyramid

```
┌─────────────────────────────────────────────────────────┐
│  STRATEGIC LAYER                                        │
│  👥 Humans (2-12 people) ←→ 🎭 Prax (Orchestrator)     │
│  Focus: Vision, requirements, high-level decisions      │
└─────────────────────────────────────────────────────────┘
                           ↓ Delegates to
┌─────────────────────────────────────────────────────────┐
│  EXECUTION LAYER                                        │
│  🅰️ Cairn (Architect) | 🅱️ Koda (Builder)              │
│  Focus: Deep analysis, implementation, research         │
│  Tools: External LLMs, APIs, web search, MCP tools      │
└─────────────────────────────────────────────────────────┘
                           ↓ Delegates to
┌─────────────────────────────────────────────────────────┐
│  TOOL ECOSYSTEM LAYER                                   │
│  🤖 DeepSeek | Grok | OpenAI | Runway | Web Crawlers   │
│  Focus: Raw computational tasks, specialized processing │
└─────────────────────────────────────────────────────────┘
```

### Key Features

**1. Hierarchical Delegation**
- Prax focuses on strategy and human interaction
- Cairn/Koda handle token-heavy execution
- External APIs provide specialized capabilities

**2. Shared Canvas Collaboration**
- Multiple users edit documents simultaneously
- Agents can write to canvas in real-time
- Live updates visible to all participants

**3. Conversation Database**
- All Claude conversations persisted to database
- Agents can query conversation history
- Context continuity across sessions
- "Remind me what we discussed" capabilities

**4. Extended Tool Ecosystem**
- Cairn/Koda access external LLMs (DeepSeek, Grok, OpenAI, etc.)
- Web search and crawl capabilities
- MCP tool integration
- Custom API endpoints

**5. Live Demo/Onboarding Mode**
- Build custom features during client demos
- Real-time customization based on client needs
- Participatory product development

---

## User Personas

### Persona 1: Small Business Team
- **Name:** 12-person startup team
- **Goal:** Collaborate with AI without creating content slop
- **Workflow:**
  - Team discusses strategy through Prax
  - Prax delegates execution to Cairn/Koda
  - Agents use specialized tools for research/implementation
  - Canvas shows real-time progress
  - All decisions tracked in conversation database
- **Value:** Coordinated AI workforce with institutional memory

### Persona 2: Sales Demo / Onboarding
- **Name:** Software company onboarding new client
- **Goal:** Demonstrate platform value through live customization
- **Workflow:**
  - Client joins collaborative session
  - Discusses specific needs
  - Prax coordinates Cairn/Koda to build custom features live
  - Client sees their solution being built in real-time
  - Leaves with custom prototype
- **Value:** Participatory sales process, instant proof of value

### Persona 3: Long-Term Project Team
- **Name:** Enterprise team building complex system over months
- **Goal:** Maintain context and decisions across many sessions
- **Workflow:**
  - Multiple Prax instances over time
  - Each instance queries conversation database for context
  - Asks Cairn/Koda for status updates
  - Continues work seamlessly across sessions
- **Value:** Zero context loss, persistent institutional memory

---

## Feature Requirements

### F-4C1: Hierarchical Task Delegation (P0 - MVP)

**Requirements:**
- Prax can delegate tasks to Cairn and Koda with structured prompts
- Delegation includes:
  - Task description
  - Success criteria
  - Tool permissions (which external APIs to use)
  - Deadline/priority
  - Canvas location (where to write results)
- Agents report back to Prax with status updates
- Prax synthesizes agent results for humans

**Delegation Message Format:**
```json
{
  "type": "task_delegation",
  "from": "prax",
  "to": "cairn",
  "task": {
    "id": "task_123",
    "description": "Research HIPAA compliance requirements",
    "success_criteria": "Comprehensive list of requirements with sources",
    "tools_allowed": ["web_search", "deepseek"],
    "canvas_section": "compliance_analysis",
    "deadline": "2026-01-17T18:00:00Z",
    "priority": "high"
  }
}
```

**Acceptance Criteria:**
- Prax can delegate task with single message
- Cairn/Koda acknowledge task receipt
- Agents can request tool access
- Results written to canvas automatically
- Prax receives completion notification

---

### F-4C2: Shared Canvas / Document Collaboration (P0 - MVP)

**Requirements:**
- Shared document visible to all session participants
- Real-time collaborative editing (Operational Transform or CRDT)
- Section-based organization:
  - Humans can edit any section
  - Agents write to assigned sections
  - Version history for each section
- Multiple document types:
  - Markdown (default)
  - Code
  - Diagrams (Mermaid, etc.)
  - JSON/structured data

**Canvas Interface:**
```
┌─────────────────────────────────────────────────────────┐
│  📄 Shared Document: "Product Pitch Deck"              │
├─────────────────────────────────────────────────────────┤
│  Sections:                                              │
│  ├─ Executive Summary (Prax)                            │
│  ├─ Market Analysis (Cairn + Web Search)                │
│  ├─ Technical Architecture (Cairn)                      │
│  ├─ Implementation Roadmap (Koda)                       │
│  ├─ Compliance Framework (Cairn + DeepSeek)             │
│  └─ Pricing Model (Human editable)                      │
└─────────────────────────────────────────────────────────┘
```

**Acceptance Criteria:**
- Multiple users see edits in <500ms
- No edit conflicts (CRDT handles concurrent edits)
- Agents can write to assigned sections
- Version history shows who edited what
- Export to markdown, PDF, HTML

---

### F-4C3: External Tool Integration for Agents (P0 - MVP)

**Requirements:**
- Cairn and Koda can call external LLM APIs:
  - DeepSeek (code analysis)
  - Grok (creative tasks)
  - OpenAI (GPT-4 for specific tasks)
  - Claude Haiku (fast responses)
- Web capabilities:
  - Web search (Google, Bing)
  - Web crawl (Firecrawl, Jina)
  - URL fetch
- Media generation:
  - Runway (video)
  - DALL-E / Midjourney (images)
- Data access:
  - SQL databases
  - REST APIs
  - GraphQL endpoints

**Tool Configuration:**
```python
# Per-agent tool permissions
agent_tools = {
    'cairn': [
        'deepseek_api',      # Code analysis
        'web_search',         # Research
        'web_crawl',          # Deep research
        'database_read',      # Data access
        'diagram_generation'  # Architecture diagrams
    ],
    'koda': [
        'openai_api',         # Code generation
        'web_search',         # Quick lookups
        'runway_api',         # Media generation
        'database_write',     # Data persistence
        'code_execution'      # Run/test code
    ]
}
```

**Acceptance Criteria:**
- Agents can request tool usage
- Prax approves tool usage (or auto-approve by policy)
- Tool results integrated into agent responses
- Tool usage logged in audit trail
- Cost tracking per tool/API call

---

### F-4C4: Conversation Database & Context Continuity (P0 - MVP)

**Requirements:**
- All Claude conversations automatically saved to database
- Schema:
  - `session_id`
  - `user_id`
  - `agent_id`
  - `timestamp`
  - `role` (user/assistant/system)
  - `content`
  - `metadata` (tool calls, delegations, etc.)
- Query interface for agents:
  - "What did we decide about X?"
  - "Show me all conversations about feature Y"
  - "When did Alice suggest Z?"
- Context recovery for new Prax instances:
  - Auto-load last N messages from session
  - Ask Cairn/Koda for status update
  - Synthesize current state

**Database Schema:**
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    session_id VARCHAR(255),
    workspace_id VARCHAR(255),
    user_id VARCHAR(255),
    agent_id VARCHAR(50),  -- 'prax', 'cairn', 'koda', or null for humans
    timestamp TIMESTAMP,
    role VARCHAR(20),       -- 'user', 'assistant', 'system'
    content TEXT,
    metadata JSONB,         -- tool_calls, delegations, canvas_edits, etc.
    parent_message_id UUID,
    INDEX(session_id, timestamp),
    INDEX(workspace_id, timestamp),
    INDEX(user_id, timestamp)
);

CREATE TABLE agent_knowledge (
    id UUID PRIMARY KEY,
    agent_id VARCHAR(50),
    knowledge_type VARCHAR(50),  -- 'decision', 'pattern', 'lesson_learned'
    content TEXT,
    source_conversation_id UUID,
    created_at TIMESTAMP,
    relevance_score FLOAT
);
```

**Query Examples:**
```python
# Prax on session restart
db.query("""
    SELECT * FROM conversations
    WHERE session_id = ?
    ORDER BY timestamp DESC
    LIMIT 50
""")

# Agent knowledge retrieval
db.query("""
    SELECT * FROM agent_knowledge
    WHERE agent_id = 'cairn'
    AND knowledge_type = 'pattern'
    AND relevance_score > 0.8
""")
```

**Acceptance Criteria:**
- All messages saved to DB in real-time
- Agents can query conversation history
- New Prax instance can resume from DB
- Search by keyword, user, agent, timeframe
- Export full conversation as markdown

---

### F-4C5: Live Demo / Onboarding Mode (P1 - Post-MVP)

**Requirements:**
- Special "demo mode" for client onboarding
- Features:
  - Record session for replay
  - Highlight key moments (feature built, requirement met)
  - Custom branding (client logo, colors)
  - Real-time metrics (tokens used, time saved, features built)
  - Export demo as video or interactive replay

**Demo Workflow:**
1. Client joins session
2. Discusses specific needs
3. Prax: "Cairn, research their industry. Koda, draft a solution"
4. Agents work in background (visible to client)
5. Canvas shows live progress
6. Client sees custom solution emerge
7. Demo concludes with working prototype

**Acceptance Criteria:**
- Demo mode can be enabled per session
- Session recordings saved
- Highlights can be added by humans
- Custom branding applied
- Export to video or shareable link

---

### F-4C6: Configuration & Hooks System (P1 - Post-MVP)

**Requirements:**
- Per-workspace CLAUDE.md configuration
- Custom hooks for:
  - On session start
  - On task delegation
  - On tool usage
  - On canvas edit
  - On session end
- Per-user preferences:
  - Preferred agents
  - Tool permissions
  - Notification settings

**Configuration Example:**
```markdown
# workspace.md

## Tool Policies
- Cairn: Auto-approve web search, require approval for paid APIs
- Koda: Auto-approve code execution in sandbox, block database writes

## Delegation Policies
- Complex tasks (>2000 tokens): Delegate to Cairn
- Implementation tasks: Delegate to Koda
- Strategy discussions: Keep with Prax

## Canvas Rules
- Agents write to assigned sections only
- Humans can edit any section
- Auto-save every 30 seconds
```

**Acceptance Criteria:**
- Workspace config loaded on session start
- Hooks execute at correct events
- User preferences override workspace defaults
- Config can be edited via UI

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  ├─ Chat Panels (Prax, Cairn, Koda)                     │
│  ├─ Canvas Editor (Monaco / ProseMirror)                │
│  ├─ Audit Log / Activity Feed                           │
│  └─ Tool Usage Dashboard                                │
└─────────────────────────────────────────────────────────┘
                           ↓ WebSocket
┌─────────────────────────────────────────────────────────┐
│              WebSocket Server (Python)                   │
│  ├─ Session Manager (enhanced with DB persistence)      │
│  ├─ Task Delegator (Prax → Cairn/Koda)                  │
│  ├─ Tool Gateway (routes to external APIs)              │
│  └─ Canvas Sync (CRDT or OT)                            │
└─────────────────────────────────────────────────────────┘
         ↓                  ↓                  ↓
┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
│ Conversation │  │  External Tools  │  │ Agent        │
│ Database     │  │  - DeepSeek API  │  │ Orchestrator │
│ (PostgreSQL) │  │  - Grok API      │  │ (Enhanced)   │
│              │  │  - OpenAI API    │  │              │
│              │  │  - Web Search    │  │              │
└──────────────┘  └──────────────────┘  └──────────────┘
```

### Backend Components

**1. TaskDelegationManager**
```python
class TaskDelegationManager:
    def delegate_task(
        self,
        from_agent: str,  # 'prax'
        to_agent: str,    # 'cairn' or 'koda'
        task: TaskDefinition,
        session_id: str
    ) -> str:
        """
        Delegate task from orchestrator to execution agent.

        Returns: task_id for tracking
        """

    def get_task_status(self, task_id: str) -> TaskStatus:
        """Get current status of delegated task."""

    def complete_task(
        self,
        task_id: str,
        result: Any,
        canvas_section: str
    ):
        """Mark task complete, write to canvas."""
```

**2. CanvasSyncManager**
```python
class CanvasSyncManager:
    def __init__(self, algorithm='crdt'):  # or 'ot'
        self.algorithm = algorithm

    def apply_edit(
        self,
        section: str,
        content: str,
        author: str,
        timestamp: str
    ):
        """Apply edit to canvas section with conflict resolution."""

    def get_section(self, section: str) -> str:
        """Get current content of section."""

    def get_version_history(self, section: str) -> List[Edit]:
        """Get edit history for section."""
```

**3. ToolGateway**
```python
class ToolGateway:
    def __init__(self, api_keys: Dict[str, str]):
        self.tools = {
            'deepseek': DeepSeekAPI(api_keys['deepseek']),
            'grok': GrokAPI(api_keys['grok']),
            'openai': OpenAIAPI(api_keys['openai']),
            'web_search': WebSearchTool(),
            # ... more tools
        }

    async def execute_tool(
        self,
        tool_name: str,
        params: Dict,
        requesting_agent: str
    ) -> ToolResult:
        """Execute tool call on behalf of agent."""

    def check_permission(
        self,
        agent_id: str,
        tool_name: str,
        workspace_config: Dict
    ) -> bool:
        """Verify agent has permission to use tool."""
```

**4. ConversationDatabase**
```python
class ConversationDatabase:
    def __init__(self, db_url: str):
        self.db = PostgreSQL(db_url)

    def save_message(
        self,
        session_id: str,
        agent_id: str,
        role: str,
        content: str,
        metadata: Dict
    ):
        """Save message to database."""

    def query_history(
        self,
        session_id: str,
        filters: Dict,
        limit: int = 50
    ) -> List[Message]:
        """Query conversation history."""

    def get_session_summary(self, session_id: str) -> str:
        """Generate summary of session for context recovery."""
```

### Frontend Components

**1. Canvas Editor**
- Monaco Editor for code
- ProseMirror for rich text
- Real-time collaboration cursors
- Section-based editing with permissions

**2. Task Dashboard**
- Active delegations
- Task progress bars
- Agent status (working on X, completed Y)
- Tool usage metrics

**3. Conversation Database UI**
- Search past conversations
- Filter by agent, user, keyword
- Export conversations
- Visualize conversation threads

---

## Implementation Phases

### Phase 4C.1: Hierarchical Delegation Foundation (3 days)

**Tasks:**
1. Implement TaskDelegationManager
2. Enhance Prax system prompt with delegation patterns
3. Add task tracking to WorkspaceSession
4. Update WebSocket events for task lifecycle
5. Basic canvas section assignment

**Deliverables:**
- Prax can delegate tasks to Cairn/Koda
- Tasks tracked with status
- Results reported back to Prax

**Success Criteria:**
- Prax: "Cairn, research X" → Cairn receives task → completes → reports back

---

### Phase 4C.2: Canvas Collaboration (4 days)

**Tasks:**
1. Choose CRDT library (Yjs or Automerge)
2. Implement CanvasSyncManager
3. Build frontend canvas editor (Monaco + ProseMirror)
4. Add section-based permissions
5. Version history tracking
6. Export functionality

**Deliverables:**
- Shared canvas with real-time editing
- Section-based organization
- Agents can write to assigned sections
- Export to markdown/PDF

**Success Criteria:**
- Multiple users edit canvas simultaneously, no conflicts
- Agents write to sections, visible to all users
- Export includes all sections

---

### Phase 4C.3: External Tool Integration (3 days)

**Tasks:**
1. Implement ToolGateway
2. Add API integrations:
   - DeepSeek API
   - OpenAI API
   - Web search (SerpAPI or Brave)
3. Update Cairn/Koda system prompts with tool descriptions
4. Add permission checking
5. Tool usage audit logging

**Deliverables:**
- Cairn/Koda can call external APIs
- Tool results integrated into responses
- Permission system enforced
- Cost tracking per tool

**Success Criteria:**
- Cairn: "Use DeepSeek to analyze this code" → DeepSeek called → results returned
- Tool usage logged in audit trail

---

### Phase 4C.4: Conversation Database (3 days)

**Tasks:**
1. Set up PostgreSQL database
2. Implement ConversationDatabase class
3. Auto-save all messages to DB
4. Build query interface for agents
5. Context recovery for new Prax instances
6. Frontend search UI

**Deliverables:**
- All conversations saved to database
- Agents can query history
- Search UI for humans
- Context recovery works

**Success Criteria:**
- New Prax instance resumes from DB
- Search: "What did we decide about feature X?" → relevant messages shown
- No data loss across sessions

---

### Phase 4C.5: Live Demo Mode (2 days)

**Tasks:**
1. Add demo mode flag to sessions
2. Session recording
3. Highlight feature for key moments
4. Custom branding support
5. Export to video or shareable link

**Deliverables:**
- Demo mode enabled per session
- Recordings saved
- Export to video

**Success Criteria:**
- Client onboarding: features built live, recorded, exportable

---

### Phase 4C.6: Configuration & Polish (2 days)

**Tasks:**
1. Workspace CLAUDE.md configuration
2. Hooks system
3. User preferences UI
4. Performance optimization
5. Documentation

**Deliverables:**
- Configurable workspace settings
- Hooks execute correctly
- User guide for Phase 4C

**Success Criteria:**
- Workspace config loaded and applied
- Hooks fire on correct events
- Users can customize experience

---

## Success Metrics

### Collaboration Metrics
- **Team Size:** Support 12+ simultaneous users
- **Task Delegation:** 80%+ of execution tasks delegated to Cairn/Koda
- **Canvas Usage:** 70%+ of sessions use shared canvas
- **Tool Calls:** Average 5+ external tool calls per session

### Context Continuity
- **Session Resumption:** 100% success rate for context recovery
- **Query Accuracy:** 90%+ relevant results for "What did we discuss?" queries
- **Knowledge Retention:** Key decisions retrievable months later

### Business Value
- **Onboarding Time:** Reduce from 2 weeks to 2 hours (live demo)
- **Content Quality:** Reduce AI slop by 80% (coordinated generation)
- **Attribution:** 100% of ideas/decisions tracked to source
- **Cost Efficiency:** 40% token savings (Prax delegates heavy work)

---

## Risks & Mitigations

### Risk 1: Database Performance
**Risk:** Query latency impacts agent response time
**Mitigation:**
- Index frequently queried columns
- Cache recent conversations in Redis
- Async queries don't block agent responses

### Risk 2: Canvas Sync Complexity
**Risk:** CRDT implementation too complex
**Mitigation:**
- Use proven library (Yjs)
- Start with text-only, add rich features later
- Fallback to last-write-wins if needed

### Risk 3: External API Costs
**Risk:** Tool usage costs spiral
**Mitigation:**
- Per-workspace budgets
- Require approval for expensive tools
- Cost alerts at thresholds

### Risk 4: Tool Permission Abuse
**Risk:** Agents call unauthorized tools
**Mitigation:**
- Strict permission checking
- Audit all tool calls
- Require human approval for sensitive operations

---

## Future Enhancements (Phase 4D+)

1. **Multi-Workspace Support:** Teams can have multiple workspaces
2. **Agent Specialization:** Custom agent roles beyond Prax/Cairn/Koda
3. **Template Library:** Pre-built workflows for common use cases
4. **Integration Marketplace:** Third-party tools and APIs
5. **Mobile Apps:** iOS/Android for on-the-go collaboration
6. **Voice/Video:** WebRTC for richer collaboration
7. **AI Training:** Fine-tune agents on workspace conversations

---

## Conclusion

Phase 4C transforms the collaborative workspace into a **hierarchical AI delegation platform** that solves the coordination chaos plaguing teams using AI. By combining:
- Structured delegation (Prax → Cairn/Koda → External Tools)
- Shared canvas collaboration
- Persistent conversation database
- Live demo capabilities

We enable small teams to operate like coordinated AI workforces, eliminating content slop while maintaining perfect attribution and institutional memory.

**This is the future of AI-augmented teamwork.**

---

**Next Steps:**
1. Review and approve PRD
2. Break down into implementable tickets
3. Start with Phase 4C.1 (Hierarchical Delegation)
4. Ship incrementally with user testing at each phase

**Estimated Timeline:** 17 days total (3-4 weeks with testing)

**Dependencies:**
- PostgreSQL database setup
- CRDT library integration (Yjs)
- External API keys (DeepSeek, OpenAI, etc.)
- Canvas editor component

---

**Document Version:** 1.0
**Last Updated:** January 16, 2026
**Approved By:** Pending
