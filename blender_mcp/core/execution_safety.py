"""
High Mode Execution Safety Layer
Crash protection for dangerous bpy.ops operations.

Philosophy: No restrictions, but maximum stability.
- All bpy.ops calls wrapped in try-except
- Context validation before dangerous operations
- Graceful degradation on failure
"""

import functools
import traceback
from typing import Any, Callable, Dict, Optional, Tuple, cast
from .thread_safety import execute_on_main_thread, SafeOperators

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False


class ExecutionSafety:
    """Crash protection utilities for High Mode operations."""

    @staticmethod
    def safe_bpy_ops(
        operator_path: str,
        fallback_result: Optional[Any] = None,
        context_override: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[bool, Any]:
        """
        Safely execute a bpy.ops operator.

        Args:
            operator_path: e.g., "object.quadriflow_remesh", "object.bake"
            fallback_result: Return this on failure
            context_override: Context override dict for Blender 5.0+
            **kwargs: Operator parameters

        Returns:
            (success: bool, result: Any)
        """
        if not BPY_AVAILABLE:
            return False, "bpy not available"

        try:
            # Parse operator path (e.g., "object.quadriflow_remesh")
            parts = operator_path.split(".")
            if len(parts) != 2:
                return False, f"Invalid operator path: {operator_path}"

            ops_module = getattr(bpy.ops, parts[0], None)
            if not ops_module:
                return False, f"Unknown ops module: {parts[0]}"

            operator = getattr(ops_module, parts[1], None)
            if not operator:
                return False, f"Unknown operator: {parts[1]}"

            # Check if operator can run (poll)
            if hasattr(operator, "poll") and not operator.poll():
                return False, f"Operator {operator_path} cannot run in current context"

            # Execute with or without context override
            if context_override and hasattr(bpy.context, "temp_override"):
                # Blender 5.0+ temp_override
                with bpy.context.temp_override(**context_override):
                    result = execute_on_main_thread(operator, **kwargs)
            else:
                result = execute_on_main_thread(operator, **kwargs)

            return True, result

        except Exception as e:
            error_msg = f"{operator_path} failed: {str(e)}"
            print(f"[MCP Safety] {error_msg}")
            return False, error_msg

    @staticmethod
    def safe_mode_set(mode: str, object_name: Optional[str] = None) -> tuple[bool, str]:
        """
        Safely switch to edit/object mode.

        Returns:
            (success: bool, message: str)
        """
        if not BPY_AVAILABLE:
            return False, "bpy not available"

        try:
            obj = None
            if object_name:
                obj = bpy.data.objects.get(object_name)
            else:
                obj = bpy.context.active_object

            if not obj:
                return False, "No object found"

            # Already in desired mode
            if obj.mode == mode:
                return True, f"Already in {mode} mode"

            # Check if mode change is possible
            if obj.type not in ["MESH", "CURVE", "SURFACE", "META", "FONT", "ARMATURE"]:
                return False, f"Cannot set mode on {obj.type} objects"

            # Perform mode switch
            if bpy.context.view_layer:
                bpy.context.view_layer.objects.active = obj
            SafeOperators.mode_set(mode=mode)
            return True, f"Switched to {mode} mode"

        except Exception as e:
            return False, f"Mode switch failed: {str(e)}"

    @staticmethod
    def safe_render_engine_switch(engine: str) -> tuple[bool, str]:
        """Safely switch render engine with validation."""
        if not BPY_AVAILABLE:
            return False, "bpy not available"

        try:
            valid_engines = ["BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"]
            if engine not in valid_engines:
                return False, f"Invalid engine: {engine}. Use: {valid_engines}"

            scene = bpy.context.scene
            if not scene:
                return False, "No active scene"
            old_engine = scene.render.engine
            # Cast to Any to bypass Literal restriction in typed bpy
            cast(Any, scene.render).engine = engine

            return True, f"Switched from {old_engine} to {engine}"

        except Exception as e:
            return False, f"Engine switch failed: {str(e)}"

    @staticmethod
    def validate_context_for_bake() -> tuple[bool, str]:
        """Validate that baking can proceed safely."""
        if not BPY_AVAILABLE:
            return False, "bpy not available"

        try:
            scene = bpy.context.scene
            if not scene:
                return False, "No active scene"

            # Check render engine
            if scene.render.engine != "CYCLES":
                return False, "Baking requires Cycles render engine"

            # Check for active object
            if not bpy.context.active_object:
                return False, "No active object"

            # Check for UV layer
            obj = bpy.context.active_object
            if obj.type == "MESH" and not obj.data.uv_layers:
                return False, "Mesh has no UV layer"

            return True, "Context valid for baking"

        except Exception as e:
            return False, f"Context validation failed: {str(e)}"


def god_mode_safe(default_return: Any = None, log_errors: bool = True) -> Callable:
    """
    Decorator for High Mode safe execution.
    Catches ALL exceptions and returns default value.

    Usage:
        @god_mode_safe(default_return={"error": "Execution failed"})
        def dangerous_operation():
            bpy.ops.object.quadriflow_remesh()
            return {"success": True}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_detail = traceback.format_exc()
                if log_errors:
                    print(f"[MCP GodMode] {func.__name__} crashed: {e}")
                    print(error_detail)

                # Return default with error info
                if isinstance(default_return, dict):
                    result = default_return.copy()
                    result["error"] = str(e)
                    result["error_type"] = type(e).__name__
                    return result
                return default_return

        return wrapper

    return decorator


# Convenience exports
safe_ops = ExecutionSafety.safe_bpy_ops
safe_mode = ExecutionSafety.safe_mode_set
safe_engine = ExecutionSafety.safe_render_engine_switch
validate_bake = ExecutionSafety.validate_context_for_bake

__all__ = [
    "ExecutionSafety",
    "god_mode_safe",
    "safe_ops",
    "safe_mode",
    "safe_engine",
    "validate_bake",
]
