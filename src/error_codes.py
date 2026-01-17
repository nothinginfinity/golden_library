#!/usr/bin/env python3
"""
Phase 4C Error Codes

Standardized error codes and responses for the collaborative workspace.
All error responses follow this format:
{
    "error": true,
    "code": "E001_SESSION_NOT_FOUND",
    "message": "Human-readable message",
    "retry_after": Optional[int],  # seconds
    "request_id": Optional[str]
}
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
import uuid


class ErrorCategory(Enum):
    """Error categories for grouping."""
    SESSION = "SESSION"
    DATABASE = "DATABASE"
    TOOL = "TOOL"
    DELEGATION = "DELEGATION"
    CANVAS = "CANVAS"
    CONFIG = "CONFIG"
    DEMO = "DEMO"
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    INTERNAL = "INTERNAL"


@dataclass
class ErrorCode:
    """Error code definition."""
    code: str
    message: str
    category: ErrorCategory
    retryable: bool = False
    default_retry_after: Optional[int] = None


# Error code registry
ERROR_CODES = {
    # Session errors (E001-E019)
    "E001_SESSION_NOT_FOUND": ErrorCode(
        code="E001_SESSION_NOT_FOUND",
        message="Session not found",
        category=ErrorCategory.SESSION
    ),
    "E002_SESSION_EXPIRED": ErrorCode(
        code="E002_SESSION_EXPIRED",
        message="Session has expired",
        category=ErrorCategory.SESSION
    ),
    "E003_SESSION_FULL": ErrorCode(
        code="E003_SESSION_FULL",
        message="Session has reached maximum participant limit",
        category=ErrorCategory.SESSION
    ),
    "E004_INVALID_SESSION_ID": ErrorCode(
        code="E004_INVALID_SESSION_ID",
        message="Invalid session ID format",
        category=ErrorCategory.SESSION
    ),

    # Database errors (E020-E039)
    "E020_DB_NOT_INITIALIZED": ErrorCode(
        code="E020_DB_NOT_INITIALIZED",
        message="Database not initialized",
        category=ErrorCategory.DATABASE,
        retryable=True,
        default_retry_after=5
    ),
    "E021_DB_CONNECTION_FAILED": ErrorCode(
        code="E021_DB_CONNECTION_FAILED",
        message="Database connection failed",
        category=ErrorCategory.DATABASE,
        retryable=True,
        default_retry_after=10
    ),
    "E022_DB_QUERY_FAILED": ErrorCode(
        code="E022_DB_QUERY_FAILED",
        message="Database query failed",
        category=ErrorCategory.DATABASE,
        retryable=True,
        default_retry_after=5
    ),
    "E023_DB_POOL_EXHAUSTED": ErrorCode(
        code="E023_DB_POOL_EXHAUSTED",
        message="Database connection pool exhausted",
        category=ErrorCategory.DATABASE,
        retryable=True,
        default_retry_after=30
    ),

    # Tool errors (E040-E059)
    "E040_TOOL_NOT_FOUND": ErrorCode(
        code="E040_TOOL_NOT_FOUND",
        message="Tool not found",
        category=ErrorCategory.TOOL
    ),
    "E041_TOOL_PERMISSION_DENIED": ErrorCode(
        code="E041_TOOL_PERMISSION_DENIED",
        message="Agent does not have permission to use this tool",
        category=ErrorCategory.TOOL
    ),
    "E042_TOOL_RATE_LIMITED": ErrorCode(
        code="E042_TOOL_RATE_LIMITED",
        message="Tool rate limit exceeded",
        category=ErrorCategory.TOOL,
        retryable=True,
        default_retry_after=30
    ),
    "E043_TOOL_EXECUTION_FAILED": ErrorCode(
        code="E043_TOOL_EXECUTION_FAILED",
        message="Tool execution failed",
        category=ErrorCategory.TOOL,
        retryable=True,
        default_retry_after=5
    ),
    "E044_TOOL_TIMEOUT": ErrorCode(
        code="E044_TOOL_TIMEOUT",
        message="Tool execution timed out",
        category=ErrorCategory.TOOL,
        retryable=True,
        default_retry_after=10
    ),

    # Delegation errors (E060-E079)
    "E060_DELEGATION_FAILED": ErrorCode(
        code="E060_DELEGATION_FAILED",
        message="Task delegation failed",
        category=ErrorCategory.DELEGATION
    ),
    "E061_AGENT_BUSY": ErrorCode(
        code="E061_AGENT_BUSY",
        message="Target agent is currently busy",
        category=ErrorCategory.DELEGATION,
        retryable=True,
        default_retry_after=15
    ),
    "E062_CIRCULAR_DELEGATION": ErrorCode(
        code="E062_CIRCULAR_DELEGATION",
        message="Circular delegation detected",
        category=ErrorCategory.DELEGATION
    ),
    "E063_INVALID_AGENT": ErrorCode(
        code="E063_INVALID_AGENT",
        message="Invalid agent specified",
        category=ErrorCategory.DELEGATION
    ),
    "E064_TASK_NOT_FOUND": ErrorCode(
        code="E064_TASK_NOT_FOUND",
        message="Delegated task not found",
        category=ErrorCategory.DELEGATION
    ),

    # Canvas errors (E080-E099)
    "E080_CANVAS_NOT_FOUND": ErrorCode(
        code="E080_CANVAS_NOT_FOUND",
        message="Canvas document not found",
        category=ErrorCategory.CANVAS
    ),
    "E081_SECTION_LOCKED": ErrorCode(
        code="E081_SECTION_LOCKED",
        message="Canvas section is locked by another user",
        category=ErrorCategory.CANVAS,
        retryable=True,
        default_retry_after=5
    ),
    "E082_CONFLICT_DETECTED": ErrorCode(
        code="E082_CONFLICT_DETECTED",
        message="Edit conflict detected",
        category=ErrorCategory.CANVAS,
        retryable=True
    ),
    "E083_INVALID_SECTION": ErrorCode(
        code="E083_INVALID_SECTION",
        message="Invalid canvas section",
        category=ErrorCategory.CANVAS
    ),

    # Config errors (E100-E119)
    "E100_CONFIG_NOT_AVAILABLE": ErrorCode(
        code="E100_CONFIG_NOT_AVAILABLE",
        message="Configuration not available",
        category=ErrorCategory.CONFIG
    ),
    "E101_INVALID_CONFIG": ErrorCode(
        code="E101_INVALID_CONFIG",
        message="Invalid configuration format",
        category=ErrorCategory.CONFIG
    ),
    "E102_CONFIG_PARSE_ERROR": ErrorCode(
        code="E102_CONFIG_PARSE_ERROR",
        message="Failed to parse CLAUDE.md configuration",
        category=ErrorCategory.CONFIG
    ),

    # Demo errors (E120-E139)
    "E120_DEMO_NOT_AVAILABLE": ErrorCode(
        code="E120_DEMO_NOT_AVAILABLE",
        message="Demo recorder not available",
        category=ErrorCategory.DEMO
    ),
    "E121_DEMO_ALREADY_ACTIVE": ErrorCode(
        code="E121_DEMO_ALREADY_ACTIVE",
        message="Demo mode already active",
        category=ErrorCategory.DEMO
    ),
    "E122_DEMO_NOT_ACTIVE": ErrorCode(
        code="E122_DEMO_NOT_ACTIVE",
        message="Demo mode not active",
        category=ErrorCategory.DEMO
    ),
    "E123_RECORDING_FAILED": ErrorCode(
        code="E123_RECORDING_FAILED",
        message="Failed to record demo event",
        category=ErrorCategory.DEMO
    ),

    # Rate limit errors (E140-E149)
    "E140_RATE_LIMITED": ErrorCode(
        code="E140_RATE_LIMITED",
        message="Rate limit exceeded",
        category=ErrorCategory.RATE_LIMIT,
        retryable=True,
        default_retry_after=60
    ),
    "E141_API_QUOTA_EXCEEDED": ErrorCode(
        code="E141_API_QUOTA_EXCEEDED",
        message="API quota exceeded",
        category=ErrorCategory.RATE_LIMIT,
        retryable=True,
        default_retry_after=300
    ),

    # Internal errors (E900-E999)
    "E900_INTERNAL_ERROR": ErrorCode(
        code="E900_INTERNAL_ERROR",
        message="Internal server error",
        category=ErrorCategory.INTERNAL,
        retryable=True,
        default_retry_after=5
    ),
    "E901_NOT_IMPLEMENTED": ErrorCode(
        code="E901_NOT_IMPLEMENTED",
        message="Feature not implemented",
        category=ErrorCategory.INTERNAL
    ),
}


def make_error_response(
    error_code: str,
    details: Optional[str] = None,
    retry_after: Optional[int] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        error_code: Error code key (e.g., "E001_SESSION_NOT_FOUND")
        details: Optional additional details
        retry_after: Override retry_after seconds
        request_id: Request ID for tracking

    Returns:
        Error response dict
    """
    error_def = ERROR_CODES.get(error_code)

    if not error_def:
        # Fallback for unknown error codes
        return {
            "error": True,
            "code": error_code,
            "message": details or "Unknown error",
            "request_id": request_id or str(uuid.uuid4())[:8]
        }

    message = error_def.message
    if details:
        message = f"{message}: {details}"

    response = {
        "error": True,
        "code": error_def.code,
        "message": message,
        "category": error_def.category.value,
        "retryable": error_def.retryable,
        "request_id": request_id or str(uuid.uuid4())[:8]
    }

    # Add retry_after if applicable
    actual_retry = retry_after or error_def.default_retry_after
    if actual_retry:
        response["retry_after"] = actual_retry

    return response


def is_retryable(error_response: Dict[str, Any]) -> bool:
    """Check if an error response indicates a retryable error."""
    return error_response.get("retryable", False)


def get_retry_after(error_response: Dict[str, Any]) -> Optional[int]:
    """Get retry_after value from error response."""
    return error_response.get("retry_after")


# Convenience functions for common errors
def session_not_found(session_id: str = None) -> Dict[str, Any]:
    details = f"session_id={session_id}" if session_id else None
    return make_error_response("E001_SESSION_NOT_FOUND", details)


def db_not_initialized() -> Dict[str, Any]:
    return make_error_response("E020_DB_NOT_INITIALIZED")


def tool_permission_denied(tool: str, agent: str) -> Dict[str, Any]:
    return make_error_response("E041_TOOL_PERMISSION_DENIED", f"{agent} cannot use {tool}")


def tool_rate_limited(tool: str, retry_after: int = 30) -> Dict[str, Any]:
    return make_error_response("E042_TOOL_RATE_LIMITED", tool, retry_after=retry_after)


def circular_delegation(chain: str) -> Dict[str, Any]:
    return make_error_response("E062_CIRCULAR_DELEGATION", chain)


def section_locked(section: str, locked_by: str) -> Dict[str, Any]:
    return make_error_response("E081_SECTION_LOCKED", f"{section} locked by {locked_by}")


def demo_not_available() -> Dict[str, Any]:
    return make_error_response("E120_DEMO_NOT_AVAILABLE")


def demo_already_active() -> Dict[str, Any]:
    return make_error_response("E121_DEMO_ALREADY_ACTIVE")


def demo_not_active() -> Dict[str, Any]:
    return make_error_response("E122_DEMO_NOT_ACTIVE")


def config_not_available() -> Dict[str, Any]:
    return make_error_response("E100_CONFIG_NOT_AVAILABLE")


def internal_error(details: str = None) -> Dict[str, Any]:
    return make_error_response("E900_INTERNAL_ERROR", details)


if __name__ == "__main__":
    # Test error responses
    print("Error Code Examples:")
    print("-" * 60)

    print("\n1. Session not found:")
    print(session_not_found("sess_abc123"))

    print("\n2. Tool permission denied:")
    print(tool_permission_denied("deepseek", "koda"))

    print("\n3. Section locked:")
    print(section_locked("analysis", "cairn"))

    print("\n4. Rate limited:")
    print(tool_rate_limited("web_search", 60))

    print("\n5. Internal error:")
    print(internal_error("Unexpected state"))
