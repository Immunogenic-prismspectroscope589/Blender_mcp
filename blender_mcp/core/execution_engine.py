"""
Execution Engine for Blender MCP 1.0.0

Centralized, crash-safe operator execution with comprehensive safety checks.
All bpy.ops calls should go through this engine.

High Mode Philosophy: Maximum power with maximum safety.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple, Callable
import functools
from enum import Enum

try:
    import bpy

    BPY_AVAILABLE = True
    # Initial mock for SafeOps dynamic resolution
    if hasattr(bpy, "ops") and not hasattr(bpy.ops, "_mock"):
        pass
except ImportError:
    BPY_AVAILABLE = False

from .thread_safety import execute_on_main_thread, is_main_thread
from .context_manager_v3 import ContextManagerV3


@dataclass
class ExecutionResult:
    """
    Result of an operator execution.

    Attributes:
        success: Whether execution succeeded
        result: The operator return value (if success)
        error: Error message (if failed)
        error_code: Machine-readable error code
        alternatives: Suggested alternative approaches
    """

    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    alternatives: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        if self.success:
            return {"success": True, "result": self.result}
        else:
            result: Dict[str, Any] = {
                "success": False,
                "error": self.error,
                "code": self.error_code or "EXECUTION_ERROR",
            }
            if self.alternatives:
                result["alternatives"] = self.alternatives
            return result

    def to_error_dict(self) -> Dict[str, Any]:
        """Convert to error dictionary (convenience method)."""
        return self.to_dict()


class ExecutionMode(Enum):
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"


class DiffLevel(Enum):
    NONE = "NONE"
    BASIC = "BASIC"
    TRANSFORM = "TRANSFORM"
    FULL = "FULL"


@dataclass
class ExecutionPolicy:
    """Global execution policy."""

    mode: ExecutionMode = ExecutionMode.READ_WRITE
    diff_level: DiffLevel = DiffLevel.TRANSFORM

    _instance: Optional["ExecutionPolicy"] = None

    @classmethod
    def get(cls) -> "ExecutionPolicy":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_mode(cls, mode: ExecutionMode) -> None:
        cls.get().mode = mode

    @classmethod
    def set_diff_level(cls, level: DiffLevel) -> None:
        cls.get().diff_level = level


class ExecutionEngine:
    """
    High Mode Execution Engine - Maximum power, maximum safety.

    This class provides centralized operator execution with:
    - Context validation
    - Operator whitelist/blacklist
    - Poll checking
    - Comprehensive error handling
    - Alternative suggestions
    - Execution Policy Enforcement (Read-Only/DiffLevel)
    """

    # =========================================================================
    # MUTATION OPERATORS - Blocked in READ_ONLY mode
    # =========================================================================
    MUTATION_OPERATORS = {
        "object.delete",
        "object.join",
        "object.duplicate",
        "mesh.primitive_cube_add",
        "mesh.primitive_plane_add",
        "mesh.primitive_circle_add",
        "mesh.primitive_uv_sphere_add",
        "mesh.primitive_ico_sphere_add",
        "mesh.primitive_cylinder_add",
        "mesh.primitive_cone_add",
        "mesh.primitive_torus_add",
        "mesh.primitive_grid_add",
        "mesh.primitive_monkey_add",
        "object.modifier_add",
        "object.modifier_apply",
        "object.modifier_remove",
        "transform.translate",
        "transform.rotate",
        "transform.resize",
        "collection.create",
        "collection.objects_remove",
    }

    # =========================================================================
    # DANGEROUS OPERATORS - These crash in socket/headless mode
    # =========================================================================

    MODAL_OPERATORS = {
        # Interactive tools requiring UI
        "mesh.loopcut_slide",
        "mesh.knife_tool",
        "mesh.bisect",
        "transform.translate",
        "transform.rotate",
        "transform.resize",
        "transform.transform",
        "view3d.render_border",
        "view3d.zoom_border",
        "view3d.view_all",
        "view3d.view_selected",
        "view3d.snap_cursor_to_selected",
        "view3d.snap_cursor_to_center",
        # Paint modes
        "paint.brush_stroke",
        "paint.vertex_paint",
        "paint.texture_paint",
        "paint.weight_paint",
        "sculpt.brush_stroke",
    }

    UI_DEPENDENT_OPERATORS = {
        # Require specific UI areas
        "outliner.collection_new",
        "outliner.collection_delete",
        "outliner.collection_link",
        "outliner.collection_unlink",
        "outliner.collection_objects_select",
        "outliner.show_active",
        # Timeline/Dopesheet
        "action.clean",
        "action.sample",
        "action.unsnap",
        "graph.clean",
        "graph.sample",
        "graph.smooth",
        # UV Editor specific
        "uv.select",
        "uv.select_border",
        "uv.select_circle",
        "uv.select_lasso",
    }

    SCENE_DESTRUCTIVE_OPERATORS = {
        # Can crash if UI is active
        "wm.read_homefile",
        "wm.read_factory_settings",
        "wm.quit_blender",
    }

    # Combined dangerous set
    DANGEROUS_OPERATORS = MODAL_OPERATORS | UI_DEPENDENT_OPERATORS | SCENE_DESTRUCTIVE_OPERATORS

    # =========================================================================
    # SAFE ALTERNATIVES - When dangerous ops are blocked
    # =========================================================================

    OPERATOR_ALTERNATIVES = {
        "mesh.loopcut_slide": [
            "Use 'mesh.subdivide' for simple subdivision",
            "Use modifier-based subdivision (SUBSURF)",
            "Use 'manage_modeling' with mesh_operation='SUBDIVIDE'",
        ],
        "mesh.knife_tool": [
            "Use boolean operations for cutting",
            "Use 'mesh.bisect' with clear_inner/clear_outer",
            "Pre-cut in manual Blender UI session",
        ],
        "transform.translate": [
            "Set obj.location directly",
            "Use 'manage_modeling' with action='TRANSFORM'",
            "Use bpy.ops.transform.translate with view context",
        ],
        "wm.read_homefile": [
            "Create new scene data with bpy.data.scenes.new()",
            "Clear current scene objects manually",
            "Restart Blender for completely fresh file",
        ],
        "paint.brush_stroke": [
            "Use direct mesh manipulation",
            "Use sculpting modifiers",
            "Paint in manual Blender UI session",
        ],
    }

    @classmethod
    def _get_operator(cls, operator_path: str) -> Optional[Any]:
        """
        Safely get operator reference.

        Args:
            operator_path: e.g., "object.mode_set"

        Returns:
            Operator or None
        """
        if not BPY_AVAILABLE:
            return None

        try:
            parts = operator_path.split(".")
            if len(parts) != 2:
                return None

            ops_module = getattr(bpy.ops, parts[0], None)
            if not ops_module:
                return None

            return getattr(ops_module, parts[1], None)
        except Exception:
            return None

    @staticmethod
    def _invoke_operator(
        operator: Any, params: Dict[str, Any], exec_context: Optional[str] = None
    ) -> Any:
        """
        Invoke a Blender operator with optional execution context.
        Blender operators accept exec_context ('EXEC_DEFAULT', 'INVOKE_DEFAULT', etc.)
        as the first positional argument only; it cannot be passed as keyword.
        """
        if exec_context:
            return operator(exec_context, **params)
        return operator(**params)

    @classmethod
    def check_poll(cls, operator_path: str) -> Tuple[bool, Optional[str]]:
        """Check if operator can run in current context."""
        operator = cls._get_operator(operator_path)
        if operator is None:
            return False, "Operator not found"

        try:
            if hasattr(operator, "poll"):
                if operator.poll():
                    return True, None
                else:
                    return False, f"{operator_path}.poll() returned False"
            # No poll method means it can probably run
            return True, None
        except Exception as e:
            return False, f"Poll check failed: {str(e)}"

    @classmethod
    def execute(
        cls,
        operator_path: str,
        params: Optional[Dict[str, Any]] = None,
        context_override: Optional[Dict[str, Any]] = None,
        exec_context: Optional[str] = None,
        allow_dangerous: bool = False,
        check_context: bool = True,
    ) -> ExecutionResult:
        """
        Execute operator with full safety checks.

        This is the MAIN entry point for all operator execution.

        Args:
            operator_path: e.g., "object.mode_set", "mesh.primitive_cube_add"
            params: Operator parameters
            context_override: Context override dict for temp_override
            allow_dangerous: Allow modal/UI-dependent operators (use with caution)
            check_context: Validate context before execution

        Returns:
            ExecutionResult with success status and details

        Examples:
            # Safe operation
            result = ExecutionEngine.execute(
                "mesh.primitive_cube_add",
                params={"size": 2, "location": (0, 0, 0)}
            )

            # Mode switch
            result = ExecutionEngine.execute(
                "object.mode_set",
                params={"mode": "EDIT"}
            )

            if result.success:
                print("Success!")
            else:
                print(f"Failed: {result.error}")
                print(f"Try: {result.alternatives}")
        """
        params = params or {}

        # 0. Check Execution Policy
        policy = ExecutionPolicy.get()
        if policy.mode == ExecutionMode.READ_ONLY:
            # Check against explicit mutation list
            if operator_path in cls.MUTATION_OPERATORS:
                return ExecutionResult(
                    success=False,
                    error=f"Operator '{operator_path}' is blocked in READ_ONLY mode.",
                    error_code="POLICY_VIOLATION_READ_ONLY",
                    alternatives=["Switch ExecutionPolicy to READ_WRITE"],
                )

            # Heuristic: Block all 'ops.mesh' and 'ops.transform' if not explicitly safe?
            # For now, rely on MUTATION_OPERATORS list as per plan.

        # 1. Validate context
        if check_context:
            is_valid, error = ContextManagerV3.validate_context(
                require_scene=True, require_object=False
            )
            if not is_valid:
                # Mypy guard
                err_msg = error.message if error else "Unknown context error"
                err_code = error.code if error else "CONTEXT_ERROR"
                err_alts = error.alternatives if error else []

                return ExecutionResult(
                    success=False, error=err_msg, error_code=err_code, alternatives=err_alts
                )

        # 2. Check if operator is dangerous
        if not allow_dangerous and operator_path in cls.DANGEROUS_OPERATORS:
            return ExecutionResult(
                success=False,
                error=f"'{operator_path}' is blocked in socket mode (requires UI interaction)",
                error_code="MODAL_OPERATOR_BLOCKED",
                alternatives=cls.OPERATOR_ALTERNATIVES.get(
                    operator_path,
                    [
                        "Use non-interactive alternatives",
                        "Perform this operation in Blender UI manually",
                    ],
                ),
            )

        # 3. Get operator
        operator = cls._get_operator(operator_path)
        if operator is None:
            return ExecutionResult(
                success=False,
                error=f"Operator '{operator_path}' not found",
                error_code="OPERATOR_NOT_FOUND",
            )

        # 4. Check poll
        can_run, poll_reason = cls.check_poll(operator_path)
        if not can_run:
            return ExecutionResult(
                success=False,
                error=f"Cannot execute '{operator_path}': {poll_reason}",
                error_code="POLL_FAILED",
                alternatives=[
                    "Check object type and mode",
                    "Verify required context exists",
                    "Check if object is selected",
                ],
            )

        # 5. Execute
        try:
            # Automatic Thread Safety
            if not is_main_thread() and BPY_AVAILABLE:

                def _threaded_exec() -> Any:
                    if context_override and hasattr(bpy.context, "temp_override"):
                        with bpy.context.temp_override(**context_override):
                            return cls._invoke_operator(operator, params, exec_context)
                    else:
                        return cls._invoke_operator(operator, params, exec_context)

                result = execute_on_main_thread(_threaded_exec, timeout=30.0)
            else:
                if context_override and hasattr(bpy.context, "temp_override"):
                    with bpy.context.temp_override(**context_override):
                        result = cls._invoke_operator(operator, params, exec_context)
                else:
                    result = cls._invoke_operator(operator, params, exec_context)

            return ExecutionResult(success=True, result=result)

        except RuntimeError as e:
            # Common operator errors
            error_str = str(e)

            if "context is incorrect" in error_str.lower():
                return ExecutionResult(
                    success=False,
                    error=f"Context error: {error_str}",
                    error_code="CONTEXT_ERROR",
                    alternatives=[
                        "Check object is in correct mode",
                        "Verify object type supports this operation",
                        "Ensure required data exists (UVs, materials)",
                    ],
                )

            if "poll()" in error_str.lower():
                return ExecutionResult(
                    success=False,
                    error=f"Poll failed: {error_str}",
                    error_code="POLL_FAILED",
                    alternatives=["Check operator requirements", "Verify context is valid"],
                )

            return ExecutionResult(
                success=False, error=f"Runtime error: {error_str}", error_code="RUNTIME_ERROR"
            )

    @classmethod
    def _safe_execute_wrapper(cls, operator: Any, params: Dict[str, Any]) -> Any:
        """Wrapper for main thread execution."""
        return operator(**params)

    @classmethod
    def execute_safe(cls, operator_path: str, **params: Any) -> ExecutionResult:
        """
        Streamlined execution method for SafeOps proxy.
        Automatically handles thread safety and context.
        """
        return cls.execute(operator_path, params=params)

    @classmethod
    def execute_batch(
        cls, operations: List[Tuple[str, Dict[str, Any]]], stop_on_error: bool = True
    ) -> List[ExecutionResult]:
        """
        Execute multiple operators in batch.

        Args:
            operations: List of (operator_path, params) tuples
            stop_on_error: Stop if any operation fails

        Returns:
            List of ExecutionResults
        """
        results = []

        for op_path, params in operations:
            result = cls.execute(op_path, params)
            results.append(result)

            if not result.success and stop_on_error:
                break

        return results

    @classmethod
    def is_safe(cls, operator_path: str) -> Tuple[bool, Optional[str]]:
        """
        Check if operator is safe to run in socket mode.

        Args:
            operator_path: Operator to check

        Returns:
            Tuple of (is_safe, reason_if_not)
        """
        if operator_path in cls.DANGEROUS_OPERATORS:
            if operator_path in cls.MODAL_OPERATORS:
                return False, "Modal operator requires UI interaction"
            elif operator_path in cls.UI_DEPENDENT_OPERATORS:
                return False, "Requires specific UI context"
            elif operator_path in cls.SCENE_DESTRUCTIVE_OPERATORS:
                return False, "Can crash active UI session"

        return True, None


# ============================================================================
# DECORATORS
# ============================================================================


def safe_execute(
    operator_path: Optional[str] = None,
    fallback_result: Optional[Dict[str, Any]] = None,
    allow_dangerous: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to wrap function in execution safety.

    Usage:
        @safe_execute("mesh.primitive_cube_add")
        def create_cube(size=1.0):
            return {"size": size}

        Or:
        @safe_execute()
        def my_function():
            # Multiple operations
            pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_result = fallback_result or {"error": str(e)}
                error_result["success"] = False
                error_result["error_type"] = type(e).__name__
                return error_result

        return wrapper

    return decorator


def require_context(
    require_scene: bool = True, require_object: bool = False
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to ensure valid context before execution.

    Usage:
        @require_context(require_scene=True, require_object=True)
        def edit_mesh(obj_name: str):
            # This will only run if context is valid
            pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            is_valid, error = ContextManagerV3.validate_context(
                require_scene=require_scene, require_object=require_object
            )
            if not is_valid:
                return error.to_dict() if error else {"error": "Unknown context error"}
            return func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def safe_mode_set(mode: str, obj: Optional[Any] = None) -> ExecutionResult:
    """
    Safely switch to specified mode.

    Args:
        mode: Target mode (OBJECT, EDIT, SCULPT, etc.)
        obj: Target object (or active object if None)

    Returns:
        ExecutionResult
    """
    target = obj or ContextManagerV3.get_active_object()
    if target is None:
        return ExecutionResult(
            success=False, error="No active object", error_code="NO_ACTIVE_OBJECT"
        )

    if target.mode == mode:
        return ExecutionResult(success=True, result="Already in mode")

    # Set active first
    ContextManagerV3.set_active_object(target)

    return ExecutionEngine.execute("object.mode_set", params={"mode": mode})


def safe_delete(objects: List[Any], use_global: bool = False) -> ExecutionResult:
    """
    Safely delete objects.

    Args:
        objects: List of objects to delete
        use_global: Delete from all scenes

    Returns:
        ExecutionResult
    """
    if not objects:
        return ExecutionResult(success=True, result="No objects to delete")

    # Deselect all
    ContextManagerV3.deselect_all_objects()

    # Select targets
    for obj in objects:
        if obj and obj.name in bpy.data.objects:
            obj.select_set(True)

    # Delete
    return ExecutionEngine.execute("object.delete", params={"use_global": use_global})


class SafeOps:
    """
    Dynamic Proxy for bpy.ops to ensure safety.

    Usage:
        SafeOps.mesh.primitive_cube_add(size=2)
        SafeOps.object.mode_set(mode='EDIT')
    """

    class _OpCategory:
        def __init__(self, category: str) -> None:
            self.category = category

        def __getattr__(self, name: str) -> Any:
            def wrapper(**kwargs: Any) -> ExecutionResult:
                exec_ctx = kwargs.pop("_exec_context", None)
                op_path = f"{self.category}.{name}"
                result = ExecutionEngine.execute(op_path, params=kwargs, exec_context=exec_ctx)
                return result

            return wrapper

    _instance = None

    def __new__(cls) -> "SafeOps":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __getattr__(self, name: str) -> "_OpCategory":
        return self._OpCategory(name)


# Global Instance
safe_ops = SafeOps()

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ExecutionResult",
    "ExecutionEngine",
    "safe_execute",
    "require_context",
    "safe_mode_set",
    "safe_delete",
    "SafeOps",
    "safe_ops",
]
