"""
Eevee Next Render Handler for Blender MCP 1.0.0

Implements:
- Eevee Next quality presets
- Raytracing configuration
- View Layer management
- Render pass setup

High Mode: Maximum visual quality, maximum performance.
"""

from ..core.thread_safety import ensure_main_thread
from ..dispatcher import register_handler
from ..core.enums import EeveeNextAction
from ..core.response_builder import ResponseBuilder
from ..core.validation_utils import ValidationUtils
from ..core.render_eevee_next import (
    EeveeNextManager,
    ViewLayerManager,
    RenderPassManager,
    EeveeNextQualityPreset,
    RaytracingQualityPreset,
)
from typing import Any

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None


@register_handler(
    "manage_eevee_next",
    actions=[a.value for a in EeveeNextAction],
    schema={
        "type": "object",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(EeveeNextAction, "Eevee Next action"),
            "scene_name": {"type": "string"},
            "view_layer_name": {"type": "string"},
            # Quality presets
            "preset": {
                **ValidationUtils.generate_enum_schema(EeveeNextQualityPreset, "Quality preset"),
                "default": EeveeNextQualityPreset.HIGH.value,
            },
            "raytracing_preset": {
                **ValidationUtils.generate_enum_schema(
                    RaytracingQualityPreset, "Raytracing preset"
                ),
                "default": RaytracingQualityPreset.HIGH.value,
            },
            "viewport_mode": {
                "type": "string",
                "enum": ["PERFORMANCE", "BALANCED", "QUALITY"],
                "default": "BALANCED",
            },
            # Custom settings
            "custom_settings": {"type": "object"},
            # View Layer overrides
            "override_type": {"type": "string", "enum": ["material", "world", "samples"]},
            "override_value": {"type": "string"},
            # Render passes
            "passes": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "combined",
                        "z",
                        "mist",
                        "normal",
                        "diffuse",
                        "specular",
                        "emit",
                        "environment",
                        "ao",
                        "shadow",
                    ],
                },
            },
            # Cryptomatte
            "levels": {"type": "integer", "default": 6},
            "asset": {"type": "boolean", "default": True},
            "material": {"type": "boolean", "default": True},
            "object_": {"type": "boolean", "default": True},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_eevee_next(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Eevee Next render configuration and View Layer management.
    """
    validation_error = ValidationUtils.validate_enum(action, EeveeNextAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_eevee_next", action=action
        )

    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_eevee_next",
            action=action,
            error_code="NO_CONTEXT",
            message="Blender Python API not available",
        )

    # Get scene
    scene_name = params.get("scene_name")
    scene = bpy.data.scenes.get(scene_name) if scene_name else bpy.context.scene

    if not scene:
        return ResponseBuilder.error(
            handler="manage_eevee_next",
            action=action,
            error_code="OBJECT_INVALID",
            message=f"Scene not found: {scene_name}",
        )

    try:
        # Eevee Next Setup
        if action == EeveeNextAction.SETUP_EEVEE_NEXT.value:
            return EeveeNextManager.setup_eevee_next(
                scene,
                preset=params.get("preset", EeveeNextQualityPreset.HIGH.value),
                custom_settings=params.get("custom_settings"),
            )

        elif action == EeveeNextAction.SETUP_RAYTRACING.value:
            return EeveeNextManager.setup_raytracing(
                scene, quality=params.get("raytracing_preset", RaytracingQualityPreset.HIGH.value)
            )

        elif action == EeveeNextAction.OPTIMIZE_VIEWPORT.value:
            return EeveeNextManager.optimize_for_viewport(
                scene, quality=params.get("viewport_mode", "BALANCED")
            )

        # View Layers
        elif action == EeveeNextAction.CREATE_CLAY_VIEW_LAYER.value:
            return ViewLayerManager.create_clay_render_view_layer(
                scene, name=params.get("view_layer_name", "Clay")
            )

        elif action == EeveeNextAction.CREATE_WIREFRAME_VIEW_LAYER.value:
            return ViewLayerManager.create_wireframe_view_layer(
                scene, name=params.get("view_layer_name", "Wireframe")
            )

        elif action == EeveeNextAction.SET_VIEW_LAYER_OVERRIDE.value:
            view_layer_name = params.get("view_layer_name", "ViewLayer")
            view_layer = scene.view_layers.get(view_layer_name)

            if not view_layer:
                return ResponseBuilder.error(
                    handler="manage_eevee_next",
                    action=EeveeNextAction.SET_VIEW_LAYER_OVERRIDE.value,
                    error_code="OBJECT_NOT_FOUND",
                    message=f"View layer not found: {view_layer_name}",
                )

            return ViewLayerManager.set_view_layer_override(
                view_layer,
                params.get("override_type", "material"),
                params.get("override_value", ""),
            )

        # Render Passes
        elif action == EeveeNextAction.ENABLE_RENDER_PASSES.value:
            view_layer_name = params.get("view_layer_name", "ViewLayer")
            view_layer = scene.view_layers.get(view_layer_name)

            if not view_layer:
                return ResponseBuilder.error(
                    handler="manage_eevee_next",
                    action=EeveeNextAction.ENABLE_RENDER_PASSES.value,
                    error_code="OBJECT_NOT_FOUND",
                    message="View layer not found",
                )

            return RenderPassManager.enable_passes(view_layer, params.get("passes", ["combined"]))

        elif action == EeveeNextAction.SETUP_CRYPTOMATTE.value:
            view_layer_name = params.get("view_layer_name", "ViewLayer")
            view_layer = scene.view_layers.get(view_layer_name)

            if not view_layer:
                return ResponseBuilder.error(
                    handler="manage_eevee_next",
                    action=EeveeNextAction.SETUP_CRYPTOMATTE.value,
                    error_code="OBJECT_NOT_FOUND",
                    message="View layer not found",
                )

            return RenderPassManager.setup_cryptomatte(
                view_layer,
                levels=params.get("levels", 6),
                asset=params.get("asset", True),
                material=params.get("material", True),
                object_=params.get("object_", True),
            )

        elif action == EeveeNextAction.SETUP_FOR_CI_CD.value:
            from ..core.headless_mode import CI_CDManager

            return CI_CDManager.setup_for_ci_cd(scene)

        else:
            return ResponseBuilder.error(
                handler="manage_eevee_next",
                action=action,
                error_code="MISSING_PARAMETER",
                message=f"Unknown Eevee Next action: {action}",
            )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_eevee_next",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Eevee Next operation failed: {str(e)}",
        )
