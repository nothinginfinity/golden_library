#!/usr/bin/env python3
"""
WebSocket Handler Helpers for Phase 4C

Reduces boilerplate in WebSocket message handlers:
- Standardized message routing
- Error response formatting
- Request validation
- Async handler wrappers
"""

from typing import Optional, Dict, Any, Callable, Awaitable
from functools import wraps
import json
import traceback

# Import error codes
try:
    from error_codes import make_error_response, internal_error
    HAS_ERROR_CODES = True
except ImportError:
    HAS_ERROR_CODES = False
    def make_error_response(code, details=None, **kwargs):
        return {'error': details or code}
    def internal_error(details=None):
        return {'error': details or 'Internal error'}


def ws_error(code: str, message: str, request_id: str = None) -> Dict[str, Any]:
    """Create a WebSocket error response."""
    response = {
        'type': 'error',
        'error': True,
        'code': code,
        'message': message
    }
    if request_id:
        response['request_id'] = request_id
    return response


def ws_success(data: Dict[str, Any], msg_type: str = 'response') -> Dict[str, Any]:
    """Create a WebSocket success response."""
    return {
        'type': msg_type,
        'success': True,
        **data
    }


def validate_ws_message(
    data: Dict[str, Any],
    required_fields: list,
    optional_fields: list = None
) -> Optional[Dict[str, Any]]:
    """
    Validate WebSocket message has required fields.

    Args:
        data: Message data
        required_fields: List of required field names
        optional_fields: List of optional field names (for documentation)

    Returns:
        Error dict if validation fails, None if valid
    """
    missing = [f for f in required_fields if f not in data]
    if missing:
        return ws_error(
            'E400_MISSING_FIELDS',
            f"Missing required fields: {', '.join(missing)}"
        )
    return None


def ws_handler(required_fields: list = None, optional_fields: list = None):
    """
    Decorator for WebSocket message handlers.

    Provides:
    - Field validation
    - Error handling with traceback logging
    - Standardized response formatting

    Usage:
        @ws_handler(required_fields=['session_id', 'content'])
        async def handle_send_message(self, data):
            # data is validated to have session_id and content
            ...
            return {'message_id': msg.id}
    """
    required = required_fields or []

    def decorator(func: Callable[..., Awaitable[Dict]]):
        @wraps(func)
        async def wrapper(self, data: Dict[str, Any], *args, **kwargs):
            # Validate required fields
            validation_error = validate_ws_message(data, required, optional_fields)
            if validation_error:
                return validation_error

            try:
                result = await func(self, data, *args, **kwargs)

                # If result is already formatted, return as-is
                if isinstance(result, dict) and ('error' in result or 'type' in result):
                    return result

                # Wrap success response
                return ws_success(result)

            except Exception as e:
                # Log the error with traceback
                print(f"[WS Handler Error] {func.__name__}: {e}")
                traceback.print_exc()

                return ws_error(
                    'E500_INTERNAL_ERROR',
                    str(e),
                    request_id=data.get('request_id')
                )

        return wrapper
    return decorator


class WSMessageRouter:
    """
    Route WebSocket messages to appropriate handlers.

    Usage:
        router = WSMessageRouter()

        @router.handler('send_message')
        async def handle_send(data):
            ...

        # In WebSocket handler:
        result = await router.route(message_type, data)
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def handler(self, message_type: str, required_fields: list = None):
        """
        Register a handler for a message type.

        Args:
            message_type: Type string to match
            required_fields: Fields required in message data
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(data: Dict[str, Any], *args, **kwargs):
                if required_fields:
                    validation_error = validate_ws_message(data, required_fields)
                    if validation_error:
                        return validation_error

                try:
                    return await func(data, *args, **kwargs)
                except Exception as e:
                    print(f"[WSRouter Error] {message_type}: {e}")
                    traceback.print_exc()
                    return ws_error('E500_INTERNAL_ERROR', str(e))

            self._handlers[message_type] = wrapper
            return func

        return decorator

    async def route(self, message_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Route a message to its handler."""
        handler = self._handlers.get(message_type)
        if not handler:
            return ws_error(
                'E404_UNKNOWN_MESSAGE_TYPE',
                f"Unknown message type: {message_type}"
            )
        return await handler(data)

    def list_handlers(self) -> list:
        """List all registered message types."""
        return list(self._handlers.keys())


def broadcast_event(
    session_manager,
    session_id: str,
    event_type: str,
    data: Dict[str, Any],
    exclude_user: str = None
):
    """
    Broadcast an event to all users in a session.

    Args:
        session_manager: WorkspaceSessionManager instance
        session_id: Session to broadcast to
        event_type: Event type string
        data: Event data
        exclude_user: Optional user ID to exclude from broadcast
    """
    if hasattr(session_manager, '_queue_ws_event'):
        session_manager._queue_ws_event(session_id, event_type, data)
    elif hasattr(session_manager, 'broadcast_to_session'):
        session_manager.broadcast_to_session(
            session_id,
            {'type': event_type, **data},
            exclude_user=exclude_user
        )


def format_agent_response(
    agent_id: str,
    content: str,
    session_id: str,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Format a standardized agent response message."""
    from datetime import datetime
    import uuid

    return {
        'type': 'agent_message',
        'id': str(uuid.uuid4())[:12],
        'agent_id': agent_id,
        'content': content,
        'session_id': session_id,
        'timestamp': datetime.utcnow().isoformat(),
        'metadata': metadata or {}
    }


if __name__ == "__main__":
    import asyncio

    # Test the helpers
    print("Testing WS helpers...")

    # Test validation
    data = {'session_id': '123'}
    error = validate_ws_message(data, ['session_id', 'content'])
    print(f"Validation error (expected): {error}")

    data2 = {'session_id': '123', 'content': 'hello'}
    error2 = validate_ws_message(data2, ['session_id', 'content'])
    print(f"Validation success: {error2 is None}")

    # Test router
    router = WSMessageRouter()

    @router.handler('test_message', required_fields=['value'])
    async def handle_test(data):
        return {'result': data['value'] * 2}

    async def test_router():
        result = await router.route('test_message', {'value': 21})
        print(f"Router result: {result}")

        result2 = await router.route('unknown', {})
        print(f"Unknown type: {result2}")

    asyncio.run(test_router())

    print("\n✓ WS helpers tests passed!")
