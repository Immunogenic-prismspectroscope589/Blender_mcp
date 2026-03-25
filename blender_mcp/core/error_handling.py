"""
Advanced Error Handling and Tolerance System for Blender MCP
Provides robust error recovery, type coercion, and API compatibility layers
"""

import functools
import traceback
from typing import Any, Callable, Dict, Optional, TypeVar, Literal

import bpy

T = TypeVar("T")


class BlenderAPIError(Exception):
    """Base exception for Blender API errors with recovery hints"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        recovery_hint: Optional[str] = None,
        alternative_actions: Optional[list] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.recovery_hint = recovery_hint
        self.alternative_actions = alternative_actions or []


class APICompatibilityError(BlenderAPIError):
    """Raised when API compatibility issues are detected"""

    pass


class TypeCoercionError(BlenderAPIError):
    """Raised when type coercion fails"""

    pass


class ErrorRecovery:
    """Provides error recovery strategies"""

    @staticmethod
    def coerce_value(value: Any, target_type: type, default: Optional[Any] = None) -> Any:
        """Safely coerce a value to target type with fallback"""
        if value is None:
            return default

        try:
            if target_type is int:
                return int(float(value)) if isinstance(value, str) else int(value)
            elif target_type is float:
                return float(value)
            elif target_type is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes", "on")
                return bool(value)
            elif target_type is set:
                if isinstance(value, dict):
                    return set(value.keys())
                elif isinstance(value, (list, tuple)):
                    return set(value)
                return {value}
            elif target_type is list:
                return list(value) if not isinstance(value, str) else [value]
            else:
                return target_type(value)
        except (ValueError, TypeError) as e:
            if default is not None:
                return default
            raise TypeCoercionError(
                f"Cannot coerce {type(value).__name__} to {target_type.__name__}: {e}",
                error_code="TYPE_COERCION_FAILED",
                recovery_hint=f"Provide a valid {target_type.__name__} value",
            )

    @staticmethod
    def safe_get_attr(
        obj: Any, attr: str, default: Optional[Any] = None, alternatives: Optional[list] = None
    ) -> Any:
        """Safely get attribute with alternatives"""
        alternatives = alternatives or []
        for name in [attr] + alternatives:
            if hasattr(obj, name):
                return getattr(obj, name)
        return default

    @staticmethod
    def with_fallback(fallback_value: T, exceptions: tuple = (Exception,)) -> Callable:
        """Decorator to provide fallback value on exception"""

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> T:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    print(f"[MCP] Fallback triggered for {func.__name__}: {e}")
                    return fallback_value

            return wrapper

        return decorator


class APICompatibilityLayer:
    """Handles API differences between Blender versions"""

    # High Mode: Coerce to tuple (handles MagicMock in tests)
    try:
        _raw_version = getattr(getattr(bpy, "app", None), "version", (5, 0, 0))
        if _raw_version and len(_raw_version) >= 3:
            BLENDER_VERSION = tuple(int(v) for v in _raw_version[:3])
        else:
            BLENDER_VERSION = (5, 0, 0)
    except (TypeError, ValueError, IndexError):
        BLENDER_VERSION = (5, 0, 0)

    @classmethod
    def get_attr_name(cls, base_name: str, version_map: Optional[Dict[tuple, str]] = None) -> str:
        """Get version-specific attribute name"""
        version_map = version_map or {}
        try:
            for (major, minor), name in sorted(version_map.items(), reverse=True):
                if cls.BLENDER_VERSION >= (major, minor, 0):
                    return name
        except TypeError:
            # MagicMock fallback - return base name
            pass
        return base_name

    @classmethod
    def check_enum_value(cls, enum_type: str, value: str, fallback: Optional[str] = None) -> str:
        """Check if enum value is valid, return fallback if not"""
        # Enum kontrolü için bpy.types üzerinden erişim
        try:
            enum_items = getattr(bpy.types, enum_type, None)
            if enum_items and hasattr(enum_items, "__members__"):
                valid_values = [e.name for e in enum_items]
                if value in valid_values:
                    return value
        except:
            pass
        return fallback or value


def robust_execute(
    func: Callable,
    *args: Any,
    error_context: str = "",
    coerce_types: Optional[Dict[str, type]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute function with robust error handling and type coercion

    Args:
        func: Function to execute
        error_context: Context string for error messages
        coerce_types: Dict of {param_name: target_type} for type coercion

    Returns:
        Dict with 'success', 'result', and 'error' keys
    """
    try:
        # Type coercion
        if coerce_types:
            for param, target_type in coerce_types.items():
                if param in kwargs:
                    kwargs[param] = ErrorRecovery.coerce_value(
                        kwargs[param], target_type, kwargs.get(param)
                    )

        result = func(*args, **kwargs)
        return {"success": True, "result": result, "error": None}

    except BlenderAPIError as e:
        return {
            "success": False,
            "result": None,
            "error": {
                "message": str(e),
                "code": e.error_code,
                "recovery_hint": e.recovery_hint,
                "alternatives": e.alternative_actions,
            },
        }
    except Exception as e:
        tb = traceback.format_exc()
        return {
            "success": False,
            "result": None,
            "error": {
                "message": f"{error_context}: {str(e)}",
                "code": "EXECUTION_ERROR",
                "traceback": tb if bpy.app.debug else None,
                "recovery_hint": "Check parameters and try again",
            },
        }


def validate_params(schema: Dict[str, Dict], params: Dict) -> Dict[str, Any]:
    """
    Validate and sanitize parameters against schema

    Schema format:
    {
        "param_name": {
            "type": int|float|str|bool|list|set,
            "required": bool,
            "default": value,
            "min": value,
            "max": value,
            "enum": [valid_values]
        }
    }
    """
    errors = []
    sanitized = {}

    for name, spec in schema.items():
        value = params.get(name)

        # Required check
        if spec.get("required") and value is None:
            errors.append(f"Missing required parameter: {name}")
            continue

        # Default value
        if value is None and "default" in spec:
            value = spec["default"]

        if value is None:
            continue

        # Type coercion
        target_type = spec.get("type")
        if target_type:
            try:
                value = ErrorRecovery.coerce_value(value, target_type)
            except TypeCoercionError as e:
                errors.append(f"Parameter '{name}': {e}")
                continue

        # Range check
        if "min" in spec and value < spec["min"]:
            errors.append(f"Parameter '{name}' below minimum {spec['min']}")
            continue
        if "max" in spec and value > spec["max"]:
            errors.append(f"Parameter '{name}' above maximum {spec['max']}")
            continue

        # Enum check
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"Parameter '{name}' must be one of: {spec['enum']}")
            continue

        sanitized[name] = value

    if errors:
        return {"valid": False, "errors": errors, "sanitized": None}

    return {"valid": True, "errors": [], "sanitized": sanitized}


class ExecutionContext:
    """Context manager for safe execution with state preservation"""

    def __init__(self, mode: str = "OBJECT", area_type: str = "VIEW_3D") -> None:
        self.target_mode = mode
        self.area_type = area_type
        self.original_mode: Optional[str] = None
        self.original_area: Optional[str] = None
        self.obj: Optional[Any] = None

    def __enter__(self) -> "ExecutionContext":
        if bpy.context.object:
            self.obj = bpy.context.object
            # Explicit check for mypy
            if self.obj:
                self.original_mode = self.obj.mode
                if self.obj.mode != self.target_mode:
                    try:
                        bpy.ops.object.mode_set(mode=self.target_mode)
                    except Exception as e:
                        print(f"[MCP] Mode switch warning: {e}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        if self.obj and self.original_mode and self.obj.mode != self.original_mode:
            try:
                bpy.ops.object.mode_set(mode=self.original_mode)
            except Exception as e:
                print(f"[MCP] Mode restore warning: {e}")
        return False  # Don't suppress exceptions
