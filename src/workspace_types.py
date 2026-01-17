#!/usr/bin/env python3
"""
Type Definitions for Phase 4C

Central type definitions to improve code quality and IDE support.
"""

from typing import (
    TypedDict, Optional, List, Dict, Any,
    Callable, Awaitable, Union, Literal
)
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


# ========== Session Types ==========

class UserRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class MessageDict(TypedDict, total=False):
    """Dictionary representation of a message."""
    id: str
    session_id: str
    user_id: str
    agent_id: Optional[str]
    role: str
    content: str
    timestamp: str
    mentions: List[str]


class SessionDict(TypedDict, total=False):
    """Dictionary representation of a session."""
    id: str
    created_at: str
    owner_id: str
    participants: Dict[str, str]
    messages: List[MessageDict]
    demo_mode: bool
    is_active: bool


# ========== Agent Types ==========

AgentId = Literal["prax", "cairn", "koda"]


class AgentConfig(TypedDict, total=False):
    """Configuration for an agent."""
    id: AgentId
    name: str
    role: str
    system_prompt: str
    tools_allowed: List[str]
    model: str
    temperature: float


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class TaskDict(TypedDict, total=False):
    """Dictionary representation of a delegated task."""
    id: str
    description: str
    from_agent: AgentId
    to_agent: AgentId
    status: str
    priority: str
    canvas_section: Optional[str]
    created_at: str
    completed_at: Optional[str]


# ========== Canvas Types ==========

class SectionType(str, Enum):
    MARKDOWN = "markdown"
    CODE = "code"
    DIAGRAM = "diagram"
    JSON = "json"


class EditOperation(str, Enum):
    REPLACE = "replace"
    INSERT = "insert"
    DELETE = "delete"


class CanvasSectionDict(TypedDict, total=False):
    """Dictionary representation of a canvas section."""
    name: str
    section_type: str
    content: str
    owner: Optional[str]
    version: int
    locked_by: Optional[str]


class CanvasDocumentDict(TypedDict, total=False):
    """Dictionary representation of a canvas document."""
    id: str
    session_id: str
    title: str
    sections: Dict[str, CanvasSectionDict]
    created_at: str
    updated_at: str


# ========== Tool Types ==========

class ToolCategory(str, Enum):
    LLM = "llm"
    WEB = "web"
    CODE = "code"
    FILE = "file"
    SYSTEM = "system"


class ToolResultDict(TypedDict, total=False):
    """Dictionary representation of a tool result."""
    success: bool
    result: Any
    error: Optional[str]
    duration_ms: float
    tool_name: str
    agent_id: str


class ToolPermissions(TypedDict, total=False):
    """Tool permissions for an agent."""
    allowed: List[str]
    denied: List[str]
    rate_limit: Optional[int]


# ========== Error Types ==========

class ErrorResponse(TypedDict):
    """Standardized error response."""
    error: bool
    code: str
    message: str
    category: str
    retryable: bool
    request_id: str
    retry_after: Optional[int]


# ========== WebSocket Types ==========

class WSMessage(TypedDict, total=False):
    """WebSocket message structure."""
    type: str
    data: Dict[str, Any]
    request_id: Optional[str]


class WSResponse(TypedDict, total=False):
    """WebSocket response structure."""
    type: str
    success: bool
    error: Optional[bool]
    code: Optional[str]
    message: Optional[str]
    data: Dict[str, Any]


# ========== Demo Types ==========

class EventType(str, Enum):
    MESSAGE = "message"
    AGENT_RESPONSE = "agent_response"
    TOOL_CALL = "tool_call"
    DELEGATION = "delegation"
    CANVAS_EDIT = "canvas_edit"
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"
    HIGHLIGHT = "highlight"


class RecordingDict(TypedDict, total=False):
    """Dictionary representation of a demo recording."""
    id: str
    session_id: str
    title: str
    started_at: str
    ended_at: Optional[str]
    duration_ms: int
    event_count: int
    highlights: List[Dict]


# ========== Database Types ==========

class StoredMessageDict(TypedDict, total=False):
    """Message as stored in database."""
    id: str
    session_id: str
    user_id: str
    agent_id: Optional[str]
    role: str
    content: str
    timestamp: str
    mentions: List[str]
    workspace_id: Optional[str]


class SessionSummaryDict(TypedDict, total=False):
    """Summary of a session for context recovery."""
    session_id: str
    workspace_id: Optional[str]
    created_at: str
    last_activity: str
    message_count: int
    participants: List[str]
    agents_used: List[str]
    key_topics: List[str]
    decisions: List[str]


# ========== Handler Types ==========

# Type for async WebSocket handlers
WSHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

# Type for hook handlers
HookHandler = Callable[[str, Dict[str, Any]], None]

# Type for event handlers
EventHandler = Callable[[EventType, Dict[str, Any]], None]


# ========== Utility Functions ==========

def validate_agent_id(agent_id: str) -> bool:
    """Check if agent ID is valid."""
    return agent_id.lower() in ('prax', 'cairn', 'koda')


def validate_session_id(session_id: str) -> bool:
    """Check if session ID format is valid."""
    return bool(session_id) and len(session_id) >= 6


if __name__ == "__main__":
    # Test type validation
    print("Type definitions loaded successfully")
    print(f"Valid agents: {list(AgentId.__args__)}")
    print(f"Task statuses: {[s.value for s in TaskStatus]}")
    print(f"Edit operations: {[e.value for e in EditOperation]}")
