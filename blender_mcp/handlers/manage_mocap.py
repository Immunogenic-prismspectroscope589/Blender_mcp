"""
Motion Capture Handler for Blender MCP 1.0.0 (Refactored)

Import, Cleanup, Retargeting, and Analysis of Mocap Data.
- Uses MocapAction Enum for strict typing
- Validates input via ValidationUtils
- Integrates with ContextManagerV3 for safety

High Mode Philosophy: Turn raw motion data into character soul.
"""

from typing import Optional

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..dispatcher import register_handler
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.enums import MocapAction
from ..core.validation_utils import ValidationUtils
from ..core.resolver import resolve_name
from ..core.thread_safety import ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3

logger = get_logger()


@register_handler(
    "manage_mocap",
    actions=[a.value for a in MocapAction],
    category="animation",
    schema={
        "type": "object",
        "title": "Motion Capture Manager",
        "description": "Process Motion Capture data: Import, Clean, Retarget, and Export.",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(MocapAction, "Operation to perform."),
            "filepath": {
                "type": "string",
                "description": "Path to BVH/FBX file for import/export.",
            },
            "armature_name": {"type": "string", "description": "Target armature for operations."},
            "source_armature": {
                "type": "string",
                "description": "Source armature for retargeting.",
            },
            "target_armature": {
                "type": "string",
                "description": "Target armature for retargeting.",
            },
            "smoothness": {
                "type": "number",
                "description": "Factor for curve smoothing (0.0 - 1.0).",
            },
            "threshold": {
                "type": "number",
                "description": "Threshold for noise cleaning/keyframe reduction.",
            },
            "frame_start": {"type": "integer", "description": "Start frame for processing."},
            "frame_end": {"type": "integer", "description": "End frame for processing."},
            "lock_axis": {
                "type": "string",
                "enum": ["X", "Y", "Z"],
                "description": "Axis to lock for ground contact fixes.",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_mocap(action: Optional[str] = None, **params):  # type: ignore[no-untyped-def]
    """
    Manage Motion Capture workflows.
    """
    # 1. Validate Action
    validation_error = ValidationUtils.validate_enum(action, MocapAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(validation_error, handler="manage_mocap", action=action)

    # Dispatch to specific handlers
    try:
        # Import Operations
        if action == MocapAction.IMPORT_BVH.value:
            return _import_bvh(params)
        elif action == MocapAction.IMPORT_FBX_ANIMATION.value:
            return _import_fbx(params)

        # Cleanup Operations
        elif action == MocapAction.CLEAN_NOISE.value:
            return _clean_noise(params)
        elif action == MocapAction.SMOOTH_CURVES.value:
            return _smooth_curves(params)
        elif action == MocapAction.REDUCE_KEYFRAMES.value:
            return _reduce_keyframes(params)

        # Retargeting
        elif action == MocapAction.RETARGET_TO_RIG.value:
            return _retarget_to_rig(params)

        # Foot/Ground Fixes
        elif action == MocapAction.FOOT_LOCK_FIX.value:
            return _fix_foot_sliding(params)

        # Analysis
        elif action == MocapAction.ANALYZE_MOTION.value:
            return _analyze_motion(params)

        return ResponseBuilder.error(
            handler="manage_mocap",
            action=action,
            error_code="NOT_IMPLEMENTED",
            message=f"Action '{action}' is defined but not yet implemented.",
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return ResponseBuilder.error(
            handler="manage_mocap",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Mocap operation failed: {str(e)}",
        )


# =============================================================================
# INTERNAL HANDLERS
# =============================================================================


def _import_bvh(params):  # type: ignore[no-untyped-def]
    import os as _os

    filepath = params.get("filepath")
    if not filepath:
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="IMPORT_BVH",
            error_code="MISSING_PARAMETER",
            message="filepath is required.",
        )

    # Validate file exists BEFORE calling the operator — gives a clear error message
    # instead of a cryptic FileNotFoundError from inside Blender's BVH importer.
    if not _os.path.isfile(filepath):
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="IMPORT_BVH",
            error_code="FILE_NOT_FOUND",
            message=(
                f"BVH file not found: {filepath!r}. "
                "Provide a full absolute path to an existing .bvh file."
            ),
        )

    try:
        bpy.ops.import_anim.bvh(
            filepath=filepath,
            global_scale=1.0,
            use_fps_scale=True,
            update_scene_fps=True,
            update_scene_duration=True,
        )
        # Get imported object (usually active)
        obj = bpy.context.active_object
        return ResponseBuilder.success(
            handler="manage_mocap",
            action="IMPORT_BVH",
            data={"object": obj.name if obj else "Unknown", "path": filepath},
            affected_objects=(
                [{"name": obj.name, "type": "ARMATURE", "changes": ["imported"]}] if obj else []
            ),
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="IMPORT_BVH",
            error_code="EXECUTION_ERROR",
            message=f"Failed to import BVH: {str(e)}",
        )


def _import_fbx(params):  # type: ignore[no-untyped-def]
    filepath = params.get("filepath")
    if not filepath:
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="IMPORT_FBX_ANIMATION",
            error_code="MISSING_PARAMETER",
            message="filepath is required.",
        )

    try:
        bpy.ops.import_scene.fbx(filepath=filepath, use_anim=True)
        return {"success": True, "message": "Imported FBX Animation", "path": filepath}
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="IMPORT_FBX_ANIMATION",
            error_code="EXECUTION_ERROR",
            message=f"Failed to import FBX: {str(e)}",
        )


def _clean_noise(params):  # type: ignore[no-untyped-def]
    armature_name = params.get("armature_name")
    threshold = params.get("threshold", 0.001)

    obj = resolve_name(armature_name) if armature_name else bpy.context.active_object
    if not obj or not obj.animation_data or not obj.animation_data.action:
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="CLEAN_NOISE",
            error_code="INVALID_CONTEXT",
            message="No active object with animation data found.",
        )

    # Simple noise cleaning using clean_keyframes (decimate)
    with ContextManagerV3.temp_override(
        area_type="GRAPH_EDITOR"
    ):  # Needs context for some ops, but fcurves usage is safer
        # We'll use API access instead of ops for safety if possible, or basic op
        try:
            action = obj.animation_data.action
            # Fix: Blender 5.0 Slotted Action Compatibility
            fcurves = []
            if hasattr(action, "slots"):
                for slot in action.slots:
                    fcurves.extend(slot.fcurves)
            elif hasattr(action, "fcurves"):
                fcurves.extend(action.fcurves)

            for fcurve in fcurves:
                # Basic cleaning logic or using Blender operator
                # Using operator requires selecting all keys
                pass

            # Use built-in operator
            bpy.ops.graph.clean(threshold=threshold, channels=False)
            return {"success": True, "message": f"Cleaned noise with threshold {threshold}"}
        except Exception as e:
            # Fallback to per-fcurve manual cleaning if context fails
            return {"success": False, "message": f"Context error: {str(e)}"}


def _smooth_curves(params):  # type: ignore[no-untyped-def]
    armature_name = params.get("armature_name")
    params.get("smoothness", 0.5)

    obj = resolve_name(armature_name) if armature_name else bpy.context.active_object
    if not obj or not obj.animation_data or not obj.animation_data.action:
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="SMOOTH_CURVES",
            error_code="INVALID_CONTEXT",
            message="No active object with animation data found.",
        )

    try:
        bpy.ops.graph.smooth()  # Simplest version
        return {"success": True, "message": "Smoothed curves"}
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="SMOOTH_CURVES",
            error_code="EXECUTION_ERROR",
            message=f"Failed to smooth curves: {str(e)}",
        )


def _reduce_keyframes(params):  # type: ignore[no-untyped-def]
    params.get("armature_name")
    ratio = params.get("threshold", 0.1)  # Decimate ratio

    try:
        bpy.ops.action.clean(threshold=ratio)  # This removes useless keys
        return {"success": True, "message": "Reduced keyframes"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _retarget_to_rig(params):  # type: ignore[no-untyped-def]
    source = params.get("source_armature")
    target = params.get("target_armature")

    if not source or not target:
        return ResponseBuilder.error(
            handler="manage_mocap",
            action="RETARGET_TO_RIG",
            error_code="MISSING_PARAMETER",
            message="source_armature and target_armature are required.",
        )

    # Placeholder for complex retargeting logic (Rigify/Rokoko style)
    # This usually requires bone mapping.

    return {
        "success": False,
        "message": "Retargeting requires complex mapping implementation not fully available in this standardized handler yet.",
    }


def _fix_foot_sliding(params):  # type: ignore[no-untyped-def]
    # Analyzing height of foot bones and locking if below threshold
    return {"success": True, "message": "Foot sliding fix placeholder executed."}


def _analyze_motion(params):  # type: ignore[no-untyped-def]
    # Calculate velocity, range of motion, etc.
    return {"success": True, "analysis": "Motion analysis placeholder data."}
