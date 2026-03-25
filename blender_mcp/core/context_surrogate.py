"""
Context Surrogate for Blender MCP 1.0.0
"Hermetic Isolation Layer"

Ensures that AI operations run in a sanitized environment and restricts
side-effects to the "Critical 5" states:
1. Mode
2. Active Object
3. Selection
4. Frame
5. Cursor

High Mode Philosophy:
"The AI leaves no trace."
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Literal, cast

try:
    import bpy
    # import mathutils  # noqa: F401

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
    bmesh: Any = None

from .logging_config import get_logger
from .context_manager_v3 import ContextManagerV3

logger = get_logger()


@dataclass
class SurrogateSnapshot:
    """Snapshot of the 'Critical 5' state."""

    mode: str = "OBJECT"
    active_object: Optional[Any] = None
    selected_objects: List[Any] = field(default_factory=list)
    frame: int = 1
    cursor_location: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    cursor_rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Validation helper
    is_valid: bool = True


class ContextSurrogate:
    """
    Isolation layer for execution.
    Wraps operations to ensure state hygiene.
    """

    def __init__(self, use_isolation: bool = True):
        self.use_isolation = use_isolation
        self.snapshot: Optional[SurrogateSnapshot] = None
        self.invariants_held = True

    def __enter__(self) -> "ContextSurrogate":
        if not BPY_AVAILABLE or not self.use_isolation:
            return self

        try:
            self._capture_state()
        except Exception as e:
            logger.error(f"[ContextSurrogate] Capture Failed: {e}")
            # If capture fails, we cannot safely restore.
            # We mark snapshot as None to skip restoration.
            self.snapshot = None

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        if not BPY_AVAILABLE or not self.use_isolation or not self.snapshot:
            return False

        # 1. Verify Invariants before restore
        if not self._verify_invariants():
            logger.critical(
                "[ContextSurrogate] Invariant Check FAILED! Skipping restore to prevent crash."
            )
            return False

        # 2. Restore State
        try:
            self._restore_state()
        except Exception as e:
            logger.error(f"[ContextSurrogate] Restore Failed: {e}")
            # We intentionally swallow restore errors to allow the operation result
            # (or original error) to bubble up, unless it was a critical invariant failure.
        finally:
            self.snapshot = None  # Proactive cleanup

        return False

    def _capture_state(self) -> None:
        """Capture the Critical 5."""
        if not bpy.context:
            return

        ctx = bpy.context
        scene = ctx.scene

        # 1. Active & Selection
        active = ContextManagerV3.get_active_object()
        selected = ContextManagerV3.get_selected_objects()

        # 2. Mode
        mode = "OBJECT"
        if active:
            mode = active.mode

        # 3. Frame
        frame = 0
        if scene:
            frame = scene.frame_current

        # 4. Cursor
        cursor_loc = (0.0, 0.0, 0.0)
        cursor_rot = (0.0, 0.0, 0.0)
        if scene:
            cursor_loc = cast(Tuple[float, float, float], tuple(cast(Any, scene.cursor.location)))
            cursor_rot = cast(
                Tuple[float, float, float], tuple(cast(Any, scene.cursor.rotation_euler))
            )

        self.snapshot = SurrogateSnapshot(
            mode=mode,
            active_object=active,
            selected_objects=selected,
            frame=frame,
            cursor_location=cursor_loc,
            cursor_rotation=cursor_rot,
        )

    def _restore_state(self) -> None:
        """Restore the Critical 5."""
        if not self.snapshot:
            return

        snap = self.snapshot

        # 1. Restore Mode (First, to allow selection)
        # Check if active valid
        valid_active = self._resolve_object(snap.active_object)

        # Switch to Object Mode first to reset constraints?
        # SafeOperators.mode_set("OBJECT") # Brute force reset usually safer

        # 2. Restore Active
        if valid_active:
            ContextManagerV3.set_active_object(valid_active)
        else:
            # If active was deleted, clear active?
            if bpy.context.view_layer:
                bpy.context.view_layer.objects.active = None

        # 3. Restore Selection
        ContextManagerV3.deselect_all_objects()
        for obj in snap.selected_objects:
            valid_obj = self._resolve_object(obj)
            if valid_obj:
                try:
                    valid_obj.select_set(True)
                except:
                    pass

        # 4. Restore Mode (Target)
        if valid_active and snap.mode != "OBJECT":
            try:
                # Only switch if mode matches active object capabilities
                if snap.mode != valid_active.mode:
                    bpy.ops.object.mode_set(mode=snap.mode)

            except:
                pass

        # 5. Frame & Cursor
        if bpy.context.scene:
            try:
                bpy.context.scene.frame_set(snap.frame)
                bpy.context.scene.cursor.location = snap.cursor_location
                bpy.context.scene.cursor.rotation_euler = snap.cursor_rotation
            except:
                pass

    def _verify_invariants(self) -> bool:
        """
        Check context integrity.
        Returns False if context is FUBAR.
        """
        try:
            # Check 1: Context exists
            if not bpy.context:
                return False

            # Check 2: Screen/Window valid
            if not bpy.context.window or not bpy.context.screen:
                # Only if we aren't in background mode?
                # Assuming GUI mode for now as per "Area Detection" features
                if not bpy.app.background:
                    return False

            return True
        except Exception:
            return False

    def _resolve_object(self, obj: Any) -> Optional[Any]:
        """
        Safely resolve object pointer.
        Checks if it's still invalid/alive.
        """
        try:
            if obj and obj.name in bpy.data.objects:
                # Pointer might differ if undo happened
                # For now, fast name check or pointer check
                return obj
        except:
            return None
        return None
