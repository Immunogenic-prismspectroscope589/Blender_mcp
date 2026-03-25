"""
Standardized Error Protocol for Blender MCP 1.0.0 "High Mode Ultra"

Provides consistent error codes usage.

Note: The MCPError class has been moved to core.exceptions to unify
Runtime Exceptions with Protocol Data.
"""

from enum import Enum
from typing import Any, Dict, Optional

from .exceptions import MCPError

# Forward reference to avoid circular import
# from .exceptions import MCPError # Moved to try/except block below or handled dynamically


class ErrorCode(Enum):
    """
    Standardized error codes for Blender MCP operations.

    These codes provide machine-readable categorization of errors
    for automated error handling and recovery.
    """

    # Context errors
    NO_CONTEXT = "NO_CONTEXT"
    NO_SCENE = "NO_SCENE"
    NO_VIEW_LAYER = "NO_VIEW_LAYER"
    NO_ACTIVE_OBJECT = "NO_ACTIVE_OBJECT"

    # Object errors
    OBJECT_NOT_FOUND = "OBJECT_NOT_FOUND"
    MULTIPLE_OBJECTS_FOUND = "MULTIPLE_OBJECTS_FOUND"
    WRONG_OBJECT_TYPE = "WRONG_OBJECT_TYPE"
    OBJECT_DELETED = "OBJECT_DELETED"

    # Operator errors
    POLL_FAILED = "POLL_FAILED"
    MODAL_OPERATOR_BLOCKED = "MODAL_OPERATOR_BLOCKED"
    OPERATOR_NOT_FOUND = "OPERATOR_NOT_FOUND"
    OPERATOR_CRASHED = "OPERATOR_CRASHED"

    # Validation errors
    MISSING_PARAMETER = "MISSING_PARAMETER"
    INVALID_PARAMETER_TYPE = "INVALID_PARAMETER_TYPE"
    INVALID_PARAMETER_VALUE = "INVALID_PARAMETER_VALUE"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Mode errors
    MODE_SWITCH_FAILED = "MODE_SWITCH_FAILED"
    WRONG_MODE = "WRONG_MODE"

    # Data errors
    NO_MESH_DATA = "NO_MESH_DATA"
    NO_UV_LAYERS = "NO_UV_LAYERS"
    NO_MATERIAL = "NO_MATERIAL"
    NO_TEXTURE = "NO_TEXTURE"

    # Execution errors
    EXECUTION_ERROR = "EXECUTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CRASH_RECOVERED = "CRASH_RECOVERED"
    THREAD_ERROR = "THREAD_ERROR"

    # Version errors
    VERSION_INCOMPATIBLE = "VERSION_INCOMPATIBLE"
    API_CHANGED = "API_CHANGED"

    # Generic
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    EXPORT_ERROR = "EXPORT_ERROR"


__all__ = ["ErrorCode", "ErrorProtocol", "create_error", "MCPError"]


def create_error(
    error_code: Any,
    message: Optional[str] = None,
    custom_message: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Factory for creating legacy error dictionaries.

    Args:
        error_code: The standardized error code (Enum or str).
        message: Optional message override.
        custom_message: Alias for message (for backward compatibility).
        **kwargs: Additional details (e.g., field, details).

    Returns:
        Dict[str, Any]: The error dictionary expected by legacy handlers.
    """
    # 1. Resolve Code
    code_val = getattr(error_code, "value", str(error_code))

    # 2. Resolve Message
    final_msg = message or custom_message
    if not final_msg:
        # If no message, try to use the Enum name or value
        final_msg = getattr(error_code, "name", str(error_code))

    # 3. Construct Dictionary
    # This structure must match what legacy handlers expect.
    # Often used in validation_utils to return a simple dict.
    result = {
        "code": code_val,
        "message": final_msg,
    }

    # Merge kwargs (like 'field', 'details', 'expected_type')
    result.update(kwargs)

    return result


# Backward Compatibility Alias
ErrorProtocol = ErrorCode
