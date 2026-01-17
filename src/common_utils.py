#!/usr/bin/env python3
"""
Common Utilities for Phase 4C

Shared utilities to reduce code duplication:
- Session validation helpers
- Error response formatting
- JSON serialization helpers
- Audit log helpers
- Permission checking
"""

from typing import Optional, Dict, Any, Callable, TypeVar, Tuple
from functools import wraps
import json
import uuid
from datetime import datetime

# Import error codes
try:
    from error_codes import (
        make_error_response, session_not_found, db_not_initialized,
        internal_error, HAS_ERROR_CODES
    )
except ImportError:
    HAS_ERROR_CODES = False
    def make_error_response(code, details=None, **kwargs):
        return {'error': details or code}
    def session_not_found(session_id=None):
        return {'error': 'Session not found'}
    def db_not_initialized():
        return {'error': 'Database not initialized'}
    def internal_error(details=None):
        return {'error': details or 'Internal error'}


T = TypeVar('T')


class SessionValidator:
    """
    Helper class for validating sessions and handling common patterns.

    Usage:
        validator = SessionValidator(session_manager)
        session, error = validator.require_session(session_id)
        if error:
            return error
        # Use session...
    """

    def __init__(self, session_manager):
        self.session_manager = session_manager

    def get_session(self, session_id: str):
        """Get session by ID, returns None if not found."""
        return self.session_manager.sessions.get(session_id)

    def require_session(self, session_id: str) -> Tuple[Any, Optional[Dict]]:
        """
        Validate session exists.

        Returns:
            (session, None) if valid
            (None, error_dict) if invalid
        """
        session = self.get_session(session_id)
        if not session:
            return (None, session_not_found(session_id))
        return (session, None)

    def require_active_session(self, session_id: str) -> Tuple[Any, Optional[Dict]]:
        """
        Validate session exists and is active.

        Returns:
            (session, None) if valid and active
            (None, error_dict) if invalid or inactive
        """
        session, error = self.require_session(session_id)
        if error:
            return (None, error)

        if hasattr(session, 'is_active') and not session.is_active:
            return (None, make_error_response("E002_SESSION_EXPIRED", session_id))

        return (session, None)

    def require_user_in_session(
        self,
        session_id: str,
        user_id: str
    ) -> Tuple[Any, Optional[Dict]]:
        """
        Validate session exists and user is a participant.

        Returns:
            (session, None) if valid
            (None, error_dict) if invalid
        """
        session, error = self.require_session(session_id)
        if error:
            return (None, error)

        if hasattr(session, 'participants'):
            if user_id not in session.participants:
                return (None, make_error_response(
                    "E003_SESSION_FULL",
                    f"User {user_id} not in session"
                ))

        return (session, None)


def require_session(session_manager, session_id: str) -> Tuple[Any, Optional[Dict]]:
    """
    Standalone function to validate session exists.

    Usage:
        session, error = require_session(self, session_id)
        if error:
            return error
    """
    session = session_manager.sessions.get(session_id)
    if not session:
        return (None, session_not_found(session_id))
    return (session, None)


def require_db(session_manager) -> Tuple[Any, Optional[Dict]]:
    """
    Validate database is initialized.

    Usage:
        db, error = require_db(self)
        if error:
            return error
    """
    if not hasattr(session_manager, '_conversation_db') or not session_manager._conversation_db:
        return (None, db_not_initialized())
    return (session_manager._conversation_db, None)


def safe_json_serialize(obj: Any, default_handler: Callable = None) -> str:
    """
    Safely serialize object to JSON with default handlers.

    Args:
        obj: Object to serialize
        default_handler: Optional custom handler for non-serializable types

    Returns:
        JSON string
    """
    def default(o):
        if default_handler:
            try:
                return default_handler(o)
            except (TypeError, ValueError):
                pass

        if hasattr(o, 'to_dict'):
            return o.to_dict()
        if hasattr(o, '__dict__'):
            return o.__dict__
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, (set, frozenset)):
            return list(o)

        return str(o)

    return json.dumps(obj, default=default)


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = str(uuid.uuid4())[:12]
    return f"{prefix}_{uid}" if prefix else uid


def create_audit_entry(
    action: str,
    session_id: str,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    details: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Create a standardized audit log entry.

    Args:
        action: Action being audited
        session_id: Session ID
        user_id: Optional user ID
        agent_id: Optional agent ID
        details: Optional additional details

    Returns:
        Audit entry dict
    """
    return {
        'id': generate_id('audit'),
        'timestamp': datetime.utcnow().isoformat(),
        'action': action,
        'session_id': session_id,
        'user_id': user_id,
        'agent_id': agent_id,
        'details': details or {}
    }


def validate_agent_id(agent_id: str) -> bool:
    """Check if agent ID is valid."""
    valid_agents = {'prax', 'cairn', 'koda'}
    return agent_id.lower() in valid_agents


def validate_tool_name(tool_name: str) -> bool:
    """Check if tool name is valid."""
    # Could be extended to check against registered tools
    return bool(tool_name) and len(tool_name) < 100


class Timer:
    """Simple context manager for timing operations."""

    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration_ms = 0

    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, *args):
        self.end_time = datetime.utcnow()
        delta = self.end_time - self.start_time
        self.duration_ms = delta.total_seconds() * 1000

    @property
    def elapsed_ms(self) -> float:
        if self.end_time:
            return self.duration_ms
        delta = datetime.utcnow() - self.start_time
        return delta.total_seconds() * 1000


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to max length with suffix."""
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def deep_merge(base: Dict, updates: Dict) -> Dict:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        updates: Updates to merge in

    Returns:
        Merged dictionary (new dict, base is not modified)
    """
    result = base.copy()

    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


if __name__ == "__main__":
    # Test utilities
    print("Testing common utilities...")

    # Test ID generation
    print(f"Generated ID: {generate_id('test')}")

    # Test audit entry
    entry = create_audit_entry("test_action", "sess_123", agent_id="koda")
    print(f"Audit entry: {entry}")

    # Test timer
    import time
    with Timer("test_op") as t:
        time.sleep(0.1)
    print(f"Timer: {t.duration_ms:.2f}ms")

    # Test truncate
    print(f"Truncated: {truncate_string('Hello World this is a long string', 20)}")

    # Test deep merge
    base = {'a': 1, 'b': {'c': 2, 'd': 3}}
    updates = {'b': {'c': 10, 'e': 5}, 'f': 6}
    print(f"Deep merge: {deep_merge(base, updates)}")

    print("\n✓ All utility tests passed!")
