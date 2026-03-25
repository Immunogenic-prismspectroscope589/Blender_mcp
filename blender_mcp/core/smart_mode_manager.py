"""
Smart Mode Manager for Blender MCP 1.0.0

High Mode Philosophy: Mode switching should be automatic, safe, and invisible.

Features:
- Automatic mode detection
- Safe mode switching with validation
- Context preservation
- Mode-aware operation routing
- Automatic restoration
"""

from typing import Any, Dict, Optional, List, Callable, Tuple, Iterator
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager
import functools

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]

from .thread_safety import execute_on_main_thread, SafeOperators
from .context_manager_v3 import ContextManagerV3

from .error_protocol import ErrorProtocol, create_error
from .logging_config import get_logger

logger = get_logger()


class ModeType(Enum):
    """Blender mode types."""

    OBJECT = "OBJECT"
    EDIT = "EDIT"
    SCULPT = "SCULPT"
    VERTEX_PAINT = "VERTEX_PAINT"
    WEIGHT_PAINT = "WEIGHT_PAINT"
    TEXTURE_PAINT = "TEXTURE_PAINT"
    POSE = "POSE"
    GPENCIL_EDIT = "GPENCIL_EDIT"
    GPENCIL_SCULPT = "GPENCIL_SCULPT"
    GPENCIL_PAINT = "GPENCIL_PAINT"


@dataclass
class ModeContext:
    """Context for mode operations."""

    object_name: str
    from_mode: str
    to_mode: str
    success: bool = False
    error: Optional[str] = None
    restore_needed: bool = True


class ModeValidator:
    """
    Validates if mode operations can be performed.
    """

    # Mode compatibility matrix
    # Key: target mode, Value: list of compatible object types
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
            "GPENCIL",
            "CAMERA",
            "LIGHT",
        ],
        "EDIT": ["MESH", "CURVE", "SURFACE", "META", "FONT", "ARMATURE", "LATTICE"],
        "SCULPT": ["MESH"],
        "VERTEX_PAINT": ["MESH"],
        "WEIGHT_PAINT": ["MESH"],
        "TEXTURE_PAINT": ["MESH"],
        "POSE": ["ARMATURE"],
    }

    # Required data for each mode
    MODE_REQUIREMENTS = {
        "SCULPT": ["mesh data"],
        "VERTEX_PAINT": ["vertex colors"],
        "WEIGHT_PAINT": ["vertex groups"],
        "TEXTURE_PAINT": ["UV map", "material"],
    }

    @classmethod
    def can_enter_mode(cls, obj: Any, mode: str) -> Tuple[bool, Optional[str]]:
        """
        Check if object can enter the specified mode.

        Returns:
            (can_enter, error_message)
        """
        if not obj:
            return False, "No object provided"

        # Check object type compatibility
        obj_type = getattr(obj, "type", "UNKNOWN")
        compatible_types = cls.MODE_COMPATIBILITY.get(mode, [])

        if obj_type not in compatible_types:
            return False, f"Object type '{obj_type}' cannot enter '{mode}' mode"

        # Check mode-specific requirements
        requirements = cls.MODE_REQUIREMENTS.get(mode, [])
        if "mesh data" in requirements:
            if not obj.data:
                return False, "Object has no mesh data"

        if "vertex colors" in requirements:
            if hasattr(obj.data, "vertex_colors"):
                if not obj.data.vertex_colors:
                    # Auto-create vertex colors
                    pass  # Will be handled by mode entry

        return True, None

    @classmethod
    def validate_mode_switch(
        cls, obj: Any, from_mode: str, to_mode: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate a mode switch operation."""
        if from_mode == to_mode:
            return True, None  # Already in target mode

        return cls.can_enter_mode(obj, to_mode)


class SmartModeManager:
    """
    Intelligent mode management for Blender MCP.

    Automatically handles:
    - Mode validation
    - Safe switching
    - Context preservation
    - Error recovery
    """

    _instance: Optional["SmartModeManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "SmartModeManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._mode_stack: List[ModeContext] = []
        self._current_context: Optional[ModeContext] = None

    def get_current_mode(self, obj: Optional[Any] = None) -> str:
        """Get current mode of object or active object."""
        if obj is None:
            obj = ContextManagerV3.get_active_object()

        if not obj:
            return "OBJECT"  # Default

        return getattr(obj, "mode", "OBJECT")

    def switch_mode(self, obj: Any, target_mode: str, restore_on_exit: bool = True) -> ModeContext:
        """
        Switch object to target mode.

        Args:
            obj: Target object
            target_mode: Mode to enter
            restore_on_exit: Whether to restore original mode

        Returns:
            ModeContext with operation result
        """
        obj_name = getattr(obj, "name", "unknown")
        current_mode = self.get_current_mode(obj)

        context = ModeContext(
            object_name=obj_name,
            from_mode=current_mode,
            to_mode=target_mode,
            restore_needed=restore_on_exit,
        )

        # Validate
        can_switch, error = ModeValidator.validate_mode_switch(obj, current_mode, target_mode)

        if not can_switch:
            context.error = error
            logger.warning(f"Mode switch rejected: {error}")
            return context

        # Already in target mode
        if current_mode == target_mode:
            context.success = True
            context.restore_needed = False
            return context

        # Perform switch on main thread
        def do_switch() -> Tuple[bool, Optional[str]]:
            try:
                # Ensure object is active
                ContextManagerV3.set_active_object(obj)

                # Switch mode
                SafeOperators.mode_set(mode=target_mode)

                # Verify
                actual_mode = self.get_current_mode(obj)
                if actual_mode != target_mode:
                    raise RuntimeError(f"Mode switch failed: still in {actual_mode}")

                return True, None
            except Exception as e:
                return False, str(e)

        try:
            success, error = execute_on_main_thread(do_switch, timeout=10.0)

            if success:
                context.success = True
                if restore_on_exit:
                    self._mode_stack.append(context)
                logger.debug(f"Mode switched: {current_mode} -> {target_mode}")
            else:
                context.error = error
                logger.error(f"Mode switch failed: {error}")

        except Exception as e:
            context.error = str(e)
            logger.error(f"Mode switch exception: {e}")

        return context

    def restore_mode(self, context: Optional[ModeContext] = None) -> bool:
        """
        Restore object to previous mode.

        Args:
            context: ModeContext to restore (uses last if None)

        Returns:
            True if restored successfully
        """
        if context is None:
            if not self._mode_stack:
                return True  # Nothing to restore
            context = self._mode_stack.pop()

        if not context.restore_needed:
            return True

        # Find object
        obj = bpy.data.objects.get(context.object_name)
        if not obj:
            logger.warning(f"Cannot restore mode: object '{context.object_name}' not found")
            return False

        current_mode = self.get_current_mode(obj)

        # Already in correct mode
        if current_mode == context.from_mode:
            return True

        # Restore
        def do_restore() -> Tuple[bool, Optional[str]]:
            try:
                ContextManagerV3.set_active_object(obj)
                SafeOperators.mode_set(mode=context.from_mode)
                return True, None
            except Exception as e:
                return False, str(e)

        try:
            success, error = execute_on_main_thread(do_restore, timeout=10.0)

            if success:
                logger.debug(f"Mode restored: {current_mode} -> {context.from_mode}")
                return True
            else:
                logger.error(f"Mode restore failed: {error}")
                return False

        except Exception as e:
            logger.error(f"Mode restore exception: {e}")
            return False

    @contextmanager
    def mode_context(self, obj: Any, target_mode: str) -> Iterator[Any]:
        """
        Context manager for safe mode switching.

        Usage:
            with SmartModeManager().mode_context(obj, 'EDIT'):
                # Do edit mode operations
                pass
            # Automatically restored to previous mode
        """
        context = self.switch_mode(obj, target_mode, restore_on_exit=True)

        if not context.success:
            raise RuntimeError(f"Cannot enter {target_mode} mode: {context.error}")

        try:
            yield obj
        finally:
            self.restore_mode(context)

    def ensure_mode(
        self, obj: Any, required_mode: str, auto_switch: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Ensure object is in required mode.

        Args:
            obj: Target object
            required_mode: Required mode
            auto_switch: Whether to auto-switch if needed

        Returns:
            (is_in_mode, error_message)
        """
        current_mode = self.get_current_mode(obj)

        if current_mode == required_mode:
            return True, None

        if not auto_switch:
            return False, f"Object is in {current_mode} mode, {required_mode} required"

        context = self.switch_mode(obj, required_mode, restore_on_exit=False)

        if context.success:
            return True, None
        else:
            return False, context.error


# Decorator for mode-aware functions
def requires_mode(mode: str, object_param: str = "object_name") -> Callable:
    """
    Decorator to ensure function runs in specific mode.

    Usage:
        @requires_mode('EDIT', 'object_name')
        def edit_mesh(object_name, **params):
            # Guaranteed to be in EDIT mode
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get object
            obj: Optional[Any] = None
            obj_name = kwargs.get(object_param)
            if obj_name:
                obj = bpy.data.objects.get(obj_name)
            else:
                obj = ContextManagerV3.get_active_object()

            if not obj:
                return create_error(ErrorProtocol.NO_ACTIVE_OBJECT)

            # Ensure mode
            manager = SmartModeManager()
            success, error = manager.ensure_mode(obj, mode, auto_switch=True)

            if not success:
                return create_error(ErrorProtocol.MODE_SWITCH_FAILED, custom_message=error)

            # Execute function
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Convenience functions
def enter_mode(obj: Any, mode: str) -> Dict[str, Any]:
    """Quick mode entry."""
    manager = SmartModeManager()
    context = manager.switch_mode(obj, mode, restore_on_exit=False)

    if context.success:
        return {"success": True, "object": context.object_name, "mode": context.to_mode}
    else:
        return {"success": False, "error": context.error, "code": "MODE_SWITCH_FAILED"}


def exit_mode(obj: Any, target_mode: str = "OBJECT") -> Dict[str, Any]:
    """Quick mode exit."""
    manager = SmartModeManager()
    context = ModeContext(
        object_name=getattr(obj, "name", "unknown"),
        from_mode=manager.get_current_mode(obj),
        to_mode=target_mode,
        restore_needed=False,
    )

    manager.restore_mode(context)

    return {"success": True, "object": context.object_name, "mode": target_mode}


class SculptModeManager:
    """
    Specialized mode manager for sculpting operations.

    Handles the complex mode transition requirements for sculpting:
    - Mesh validation
    - Dyntopo state management
    - Brush context preservation
    """

    @classmethod
    def enter_sculpt_mode(cls, obj: Any) -> Dict[str, Any]:
        """
        Safely enter sculpt mode with full validation.

        Returns:
            {
                "success": bool,
                "previous_mode": str,
                "symmetry": dict,
                "error": str (if failed)
            }
        """
        if not obj:
            return {"success": False, "error": "No object provided"}

        if obj.type != "MESH":
            return {
                "success": False,
                "error": f"Object type '{obj.type}' cannot enter SCULPT mode. Only MESH allowed.",
            }

        if not obj.data:
            return {"success": False, "error": "Object has no mesh data"}

        previous_mode = getattr(obj, "mode", "OBJECT")

        # Already in sculpt mode
        if previous_mode == "SCULPT":
            return {
                "success": True,
                "previous_mode": previous_mode,
                "symmetry": cls._get_symmetry_state(),
            }

        # Perform mode switch
        def do_enter_sculpt() -> bool:
            # Ensure active
            ContextManagerV3.set_active_object(obj)

            # Switch to object mode first (if needed)
            if obj.mode != "OBJECT":
                SafeOperators.mode_set(mode="OBJECT")

            # Now enter sculpt mode
            SafeOperators.mode_set(mode="SCULPT")

            # Verify
            if obj.mode != "SCULPT":
                raise RuntimeError(f"Failed to enter SCULPT mode, currently in {obj.mode}")

            return True

        try:
            execute_on_main_thread(do_enter_sculpt, timeout=10.0)

            logger.info(f"Entered sculpt mode on '{obj.name}' (was: {previous_mode})")

            return {
                "success": True,
                "previous_mode": previous_mode,
                "symmetry": cls._get_symmetry_state(),
            }

        except Exception as e:
            logger.error(f"Failed to enter sculpt mode: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"object": obj.name, "attempted_mode": "SCULPT"},
            }

    @classmethod
    def exit_sculpt_mode(cls, obj: Any, restore_mode: str = "OBJECT") -> Dict[str, Any]:
        """
        Safely exit sculpt mode.

        Args:
            obj: Object to exit sculpt mode
            restore_mode: Mode to return to (default: OBJECT)

        Returns:
            {"success": bool, "restored_mode": str, "error": str}
        """
        if not obj:
            return {"success": False, "error": "No object provided"}

        current_mode = getattr(obj, "mode", "OBJECT")

        if current_mode != "SCULPT":
            return {
                "success": True,
                "restored_mode": current_mode,
                "note": "Object was not in sculpt mode",
            }

        def do_exit_sculpt() -> str:
            ContextManagerV3.set_active_object(obj)
            SafeOperators.mode_set(mode=restore_mode)
            return str(obj.mode)

        try:
            actual_mode = execute_on_main_thread(do_exit_sculpt, timeout=10.0)

            logger.info(f"Exited sculpt mode on '{obj.name}', now in {actual_mode}")

            return {"success": True, "restored_mode": actual_mode}

        except Exception as e:
            logger.error(f"Failed to exit sculpt mode: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def _get_symmetry_state(cls) -> Dict[str, bool]:
        """Get current symmetry settings."""
        try:
            tool_settings = getattr(bpy.context.tool_settings, "sculpt", None)
            if tool_settings:
                return {
                    "X": tool_settings.use_symmetry_x,
                    "Y": tool_settings.use_symmetry_y,
                    "Z": tool_settings.use_symmetry_z,
                }
        except:
            pass
        return {"X": True, "Y": False, "Z": False}

    @classmethod
    def ensure_sculpt_mode_for_dyntopo(cls, obj: Any) -> Dict[str, Any]:
        """
        Ensure object is in sculpt mode before dyntopo operations.

        CRITICAL: This is the fix for the "Must be in sculpt mode to toggle dyntopo" error.
        The error occurs because we check dyntopo toggle before ensuring sculpt mode.

        Returns:
            {"success": bool, "was_already_in_sculpt": bool, "error": str}
        """
        current_mode = getattr(obj, "mode", "OBJECT")

        if current_mode == "SCULPT":
            return {"success": True, "was_already_in_sculpt": True}

        # Need to enter sculpt mode first
        result = cls.enter_sculpt_mode(obj)
        result["was_already_in_sculpt"] = False
        return result


__all__ = [
    "SmartModeManager",
    "ModeValidator",
    "ModeContext",
    "ModeType",
    "SculptModeManager",
    "requires_mode",
    "enter_mode",
    "exit_mode",
]
