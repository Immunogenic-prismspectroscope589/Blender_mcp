import traceback
from functools import wraps
import logging

# Set up logging for the MCP tools
logger = logging.getLogger("mcp_tools")


def mcp_tool_handler(func):
    """
    Universal Error Handler Decorator for Blender MCP Tools.
    Catches Python/API exceptions, prevents silent failures,
    and returns a standardized JSON-compatible dict to the LLM agent.

    This enforces the 'Fail-Fast & Resilience' and 'Zero Trust Input'
    architectural rules (Rules 5, 9).
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Ensure return format is consistent (Success)
            if isinstance(result, dict) and "success" not in result:
                result["success"] = True
            elif not isinstance(result, dict):
                return {"success": True, "data": result}
            return result

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            # Log the full stack trace on the server side
            logger.error(f"[mcp_tool_handler] CATCH: {func.__name__} -> {error_type}: {error_msg}")
            logger.debug(traceback.format_exc())

            # Return standardized Graceful Degradation payload
            return {
                "success": False,
                "error_type": error_type,
                "message": error_msg,
                "hint": f"Execution failed in '{func.__name__}'. See server logs for full traceback.",
                "traceback_summary": traceback.format_exc().splitlines()[-3:],  # Send tail of trace
            }

    return wrapper


def validate_enum(value: str, allowed_values: set, param_name: str) -> str:
    """Helper to validate enum values natively."""
    if value not in allowed_values:
        raise ValueError(f"Invalid {param_name}: '{value}'. Must be one of {allowed_values}")
    return value
