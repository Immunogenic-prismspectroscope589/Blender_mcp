from typing import Any, Optional, Dict, List, Union
from enum import Enum

# Forward ref to avoid circular import if needed,
# but ErrorCode is in error_protocol which doesn't import exceptions.
# However, we want to deprecate error_protocol's MCPError class.


class MCPError(Exception):
    """
    Standardized Base Exception for all MCP errors.

    Unifies Runtime Exception capabilities with Rich Error Protocol data.
    """

    def __init__(
        self,
        message: str,
        error_code: Union[str, int, Enum] = -32000,
        data: Optional[Any] = None,
        tool: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        alternatives: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message

        # Normalize error code
        if isinstance(error_code, Enum):
            self.code = error_code.value
        else:
            self.code = error_code

        self.data = data

        # Rich Protocol Fields
        self.tool = tool
        self.action = action
        self.details = details or {}
        self.suggestion = suggestion
        self.alternatives = alternatives or []

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict for Protocol."""
        return {
            "error": {
                "code": str(self.code),
                "message": self.message,
                "data": self.data,
                "details": self.details,
                "suggestion": self.suggestion,
            }
        }


class SecurityError(MCPError):
    """Raised when an action is blocked by Safe Mode"""

    def __init__(self, message: str = "Action blocked by Security Policy") -> None:
        super().__init__(message, error_code=-32001)


class ValidationError(MCPError):
    """Raised when input parameters are invalid"""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=-32602)


class ExecutionError(MCPError):
    """Raised when Blender fails to execute the command"""

    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        data = {"type": type(original_exception).__name__} if original_exception else None
        super().__init__(message, error_code=-32603, data=data)
