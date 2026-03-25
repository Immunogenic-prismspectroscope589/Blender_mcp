"""
Compositor Modifier Handler for Blender MCP 1.0.0

Implements:
- Compositor modifiers for objects
- VSE compositor strips
- Real-time viewport compositor
- Effect chains

High Mode: Post-processing without boundaries.
"""

from ..core.thread_safety import ensure_main_thread
from ..dispatcher import register_handler
from ..core.error_protocol import ErrorProtocol
from ..core.response_builder import ResponseBuilder
from ..core.enums import CompositorModifierAction
from ..core.validation_utils import ValidationUtils
from ..core.compositor_modifier import (
    CompositorModifierManager,
    VSECompositorManager,
    RealTimeEffectManager,
    CompositorEffectType,
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
    "manage_compositor_modifier",
    actions=[a.value for a in CompositorModifierAction],
    schema={
        "type": "object",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                CompositorModifierAction, "Compositor modifier action"
            ),
            "object_name": {"type": "string"},
            "object_index": {"type": "integer"},
            # Effect settings
            "effect": ValidationUtils.generate_enum_schema(
                CompositorEffectType, "Compositor effect type"
            ),
            "effects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"effect": {"type": "string"}, "settings": {"type": "object"}},
                },
            },
            "settings": {"type": "object"},
            "node_group_name": {"type": "string"},
            "modifier_name": {"type": "string"},
            # VSE settings
            "scene_name": {"type": "string"},
            "frame_start": {"type": "integer"},
            "frame_end": {"type": "integer"},
            "channel": {"type": "integer", "default": 1},
            "enabled": {"type": "boolean", "default": True},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_compositor_modifier(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Compositor modifier and effect management.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_compositor_modifier",
            action=action or "UNKNOWN",
            error_code=ErrorProtocol.NO_CONTEXT,
            message="Blender not available",
        )

    validation_error = ValidationUtils.validate_enum(action, CompositorModifierAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_compositor_modifier", action=action
        )

    try:
        # Object-based modifiers
        if action in [
            CompositorModifierAction.ADD_COMPOSITOR_MODIFIER.value,
            CompositorModifierAction.ADD_EFFECT_CHAIN.value,
            CompositorModifierAction.REMOVE_MODIFIER.value,
        ]:
            # Get target object
            obj = None
            if "object_name" in params:
                obj = bpy.data.objects.get(params.get("object_name"))
            elif "object_index" in params:
                obj = BlenderCompatibility.get_object_by_index(int(params.get("object_index", 0)))
            else:
                obj = bpy.context.active_object

            if not obj:
                return ResponseBuilder.error(
                    handler="manage_compositor_modifier",
                    action=action,
                    error_code=ErrorProtocol.NO_MESH_DATA,
                    message="Object not found",
                )

            if action == CompositorModifierAction.ADD_COMPOSITOR_MODIFIER.value:
                effect = params.get("effect", CompositorEffectType.BLOOM.value)
                return CompositorModifierManager.add_modifier(
                    obj,
                    effect,
                    settings=params.get("settings"),
                    node_group_name=params.get("node_group_name"),
                )

            elif action == CompositorModifierAction.ADD_EFFECT_CHAIN.value:
                effects = params.get("effects", [])
                return CompositorModifierManager.create_effect_chain(obj, effects)

            elif action == CompositorModifierAction.REMOVE_MODIFIER.value:
                modifier_name = params.get("modifier_name")
                if not modifier_name:
                    return ResponseBuilder.error(
                        handler="manage_compositor_modifier",
                        action=CompositorModifierAction.REMOVE_MODIFIER.value,
                        error_code=ErrorProtocol.MISSING_PARAMETER,
                        message="modifier_name is required",
                        details={"field": "modifier_name"},
                    )
                return CompositorModifierManager.remove_modifier(obj, modifier_name)

        # VSE operations
        elif action == CompositorModifierAction.ADD_VSE_STRIP.value:
            scene_name = params.get("scene_name")
            scene = bpy.data.scenes.get(scene_name) if scene_name else bpy.context.scene

            if not scene:
                return ResponseBuilder.error(
                    handler="manage_compositor_modifier",
                    action=CompositorModifierAction.ADD_VSE_STRIP.value,
                    error_code=ErrorProtocol.NO_MESH_DATA,
                    message=f"Scene not found: {scene_name}",
                    details={"object_name": scene_name},
                )

            return VSECompositorManager.add_compositor_strip(
                scene,
                params.get("frame_start", 1),
                params.get("frame_end", 250),
                channel=params.get("channel", 1),
                effect_type=params.get("effect", CompositorEffectType.BLOOM.value),
                settings=params.get("settings"),
            )

        # Real-time viewport compositor
        elif action == CompositorModifierAction.SETUP_REALTIME_COMPOSITOR.value:
            scene_name = params.get("scene_name")
            scene = bpy.data.scenes.get(scene_name) if scene_name else bpy.context.scene

            if not scene:
                return ResponseBuilder.error(
                    handler="manage_compositor_modifier",
                    action=CompositorModifierAction.SETUP_REALTIME_COMPOSITOR.value,
                    error_code=ErrorProtocol.NO_MESH_DATA,
                    message=f"Scene not found: {scene_name}",
                    details={"object_name": scene_name},
                )

            return RealTimeEffectManager.setup_realtime_compositor(
                scene, enabled=params.get("enabled", True)
            )

        elif action == CompositorModifierAction.ADD_VIEWPORT_EFFECT.value:
            scene_name = params.get("scene_name")
            scene = bpy.data.scenes.get(scene_name) if scene_name else bpy.context.scene

            if not scene:
                return ResponseBuilder.error(
                    handler="manage_compositor_modifier",
                    action=CompositorModifierAction.ADD_VIEWPORT_EFFECT.value,
                    error_code=ErrorProtocol.NO_MESH_DATA,
                    message=f"Scene not found: {scene_name}",
                    details={"object_name": scene_name},
                )

            return RealTimeEffectManager.add_viewport_effect(
                scene,
                params.get("effect", CompositorEffectType.BLOOM.value),
                settings=params.get("settings"),
            )

        else:
            return ResponseBuilder.error(
                handler="manage_compositor_modifier",
                action=action or "UNKNOWN",
                error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
                message=f"Unknown compositor action: {action}",
                details={"field": "action"},
            )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_compositor_modifier",
            action=action or "UNKNOWN",
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Compositor operation failed: {str(e)}",
        )

    return ResponseBuilder.error(
        handler="manage_compositor_modifier",
        action=action,
        error_code="UNKNOWN_ACTION",
        message=f"Unknown action: {action}",
    )
