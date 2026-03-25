"""
Manage Objects - V1.0.0 Refactored (SSOT)

Safe object lifecycle management with strict typing and enum-based actions.
Implements Rules 1 (SSOT), 2 (Strict Typing), and 9 (Zero Trust Input).
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast
from collections.abc import Iterable  # Bug 4 Fix

if TYPE_CHECKING:
    import bpy
    import mathutils

    BPY_AVAILABLE = True
else:
    try:
        import bpy
        import mathutils

        BPY_AVAILABLE = True
    except ImportError:
        BPY_AVAILABLE = False
        bpy = None
        mathutils = None

from ..core.resolver import resolve_name
from ..core.thread_safety import execute_on_main_thread, SafeOperators
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..dispatcher import register_handler

# SSOT Imports
from ..core.enums import ObjectAction, ObjectOrigin
from ..core.constants import ObjectDefaults
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_objects",
    priority=11,
    schema={
        "type": "object",
        "title": "Object Manager (CORE)",
        "description": (
            "CORE — Object-level operations: rename, delete, duplicate, join, parent/unparent, "
            "hide/show, transform.\n\n"
            "Use after execute_blender_code creates objects, or to manage existing objects.\n"
            "PARENTING WARNING: After parenting, child.location becomes parent-relative. "
            "Always use world_location (not location) to verify absolute positions.\n"
            "ACTIONS: RENAME, DELETE, DUPLICATE, JOIN, PARENT, CLEAR_PARENT, TRANSFORM, HIDE, SHOW"
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "RENAME",
                    "DELETE",
                    "DUPLICATE",
                    "JOIN",
                    "PARENT",
                    "CLEAR_PARENT",
                    "SET_ORIGIN",
                    "TRANSFORM",
                    "LIST",
                    "GET_INFO",
                ],
                "description": "Object operation action",
            },
            "object_name": {"type": "string", "description": "Target object name (for TRANSFORM)"},
            "location": {
                "type": "array",
                "items": {"type": "number"},
                "description": "New location [x, y, z]",
            },
            "rotation": {
                "type": "array",
                "items": {"type": "number"},
                "description": "New rotation euler [x, y, z] (radians)",
            },
            "scale": {
                "type": "array",
                "items": {"type": "number"},
                "description": "New scale [x, y, z]",
            },
            "name": {
                "type": "string",
                "description": "Current object name (for RENAME/DELETE/PARENT)",
            },
            "new_name": {"type": "string", "description": "New name (for RENAME)"},
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of object names (for DELETE/DUPLICATE/JOIN)",
            },
            "target": {"type": "string", "description": "Target parent object (for PARENT)"},
            "keep_transform": {
                "type": "boolean",
                "description": "Keep transform when clearing parent",
            },
            "origin_type": ValidationUtils.generate_enum_schema(ObjectOrigin, "Origin set mode"),
        },
        "required": ["action"],
    },
    actions=[
        "RENAME",
        "DELETE",
        "DUPLICATE",
        "JOIN",
        "PARENT",
        "CLEAR_PARENT",
        "SET_ORIGIN",
        "TRANSFORM",
        "LIST",
        "GET_INFO",
    ],
    category="objects",
)
def manage_objects(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Manage Object Lifecycle and Hierarchy.

    Strictly typed handler for basic object operations.
    """
    # 1. Zero Trust Input Validation
    if not action:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=None,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    # Validate Action Enum
    validation_error = ValidationUtils.validate_enum(action, ObjectAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(validation_error, handler="manage_objects", action=action)

    try:
        # 2. Dispatch to Sub-Handlers
        if action == ObjectAction.RENAME.value:
            return _handle_rename(**params)
        elif action == ObjectAction.DELETE.value:
            return _handle_delete(**params)
        elif action == ObjectAction.DUPLICATE.value:
            return _handle_duplicate(**params)
        elif action == ObjectAction.JOIN.value:
            return _handle_join(**params)
        elif action == ObjectAction.PARENT.value:
            return _handle_parent(**params)
        elif action == ObjectAction.CLEAR_PARENT.value:
            return _handle_clear_parent(**params)
        elif action == ObjectAction.SET_ORIGIN.value:
            return _handle_set_origin(**params)
        elif action == ObjectAction.TRANSFORM.value:
            return _handle_transform(**params)
        elif action == ObjectAction.LIST.value:
            return _handle_list(**params)
        elif action == ObjectAction.GET_INFO.value:
            return _handle_get_info(**params)
        else:
            # Should be unreachable due to validate_enum, but safe fallback
            return ResponseBuilder.error(
                handler="manage_objects",
                action=action,
                error_code="INVALID_ACTION",
                message=f"Unknown action: {action}",
            )

    except Exception as e:
        logger.error(f"manage_objects.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_objects", action=action, error_code="EXECUTION_ERROR", message=str(e)
        )


def _handle_list(**params: Any) -> Dict[str, Any]:
    """Handle LIST action."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.LIST.value,
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    names = [obj.name for obj in bpy.data.objects]
    return ResponseBuilder.success(
        handler="manage_objects",
        action=ObjectAction.LIST.value,
        data={"count": len(names), "objects": names},
    )


def _handle_get_info(**params: Any) -> Dict[str, Any]:
    """Handle GET_INFO action."""
    obj_name = params.get("name") or params.get("object_name")
    if not obj_name:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.GET_INFO.value,
            error_code="MISSING_PARAMETER",
            message="name parameter required for GET_INFO",
        )

    obj = resolve_name(obj_name)
    if not obj:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.GET_INFO.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{obj_name}' not found",
        )

    info = {
        "name": obj.name,
        "type": obj.type,
        "location": list(cast(Iterable[float], obj.location)),
        "rotation": list(cast(Iterable[float], obj.rotation_euler)),
        "scale": list(cast(Iterable[float], obj.scale)),
        "parent": obj.parent.name if obj.parent else None,
        "visible": not obj.hide_viewport,
    }
    return ResponseBuilder.success(
        handler="manage_objects", action=ObjectAction.GET_INFO.value, data=info
    )


def _handle_rename(**params: Any) -> Dict[str, Any]:
    """Handle RENAME action."""
    old_name = params.get("name")
    new_name = params.get("new_name")

    if not old_name or not new_name:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.RENAME.value,
            error_code="MISSING_PARAMETER",
            message="Both 'name' and 'new_name' required",
        )

    obj = resolve_name(old_name)
    if not obj:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.RENAME.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{old_name}' not found",
        )

    try:
        # Property access is thread-safe for basic types, but better safe
        def rename_op() -> str:
            obj.name = new_name
            return str(obj.name)

        final_name = cast(str, execute_on_main_thread(rename_op))

        return ResponseBuilder.success(
            handler="manage_objects",
            action=ObjectAction.RENAME.value,
            data={"old_name": old_name, "new_name": final_name},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.RENAME.value,
            error_code="EXECUTION_ERROR",
            message=f"Rename failed: {str(e)}",
        )


def _handle_delete(**params: Any) -> Dict[str, Any]:
    """Handle DELETE action."""
    names = params.get("names", [])
    name = params.get("name")

    if name:
        names.append(name)

    if not names:
        # Delete selected objects
        try:

            def delete_selected() -> None:
                SafeOperators.delete()

            execute_on_main_thread(delete_selected, timeout=ObjectDefaults.DEFAULT_TIMEOUT)
            return ResponseBuilder.success(
                handler="manage_objects",
                action=ObjectAction.DELETE.value,
                data={"message": "Deleted selected objects"},
            )
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_objects",
                action=ObjectAction.DELETE.value,
                error_code="EXECUTION_ERROR",
                message=f"Delete failed: {str(e)}",
            )

    # Delete by name
    count = 0
    errors: List[str] = []

    def delete_by_names() -> Tuple[int, List[str]]:
        local_count = 0
        local_errors: List[str] = []
        for n in names:
            obj = resolve_name(n)
            if obj:
                try:
                    # Remove from main database properly
                    # Mypy doesn't know bpy.data.objects.remove, so we ignore or cast
                    # But since we are strictly typing, we assume bpy is available here
                    if bpy:
                        bpy.data.objects.remove(obj, do_unlink=True)
                    local_count += 1
                except Exception as e:
                    local_errors.append(f"{n}: {e}")
            else:
                local_errors.append(f"{n}: not found")
        return local_count, local_errors

    try:
        count, errors = cast(
            Tuple[int, List[str]],
            execute_on_main_thread(delete_by_names, timeout=ObjectDefaults.DEFAULT_TIMEOUT),
        )
        return ResponseBuilder.success(
            handler="manage_objects",
            action=ObjectAction.DELETE.value,
            data={"deleted_count": count, "errors": errors if errors else None},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.DELETE.value,
            error_code="EXECUTION_ERROR",
            message=f"Delete execution failed: {str(e)}",
        )


def _handle_duplicate(**params: Any) -> Dict[str, Any]:
    """Handle DUPLICATE action."""
    names = params.get("names", [])

    def duplicate_objects() -> List[str]:
        # Setup selection for duplication
        if names:
            ContextManagerV3.deselect_all_objects()
            objs_to_dup = []
            for name in names:
                obj = resolve_name(name)
                if obj:
                    obj.select_set(True)
                    objs_to_dup.append(obj)

            # ContextManagerV3 ensures proper context for ops
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D",
                active_object=objs_to_dup[0] if objs_to_dup else None,
                selected_objects=objs_to_dup,
            ):
                safe_ops.object.duplicate()
        else:
            # Duplicate current selection
            # mypy complains about ContextManagerV3 args not matching exactly if strict
            current_selected = list(bpy.context.selected_objects) if bpy else []
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", selected_objects=current_selected
            ):
                safe_ops.object.duplicate()

        # Return duplicated objects (now selected)
        duplicated = [o.name for o in ContextManagerV3.get_selected_objects()]
        return duplicated

    try:
        result = cast(
            List[str],
            execute_on_main_thread(duplicate_objects, timeout=ObjectDefaults.DEFAULT_TIMEOUT),
        )
        return ResponseBuilder.success(
            handler="manage_objects",
            action=ObjectAction.DUPLICATE.value,
            data={"duplicated_objects": result},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.DUPLICATE.value,
            error_code="EXECUTION_ERROR",
            message=f"Duplicate failed: {str(e)}",
        )


def _handle_join(**params: Any) -> Dict[str, Any]:
    """Handle JOIN action."""
    names = params.get("names", [])

    if len(names) < 2:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.JOIN.value,
            error_code="MISSING_PARAMETER",
            message="At least two objects required for JOIN",
        )

    def join_objects() -> str:
        # Last object is active (target)
        active_name = names[-1]
        active_obj = resolve_name(active_name)

        if not active_obj:
            raise ValueError(f"Active object '{active_name}' not found")

        # Select all objects to join
        ContextManagerV3.deselect_all_objects()

        joined_names = []
        for n in names:
            o = resolve_name(n)
            if o:
                o.select_set(True)
                joined_names.append(o.name)

        # Use Standard Context Manager
        ContextManagerV3.set_active_object(active_obj)
        # mypy safe list conversion
        sel_objs = list(bpy.context.selected_objects) if bpy else []
        with ContextManagerV3.temp_override(active_object=active_obj, selected_objects=sel_objs):
            SafeOperators.join()

        return str(active_obj.name)

    try:
        result = cast(
            str, execute_on_main_thread(join_objects, timeout=ObjectDefaults.EXTENDED_TIMEOUT)
        )
        return ResponseBuilder.success(
            handler="manage_objects", action=ObjectAction.JOIN.value, data={"joined_object": result}
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.JOIN.value,
            error_code="EXECUTION_ERROR",
            message=f"Join failed: {str(e)}",
        )


def _handle_parent(**params: Any) -> Dict[str, Any]:
    """Handle PARENT action."""
    child_name = params.get("name")
    parent_name = params.get("target")

    if not child_name or not parent_name:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.PARENT.value,
            error_code="MISSING_PARAMETER",
            message="Both 'name' (child) and 'target' (parent) required",
        )

    def parent_op() -> Tuple[str, str]:
        child = resolve_name(child_name)
        parent = resolve_name(parent_name)

        if not child or not parent:
            raise ValueError("One or both objects not found")

        child.parent = parent
        child.matrix_parent_inverse = parent.matrix_world.inverted()
        return child.name, parent.name

    try:
        c_name, p_name = cast(Tuple[str, str], execute_on_main_thread(parent_op))
        return ResponseBuilder.success(
            handler="manage_objects",
            action=ObjectAction.PARENT.value,
            data={"child": c_name, "parent": p_name},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.PARENT.value,
            error_code="EXECUTION_ERROR",
            message=f"Parenting failed: {str(e)}",
        )


def _handle_clear_parent(**params: Any) -> Dict[str, Any]:
    """Handle CLEAR_PARENT action."""
    obj_name = params.get("name")

    keep_transform = params.get("keep_transform", True)

    def clear_parent_op() -> str:
        obj = resolve_name(obj_name) if obj_name else ContextManagerV3.get_active_object()
        if not obj:
            raise ValueError("No active object found")

        ContextManagerV3.set_active_object(obj)

        with ContextManagerV3.temp_override(area_type="VIEW_3D", active_object=obj):
            if keep_transform:
                safe_ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
            else:
                safe_ops.object.parent_clear(type="CLEAR")
        return str(obj.name)

    try:
        obj_processed = cast(
            str, execute_on_main_thread(clear_parent_op, timeout=ObjectDefaults.DEFAULT_TIMEOUT)
        )
        return ResponseBuilder.success(
            handler="manage_objects",
            action=ObjectAction.CLEAR_PARENT.value,
            data={"object": obj_processed, "keep_transform": keep_transform},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.CLEAR_PARENT.value,
            error_code="EXECUTION_ERROR",
            message=f"Clear parent failed: {str(e)}",
        )


def _handle_set_origin(**params: Any) -> Dict[str, Any]:
    """Handle SET_ORIGIN action."""
    obj_name = params.get("name")
    origin_type = params.get("origin_type", ObjectOrigin.GEOMETRY_ORIGIN.value)

    # Validate Origin Enum
    val_err = ValidationUtils.validate_enum(origin_type, ObjectOrigin, "origin_type")
    if val_err:
        return ResponseBuilder.from_error(
            val_err, handler="manage_objects", action=ObjectAction.SET_ORIGIN.value
        )

    def set_origin_op() -> str:
        obj = resolve_name(obj_name) if obj_name else ContextManagerV3.get_active_object()
        if not obj:
            raise ValueError("No active object found")

        ContextManagerV3.set_active_object(obj)
        with ContextManagerV3.temp_override(area_type="VIEW_3D", active_object=obj):
            safe_ops.object.origin_set(type=origin_type, center="MEDIAN")
        return str(obj.name)

    try:
        obj_processed = cast(
            str, execute_on_main_thread(set_origin_op, timeout=ObjectDefaults.DEFAULT_TIMEOUT)
        )
        return ResponseBuilder.success(
            handler="manage_objects",
            action=ObjectAction.SET_ORIGIN.value,
            data={"object": obj_processed, "origin_type": origin_type},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.SET_ORIGIN.value,
            error_code="EXECUTION_ERROR",
            message=f"Set origin failed: {str(e)}",
        )


def _handle_transform(**params: Any) -> Dict[str, Any]:
    """
    Apply location, rotation, and scale to an object.
    """
    # Fix Semantic Ambiguity (RSK-102): fallback chain
    obj_name = params.get("object_name") or params.get("name")

    def transform_op() -> Dict[str, Any]:
        # Strict validation: Do not fall back to active_object if missing
        obj = resolve_name(obj_name) if obj_name else None
        if not obj:
            raise ValueError(
                f"Object '{obj_name}' not found. Provide a valid 'object_name' or 'name' for TRANSFORM."
            )

        if "location" in params:
            obj.location = mathutils.Vector(params["location"])
        if "rotation" in params:
            obj.rotation_euler = mathutils.Euler(params["rotation"])
        if "scale" in params:
            obj.scale = mathutils.Vector(params["scale"])

        return {
            "object": str(obj.name),
            "location": list(cast(Iterable[float], obj.location)) if obj.location else [],
            "rotation": (
                list(cast(Iterable[float], obj.rotation_euler)) if obj.rotation_euler else []
            ),
            "scale": list(cast(Iterable[float], obj.scale)) if obj.scale else [],
        }

    try:
        result = cast(Dict[str, Any], execute_on_main_thread(transform_op))
        return ResponseBuilder.success(
            handler="manage_objects", action=ObjectAction.TRANSFORM.value, data=result
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_objects",
            action=ObjectAction.TRANSFORM.value,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )
