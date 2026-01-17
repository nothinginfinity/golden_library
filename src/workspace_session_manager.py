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
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

# Import AgentOrchestrator for per-session agent management
try:
    from agent_orchestrator import AgentOrchestrator
except ImportError:
    AgentOrchestrator = None
    print("[WorkspaceSessionManager] Warning: AgentOrchestrator not available")


class UserRole(Enum):
    """User roles in a session."""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class AuditEntry:
    """Represents an audit log entry."""
    id: str
    session_id: str
    timestamp: str
    user_id: str
    action: str  # 'join', 'leave', 'message', 'claim_control', 'release_control', 'role_change', 'lock_acquire', 'lock_release'
    details: Dict[str, Any] = field(default_factory=dict)

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
            'audit_log': [entry.to_dict() for entry in self.audit_log]
            # orchestrator excluded (not JSON serializable)
        }

    def is_expired(self) -> bool:
        """Check if session has expired."""
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.utcnow() > expires


class WorkspaceSessionManager:
    """Manages all workspace sessions."""

    def __init__(self, session_duration_hours: int = 24):
        self.sessions: Dict[str, WorkspaceSession] = {}
        self.session_duration_hours = session_duration_hours
        self.cleanup_task = None

    def _add_audit_entry(self, session_id: str, user_id: str, action: str, details: Dict[str, Any] = None):
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
            details=details or {}
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

        # Initialize AgentOrchestrator for this session
        if AgentOrchestrator:
            try:
                session.orchestrator = AgentOrchestrator(session_users=session.users)
                print(f"[SessionManager] Initialized AgentOrchestrator for session {session_id}")
            except Exception as e:
                print(f"[SessionManager] Warning: Could not initialize orchestrator: {e}")

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

        # Delete session if no users left
        if not session.users:
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

        return message

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


# Global session manager instance
session_manager = WorkspaceSessionManager()
