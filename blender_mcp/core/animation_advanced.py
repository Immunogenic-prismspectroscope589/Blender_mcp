"""
Advanced Animation System for Blender MCP 1.0.0

Implements:
- Action Slots (Blender 5.0)
- NLA (Non-Linear Animation)
- FCurve Modifiers
- Keyframe Interpolation
- Driver-based Animation

High Mode Philosophy: Control every animation detail.
"""

from typing import TYPE_CHECKING, Dict, Any, List, Optional, cast
from enum import Enum

if TYPE_CHECKING:
    import bpy

    # from bpy.types import FCurve, Keyframe # REMOVED F401
    # import mathutils # REMOVED F401
    # from mathutils import Vector, Euler, Quaternion # REMOVED F401

try:
    if not TYPE_CHECKING:
        import bpy

        # from bpy.types import FCurve, Keyframe # REMOVED F401
        # import mathutils # REMOVED F401
        # from mathutils import Vector, Euler, Quaternion # REMOVED F401
    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]

from .context_manager_v3 import ContextManagerV3
from .thread_safety import execute_on_main_thread, SafeOperators
from .error_protocol import ErrorProtocol, create_error
from .logging_config import get_logger

logger = get_logger()


class InterpolationType(Enum):
    """Keyframe interpolation types."""

    CONSTANT = "CONSTANT"
    LINEAR = "LINEAR"
    BEZIER = "BEZIER"
    SINE = "SINE"
    QUAD = "QUAD"
    CUBIC = "CUBIC"
    QUART = "QUART"
    QUINT = "QUINT"
    EXPO = "EXPO"
    CIRC = "CIRC"
    BACK = "BACK"
    BOUNCE = "BOUNCE"
    ELASTIC = "ELASTIC"


class EasingType(Enum):
    """Easing types for interpolation."""

    AUTO = "AUTO"
    EASE_IN = "EASE_IN"
    EASE_OUT = "EASE_OUT"
    EASE_IN_OUT = "EASE_IN_OUT"


class NLAManager:
    """
    Non-Linear Animation management for complex animation layering.
    """

    @staticmethod
    def push_to_nla(
        obj: Any,
        track_name: Optional[str] = None,
        start_frame: int = 1,
        blend_type: str = "REPLACE",
    ) -> Dict[str, Any]:
        """
        Push current action to NLA stack.

        Args:
            obj: Animated object
            track_name: Custom track name (optional)
            start_frame: Start frame for strip
            blend_type: 'REPLACE', 'ADD', 'SUBTRACT', 'MULTIPLY'
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            if not obj.animation_data or not obj.animation_data.action:
                return create_error(
                    ErrorProtocol.NO_CONTEXT, custom_message="Object has no active action"
                )

            ad = obj.animation_data
            action = ad.action

            if not track_name:
                track_name = f"Track_{action.name}"

            def execution() -> Dict[str, Any]:
                # Push down
                if bpy.context.view_layer:
                    bpy.context.view_layer.objects.active = obj
                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    SafeOperators.nla_bake(
                        frame_start=start_frame,
                        frame_end=int(action.frame_range[1]),
                        only_selected=False,
                        visual_keying=False,
                        clear_parents=False,
                        clean_curves=False,
                        bake_types={"OBJECT"},
                    )

                return {
                    "success": True,
                    "object": obj.name,
                    "action": action.name,
                    "track": track_name,
                    "start_frame": start_frame,
                }

            return cast(Dict[str, Any], execute_on_main_thread(execution))

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"NLA push failed: {str(e)}"
            )

    @staticmethod
    def create_nla_track(obj: Any, track_name: str) -> Dict[str, Any]:
        """
        Create new NLA track.
        """
        try:
            if not obj.animation_data:
                obj.animation_data_create()

            ad = obj.animation_data
            track = ad.nla_tracks.new()
            track.name = track_name

            return {
                "success": True,
                "object": obj.name,
                "track_name": track.name,
                "track_index": len(ad.nla_tracks) - 1,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"NLA track creation failed: {str(e)}"
            )

    @staticmethod
    def add_strip_to_track(
        obj: Any,
        track_index: int,
        action_name: str,
        start_frame: int = 1,
        end_frame: Optional[int] = None,
        blend_type: str = "REPLACE",
        influence: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Add action strip to NLA track.
        """
        try:
            action = bpy.data.actions.get(action_name)
            if not action:
                return create_error(ErrorProtocol.OBJECT_NOT_FOUND, object_name=action_name)

            ad = obj.animation_data
            if not ad or track_index >= len(ad.nla_tracks):
                return create_error(
                    ErrorProtocol.NO_MESH_DATA, custom_message=f"NLA track {track_index} not found"
                )

            track = ad.nla_tracks[track_index]
            strip = track.strips.new(action.name, start_frame, action)

            if end_frame:
                strip.action_frame_end = end_frame

            strip.blend_type = blend_type
            strip.influence = influence

            return {
                "success": True,
                "object": obj.name,
                "track_index": track_index,
                "action": action_name,
                "strip_name": strip.name,
                "start_frame": start_frame,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"NLA strip creation failed: {str(e)}"
            )

    @staticmethod
    def set_strip_influence(
        obj: Any, track_index: int, strip_name: str, influence: float, frame: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Set influence for NLA strip (with optional keyframe).
        """
        try:
            ad = obj.animation_data
            track = ad.nla_tracks[track_index]
            strip = track.strips.get(strip_name)

            if not strip:
                return create_error(ErrorProtocol.OBJECT_NOT_FOUND, object_name=strip_name)

            strip.influence = influence

            if frame is not None:
                # Keyframe the influence
                strip.influence = influence
                strip.keyframe_insert(data_path="influence", frame=frame)

            return {
                "success": True,
                "strip": strip_name,
                "influence": influence,
                "keyframed": frame is not None,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Influence set failed: {str(e)}"
            )


class FCurveModifierManager:
    """
    Manage FCurve modifiers for procedural animation effects.
    """

    MODIFIER_TYPES = {
        "GENERATOR": "Generator",
        "FNGENERATOR": "Built-in Function",
        "ENVELOPE": "Envelope",
        "NOISE": "Noise",
        "CYCLES": "Cycles",
        "STEPPED": "Stepped",
        "LIMITS": "Limits",
    }

    @staticmethod
    def add_noise_modifier(
        obj: Any,
        data_path: str,
        strength: float = 1.0,
        scale: float = 1.0,
        phase: float = 0.0,
        offset: float = 0.0,
        depth: int = 0,
    ) -> Dict[str, Any]:
        """
        Add noise modifier to FCurve.

        Args:
            strength: Amplitude of noise
            scale: Scale of noise in frames
            phase: Phase offset
            offset: Vertical offset
            depth: Number of octaves (0-5)
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            fcurve = FCurveModifierManager._get_fcurve(obj, data_path)
            if not fcurve:
                return create_error(
                    ErrorProtocol.OBJECT_NOT_FOUND,
                    custom_message=f"FCurve for {data_path} not found",
                )

            mod = fcurve.modifiers.new(type="NOISE")
            mod.strength = strength
            mod.scale = scale
            mod.phase = phase
            mod.offset = offset
            mod.depth = depth

            return {
                "success": True,
                "object": obj.name,
                "data_path": data_path,
                "modifier": "NOISE",
                "strength": strength,
                "scale": scale,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Noise modifier failed: {str(e)}"
            )

    @staticmethod
    def add_cycles_modifier(
        obj: Any,
        data_path: str,
        mode_before: str = "REPEAT",
        mode_after: str = "REPEAT",
        cycles_before: int = 0,
        cycles_after: int = 0,
    ) -> Dict[str, Any]:
        """
        Add cycles modifier for looping animation.

        Args:
            mode_before: 'NONE', 'REPEAT', 'REPEAT_MIRROR', 'PINGPONG'
            mode_after: 'NONE', 'REPEAT', 'REPEAT_MIRROR', 'PINGPONG'
        """
        try:
            fcurve = FCurveModifierManager._get_fcurve(obj, data_path)
            if not fcurve:
                return create_error(
                    ErrorProtocol.OBJECT_NOT_FOUND,
                    custom_message=f"FCurve for {data_path} not found",
                )

            mod = fcurve.modifiers.new(type="CYCLES")
            mod.mode_before = mode_before
            mod.mode_after = mode_after
            mod.cycles_before = cycles_before
            mod.cycles_after = cycles_after

            return {
                "success": True,
                "object": obj.name,
                "data_path": data_path,
                "modifier": "CYCLES",
                "mode_before": mode_before,
                "mode_after": mode_after,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Cycles modifier failed: {str(e)}"
            )

    @staticmethod
    def add_envelope_modifier(
        obj: Any, data_path: str, default_min: float = 0.0, default_max: float = 1.0
    ) -> Dict[str, Any]:
        """
        Add envelope modifier with control points.
        """
        try:
            fcurve = FCurveModifierManager._get_fcurve(obj, data_path)
            if not fcurve:
                return create_error(
                    ErrorProtocol.OBJECT_NOT_FOUND,
                    custom_message=f"FCurve for {data_path} not found",
                )

            mod = fcurve.modifiers.new(type="ENVELOPE")
            mod.default_min = default_min
            mod.default_max = default_max

            return {"success": True, "object": obj.name, "modifier": "ENVELOPE"}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Envelope modifier failed: {str(e)}"
            )

    @staticmethod
    def add_limits_modifier(
        obj: Any,
        data_path: str,
        use_min: bool = False,
        use_max: bool = False,
        min_value: float = 0.0,
        max_value: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Add limits modifier to clamp FCurve values.
        """
        try:
            fcurve = FCurveModifierManager._get_fcurve(obj, data_path)
            if not fcurve:
                return create_error(
                    ErrorProtocol.OBJECT_NOT_FOUND,
                    custom_message=f"FCurve for {data_path} not found",
                )

            mod = fcurve.modifiers.new(type="LIMITS")
            mod.use_min_x = use_min
            mod.use_max_x = use_max
            mod.min_x = min_value
            mod.max_x = max_value

            return {
                "success": True,
                "object": obj.name,
                "modifier": "LIMITS",
                "min": min_value if use_min else None,
                "max": max_value if use_max else None,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Limits modifier failed: {str(e)}"
            )

    @staticmethod
    def _get_fcurve(obj: Any, data_path: str) -> Optional[Any]:
        """Get or create FCurve for data path."""
        if not obj.animation_data:
            obj.animation_data_create()

        ad = obj.animation_data
        if not ad.action:
            ad.action = bpy.data.actions.new(name=f"{obj.name}_Action")

        # Try to find existing
        action = ad.action
        fcurves_list = []
        if hasattr(action, "slots") and action.slots:
            for slot in action.slots:
                fcurves_list.extend(list(slot.fcurves))
        elif hasattr(action, "fcurves"):
            fcurves_list.extend(list(action.fcurves))

        for fcurve in fcurves_list:
            if getattr(fcurve, "data_path", "") == data_path:
                return fcurve

        # Create new
        if hasattr(action, "fcurves"):
            return action.fcurves.new(data_path=data_path)
        elif hasattr(action, "slots") and action.slots:
            return action.slots[0].fcurves.new(data_path=data_path)
        return None


class KeyframeManager:
    """
    Advanced keyframe manipulation.
    """

    @staticmethod
    def insert_keyframe_with_interpolation(
        obj: Any,
        data_path: str,
        frame: int,
        value: float,
        interpolation: str = "BEZIER",
        easing: str = "AUTO",
        handle_type: str = "AUTO_CLAMPED",
    ) -> Dict[str, Any]:
        """
        Insert keyframe with specific interpolation settings.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Insert keyframe
            obj.keyframe_insert(data_path=data_path, frame=frame)

            # Get FCurve and set interpolation
            fcurve = None
            if obj.animation_data and obj.animation_data.action:
                action = obj.animation_data.action
                fcurves_list = []
                if hasattr(action, "slots") and action.slots:
                    for slot in action.slots:
                        fcurves_list.extend(list(slot.fcurves))
                elif hasattr(action, "fcurves"):
                    fcurves_list.extend(list(action.fcurves))

                for fc in fcurves_list:
                    if getattr(fc, "data_path", "") == data_path:
                        fcurve = fc
                        break

            if fcurve:
                for kp in fcurve.keyframe_points:
                    if kp.co[0] == frame:
                        kp.interpolation = interpolation
                        kp.easing = easing
                        kp.handle_left_type = handle_type
                        kp.handle_right_type = handle_type
                        break

            return {
                "success": True,
                "object": obj.name,
                "data_path": data_path,
                "frame": frame,
                "value": value,
                "interpolation": interpolation,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Keyframe insertion failed: {str(e)}"
            )

    @staticmethod
    def copy_keyframe_range(
        source_obj: Any,
        target_obj: Any,
        data_path: str,
        frame_start: int,
        frame_end: int,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Copy keyframe range from one object to another.
        """
        try:
            if not source_obj.animation_data or not source_obj.animation_data.action:
                return create_error(
                    ErrorProtocol.NO_CONTEXT, custom_message="Source has no animation"
                )

            source_action = source_obj.animation_data.action
            target_action = target_obj.animation_data.action if target_obj.animation_data else None

            if not target_action:
                target_obj.animation_data_create()
                target_action = bpy.data.actions.new(name=f"{target_obj.name}_Action")
                target_obj.animation_data.action = target_action

            copied = 0

            source_fcurves = []
            if hasattr(source_action, "slots") and source_action.slots:
                for slot in source_action.slots:
                    source_fcurves.extend(list(slot.fcurves))
            elif hasattr(source_action, "fcurves"):
                source_fcurves.extend(list(source_action.fcurves))

            for fcurve in source_fcurves:
                if getattr(fcurve, "data_path", "") == data_path:
                    # Create target fcurve
                    if hasattr(target_action, "fcurves"):
                        target_fcurve = target_action.fcurves.new(data_path=data_path)
                    elif hasattr(target_action, "slots") and target_action.slots:
                        target_fcurve = target_action.slots[0].fcurves.new(data_path=data_path)
                    else:
                        continue

                    for kp in fcurve.keyframe_points:
                        if frame_start <= kp.co[0] <= frame_end:
                            new_frame = kp.co[0] + offset
                            target_kp = target_fcurve.keyframe_points.insert(
                                new_frame, kp.co[1], options={"FAST"}
                            )
                            target_kp.interpolation = kp.interpolation
                            target_kp.handle_left = kp.handle_left
                            target_kp.handle_right = kp.handle_right
                            copied += 1

            return {
                "success": True,
                "source": source_obj.name,
                "target": target_obj.name,
                "frames_copied": copied,
                "frame_range": (frame_start + offset, frame_end + offset),
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Keyframe copy failed: {str(e)}"
            )

    @staticmethod
    def ease_in_out_keyframes(
        obj: Any, data_path: str, frame_start: int, frame_end: int, ease_type: str = "EASE_IN_OUT"
    ) -> Dict[str, Any]:
        """
        Apply easing to all keyframes in range.
        """
        try:
            if not obj.animation_data or not obj.animation_data.action:
                return create_error(ErrorProtocol.NO_CONTEXT)

            modified = 0
            action = obj.animation_data.action

            fcurves_list = []
            if hasattr(action, "slots") and action.slots:
                for slot in action.slots:
                    fcurves_list.extend(list(slot.fcurves))
            elif hasattr(action, "fcurves"):
                fcurves_list.extend(list(action.fcurves))

            for fcurve in fcurves_list:
                if getattr(fcurve, "data_path", "") == data_path:
                    for kp in fcurve.keyframe_points:
                        if frame_start <= kp.co[0] <= frame_end:
                            kp.easing = ease_type
                            modified += 1

            return {
                "success": True,
                "object": obj.name,
                "keyframes_modified": modified,
                "easing": ease_type,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Easing apply failed: {str(e)}"
            )


class DriverManager:
    """
    Create and manage drivers for procedural animation.
    """

    @staticmethod
    def add_variable_driver(
        target_obj: Any,
        target_data_path: str,
        driver_type: str = "SUM",
        variables: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Add driver with variables.

        Args:
            variables: List of variable configs
                [{"name": "var1", "type": "TRANSFORMS",
                  "target": obj, "data_path": "location", ...}]
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Create driver
            driver = target_obj.driver_add(target_data_path)
            driver.driver.type = driver_type

            # Add variables
            created_vars = []
            if variables:
                for var_config in variables:
                    var = driver.driver.variables.new()
                    var.name = var_config.get("name", "var")
                    var.type = var_config.get("type", "SINGLE_PROP")

                    target = var_config.get("target")
                    if target and var.targets:
                        var.targets[0].id = target
                        var.targets[0].data_path = var_config.get("data_path", "location")

                    created_vars.append(var.name)

            # Set expression if scripted
            if driver_type == "SCRIPTED":
                driver.driver.expression = var_config.get("expression", "var")

            return {
                "success": True,
                "target": target_obj.name,
                "data_path": target_data_path,
                "driver_type": driver_type,
                "variables": created_vars,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Driver creation failed: {str(e)}"
            )

    @staticmethod
    def add_noise_driver(
        obj: Any,
        data_path: str,
        frame_var: str = "frame",
        frequency: float = 1.0,
        amplitude: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Add noise-based driver using noise.noise() function.
        """
        try:
            driver = obj.driver_add(data_path)
            driver.driver.type = "SCRIPTED"

            # Create frame variable
            var = driver.driver.variables.new()
            var.name = "frame"
            var.type = "FRAME"

            # Expression using noise
            driver.driver.expression = f"{amplitude} * noise.noise(frame * {frequency})"

            return {
                "success": True,
                "object": obj.name,
                "data_path": data_path,
                "expression": driver.driver.expression,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Noise driver failed: {str(e)}"
            )


class AnimationBaker:
    """
    Bake animation for export or optimization.
    """

    @staticmethod
    def bake_action(
        obj: Any,
        frame_start: int,
        frame_end: int,
        step: int = 1,
        only_selected: bool = False,
        visual_keying: bool = True,
        clear_constraints: bool = False,
        clear_parents: bool = False,
        bake_types: Optional[set] = None,
    ) -> Dict[str, Any]:
        """
        Bake object animation to keyframes.

        Args:
            bake_types: {'POSE', 'OBJECT'} or combination
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            if bake_types is None:
                bake_types = {"OBJECT"}

            # Store original mode
            original_mode = obj.mode

            def execution() -> Dict[str, Any]:
                # Select object
                if bpy.context.view_layer:
                    bpy.context.view_layer.objects.active = obj
                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    SafeOperators.mode_set(mode="OBJECT")

                    # Bake
                    SafeOperators.nla_bake(
                        frame_start=frame_start,
                        frame_end=frame_end,
                        step=step,
                        only_selected=only_selected,
                        visual_keying=visual_keying,
                        clear_constraints=clear_constraints,
                        clear_parents=clear_parents,
                        bake_types=bake_types,
                        object=obj,
                    )

                    # Restore mode if it was a pose bake
                    if "POSE" in bake_types and original_mode == "POSE":
                        SafeOperators.mode_set(mode="POSE")

                return {
                    "success": True,
                    "object": obj.name,
                    "frame_range": (frame_start, frame_end),
                    "step": step,
                    "bake_types": list(bake_types),
                }

            return cast(Dict[str, Any], execute_on_main_thread(execution))

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Bake failed: {str(e)}"
            )

    @staticmethod
    def bake_constraints(obj: Any, frame_start: int, frame_end: int) -> Dict[str, Any]:
        """
        Bake constraints to keyframes (preserve visual result).
        """
        return AnimationBaker.bake_action(
            obj, frame_start, frame_end, visual_keying=True, clear_constraints=True
        )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "NLAManager",
    "FCurveModifierManager",
    "KeyframeManager",
    "DriverManager",
    "AnimationBaker",
    "InterpolationType",
    "EasingType",
]
