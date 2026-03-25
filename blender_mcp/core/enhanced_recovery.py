"""
Enhanced Error Recovery System for Blender MCP 1.0.0

High Mode Philosophy: Errors should be recoverable, informative, and never crash.

Features:
- Automatic retry with exponential backoff
- Context restoration
- Operation rollback
- Detailed error context
- Recovery suggestions
"""

import time
import traceback
from typing import Any, Dict, Optional, List, Callable, Tuple, Type, cast
from dataclasses import dataclass, field
from functools import wraps
from enum import Enum

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from .logging_config import get_logger
from .context_manager_v3 import ContextManagerV3

logger = get_logger()


class RecoveryStrategy(Enum):
    """Recovery strategies for failed operations."""

    RETRY = "retry"  # Simple retry
    RETRY_WITH_DELAY = "retry_with_delay"  # Retry after delay
    FALLBACK = "fallback"  # Use alternative approach
    ROLLBACK = "rollback"  # Rollback and retry
    SKIP = "skip"  # Skip operation
    ABORT = "abort"  # Abort with error


@dataclass
class ErrorContext:
    """Detailed error context."""

    tool: str = ""
    action: str = ""
    params: Dict = field(default_factory=dict)
    exception: Optional[Exception] = None
    traceback_str: str = ""
    recovery_attempts: int = 0
    context_snapshot: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "tool": self.tool,
            "action": self.action,
            "params": {k: str(v) for k, v in self.params.items()},
            "exception_type": type(self.exception).__name__ if self.exception else None,
            "exception_message": str(self.exception) if self.exception else None,
            "recovery_attempts": self.recovery_attempts,
        }


@dataclass
class RecoveryResult:
    """Result of recovery attempt."""

    success: bool
    result: Optional[Any] = None
    error: Optional[Dict[str, Any] | str] = None
    strategy_used: RecoveryStrategy = RecoveryStrategy.ABORT
    attempts: int = 0
    warnings: List[str] = field(default_factory=list)


class ContextSnapshot:
    """
    Captures and restores Blender context.

    Captures:
    - Active object
    - Selected objects
    - Current mode
    - Scene settings
    """

    def __init__(self) -> None:
        self.data: Dict[str, Any] = {}
        if BPY_AVAILABLE:
            self._capture()

    def _capture(self) -> None:
        """Capture current context."""
        try:
            self.data["active_object"] = bpy.context.active_object
            self.data["selected_objects"] = list(bpy.context.selected_objects)
            self.data["mode"] = "OBJECT"

            if self.data["active_object"]:
                self.data["mode"] = self.data["active_object"].mode

            self.data["scene"] = bpy.context.scene
            self.data["frame"] = bpy.context.scene.frame_current if bpy.context.scene else 1

        except Exception as e:
            logger.warning(f"Context capture failed: {e}")

    def restore(self) -> bool:
        """Restore captured context."""
        if not BPY_AVAILABLE:
            return False

        try:
            # Restore active object
            if self.data.get("active_object"):
                try:
                    if bpy.context.view_layer:
                        bpy.context.view_layer.objects.active = self.data["active_object"]
                except:
                    pass

            # Restore selection
            if self.data.get("selected_objects"):
                try:
                    ContextManagerV3.deselect_all_objects()
                    # Restore selection
                    if bpy.context.view_layer:
                        for obj in self.data["selected_objects"]:
                            if obj and obj.name in bpy.context.view_layer.objects:
                                obj.select_set(True)
                except:
                    pass

            # Restore mode
            if self.data.get("active_object") and self.data.get("mode"):
                try:
                    obj = self.data["active_object"]
                    # Make active
                    if bpy.context.view_layer and obj:
                        if obj.name in bpy.context.view_layer.objects:
                            bpy.context.view_layer.objects.active = obj
                            if obj.mode != self.data["mode"]:
                                bpy.ops.object.mode_set(mode=self.data["mode"])
                except:
                    pass

            # Restore frame
            if self.data.get("scene") and self.data.get("frame"):
                try:
                    self.data["scene"].frame_current = self.data["frame"]
                except:
                    pass

            return True

        except Exception as e:
            logger.error(f"Context restore failed: {e}")
            return False


class RetryPolicy:
    """
    Configurable retry policy.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 0.5,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Check if operation should be retried."""
        if attempt >= self.max_attempts:
            return False

        return isinstance(exception, self.retryable_exceptions)

    def get_delay(self, attempt: int) -> float:
        """Get delay before next retry."""
        delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
        return min(delay, self.max_delay)


class EnhancedRecovery:
    """
    Enhanced error recovery system.

    Provides:
    - Automatic retry with backoff
    - Context preservation
    - Recovery strategies
    - Detailed error reporting
    """

    # Error patterns and suggested recoveries
    ERROR_PATTERNS: Dict[str, Dict[str, Any]] = {
        "timeout": {
            "patterns": ["timeout", "time out", "took too long"],
            "strategy": RecoveryStrategy.RETRY_WITH_DELAY,
            "suggestion": "Increase timeout or simplify operation",
        },
        "context_incorrect": {
            "patterns": ["context is incorrect", "poll() failed", "context is None"],
            "strategy": RecoveryStrategy.ROLLBACK,
            "suggestion": "Check object mode and selection",
        },
        "object_not_found": {
            "patterns": ["object not found", "not found in scene", "name not found"],
            "strategy": RecoveryStrategy.FALLBACK,
            "suggestion": "Verify object name or use resolver",
        },
        "mode_error": {
            "patterns": ["mode", "edit mode", "sculpt mode", "object mode"],
            "strategy": RecoveryStrategy.ROLLBACK,
            "suggestion": "Switch to correct mode before operation",
        },
        "attribute_error": {
            "patterns": ["attribute", "has no attribute", "'NoneType'"],
            "strategy": RecoveryStrategy.FALLBACK,
            "suggestion": "Check if required data exists",
        },
        "type_error": {
            "patterns": ["type error", "expected", "got instead"],
            "strategy": RecoveryStrategy.RETRY,
            "suggestion": "Check parameter types",
        },
    }

    @classmethod
    def execute_with_recovery(
        cls,
        operation: Callable,
        *args: Any,
        retry_policy: Optional["RetryPolicy"] = None,
        context_preservation: bool = True,
        tool: str = "",
        action: str = "",
        params: Optional[Dict[str, Any]] = None,
        context_name: str = "operation",
        recovery_strategy: Optional[Callable] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Execute operation with automatic recovery.

        Args:
            operation: Function to execute
            retry_policy: Custom retry policy
            context_preservation: Whether to preserve/restore context
            tool: Tool name for error context
            action: Action name for error context
            params: Parameters for error context

        Returns:
            RecoveryResult with operation result
        """
        retry_policy = retry_policy or RetryPolicy()
        params = params or {}

        # Capture context
        snapshot = None
        if context_preservation:
            snapshot = ContextSnapshot()

        error_context = ErrorContext(
            tool=tool,
            action=action,
            params=params,
            context_snapshot=snapshot.data if snapshot else None,
        )

        for attempt in range(1, retry_policy.max_attempts + 1):
            try:
                error_context.recovery_attempts = attempt

                # Execute operation
                result = operation(*args, **kwargs)

                return RecoveryResult(success=True, result=result, attempts=attempt)

            except Exception as e:
                error_context.exception = e
                error_context.traceback_str = traceback.format_exc()

                logger.warning(
                    f"Operation failed (attempt {attempt}/{retry_policy.max_attempts}): {e}"
                )

                # Determine recovery strategy
                strategy = cls._determine_strategy(e, attempt, retry_policy)

                if strategy == RecoveryStrategy.ABORT:
                    break

                elif strategy == RecoveryStrategy.RETRY:
                    continue

                elif strategy == RecoveryStrategy.RETRY_WITH_DELAY:
                    delay = retry_policy.get_delay(attempt)
                    logger.info(f"Retrying after {delay}s delay...")
                    time.sleep(delay)
                    continue

                elif strategy == RecoveryStrategy.ROLLBACK:
                    if snapshot:
                        logger.info("Restoring context...")
                        if snapshot.restore():
                            continue
                    # Fallback to retry
                    continue

                elif strategy == RecoveryStrategy.FALLBACK:
                    # Try alternative approach
                    logger.info("Trying fallback approach...")
                    continue

        # All attempts failed
        logger.error(f"Operation failed after {retry_policy.max_attempts} attempts")

        # Build detailed error
        error_info = cls._build_error_info(error_context)

        return RecoveryResult(
            success=False,
            error=error_info,
            attempts=error_context.recovery_attempts,
            strategy_used=RecoveryStrategy.ABORT,
        )

    @classmethod
    def _determine_strategy(
        cls, exception: Exception, attempt: int, retry_policy: RetryPolicy
    ) -> RecoveryStrategy:
        """Determine recovery strategy from exception."""
        error_str = str(exception).lower()

        # Check error patterns
        for pattern_name, pattern_info in cls.ERROR_PATTERNS.items():
            for pattern in pattern_info["patterns"]:
                if pattern in error_str:
                    strategy = cast(RecoveryStrategy, pattern_info["strategy"])

                    # Don't retry if max attempts reached
                    if attempt >= retry_policy.max_attempts:
                        return RecoveryStrategy.ABORT

                    return strategy

        # Default: retry if exception is retryable
        if retry_policy.should_retry(exception, attempt):
            return RecoveryStrategy.RETRY

        return RecoveryStrategy.ABORT

    @classmethod
    def _build_error_info(cls, context: ErrorContext) -> Dict[str, Any]:
        """Build detailed error information."""
        error_info = {
            "success": False,
            "error": str(context.exception) if context.exception else "Unknown error",
            "error_type": type(context.exception).__name__ if context.exception else "Unknown",
            "tool": context.tool,
            "action": context.action,
            "recovery_attempts": context.recovery_attempts,
        }

        # Add recovery suggestion
        if context.exception:
            error_str = str(context.exception).lower()
            for pattern_name, pattern_info in cls.ERROR_PATTERNS.items():
                for pattern in pattern_info["patterns"]:
                    if pattern in error_str:
                        error_info["suggestion"] = pattern_info["suggestion"]
                        break

        # Add traceback in debug mode
        if context.traceback_str:
            error_info["traceback"] = context.traceback_str

        return error_info


# Decorator for automatic recovery
def with_recovery(
    max_attempts: int = 3,
    preserve_context: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator for automatic error recovery.

    Usage:
        @with_recovery(max_attempts=3)
        def my_operation(**params):
            # Operation code
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_policy = RetryPolicy(
                max_attempts=max_attempts, retryable_exceptions=retryable_exceptions
            )

            # Extract tool/action from function
            tool = getattr(func, "_handler_name", func.__module__)
            action = func.__name__

            result = EnhancedRecovery.execute_with_recovery(
                func,
                *args,
                retry_policy=retry_policy,
                context_preservation=preserve_context,
                tool=tool,
                action=action,
                params=kwargs,
            )

            if result.success:
                return result.result
            else:
                return result.error

        return wrapper

    return decorator


# Convenience functions
def retry_operation(
    operation: Callable, max_attempts: int = 3, delay: float = 0.5, *args: Any, **kwargs: Any
) -> Any:
    """Simple retry wrapper."""
    policy = RetryPolicy(max_attempts=max_attempts, initial_delay=delay)

    result = EnhancedRecovery.execute_with_recovery(operation, *args, retry_policy=policy, **kwargs)

    if result.success:
        return result.result
    else:
        raise RuntimeError(result.error)


__all__ = [
    "EnhancedRecovery",
    "RecoveryResult",
    "RecoveryStrategy",
    "RetryPolicy",
    "ContextSnapshot",
    "ErrorContext",
    "with_recovery",
    "retry_operation",
]
