"""
Context Manager V3 for Blender MCP 1.0.0 "High Mode Ultra"

Advanced context management with:
- Automatic area detection and selection
- Multi-window support
- Mode transition safety with retry
- Exponential backoff for failures
- Full Blender 5.0+ compatibility
- temp_override integration

High Mode Philosophy: Context should just work.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Literal, Iterator, Tuple
from contextlib import contextmanager
from functools import wraps
from dataclasses import dataclass, field

# Blender imports
try:
    import bpy
    import mathutils

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
    mathutils: Any = None  # type: ignore[no-redef]

from .error_protocol import ErrorProtocol, create_error
from .logging_config import get_logger
from .thread_safety import SafeOperators

logger = get_logger()

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ContextSnapshot:
    """Snapshot of current Blender context for restoration."""

    scene: Optional[Any] = None
    active_object: Optional[Any] = None
    selected_objects: List[Any] = field(default_factory=list)
    mode: str = "OBJECT"


class SafeModeContext:
    """
    Context manager for safe mode switching with automatic restoration.
    V2 Compatibility Layer.
    """

    def __init__(self, target_mode: str, obj: Optional[Any] = None):
        self.target_mode = target_mode
        self.obj = obj
        self.original_mode = None
        self.original_active = None
        self.success = False

    def __enter__(self) -> bool:
        if not BPY_AVAILABLE:
            return False
        try:
            self.original_active = ContextManagerV3.get_active_object()
            if self.obj is None:
                self.obj = self.original_active
            if self.obj is None:
                return False

            self.original_mode = self.obj.mode
            if self.original_mode != self.target_mode:
                ContextManagerV3.set_active_object(self.obj)
                self.obj.select_set(True)
                SafeOperators.mode_set(mode=self.target_mode)

            self.success = True
            return True
        except Exception as e:
            logger.warning(f"SafeModeContext warning: {e}")
            self.success = False
            return False

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        if not BPY_AVAILABLE or not self.success:
            return False
        try:
            if self.original_mode and self.obj.mode != self.original_mode:
                ContextManagerV3.set_active_object(self.obj)
                SafeOperators.mode_set(mode=self.original_mode)
            if self.original_active and self.original_active.name in bpy.data.objects:
                ContextManagerV3.set_active_object(self.original_active)
        except Exception as e:
            logger.warning(f"SafeModeContext restore warning: {e}")
        return False


class SafeSelectionContext:
    """
    Context manager for temporary selection changes.
    V2 Compatibility Layer.
    """

    def __init__(self, objects: List[Any], deselect_others: bool = True):
        self.objects = [obj for obj in objects if obj and obj.name in bpy.data.objects]
        self.deselect_others = deselect_others
        self.original_selection: List[Any] = []
        self.original_active: Optional[Any] = None

    def __enter__(self) -> "SafeSelectionContext":
        if not BPY_AVAILABLE:
            return self
        try:
            self.original_active = ContextManagerV3.get_active_object()
            self.original_selection = ContextManagerV3.get_selected_objects()

            if self.deselect_others:
                ContextManagerV3.deselect_all_objects()

            for obj in self.objects:
                ContextManagerV3.select_object(obj, True)

            if self.objects:
                ContextManagerV3.set_active_object(self.objects[-1])
        except Exception as e:
            logger.warning(f"SafeSelectionContext warning: {e}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        if not BPY_AVAILABLE:
            return False
        try:
            ContextManagerV3.deselect_all_objects()
            for obj in self.original_selection:
                if obj and obj.name in bpy.data.objects:
                    ContextManagerV3.select_object(obj, True)
            if self.original_active and self.original_active.name in bpy.data.objects:
                ContextManagerV3.set_active_object(self.original_active)
        except Exception as e:
            logger.warning(f"SafeSelectionContext restore warning: {e}")
        return False


# =============================================================================
# AREA TYPE PRIORITIES
# =============================================================================

AREA_TYPE_PRIORITY = {
    # Primary work areas
    "VIEW_3D": 1,
    "IMAGE_EDITOR": 2,
    "NODE_EDITOR": 3,
    "SEQUENCER": 4,
    # Secondary areas
    "OUTLINER": 10,
    "PROPERTIES": 11,
    "CONSOLE": 12,
    "INFO": 13,
    "TEXT_EDITOR": 14,
    "DOPESHEET_EDITOR": 15,
    "GRAPH_EDITOR": 16,
    "NLA_EDITOR": 17,
    "CLIP_EDITOR": 18,
    "FILE_BROWSER": 19,
    "PREFERENCES": 20,
}

# Mode compatibility matrix
MODE_COMPATIBILITY = {
    "OBJECT": [
        "MESH",
        "CURVE",
        "SURFACE",
        "META",
        "FONT",
        "ARMATURE",
        "LATTICE",
        "EMPTY",
        "CAMERA",
        "LIGHT",
        "SPEAKER",
        "LIGHT_PROBE",
        "GPENCIL",
    ],
    "EDIT": ["MESH", "CURVE", "SURFACE", "META", "FONT", "ARMATURE", "LATTICE", "GPENCIL"],
    "SCULPT": ["MESH"],
    "VERTEX_PAINT": ["MESH"],
    "WEIGHT_PAINT": ["MESH"],
    "TEXTURE_PAINT": ["MESH"],
    "POSE": ["ARMATURE"],
    "PARTICLE_EDIT": ["MESH"],
    "GPENCIL_EDIT": ["GPENCIL"],
    "GPENCIL_SCULPT": ["GPENCIL"],
    "GPENCIL_WEIGHT": ["GPENCIL"],
}


# =============================================================================
# CONTEXT MANAGER V3
# =============================================================================


class ContextManagerV3:
    """
    Advanced context management for Blender MCP.

    Provides intelligent context detection, override creation,
    and safe mode transitions.
    """

    _instance = None
    _initialized = False

    def __new__(cls) -> "ContextManagerV3":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if ContextManagerV3._initialized:
            return

        self.retry_config = {
            "max_retries": 3,
            "base_delay": 0.1,
            "max_delay": 1.0,
            "exponential_base": 2.0,
        }

        self.area_cache: Dict[str, Any] = {}
        self.last_successful_context = None

        ContextManagerV3._initialized = True

    # ========================================================================
    # SAFE ACCESSORS (V2 COMPATIBILITY)
    # ========================================================================

    @staticmethod
    def is_available() -> bool:
        """Check if bpy is available."""
        return BPY_AVAILABLE

    @staticmethod
    def get_scene() -> Optional[Any]:
        """Safely get current scene."""
        if not BPY_AVAILABLE:
            return None
        try:
            return bpy.context.scene
        except:
            return None

    @staticmethod
    def get_active_object() -> Optional[Any]:
        """Safely get active object."""
        if not BPY_AVAILABLE:
            return None
        try:
            return bpy.context.active_object
        except:
            return None

    @staticmethod
    def get_view_layer() -> Optional[Any]:
        """Safely get current view layer."""
        if not BPY_AVAILABLE:
            return None
        try:
            return bpy.context.view_layer
        except:
            return None

    @staticmethod
    def get_window() -> Optional[Any]:
        """Safely get current window."""
        if not BPY_AVAILABLE:
            return None
        try:
            return bpy.context.window
        except:
            return None

    @staticmethod
    def get_screen() -> Optional[Any]:
        """Safely get current screen."""
        if not BPY_AVAILABLE:
            return None
        try:
            return bpy.context.screen
        except:
            return None

    @staticmethod
    def get_selected_objects() -> List[Any]:
        """Safely get list of selected objects."""
        if not BPY_AVAILABLE:
            return []
        try:
            return list(bpy.context.selected_objects)
        except:
            return []

    @staticmethod
    def get_mode() -> str:
        """Safely get current mode."""
        if not BPY_AVAILABLE:
            return "OBJECT"
        try:
            obj = bpy.context.active_object
            return obj.mode if obj else "OBJECT"
        except:
            return "OBJECT"

    @classmethod
    def get_object_by_name(cls, name: str) -> Optional[Any]:
        """Safely get object by name."""
        if not BPY_AVAILABLE or not name:
            return None
        try:
            return bpy.data.objects.get(name)
        except:
            return None

    @classmethod
    def set_active_object(cls, obj: Optional[Any]) -> bool:
        """Safely set active object."""
        if not BPY_AVAILABLE:
            return False
        try:
            view_layer = cls.get_view_layer()
            if view_layer:
                view_layer.objects.active = obj
                return True
            return False
        except:
            return False

    @classmethod
    def select_object(cls, obj: Any, select: bool = True) -> bool:
        """Safely select/deselect an object."""
        if not BPY_AVAILABLE or obj is None:
            return False
        try:
            if hasattr(obj, "select_set"):
                obj.select_set(select)
                return True
            return False
        except:
            return False

    @classmethod
    def deselect_all_objects(cls) -> bool:
        """Safely deselect all objects using pure Python (bypasses Blender 5.0 operator crashes)."""
        if not BPY_AVAILABLE:
            return False
        try:
            view_layer = cls.get_view_layer()
            if view_layer:
                for obj in view_layer.objects:
                    obj.select_set(False)
            return True
        except:
            return False

    @classmethod
    def validate_context(
        cls, require_scene: bool = True, require_object: bool = False
    ) -> Tuple[bool, Any]:
        """Validate that we have minimum required context."""
        if not BPY_AVAILABLE:
            return False, ErrorProtocol.NO_CONTEXT

        try:
            _ = bpy.context
        except:
            return False, ErrorProtocol.NO_CONTEXT

        if require_scene and cls.get_scene() is None:
            return False, ErrorProtocol.NO_SCENE

        if require_object and cls.get_active_object() is None:
            return False, ErrorProtocol.NO_ACTIVE_OBJECT

        return True, None

    @classmethod
    def snapshot(cls) -> ContextSnapshot:
        """Create a snapshot of current context."""
        if not BPY_AVAILABLE:
            return ContextSnapshot()
        try:
            obj = cls.get_active_object()
            return ContextSnapshot(
                scene=cls.get_scene(),
                active_object=obj,
                selected_objects=cls.get_selected_objects(),
                mode=obj.mode if obj else "OBJECT",
            )
        except:
            return ContextSnapshot()

    @classmethod
    def restore(cls, snapshot: ContextSnapshot) -> bool:
        """Restore context from a snapshot."""
        if not BPY_AVAILABLE or snapshot is None:
            return False

        success = True
        try:
            # Restore scene
            if snapshot.scene and snapshot.scene.name in bpy.data.scenes:
                if bpy.context.window:
                    bpy.context.window.scene = snapshot.scene

            # Restore selection
            cls.deselect_all_objects()
            for obj in snapshot.selected_objects:
                if obj and obj.name in bpy.data.objects:
                    cls.select_object(obj, True)

            # Restore active object
            if snapshot.active_object and snapshot.active_object.name in bpy.data.objects:
                cls.set_active_object(snapshot.active_object)

        except Exception as e:
            logger.warning(f"Context restore partial failure: {e}")
            success = False

        return success

    # ========================================================================
    # CONTEXT OVERRIDES (Blender 5.0+ MANDATORY)
    # ========================================================================

    @classmethod
    @contextmanager
    def temp_override(
        cls,
        window: Optional[Any] = None,
        screen: Optional[Any] = None,
        area: Optional[Any] = None,
        region: Optional[Any] = None,
        area_type: Optional[str] = None,
        active_object: Optional[Any] = None,
        selected_objects: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> Iterator[Any]:
        """
        Cross-version compatible context override.
        Mandatory for Blender 5.0+.

        Args:
            window: Window to override
            screen: Screen to override
            area: Area to override
            region: Region to override
            area_type: If provided, finds best area of this type automatically
            active_object: Object to set as active (via build_override)
            selected_objects: Objects to select (via build_override)
            **kwargs: Additional context members
        """
        if not BPY_AVAILABLE:
            yield None
            return

        # Prepare arguments for build_override
        overrides = kwargs.copy()
        if window:
            overrides["window"] = window
        if screen:
            overrides["screen"] = screen
        if area:
            overrides["area"] = area
        if region:
            overrides["region"] = region

        # Use robust build_override logic (handles headless, fallbacks, object context)
        ctx_dict = cls.build_override(
            area_type=area_type,
            active_object=active_object,
            selected_objects=selected_objects,
            **overrides,
        )

        # Use temp_override (Blender 3.2+)
        if hasattr(bpy.context, "temp_override"):
            try:
                with bpy.context.temp_override(**ctx_dict):
                    yield ctx_dict
            except Exception as e:
                logger.error(f"temp_override failed: {e}")
                raise
            return

        # Legacy Fallback for Blender < 3.2 (Bug 9)
        # Yields context dict to be passed manually to operators: `bpy.ops.m(ctx_dict, ...)`
        original_active = None
        try:
            if hasattr(bpy.context, "view_layer"):
                original_active = bpy.context.view_layer.objects.active
            elif hasattr(bpy.context, "scene"):
                original_active = getattr(bpy.context.scene.objects, "active", None)

            if active_object:
                cls.set_active_object(active_object)

            yield ctx_dict

        finally:
            if active_object and original_active:
                cls.set_active_object(original_active)

    # ========================================================================
    # AREA DETECTION
    # ========================================================================

    @classmethod
    def find_area(
        cls, area_type: str = "VIEW_3D", prefer_active: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Find best matching area for operations.

        Args:
            area_type: Type of area to find
            prefer_active: Prefer currently active area if it matches

        Returns:
            Dictionary with window, screen, area, region or None
        """
        if not BPY_AVAILABLE or not bpy.context:
            return None

        try:
            ctx = bpy.context

            # Check if current area matches and prefer_active
            if prefer_active and ctx.area and ctx.area.type == area_type:
                return {
                    "window": ctx.window,
                    "screen": ctx.screen,
                    "area": ctx.area,
                    "region": next((r for r in ctx.area.regions if r.type == "WINDOW"), None),
                    "scene": ctx.scene,
                    "view_layer": ctx.view_layer,
                    "workspace": ctx.workspace,
                }

            # Search all windows
            if ctx.window_manager:
                for window in ctx.window_manager.windows:
                    screen = window.screen
                    if not screen:
                        continue

                for area in screen.areas:
                    if area.type == area_type:
                        # Find WINDOW region
                        region = None
                        for r in area.regions:
                            if r.type == "WINDOW":
                                region = r
                                break

                        return {
                            "window": window,
                            "screen": screen,
                            "area": area,
                            "region": region,
                            "scene": ctx.scene,
                            "view_layer": ctx.view_layer,
                            "workspace": ctx.workspace,
                        }

            # HEADLESS FALLBACK: If no area of requested type found, return the first available one
            # but with the type overridden in the dictionary if needed (though the actual area type
            # won't change, the context members will be valid for operator execution)
            if ctx.window_manager and ctx.window_manager.windows:
                window = ctx.window_manager.windows[0]
                screen = window.screen
                if screen and screen.areas:
                    area = screen.areas[0]
                    return {
                        "window": window,
                        "screen": screen,
                        "area": area,
                        "region": next((r for r in area.regions if r.type == "WINDOW"), None),
                        "scene": ctx.scene,
                        "view_layer": ctx.view_layer,
                        "workspace": ctx.workspace,
                    }

            return None

        except Exception as e:
            logger.error(f"Error finding area {area_type}: {e}")
            return None

    @classmethod
    def find_any_area(cls) -> Optional[Dict[str, Any]]:
        """Find any available area, preferring 3D view."""
        # Try preferred areas in order
        for area_type in ["VIEW_3D", "OUTLINER", "PROPERTIES", "NODE_EDITOR"]:
            result = cls.find_area(area_type, prefer_active=True)
            if result:
                return result

        # Fallback to any area
        if BPY_AVAILABLE and bpy.context and bpy.context.window_manager:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    return {
                        "window": window,
                        "screen": window.screen,
                        "area": area,
                        "region": next((r for r in area.regions if r.type == "WINDOW"), None),
                        "scene": bpy.context.scene,
                        "view_layer": bpy.context.view_layer,
                        "workspace": bpy.context.workspace,
                    }

        return None

    @classmethod
    def get_all_areas(cls) -> List[Tuple[str, Dict[str, Any]]]:
        """Get all available areas with their types."""
        areas: List[Tuple[str, Dict[str, Any]]] = []

        if not BPY_AVAILABLE or not bpy.context:
            return areas

        if not bpy.context.window_manager:
            return areas

        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area_info = {
                    "window": window,
                    "screen": window.screen,
                    "area": area,
                    "region": next((r for r in area.regions if r.type == "WINDOW"), None),
                }
                areas.append((area.type, area_info))

        # Sort by priority
        areas.sort(key=lambda x: AREA_TYPE_PRIORITY.get(x[0], 999))
        return areas

    # ========================================================================
    # CONTEXT OVERRIDE BUILDING
    # ========================================================================

    @classmethod
    def build_override(
        cls,
        area_type: Optional[str] = None,
        active_object: Optional[Any] = None,
        selected_objects: Optional[List[Any]] = None,
        mode: Optional[str] = None,
        **additional_overrides: Any,
    ) -> Dict[str, Any]:
        """
        Build complete context override dictionary.

        Args:
            area_type: Type of area to use (e.g., 'VIEW_3D')
            active_object: Object to set as active
            selected_objects: List of objects to select
            mode: Mode to ensure (requires active_object)
            **additional_overrides: Any additional context members

        Returns:
            Dictionary suitable for bpy.context.temp_override()
        """
        if not BPY_AVAILABLE or not bpy.context:
            return {}

        ctx = bpy.context

        # Initialize override with current context defaults to ensure all fields exist
        override = {
            "window": ctx.window,
            "screen": ctx.screen,
            "area": ctx.area,
            "region": ctx.region,
            "scene": ctx.scene,
            "view_layer": ctx.view_layer,
            "workspace": ctx.workspace,
            "active_object": ctx.active_object,
            "selected_objects": list(ctx.selected_objects or []),
        }

        # DEFENSIVE FALLBACK (1.0.0): If window is None (edge case in socket/headless),
        # recover from bpy.data.window_managers. Timer callbacks should always have
        # window, but this guards against unexpected states.
        if override["window"] is None:
            try:
                wm = bpy.data.window_managers[0] if bpy.data.window_managers else None
                if wm and wm.windows:
                    fallback_window = wm.windows[0]
                    override["window"] = fallback_window
                    override["screen"] = fallback_window.screen
                    if fallback_window.screen and fallback_window.screen.areas:
                        override["area"] = fallback_window.screen.areas[0]
                        override["region"] = next(
                            (
                                r
                                for r in fallback_window.screen.areas[0].regions
                                if r.type == "WINDOW"
                            ),
                            None,
                        )
                    logger.debug("build_override: recovered window from window_managers fallback")
            except Exception as e:
                logger.warning(f"build_override: window fallback failed: {e}")

        # Override with specific area if requested or if current is missing (headless)
        target_area = area_type or (ctx.area.type if ctx.area else "VIEW_3D")
        area_info = cls.find_area(target_area, prefer_active=True)
        if area_info:
            override.update(
                {
                    "window": area_info["window"],
                    "screen": area_info["screen"],
                    "area": area_info["area"],
                    "region": area_info["region"],
                    "workspace": area_info.get("workspace", ctx.workspace),
                }
            )

            # IMPORTANT: For operators that check area.type, we must ensure the
            # area in the override actually has that type. If we're using a fallback
            # area in headless mode, we might need to temporarily change its type
            # or rely on the operator being lenient. Usually, temp_override is enough.

        # Set active object
        if active_object:
            override["active_object"] = active_object
            override["object"] = active_object
            # Ensure it's also in selected_objects
            if selected_objects is None:
                override["selected_objects"] = [active_object]

        # Set selected objects
        if selected_objects is not None:
            override["selected_objects"] = selected_objects
            override["selected_editable_objects"] = [
                obj for obj in selected_objects if obj and not obj.hide_select
            ]

        # Add any additional overrides
        override.update(additional_overrides)

        # Clean up None values that might break temp_override
        return {k: v for k, v in override.items() if v is not None}

    @classmethod
    def build_minimal_override(
        cls, active_object: Optional[Any] = None, selected_objects: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """Build minimal override for simple operations."""
        override = {}

        if active_object:
            override["active_object"] = active_object
            override["object"] = active_object

        if selected_objects is not None:
            override["selected_objects"] = selected_objects

        return override

    # ========================================================================
    # MODE MANAGEMENT
    # ========================================================================

    @classmethod
    def can_set_mode(cls, obj: Any, mode: str) -> Tuple[bool, Optional[str]]:
        """
        Check if mode can be set on object.

        Returns:
            (can_set, reason) tuple
        """
        if not obj:
            return False, "No object provided"

        if not BPY_AVAILABLE:
            return False, "bpy not available"

        obj_type = getattr(obj, "type", None)
        if not obj_type:
            return False, "Object has no type"

        compatible_types = MODE_COMPATIBILITY.get(mode, [])

        if obj_type not in compatible_types:
            return False, f"Type '{obj_type}' doesn't support mode '{mode}'"

        return True, None

    @classmethod
    def set_mode(cls, obj: Any, mode: str, retry: bool = True) -> Dict[str, Any]:
        """
        Safely set object mode with retry logic.

        Args:
            obj: Object to set mode on
            mode: Target mode
            retry: Whether to retry on failure

        Returns:
            Result dictionary with success status
        """
        if not BPY_AVAILABLE or not bpy:
            return create_error(
                ErrorProtocol.NO_CONTEXT, custom_message="Blender API not available"
            )

        if not obj:
            return create_error(
                ErrorProtocol.NO_ACTIVE_OBJECT, custom_message="No object provided for mode switch"
            )

        # Check compatibility
        can_set, reason = cls.can_set_mode(obj, mode)
        if not can_set:
            return create_error(ErrorProtocol.MODE_SWITCH_FAILED, custom_message=reason)

        # Get current mode
        current_mode = getattr(obj, "mode", "OBJECT")

        if current_mode == mode:
            return {
                "success": True,
                "mode": mode,
                "changed": False,
                "message": f"Already in {mode} mode",
            }

        # Ensure object is active
        try:
            if bpy.context.view_layer:
                if bpy.context.view_layer.objects.active != obj:
                    bpy.context.view_layer.objects.active = obj
        except Exception as e:
            logger.warning(f"Could not set active object: {e}")

        # Attempt mode switch with retry
        max_retries = 3 if retry else 1
        last_error = None

        for attempt in range(max_retries):
            try:
                # Use operator for mode switch
                SafeOperators.mode_set(mode=mode)

                return {"success": True, "mode": mode, "changed": True, "attempts": attempt + 1}
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Mode switch attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    delay = min(0.1 * (2**attempt), 0.5)
                    time.sleep(delay)

        return create_error(
            ErrorProtocol.MODE_SWITCH_FAILED,
            custom_message=f"Failed to switch to {mode} mode: {last_error}",
            details={
                "target_mode": mode,
                "current_mode": current_mode,
                "object_type": obj.type,
                "attempts": max_retries,
            },
        )

    @classmethod
    @contextmanager
    def mode_context(
        cls, obj: Any, target_mode: str, restore: bool = True
    ) -> Iterator[Optional[Any]]:
        """
        Context manager for temporary mode switch.

        Usage:
            with ContextManagerV3.mode_context(obj, 'EDIT'):
                # Do edit mode operations
                bpy.ops.mesh.subdivide()
        """
        if not obj or not BPY_AVAILABLE:
            yield None
            return

        original_mode = getattr(obj, "mode", "OBJECT")

        # Switch to target mode
        result = cls.set_mode(obj, target_mode)
        if not result.get("success"):
            yield None
            return

        try:
            yield obj
        finally:
            if restore and obj:
                try:
                    cls.set_mode(obj, original_mode, retry=False)
                except Exception as e:
                    logger.warning(f"Could not restore mode: {e}")

    # ========================================================================
    # SAFE OPERATOR EXECUTION
    # ========================================================================

    @classmethod
    def safe_execute(
        cls,
        operator: Callable[..., Any],
        *args: Any,
        area_type: Optional[str] = None,
        active_object: Optional[Any] = None,
        selected_objects: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute operator with automatic context override.

        Args:
            operator: bpy.ops operator to execute
            *args: Positional arguments for operator
            area_type: Area type for context
            active_object: Active object for context
            selected_objects: Selected objects for context
            **kwargs: Keyword arguments for operator

        Returns:
            Result dictionary
        """
        if not BPY_AVAILABLE:
            return create_error(
                ErrorProtocol.NO_CONTEXT, custom_message="Blender API not available"
            )

        # Check if operator can run
        if hasattr(operator, "poll") and not operator.poll():
            return create_error(
                ErrorProtocol.POLL_FAILED,
                custom_message=f"Operator {operator.__name__} cannot run in current context",
            )

        # Build override
        override = cls.build_override(
            area_type=area_type, active_object=active_object, selected_objects=selected_objects
        )

        try:
            with bpy.context.temp_override(**override):
                result = operator(*args, **kwargs)

                return {"success": True, "result": result, "operator": operator.__name__}

        except Exception as e:
            logger.error(f"Operator execution failed: {e}")
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Operator failed: {str(e)}"
            )

    # ========================================================================
    # EXEC_CTX - PRODUCTION CONTEXT FOR WHITELISTED OPERATORS
    # ========================================================================

    @classmethod
    @contextmanager
    def exec_ctx(
        cls,
        area_type: str = "VIEW_3D",
        active_object: Optional[Any] = None,
        selected_objects: Optional[List[Any]] = None,
        scene: Optional[Any] = None,
        ensure_object_mode: bool = False,
        **additional_overrides: Any,
    ) -> Any:
        """
        Production-grade context manager for operator execution.

        Use this for whitelisted operations that require a fully prepared
        context: export, bake, duplicate, render, sculpt.

        Features:
        - Builds complete temp_override with area/window/region
        - Optional: ensures OBJECT mode before execution
        - Logs context state for debugging

        Usage:
            with ContextManagerV3.exec_ctx(
                area_type='VIEW_3D',
                active_object=cube,
                selected_objects=[cube]
            ):
                bpy.ops.object.duplicate()
        """
        if not BPY_AVAILABLE or not bpy:
            yield None
            return

        # Optionally ensure object mode for clean operator execution
        original_mode = None
        if ensure_object_mode and active_object:
            original_mode = getattr(active_object, "mode", "OBJECT")
            if original_mode != "OBJECT":
                try:
                    if bpy.context.view_layer:
                        bpy.context.view_layer.objects.active = active_object
                    SafeOperators.mode_set(mode="OBJECT")
                except Exception as e:
                    logger.warning(f"exec_ctx: mode switch to OBJECT failed: {e}")

        # Build override with scene if provided
        extra = dict(additional_overrides)
        if scene:
            extra["scene"] = scene
            # Ensure view_layer matches scene
            if scene.view_layers:
                extra.setdefault("view_layer", scene.view_layers[0])

        override = cls.build_override(
            area_type=area_type,
            active_object=active_object,
            selected_objects=selected_objects,
            **extra,
        )

        logger.debug(
            f"exec_ctx: area_type={area_type}, "
            f"window={'YES' if override.get('window') else 'NO'}, "
            f"area={'YES' if override.get('area') else 'NO'}, "
            f"active_object={getattr(active_object, 'name', None)}"
        )

        try:
            with bpy.context.temp_override(**override) as ctx:
                yield ctx
        except Exception as e:
            logger.error(f"exec_ctx override failed: {e}")
            raise
        finally:
            # Restore original mode if we changed it
            if original_mode and original_mode != "OBJECT" and active_object:
                try:
                    SafeOperators.mode_set(mode=original_mode)
                except Exception as e:
                    logger.warning(f"exec_ctx: mode restore to {original_mode} failed: {e}")


# =============================================================================
# DECORATORS
# =============================================================================


def with_context(
    area_type: Optional[str] = None, require_active_object: bool = False, auto_select: bool = False
) -> Callable[..., Any]:
    """
    Decorator to provide context for functions.

    Usage:
        @with_context(area_type='VIEW_3D', require_active_object=True)
        def my_operation(obj_name, **kwargs):
            # Context is automatically set up
            bpy.ops.object.modifier_add(type='SUBSURF')
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not BPY_AVAILABLE:
                return create_error(
                    ErrorProtocol.NO_CONTEXT, custom_message="Blender API not available"
                )

            # Get or find active object
            active_obj = kwargs.get("active_object")

            if require_active_object and not active_obj:
                obj_name = kwargs.get("object_name")
                if obj_name:
                    active_obj = bpy.data.objects.get(obj_name)
                    if not active_obj:
                        return create_error(ErrorProtocol.OBJECT_NOT_FOUND, object_name=obj_name)
                    kwargs["active_object"] = active_obj

            # Execute with context
            with ContextManagerV3.temp_override(area_type=area_type, active_object=active_obj):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def with_mode(mode: str, restore: bool = True) -> Callable[..., Any]:
    """
    Decorator to ensure specific mode for function execution.

    Usage:
        @with_mode('EDIT')
        def edit_mesh_operations(obj_name, **kwargs):
            # Object is guaranteed to be in EDIT mode
            bpy.ops.mesh.subdivide()
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            obj = kwargs.get("active_object")

            if not obj:
                obj_name = kwargs.get("object_name")
                if obj_name:
                    obj = bpy.data.objects.get(obj_name) if BPY_AVAILABLE else None

            if not obj:
                return create_error(
                    ErrorProtocol.NO_ACTIVE_OBJECT,
                    custom_message=f"Mode '{mode}' requires an active object",
                )

            with ContextManagerV3.mode_context(obj, mode, restore=restore):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def ensure_object_mode(obj: Optional[Any] = None) -> Tuple[bool, str]:
    """Ensure object is in OBJECT mode."""
    if not BPY_AVAILABLE:
        return False, "bpy not available"

    target = obj or ContextManagerV3.get_active_object()
    if not target:
        return False, "No object"

    if target.mode == "OBJECT":
        return True, "Already in OBJECT mode"

    try:
        ContextManagerV3.set_active_object(target)
        SafeOperators.mode_set(mode="OBJECT")
        return True, "Switched to OBJECT mode"
    except Exception as e:
        return False, f"Failed: {str(e)}"


def ensure_edit_mode(obj: Optional[Any] = None) -> Tuple[bool, str]:
    """Ensure object is in EDIT mode."""
    if not BPY_AVAILABLE:
        return False, "bpy not available"

    target = obj or ContextManagerV3.get_active_object()
    if not target:
        return False, "No object"

    if target.type != "MESH":
        return False, f"Cannot edit {target.type}"

    if target.mode == "EDIT":
        return True, "Already in EDIT mode"

    try:
        ContextManagerV3.set_active_object(target)
        SafeOperators.mode_set(mode="EDIT")
        return True, "Switched to EDIT mode"
    except Exception as e:
        return False, f"Failed: {str(e)}"


def ensure_context(area_type: Optional[str] = None, active_object: Optional[Any] = None) -> bool:
    """Ensure we have a valid context."""
    if not BPY_AVAILABLE:
        return False

    if area_type:
        area_info = ContextManagerV3.find_area(area_type)
        return area_info is not None

    return bpy.context is not None


def get_safe_context() -> Optional[Dict[str, Any]]:
    """Get a safe context dictionary."""
    if not BPY_AVAILABLE:
        return None

    try:
        ctx = bpy.context
        return {
            "scene": ctx.scene,
            "view_layer": ctx.view_layer,
            "active_object": ctx.active_object,
            "selected_objects": list(ctx.selected_objects),
        }
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        return None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ContextManagerV3",
    "ContextSnapshot",
    "SafeModeContext",
    "SafeSelectionContext",
    "with_context",
    "with_mode",
    "ensure_context",
    "ensure_object_mode",
    "ensure_edit_mode",
    "get_safe_context",
    "AREA_TYPE_PRIORITY",
    "MODE_COMPATIBILITY",
]
