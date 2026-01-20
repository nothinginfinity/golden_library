#!/usr/bin/env python3
"""
Workspace Session Manager - Manages collaborative workspace sessions

Handles:
- Session creation and lifecycle
- User presence tracking
- Message broadcasting
- State synchronization
- Agent orchestration per session
"""

import uuid
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

# Redis for API key retrieval
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

def get_api_key():
    """Get Anthropic API key from environment, Redis, or file."""
    # 1. Check environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if api_key:
        return api_key

    # 2. Check Redis
    if REDIS_AVAILABLE:
        redis_host = os.environ.get('REDISHOST') or os.environ.get('REDIS_HOST', 'localhost')
        redis_port = int(os.environ.get('REDISPORT') or os.environ.get('REDIS_PORT', '6379'))
        redis_password = os.environ.get('REDISPASSWORD') or os.environ.get('REDIS_PASSWORD', '')
        try:
            if redis_password:
                r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True, socket_timeout=2)
            else:
                r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True, socket_timeout=2)
            data = r.get('golden_library:api_keys')
            if data:
                keys = json.loads(data)
                api_key = keys.get('claude')
                if api_key:
                    print(f"[SessionManager] Got API key from Redis")
                    return api_key
        except Exception as e:
            print(f"[SessionManager] Redis lookup failed: {e}")

    # 3. Check file
    api_keys_file = Path.home() / '.claude' / 'api_keys.json'
    if api_keys_file.exists():
        try:
            with open(api_keys_file, 'r') as f:
                keys = json.load(f)
            api_key = keys.get('claude')
            if api_key:
                return api_key
        except:
            pass

    return None

# Import AgentOrchestrator for per-session agent management
try:
    from agent_orchestrator import AgentOrchestrator
except ImportError:
    AgentOrchestrator = None
    print("[WorkspaceSessionManager] Warning: AgentOrchestrator not available")

# Import ConversationDatabase for persistent storage (Phase 4C.4)
try:
    from conversation_database import ConversationDatabase, StoredMessage, get_conversation_db
    HAS_CONVERSATION_DB = True
except ImportError:
    HAS_CONVERSATION_DB = False
    print("[WorkspaceSessionManager] Warning: ConversationDatabase not available")

# Import DemoRecorder for live demo mode (Phase 4C.5)
try:
    from demo_recorder import DemoRecorder, EventType, BrandingConfig, get_demo_recorder
    HAS_DEMO_RECORDER = True
except ImportError:
    HAS_DEMO_RECORDER = False
    print("[WorkspaceSessionManager] Warning: DemoRecorder not available")

# Import WorkspaceConfig for configuration & hooks (Phase 4C.6)
try:
    from workspace_config import WorkspaceConfig, HookEvent, get_workspace_config
    HAS_WORKSPACE_CONFIG = True
except ImportError:
    HAS_WORKSPACE_CONFIG = False
    print("[WorkspaceSessionManager] Warning: WorkspaceConfig not available")

# Import error codes (Phase 4C - Day 2 consolidation)
try:
    from error_codes import (
        make_error_response, session_not_found, db_not_initialized,
        demo_not_available, demo_already_active, demo_not_active,
        config_not_available, internal_error
    )
    HAS_ERROR_CODES = True
except ImportError:
    HAS_ERROR_CODES = False
    # Fallback error function
    def make_error_response(code, details=None, **kwargs):
        return {'error': details or code}


class UserRole(Enum):
    """User roles in a session."""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class AgentMessage:
    """Agent-to-agent message with orchestration metadata."""
    id: str
    from_agent: str  # 'prax', 'cairn', 'koda'
    to_agent: str    # 'prax', 'cairn', 'koda'
    content: str
    timestamp: str
    priority: str = 'medium'  # 'high', 'medium', 'low'
    read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)  # workflow_id, task_type, deadline, depends_on, context_keys

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class WorkflowState:
    """Tracks multi-agent workflow state."""
    id: str
    name: str
    status: str  # 'active', 'completed', 'blocked'
    milestones: Dict[str, Dict] = field(default_factory=dict)  # milestone -> {status, completion%}
    dependencies: List[str] = field(default_factory=list)
    assigned_agents: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    deadline: Optional[str] = None

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class AuditEntry:
    """Represents an audit log entry."""
    id: str
    session_id: str
    timestamp: str
    user_id: str
    action: str  # 'join', 'leave', 'message', 'claim_control', 'release_control', 'role_change', 'lock_acquire', 'lock_release', 'agent_message_sent', 'blocker_escalated', 'milestone_updated', 'context_shared', 'task_delegated', 'task_acknowledged', 'task_started', 'task_completed', 'task_blocked', 'task_failed', 'canvas_updated'
    details: Dict[str, Any] = field(default_factory=dict)
    workflow_id: Optional[str] = None  # Link to workflow if applicable

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class User:
    """Represents a user in a workspace session."""
    id: str
    name: str
    role: UserRole
    websocket: Any  # WebSocket connection
    joined_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    cursor_position: Optional[Dict] = None
    is_typing: bool = False
    avatar_color: Optional[str] = None  # Hex color for avatar background

    def __post_init__(self):
        """Generate avatar color if not provided."""
        if not self.avatar_color:
            # Generate consistent color based on user ID
            import hashlib
            hash_val = int(hashlib.md5(self.id.encode()).hexdigest()[:6], 16)
            colors = ['#3b82f6', '#a855f7', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#8b5cf6']
            self.avatar_color = colors[hash_val % len(colors)]

    def get_initials(self) -> str:
        """Get user initials for avatar."""
        parts = self.name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return self.name[:2].upper()

    def to_dict(self):
        """Convert to dict for JSON serialization (excluding websocket)."""
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role.value,
            'joined_at': self.joined_at,
            'last_seen': self.last_seen,
            'cursor_position': self.cursor_position,
            'is_typing': self.is_typing,
            'avatar_color': self.avatar_color,
            'initials': self.get_initials()
        }


@dataclass
class Message:
    """Represents a message in the workspace."""
    id: str
    session_id: str
    user_id: str
    agent_id: Optional[str]  # 'a', 'b', 'moderator', or None for user messages
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    mentions: List[str] = field(default_factory=list)  # List of mentioned user_ids

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class WorkspaceSession:
    """Represents a collaborative workspace session."""
    id: str
    created_at: str
    expires_at: str
    owner_id: str
    users: Dict[str, User] = field(default_factory=dict)  # user_id -> User
    messages: List[Message] = field(default_factory=list)
    agent_contexts: Dict[str, List] = field(default_factory=lambda: {
        'a': [],
        'b': [],
        'moderator': []
    })
    documents: Dict[str, str] = field(default_factory=dict)  # agent_id -> document
    agent_control: Dict[str, Optional[str]] = field(default_factory=lambda: {
        'a': None,  # user_id who controls Agent A
        'b': None,  # user_id who controls Agent B
        'moderator': None  # user_id who controls Moderator
    })
    document_locks: Dict[str, Optional[str]] = field(default_factory=lambda: {
        'a': None,  # user_id currently editing Agent A
        'b': None,  # user_id currently editing Agent B
        'moderator': None  # user_id currently editing Moderator
    })
    audit_log: List[AuditEntry] = field(default_factory=list)
    orchestrator: Any = None  # AgentOrchestrator instance for this session

    # Phase 4B: Agent-to-Agent Communication
    agent_inboxes: Dict[str, List[AgentMessage]] = field(default_factory=lambda: {
        'prax': [],
        'cairn': [],
        'koda': []
    })
    shared_contexts: Dict[str, Any] = field(default_factory=dict)  # context_key -> content
    workflows: Dict[str, WorkflowState] = field(default_factory=dict)  # workflow_id -> state
    agent_capabilities: Dict[str, List[str]] = field(default_factory=lambda: {
        'prax': ['orchestration', 'coordination', 'strategy'],
        'cairn': ['architecture', 'design', 'code_review'],
        'koda': ['implementation', 'testing', 'debugging']
    })
    agent_workload: Dict[str, Dict] = field(default_factory=lambda: {
        'prax': {'active_tasks': 0, 'status': 'idle'},
        'cairn': {'active_tasks': 0, 'status': 'idle'},
        'koda': {'active_tasks': 0, 'status': 'idle'}
    })

    # Phase 4C.1: Hierarchical Delegation
    delegated_tasks: Dict[str, Any] = field(default_factory=dict)  # task_id -> task_info
    canvas_sections: Dict[str, Dict] = field(default_factory=dict)  # section_name -> {content, owner, updated_at}

    # Phase 4C.5: Demo Mode
    demo_mode: bool = False
    demo_recording_id: Optional[str] = None
    demo_title: Optional[str] = None
    demo_branding: Optional[Dict] = None

    def to_dict(self):
        """Convert to dict for JSON serialization (excluding orchestrator)."""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'owner_id': self.owner_id,
            'users': {uid: user.to_dict() for uid, user in self.users.items()},
            'messages': [msg.to_dict() for msg in self.messages],
            'agent_contexts': self.agent_contexts,
            'documents': self.documents,
            'agent_control': self.agent_control,
            'document_locks': self.document_locks,
            'audit_log': [entry.to_dict() for entry in self.audit_log],
            # Phase 4B fields
            'agent_inboxes': {
                agent: [msg.to_dict() for msg in msgs]
                for agent, msgs in self.agent_inboxes.items()
            },
            'shared_contexts': self.shared_contexts,
            'workflows': {wid: wf.to_dict() for wid, wf in self.workflows.items()},
            'agent_capabilities': self.agent_capabilities,
            'agent_workload': self.agent_workload,
            # Phase 4C.1 fields
            'delegated_tasks': self.delegated_tasks,
            'canvas_sections': self.canvas_sections
            # orchestrator excluded (not JSON serializable)
        }

    def is_expired(self) -> bool:
        """Check if session has expired."""
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.utcnow() > expires


class WorkspaceSessionManager:
    """Manages all workspace sessions."""

    def __init__(self, session_duration_hours: int = 24, database_url: Optional[str] = None, workspace_dir: Optional[str] = None):
        self.sessions: Dict[str, WorkspaceSession] = {}
        self.session_duration_hours = session_duration_hours
        self.cleanup_task = None
        self.ws_event_queue: List[Dict] = []  # Queue for WebSocket events to broadcast

        # Phase 4C.4: Conversation Database
        self._conversation_db: Optional[Any] = None
        self._database_url = database_url
        self._db_initialized = False

        # Phase 4C.6: Workspace Configuration
        self._workspace_config: Optional[Any] = None
        self._workspace_dir = workspace_dir
        if HAS_WORKSPACE_CONFIG and workspace_dir:
            self._workspace_config = WorkspaceConfig(workspace_dir)
            print(f"[SessionManager] Loaded workspace config: {self._workspace_config.settings.workspace_name}")

    def _add_audit_entry(self, session_id: str, user_id: str, action: str, details: Dict[str, Any] = None, workflow_id: Optional[str] = None):
        """Add an entry to the audit log."""
        session = self.sessions.get(session_id)
        if not session:
            return

        entry = AuditEntry(
            id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id,
            action=action,
            details=details or {},
            workflow_id=workflow_id
        )

        session.audit_log.append(entry)
        print(f"[SessionManager] Audit: {action} by {user_id} in {session_id}")

    def _parse_mentions(self, content: str, session_id: str) -> List[str]:
        """
        Parse @mentions from message content and return list of mentioned user IDs.

        Supports:
        - @username (exact match)
        - @"User Name" (quoted names with spaces)
        """
        import re

        session = self.sessions.get(session_id)
        if not session:
            return []

        mentioned_ids = []

        # Pattern 1: @"User Name" (quoted)
        quoted_pattern = r'@"([^"]+)"'
        quoted_matches = re.findall(quoted_pattern, content)

        # Pattern 2: @username (no spaces)
        simple_pattern = r'@(\w+)'
        simple_matches = re.findall(simple_pattern, content)

        all_mentions = quoted_matches + simple_matches

        # Match against actual user names in session
        for mention in all_mentions:
            mention_lower = mention.lower()
            for user_id, user in session.users.items():
                # Match full name or first name
                if (user.name.lower() == mention_lower or
                    user.name.lower().startswith(mention_lower + ' ') or
                    user.name.split()[0].lower() == mention_lower):
                    if user_id not in mentioned_ids:
                        mentioned_ids.append(user_id)
                        break

        return mentioned_ids

    def create_session(self, owner_id: str, owner_name: str, owner_ws: Any) -> WorkspaceSession:
        """Create a new workspace session."""
        session_id = self._generate_session_id()
        now = datetime.utcnow()
        expires = now + timedelta(hours=self.session_duration_hours)

        # Create owner user
        owner = User(
            id=owner_id,
            name=owner_name,
            role=UserRole.OWNER,
            websocket=owner_ws
        )

        # Create session
        session = WorkspaceSession(
            id=session_id,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            owner_id=owner_id,
            users={owner_id: owner}
        )

        # Initialize AgentOrchestrator for this session (with MCP tools support)
        if AgentOrchestrator:
            try:
                # Get API key from env, Redis, or file
                api_key = get_api_key()
                if api_key:
                    session.orchestrator = AgentOrchestrator(
                        api_key=api_key,
                        session_users=session.users,
                        session_manager=self,  # Pass session manager for MCP tools
                        session_id=session_id   # Pass session ID for MCP tool calls
                    )
                    print(f"[SessionManager] Initialized AgentOrchestrator for session {session_id} with MCP tools")
                else:
                    print(f"[SessionManager] Warning: No API key found - agents will not work. Save key in Config tab.")
            except Exception as e:
                print(f"[SessionManager] Warning: Could not initialize orchestrator: {e}")
                import traceback
                traceback.print_exc()

        self.sessions[session_id] = session
        print(f"[SessionManager] Created session {session_id} for user {owner_name}")

        return session

    def join_session(self, session_id: str, user_id: str, user_name: str, websocket: Any) -> Optional[WorkspaceSession]:
        """Join an existing session."""
        session = self.sessions.get(session_id)

        if not session:
            print(f"[SessionManager] Session {session_id} not found")
            return None

        if session.is_expired():
            print(f"[SessionManager] Session {session_id} has expired")
            return None

        # Add user to session
        user = User(
            id=user_id,
            name=user_name,
            role=UserRole.EDITOR,  # Default role for joiners
            websocket=websocket
        )

        session.users[user_id] = user
        print(f"[SessionManager] User {user_name} joined session {session_id}")

        # Update orchestrator with new session users
        if session.orchestrator:
            session.orchestrator.update_session_users(session.users)

        # Audit log
        self._add_audit_entry(session_id, user_id, 'join', {'user_name': user_name})

        return session

    def leave_session(self, session_id: str, user_id: str):
        """User leaves a session."""
        session = self.sessions.get(session_id)

        if not session:
            return

        if user_id in session.users:
            user_name = session.users[user_id].name

            # Audit log
            self._add_audit_entry(session_id, user_id, 'leave', {'user_name': user_name})

            del session.users[user_id]
            print(f"[SessionManager] User {user_name} left session {session_id}")

            # Update orchestrator with updated session users
            if session.orchestrator:
                session.orchestrator.update_session_users(session.users)

        # Auto-export and delete session if no users left
        if not session.users:
            # Auto-export if session had messages
            if len(session.messages) > 0:
                print(f"[SessionManager] Auto-exporting session {session_id} before deletion")
                export_path = self.export_session_to_file(session_id)
                if export_path:
                    print(f"[SessionManager] Session {session_id} exported to {export_path}")
                else:
                    print(f"[SessionManager] Warning: Failed to export session {session_id}")

            del self.sessions[session_id]
            print(f"[SessionManager] Deleted empty session {session_id}")

    def get_session(self, session_id: str) -> Optional[WorkspaceSession]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def add_message(self, session_id: str, user_id: str, agent_id: Optional[str], role: str, content: str) -> Optional[Message]:
        """Add a message to a session."""
        session = self.sessions.get(session_id)

        if not session:
            return None

        # Parse mentions from content
        mentions = self._parse_mentions(content, session_id)

        message = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            role=role,
            content=content,
            mentions=mentions
        )

        session.messages.append(message)

        # Also add to agent context if it's an agent message
        if agent_id and agent_id in session.agent_contexts:
            session.agent_contexts[agent_id].append({
                'role': role,
                'content': content
            })

        # Audit log for user messages (not assistant responses to avoid noise)
        if role == 'user':
            self._add_audit_entry(
                session_id, user_id, 'message',
                {
                    'agent_id': agent_id,
                    'message_preview': content[:100] if content else '',
                    'mentions': mentions
                }
            )

        # Phase 4C.4: Auto-save to database
        if HAS_CONVERSATION_DB and self._db_initialized:
            asyncio.create_task(self._save_message_to_db(message))

        # Phase 4C.5: Record to demo if active
        if HAS_DEMO_RECORDER and session.demo_mode:
            event_type = 'agent_response' if agent_id else 'message'
            self.record_demo_event(
                session_id=session_id,
                event_type=event_type,
                actor=agent_id or user_id,
                content={'message': content, 'agent_id': agent_id}
            )

        return message

    # ===== Phase 4C.4: Conversation Database Methods =====

    async def initialize_database(self, database_url: Optional[str] = None):
        """Initialize the conversation database."""
        if not HAS_CONVERSATION_DB:
            print("[SessionManager] ConversationDatabase not available, skipping DB init")
            return False

        try:
            self._conversation_db = await get_conversation_db(
                database_url=database_url or self._database_url
            )
            self._db_initialized = True
            print("[SessionManager] ConversationDatabase initialized")
            return True
        except Exception as e:
            print(f"[SessionManager] Failed to initialize database: {e}")
            return False

    async def _save_message_to_db(self, message: Message):
        """Save a message to the conversation database."""
        if not self._conversation_db:
            return

        try:
            stored_msg = StoredMessage(
                id=message.id,
                session_id=message.session_id,
                user_id=message.user_id,
                agent_id=message.agent_id,
                role=message.role,
                content=message.content,
                timestamp=message.timestamp,
                mentions=message.mentions
            )
            await self._conversation_db.save_message(stored_msg)
        except Exception as e:
            print(f"[SessionManager] Error saving message to DB: {e}")

    async def search_conversation_history(
        self,
        query: str,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search conversation history. Available to agents via query interface.

        Args:
            query: Search query
            session_id: Limit to specific session
            agent_id: Limit to specific agent's messages
            limit: Max results

        Returns:
            List of matching messages with relevance scores
        """
        if not self._conversation_db:
            return []

        try:
            results = await self._conversation_db.search_messages(
                query=query,
                session_id=session_id,
                agent_id=agent_id,
                limit=limit
            )
            return [
                {'message': msg.to_dict(), 'score': score}
                for msg, score in results
            ]
        except Exception as e:
            print(f"[SessionManager] Error searching history: {e}")
            return []

    async def search_decisions(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search for decision-related messages.

        Args:
            query: Topic to search for
            session_id: Limit to specific session
            limit: Max results

        Returns:
            List of decision messages
        """
        if not self._conversation_db:
            return []

        try:
            results = await self._conversation_db.search_decisions(
                query=query,
                session_id=session_id,
                limit=limit
            )
            return [
                {'message': msg.to_dict(), 'score': score}
                for msg, score in results
            ]
        except Exception as e:
            print(f"[SessionManager] Error searching decisions: {e}")
            return []

    async def get_context_for_prax(self, session_id: str) -> Dict[str, Any]:
        """
        Get context for a new Prax instance to resume work.

        Args:
            session_id: Session to recover context from

        Returns:
            Context dict with messages, summary, and recovery instructions
        """
        if not self._conversation_db:
            # Fallback: return in-memory messages
            session = self.sessions.get(session_id)
            if not session:
                return {'error': 'Session not found'}

            return {
                'session_id': session_id,
                'messages': [m.to_dict() for m in session.messages[-50:]],
                'summary': None,
                'recovery_instructions': ['Database not available, using in-memory messages']
            }

        try:
            return await self._conversation_db.get_context_for_prax(session_id)
        except Exception as e:
            print(f"[SessionManager] Error getting Prax context: {e}")
            return {'error': str(e)}

    async def update_session_summary(
        self,
        session_id: str,
        key_topics: Optional[List[str]] = None,
        decisions: Optional[List[str]] = None
    ) -> bool:
        """Update session summary with key topics and decisions."""
        if not self._conversation_db:
            return False

        try:
            return await self._conversation_db.update_session_summary(
                session_id=session_id,
                key_topics=key_topics,
                decisions=decisions
            )
        except Exception as e:
            print(f"[SessionManager] Error updating summary: {e}")
            return False

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self._conversation_db:
            return {'error': 'Database not initialized'}

        try:
            return await self._conversation_db.get_statistics()
        except Exception as e:
            return {'error': str(e)}

    # ===== Phase 4C.5: Demo Mode Methods =====

    def start_demo_mode(
        self,
        session_id: str,
        title: str = "Demo Recording",
        description: str = "",
        branding: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Start demo mode for a session.

        Args:
            session_id: Session to record
            title: Demo title
            description: Demo description
            branding: Custom branding config

        Returns:
            Recording info or None
        """
        if not HAS_DEMO_RECORDER:
            return demo_not_available() if HAS_ERROR_CODES else {'error': 'DemoRecorder not available'}

        session = self.sessions.get(session_id)
        if not session:
            return session_not_found(session_id) if HAS_ERROR_CODES else {'error': 'Session not found'}

        if session.demo_mode:
            return demo_already_active() if HAS_ERROR_CODES else {'error': 'Demo mode already active'}

        try:
            recorder = get_demo_recorder()

            # Convert branding dict to BrandingConfig if provided
            branding_config = None
            if branding:
                branding_config = BrandingConfig(**branding)

            recording = recorder.start_recording(
                session_id=session_id,
                title=title,
                description=description,
                branding=branding_config
            )

            session.demo_mode = True
            session.demo_recording_id = recording.id
            session.demo_title = title
            session.demo_branding = branding

            print(f"[SessionManager] Demo mode started for session {session_id}: {recording.id}")

            return {
                'recording_id': recording.id,
                'title': title,
                'started_at': recording.started_at
            }
        except Exception as e:
            print(f"[SessionManager] Error starting demo mode: {e}")
            return {'error': str(e)}

    def stop_demo_mode(self, session_id: str) -> Optional[Dict]:
        """
        Stop demo mode for a session.

        Args:
            session_id: Session to stop recording

        Returns:
            Recording summary or None
        """
        if not HAS_DEMO_RECORDER:
            return demo_not_available() if HAS_ERROR_CODES else {'error': 'DemoRecorder not available'}

        session = self.sessions.get(session_id)
        if not session:
            return session_not_found(session_id) if HAS_ERROR_CODES else {'error': 'Session not found'}

        if not session.demo_mode:
            return demo_not_active() if HAS_ERROR_CODES else {'error': 'Demo mode not active'}

        try:
            recorder = get_demo_recorder()
            recording = recorder.stop_recording(session_id)

            session.demo_mode = False
            recording_id = session.demo_recording_id
            session.demo_recording_id = None
            session.demo_title = None

            if recording:
                print(f"[SessionManager] Demo mode stopped: {recording.id} ({recording.duration_ms}ms)")
                return {
                    'recording_id': recording.id,
                    'duration_ms': recording.duration_ms,
                    'event_count': len(recording.events),
                    'highlight_count': len(recording.highlights)
                }
            return {'recording_id': recording_id, 'status': 'stopped'}
        except Exception as e:
            print(f"[SessionManager] Error stopping demo mode: {e}")
            return {'error': str(e)}

    def add_demo_highlight(
        self,
        session_id: str,
        label: str,
        description: Optional[str] = None
    ) -> bool:
        """
        Add a highlight marker to the current demo recording.

        Args:
            session_id: Session ID
            label: Short label for the highlight
            description: Optional longer description

        Returns:
            True if added successfully
        """
        if not HAS_DEMO_RECORDER:
            return False

        session = self.sessions.get(session_id)
        if not session or not session.demo_mode:
            return False

        try:
            recorder = get_demo_recorder()
            event = recorder.add_highlight(session_id, label, description)
            return event is not None
        except Exception as e:
            print(f"[SessionManager] Error adding highlight: {e}")
            return False

    def record_demo_event(
        self,
        session_id: str,
        event_type: str,
        actor: str,
        content: Dict[str, Any]
    ):
        """
        Record an event to the demo (internal use).

        Called automatically when messages are sent, etc.
        """
        if not HAS_DEMO_RECORDER:
            return

        session = self.sessions.get(session_id)
        if not session or not session.demo_mode:
            return

        try:
            recorder = get_demo_recorder()
            recorder.record_event(
                session_id=session_id,
                event_type=EventType(event_type),
                actor=actor,
                content=content
            )
        except Exception as e:
            # Don't let recording errors affect normal operation
            pass

    def get_demo_recordings(self) -> List[Dict]:
        """List all saved demo recordings."""
        if not HAS_DEMO_RECORDER:
            return []

        try:
            recorder = get_demo_recorder()
            return recorder.list_recordings()
        except Exception as e:
            print(f"[SessionManager] Error listing recordings: {e}")
            return []

    def export_demo_html(self, recording_id: str) -> Optional[str]:
        """Export a demo recording as HTML."""
        if not HAS_DEMO_RECORDER:
            return None

        try:
            recorder = get_demo_recorder()
            return recorder.export_html(recording_id)
        except Exception as e:
            print(f"[SessionManager] Error exporting HTML: {e}")
            return None

    def export_demo_json(self, recording_id: str) -> Optional[str]:
        """Export a demo recording as JSON."""
        if not HAS_DEMO_RECORDER:
            return None

        try:
            recorder = get_demo_recorder()
            return recorder.export_json(recording_id)
        except Exception as e:
            print(f"[SessionManager] Error exporting JSON: {e}")
            return None

    # ===== Phase 4C.6: Configuration & Hooks Methods =====

    def get_workspace_config(self) -> Optional[Any]:
        """Get the workspace configuration object."""
        return self._workspace_config

    def get_workspace_settings(self) -> Dict[str, Any]:
        """Get all workspace settings."""
        if not self._workspace_config:
            return {}
        return self._workspace_config.get_all_settings()

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get preferences for a user."""
        if not self._workspace_config:
            return {'user_id': user_id, 'theme': 'dark'}  # Defaults

        prefs = self._workspace_config.get_user_preferences(user_id)
        return prefs.to_dict()

    def update_user_preferences(self, user_id: str, **updates) -> Dict[str, Any]:
        """Update user preferences."""
        if not self._workspace_config:
            return {'error': 'Config not available'}

        prefs = self._workspace_config.update_user_preferences(user_id, **updates)
        return prefs.to_dict()

    def register_hook(
        self,
        event: str,
        callback,
        priority: int = 0,
        description: str = ""
    ) -> Optional[str]:
        """Register a hook for workspace events."""
        if not self._workspace_config:
            return None

        try:
            hook_event = HookEvent(event)
            return self._workspace_config.register_hook(
                hook_event, callback, priority, description
            )
        except ValueError:
            print(f"[SessionManager] Unknown hook event: {event}")
            return None

    def fire_hook(self, event: str, data: Dict[str, Any]):
        """Fire hooks for an event (sync version)."""
        if not self._workspace_config:
            return

        try:
            hook_event = HookEvent(event)
            self._workspace_config.fire_hook_sync(hook_event, data)
        except ValueError:
            pass

    async def fire_hook_async(self, event: str, data: Dict[str, Any]) -> List[Any]:
        """Fire hooks for an event (async version)."""
        if not self._workspace_config:
            return []

        try:
            hook_event = HookEvent(event)
            return await self._workspace_config.fire_hook(hook_event, data)
        except ValueError:
            return []

    def get_agent_config(self, agent_id: str) -> Dict[str, Any]:
        """Get configuration for a specific agent."""
        if not self._workspace_config:
            return {
                'personality': 'neutral',
                'temperature': 0.5,
                'max_tokens': 4096
            }
        return self._workspace_config.get_agent_config(agent_id)

    def reload_config(self):
        """Reload workspace configuration from disk."""
        if self._workspace_config:
            self._workspace_config.reload()
            print("[SessionManager] Workspace config reloaded")

    def update_user_presence(self, session_id: str, user_id: str, **kwargs):
        """Update user presence info (cursor, typing, etc)."""
        session = self.sessions.get(session_id)

        if not session or user_id not in session.users:
            return

        user = session.users[user_id]
        user.last_seen = datetime.utcnow().isoformat()

        if 'cursor_position' in kwargs:
            user.cursor_position = kwargs['cursor_position']
        if 'is_typing' in kwargs:
            user.is_typing = kwargs['is_typing']

    async def broadcast_to_session(self, session_id: str, event: str, data: Dict, exclude_user: Optional[str] = None):
        """Broadcast a message to all users in a session."""
        session = self.sessions.get(session_id)

        if not session:
            return

        message = json.dumps({
            'event': event,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        })

        disconnected_users = []

        for user_id, user in session.users.items():
            if exclude_user and user_id == exclude_user:
                continue

            try:
                await user.websocket.send(message)
            except Exception as e:
                print(f"[SessionManager] Error sending to user {user.name}: {e}")
                disconnected_users.append(user_id)

        # Clean up disconnected users
        for user_id in disconnected_users:
            self.leave_session(session_id, user_id)

    async def cleanup_expired_sessions(self):
        """Background task to clean up expired sessions."""
        while True:
            try:
                expired = [
                    sid for sid, session in self.sessions.items()
                    if session.is_expired()
                ]

                for session_id in expired:
                    print(f"[SessionManager] Cleaning up expired session {session_id}")
                    del self.sessions[session_id]

                # Run cleanup every 5 minutes
                await asyncio.sleep(300)

            except Exception as e:
                print(f"[SessionManager] Cleanup error: {e}")
                await asyncio.sleep(60)

    def start_cleanup_task(self):
        """Start the cleanup background task."""
        if not self.cleanup_task:
            self.cleanup_task = asyncio.create_task(self.cleanup_expired_sessions())

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        # Generate short, readable session IDs (6 characters)
        import random
        import string

        while True:
            session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            if session_id not in self.sessions:
                return session_id

    def _queue_ws_event(self, session_id: str, event_type: str, data: Dict):
        """
        Queue a WebSocket event for broadcast.

        Args:
            session_id: Session ID to broadcast to
            event_type: Event type name
            data: Event data
        """
        self.ws_event_queue.append({
            'session_id': session_id,
            'event': event_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        })

    def get_and_clear_ws_events(self) -> List[Dict]:
        """
        Get all pending WebSocket events and clear the queue.

        Returns:
            List of event dicts
        """
        events = self.ws_event_queue.copy()
        self.ws_event_queue.clear()
        return events

    def can_control_agent(self, session_id: str, user_id: str) -> bool:
        """Check if user has permission to control agents (OWNER or EDITOR)."""
        session = self.sessions.get(session_id)
        if not session or user_id not in session.users:
            return False

        user = session.users[user_id]
        return user.role in (UserRole.OWNER, UserRole.EDITOR)

    def can_send_messages(self, session_id: str, user_id: str) -> bool:
        """Check if user has permission to send messages (OWNER or EDITOR)."""
        return self.can_control_agent(session_id, user_id)

    def can_change_roles(self, session_id: str, user_id: str) -> bool:
        """Check if user has permission to change roles (OWNER only)."""
        session = self.sessions.get(session_id)
        if not session or user_id not in session.users:
            return False

        return session.users[user_id].role == UserRole.OWNER

    def change_user_role(self, session_id: str, requesting_user_id: str, target_user_id: str, new_role: str) -> bool:
        """
        Change a user's role (OWNER only).

        Args:
            session_id: Session ID
            requesting_user_id: User requesting the change
            target_user_id: User whose role to change
            new_role: New role ('owner', 'editor', or 'viewer')

        Returns:
            True if successful, False otherwise
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        # Check permission
        if not self.can_change_roles(session_id, requesting_user_id):
            print(f"[SessionManager] User {requesting_user_id} not authorized to change roles")
            return False

        # Can't change owner's role
        if target_user_id == session.owner_id:
            print(f"[SessionManager] Cannot change owner's role")
            return False

        # Validate new role
        try:
            role_enum = UserRole(new_role)
        except ValueError:
            print(f"[SessionManager] Invalid role: {new_role}")
            return False

        # Update role
        if target_user_id in session.users:
            old_role = session.users[target_user_id].role.value
            session.users[target_user_id].role = role_enum
            print(f"[SessionManager] Changed {target_user_id} role to {new_role}")

            # Update orchestrator with updated session users
            if session.orchestrator:
                session.orchestrator.update_session_users(session.users)

            # Audit log
            self._add_audit_entry(
                session_id, requesting_user_id, 'role_change',
                {'target_user_id': target_user_id, 'old_role': old_role, 'new_role': new_role}
            )

            return True

        return False

    def claim_agent_control(self, session_id: str, user_id: str, agent_id: str) -> bool:
        """
        Claim control of an agent.

        Args:
            session_id: Session ID
            user_id: User requesting control
            agent_id: Agent to control ('a', 'b', 'moderator')

        Returns:
            True if control granted, False if agent already controlled or no permission
        """
        session = self.sessions.get(session_id)
        if not session or agent_id not in session.agent_control:
            return False

        # Check permission
        if not self.can_control_agent(session_id, user_id):
            print(f"[SessionManager] User {user_id} not authorized to control agents")
            return False

        # If agent is uncontrolled or controlled by requesting user, grant control
        current_controller = session.agent_control.get(agent_id)
        if current_controller is None or current_controller == user_id:
            session.agent_control[agent_id] = user_id
            print(f"[SessionManager] User {user_id} claimed control of agent {agent_id}")

            # Audit log
            self._add_audit_entry(session_id, user_id, 'claim_control', {'agent_id': agent_id})

            return True

        return False

    def release_agent_control(self, session_id: str, user_id: str, agent_id: str) -> bool:
        """Release control of an agent."""
        session = self.sessions.get(session_id)
        if not session or agent_id not in session.agent_control:
            return False

        # Only the controller can release
        if session.agent_control.get(agent_id) == user_id:
            session.agent_control[agent_id] = None
            print(f"[SessionManager] User {user_id} released control of agent {agent_id}")

            # Audit log
            self._add_audit_entry(session_id, user_id, 'release_control', {'agent_id': agent_id})

            return True

        return False

    def handoff_agent_control(self, session_id: str, from_user_id: str, to_user_id: str, agent_id: str) -> bool:
        """
        Hand off agent control from one user to another.

        Args:
            session_id: Session ID
            from_user_id: Current controller
            to_user_id: New controller
            agent_id: Agent to transfer

        Returns:
            True if successful, False otherwise
        """
        session = self.sessions.get(session_id)
        if not session or agent_id not in session.agent_control:
            return False

        # Verify current controller
        if session.agent_control.get(agent_id) != from_user_id:
            print(f"[SessionManager] User {from_user_id} is not current controller")
            return False

        # Verify target user exists and has permission
        if to_user_id not in session.users:
            print(f"[SessionManager] Target user {to_user_id} not in session")
            return False

        if not self.can_control_agent(session_id, to_user_id):
            print(f"[SessionManager] Target user {to_user_id} cannot control agents")
            return False

        # Transfer control
        session.agent_control[agent_id] = to_user_id
        print(f"[SessionManager] Handed off {agent_id} from {from_user_id} to {to_user_id}")

        # Audit log
        self._add_audit_entry(
            session_id, from_user_id, 'handoff_control',
            {'agent_id': agent_id, 'to_user_id': to_user_id}
        )

        return True

    def acquire_document_lock(self, session_id: str, user_id: str, agent_id: str) -> bool:
        """
        Acquire a document lock (starts editing).

        Returns:
            True if lock acquired, False if already locked by someone else
        """
        session = self.sessions.get(session_id)
        if not session or agent_id not in session.document_locks:
            return False

        # Check if user has permission to edit
        if not self.can_send_messages(session_id, user_id):
            print(f"[SessionManager] User {user_id} not authorized to edit documents")
            return False

        # Check if document is already locked by someone else
        current_lock = session.document_locks.get(agent_id)
        if current_lock and current_lock != user_id:
            print(f"[SessionManager] Document {agent_id} already locked by {current_lock}")
            return False

        # Acquire lock
        session.document_locks[agent_id] = user_id
        print(f"[SessionManager] User {user_id} acquired lock on {agent_id}")

        # Audit log
        self._add_audit_entry(session_id, user_id, 'lock_acquire', {'agent_id': agent_id})

        return True

    def release_document_lock(self, session_id: str, user_id: str, agent_id: str) -> bool:
        """Release a document lock (stops editing)."""
        session = self.sessions.get(session_id)
        if not session or agent_id not in session.document_locks:
            return False

        # Only the lock holder can release
        if session.document_locks.get(agent_id) == user_id:
            session.document_locks[agent_id] = None
            print(f"[SessionManager] User {user_id} released lock on {agent_id}")

            # Audit log
            self._add_audit_entry(session_id, user_id, 'lock_release', {'agent_id': agent_id})

            return True

        return False

    def get_session_stats(self) -> Dict:
        """Get statistics about all sessions."""
        return {
            'total_sessions': len(self.sessions),
            'total_users': sum(len(s.users) for s in self.sessions.values()),
            'sessions': [
                {
                    'id': s.id,
                    'users': len(s.users),
                    'messages': len(s.messages),
                    'created_at': s.created_at
                }
                for s in self.sessions.values()
            ]
        }

    # ===== Phase 4B: MCP Inbox Tools =====

    def send_agent_message(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str,
        content: str,
        priority: str = 'medium',
        metadata: Optional[Dict] = None
    ) -> Optional[AgentMessage]:
        """
        Send message from one agent to another via inbox.

        Args:
            session_id: Session ID
            from_agent: Source agent ('prax', 'cairn', 'koda')
            to_agent: Target agent ('prax', 'cairn', 'koda')
            content: Message content
            priority: 'high', 'medium', or 'low'
            metadata: Optional metadata dict with workflow_id, task_type, etc.

        Returns:
            AgentMessage if successful, None otherwise
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        # Validate agent IDs
        valid_agents = ['prax', 'cairn', 'koda']
        if from_agent not in valid_agents or to_agent not in valid_agents:
            print(f"[SessionManager] Invalid agent ID: {from_agent} -> {to_agent}")
            return None

        # Create message
        message = AgentMessage(
            id=str(uuid.uuid4()),
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            timestamp=datetime.utcnow().isoformat(),
            priority=priority,
            read=False,
            metadata=metadata or {}
        )

        # Add to target agent's inbox
        session.agent_inboxes[to_agent].append(message)

        # Update agent workload
        session.agent_workload[to_agent]['active_tasks'] += 1

        # Audit log
        self._add_audit_entry(
            session_id,
            from_agent,  # Using from_agent as user_id for agent actions
            'agent_message_sent',
            {
                'from_agent': from_agent,
                'to_agent': to_agent,
                'priority': priority,
                'message_preview': content[:100],
                'workflow_id': metadata.get('workflow_id') if metadata else None
            },
            workflow_id=metadata.get('workflow_id') if metadata else None
        )

        print(f"[SessionManager] Agent message: {from_agent} → {to_agent} (priority: {priority})")

        # Queue WebSocket event for broadcast (will be picked up by async task)
        self._queue_ws_event(session_id, 'agent_message_sent', {
            'message_id': message.id,
            'from_agent': from_agent,
            'to_agent': to_agent,
            'priority': priority,
            'content_preview': content[:100],
            'workflow_id': metadata.get('workflow_id') if metadata else None,
            'unread_count': len([m for m in session.agent_inboxes[to_agent] if not m.read])
        })

        return message

    def check_inbox(
        self,
        session_id: str,
        agent_id: str,
        from_agent: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 10,
        workflow_id: Optional[str] = None
    ) -> List[AgentMessage]:
        """
        Check agent's inbox for messages.

        Args:
            session_id: Session ID
            agent_id: Agent checking inbox ('prax', 'cairn', 'koda')
            from_agent: Optional filter by sender
            unread_only: Only return unread messages
            limit: Max messages to return
            workflow_id: Optional filter by workflow

        Returns:
            List of AgentMessages
        """
        session = self.sessions.get(session_id)
        if not session or agent_id not in session.agent_inboxes:
            return []

        messages = session.agent_inboxes[agent_id]

        # Apply filters
        filtered = messages
        if from_agent:
            filtered = [m for m in filtered if m.from_agent == from_agent]
        if unread_only:
            filtered = [m for m in filtered if not m.read]
        if workflow_id:
            filtered = [m for m in filtered if m.metadata.get('workflow_id') == workflow_id]

        # Return most recent first, limited
        return list(reversed(filtered))[:limit]

    def mark_read(self, session_id: str, agent_id: str, message_id: str) -> bool:
        """
        Mark an agent message as read.

        Args:
            session_id: Session ID
            agent_id: Agent who read the message
            message_id: Message ID

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session or agent_id not in session.agent_inboxes:
            return False

        for msg in session.agent_inboxes[agent_id]:
            if msg.id == message_id:
                msg.read = True
                return True

        return False

    def search_messages(
        self,
        session_id: str,
        agent_id: str,
        query: str,
        from_agent: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> List[AgentMessage]:
        """
        Search agent inbox for messages matching query.

        Args:
            session_id: Session ID
            agent_id: Agent searching inbox
            query: Keyword or phrase to search
            from_agent: Optional filter by sender
            workflow_id: Optional filter by workflow
            task_type: Optional filter by task type

        Returns:
            List of matching AgentMessages
        """
        session = self.sessions.get(session_id)
        if not session or agent_id not in session.agent_inboxes:
            return []

        messages = session.agent_inboxes[agent_id]

        # Apply filters
        filtered = messages
        if from_agent:
            filtered = [m for m in filtered if m.from_agent == from_agent]
        if workflow_id:
            filtered = [m for m in filtered if m.metadata.get('workflow_id') == workflow_id]
        if task_type:
            filtered = [m for m in filtered if m.metadata.get('task_type') == task_type]

        # Search content
        query_lower = query.lower()
        results = [m for m in filtered if query_lower in m.content.lower()]

        return results

    # ===== Phase 4B: Orchestration Tools =====

    def broadcast_status_request(
        self,
        session_id: str,
        targets: List[str],
        workflow_id: str,
        request_type: str = 'progress'
    ) -> List[AgentMessage]:
        """
        Prax broadcasts status request to multiple agents.

        Args:
            session_id: Session ID
            targets: List of agent IDs to request from
            workflow_id: Workflow ID
            request_type: 'progress', 'blockers', 'eta', 'capabilities'

        Returns:
            List of sent messages
        """
        sent_messages = []

        for agent in targets:
            msg = self.send_agent_message(
                session_id,
                from_agent='prax',
                to_agent=agent,
                content=f"Status request: {request_type} for workflow {workflow_id}",
                priority='medium',
                metadata={
                    'workflow_id': workflow_id,
                    'task_type': 'status_request',
                    'request_type': request_type
                }
            )
            if msg:
                sent_messages.append(msg)

        return sent_messages

    def get_workflow_status(self, session_id: str, workflow_id: str) -> Optional[WorkflowState]:
        """
        Get current workflow state.

        Args:
            session_id: Session ID
            workflow_id: Workflow ID

        Returns:
            WorkflowState or None
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        return session.workflows.get(workflow_id)

    def create_workflow(
        self,
        session_id: str,
        workflow_id: str,
        name: str,
        assigned_agents: List[str],
        deadline: Optional[str] = None
    ) -> Optional[WorkflowState]:
        """
        Create a new workflow.

        Args:
            session_id: Session ID
            workflow_id: Unique workflow ID
            name: Workflow name
            assigned_agents: List of agent IDs
            deadline: Optional deadline (ISO format)

        Returns:
            WorkflowState or None
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        workflow = WorkflowState(
            id=workflow_id,
            name=name,
            status='active',
            assigned_agents=assigned_agents,
            deadline=deadline
        )

        session.workflows[workflow_id] = workflow

        print(f"[SessionManager] Created workflow {workflow_id}: {name}")

        # Queue WebSocket event
        self._queue_ws_event(session_id, 'workflow_created', {
            'workflow_id': workflow_id,
            'name': name,
            'assigned_agents': assigned_agents,
            'deadline': deadline
        })

        return workflow

    def set_milestone(
        self,
        session_id: str,
        workflow_id: str,
        milestone: str,
        status: str = 'in_progress',
        completion_percentage: int = 0
    ) -> bool:
        """
        Set or update a workflow milestone.

        Args:
            session_id: Session ID
            workflow_id: Workflow ID
            milestone: Milestone name
            status: 'pending', 'in_progress', 'completed', 'blocked'
            completion_percentage: 0-100

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session or workflow_id not in session.workflows:
            return False

        workflow = session.workflows[workflow_id]
        workflow.milestones[milestone] = {
            'status': status,
            'completion_percentage': completion_percentage,
            'updated_at': datetime.utcnow().isoformat()
        }

        # Audit log
        self._add_audit_entry(
            session_id,
            'system',
            'milestone_updated',
            {
                'workflow_id': workflow_id,
                'milestone': milestone,
                'status': status,
                'completion_percentage': completion_percentage
            },
            workflow_id=workflow_id
        )

        print(f"[SessionManager] Milestone updated: {milestone} → {status} ({completion_percentage}%)")

        # Queue WebSocket event
        self._queue_ws_event(session_id, 'workflow_milestone_updated', {
            'workflow_id': workflow_id,
            'milestone': milestone,
            'status': status,
            'completion_percentage': completion_percentage
        })

        return True

    def get_dependencies(self, session_id: str, workflow_id: str) -> List[str]:
        """
        Get workflow dependencies.

        Args:
            session_id: Session ID
            workflow_id: Workflow ID

        Returns:
            List of dependency workflow IDs
        """
        session = self.sessions.get(session_id)
        if not session or workflow_id not in session.workflows:
            return []

        return session.workflows[workflow_id].dependencies

    def escalate_blocker(
        self,
        session_id: str,
        blocker_description: str,
        affected_agents: List[str],
        severity: str = 'medium',
        requires_human_input: bool = False
    ) -> str:
        """
        Escalate blocker to humans via UI notification.

        Args:
            session_id: Session ID
            blocker_description: Description of blocker
            affected_agents: List of affected agent IDs
            severity: 'high', 'medium', 'low'
            requires_human_input: Whether human intervention needed

        Returns:
            Blocker ID
        """
        session = self.sessions.get(session_id)
        if not session:
            return ""

        blocker_id = str(uuid.uuid4())

        # Audit log
        self._add_audit_entry(
            session_id,
            'system',
            'blocker_escalated',
            {
                'blocker_id': blocker_id,
                'description': blocker_description,
                'affected_agents': affected_agents,
                'severity': severity,
                'requires_human_input': requires_human_input
            }
        )

        print(f"[SessionManager] Blocker escalated: {blocker_description} (severity: {severity})")

        # Queue WebSocket event
        self._queue_ws_event(session_id, 'blocker_escalated', {
            'blocker_id': blocker_id,
            'description': blocker_description,
            'affected_agents': affected_agents,
            'severity': severity,
            'requires_human_input': requires_human_input
        })

        return blocker_id

    def reassign_task(
        self,
        session_id: str,
        workflow_id: str,
        from_agent: str,
        to_agent: str,
        task_context: str,
        reason: str
    ) -> bool:
        """
        Reassign task from one agent to another.

        Args:
            session_id: Session ID
            workflow_id: Workflow ID
            from_agent: Current agent
            to_agent: New agent
            task_context: Task description
            reason: Reason for reassignment

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session or workflow_id not in session.workflows:
            return False

        # Send message to new agent
        self.send_agent_message(
            session_id,
            from_agent='prax',
            to_agent=to_agent,
            content=f"Task reassigned from {from_agent}: {task_context}\nReason: {reason}",
            priority='high',
            metadata={
                'workflow_id': workflow_id,
                'task_type': 'reassignment',
                'original_agent': from_agent
            }
        )

        # Update workload
        session.agent_workload[from_agent]['active_tasks'] -= 1
        session.agent_workload[to_agent]['active_tasks'] += 1

        print(f"[SessionManager] Task reassigned: {from_agent} → {to_agent} ({reason})")

        return True

    # ===== Phase 4B: Context Sharing Tools =====

    def share_context(
        self,
        session_id: str,
        from_agent: str,
        target: str,
        context_key: str,
        content: Any,
        workflow_id: str
    ) -> bool:
        """
        Share context/knowledge between agents.

        Args:
            session_id: Session ID
            from_agent: Agent sharing context
            target: Target agent or 'all'
            context_key: Unique context key
            content: Context content (any JSON-serializable data)
            workflow_id: Workflow ID

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        # Store in shared contexts with workflow scope
        full_key = f"{workflow_id}:{context_key}"
        session.shared_contexts[full_key] = {
            'content': content,
            'from_agent': from_agent,
            'target': target,
            'workflow_id': workflow_id,
            'created_at': datetime.utcnow().isoformat()
        }

        # Audit log
        self._add_audit_entry(
            session_id,
            from_agent,
            'context_shared',
            {
                'context_key': context_key,
                'target': target,
                'workflow_id': workflow_id
            },
            workflow_id=workflow_id
        )

        # Notify target agent(s)
        if target == 'all':
            agents = ['prax', 'cairn', 'koda']
        else:
            agents = [target]

        for agent in agents:
            if agent != from_agent:
                self.send_agent_message(
                    session_id,
                    from_agent=from_agent,
                    to_agent=agent,
                    content=f"Shared context available: {context_key}",
                    priority='medium',
                    metadata={
                        'workflow_id': workflow_id,
                        'task_type': 'context_share',
                        'context_keys': [context_key]
                    }
                )

        print(f"[SessionManager] Context shared: {context_key} by {from_agent} to {target}")

        # Queue WebSocket event
        self._queue_ws_event(session_id, 'context_shared', {
            'context_key': context_key,
            'from_agent': from_agent,
            'target': target,
            'workflow_id': workflow_id
        })

        return True

    def get_shared_context(
        self,
        session_id: str,
        context_key: str,
        workflow_id: str
    ) -> Optional[Dict]:
        """
        Retrieve shared context.

        Args:
            session_id: Session ID
            context_key: Context key
            workflow_id: Workflow ID

        Returns:
            Context data or None
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        full_key = f"{workflow_id}:{context_key}"
        return session.shared_contexts.get(full_key)

    def list_shared_contexts(self, session_id: str, workflow_id: str) -> List[str]:
        """
        List all shared contexts for a workflow.

        Args:
            session_id: Session ID
            workflow_id: Workflow ID

        Returns:
            List of context keys
        """
        session = self.sessions.get(session_id)
        if not session:
            return []

        prefix = f"{workflow_id}:"
        return [
            key.split(':', 1)[1]
            for key in session.shared_contexts.keys()
            if key.startswith(prefix)
        ]

    # ===== Phase 4B: Agent Discovery & Coordination =====

    def get_agent_capabilities(self, session_id: str, agent_id: str) -> List[str]:
        """
        Get agent's capabilities.

        Args:
            session_id: Session ID
            agent_id: Agent ID

        Returns:
            List of capability strings
        """
        session = self.sessions.get(session_id)
        if not session:
            return []

        return session.agent_capabilities.get(agent_id, [])

    def get_agent_workload(self, session_id: str, agent_id: str) -> Dict:
        """
        Get agent's current workload status.

        Args:
            session_id: Session ID
            agent_id: Agent ID

        Returns:
            Workload dict with active_tasks and status
        """
        session = self.sessions.get(session_id)
        if not session:
            return {}

        return session.agent_workload.get(agent_id, {})

    def check_timeline_conflicts(
        self,
        session_id: str,
        agent_id: str,
        new_task: Dict
    ) -> bool:
        """
        Check if agent has timeline conflicts for new task.

        Args:
            session_id: Session ID
            agent_id: Agent ID
            new_task: Dict with 'estimated_duration', 'deadline', 'priority'

        Returns:
            True if conflict exists
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        workload = session.agent_workload.get(agent_id, {})

        # Simple conflict detection: if agent has more than 3 active tasks, flag conflict
        # In production, would parse deadlines and check actual timeline
        return workload.get('active_tasks', 0) >= 3

    def set_deadline(
        self,
        session_id: str,
        workflow_id: str,
        task_id: str,
        deadline: str
    ) -> bool:
        """
        Set deadline for a task in workflow.

        Args:
            session_id: Session ID
            workflow_id: Workflow ID
            task_id: Task ID
            deadline: ISO format datetime string

        Returns:
            True if successful
        """
        session = self.sessions.get(session_id)
        if not session or workflow_id not in session.workflows:
            return False

        workflow = session.workflows[workflow_id]

        # Store in workflow metadata
        if not hasattr(workflow, 'task_deadlines'):
            workflow.task_deadlines = {}

        workflow.task_deadlines[task_id] = deadline

        print(f"[SessionManager] Deadline set for {task_id}: {deadline}")

        return True

    # ===== Phase 4C.1: Canvas Section Management =====

    def create_canvas_section(
        self,
        session_id: str,
        section_name: str,
        owner: Optional[str] = None,
        initial_content: str = ""
    ) -> bool:
        """
        Create a new canvas section.

        Args:
            session_id: Session ID
            section_name: Unique section name
            owner: Optional owner agent ID (cairn, koda) or None for shared
            initial_content: Optional initial content

        Returns:
            True if created, False if section exists or session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        if section_name in session.canvas_sections:
            print(f"[SessionManager] Canvas section '{section_name}' already exists")
            return False

        session.canvas_sections[section_name] = {
            'content': initial_content,
            'owner': owner,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'version': 1,
            'history': [{
                'version': 1,
                'content': initial_content,
                'updated_by': owner or 'system',
                'timestamp': datetime.utcnow().isoformat()
            }]
        }

        print(f"[SessionManager] Canvas section created: {section_name} (owner: {owner})")

        # Queue WebSocket event
        self._queue_ws_event(session_id, 'canvas_section_created', {
            'section_name': section_name,
            'owner': owner
        })

        return True

    def update_canvas_section(
        self,
        session_id: str,
        section_name: str,
        content: str,
        updated_by: str
    ) -> bool:
        """
        Update content of a canvas section.

        Args:
            session_id: Session ID
            section_name: Section name to update
            content: New content
            updated_by: Agent or user ID making the update

        Returns:
            True if updated, False if section not found or permission denied
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        if section_name not in session.canvas_sections:
            # Auto-create section if it doesn't exist
            self.create_canvas_section(session_id, section_name, updated_by)

        section = session.canvas_sections[section_name]

        # Check ownership (if section has owner, only owner can update)
        if section['owner'] and section['owner'] != updated_by:
            print(f"[SessionManager] Permission denied: {updated_by} cannot update section owned by {section['owner']}")
            return False

        # Update section
        section['content'] = content
        section['updated_at'] = datetime.utcnow().isoformat()
        section['version'] += 1

        # Add to history (keep last 10 versions)
        section['history'].append({
            'version': section['version'],
            'content': content[:1000] + '...' if len(content) > 1000 else content,  # Truncate for history
            'updated_by': updated_by,
            'timestamp': section['updated_at']
        })
        if len(section['history']) > 10:
            section['history'] = section['history'][-10:]

        # Audit log
        self._add_audit_entry(
            session_id,
            updated_by,
            'canvas_updated',
            {
                'section_name': section_name,
                'version': section['version'],
                'content_length': len(content)
            }
        )

        print(f"[SessionManager] Canvas section updated: {section_name} (v{section['version']})")

        # Queue WebSocket event
        self._queue_ws_event(session_id, 'canvas_section_updated', {
            'section_name': section_name,
            'updated_by': updated_by,
            'version': section['version'],
            'content_preview': content[:200] if content else ''
        })

        return True

    def get_canvas_section(
        self,
        session_id: str,
        section_name: str
    ) -> Optional[Dict]:
        """
        Get canvas section content.

        Args:
            session_id: Session ID
            section_name: Section name

        Returns:
            Section dict or None
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        return session.canvas_sections.get(section_name)

    def list_canvas_sections(self, session_id: str) -> List[Dict]:
        """
        List all canvas sections for a session.

        Args:
            session_id: Session ID

        Returns:
            List of section info dicts
        """
        session = self.sessions.get(session_id)
        if not session:
            return []

        return [
            {
                'name': name,
                'owner': info['owner'],
                'updated_at': info['updated_at'],
                'version': info['version'],
                'content_length': len(info['content'])
            }
            for name, info in session.canvas_sections.items()
        ]

    def assign_canvas_section(
        self,
        session_id: str,
        section_name: str,
        agent_id: str
    ) -> bool:
        """
        Assign ownership of a canvas section to an agent.

        Args:
            session_id: Session ID
            section_name: Section name
            agent_id: Agent to assign ('cairn' or 'koda')

        Returns:
            True if assigned
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        if section_name not in session.canvas_sections:
            # Create section with owner
            return self.create_canvas_section(session_id, section_name, agent_id)

        session.canvas_sections[section_name]['owner'] = agent_id
        print(f"[SessionManager] Canvas section '{section_name}' assigned to {agent_id}")

        self._queue_ws_event(session_id, 'canvas_section_assigned', {
            'section_name': section_name,
            'agent_id': agent_id
        })

        return True

    def get_canvas_section_history(
        self,
        session_id: str,
        section_name: str
    ) -> List[Dict]:
        """
        Get version history for a canvas section.

        Args:
            session_id: Session ID
            section_name: Section name

        Returns:
            List of version history entries
        """
        session = self.sessions.get(session_id)
        if not session or section_name not in session.canvas_sections:
            return []

        return session.canvas_sections[section_name].get('history', [])

    # ===== Phase 4C.1: Task Delegation Integration =====

    def register_delegated_task(
        self,
        session_id: str,
        task_id: str,
        task_info: Dict
    ) -> bool:
        """
        Register a delegated task in the session.

        Args:
            session_id: Session ID
            task_id: Task ID
            task_info: Task information dict

        Returns:
            True if registered
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.delegated_tasks[task_id] = task_info

        # Update agent workload
        to_agent = task_info.get('to_agent')
        if to_agent in session.agent_workload:
            session.agent_workload[to_agent]['active_tasks'] += 1
            session.agent_workload[to_agent]['status'] = 'working'

        # Audit log
        self._add_audit_entry(
            session_id,
            task_info.get('from_agent', 'prax'),
            'task_delegated',
            {
                'task_id': task_id,
                'to_agent': to_agent,
                'description': task_info.get('description', '')[:100]
            }
        )

        print(f"[SessionManager] Task registered: {task_id}")
        return True

    def update_delegated_task(
        self,
        session_id: str,
        task_id: str,
        updates: Dict
    ) -> bool:
        """
        Update a delegated task in the session.

        Args:
            session_id: Session ID
            task_id: Task ID
            updates: Updates to apply

        Returns:
            True if updated
        """
        session = self.sessions.get(session_id)
        if not session or task_id not in session.delegated_tasks:
            return False

        session.delegated_tasks[task_id].update(updates)

        # If task completed/failed, update workload
        status = updates.get('status')
        if status in ['completed', 'failed', 'cancelled']:
            to_agent = session.delegated_tasks[task_id].get('to_agent')
            if to_agent in session.agent_workload:
                session.agent_workload[to_agent]['active_tasks'] = max(
                    0,
                    session.agent_workload[to_agent]['active_tasks'] - 1
                )
                if session.agent_workload[to_agent]['active_tasks'] == 0:
                    session.agent_workload[to_agent]['status'] = 'idle'

        return True

    def get_delegated_task(
        self,
        session_id: str,
        task_id: str
    ) -> Optional[Dict]:
        """
        Get a delegated task by ID.

        Args:
            session_id: Session ID
            task_id: Task ID

        Returns:
            Task info dict or None
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        return session.delegated_tasks.get(task_id)

    def list_delegated_tasks(
        self,
        session_id: str,
        agent_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        List delegated tasks for a session.

        Args:
            session_id: Session ID
            agent_id: Optional filter by agent
            status: Optional filter by status

        Returns:
            List of task info dicts
        """
        session = self.sessions.get(session_id)
        if not session:
            return []

        tasks = list(session.delegated_tasks.values())

        if agent_id:
            tasks = [t for t in tasks if t.get('to_agent') == agent_id]

        if status:
            tasks = [t for t in tasks if t.get('status') == status]

        return tasks


    # ===== Phase: Storage Integration - Export Methods =====

    def export_session_to_file(self, session_id: str) -> Optional[str]:
        """
        Export full session data to JSON file for storage.

        Args:
            session_id: Session ID to export

        Returns:
            Path to exported file, or None if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            print(f"[SessionManager] Cannot export: session {session_id} not found")
            return None

        # Create export directory
        export_dir = Path.home() / '.claude' / 'workspace_sessions'
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"session_{session_id}_{timestamp}.json"
        filepath = export_dir / filename

        # Build export data
        export_data = {
            'session_id': session.id,
            'created_at': session.created_at,
            'expires_at': session.expires_at,
            'exported_at': datetime.utcnow().isoformat(),
            'owner_id': session.owner_id,
            'participants': [
                {
                    'id': user.id,
                    'name': user.name,
                    'role': user.role.value,
                    'joined_at': user.joined_at,
                    'avatar_color': user.avatar_color
                }
                for user in session.users.values()
            ],
            'messages': [msg.to_dict() for msg in session.messages],
            'message_count': len(session.messages),
            'canvas_sections': session.canvas_sections,
            'delegated_tasks': session.delegated_tasks,
            'workflows': {wid: wf.to_dict() for wid, wf in session.workflows.items()},
            'agent_inboxes': {
                agent: [msg.to_dict() for msg in msgs]
                for agent, msgs in session.agent_inboxes.items()
            },
            'shared_contexts': session.shared_contexts,
            'audit_log': [entry.to_dict() for entry in session.audit_log],
            'audit_log_count': len(session.audit_log),
            'demo_mode': session.demo_mode,
            'demo_title': session.demo_title
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            print(f"[SessionManager] Exported session {session_id} to {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[SessionManager] Error exporting session: {e}")
            return None

    def list_exported_sessions(self, limit: int = 50) -> List[Dict]:
        """
        List all exported workspace sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session metadata dicts
        """
        export_dir = Path.home() / '.claude' / 'workspace_sessions'
        if not export_dir.exists():
            return []

        sessions = []
        for filepath in sorted(export_dir.glob('session_*.json'), reverse=True)[:limit]:
            try:
                stat = filepath.stat()
                # Read header info only
                with open(filepath, 'r') as f:
                    data = json.load(f)

                sessions.append({
                    'filename': filepath.name,
                    'session_id': data.get('session_id'),
                    'created_at': data.get('created_at'),
                    'exported_at': data.get('exported_at'),
                    'message_count': data.get('message_count', 0),
                    'participant_count': len(data.get('participants', [])),
                    'participants': [p.get('name') for p in data.get('participants', [])],
                    'file_size': stat.st_size,
                    'file_modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except Exception as e:
                print(f"[SessionManager] Error reading {filepath}: {e}")
                continue

        return sessions

    def get_exported_session(self, session_id: str) -> Optional[Dict]:
        """
        Get full data for an exported session.

        Args:
            session_id: Session ID to retrieve

        Returns:
            Full session data dict, or None
        """
        export_dir = Path.home() / '.claude' / 'workspace_sessions'
        if not export_dir.exists():
            return None

        # Find matching session file (most recent if multiple)
        matching = sorted(export_dir.glob(f'session_{session_id}_*.json'), reverse=True)
        if not matching:
            return None

        try:
            with open(matching[0], 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[SessionManager] Error reading session {session_id}: {e}")
            return None

    def get_workspace_storage_stats(self) -> Dict:
        """
        Get statistics about workspace session storage.

        Returns:
            Stats dict with counts, sizes, etc.
        """
        export_dir = Path.home() / '.claude' / 'workspace_sessions'

        stats = {
            'total_sessions': 0,
            'total_size_bytes': 0,
            'total_messages': 0,
            'oldest_session': None,
            'newest_session': None,
            'path': str(export_dir)
        }

        if not export_dir.exists():
            return stats

        sessions = []
        for filepath in export_dir.glob('session_*.json'):
            try:
                stat = filepath.stat()
                stats['total_sessions'] += 1
                stats['total_size_bytes'] += stat.st_size

                with open(filepath, 'r') as f:
                    data = json.load(f)
                stats['total_messages'] += data.get('message_count', 0)

                sessions.append({
                    'created_at': data.get('created_at'),
                    'exported_at': data.get('exported_at')
                })
            except:
                continue

        if sessions:
            sessions.sort(key=lambda x: x.get('created_at', ''))
            stats['oldest_session'] = sessions[0].get('created_at')
            stats['newest_session'] = sessions[-1].get('created_at')

        return stats

    def search_exported_sessions(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search across exported workspace sessions.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching session/message results
        """
        export_dir = Path.home() / '.claude' / 'workspace_sessions'
        if not export_dir.exists():
            return []

        query_lower = query.lower()
        results = []

        for filepath in sorted(export_dir.glob('session_*.json'), reverse=True):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)

                # Search in messages
                for msg in data.get('messages', []):
                    content = msg.get('content', '')
                    if query_lower in content.lower():
                        results.append({
                            'type': 'message',
                            'session_id': data.get('session_id'),
                            'filename': filepath.name,
                            'message_id': msg.get('id'),
                            'content_preview': content[:200],
                            'timestamp': msg.get('timestamp'),
                            'user_id': msg.get('user_id'),
                            'agent_id': msg.get('agent_id')
                        })

                        if len(results) >= limit:
                            return results

                # Search in canvas sections
                for section_name, section_data in data.get('canvas_sections', {}).items():
                    content = section_data.get('content', '')
                    if query_lower in content.lower() or query_lower in section_name.lower():
                        results.append({
                            'type': 'canvas',
                            'session_id': data.get('session_id'),
                            'filename': filepath.name,
                            'section_name': section_name,
                            'content_preview': content[:200],
                            'owner': section_data.get('owner'),
                            'updated_at': section_data.get('updated_at')
                        })

                        if len(results) >= limit:
                            return results

            except Exception as e:
                continue

        return results

    def delete_exported_session(self, filename: str) -> bool:
        """
        Delete an exported session file.

        Args:
            filename: Filename to delete

        Returns:
            True if deleted successfully
        """
        export_dir = Path.home() / '.claude' / 'workspace_sessions'
        filepath = export_dir / filename

        # Security: ensure file is in expected directory
        if not filepath.parent.resolve() == export_dir.resolve():
            print(f"[SessionManager] Security: attempted path traversal with {filename}")
            return False

        if not filepath.exists():
            return False

        try:
            filepath.unlink()
            print(f"[SessionManager] Deleted exported session: {filename}")
            return True
        except Exception as e:
            print(f"[SessionManager] Error deleting {filename}: {e}")
            return False

    def get_workspace_timeline_items(self, limit: int = 100) -> List[Dict]:
        """
        Get workspace sessions formatted for timeline display.

        Args:
            limit: Max items

        Returns:
            List of timeline-formatted items
        """
        sessions = self.list_exported_sessions(limit=limit)
        timeline_items = []

        for session in sessions:
            timeline_items.append({
                'id': f"workspace_{session['session_id']}",
                'type': 'workspace_session',
                'title': f"Workspace Session ({session['participant_count']} participants)",
                'preview': f"{session['message_count']} messages, participants: {', '.join(session['participants'][:3])}",
                'timestamp': session.get('created_at'),
                'source': 'workspaceSessions',
                'metadata': {
                    'session_id': session['session_id'],
                    'filename': session['filename'],
                    'message_count': session['message_count'],
                    'participants': session['participants']
                }
            })

        return timeline_items


# Global session manager instance
session_manager = WorkspaceSessionManager()
