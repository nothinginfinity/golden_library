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


class UserRole(Enum):
    """User roles in a session."""
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


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

    def to_dict(self):
        """Convert to dict for JSON serialization (excluding websocket)."""
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role.value,
            'joined_at': self.joined_at,
            'last_seen': self.last_seen,
            'cursor_position': self.cursor_position,
            'is_typing': self.is_typing
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

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'owner_id': self.owner_id,
            'users': {uid: user.to_dict() for uid, user in self.users.items()},
            'messages': [msg.to_dict() for msg in self.messages],
            'agent_contexts': self.agent_contexts,
            'documents': self.documents
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

        return session

    def leave_session(self, session_id: str, user_id: str):
        """User leaves a session."""
        session = self.sessions.get(session_id)

        if not session:
            return

        if user_id in session.users:
            user_name = session.users[user_id].name
            del session.users[user_id]
            print(f"[SessionManager] User {user_name} left session {session_id}")

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

        message = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            role=role,
            content=content
        )

        session.messages.append(message)

        # Also add to agent context if it's an agent message
        if agent_id and agent_id in session.agent_contexts:
            session.agent_contexts[agent_id].append({
                'role': role,
                'content': content
            })

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
