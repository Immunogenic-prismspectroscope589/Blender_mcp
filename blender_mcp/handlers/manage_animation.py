"""
Animation Handler for Blender MCP 1.0.0 (Refactored)

Timeline control, Keyframe management, and Playback with:
- Property path resolution (rotation_z -> rotation_euler[2])
- Multi-language support
- Batch keyframe insertion
- Smart property aliases
- Intent-Based Animation

High Mode Philosophy: User-friendly input, machine-perfect output.
"""

from typing import Any, Dict, List, Optional

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..dispatcher import register_handler
from ..core.resolver import resolve_name
from ..core.thread_safety import ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.property_resolver import resolve_property_path, get_property_friendly_name
from ..core.enums import AnimationAction
from ..core.validation_utils import ValidationUtils
from ..core.error_protocol import ErrorCode
from ..core.exceptions import MCPError

logger = get_logger()


def _ensure_action_slot(obj: Any) -> None:
    """
    Ensure object has an active Action Slot (Blender 5.0+).
    Prevent creation of legacy actions.
    """
    # 1. Check for Linked Data (Safety Guard)
    if getattr(obj, "library", None):
        # We cannot modify linked data directly
        raise MCPError(
            message=f"Object '{obj.name}' is a Linked Object from '{obj.library.filepath}'. "
            "Cannot modify animation directly. Please create a Library Override first.",
            error_code=ErrorCode.VALIDATION_ERROR,
            suggestion="Create a Library Override for this object.",
        )

    if not obj.animation_data:
        obj.animation_data_create()

    # Check for Action Slots (Blender 5.0 feature)
    if hasattr(obj.animation_data, "action_slots"):
        if len(obj.animation_data.action_slots) == 0:
            # Create new slot
            slot = obj.animation_data.action_slots.new(name="Slot 1")

            # Ensure slot has an action
            if not slot.action:
                new_action = bpy.data.actions.new(name=f"{obj.name}Action")
                slot.action = new_action

    # Legacy fallback handled by Blender automatically if slots missing,
    # but we force slots for 5.0 compliance.


def _insert_keyframe(obj: Any, data_path: str, index: int, frame: int) -> None:
    """
    Typed wrapper for Blender's dynamic keyframe_insert API.
    Ensures Action Slots are used.
    """
    _ensure_action_slot(obj)
    insert_fn = getattr(obj, "keyframe_insert")
    insert_fn(data_path=data_path, index=index, frame=frame)


def _delete_keyframe(obj: Any, data_path: str, index: int, frame: int) -> None:
    """Typed wrapper for Blender's dynamic keyframe_delete API."""
    delete_fn = getattr(obj, "keyframe_delete")
    delete_fn(data_path=data_path, index=index, frame=frame)


@register_handler(
    "manage_animation",
    actions=[a.value for a in AnimationAction],
    category="animation",
    priority=13,
    schema={
        "type": "object",
        "title": "Animation Manager (CORE)",
        "description": (
            "CORE — Keyframe insertion, timeline control, F-curve management.\n\n"
            "Use to animate object transforms, shape keys, or any property.\n"
            "ANIMATION OVERRIDE WARNING: If an object already has animation_data, its transforms "
            "reset every frame. Check get_object_info animation_data before manually setting values. "
            "Use obj.animation_data_clear() via execute_blender_code to disable override.\n"
            "ACTIONS: INSERT_KEYFRAME, DELETE_KEYFRAME, SET_FRAME, PLAY, STOP, "
            "SET_FRAME_RANGE, INSERT_KEYFRAME_MULTI, INTENT_BASED_KEYFRAME"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                AnimationAction, "Operation to perform."
            ),
            "frame": {"type": "integer", "description": "Target frame number."},
            "start_frame": {"type": "integer", "description": "Start frame of range."},
            "end_frame": {"type": "integer", "description": "End frame of range."},
            "object_name": {
                "type": "string",
                "description": "Object to animate (default: active).",
            },
            "property_path": {
                "type": "string",
                "description": "Data path to keyframe. Supports: location, rotation_z, rx, tx, scale, all_transforms, and multi-language aliases.",
            },
            "property_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Multiple property paths for INSERT_KEYFRAME_MULTI action.",
            },
            "index": {
                "type": "integer",
                "description": "Array index for property (0=x, 1=y, 2=z). Auto-detected from path if not provided.",
            },
            # Intent-Based Animation Params
            "animation_style": {
                "type": "string",
                "enum": ["snappy", "smooth", "robotic", "organic", "bouncy", "heavy"],
                "description": "Animation style for F-curve interpolation.",
            },
            "emotion": {
                "type": "string",
                "enum": ["happy", "sad", "angry", "tired", "excited", "neutral"],
                "description": "Emotional quality of movement. Affects timing and spacing.",
            },
            "keyframes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "frame": {"type": "integer"},
                        "value": {"type": "number"},
                        "handle_type": {
                            "type": "string",
                            "enum": ["AUTO", "AUTO_CLAMPED", "VECTOR", "ALIGNED", "FREE"],
                        },
                    },
                },
                "description": "Keyframe data for INTENT_BASED_KEYFRAME.",
            },
            "auto_tangents": {
                "type": "boolean",
                "default": True,
                "description": "Whether to automatically calculate bezier handles based on style/emotion.",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_animation(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Super-Tool for Animation with smart property path resolution.
    """
    scene = getattr(bpy.context, "scene", None)
    if scene is None:
        return ResponseBuilder.error(
            handler="manage_animation",
            action=action or "UNKNOWN_ACTION",
            error_code="NO_SCENE",
            message="No active scene available",
            recoverable=True,
            suggestion="Open or create a scene before animation operations",
        )

    # 1. Validate Action
    validation_error = ValidationUtils.validate_enum(action, AnimationAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_animation", action=action
        )

    # Frame control
    if action == AnimationAction.SET_FRAME.value:
        return _handle_set_frame(scene, params)

    elif action == AnimationAction.GET_FRAME.value:
        return {
            "success": True,
            "current_frame": scene.frame_current,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "fps": scene.render.fps,
        }

    elif action == AnimationAction.SET_RANGE.value:
        return _handle_set_range(scene, params)

    elif action == AnimationAction.PLAY.value:
        try:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.screen.animation_play()
            return {"success": True, "state": "playing", "current_frame": scene.frame_current}
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_animation",
                action=action,
                error_code="EXECUTION_ERROR",
                message=f"Failed to start playback: {str(e)}",
            )

    elif action == AnimationAction.STOP.value:
        try:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.screen.animation_cancel()
            return {"success": True, "state": "stopped", "current_frame": scene.frame_current}
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_animation",
                action=action,
                error_code="EXECUTION_ERROR",
                message=f"Failed to stop playback: {str(e)}",
            )

    elif action == AnimationAction.INSERT_KEYFRAME.value:
        return _handle_insert_keyframe(scene, params)

    elif action == AnimationAction.INSERT_KEYFRAME_MULTI.value:
        return _handle_insert_keyframe_multi(scene, params)

    elif action == AnimationAction.DELETE_KEYFRAME.value:
        return _handle_delete_keyframe(scene, params)

    elif action == AnimationAction.CLEAR_KEYFRAMES.value:
        return _handle_clear_keyframes(params)

    elif action == AnimationAction.INTENT_BASED_KEYFRAME.value:
        return _handle_intent_based_keyframe(scene, params)

    # Should be unreachable due to validation
    return ResponseBuilder.error(
        handler="manage_animation",
        action=action or "UNKNOWN_ACTION",
        error_code="INVALID_ACTION",
        message=f"Unknown action: '{action}'",
    )


# =============================================================================
# HANDLER FUNCTIONS
# =============================================================================


def _handle_set_frame(scene: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    f = params.get("frame", 1)
    try:
        scene.frame_set(int(f))
        return {"success": True, "current_frame": scene.frame_current}
    except Exception:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="SET_FRAME",
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Invalid frame value: {f}",
            suggestion="Provide an integer frame number",
        )


def _handle_set_range(scene: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    s = params.get("start_frame")
    end_frame = params.get("end_frame")

    if s is not None:
        try:
            scene.frame_start = int(s)
        except Exception:
            return ResponseBuilder.error(
                handler="manage_animation",
                action="SET_RANGE",
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Invalid start_frame value: {s}",
                suggestion="Provide an integer frame number",
            )

    if end_frame is not None:
        try:
            scene.frame_end = int(end_frame)
        except Exception:
            return ResponseBuilder.error(
                handler="manage_animation",
                action="SET_RANGE",
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Invalid end_frame value: {end_frame}",
                suggestion="Provide an integer frame number",
            )

    return {"success": True, "range": [scene.frame_start, scene.frame_end]}


def _handle_insert_keyframe(scene: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name) if obj_name else bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INSERT_KEYFRAME",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: {obj_name or '(active object)'}",
            suggestion="Use '@active' or provide a valid object name",
        )

    path_input = params.get("property_path", "location")
    frame = params.get("frame", scene.frame_current)

    resolved = resolve_property_path(path_input, obj)

    if resolved is None:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INSERT_KEYFRAME",
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Could not resolve property path: '{path_input}'",
            suggestion="Use standard paths like 'location', 'rotation_z', 'scale_x' or multi-language aliases",
        )

    # Handle batch properties (list of tuples)
    if isinstance(resolved, list):
        inserted = []
        errors = []

        for data_path, index in resolved:
            try:
                _insert_keyframe(obj, data_path=data_path, index=index, frame=frame)
                friendly_name = get_property_friendly_name(data_path, index)
                inserted.append(friendly_name)
            except Exception as e:
                errors.append(f"{data_path}[{index}]: {str(e)}")

        return ResponseBuilder.success(
            handler="manage_animation",
            action="INSERT_KEYFRAME",
            data={
                "inserted": inserted,
                "errors": errors if errors else None,
                "frame": frame,
                "object": obj.name,
            },
            affected_objects=[{"name": obj.name, "type": obj.type, "changes": ["keyframe"]}],
        )

    # Handle single property
    else:
        data_path, index = resolved

        try:
            _insert_keyframe(obj, data_path=data_path, index=index, frame=frame)
            friendly_name = get_property_friendly_name(data_path, index)

            return ResponseBuilder.success(
                handler="manage_animation",
                action="INSERT_KEYFRAME",
                data={
                    "property": friendly_name,
                    "data_path": data_path,
                    "index": index,
                    "frame": frame,
                    "object": obj.name,
                },
                affected_objects=[{"name": obj.name, "type": obj.type, "changes": ["keyframe"]}],
            )
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_animation",
                action="INSERT_KEYFRAME",
                error_code="EXECUTION_ERROR",
                message=f"Failed to insert keyframe for '{path_input}': {str(e)}",
                details={"resolved_path": data_path, "resolved_index": index, "object": obj.name},
            )


def _handle_insert_keyframe_multi(scene: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name) if obj_name else bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INSERT_KEYFRAME_MULTI",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: {obj_name or '(active object)'}",
            suggestion="Provide a valid object name or semantic tag like '@hero'",
        )

    paths = params.get("property_paths", [])
    if not paths:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INSERT_KEYFRAME_MULTI",
            error_code="MISSING_PARAMETER",
            message="property_paths array is required for INSERT_KEYFRAME_MULTI",
        )

    frame = params.get("frame", scene.frame_current)

    inserted = []
    errors = []

    for path_input in paths:
        resolved = resolve_property_path(path_input, obj)

        if resolved is None:
            errors.append(f"'{path_input}': Could not resolve")
            continue

        # Handle batch properties
        if isinstance(resolved, list):
            for data_path, index in resolved:
                try:
                    _insert_keyframe(obj, data_path=data_path, index=index, frame=frame)
                    inserted.append(get_property_friendly_name(data_path, index))
                except Exception as e:
                    errors.append(f"'{path_input}'->{data_path}[{index}]: {str(e)}")
        else:
            data_path, index = resolved
            try:
                _insert_keyframe(obj, data_path=data_path, index=index, frame=frame)
                inserted.append(get_property_friendly_name(data_path, index))
            except Exception as e:
                errors.append(f"'{path_input}': {str(e)}")

    return ResponseBuilder.success(
        handler="manage_animation",
        action="INSERT_KEYFRAME_MULTI",
        data={
            "inserted_count": len(inserted),
            "inserted": inserted,
            "errors": errors if errors else None,
            "frame": frame,
            "object": obj.name,
        },
        affected_objects=[{"name": obj.name, "type": obj.type, "changes": ["keyframe"]}],
    )


def _handle_delete_keyframe(scene: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name) if obj_name else bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="DELETE_KEYFRAME",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: '{obj_name}'",
            suggestion="Check object name or select an active object",
        )

    path_input = params.get("property_path", "location")
    frame = params.get("frame", scene.frame_current)

    resolved = resolve_property_path(path_input, obj)

    if resolved is None:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="DELETE_KEYFRAME",
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Could not resolve property path: '{path_input}'",
            suggestion="Use paths like: location, rotation_euler, scale, location_x, rotation_z",
        )

    deleted = []
    errors = []

    # Handle both single and batch properties
    paths_to_delete = resolved if isinstance(resolved, list) else [resolved]

    for data_path, index in paths_to_delete:
        try:
            _delete_keyframe(obj, data_path=data_path, index=index, frame=frame)
            deleted.append(get_property_friendly_name(data_path, index))
        except Exception as e:
            errors.append(f"{data_path}[{index}]: {str(e)}")

    return {
        "success": len(deleted) > 0,
        "deleted": deleted,
        "errors": errors if errors else None,
        "frame": frame,
        "object": obj.name,
    }


def _handle_clear_keyframes(params: Dict[str, Any]) -> Dict[str, Any]:
    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name) if obj_name else bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="CLEAR_KEYFRAMES",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: '{obj_name}'",
            suggestion="Check object name or select an active object",
        )

    try:
        obj.animation_data_clear()
        return {"success": True, "message": "Animation data cleared", "object": obj.name}
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="CLEAR_KEYFRAMES",
            error_code="EXECUTION_ERROR",
            message=f"Failed to clear animation data: {str(e)}",
        )


# =============================================================================
# INTENT-BASED ANIMATION (Refactored)
# =============================================================================


def _handle_intent_based_keyframe(scene: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create keyframes with style/emotion-driven F-curve interpolation.
    """
    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name) if obj_name else bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INTENT_BASED_KEYFRAME",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: '{obj_name}'",
            suggestion="Check object name or select an active object",
        )

    # Required parameters
    path_input = params.get("property_path")
    keyframes = params.get("keyframes", [])
    style = params.get("animation_style", "smooth")
    emotion = params.get("emotion", "neutral")
    auto_tangents = params.get("auto_tangents", True)

    if not path_input:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INTENT_BASED_KEYFRAME",
            error_code="MISSING_PARAMETER",
            message="property_path is required",
            suggestion="Use paths like: location, rotation_euler, scale, location_x, rotation_z",
        )

    if not keyframes or len(keyframes) < 2:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INTENT_BASED_KEYFRAME",
            error_code="INVALID_PARAMETER_VALUE",
            message="At least 2 keyframes are required",
            suggestion='Provide keyframes as [{"frame": 1, "value": 0}, {"frame": 30, "value": 5}]',
        )

    # Resolve property path
    resolved = resolve_property_path(path_input, obj)
    if resolved is None:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INTENT_BASED_KEYFRAME",
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Could not resolve property path: {path_input}",
            suggestion="Use paths like: location, rotation_euler, scale, location_x, rotation_z",
        )

    # Handle batch properties (like all_transforms)
    if isinstance(resolved, list):
        data_path, index = resolved[0]  # Use first for now
    else:
        data_path, index = resolved

    # Get style/emotion configuration
    handle_config = _get_animation_style_config(style, emotion)

    # Insert keyframes with calculated handles
    inserted = []
    errors = []

    try:
        # Ensure animation data exists
        if not obj.animation_data:
            obj.animation_data_create()

        # Insert keyframes
        for i, kf_data in enumerate(keyframes):
            frame = kf_data.get("frame")
            value = kf_data.get("value")

            if frame is None or value is None:
                errors.append(f"Keyframe {i}: missing frame or value")
                continue

            # Set frame and value
            scene.frame_set(frame)

            # Set the property value
            try:
                if data_path == "location":
                    obj.location[index] = value
                elif data_path == "rotation_euler":
                    obj.rotation_euler[index] = value
                elif data_path == "scale":
                    obj.scale[index] = value
                else:
                    # Try generic path
                    prop_obj = (
                        obj.path_resolve(data_path.rsplit(".", 1)[0])  # type: ignore[func-returns-value, unused-ignore]
                        if "." in data_path
                        else obj
                    )
                    prop_name = data_path.rsplit(".", 1)[-1] if "." in data_path else data_path
                    if index != -1:
                        # Handle array indices
                        prop_array = getattr(prop_obj, prop_name)
                        prop_array[index] = value
                    else:
                        setattr(prop_obj, prop_name, value)
            except Exception as e:
                errors.append(f"Keyframe {i}: Failed to set value: {e}")
                continue

            # Insert keyframe
            try:
                _insert_keyframe(obj, data_path=data_path, index=index, frame=frame)
                inserted.append({"frame": frame, "value": value})
            except Exception as e:
                errors.append(f"Keyframe {i}: Failed to insert: {e}")

        # Apply handle types if auto_tangents enabled
        if auto_tangents and inserted and len(inserted) >= 2:
            _apply_handle_types(obj, data_path, index, handle_config, inserted)

        # Return success response
        friendly_name = get_property_friendly_name(data_path, index)

        return {
            "success": len(inserted) >= 2,
            "inserted_count": len(inserted),
            "keyframe_frames": [k["frame"] for k in inserted],
            "property": friendly_name,
            "data_path": data_path,
            "index": index,
            "style_applied": style,
            "emotion_applied": emotion,
            "handle_configuration": handle_config if auto_tangents else None,
            "object": obj.name,
            "errors": errors if errors else None,
            "suggestions": _get_animation_suggestions(style, emotion),
        }

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation",
            action="INTENT_BASED_KEYFRAME",
            error_code="EXECUTION_ERROR",
            message=f"Failed to create intent-based animation: {str(e)}",
        )


def _get_animation_style_config(style: str, emotion: str) -> Dict[str, Any]:
    """
    Get handle type configuration based on style and emotion.
    """
    # Base configurations by style
    style_configs: Dict[str, Dict[str, Any]] = {
        "snappy": {
            "keyframe_type": "BEZIER",
            "handle_left_type": "VECTOR",  # Sharp incoming
            "handle_right_type": "VECTOR",  # Sharp outgoing
            "easing": "EASE_IN_OUT",
            "description": "Fast, accented movement with sharp changes",
        },
        "smooth": {
            "keyframe_type": "BEZIER",
            "handle_left_type": "AUTO",
            "handle_right_type": "AUTO",
            "easing": "EASE_IN_OUT",
            "description": "Flowing, organic curves",
        },
        "robotic": {
            "keyframe_type": "BEZIER",
            "handle_left_type": "VECTOR",
            "handle_right_type": "VECTOR",
            "easing": "LINEAR",
            "description": "Linear, mechanical movement",
        },
        "organic": {
            "keyframe_type": "BEZIER",
            "handle_left_type": "ALIGNED",
            "handle_right_type": "ALIGNED",
            "easing": "EASE_IN_OUT",
            "description": "Natural ease-in-out curves",
        },
        "bouncy": {
            "keyframe_type": "BEZIER",
            "handle_left_type": "FREE",
            "handle_right_type": "FREE",
            "easing": "EASE_OUT",
            "overshoot": True,
            "description": "Overshoot and settle behavior",
        },
        "heavy": {
            "keyframe_type": "BEZIER",
            "handle_left_type": "AUTO_CLAMPED",
            "handle_right_type": "AUTO_CLAMPED",
            "easing": "EASE_IN",
            "description": "Slow start, powerful finish",
        },
    }

    # Emotion modifiers
    emotion_modifiers: Dict[str, Dict[str, Any]] = {
        "happy": {
            "easing": "EASE_OUT",
            "spacing": "closer_at_end",  # Quick anticipation, fast action
            "energy": 1.2,
        },
        "sad": {
            "easing": "EASE_IN",
            "spacing": "closer_at_start",  # Slow, heavy
            "energy": 0.6,
        },
        "angry": {"easing": "EASE_IN_OUT", "spacing": "uniform", "energy": 1.5, "sharpness": 0.8},
        "tired": {"easing": "EASE_IN", "spacing": "closer_at_start", "energy": 0.4, "drift": 0.3},
        "excited": {
            "easing": "EASE_OUT",
            "spacing": "closer_at_end",
            "energy": 1.4,
            "overshoot": 0.15,
        },
        "neutral": {
            "easing": None,  # Use style default
            "spacing": "normal",
            "energy": 1.0,
        },
    }

    # Get base config
    config = style_configs.get(style, style_configs["smooth"]).copy()

    # Apply emotion modifier
    emotion_mod = emotion_modifiers.get(emotion, emotion_modifiers["neutral"])
    if emotion_mod.get("easing"):
        config["easing"] = emotion_mod["easing"]
    config["emotion_data"] = emotion_mod

    return config


def _apply_handle_types(
    obj: Any,
    data_path: str,
    index: int,
    config: Dict[str, Any],
    keyframes: List[Dict[str, Any]],
) -> None:
    """Apply handle types to inserted keyframes."""
    if not obj.animation_data or not obj.animation_data.action:
        return

    action = obj.animation_data.action

    # Find the FCurve
    fcurve = None

    # Support for Blender 5.0 Action Slots / Layered Actions
    if hasattr(action, "fcurves"):
        # Legacy / Standard Action
        for fc in action.fcurves:
            if fc.data_path == data_path and fc.array_index == index:
                fcurve = fc
                break
    elif hasattr(action, "slots"):
        # Blender 5.0+ Layered Action with Slots
        # We try to find the curve in the first layer for now
        for slot in action.slots:
            for fc in slot.fcurves:
                if fc.data_path == data_path and fc.array_index == index:
                    fcurve = fc
                    break
            if fcurve:
                break

    if not fcurve:
        return

    # Apply handle types to keyframes
    handle_left = config.get("handle_left_type", "AUTO")
    handle_right = config.get("handle_right_type", "AUTO")

    for kf in fcurve.keyframe_points:
        if kf.co.x in [k["frame"] for k in keyframes]:
            kf.handle_left_type = handle_left
            kf.handle_right_type = handle_right

            # Apply easing-based handle adjustments
            if config.get("emotion_data", {}).get("overshoot"):
                # Add slight overshoot for bouncy/excited
                overshoot = config["emotion_data"]["overshoot"]
                if kf.handle_right_type == "FREE":
                    kf.handle_right.y += overshoot * 0.1


def _get_animation_suggestions(style: str, emotion: str) -> list:
    """Get suggestions for follow-up animations."""
    suggestions = []
    if style == "bouncy":
        suggestions.append("Try a 'squash and stretch' scale animation on a parallel track")
    if emotion == "angry":
        suggestions.append("Add a high-frequency noise modifier for 'shaking' effect")

    return suggestions
