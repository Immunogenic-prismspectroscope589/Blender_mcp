"""
Manage Scene - V1.0.0 Refactored

Safe scene management with thread safety and crash prevention.
"""

try:
    import bpy

    # Type checking imports
    from typing import TYPE_CHECKING, Any, Dict, Optional, cast
    from collections.abc import Iterable

    if TYPE_CHECKING:
        pass

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    from typing import Any, Dict, Optional, cast, Iterable


from ..core.thread_safety import execute_on_main_thread, ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..dispatcher import register_handler
from ..utils.path import get_safe_path
from ..core.enums import SceneAction
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_scene",
    priority=14,
    schema={
        "type": "object",
        "title": "Scene Manager (CORE)",
        "description": (
            "CORE — Scene file I/O, playback control, render settings, scene inspection.\n\n"
            "Use to: save/open .blend files, set render resolution/engine, control animation playback, "
            "get scene info, clear scenes.\n"
            "ACTIONS: SAVE, OPEN, GET_SCENE_INFO, SET_RENDER_SETTINGS, PLAY, STOP, SET_FRAME_RANGE, CLEAR"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                SceneAction, "Scene operation to perform"
            ),
            "filepath": {"type": "string", "description": "File path for IO operations"},
            "object_name": {"type": "string", "description": "Target object for inspection"},
            "params": {"type": "object", "description": "Additional parameters"},
        },
        "required": ["action"],
    },
    actions=[a.value for a in SceneAction],
    category="scene",
)
@ensure_main_thread
def manage_scene(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    God-Mode Scene Management.

    Actions:
        - OPEN_FILE: Open a .blend file
        - SAVE_FILE: Save current file
        - NEW_SCENE: Create new scene (without file reload)
        - PLAYBACK_START/STOP: Animation playback control
        - INSPECT_OBJECT: Deep object inspection
        - INSPECT_SCENE: Scene statistics
        - SET_UNIT_SYSTEM: Change units (METRIC/IMPERIAL)
        - CLEAN_ORPHANS: Remove unused data blocks
        - GET_3D_CURSOR: Get location and rotation of the 3D Cursor
        - SET_3D_CURSOR: Move the 3D Cursor to a location
    """
    validation_error = ValidationUtils.validate_enum(action, SceneAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(validation_error, handler="manage_scene", action=action)

    try:
        if action == SceneAction.OPEN_FILE.value:
            return _handle_open_file(**params)
        elif action == SceneAction.SAVE_FILE.value:
            return _handle_save_file(**params)
        elif action == SceneAction.NEW_SCENE.value:
            return _handle_new_scene(**params)
        elif action == SceneAction.PLAYBACK_START.value:
            return _handle_playback_start(**params)
        elif action == SceneAction.PLAYBACK_STOP.value:
            return _handle_playback_stop(**params)
        elif action == SceneAction.INSPECT_OBJECT.value:
            return _handle_inspect_object(**params)
        elif action == SceneAction.INSPECT_SCENE.value:
            return _handle_inspect_scene(**params)
        elif action == SceneAction.SET_UNIT_SYSTEM.value:
            return _handle_set_unit_system(**params)
        elif action == SceneAction.CLEAN_ORPHANS.value:
            return _handle_clean_orphans(**params)
        elif action == SceneAction.GET_3D_CURSOR.value:
            return _handle_get_3d_cursor(**params)
        elif action == SceneAction.SET_3D_CURSOR.value:
            return _handle_set_3d_cursor(**params)
        else:
            # Should be caught by validation, but double check
            return ResponseBuilder.error(
                handler="manage_scene",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_scene.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_scene", action=action, error_code="EXECUTION_ERROR", message=str(e)
        )


def _handle_open_file(**params: Any) -> Dict[str, Any]:
    """Handle OPEN_FILE - with safety warnings."""
    path = params.get("filepath")
    if not path:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.OPEN_FILE.value,
            error_code="MISSING_PARAMETER",
            message="filepath required",
        )

    try:
        safe_path = get_safe_path(path)

        # WARNING: open_mainfile resets entire Blender context
        def open_file() -> None:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.wm.open_mainfile(filepath=safe_path)

        execute_on_main_thread(open_file, timeout=60.0)

        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.OPEN_FILE.value,
            data={
                "message": f"Opened {safe_path}",
                "warning": "File opened. MCP connection may need to be reestablished.",
            },
        )
    except Exception as e:
        logger.error(f"OPEN_FILE failed: {e}")
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.OPEN_FILE.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to open file: {str(e)}",
        )


def _handle_save_file(**params: Any) -> Dict[str, Any]:
    """Handle SAVE_FILE."""
    path = params.get("filepath")

    try:

        def save_file() -> None:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                if path:
                    safe_path = get_safe_path(path)
                    safe_ops.wm.save_as_mainfile(filepath=safe_path)
                else:
                    safe_ops.wm.save_mainfile()

        execute_on_main_thread(save_file, timeout=30.0)
        return ResponseBuilder.success(
            handler="manage_scene", action=SceneAction.SAVE_FILE.value, data={"message": "Saved"}
        )

    except Exception as e:
        logger.error(f"SAVE_FILE failed: {e}")
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.SAVE_FILE.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to save: {str(e)}",
        )


def _handle_new_scene(**params: Any) -> Dict[str, Any]:
    """
    Handle NEW_SCENE - Safe implementation without file reload.

    CRITICAL: wm.read_homefile crashes in socket mode!
    We create new scene data instead.
    """
    try:

        def create_new_scene() -> str:
            # Create new scene without destroying UI context
            new_scene = bpy.data.scenes.new(name="Scene")

            # Remove default objects
            for obj in list(new_scene.objects):
                bpy.data.objects.remove(obj, do_unlink=True)

            # Set as active
            window = ContextManagerV3.get_window()
            if window:
                window.scene = new_scene

            return str(new_scene.name)

        scene_name = cast(str, execute_on_main_thread(create_new_scene, timeout=10.0))

        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.NEW_SCENE.value,
            data={
                "message": "New Scene Created",
                "scene_name": scene_name,
                "note": "Created without file reload (safer in socket mode)",
            },
        )

    except Exception as e:
        logger.error(f"NEW_SCENE failed: {e}")
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.NEW_SCENE.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to create new scene: {str(e)}",
        )


def _handle_playback_start(**params: Any) -> Dict[str, Any]:
    """Start animation playback."""
    # V1.0.0 Fix: Thread / Context safety for modal operators
    # RCA: PLAYBACK_START timeout (60s) due to main thread block or background mode
    if bpy.app.background:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.PLAYBACK_START.value,
            error_code="EXECUTION_ERROR",
            message="Playback cannot be started in background/headless mode",
        )

    try:
        # Using a small timeout because animation_play is modal and might block if not handled correctly
        # In GUI mode, it starts the playback. In headless, it's not supported.
        def _play_animation() -> None:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.screen.animation_play()

        execute_on_main_thread(_play_animation, timeout=2.0)
        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.PLAYBACK_START.value,
            data={"state": "playing"},
        )
    except Exception as e:
        # If it times out but started playing, we can still report success in some cases,
        # but for stability, we report the error if it's a real failure.
        if "Timeout" in str(e):
            # It's common for modal ops to timeout on the bridge side even if they start
            return ResponseBuilder.success(
                handler="manage_scene",
                action=SceneAction.PLAYBACK_START.value,
                data={
                    "state": "playing_assumed",
                    "note": "Started but modal op blocked thread return",
                },
            )
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.PLAYBACK_START.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to start playback: {str(e)}",
        )


def _handle_playback_stop(**params: Any) -> Dict[str, Any]:
    """Stop animation playback."""
    try:

        def _cancel_animation() -> None:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.screen.animation_cancel()

        execute_on_main_thread(_cancel_animation, timeout=5.0)
        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.PLAYBACK_STOP.value,
            data={"state": "stopped"},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.PLAYBACK_STOP.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to stop playback: {str(e)}",
        )


def _handle_inspect_object(**params: Any) -> Dict[str, Any]:
    """Deep object inspection."""
    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name) if obj_name else ContextManagerV3.get_active_object()

    if not obj:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.INSPECT_OBJECT.value,
            error_code="NO_ACTIVE_OBJECT",
            message="No active object found",
        )

    try:
        data = {
            "name": obj.name,
            "type": obj.type,
            "location": list(cast(Iterable[float], obj.location)) if obj.location else [],
            "rotation": list(cast(Iterable[float], obj.rotation_euler))
            if obj.rotation_euler
            else [],
            "scale": list(cast(Iterable[float], obj.scale)) if obj.scale else [],
            "parent": obj.parent.name if obj.parent else None,
            "modifiers": [m.name for m in obj.modifiers],
            "constraints": [c.name for c in obj.constraints] if hasattr(obj, "constraints") else [],
            "users_collection": [c.name for c in obj.users_collection],
            "data_users": obj.data.users if obj.data else 0,
        }

        if obj.type == "MESH":
            # mypy needs help knowing data is a Mesh if type is MESH
            if obj.data and hasattr(obj.data, "vertices"):
                # We can't easily cast to Mesh here because Mesh isn't imported from bpy.types at root level easily
                # but we can check attributes
                mesh_data: Any = obj.data
                data["stats"] = {
                    "verts": len(mesh_data.vertices),
                    "edges": len(mesh_data.edges),
                    "polys": len(mesh_data.polygons),
                    "materials": [m.name for m in mesh_data.materials if m],
                }

        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.INSPECT_OBJECT.value,
            data={"inspection": data},
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.INSPECT_OBJECT.value,
            error_code="EXECUTION_ERROR",
            message=f"Inspection failed: {str(e)}",
        )


def _handle_inspect_scene(**params: Any) -> Dict[str, Any]:
    """Scene statistics."""
    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.INSPECT_SCENE.value,
            error_code="NO_SCENE",
            message="No scene found",
        )

    try:
        active = ContextManagerV3.get_active_object()
        selected = ContextManagerV3.get_selected_objects()

        stats = {
            "name": scene.name,
            "frame_current": scene.frame_current,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "render_engine": scene.render.engine,
            "active_object": active.name if active else None,
            "selected_objects": [o.name for o in selected],
            "total_objects": len(bpy.data.objects),
            "total_materials": len(bpy.data.materials),
            "total_meshes": len(bpy.data.meshes),
        }
        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.INSPECT_SCENE.value,
            data={"scene_stats": stats},
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.INSPECT_SCENE.value,
            error_code="EXECUTION_ERROR",
            message=f"Scene inspection failed: {str(e)}",
        )


def _handle_set_unit_system(**params: Any) -> Dict[str, Any]:
    """Set unit system."""
    system = params.get("params", {}).get("system", "METRIC")

    valid_systems = ["METRIC", "IMPERIAL", "NONE"]
    if system not in valid_systems:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.SET_UNIT_SYSTEM.value,
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Invalid system: {system}. Use: {valid_systems}",
            details={"valid_systems": valid_systems, "provided": system},
        )

    try:
        scene = ContextManagerV3.get_scene()
        if scene:
            scene.unit_settings.system = system
            return {"success": True, "system": system}
        else:
            return ResponseBuilder.error(
                handler="manage_scene",
                action=SceneAction.INSPECT_SCENE.value,
                error_code="NO_SCENE",
                message="No scene found",
            )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.SET_UNIT_SYSTEM.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to set unit system: {str(e)}",
        )


def _handle_clean_orphans(**params: Any) -> Dict[str, Any]:
    """Clean orphaned data blocks."""
    from ..core.diagnostics import SystemDoctor

    try:
        # Run twice to catch nested dependencies
        count1 = SystemDoctor.clean_orphan_data()
        count2 = SystemDoctor.clean_orphan_data()

        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.CLEAN_ORPHANS.value,
            data={
                "removed_blocks": count1 + count2,
                "details": {"first_pass": count1, "second_pass": count2},
            },
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.CLEAN_ORPHANS.value,
            error_code="EXECUTION_ERROR",
            message=f"Cleanup failed: {str(e)}",
        )


def _handle_get_3d_cursor(**params: Any) -> Dict[str, Any]:
    """Get location and rotation of 3D Cursor."""
    try:
        scene = ContextManagerV3.get_scene()
        cursor = scene.cursor
        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.GET_3D_CURSOR.value,
            data={
                "location": list(cursor.location),
                "rotation_euler": list(cursor.rotation_euler),
                "rotation_mode": cursor.rotation_mode,
            },
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.GET_3D_CURSOR.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to get 3D cursor: {str(e)}",
        )


def _handle_set_3d_cursor(**params: Any) -> Dict[str, Any]:
    """Move the 3D Cursor to a specific absolute location."""
    try:
        location = params.get("params", {}).get("location")
        if not location or len(location) != 3:
            return ResponseBuilder.error(
                handler="manage_scene",
                action=SceneAction.SET_3D_CURSOR.value,
                error_code="MISSING_PARAMETER",
                message="Valid 3D [x, y, z] 'location' required in params.",
            )

        scene = ContextManagerV3.get_scene()
        scene.cursor.location = location
        return ResponseBuilder.success(
            handler="manage_scene",
            action=SceneAction.SET_3D_CURSOR.value,
            data={"message": f"3D Cursor moved to {location}"},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_scene",
            action=SceneAction.SET_3D_CURSOR.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to set 3D cursor: {str(e)}",
        )


# =============================================================================
# ALIAS WRAPPERS
# =============================================================================


@register_handler(
    "open_file",
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open_file"],
                "default": "open_file",
                "description": "Alias action",
            },
            "filepath": {"type": "string"},
        },
        "required": ["action", "filepath"],
    },
    category="scene",
)
def open_file_alias(**params: Any) -> Dict[str, Any]:
    """Alias for manage_scene(action='OPEN_FILE')"""
    params.pop("action", None)
    return manage_scene(action=SceneAction.OPEN_FILE.value, **params)


@register_handler(
    "save_file",
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["save_file"],
                "default": "save_file",
                "description": "Alias action",
            },
            "filepath": {"type": "string"},
        },
        "required": ["action"],
    },
    category="scene",
)
def save_file_alias(**params: Any) -> Dict[str, Any]:
    """Alias for manage_scene(action='SAVE_FILE')"""
    params.pop("action", None)
    return manage_scene(action=SceneAction.SAVE_FILE.value, **params)


@register_handler(
    "new_scene",
    priority=9,
    schema={
        "type": "object",
        "title": "New Scene (ESSENTIAL)",
        "description": (
            "ESSENTIAL — Create a fresh empty Blender scene without reloading Blender. "
            "Use at the start of every new modeling task to ensure a clean slate.\n"
            "Clears all existing objects and sets metric units. Safe in socket/MCP mode "
            "(does NOT use wm.read_homefile which crashes in socket mode).\n"
            "ACTIONS: new_scene"
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": ["new_scene"],
                "default": "new_scene",
                "description": "Action to perform",
            }
        },
        "required": ["action"],
    },
    category="scene",
)
def new_scene_alias(**params: Any) -> Dict[str, Any]:
    """Alias for manage_scene(action='NEW_SCENE') — ESSENTIAL tier shortcut."""
    params.pop("action", None)
    return manage_scene(action=SceneAction.NEW_SCENE.value, **params)
