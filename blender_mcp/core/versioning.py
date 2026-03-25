"""
Enhanced Blender API Version Compatibility System
Handles API differences between Blender 4.x and 5.x with automatic fallback strategies.
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional
import bpy

from .thread_safety import execute_on_main_thread, SafeOperators, ensure_main_thread
from .context_manager_v3 import ContextManagerV3


class BlenderCompatibility:
    """
    Comprehensive Blender API compatibility layer.
    Provides version-specific implementations with automatic fallbacks.
    Acts as the Single Source of Truth (SSOT) for versioning logic.
    """

    # High Mode: Coerce to tuple (handles MagicMock in tests)
    try:
        _raw_version = getattr(getattr(bpy, "app", None), "version", (5, 0, 0))
        if _raw_version and len(_raw_version) >= 3:
            VERSION = tuple(int(v) for v in _raw_version[:3])
        else:
            VERSION = (5, 0, 0)
    except (TypeError, ValueError, IndexError):
        VERSION = (5, 0, 0)

    VERSION_MAJOR = VERSION[0]
    VERSION_MINOR = VERSION[1]

    @classmethod
    def is_version(cls, major: int, minor: int = 0, micro: int = 0) -> bool:
        """Check if current version meets minimum requirement"""
        try:
            return cls.VERSION >= (major, minor, micro)
        except TypeError:
            return True

    @classmethod
    def is_blender5(cls) -> bool:
        """Check if running Blender 5.x"""
        return cls.VERSION_MAJOR >= 5

    @classmethod
    def is_blender4(cls) -> bool:
        """Check if running Blender 4.x"""
        return cls.VERSION_MAJOR == 4

    @classmethod
    def use_auto_smooth_modifier(cls) -> bool:
        """
        Check if Auto Smooth should be applied via modifier (Blender 4.1+).
        In Blender 4.1, mesh.use_auto_smooth was removed and replaced by a modifier.
        """
        return cls.is_version(4, 1, 0)

    # ==================== CONTEXT OVERRIDES ====================

    @classmethod
    def get_context_override(cls, area_type: str = "VIEW_3D") -> Optional[Dict[str, Any]]:
        """
        Get context override for operators requiring specific areas.
        """
        if cls.is_version(5, 0, 0):
            return None  # Use temp_override with context manager

        # Legacy override for Blender 4.x
        if not bpy.context.window:
            return None
        window = bpy.context.window
        screen = window.screen
        if not screen:
            return None
        for area in screen.areas:
            if area.type == area_type:
                for region in area.regions:
                    if region.type == "WINDOW":
                        return {
                            "window": window,
                            "screen": screen,
                            "area": area,
                            "region": region,
                        }
        return None

    @classmethod
    def temp_override(cls, area_type: str = "VIEW_3D") -> Any:
        """
        Context manager for temporary context override.
        Works with both Blender 4.x and 5.x.
        """

        class OverrideContext:
            def __init__(self, compat_cls: Any, area_type: str) -> None:
                self.compat = compat_cls
                self.area_type = area_type
                self.override_dict = None
                self.temp_override: Optional[Any] = None

            def __enter__(self) -> Optional[Any]:
                if self.compat.is_version(5, 0, 0):
                    # Blender 5.0+: Use temp_override logic (simplified for now)
                    # For strict 5.0, we might need to find window/area first to pass to temp_override
                    # But bpy.context.temp_override usually takes named args found in context
                    # If we need specific area, we might need to find it first

                    # Try to find window/area/region even for 5.0 to be safe
                    context_dict = self.compat._get_context_dict(self.area_type)
                    if context_dict and hasattr(bpy.context, "temp_override"):
                        self.temp_override = bpy.context.temp_override(**context_dict)
                        if self.temp_override:
                            return self.temp_override.__enter__()
                else:
                    self.override_dict = self.compat.get_context_override(self.area_type)
                    return self.override_dict
                return None

            def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
                if self.temp_override:
                    return self.temp_override.__exit__(exc_type, exc_val, exc_tb)
                return False

        return OverrideContext(cls, area_type)

    @classmethod
    def _get_context_dict(cls, area_type: str) -> Dict[str, Any]:
        """Helper to find context elements"""
        if not bpy.context.window:
            return {}
        window = bpy.context.window
        screen = window.screen
        if not screen:
            return {}
        for area in screen.areas:
            if area.type == area_type:
                for region in area.regions:
                    if region.type == "WINDOW":
                        return {
                            "window": window,
                            "screen": screen,
                            "area": area,
                            "region": region,
                        }
        return {}

    # ==================== ATTRIBUTE COMPATIBILITY ====================

    @classmethod
    def get_rigid_body_world_attr(cls, rbw: Any, attr_name: str, default: Any = None) -> Any:
        if attr_name == "steps_per_second" and cls.is_blender5():
            substeps = getattr(rbw, "substeps_per_frame", 10)
            return substeps * 60
        return getattr(rbw, attr_name, default)

    @classmethod
    def set_rigid_body_world_attr(cls, rbw: Any, attr_name: str, value: Any) -> bool:
        if attr_name == "steps_per_second" and cls.is_blender5():
            try:
                substeps = max(1, int(value) // 60)
                rbw.substeps_per_frame = substeps
                return True
            except (TypeError, ValueError):
                return False
        if hasattr(rbw, attr_name):
            setattr(rbw, attr_name, value)
            return True
        return False

    @classmethod
    @ensure_main_thread
    def copy_pose_data(cls, source_bone: Any, target_bone: Any) -> bool:
        if not source_bone or not target_bone:
            return False
        try:
            target_bone.location = source_bone.location.copy()
            target_bone.rotation_quaternion = source_bone.rotation_quaternion.copy()
            target_bone.rotation_euler = source_bone.rotation_euler.copy()
            target_bone.scale = source_bone.scale.copy()
            return True
        except Exception:
            return False

    @classmethod
    def get_sequences(cls, scene: Optional[Any] = None) -> List[Any]:
        target_scene = scene or bpy.context.scene
        if not target_scene:
            return []
        if not target_scene.sequence_editor:
            return []
        if hasattr(target_scene.sequence_editor, "sequences_all"):
            return list(target_scene.sequence_editor.sequences_all)
        return list(target_scene.sequence_editor.sequences)

    @classmethod
    @ensure_main_thread
    def new_movie_strip(
        cls, scene: Any, channel: int, filepath: str, frame_start: int, **kwargs: Any
    ) -> Any:
        if not scene.sequence_editor:
            return None
        try:
            if cls.is_blender5():
                return scene.sequence_editor.sequences.new_movie(
                    name=kwargs.get("name", "Movie"),
                    filepath=filepath,
                    channel=channel,
                    frame_start=frame_start,
                )
            else:
                return scene.sequence_editor.sequences.new_movie(
                    name=kwargs.get("name", "Movie"),
                    file=filepath,
                    channel=channel,
                    frame_start=frame_start,
                )
        except Exception:
            return None

    @classmethod
    @ensure_main_thread
    def ensure_compositor_tree(cls, scene: Optional[Any] = None) -> bool:
        target_scene = scene or bpy.context.scene
        if not target_scene:
            return False

        target_scene.use_nodes = True
        if not target_scene.node_tree:
            try:
                target_scene.node_tree = bpy.data.node_groups.new(
                    name="CompositorNodeTree",
                    type="CompositorNodeTree",
                )
            except Exception:
                return False
                return False
        return target_scene.node_tree is not None

    @classmethod
    def get_compositor_tree(cls, scene: Optional[Any] = None) -> Optional[Any]:
        target_scene = scene or bpy.context.scene
        if not target_scene:
            return None
        target_scene.use_nodes = True
        return getattr(target_scene, "node_tree", None)

    @classmethod
    @ensure_main_thread
    def get_brush_by_name(cls, brush_name: str, sculpt_tool: Optional[Any] = None) -> Optional[Any]:
        try:
            if brush_name in bpy.data.brushes:
                return bpy.data.brushes[brush_name]
            # Simple fallback
            for brush in bpy.data.brushes:
                if brush.name.lower() == brush_name.lower():
                    return brush
            return None
        except Exception:
            return None

    @classmethod
    @ensure_main_thread
    def duplicate_object(cls, obj: Any) -> Optional[Any]:
        if not obj:
            return None
        try:
            ContextManagerV3.deselect_all_objects()
            obj.select_set(True)
            if bpy.context.view_layer:
                bpy.context.view_layer.objects.active = obj
            if cls.is_blender5():
                # Avoid direct bpy.ops if possible, but duplicate usually requires ops
                # safe_ops wrapper would be better, but we are inside core.
                bpy.ops.object.duplicate_move()
            else:
                bpy.ops.object.duplicate()
            return bpy.context.active_object
        except Exception:
            return None

    @classmethod
    def get_object_by_index(cls, index: int) -> Optional[Any]:
        try:
            if not bpy.context.scene:
                return None
            objects = list(bpy.context.scene.objects)
            if 0 <= index < len(objects):
                return objects[index]
        except Exception:
            pass
        return None

    # ==================== MODE SWITCHING ====================

    @classmethod
    def ensure_mode(cls, obj: Any, target_mode: str, context: Optional[Any] = None) -> bool:
        if not obj:
            return False

        def execution() -> bool:
            local_context = context or bpy.context
            try:
                if obj.mode != target_mode:
                    with cls.temp_override(area_type="VIEW_3D"):
                        if local_context.mode != "OBJECT":
                            bpy.ops.object.mode_set(mode="OBJECT")
                        ContextManagerV3.deselect_all_objects()
                        obj.select_set(True)
                        if local_context.view_layer:
                            local_context.view_layer.objects.active = obj
                        bpy.ops.object.mode_set(mode=target_mode)
                    return True
            except Exception:
                return False
            return bool(obj.mode == target_mode)

        return bool(execute_on_main_thread(execution))

    @classmethod
    def with_mode_restore(cls, target_mode: str = "OBJECT") -> Callable:
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                obj = kwargs.get("obj") or bpy.context.active_object
                if not obj:
                    return func(*args, **kwargs)
                original_mode = obj.mode
                if target_mode != original_mode:
                    cls.ensure_mode(obj, target_mode)
                try:
                    return func(*args, **kwargs)
                finally:
                    if obj.mode != original_mode:
                        cls.ensure_mode(obj, original_mode)

            return wrapper

        return decorator

    @staticmethod
    def requires_mouse_event() -> bool:
        return bool(bpy.app.version >= (4, 0, 0))
