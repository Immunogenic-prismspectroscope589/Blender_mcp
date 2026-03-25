"""
Standardized Response Builder for Blender MCP 1.0.0

Provides deterministic, structured outputs for all handlers.
LLM-friendly format with consistent schema.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import time

# Throttle psutil memory check — at most once every 30s to avoid
# per-response OS system call overhead (NtQueryInformationProcess on Windows).
_psutil_last_check: float = 0.0
_psutil_last_result: Optional[float] = None


from .error_protocol import ErrorCode

_SUGGESTION_MAP = {
    ErrorCode.NO_CONTEXT.value: "Ensure Blender is running and the command is executed within a valid context.",
    ErrorCode.OBJECT_NOT_FOUND.value: (
        "Verify the object name using get_scene_graph GET_OBJECTS_FLAT."
    ),
    ErrorCode.POLL_FAILED.value: (
        "Operator cannot run in current context. Use execute_blender_code with bpy.data API instead of bpy.ops."
    ),
    ErrorCode.VALIDATION_ERROR.value: (
        "Check input parameters. Use manage_agent_context GET_ACTION_HELP to see the full schema."
    ),
    ErrorCode.EXECUTION_ERROR.value: (
        "Blender execution error. Check 'traceback' in details. "
        "Try execute_blender_code with bpy.data API for direct control."
    ),
    ErrorCode.TIMEOUT_ERROR.value: (
        "Operation timed out. Break the task into smaller steps or simplify the scene first."
    ),
    "MISSING_PARAMETER": (
        "Required parameter missing. Use manage_agent_context GET_ACTION_HELP to see the full schema."
    ),
    "UNKNOWN_ACTION": (
        "Invalid action value. Use manage_agent_context GET_ACTION_HELP to see valid actions for this tool."
    ),
    "NOT_FOUND": ("Item not found. Use get_scene_graph GET_OBJECTS_FLAT to list scene contents."),
    "INVALID_ACTION": (
        "Invalid action. Use manage_agent_context GET_ACTION_HELP to get a list of valid actions."
    ),
    "SYNTAX_ERROR": "Python syntax error in code. Fix the code per the traceback and retry.",
    "QUERY_TOO_SHORT": "Provide at least one meaningful keyword. Try GET_TOOL_CATALOG for a full listing.",
    "OBJECT_HAS_ANIMATION": (
        "Object has animation data overriding manual transforms. "
        "Clear the action with execute_blender_code: obj.animation_data_clear() before setting transforms."
    ),
}

# Per-error suggested next steps for agents — keyed by error_code string
_NEXT_STEPS_MAP: Dict[str, List[Dict[str, Any]]] = {
    ErrorCode.OBJECT_NOT_FOUND.value: [
        {
            "description": "List all scene objects with world positions",
            "suggested_tool": "get_scene_graph",
            "suggested_action": "GET_OBJECTS_FLAT",
        },
        {
            "description": "Get full scene hierarchy",
            "suggested_tool": "get_scene_graph",
            "suggested_action": "get_scene_graph",
        },
    ],
    ErrorCode.POLL_FAILED.value: [
        {
            "description": "Use bpy.data Python API instead of operators",
            "suggested_tool": "execute_blender_code",
            "suggested_action": "execute_blender_code",
        },
    ],
    ErrorCode.EXECUTION_ERROR.value: [
        {
            "description": "Execute custom Python for direct bpy API control",
            "suggested_tool": "execute_blender_code",
            "suggested_action": "execute_blender_code",
        },
        {
            "description": "Inspect scene state before retrying",
            "suggested_tool": "get_scene_graph",
            "suggested_action": "GET_OBJECTS_FLAT",
        },
    ],
    "MISSING_PARAMETER": [
        {
            "description": "Get full parameter schema for this tool",
            "suggested_tool": "manage_agent_context",
            "suggested_action": "GET_ACTION_HELP",
        },
    ],
    "UNKNOWN_ACTION": [
        {
            "description": "Get valid actions for this tool",
            "suggested_tool": "manage_agent_context",
            "suggested_action": "GET_ACTION_HELP",
        },
    ],
    "INVALID_ACTION": [
        {
            "description": "Get valid actions for this tool",
            "suggested_tool": "manage_agent_context",
            "suggested_action": "GET_ACTION_HELP",
        },
    ],
    "NOT_FOUND": [
        {
            "description": "List all scene objects with world-space positions",
            "suggested_tool": "get_scene_graph",
            "suggested_action": "GET_OBJECTS_FLAT",
        },
        {
            "description": "Get full scene hierarchy",
            "suggested_tool": "get_scene_graph",
            "suggested_action": "get_scene_graph",
        },
    ],
    "OBJECT_HAS_ANIMATION": [
        {
            "description": "Clear animation data so manual transforms stick",
            "suggested_tool": "execute_blender_code",
            "suggested_action": "execute_blender_code",
        },
        {
            "description": "Inspect current animation state",
            "suggested_tool": "get_object_info",
            "suggested_action": "GET_INFO",
        },
    ],
}


class ResponseBuilder:
    """
    Standardized response builder for deterministic outputs.

    All handlers MUST use this class for consistent LLM-friendly responses.
    """

    VERSION = "1.0.0"

    @staticmethod
    def _generate_summary(action: str, data: Dict[str, Any], state_diff: Dict[str, Any]) -> str:
        """Generate a human-readable summary of the operation."""
        summary = f"Action '{action}' completed successfully."

        # 1. Check for specific data summary
        if "summary" in data:
            return str(data["summary"])

        # 2. Check for count
        if "count" in data:
            summary += f" Processed {data['count']} items."

        # 3. Analyze State Diff
        if state_diff:
            added = len(state_diff.get("added", []))
            removed = len(state_diff.get("removed", []))
            modified = len(state_diff.get("modified", {}))

            changes = []
            if added:
                changes.append(f"{added} added")
            if removed:
                changes.append(f"{removed} deleted")
            if modified:
                changes.append(f"{modified} modified")

            if changes:
                summary += " Changes: " + ", ".join(changes) + "."

        return summary

    @classmethod
    def success(
        cls,
        handler: str,
        action: str,
        data: Optional[Dict[str, Any]] = None,
        affected_objects: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[Dict[str, Any]]] = None,
        undo_info: Optional[Dict[str, Any]] = None,
        next_steps: Optional[List[Dict[str, Any]]] = None,
        duration_ms: Optional[float] = None,
        state_diff: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build a successful response.

        Args:
            handler: Handler name (e.g., "manage_modeling")
            action: Action name (e.g., "EXTRUDE")
            data: Operation-specific data
            affected_objects: List of affected objects with changes
            warnings: List of warning messages
            undo_info: Undo/rollback information
            next_steps: Suggested next steps for LLM
            duration_ms: Operation duration in milliseconds
            state_diff: Granular semantic diff (Deep Mirror)

        Returns:
            Standardized response dictionary
        """
        warnings_list = warnings or []

        # Bug 24: Proactive OOM Warning System — throttled to once per 30s
        # to avoid per-response OS system call overhead.
        global _psutil_last_check, _psutil_last_result
        now = time.monotonic()
        if now - _psutil_last_check >= 30.0:
            try:
                import psutil
                import os

                _psutil_last_result = psutil.Process(os.getpid()).memory_percent()
                _psutil_last_check = now
            except Exception:
                _psutil_last_check = now  # back off even on failure
        if _psutil_last_result is not None and _psutil_last_result > 85.0:
            warnings_list.append(
                {
                    "code": "MEMORY_WARNING",
                    "message": f"WARNING - Approaching memory limit. RAM usage: {_psutil_last_result:.1f}%",
                    "severity": "high",
                }
            )

        return {
            "status": "OK",
            "success": True,
            "summary": cls._generate_summary(action, data or {}, state_diff or {}),
            "data": data or {},
            "metadata": {
                "handler": handler,
                "action": action,
                "duration_ms": duration_ms or 0,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "version": cls.VERSION,
                "api_level": "1.0.0",
            },
            "state_diff": state_diff or {},
            "affected_objects": affected_objects or [],
            "warnings": warnings_list,
            "errors": [],
            "undo_info": undo_info
            or {"undo_steps": 0, "undo_message": "", "backup_created": False, "backup_id": None},
            "next_steps": next_steps or [],
        }

    @classmethod
    def error(
        cls,
        handler: str,
        action: Optional[str],
        error_code: Union[str, Any],
        message: str,
        recoverable: bool = False,
        suggestion: str = "",
        affected_objects: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[Dict[str, Any]]] = None,
        undo_info: Optional[Dict[str, Any]] = None,
        next_steps: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build an error response.

        Args:
            handler: Handler name
            action: Action name
            error_code: Machine-readable error code (Enum, str, or MCPError exception object)
            message: Human-readable error message
            recoverable: Whether the error can be recovered from
            suggestion: Suggestion for fixing the error
            affected_objects: Objects affected before error
            warnings: Warnings before error occurred
            undo_info: Undo information if partial completion
            next_steps: Recovery steps
        """
        # GUARD: Handle MCPError exception objects (Unified Error System v26.0)
        final_code = error_code
        final_message = message
        final_suggestion = suggestion

        # Checking against Exception class name or duck typing to avoid circular imports if possible
        # but importing MCPError is safe here if inside TYPE_CHECKING or careful.
        # Simple hasattr checks work for duck typing the Exception.

        if hasattr(error_code, "code") and hasattr(error_code, "message"):
            # It's an MCPError Exception (or compatible object)
            final_code = getattr(error_code, "code", "UNKNOWN_ERROR")
            if not final_message:
                final_message = getattr(error_code, "message", "Unknown Error")
            if not final_suggestion and hasattr(error_code, "suggestion"):
                final_suggestion = getattr(error_code, "suggestion", "")

        # Auto-suggestion fallback
        if not final_suggestion:
            final_suggestion = _SUGGESTION_MAP.get(str(final_code), "")

        return {
            "status": "ERROR",
            "success": False,
            "data": {},
            "metadata": {
                "handler": handler,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "version": cls.VERSION,
            },
            "affected_objects": affected_objects or [],
            "warnings": warnings or [],
            "errors": [
                {
                    "code": str(final_code),
                    "message": str(final_message),
                    "recoverable": recoverable,
                    "suggestion": str(final_suggestion),
                }
            ],
            "undo_info": undo_info
            or {"undo_steps": 0, "undo_message": "", "backup_created": False, "backup_id": None},
            "next_steps": next_steps
            or _NEXT_STEPS_MAP.get(
                str(final_code),
                [
                    {
                        "description": "Check error details and retry",
                        "suggested_tool": handler,
                        "suggested_action": action,
                    }
                ],
            ),
        }

    @classmethod
    def from_error(
        cls,
        error: Any,
        handler: str,
        action: Optional[str] = None,
        recoverable: bool = True,
    ) -> Dict[str, Any]:
        """
        Convert error_protocol style errors into standardized response shape.

        Supported inputs:
        - Dict from create_error/ErrorProtocol (keys: error/message, code, suggestion, details)
        - MCPError-like object (attributes: message, code, suggestion, details)
        - Exception / generic object
        """
        code = "UNKNOWN_ERROR"
        message = "Unknown error"
        suggestion = ""
        details: Dict[str, Any] = {}

        if isinstance(error, dict):
            code = str(error.get("code", code))
            message = str(error.get("error") or error.get("message") or message)
            suggestion = str(error.get("suggestion") or "")
            raw_details = error.get("details")
            if isinstance(raw_details, dict):
                details = raw_details
        elif hasattr(error, "code") and hasattr(error, "message"):
            code = str(getattr(error, "code"))
            message = str(getattr(error, "message"))
            raw_suggestion = getattr(error, "suggestion", "")
            suggestion = str(raw_suggestion) if raw_suggestion else ""
            raw_details = getattr(error, "details", None)
            if isinstance(raw_details, dict):
                details = raw_details
        elif isinstance(error, Exception):
            code = type(error).__name__.upper()
            message = str(error)
        elif error is not None:
            message = str(error)

        return cls.error(
            handler=handler,
            action=action or "UNKNOWN_ACTION",
            error_code=code,
            message=message,
            recoverable=recoverable,
            suggestion=suggestion,
            details=details,
        )

    @classmethod
    def partial(
        cls,
        handler: str,
        action: str,
        data: Dict[str, Any],
        completed_steps: List[str],
        failed_steps: List[Dict[str, Any]],
        affected_objects: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build a partial success response (some steps completed, some failed).

        Args:
            handler: Handler name
            action: Action name
            data: Partial result data
            completed_steps: List of completed step names
            failed_steps: List of failed steps with error details
        """
        return {
            "status": "PARTIAL",
            "success": True,  # Kısmen başarılı
            "data": data,
            "metadata": {
                "handler": handler,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "version": cls.VERSION,
            },
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "affected_objects": affected_objects or [],
            "warnings": warnings or [],
            "errors": [step["error"] for step in failed_steps],
            "undo_info": {
                "undo_steps": len(completed_steps),
                "undo_message": f"Rollback {len(completed_steps)} completed steps",
                "backup_created": True,
                "backup_id": kwargs.get("backup_id"),
            },
            "next_steps": [
                {
                    "description": f"Retry failed steps: {', '.join(s['name'] for s in failed_steps)}",
                    "suggested_tool": handler,
                    "suggested_action": action,
                }
            ],
        }

    @classmethod
    def warning(
        cls,
        handler: str,
        action: str,
        data: Dict[str, Any],
        warnings: List[Dict[str, Any]],
        affected_objects: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build a warning response (success but with warnings).
        """
        return {
            "status": "WARNING",
            "success": True,
            "data": data,
            "metadata": {
                "handler": handler,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "version": cls.VERSION,
            },
            "affected_objects": affected_objects or [],
            "warnings": warnings,
            "errors": [],
            "undo_info": {
                "undo_steps": 1,
                "undo_message": f"{handler}.{action}",
                "backup_created": False,
                "backup_id": None,
            },
            "next_steps": [
                {
                    "description": "Review warnings before proceeding",
                    "suggested_tool": handler,
                    "suggested_action": action,
                }
            ],
        }

    @classmethod
    def preview(
        cls,
        handler: str,
        action: str,
        preview_data: Dict[str, Any],
        confidence: Optional[float] = None,
        affected_objects: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build a preview/dry-run response.

        Args:
            preview_data: Simulated result data
            confidence: Confidence score (0-1) for the preview
        """
        return {
            "status": "PREVIEW",
            "success": True,
            "preview": True,
            "data": preview_data,
            "metadata": {
                "handler": handler,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "version": cls.VERSION,
            },
            "confidence": confidence,
            "affected_objects": affected_objects or [],
            "warnings": warnings or [],
            "errors": [],
            "undo_info": {"undo_steps": 0, "note": "This is a preview - no changes made"},
            "next_steps": [
                {
                    "description": "Execute the operation",
                    "suggested_tool": handler,
                    "suggested_action": action,
                }
            ],
        }

    @classmethod
    def validation_report(
        cls,
        handler: str,
        action: str,
        target_action: str,
        valid: bool,
        errors: List[Any],
        warnings: List[Any],
        normalized_params: Optional[Dict[str, Any]] = None,
        next_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build deterministic validation-step response."""
        return {
            "status": "OK" if valid else "ERROR",
            "success": valid,
            "data": {
                "valid": valid,
                "target_action": target_action,
                "normalized_params": normalized_params,
            },
            "metadata": {
                "handler": handler,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "version": cls.VERSION,
                "phase": "validate",
            },
            "warnings": warnings,
            "errors": errors,
            "next_steps": next_steps or [],
        }

    @classmethod
    def preview_report(
        cls,
        handler: str,
        action: str,
        target_action: str,
        simulation: Dict[str, Any],
        normalized_params: Optional[Dict[str, Any]] = None,
        next_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build deterministic preview-step response."""
        return {
            "status": "PREVIEW",
            "success": True,
            "preview": True,
            "data": {
                "target_action": target_action,
                "simulation": simulation,
                "normalized_params": normalized_params,
            },
            "metadata": {
                "handler": handler,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "version": cls.VERSION,
                "phase": "preview",
            },
            "warnings": simulation.get("warnings", []),
            "errors": [],
            "next_steps": next_steps or [],
        }

    @classmethod
    def add_affected_object(
        cls, response: Dict[str, Any], name: str, obj_type: str, changes: List[str]
    ) -> Dict[str, Any]:
        """Add an affected object to an existing response."""
        if "affected_objects" not in response:
            response["affected_objects"] = []

        response["affected_objects"].append({"name": name, "type": obj_type, "changes": changes})
        return response

    @classmethod
    def add_warning(
        cls, response: Dict[str, Any], code: str, message: str, severity: str = "medium"
    ) -> Dict[str, Any]:
        """Add a warning to an existing response."""
        if "warnings" not in response:
            response["warnings"] = []

        response["warnings"].append({"code": code, "message": message, "severity": severity})
        return response

    @classmethod
    def add_next_step(
        cls, response: Dict[str, Any], description: str, tool: str, action: str
    ) -> Dict[str, Any]:
        """Add a suggested next step to an existing response."""
        if "next_steps" not in response:
            response["next_steps"] = []

        response["next_steps"].append(
            {"description": description, "suggested_tool": tool, "suggested_action": action}
        )
        return response


class ResponseTimer:
    """Context manager for timing operations."""

    def __init__(self) -> None:
        self.start_time: Optional[float] = None
        self.duration_ms: float = 0.0

    def __enter__(self) -> "ResponseTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        if self.start_time is None:
            self.duration_ms = 0.0
            return
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000

    def get_duration(self) -> float:
        return self.duration_ms


# Convenience functions for quick usage
def success_response(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Quick success response."""
    return ResponseBuilder.success(*args, **kwargs)


def error_response(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Quick error response."""
    return ResponseBuilder.error(*args, **kwargs)


def partial_response(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Quick partial response."""
    return ResponseBuilder.partial(*args, **kwargs)
