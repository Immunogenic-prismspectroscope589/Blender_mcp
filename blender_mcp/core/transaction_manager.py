"""
Transaction Manager for Blender MCP
"Atomic Execution or Nothing."

Ensures that operations are atomic. If an operation fails,
the system rolls back to the state before the operation started.

High Mode Philosophy:
"Do or do not. There is no try (and leave broken state)."
"""

from typing import Optional, Literal, Any
from .logging_config import get_logger

logger = get_logger()

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]


class TransactionManager:
    """
    Context manager for atomic execution.

    Usage:
        with TransactionManager("Create Cube"):
            bpy.ops.mesh.primitive_cube_add()
            raise Exception("Oops") # Trigger rollback
    """

    # Static flag to handle nested transactions (Flat Transaction Model)
    _active_transaction: Optional[str] = None

    def __init__(self, label: str = "MCP Transaction"):
        self.label = label
        self.is_root = False
        self.failed = False

    def __enter__(self) -> "TransactionManager":
        if not BPY_AVAILABLE:
            return self

        # Flat Transaction: Only the root transaction pushes undo
        if TransactionManager._active_transaction is None:
            self.is_root = True
            TransactionManager._active_transaction = self.label

            try:
                # Push Undo Step (Checkpoint)
                # using SafeOperators? No, undo_push is usually safe on main thread (where we execute)
                # SafeOperators.undo_push(message=self.label) # SafeOperators doesn't have undo_push yet
                bpy.ops.ed.undo_push(message=self.label)
                logger.debug(f"[Transaction] Started: {self.label}")
            except Exception as e:
                logger.error(f"[Transaction] Failed to push undo: {e}")
                # If we can't push undo, we can't guarantee atomicity.
                # Should we abort? Yes, per "Hardening" rules.
                raise RuntimeError(f"Could not start transaction '{self.label}': {e}")
        else:
            logger.debug(
                f"[Transaction] Nested start: {self.label} inside {TransactionManager._active_transaction}"
            )

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        if not BPY_AVAILABLE:
            return False

        if exc_type is not None:
            self.failed = True
            logger.error(f"[Transaction] Error during '{self.label}': {exc_val}")

        if self.is_root:
            try:
                if self.failed:
                    logger.warning(f"[Transaction] Rolling back: {self.label}")
                    bpy.ops.ed.undo()

                    # Trigger Identity Rebuild (Placeholder for P19.4)
                    # from .identity_manager import IdentityManager
                    # IdentityManager.rebuild()
                else:
                    logger.debug(f"[Transaction] Committed: {self.label}")
            except Exception as e:
                logger.critical(f"[Transaction] CRITICAL: Rollback failed for '{self.label}': {e}")
            finally:
                TransactionManager._active_transaction = None

        # Propagate exception
        return False
