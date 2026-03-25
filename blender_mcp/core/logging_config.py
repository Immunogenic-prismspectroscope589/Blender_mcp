"""
Centralized Logging System for Blender MCP 1.0.0

Structured, high-performance logging with:
- JSON formatting for machine parsing
- Automatic rotation
- Context enrichment (Blender version, scene, etc.)
- Performance metrics
- Request tracing

High Mode Philosophy: Maximum observability for debugging.
"""

import json
import logging
import logging.handlers
import os
import tempfile
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Callable
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from functools import wraps

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False


# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tool_name_var: ContextVar[str] = ContextVar("tool_name", default="")
action_var: ContextVar[str] = ContextVar("action", default="")


@dataclass
class LogContext:
    """Structured log context."""

    request_id: str = ""
    tool: str = ""
    action: str = ""
    user_id: str = ""
    session_id: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context from record
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "tool"):
            log_data["tool"] = record.tool
        if hasattr(record, "action"):
            log_data["action"] = record.action

        # Add exception info
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": (
                    traceback.format_exception(*record.exc_info) if record.exc_info else None
                ),
            }

        # Add extra fields
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "params"):
            log_data["params"] = record.params
        if hasattr(record, "result"):
            log_data["result"] = record.result
        if hasattr(record, "blender_version"):
            log_data["blender_version"] = record.blender_version
        if hasattr(record, "scene"):
            log_data["scene"] = record.scene

        # Add any custom attributes
        for key, value in record.__dict__.items():
            if key not in log_data and not key.startswith("_"):
                if key not in [
                    "name",
                    "msg",
                    "args",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                ]:
                    log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False, default=str)


class MCPLogger:
    """
    Centralized logger for Blender MCP.

    Features:
    - Structured JSON logging
    - Automatic file rotation
    - Context enrichment
    - Performance tracking
    """

    _instance = None
    _initialized = False

    def __new__(cls) -> Any:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: Optional[str] = None):
        if self._initialized:
            return

        self._initialized = True

        # Setup log directory
        if log_dir is None:
            log_dir = tempfile.gettempdir()
        self.log_dir = log_dir

        # Create log file path
        self.log_file = os.path.join(log_dir, "blender_mcp_v1.0.0.log")

        # Setup logger
        self._logger = logging.getLogger("blender_mcp")
        self._logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self._logger.handlers = []

        # File handler with rotation — only inside Blender to avoid Windows file-lock conflict
        # when inspect_tools.py imports handlers while Blender addon holds the log file open.
        if BPY_AVAILABLE:
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    self.log_file,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=5,
                    encoding="utf-8",
                    delay=True,  # don't open file until first write
                )
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(JSONFormatter())
                self._logger.addHandler(file_handler)
            except (PermissionError, OSError):
                pass  # Blender already holds the log file; continue without file logging

        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        self._logger.addHandler(console_handler)

        self._log_blender_info()

    def _log_blender_info(self) -> None:
        """Log Blender environment info."""
        if BPY_AVAILABLE:
            try:
                version = tuple(getattr(bpy.app, "version", (0, 0, 0)))
                self.info(
                    "Blender MCP initialized",
                    extra={
                        "blender_version": ".".join(map(str, version)),
                        "blender_path": getattr(bpy.app, "binary_path", "unknown"),
                    },
                )
            except:
                pass
        else:
            self.info("Blender MCP initialized (mock mode)")

    def _get_context(self) -> Dict[str, str]:
        """Get current logging context."""
        return {
            "request_id": request_id_var.get(""),
            "tool": tool_name_var.get(""),
            "action": action_var.get(""),
        }

    def _enrich_extra(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Enrich log extra with context."""
        extra = extra or {}
        context = self._get_context()

        # Add context to extra
        for key, value in context.items():
            if value and key not in extra:
                extra[key] = value

        # Add Blender context info
        if BPY_AVAILABLE:
            try:
                if "scene" not in extra:
                    scene = bpy.context.scene
                    extra["scene"] = scene.name if scene else None
                if "active_object" not in extra:
                    obj = bpy.context.active_object
                    extra["active_object"] = obj.name if obj else None
            except:
                pass

        return extra

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message."""
        self._logger.debug(message, extra=self._enrich_extra(extra))

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log info message."""
        self._logger.info(message, extra=self._enrich_extra(extra))

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message."""
        self._logger.warning(message, extra=self._enrich_extra(extra))

    def error(
        self, message: str, exc_info: bool = False, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log error message."""
        self._logger.error(message, exc_info=exc_info, extra=self._enrich_extra(extra))

    def critical(
        self, message: str, exc_info: bool = False, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log critical message."""
        self._logger.critical(message, exc_info=exc_info, extra=self._enrich_extra(extra))

    def log_tool_execution(
        self,
        tool: str,
        action: str,
        params: Dict[str, Any],
        result: Any,
        duration_ms: float,
        error: Optional[Exception] = None,
    ) -> None:
        """
        Log tool execution with full context.

        Args:
            tool: Tool name
            action: Action name
            params: Tool parameters (sanitized)
            result: Execution result
            duration_ms: Execution duration
            error: Optional error
        """
        extra = {
            "tool": tool,
            "action": action,
            "params": params,
            "duration_ms": duration_ms,
        }

        if error:
            extra["error"] = str(error)
            extra["error_type"] = type(error).__name__
            self.error(f"Tool execution failed: {tool}.{action}", exc_info=True, extra=extra)
        else:
            extra["result"] = result
            self.info(f"Tool execution successful: {tool}.{action}", extra=extra)


# =============================================================================
# CONTEXT MANAGEMENT
# =============================================================================


def set_request_context(
    request_id: Optional[str] = None, tool: Optional[str] = None, action: Optional[str] = None
) -> str:
    """
    Set logging context for current request.

    Returns:
        Request ID
    """
    req_id = request_id or str(uuid.uuid4())
    request_id_var.set(req_id)
    if tool:
        tool_name_var.set(tool)
    if action:
        action_var.set(action)
    return req_id


def clear_request_context() -> None:
    """Clear logging context."""
    request_id_var.set("")
    tool_name_var.set("")
    action_var.set("")


# =============================================================================
# DECORATORS
# =============================================================================


def log_execution(level: str = "info") -> Callable[..., Any]:
    """
    Decorator to log function execution.

    Usage:
        @log_execution()
        def my_handler(action, **params):
            pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = MCPLogger()
            start = time.time()

            # Extract tool/action from args if possible
            tool = kwargs.get("tool", func.__name__)
            action = kwargs.get("action", "unknown")

            set_request_context(tool=tool, action=action)

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start) * 1000

                getattr(logger, level)(
                    f"Executed {func.__name__}",
                    extra={
                        "duration_ms": duration_ms,
                        "result_preview": str(result)[:100] if result else None,
                    },
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                logger.error(
                    f"Failed {func.__name__}: {e}",
                    exc_info=True,
                    extra={"duration_ms": duration_ms},
                )
                raise
            finally:
                clear_request_context()

        return wrapper

    return decorator


def track_performance(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to track function performance.

    Usage:
        @track_performance
        def slow_operation():
            pass
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = MCPLogger()
        start = time.time()

        try:
            return func(*args, **kwargs)
        finally:
            duration_ms = (time.time() - start) * 1000
            if duration_ms > 1000:  # Log slow operations
                logger.warning(
                    f"Slow operation: {func.__name__} took {duration_ms:.0f}ms",
                    extra={"duration_ms": duration_ms},
                )

    return wrapper


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_logger() -> MCPLogger:
    """Get MCP logger instance."""
    return MCPLogger()


def log_debug(message: str, **kwargs: Any) -> None:
    """Quick debug log."""
    MCPLogger().debug(message, extra=kwargs)


def log_info(message: str, **kwargs: Any) -> None:
    """Quick info log."""
    MCPLogger().info(message, extra=kwargs)


def log_error(message: str, exc_info: bool = False, **kwargs: Any) -> None:
    """Quick error log."""
    MCPLogger().error(message, exc_info=exc_info, extra=kwargs)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "MCPLogger",
    "JSONFormatter",
    "LogContext",
    "set_request_context",
    "clear_request_context",
    "log_execution",
    "track_performance",
    "get_logger",
    "log_debug",
    "log_info",
    "log_error",
]
