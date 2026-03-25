"""
Headless/Background Mode Handler for Blender MCP 1.0.0

Implements:
- Headless mode detection and setup
- Memory management
- Contextless operations
- CI/CD optimization

High Mode: Runs anywhere, anytime, flawlessly.
"""

from ..core.thread_safety import ensure_main_thread
from ..dispatcher import register_handler
from ..core.parameter_validator import validated_handler
from ..core.enums import HeadlessModeAction
from ..core.response_builder import ResponseBuilder
from ..core.validation_utils import ValidationUtils
from ..core.headless_mode import HeadlessModeManager, MemoryManager, CI_CDManager
from typing import Any

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None


@register_handler(
    "manage_headless_mode",
    schema={
        "type": "object",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                HeadlessModeAction, "Headless mode action"
            ),
            "scene_name": {"type": "string"},
            "output_path": {"type": "string"},
            "frame": {"type": "integer"},
            "threshold_mb": {"type": "number", "default": 1000.0},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in HeadlessModeAction])
def manage_headless_mode(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Headless/background mode management.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_headless_mode",
            action=action,
            error_code="NO_CONTEXT",
            message="Blender context not available",
        )

    try:
        # Mode Detection
        if action == HeadlessModeAction.DETECT_MODE.value:
            mode = HeadlessModeManager.detect_mode()
            is_headless = HeadlessModeManager.is_headless()

            return {
                "success": True,
                "mode": mode.value,
                "is_headless": is_headless,
                "is_background": bpy.app.background,
            }

        elif action == HeadlessModeAction.ENSURE_CONTEXT.value:
            return HeadlessModeManager.ensure_minimal_context()

        # Memory Management
        elif action == HeadlessModeAction.PURGE_MEMORY.value:
            return MemoryManager.purge_unused_data()

        elif action == HeadlessModeAction.GET_MEMORY_STATS.value:
            return MemoryManager.get_memory_stats()

        elif action == HeadlessModeAction.AUTO_PURGE.value:
            return MemoryManager.auto_purge(threshold_mb=params.get("threshold_mb", 1000.0))

        # CI/CD
        elif action == HeadlessModeAction.SETUP_CI_CD.value:
            scene_name = params.get("scene_name")
            scene = bpy.data.scenes.get(scene_name) if scene_name else bpy.context.scene

            if not scene:
                return ResponseBuilder.error(
                    handler="manage_headless_mode",
                    action=action,
                    error_code="OBJECT_INVALID",
                    message=f"Scene not found: {scene_name}",
                )

            return CI_CDManager.setup_for_ci_cd(scene)

        elif action == HeadlessModeAction.VALIDATE_SCENE.value:
            scene_name = params.get("scene_name")
            scene = bpy.data.scenes.get(scene_name) if scene_name else bpy.context.scene

            if not scene:
                return ResponseBuilder.error(
                    handler="manage_headless_mode",
                    action=action,
                    error_code="OBJECT_INVALID",
                    message=f"Scene not found: {scene_name}",
                )

            return CI_CDManager.validate_scene_for_batch(scene)

        elif action == HeadlessModeAction.RENDER_HEADLESS.value:
            scene_name = params.get("scene_name")
            scene = bpy.data.scenes.get(scene_name) if scene_name else bpy.context.scene

            if not scene:
                return ResponseBuilder.error(
                    handler="manage_headless_mode",
                    action=action,
                    error_code="OBJECT_INVALID",
                    message=f"Scene not found: {scene_name}",
                )

            output_path = params.get("output_path")
            if not output_path:
                return ResponseBuilder.error(
                    handler="manage_headless_mode",
                    action=action,
                    error_code="MISSING_PARAMETER",
                    message="Missing required parameter: 'output_path'",
                )

            return HeadlessModeManager.render_headless(
                scene, output_path, frame=params.get("frame")
            )

        else:
            return ResponseBuilder.error(
                handler="manage_headless_mode",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Unknown headless mode action: {action}",
            )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_headless_mode",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Headless mode operation failed: {str(e)}",
        )
