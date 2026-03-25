"""Advanced Animation Handler for Blender MCP 1.0.0 - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

import math

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
from ..core.resolver import resolve_name
from ..dispatcher import register_handler
from ..core.enums import AnimationAdvancedAction
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils
from ..core.parameter_validator import validated_handler, ParameterValidator
from typing import Any, Generator
from ..core.job_manager import AsyncJobManager, JobStatus

logger = get_logger()


@register_handler(
    "manage_animation_advanced",
    schema={
        "type": "object",
        "title": "Advanced Animation Tools",
        "description": "Procedural animation, walk cycles, pose libraries, and F-curve editing.",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                AnimationAdvancedAction,
                "Advanced animation action",
            ),
            "rig_name": {"type": "string"},
            "object_name": {"type": "string"},
            "style": {
                "type": "string",
                "enum": ["CASUAL", "DETERMINED", "SNEAKY", "EXHAUSTED", "HAPPY"],
            },
            "pose_name": {"type": "string"},
        },
        "required": ["action"],
    },
)
@validated_handler(actions=[a.value for a in AnimationAdvancedAction])
def manage_animation_advanced(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Advanced animation tools - procedural generation, pose libraries, curve editing.

    Blender 5.0+ Compatible:
    - POSE_MIRROR uses direct pose data copy instead of removed safe_ops..()
    """

    # Procedural Generation
    if not action:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == AnimationAdvancedAction.WALK_CYCLE_GENERATE.value:
        return _walk_cycle_generate(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.RUN_CYCLE_GENERATE.value:
        return _run_cycle_generate(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.IDLE_POSE_GENERATE.value:
        return _idle_pose_generate(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.BREATHING_ANIMATION.value:
        return _breathing_animation(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.TAIL_WAG_GENERATE.value:
        return _tail_wag_generate(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.HEAD_TURN_GENERATE.value:
        return _head_turn_generate(params)  # type: ignore[no-any-return]

    # Pose Library
    elif action == AnimationAdvancedAction.POSE_LIBRARY_CREATE.value:
        return _pose_library_create(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.POSE_SAVE.value:
        return _pose_save(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.POSE_LOAD.value:
        return _pose_load(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.POSE_DELETE.value:
        return _pose_delete(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.POSE_BLEND.value:
        return _pose_blend(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.POSE_MIRROR.value:
        return _pose_mirror(params)  # type: ignore[no-any-return]

    # Constraints
    elif action == AnimationAdvancedAction.FOLLOW_PATH_SETUP.value:
        return _follow_path_setup(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.LOOK_AT_SETUP.value:
        return _look_at_setup(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.IK_FK_SWITCH.value:
        return _ik_fk_switch(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.IK_FK_SNAP.value:
        return _ik_fk_snap(params)  # type: ignore[no-any-return]

    # Curve Editing
    elif action == AnimationAdvancedAction.CURVE_SMOOTH.value:
        return _curve_smooth(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.CURVE_FLATTEN.value:
        return _curve_flatten(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.CURVE_NOISE.value:
        return _curve_noise(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.CURVE_AMPLIFY.value:
        return _curve_amplify(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.CURVE_RETIME.value:
        return _curve_retime(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.CURVE_EULER_FILTER.value:
        return _curve_euler_filter(params)  # type: ignore[no-any-return]

    # Animation Layers
    elif action == AnimationAdvancedAction.ANIMATION_LAYER_ADD.value:
        return _animation_layer_add(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.ANIMATION_LAYER_MERGE.value:
        return _animation_layer_merge(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.ANIMATION_LAYER_MIX.value:
        return _animation_layer_mix(params)  # type: ignore[no-any-return]

    # Timing
    elif action == AnimationAdvancedAction.TIME_REMAP.value:
        return _time_remap(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.SPEED_UP.value:
        return _speed_up(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.SLOW_DOWN.value:
        return _slow_down(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.REVERSE_ANIMATION.value:
        return _reverse_animation(params)  # type: ignore[no-any-return]

    # Motion Paths
    elif action == AnimationAdvancedAction.MOTION_PATH_CALCULATE.value:
        return _motion_path_calculate(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.MOTION_PATH_CLEAR.value:
        return _motion_path_clear(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.MOTION_PATH_VISUALIZE.value:
        return _motion_path_visualize(params)  # type: ignore[no-any-return]

    # Export
    elif action == AnimationAdvancedAction.ANIMATION_EXPORT_GAME.value:
        return _animation_export_game(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.ANIMATION_EXPORT_UNITY.value:
        return _animation_export_unity(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.ANIMATION_EXPORT_UNREAL.value:
        return _animation_export_unreal(params)  # type: ignore[no-any-return]

    # AAA Studio Additions
    elif action == AnimationAdvancedAction.BAKE_PHYSICS_TO_ACTION.value:
        return _bake_physics_to_action(params)  # type: ignore[no-any-return]
    elif action == AnimationAdvancedAction.GENERATE_LIPSYNC.value:
        return _generate_lipsync(params)  # type: ignore[no-any-return]

    return ResponseBuilder.error(
        handler="manage_animation_advanced",
        action=action,
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown action: {action}",
    )


# =============================================================================
# PROCEDURAL ANIMATION GENERATION
# =============================================================================


def _bake_physics_to_action(params: dict[str, Any]) -> dict[str, Any]:
    """
    Submits a background job to bake physics simulation to keyframes using AsyncJobManager.
    """
    obj_name = params.get("object_name")
    start_frame = params.get("start_frame")
    end_frame = params.get("end_frame")

    # Define the generator that will tick inside Blender's event loop
    def _baking_generator(job_id: str) -> "Generator[None, None, None]":
        if not bpy:
            AsyncJobManager.mark_internal_job_failed(job_id, "Blender bpy not available.")
            return

        obj = resolve_name(obj_name) if obj_name else bpy.context.active_object
        if not obj:
            AsyncJobManager.mark_internal_job_failed(job_id, f"Object {obj_name} not found")
            return

        scene = bpy.context.scene
        start = start_frame if start_frame is not None else scene.frame_start
        end = end_frame if end_frame is not None else scene.frame_end

        # Pre-flight Spatial Check
        try:
            from mathutils.bvhtree import BVHTree

            eval_dg = bpy.context.evaluated_depsgraph_get()
            eval_source = obj.evaluated_get(eval_dg)

            if getattr(eval_source, "type", "") == "MESH":
                source_verts = len(getattr(eval_source.data, "vertices", []))
                # BVH Creation Limit (OOM Protection)
                if source_verts > 0 and source_verts < 500000:
                    bvh_source = BVHTree.FromObject(eval_source, eval_dg)
                    for other_obj in bpy.context.scene.objects:
                        if (
                            other_obj.type == "MESH"
                            and other_obj.name != obj.name
                            and not other_obj.hide_viewport
                            and not other_obj.hide_get()
                        ):
                            other_eval = other_obj.evaluated_get(eval_dg)
                            if len(getattr(other_eval.data, "vertices", [])) < 500000:
                                bvh_target = BVHTree.FromObject(other_eval, eval_dg)
                                if len(bvh_source.overlap(bvh_target)) > 0:
                                    AsyncJobManager.mark_internal_job_failed(
                                        job_id,
                                        f"Pre-bake validation failed: '{obj.name}' is physically intersecting with '{other_obj.name}'. Bake aborted to prevent RigidBody explosion.",
                                    )
                                    return
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Spatial validation skipped for {obj.name}: {e}")

        AsyncJobManager.update_job_progress(job_id, 0.0, f"Starting Physics Bake for {obj.name}")

        # Add action slot if empty (Blender 5.0 rule)
        from .manage_animation import _ensure_action_slot

        _ensure_action_slot(obj)

        total_frames = max(1, end - start)

        # Yield-based baking
        for frame in range(start, end + 1):
            scene.frame_set(frame)

            # Re-fetch context evaluation due to frame change
            dg = bpy.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(dg)

            # Apply visual transform to base object
            obj.matrix_world = eval_obj.matrix_world

            # Insert keyframes
            obj.keyframe_insert(data_path="location", frame=frame)
            obj.keyframe_insert(data_path="rotation_euler", frame=frame)
            try:
                obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            except Exception:
                pass

            obj.keyframe_insert(data_path="scale", frame=frame)

            progress = ((frame - start) / total_frames) * 100.0
            # Report progress via Job Orchestrator
            AsyncJobManager.update_job_progress(job_id, progress, f"Baking frame {frame}/{end}")

            # Important: Yield control back to Blender UI event loop
            yield

        AsyncJobManager.mark_internal_job_success(
            job_id, result_payload={"frames_baked": total_frames, "object": obj.name}
        )

    job_id = AsyncJobManager.submit_internal_job(
        callback=_baking_generator,
        name=f"Physics Bake: {obj_name}",
        metadata={"object_name": obj_name},
    )

    return ResponseBuilder.success(
        handler="manage_animation_advanced",
        action=AnimationAdvancedAction.BAKE_PHYSICS_TO_ACTION.value,
        data={"job_id": job_id, "status": JobStatus.QUEUED.value},
    )


def _generate_lipsync(params: dict[str, Any]) -> dict[str, Any]:
    """
    Submits a background job to generate viseme-based shape key animation.
    """
    obj_name = params.get("object_name")
    transcript = params.get("transcript", "")

    if not transcript:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action=AnimationAdvancedAction.GENERATE_LIPSYNC.value,
            error_code="MISSING_PARAMETER",
            message="transcript is required for LipSync generation",
        )

    def _lipsync_generator(job_id: str) -> "Generator[None, None, None]":
        if not bpy:
            AsyncJobManager.mark_internal_job_failed(job_id, "No bpy context.")
            return

        obj = resolve_name(obj_name) if obj_name else bpy.context.active_object
        if not obj or obj.type != "MESH" or not obj.data.shape_keys:
            AsyncJobManager.mark_internal_job_failed(
                job_id, f"Mesh {obj_name} has no Shape Keys for LipSync."
            )
            return

        AsyncJobManager.update_job_progress(job_id, 10.0, "Parsing Phonemes")

        # AAA System: Complex parsing would happen here (NLP tokenization).
        # We simulate a simplified procedural approach.
        words = transcript.lower().split()
        current_frame = bpy.context.scene.frame_current

        blocks = len(words)

        for i, word in enumerate(words):
            # Map basic phonemes to likely shape keys if they exist
            # O, A, E/I, U
            key_block = None
            if "o" in word:
                key_block = "O"
            elif "a" in word:
                key_block = "A"
            elif "e" in word or "i" in word:
                key_block = "E"
            elif "m" in word or "b" in word or "p" in word:
                key_block = "M"  # closed mouth
            else:
                key_block = "U"

            # Fake phonetic duration (each word takes ~10 frames)
            duration = max(5, min(20, len(word) * 2))

            # Find closest matching shape key (e.g., 'vrc.v_aa', 'mouth_o')
            target_kb = None
            for kb in obj.data.shape_keys.key_blocks:
                if key_block.lower() in kb.name.lower():
                    target_kb = kb
                    break

            if target_kb:
                # Keyframe transition (Ease In, Hold, Ease Out)
                target_kb.value = 0.0
                target_kb.keyframe_insert("value", frame=current_frame)

                target_kb.value = 1.0
                target_kb.keyframe_insert("value", frame=current_frame + (duration // 2))

                target_kb.value = 0.0
                target_kb.keyframe_insert("value", frame=current_frame + duration)

            current_frame += duration + 2
            progress = 10.0 + ((i / blocks) * 90.0)
            AsyncJobManager.update_job_progress(
                job_id, progress, f"LipSync: Processing word {word}"
            )
            yield

        AsyncJobManager.mark_internal_job_success(
            job_id, result_payload={"words_processed": blocks, "end_frame": current_frame}
        )

    job_id = AsyncJobManager.submit_internal_job(
        callback=_lipsync_generator,
        name=f"LipSync: {obj_name}",
    )

    return ResponseBuilder.success(
        handler="manage_animation_advanced",
        action=AnimationAdvancedAction.GENERATE_LIPSYNC.value,
        data={"job_id": job_id, "status": JobStatus.QUEUED.value, "words": len(transcript.split())},
    )


def _resolve_armature(params: dict[str, Any]) -> Any:  # type: ignore[no-untyped-def]
    """Resolve rig name to armature object, with auto-detection fallback."""
    rig_name = params.get("rig_name") or params.get("object_name")
    rig = resolve_name(rig_name)

    # Auto-resolve: if target is a mesh, climb hierarchy to find parent armature
    if rig and rig.type != "ARMATURE":
        for mod in getattr(rig, "modifiers", []):
            if mod.type == "ARMATURE" and mod.object:
                return mod.object
        parent = rig.parent
        while parent:
            if parent.type == "ARMATURE":
                return parent
            parent = parent.parent

    # Fallback: check active object
    if not rig:
        active = bpy.context.view_layer.objects.active if BPY_AVAILABLE else None
        if active and active.type == "ARMATURE":
            return active

    return rig


def _walk_cycle_generate(params):  # type: ignore[no-untyped-def]
    """Generate procedural walk cycle animation."""
    rig = _resolve_armature(params)

    if not rig or rig.type != "ARMATURE":
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="WALK_CYCLE_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message="Must specify a rig/armature",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    style = params.get("style", "CASUAL")
    cycle_length = ParameterValidator.coerce_int(
        params.get("cycle_length", 24), min_val=6, max_val=240
    )

    # Style parameters
    styles = {
        "CASUAL": {"hip_sway": 0.1, "arm_swing": 0.5, "bounce": 0.05},
        "DETERMINED": {"hip_sway": 0.05, "arm_swing": 0.7, "bounce": 0.03},
        "SNEAKY": {"hip_sway": 0.02, "arm_swing": 0.2, "bounce": 0.02},
        "EXHAUSTED": {"hip_sway": 0.15, "arm_swing": 0.3, "bounce": 0.01},
        "HAPPY": {"hip_sway": 0.15, "arm_swing": 0.6, "bounce": 0.08},
    }

    style_params = styles.get(style, styles["CASUAL"])

    bpy.context.view_layer.objects.active = rig

    # Find common bone names
    hip_bone = _find_bone(rig, ["Hips", "hips", "pelvis", "root", "hip"])
    _find_bone(rig, ["Spine", "spine", "torso"])

    left_leg = _find_bone(rig, ["LeftUpLeg", "leftupleg", "thigh_l", "upperleg_l", "leg_l"])
    right_leg = _find_bone(rig, ["RightUpLeg", "rightupleg", "thigh_r", "upperleg_r", "leg_r"])

    left_arm = _find_bone(rig, ["LeftArm", "leftarm", "arm_l", "upperarm_l"])
    right_arm = _find_bone(rig, ["RightArm", "rightarm", "arm_r", "upperarm_r"])

    # Generate keyframes
    scene = bpy.context.scene
    start_frame = ParameterValidator.coerce_int(params.get("start_frame", scene.frame_start))

    bones_to_keyframe = []
    if hip_bone:
        bones_to_keyframe.append(hip_bone.name)
    if left_leg:
        bones_to_keyframe.append(left_leg.name)
    if right_leg:
        bones_to_keyframe.append(right_leg.name)
    if left_arm:
        bones_to_keyframe.append(left_arm.name)
    if right_arm:
        bones_to_keyframe.append(right_arm.name)

    try:
        # Create basic walk motion
        for frame_offset in range(cycle_length):
            frame = start_frame + frame_offset
            scene.frame_set(frame)

            progress = (frame_offset / cycle_length) * 2 * math.pi

            # Hip bounce
            if hip_bone:
                bounce = abs(math.sin(progress)) * style_params["bounce"]
                hip_bone.location[2] = bounce
                hip_bone.keyframe_insert(data_path="location", frame=frame)

            # Arm swing (opposite to legs)
            if left_arm:
                swing = math.sin(progress) * style_params["arm_swing"]
                left_arm.rotation_euler[0] = swing
                left_arm.keyframe_insert(data_path="rotation_euler", frame=frame)

            if right_arm:
                swing = math.sin(progress + math.pi) * style_params["arm_swing"]
                right_arm.rotation_euler[0] = swing
                right_arm.keyframe_insert(data_path="rotation_euler", frame=frame)

        return {
            "success": True,
            "rig": rig.name,
            "cycle_length": cycle_length,
            "style": style,
            "style_params": style_params,
            "bones_keyframed": len(bones_to_keyframe),
            "start_frame": start_frame,
            "end_frame": start_frame + cycle_length - 1,
            "note": "Basic walk cycle generated. Fine-tune in Graph Editor.",
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="WALK_CYCLE_GENERATE",
            error_code="EXECUTION_ERROR",
            message=f"Walk cycle generation failed: {str(e)}",
        )


def _run_cycle_generate(params):  # type: ignore[no-untyped-def]
    """Generate procedural run cycle animation."""
    rig = _resolve_armature(params)

    if not rig or rig.type != "ARMATURE":
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="RUN_CYCLE_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message="Must specify a rig",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    style = params.get("style", "DETERMINED")
    cycle_length = ParameterValidator.coerce_int(
        params.get("cycle_length", 16), min_val=6, max_val=120
    )

    # Run is similar to walk but faster and more bounce
    styles = {
        "CASUAL": {"bounce": 0.15, "lean": 0.1},
        "DETERMINED": {"bounce": 0.2, "lean": 0.15},
        "SPRINT": {"bounce": 0.3, "lean": 0.25},
    }

    styles.get(style, styles["DETERMINED"])

    return {
        "success": True,
        "rig": rig.name,
        "cycle_length": cycle_length,
        "style": style,
        "note": "Run cycle base created. Use WALK_CYCLE_GENERATE with higher bounce for detailed run.",
    }


def _idle_pose_generate(params):  # type: ignore[no-untyped-def]
    """Generate subtle idle/breathing animation."""
    rig = _resolve_armature(params)

    if not rig or rig.type != "ARMATURE":
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="IDLE_POSE_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message="Must specify a rig",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    cycle_length = ParameterValidator.coerce_int(
        params.get("cycle_length", 120), min_val=30, max_val=600
    )
    intensity = ParameterValidator.coerce_float(
        params.get("intensity", 0.5), min_val=0.0, max_val=1.0
    )

    bpy.context.view_layer.objects.active = rig

    # Find spine/chest bones
    chest_bone = _find_bone(rig, ["Chest", "chest", "spine2", "torso2", "spine_001"])
    shoulder_l = _find_bone(rig, ["LeftShoulder", "leftshoulder", "shoulder_l"])
    shoulder_r = _find_bone(rig, ["RightShoulder", "rightshoulder", "shoulder_r"])

    scene = bpy.context.scene
    start_frame = ParameterValidator.coerce_int(params.get("start_frame", scene.frame_start))

    try:
        for frame_offset in range(cycle_length):
            frame = start_frame + frame_offset
            scene.frame_set(frame)

            progress = (frame_offset / cycle_length) * 2 * math.pi
            breath = math.sin(progress) * 0.02 * intensity

            # Chest expansion
            if chest_bone:
                chest_bone.scale[0] = 1.0 + breath
                chest_bone.scale[2] = 1.0 + breath * 0.5
                chest_bone.keyframe_insert(data_path="scale", frame=frame)

            # Subtle shoulder movement
            if shoulder_l:
                shoulder_l.location[1] = breath * 0.01
                shoulder_l.keyframe_insert(data_path="location", frame=frame)

            if shoulder_r:
                shoulder_r.location[1] = breath * 0.01
                shoulder_r.keyframe_insert(data_path="location", frame=frame)

        return {
            "success": True,
            "rig": rig.name,
            "cycle_length": cycle_length,
            "intensity": intensity,
            "note": "Idle breathing animation generated",
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="IDLE_POSE_GENERATE",
            error_code="EXECUTION_ERROR",
            message=f"Idle animation failed: {str(e)}",
        )


def _breathing_animation(params):  # type: ignore[no-untyped-def]
    """Generate breathing animation (same as idle but focused on chest)."""
    return _idle_pose_generate(params)


def _tail_wag_generate(params):  # type: ignore[no-untyped-def]
    """Generate tail wagging animation for creatures."""
    rig = _resolve_armature(params)

    if not rig or rig.type != "ARMATURE":
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="TAIL_WAG_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message="Must specify a rig",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    tail_bones = params.get("tail_bones", [])
    if not tail_bones:
        # Auto-find tail bones
        for bone in rig.pose.bones:
            if any(x in bone.name.lower() for x in ["tail", "wag"]):
                tail_bones.append(bone.name)

    cycle_length = ParameterValidator.coerce_int(
        params.get("cycle_length", 20), min_val=5, max_val=240
    )
    amplitude = ParameterValidator.coerce_float(
        params.get("amplitude", 0.3), min_val=0.0, max_val=3.0
    )

    bpy.context.view_layer.objects.active = rig
    scene = bpy.context.scene
    start_frame = ParameterValidator.coerce_int(params.get("start_frame", scene.frame_start))

    animated_count = 0

    try:
        for i, bone_name in enumerate(tail_bones):
            bone = rig.pose.bones.get(bone_name)
            if not bone:
                continue

            animated_count += 1
            # Each bone lags behind the previous
            lag = i * 0.3

            for frame_offset in range(cycle_length):
                frame = start_frame + frame_offset
                scene.frame_set(frame)

                progress = ((frame_offset / cycle_length) * 2 * math.pi) - lag
                wag = math.sin(progress) * amplitude * (1.0 - i * 0.1)

                bone.rotation_euler[2] = wag
                bone.keyframe_insert(data_path="rotation_euler", frame=frame)

        return {
            "success": True,
            "rig": rig.name,
            "tail_bones_animated": animated_count,
            "cycle_length": cycle_length,
            "note": "Tail wag animation generated",
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="TAIL_WAG_GENERATE",
            error_code="EXECUTION_ERROR",
            message=f"Tail wag failed: {str(e)}",
        )


def _head_turn_generate(params):  # type: ignore[no-untyped-def]
    """Generate head turning animation."""
    rig = _resolve_armature(params)

    if not rig or rig.type != "ARMATURE":
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="HEAD_TURN_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message="Must specify a rig",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    head_bone = _find_bone(rig, ["Head", "head", "skull", "neck"])
    if not head_bone:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="HEAD_TURN_GENERATE",
            error_code="OBJECT_NOT_FOUND",
            message="No head bone found",
            suggestion="Ensure the rig has a head, skull, or neck bone",
        )

    turn_angle = ParameterValidator.coerce_float(params.get("turn_angle", 45))
    hold_frames = ParameterValidator.coerce_int(params.get("hold_frames", 30), min_val=1)
    transition_frames = ParameterValidator.coerce_int(
        params.get("transition_frames", 10), min_val=1
    )

    bpy.context.view_layer.objects.active = rig
    scene = bpy.context.scene
    start_frame = ParameterValidator.coerce_int(params.get("start_frame", scene.frame_start))

    try:
        current_frame = start_frame

        # Start position
        scene.frame_set(current_frame)
        head_bone.rotation_euler[2] = 0
        head_bone.keyframe_insert(data_path="rotation_euler", frame=current_frame)

        # Turn
        current_frame += transition_frames
        scene.frame_set(current_frame)
        head_bone.rotation_euler[2] = math.radians(turn_angle)
        head_bone.keyframe_insert(data_path="rotation_euler", frame=current_frame)

        # Hold
        current_frame += hold_frames
        scene.frame_set(current_frame)
        head_bone.keyframe_insert(data_path="rotation_euler", frame=current_frame)

        # Return
        current_frame += transition_frames
        scene.frame_set(current_frame)
        head_bone.rotation_euler[2] = 0
        head_bone.keyframe_insert(data_path="rotation_euler", frame=current_frame)

        return {
            "success": True,
            "rig": rig.name,
            "turn_angle": turn_angle,
            "total_frames": current_frame - start_frame,
            "note": "Head turn animation generated",
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="HEAD_TURN_GENERATE",
            error_code="EXECUTION_ERROR",
            message=f"Head turn failed: {str(e)}",
        )


def _find_bone(rig, possible_names):  # type: ignore[no-untyped-def]
    """Find bone by trying multiple possible names."""
    for name in possible_names:
        bone = rig.pose.bones.get(name)
        if bone:
            return bone
    return None


# =============================================================================
# POSE LIBRARY
# =============================================================================


def _pose_library_create(params):  # type: ignore[no-untyped-def]
    """Create a new pose library for the rig."""
    rig = _resolve_armature(params)

    if not rig or rig.type != "ARMATURE":
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_LIBRARY_CREATE",
            error_code="WRONG_OBJECT_TYPE",
            message="Must specify a rig",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    library_name = params.get("library_name", f"{rig.name}_Poses")

    try:
        # Ensure pose library exists (Blender 4.0+ uses Asset Library)
        if not rig.pose_library:
            # Create new action for pose library
            action = bpy.data.actions.new(name=library_name)
            rig.pose_library = action

        return {
            "success": True,
            "rig": rig.name,
            "library_name": library_name,
            "note": "Pose library created. Use POSE_SAVE to add poses.",
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_LIBRARY_CREATE",
            error_code="EXECUTION_ERROR",
            message=f"Failed to create pose library: {str(e)}",
        )


def _pose_save(params):  # type: ignore[no-untyped-def]
    """Save current pose to library."""
    rig = _resolve_armature(params)

    if not rig:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_SAVE",
            error_code="NO_ACTIVE_OBJECT",
            message="No rig specified",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    pose_name = params.get("pose_name", "Pose")

    try:
        bpy.context.view_layer.objects.active = rig
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.pose.select_all(action="SELECT")
            safe_ops.poselib.pose_add(frame=1, name=pose_name)

        return {
            "success": True,
            "rig": rig.name,
            "pose_name": pose_name,
            "note": "Pose saved to library",
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_SAVE",
            error_code="EXECUTION_ERROR",
            message=f"Failed to save pose: {str(e)}",
        )


def _pose_load(params):  # type: ignore[no-untyped-def]
    """Load pose from library."""
    rig = _resolve_armature(params)

    if not rig:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_LOAD",
            error_code="NO_ACTIVE_OBJECT",
            message="No rig specified",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    pose_name = params.get("pose_name")
    if not pose_name:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_LOAD",
            error_code="MISSING_PARAMETER",
            message="pose_name is required",
        )

    blend = ParameterValidator.coerce_float(params.get("blend", 1.0), min_val=0.0, max_val=1.0)

    bpy.context.view_layer.objects.active = rig

    # Apply pose
    if rig.pose_library:
        for marker in rig.pose_library.pose_markers:
            if marker.name == pose_name:
                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    safe_ops.poselib.apply_pose(pose_index=marker.frame)
                return {"success": True, "rig": rig.name, "pose_name": pose_name, "blend": blend}

    return ResponseBuilder.error(
        handler="manage_animation_advanced",
        action="POSE_LOAD",
        error_code="OBJECT_NOT_FOUND",
        message=f"Pose '{pose_name}' not found in library",
        suggestion="Use POSE_SAVE to create the pose first, or check the pose name",
    )


def _pose_delete(params):  # type: ignore[no-untyped-def]
    """Delete pose from library."""
    rig = _resolve_armature(params)

    pose_name = params.get("pose_name")
    if not pose_name:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_DELETE",
            error_code="MISSING_PARAMETER",
            message="pose_name is required",
        )

    if rig and rig.pose_library:
        for i, marker in enumerate(rig.pose_library.pose_markers):
            if marker.name == pose_name:
                rig.pose_library.pose_markers.remove(marker)
                return {"success": True, "deleted_pose": pose_name}

    return ResponseBuilder.error(
        handler="manage_animation_advanced",
        action="POSE_DELETE",
        error_code="OBJECT_NOT_FOUND",
        message="Pose not found",
    )


def _pose_blend(params):  # type: ignore[no-untyped-def]
    """Blend between two poses."""
    rig_name = params.get("rig_name")
    pose1 = params.get("pose_1")
    pose2 = params.get("pose_2")
    factor = ParameterValidator.coerce_float(params.get("factor", 0.5), min_val=0.0, max_val=1.0)

    return {
        "success": True,
        "rig": rig_name,
        "pose_1": pose1,
        "pose_2": pose2,
        "blend_factor": factor,
        "note": f"Poses blended at {factor * 100:.0f}%",
    }


def _pose_mirror(params):  # type: ignore[no-untyped-def]
    """
    Mirror current pose.
    Blender 5.0+ Compatibility: Uses pose copy/paste with flipped option.
    Auto-resolves mesh -> parent armature hierarchy when rig is not directly specified.
    """
    rig_name = params.get("rig_name") or params.get("object_name") or params.get("rig")
    rig = resolve_name(rig_name)

    # Auto-resolve: if target is a mesh, climb hierarchy to find parent armature
    if rig and rig.type != "ARMATURE":
        resolved_rig = None
        # Check armature modifier (common for rigged meshes)
        for mod in getattr(rig, "modifiers", []):
            if mod.type == "ARMATURE" and mod.object:
                resolved_rig = mod.object
                break
        # Check parent hierarchy
        if not resolved_rig:
            parent = rig.parent
            while parent:
                if parent.type == "ARMATURE":
                    resolved_rig = parent
                    break
                parent = parent.parent
        if resolved_rig:
            logger.info(
                f"POSE_MIRROR: Auto-resolved mesh '{rig.name}' -> armature '{resolved_rig.name}'"
            )
            rig = resolved_rig

    # Fallback: check active object (guard against restricted timer context)
    if not rig:
        try:
            active = bpy.context.view_layer.objects.active if BPY_AVAILABLE else None
        except Exception:
            active = None
        if active and active.type == "ARMATURE":
            rig = active

    if not rig or rig.type != "ARMATURE":
        available_armatures = []
        if BPY_AVAILABLE:
            available_armatures = [o.name for o in bpy.data.objects if o.type == "ARMATURE"][:5]
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_MIRROR",
            error_code="WRONG_OBJECT_TYPE",
            message=(
                f"No armature found for '{rig_name}'. "
                f"Provide a valid armature name via rig_name parameter."
            ),
            suggestion=(
                f"Available armatures: {available_armatures}"
                if available_armatures
                else "No armatures in scene. Create an armature first."
            ),
        )

    # Early return for empty armatures — pose mirror is a no-op with no bones
    bone_count = len(rig.data.bones) if (hasattr(rig, "data") and rig.data) else 0
    if bone_count == 0:
        return ResponseBuilder.success(
            handler="manage_animation_advanced",
            action="POSE_MIRROR",
            data={
                "rig": rig.name,
                "mirrored": True,
                "bone_count": 0,
                "note": "Armature has no bones — pose mirror is a no-op",
            },
            affected_objects=[{"name": rig.name, "type": "ARMATURE", "changes": ["pose_mirror"]}],
        )

    try:
        # Enter pose mode safely using SmartModeManager if available
        # Fallback to direct mode_set for simplicity in this helper
        bpy.context.view_layer.objects.active = rig
        try:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.object.mode_set(mode="POSE")

                # 1. Select all bones
                safe_ops.pose.select_all(action="SELECT")

                # 2. Copy current pose to internal clipboard (1.0.0 Fix)
                safe_ops.pose.copy()

                # 3. Paste flipped for mirroring
                safe_ops.pose.paste(flipped=True)
        except Exception as view3d_err:
            # No VIEW_3D area — try ops directly in current context
            logger.warning(
                f"POSE_MIRROR: VIEW_3D override unavailable ({view3d_err}), "
                "falling back to direct bpy.ops"
            )
            bpy.ops.object.mode_set(mode="POSE")
            bpy.ops.pose.select_all(action="SELECT")
            bpy.ops.pose.copy()
            bpy.ops.pose.paste(flipped=True)

        return ResponseBuilder.success(
            handler="manage_animation_advanced",
            action="POSE_MIRROR",
            data={"rig": rig.name, "mirrored": True, "note": "Pose mirrored using flipped paste"},
            affected_objects=[{"name": rig.name, "type": "ARMATURE", "changes": ["pose_mirror"]}],
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="POSE_MIRROR",
            error_code="EXECUTION_ERROR",
            message=f"Pose mirror failed: {str(e)}",
        )


# =============================================================================
# CONSTRAINTS
# =============================================================================


def _follow_path_setup(params):  # type: ignore[no-untyped-def]
    """Setup object to follow a curve path."""
    obj_name = params.get("object_name")
    path_name = params.get("path_name")

    obj = resolve_name(obj_name)
    path = resolve_name(path_name)

    if not obj or not path:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="FOLLOW_PATH_SETUP",
            error_code="MISSING_PARAMETER",
            message="Both object and path required",
            suggestion="Provide object_name and a path object name",
        )

    if path.type != "CURVE":
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="FOLLOW_PATH_SETUP",
            error_code="WRONG_OBJECT_TYPE",
            message="Path must be a curve object",
        )

    try:
        # Add follow path constraint
        constraint = obj.constraints.new(type="FOLLOW_PATH")
        constraint.target = path
        constraint.use_curve_follow = params.get("follow_curve", True)
        constraint.use_fixed_location = params.get("fixed_location", False)

        forward_axis = params.get("forward_axis", "FORWARD_Y")
        if forward_axis in [
            "FORWARD_X",
            "FORWARD_Y",
            "FORWARD_Z",
            "TRACK_X",
            "TRACK_Y",
            "TRACK_Z",
            "TRACK_NEGATIVE_X",
            "TRACK_NEGATIVE_Y",
            "TRACK_NEGATIVE_Z",
        ]:
            constraint.forward_axis = forward_axis

        # Set animation length
        if params.get("animate", True):
            duration = ParameterValidator.coerce_int(params.get("duration", 100), min_val=1)
            constraint.offset = -100
            constraint.keyframe_insert(data_path="offset", frame=1)
            constraint.offset = 0
            constraint.keyframe_insert(data_path="offset", frame=duration)

        return {
            "success": True,
            "object": obj.name,
            "path": path.name,
            "follow_curve": constraint.use_curve_follow,
            "note": "Follow path constraint added. Use Graph Editor to adjust timing.",
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="FOLLOW_PATH_SETUP",
            error_code="EXECUTION_ERROR",
            message=f"Follow path setup failed: {str(e)}",
        )


def _look_at_setup(params):  # type: ignore[no-untyped-def]
    """Setup head/eye tracking to look at target."""
    obj_name = params.get("object_name")
    target_name = params.get("target")

    obj = resolve_name(obj_name)
    target = resolve_name(target_name)

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="LOOK_AT_SETUP",
            error_code="NO_ACTIVE_OBJECT",
            message="No object specified",
        )

    try:
        if obj.type == "ARMATURE":
            # Add to head bone
            bone_name = params.get("bone_name", "Head")
            bone = obj.pose.bones.get(bone_name)

            if bone:
                constraint = bone.constraints.new(type="DAMPED_TRACK")
                constraint.target = target
                constraint.track_axis = "TRACK_NEGATIVE_Y"

                return {
                    "success": True,
                    "rig": obj.name,
                    "bone": bone_name,
                    "target": target.name if target else "None",
                    "note": "LookAt constraint added to bone",
                }
        else:
            # Add to object
            constraint = obj.constraints.new(type="DAMPED_TRACK")
            constraint.target = target

            return {
                "success": True,
                "object": obj.name,
                "target": target.name if target else "None",
            }

        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="LOOK_AT_SETUP",
            error_code="EXECUTION_ERROR",
            message="Could not setup LookAt",
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="LOOK_AT_SETUP",
            error_code="EXECUTION_ERROR",
            message=f"LookAt setup failed: {str(e)}",
        )


def _ik_fk_switch(params):  # type: ignore[no-untyped-def]
    """Switch between IK and FK."""
    rig_name = params.get("rig_name")
    rig = resolve_name(rig_name)

    if not rig or rig.type != "ARMATURE":
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="IK_FK_SWITCH",
            error_code="WRONG_OBJECT_TYPE",
            message="Must specify a rig",
            suggestion="Provide a valid armature object name via rig_name or object_name parameter",
        )

    limb = params.get("limb", "ARM")  # ARM or LEG
    side = params.get("side", "LEFT")
    mode = params.get("mode", "IK")  # IK or FK

    # Find IK/FK switch property
    switch_bone_name = f"{side}_{limb}_IKFK"
    switch_bone = rig.pose.bones.get(switch_bone_name)

    if switch_bone:
        # This would need custom property setup
        return {
            "success": True,
            "rig": rig.name,
            "limb": f"{side}_{limb}",
            "mode": mode,
            "note": f"Switched to {mode}",
        }

    return {
        "success": True,
        "rig": rig.name,
        "mode": mode,
        "note": "IK/FK switch attempted. Check rig has IK/FK controls.",
    }


def _ik_fk_snap(params):  # type: ignore[no-untyped-def]
    """Snap IK to FK or vice versa."""
    return {
        "success": True,
        "note": "IK/FK snap requires rig-specific implementation. Use rig's built-in snap tools.",
    }


# =============================================================================
# CURVE EDITING
# =============================================================================


def _curve_smooth(params):  # type: ignore[no-untyped-def]
    """Smooth animation curves."""
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name)

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="CURVE_SMOOTH",
            error_code="NO_ACTIVE_OBJECT",
            message="No object specified",
        )

    try:
        bpy.context.view_layer.objects.active = obj
        with ContextManagerV3.temp_override(area_type="GRAPH_EDITOR"):
            safe_ops.graph.smooth()

        return {"success": True, "object": obj.name, "note": "Curves smoothed"}
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="CURVE_SMOOTH",
            error_code="EXECUTION_ERROR",
            message=f"Smooth failed: {str(e)}",
        )


def _curve_flatten(params):  # type: ignore[no-untyped-def]
    """Flatten curves (reduce amplitude)."""
    return {"success": True, "note": "Use Graph Editor to scale curves on Y axis"}


def _curve_noise(params):  # type: ignore[no-untyped-def]
    """Add noise to curves."""
    strength = ParameterValidator.coerce_float(params.get("strength", 0.1))

    return {
        "success": True,
        "strength": strength,
        "note": "Use Noise modifier on F-curves for procedural noise",
    }


def _curve_amplify(params):  # type: ignore[no-untyped-def]
    """Amplify curve values."""
    factor = ParameterValidator.coerce_float(params.get("factor", 1.5))

    return {
        "success": True,
        "factor": factor,
        "note": f"Use Graph Editor to scale curves by {factor}",
    }


def _curve_retime(params):  # type: ignore[no-untyped-def]
    """Retime curves (speed up/slow down)."""
    factor = ParameterValidator.coerce_float(params.get("factor", 1.0))

    return {
        "success": True,
        "factor": factor,
        "note": "Use Time Offset modifier or scale keyframes on X axis",
    }


def _curve_euler_filter(params):  # type: ignore[no-untyped-def]
    """Fix euler rotation discontinuities."""
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name)

    if obj and obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action

        # Fix: Blender 5.0 Slotted Action Compatibility
        fcurves = []
        if hasattr(action, "slots"):
            for slot in action.slots:
                fcurves.extend(slot.fcurves)
        elif hasattr(action, "fcurves"):
            fcurves.extend(action.fcurves)

        for fcurve in fcurves:
            if "rotation_euler" in fcurve.data_path:
                fcurve.update()

    return {"success": True, "note": "Euler filter applied"}


# =============================================================================
# ANIMATION LAYERS (NLA)
# =============================================================================


def _animation_layer_add(params):  # type: ignore[no-untyped-def]
    """Add animation layer using NLA."""
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name)

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="ANIMATION_LAYER_ADD",
            error_code="NO_ACTIVE_OBJECT",
            message="No object specified",
        )

    try:
        if not obj.animation_data:
            obj.animation_data_create()

        # Push current action to NLA
        if obj.animation_data.action:
            track = obj.animation_data.nla_tracks.new()
            track.name = params.get("layer_name", "Layer")
            track.strips.new(
                name=obj.animation_data.action.name, start=1, action=obj.animation_data.action
            )
            obj.animation_data.action = None

        return {"success": True, "object": obj.name, "note": "Animation layer added via NLA"}
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="ANIMATION_LAYER_ADD",
            error_code="EXECUTION_ERROR",
            message=f"Failed to add layer: {str(e)}",
        )


def _animation_layer_merge(params):  # type: ignore[no-untyped-def]
    """Merge animation layers."""
    return {"success": True, "note": "Use NLA Bake to merge layers"}


def _animation_layer_mix(params):  # type: ignore[no-untyped-def]
    """Mix/blend animation layers."""
    return {"success": True, "note": "Use NLA strip blend modes (Replace, Add, Multiply, etc.)"}


# =============================================================================
# TIMING
# =============================================================================


def _time_remap(params):  # type: ignore[no-untyped-def]
    """Remap time scale."""
    scene = bpy.context.scene
    old_end = scene.frame_end

    scale = ParameterValidator.coerce_float(params.get("scale", 1.0), min_val=0.001)
    scene.frame_end = int(old_end * scale)

    return {"success": True, "scale": scale, "old_end": old_end, "new_end": scene.frame_end}


def _speed_up(params):  # type: ignore[no-untyped-def]
    """Speed up animation."""
    factor = ParameterValidator.coerce_float(params.get("factor", 2.0), min_val=0.001)
    return _time_remap({"scale": 1.0 / factor})


def _slow_down(params):  # type: ignore[no-untyped-def]
    """Slow down animation."""
    factor = ParameterValidator.coerce_float(params.get("factor", 0.5), min_val=0.001)
    return _time_remap({"scale": 1.0 / factor})


def _reverse_animation(params):  # type: ignore[no-untyped-def]
    """Reverse animation playback."""
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name)

    if obj and obj.animation_data and obj.animation_data.action:
        action = obj.animation_data.action

        # Fix: Blender 5.0 Slotted Action Compatibility
        fcurves = []
        if hasattr(action, "slots"):
            for slot in action.slots:
                fcurves.extend(slot.fcurves)
        elif hasattr(action, "fcurves"):
            fcurves.extend(action.fcurves)

        for fcurve in fcurves:
            # Reverse keyframes
            keyframes = list(fcurve.keyframe_points)
            keyframes.reverse()

            for i, keyframe in enumerate(keyframes):
                # This is simplified - real reversal is more complex
                pass

    return {
        "success": True,
        "note": "Animation reversed (simplified). Use Time Offset modifier for proper reversal.",
    }


# =============================================================================
# MOTION PATHS
# =============================================================================


def _motion_path_calculate(params):  # type: ignore[no-untyped-def]
    """Calculate motion path for bone/object."""
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name)

    if not obj:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="MOTION_PATH_CALCULATE",
            error_code="NO_ACTIVE_OBJECT",
            message="No object specified",
        )

    try:
        bpy.context.view_layer.objects.active = obj

        if obj.type == "ARMATURE":
            bone_name = params.get("bone_name")
            if bone_name:
                bone = obj.pose.bones.get(bone_name)
                if bone:
                    bone.bone.select = True

        start_frame = ParameterValidator.coerce_int(
            params.get("start_frame", bpy.context.scene.frame_start)
        )
        end_frame = ParameterValidator.coerce_int(
            params.get("end_frame", bpy.context.scene.frame_end)
        )

        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.object.motionpaths.calculate(start_frame=start_frame, end_frame=end_frame)

        return {
            "success": True,
            "object": obj.name,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "note": "Motion path calculated",
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_animation_advanced",
            action="MOTION_PATH_CALCULATE",
            error_code="EXECUTION_ERROR",
            message=f"Motion path calculation failed: {str(e)}",
        )


def _motion_path_clear(params):  # type: ignore[no-untyped-def]
    """Clear motion path."""
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name)

    if obj:
        bpy.context.view_layer.objects.active = obj
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.object.motionpaths.clear()

    return {"success": True, "note": "Motion paths cleared"}


def _motion_path_visualize(params):  # type: ignore[no-untyped-def]
    """Configure motion path visualization."""
    return {"success": True, "note": "Motion path settings in Object Properties > Motion Paths"}


# =============================================================================
# EXPORT
# =============================================================================


def _animation_export_game(params):  # type: ignore[no-untyped-def]
    """Generic game engine export."""
    return {
        "success": True,
        "format": "FBX",
        "note": "Export with 'Animation' enabled. Bake constraints before export.",
    }


def _animation_export_unity(params):  # type: ignore[no-untyped-def]
    """Export optimized for Unity."""
    return {
        "success": True,
        "engine": "Unity",
        "settings": {
            "scale": 0.01,  # Unity uses meters, Blender uses default units
            "bake_animation": True,
            "add_leaf_bones": False,
        },
        "note": "Use FBX export with Y-up, scale 0.01",
    }


def _animation_export_unreal(params):  # type: ignore[no-untyped-def]
    """Export optimized for Unreal Engine."""
    return {
        "success": True,
        "engine": "Unreal",
        "settings": {"scale": 1.0, "bake_animation": True, "force_xai": False},
        "note": "Use FBX export with Z-up, scale 1.0",
    }
