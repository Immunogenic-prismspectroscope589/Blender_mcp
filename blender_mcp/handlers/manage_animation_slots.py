"""
Blender 5.0 Action Slots Handler for Blender MCP 1.0.0

Implements:
- Action Slots creation and management
- Layered animation
- NLA strip operations
- FCurve modifiers

High Mode: Full animation control.
"""

from ..core.thread_safety import ensure_main_thread
from ..dispatcher import register_handler
from ..core.parameter_validator import validated_handler
from ..core.enums import AnimationSlotsAction
from ..core.response_builder import ResponseBuilder
from ..core.validation_utils import ValidationUtils
from ..core.animation_advanced import (
    NLAManager,
    FCurveModifierManager,
    KeyframeManager,
    DriverManager,
    AnimationBaker,
)
from ..core.versioning import BlenderCompatibility
from typing import Any

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None


@register_handler(
    "manage_animation_slots",
    schema={
        "type": "object",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                AnimationSlotsAction, "Animation slots action"
            ),
            "object_name": {"type": "string"},
            "object_index": {"type": "integer"},
            # Action Slots
            "action_name": {"type": "string"},
            "slots": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "target_id": {"type": "string"},
                        "id_type": {"type": "string", "default": "OBJECT"},
                        "data_path": {"type": "string"},
                    },
                },
            },
            "slot_name": {"type": "string"},
            # Keyframe
            "property_path": {"type": "string"},
            "frame": {"type": "number"},
            "value": {"type": "number"},
            "index": {"type": "integer", "default": -1},
            "interpolation": {
                "type": "string",
                "enum": ["CONSTANT", "LINEAR", "BEZIER", "SINE", "QUAD", "CUBIC", "EXPO", "BOUNCE"],
                "default": "BEZIER",
            },
            "easing": {
                "type": "string",
                "enum": ["AUTO", "EASE_IN", "EASE_OUT", "EASE_IN_OUT"],
                "default": "AUTO",
            },
            # NLA
            "track_name": {"type": "string"},
            "track_index": {"type": "integer"},
            "strip_name": {"type": "string"},
            "start_frame": {"type": "integer"},
            "end_frame": {"type": "integer"},
            "blend_type": {
                "type": "string",
                "enum": ["REPLACE", "ADD", "SUBTRACT", "MULTIPLY"],
                "default": "REPLACE",
            },
            "influence": {"type": "number"},
            # Modifier
            "data_path": {"type": "string"},
            "strength": {"type": "number", "default": 1.0},
            "scale": {"type": "number", "default": 1.0},
            "depth": {"type": "integer", "default": 0},
            "mode_before": {"type": "string", "default": "REPEAT"},
            "mode_after": {"type": "string", "default": "REPEAT"},
            "min_value": {"type": "number"},
            "max_value": {"type": "number"},
            # Driver
            "driver_type": {"type": "string", "default": "SUM"},
            "variables": {"type": "array"},
            "expression": {"type": "string"},
            # Bake
            "step": {"type": "integer", "default": 1},
            "clear_constraints": {"type": "boolean", "default": False},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in AnimationSlotsAction])
def manage_animation_slots(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Blender 5.0 Action Slots and advanced animation operations.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_animation_slots",
            action=action,
            error_code="NO_CONTEXT",
            message="Blender context not available",
        )

    # Get target object
    obj = None
    if "object_name" in params:
        obj = bpy.data.objects.get(params.get("object_name"))
    elif "object_index" in params:
        obj = BlenderCompatibility.get_object_by_index(int(params.get("object_index", 0)))
    else:
        obj = bpy.context.active_object

    if not obj and action not in [AnimationSlotsAction.CREATE_ACTION_SLOTS.value]:
        return ResponseBuilder.error(
            handler="manage_animation_slots",
            action=action,
            error_code="OBJECT_INVALID",
            message="Invalid or missing object",
        )

    try:
        # Action Slots
        if action == AnimationSlotsAction.CREATE_ACTION_SLOTS.value:
            from ..core.blender50_features import ActionSlotManager

            action_name = params.get("action_name", "NewAction")
            slots = params.get("slots", [])
            if not slots:
                slots = [{"name": "Slot1", "target_id": "Object", "id_type": "OBJECT"}]
            else:
                for slot in slots:
                    if "id_type" not in slot:
                        slot["id_type"] = "OBJECT"
            return ActionSlotManager.create_action_with_slots(action_name, slots)

        elif action == AnimationSlotsAction.ASSIGN_SLOT.value:
            from ..core.blender50_features import ActionSlotManager

            return ActionSlotManager.assign_action_slot(
                obj, str(params.get("action_name", "")), str(params.get("slot_name", ""))
            )

        # Keyframe Operations
        elif action == AnimationSlotsAction.INSERT_KEYFRAME.value:
            frame = params.get("frame")
            raw_path = params.get("property_path", "location")
            index = params.get("index", -1)

            if frame is None:
                frame = bpy.context.scene.frame_current

            # Parse compound paths like 'location.y' → data_path='location', index=1.
            # keyframe_insert() requires path and index as separate arguments;
            # passing 'location.y' as data_path silently fails in Blender 5.0.
            _AXIS_MAP = {"x": 0, "y": 1, "z": 2, "w": 3}
            path = raw_path
            if "." in raw_path and index == -1:
                parts = raw_path.rsplit(".", 1)
                if parts[-1].lower() in _AXIS_MAP:
                    path = parts[0]
                    index = _AXIS_MAP[parts[-1].lower()]

            # Ensure object is valid context for operation
            if obj:
                obj.keyframe_insert(data_path=path, index=index, frame=frame)
                return {
                    "success": True,
                    "object": obj.name,
                    "data_path": path,
                    "index": index,
                    "frame": frame,
                }
            else:
                return ResponseBuilder.error(
                    handler="manage_animation_slots",
                    action=action,
                    error_code="OBJECT_INVALID",
                    message="Object is None during keyframe insert",
                )

        elif action == AnimationSlotsAction.INSERT_KEYFRAME_INTERPOLATED.value:
            return KeyframeManager.insert_keyframe_with_interpolation(
                obj,
                params.get("property_path", "location"),
                params.get("frame", bpy.context.scene.frame_current),
                params.get("value", 0.0),
                interpolation=params.get("interpolation", "BEZIER"),
                easing=params.get("easing", "AUTO"),
            )

        elif action == AnimationSlotsAction.COPY_KEYFRAME_RANGE.value:
            target_name = params.get("target_object")
            target = bpy.data.objects.get(target_name) if target_name else None
            if not target:
                return ResponseBuilder.error(
                    handler="manage_animation_slots",
                    action=action,
                    error_code="OBJECT_INVALID",
                    message=f"Target object not found: {target_name}",
                )

            return KeyframeManager.copy_keyframe_range(
                obj,
                target,
                params.get("data_path", "location"),
                params.get("start_frame", 1),
                params.get("end_frame", 250),
                offset=params.get("offset", 0),
            )

        # NLA Operations
        elif action == AnimationSlotsAction.CREATE_NLA_TRACK.value:
            return NLAManager.create_nla_track(obj, params.get("track_name", "Track"))

        elif action == AnimationSlotsAction.ADD_NLA_STRIP.value:
            return NLAManager.add_strip_to_track(
                obj,
                params.get("track_index", 0),
                str(params.get("action_name", "")),
                start_frame=params.get("start_frame", 1),
                blend_type=params.get("blend_type", "REPLACE"),
                influence=params.get("influence", 1.0),
            )

        elif action == AnimationSlotsAction.SET_STRIP_INFLUENCE.value:
            return NLAManager.set_strip_influence(
                obj,
                params.get("track_index", 0),
                str(params.get("strip_name", "")),
                params.get("influence", 1.0),
            )

        # FCurve Modifiers
        elif action == AnimationSlotsAction.ADD_NOISE_MODIFIER.value:
            return FCurveModifierManager.add_noise_modifier(
                obj,
                params.get("data_path", "location"),
                strength=params.get("strength", 1.0),
                scale=params.get("scale", 1.0),
                depth=params.get("depth", 0),
            )

        elif action == AnimationSlotsAction.ADD_CYCLES_MODIFIER.value:
            return FCurveModifierManager.add_cycles_modifier(
                obj,
                params.get("data_path", "location"),
                mode_before=params.get("mode_before", "REPEAT"),
                mode_after=params.get("mode_after", "REPEAT"),
            )

        elif action == AnimationSlotsAction.ADD_LIMITS_MODIFIER.value:
            return FCurveModifierManager.add_limits_modifier(
                obj,
                params.get("data_path", "location"),
                use_min="min_value" in params,
                use_max="max_value" in params,
                min_value=params.get("min_value", 0.0),
                max_value=params.get("max_value", 1.0),
            )

        # Drivers
        elif action == AnimationSlotsAction.ADD_DRIVER.value:
            variables = params.get("variables", [])
            return DriverManager.add_variable_driver(
                obj,
                params.get("data_path", "location"),
                driver_type=params.get("driver_type", "SUM"),
                variables=variables,
            )

        # Baking
        elif action == AnimationSlotsAction.BAKE_ANIMATION.value:
            return AnimationBaker.bake_action(
                obj,
                params.get("start_frame", 1),
                params.get("end_frame", 250),
                step=params.get("step", 1),
                clear_constraints=params.get("clear_constraints", False),
            )

        elif action == AnimationSlotsAction.BAKE_CONSTRAINTS.value:
            return AnimationBaker.bake_constraints(
                obj, params.get("start_frame", 1), params.get("end_frame", 250)
            )

        else:
            return ResponseBuilder.error(
                handler="manage_animation_slots",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Unknown animation action: {action}",
            )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_slots",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Animation operation failed: {str(e)}",
        )
