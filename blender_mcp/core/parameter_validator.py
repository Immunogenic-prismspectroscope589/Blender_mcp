"""
Parameter Validator for Blender MCP 1.0.0

Provides schema-based parameter validation with automatic type coercion.
Prevents "missing required parameter" errors and type mismatches.
"""

import functools
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of parameter validation."""

    valid: bool
    sanitized: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        """Make subscriptable for backward compatibility."""
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow setting via subscript."""
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like get method."""
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        """Allow 'in' operator."""
        return hasattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "sanitized": self.sanitized,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ParameterValidator:
    """
    Schema-based parameter validation with automatic type coercion.

    Usage:
        validator = ParameterValidator()
        result = validator.validate(params, {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "minimum": 1},
                "name": {"type": "string"}
            },
            "required": ["name"]
        })
    """

    # Type coercion functions
    TYPE_COERCERS: Dict[str, Callable[..., Any]] = {
        "integer": lambda v, d=0, **kw: ParameterValidator.coerce_int(v, d, **kw),
        "number": lambda v, d=0.0, **kw: ParameterValidator.coerce_float(v, d, **kw),
        "float": lambda v, d=0.0, **kw: ParameterValidator.coerce_float(v, d, **kw),
        "boolean": lambda v, d=False, **kw: ParameterValidator.coerce_bool(v, d),
        "string": lambda v, d="", **kw: str(v) if v is not None else d,
        "array": lambda v, d=None, **kw: list(v) if v is not None else (d or []),
        "object": lambda v, d=None, **kw: dict(v) if v is not None else (d or {}),
    }

    @classmethod
    def coerce_int(
        cls,
        value: Any,
        default: int = 0,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
    ) -> int:
        """
        Coerce value to integer with bounds checking.

        Args:
            value: Value to coerce
            default: Default if coercion fails
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Coerced integer
        """
        try:
            if isinstance(value, str):
                # Handle string numbers including floats
                result = int(float(value))
            elif isinstance(value, (int, float)):
                result = int(value)
            elif isinstance(value, bool):
                result = 1 if value else 0
            else:
                result = default
        except (TypeError, ValueError, OverflowError):
            result = default

        # Bounds checking
        if min_val is not None:
            result = max(min_val, result)
        if max_val is not None:
            result = min(max_val, result)

        return result

    @classmethod
    def coerce_float(
        cls,
        value: Any,
        default: float = 0.0,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> float:
        """
        Coerce value to float with bounds checking.

        Args:
            value: Value to coerce
            default: Default if coercion fails
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Coerced float
        """
        try:
            if isinstance(value, str):
                result = float(value)
            elif isinstance(value, (int, float)):
                result = float(value)
            else:
                result = default
        except (TypeError, ValueError, OverflowError):
            result = default

        # Bounds checking
        if min_val is not None:
            result = max(min_val, result)
        if max_val is not None:
            result = min(max_val, result)

        return result

    @classmethod
    def coerce_bool(cls, value: Any, default: bool = False) -> bool:
        """
        Coerce value to boolean.

        Args:
            value: Value to coerce
            default: Default if coercion fails

        Returns:
            Coerced boolean
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on", "enabled")
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    @classmethod
    def coerce_type(
        cls, value: Any, target_type: Optional[str], default: Optional[Any] = None, **kwargs: Any
    ) -> Any:
        """
        Coerce value to target type.

        Args:
            value: Value to coerce
            target_type: Target type name
            default: Default if coercion fails
            **kwargs: Additional coercion parameters (min_val, max_val, etc.)

        Returns:
            Coerced value
        """
        if target_type in cls.TYPE_COERCERS:
            return cls.TYPE_COERCERS[target_type](value, default, **kwargs)
        return value if value is not None else default

    def validate(self, params: Any, schema: Dict[str, Any]) -> ValidationResult:
        """
        Validate parameters against schema.

        Args:
            params: Parameters to validate
            schema: JSON Schema-like validation schema

        Returns:
            ValidationResult with valid flag, sanitized values, and errors
        """
        sanitized = {}
        errors = []
        warnings = []

        if not isinstance(params, dict):
            errors.append("Parameters must be a dictionary")
            return ValidationResult(valid=False, errors=errors)

        properties: Dict[str, Any] = schema.get("properties", {})
        required = schema.get("required", [])

        # Check required parameters
        for req_param in required:
            if req_param not in params or params[req_param] is None:
                errors.append(f"Missing required parameter: '{req_param}'")

        # Validate and coerce each parameter
        for name, value in params.items():
            if name not in properties:
                # Unknown parameter - allow but warn
                warnings.append(f"Unknown parameter: '{name}'")
                sanitized[name] = value
                continue

            prop_schema = properties[name]
            prop_type = prop_schema.get("type")

            # Type coercion
            if prop_type and value is not None:
                coerced = self._coerce_value(value, prop_schema)
                sanitized[name] = coerced

                # Validate enum
                if "enum" in prop_schema:
                    if coerced not in prop_schema["enum"]:
                        errors.append(
                            f"Invalid value for '{name}': '{coerced}'. "
                            f"Must be one of: {prop_schema['enum']}"
                        )

                # Validate range for numbers
                if prop_type in ("integer", "number", "float"):
                    if "minimum" in prop_schema and coerced < prop_schema["minimum"]:
                        errors.append(
                            f"Value for '{name}' ({coerced}) is below minimum ({prop_schema['minimum']})"
                        )
                    if "maximum" in prop_schema and coerced > prop_schema["maximum"]:
                        errors.append(
                            f"Value for '{name}' ({coerced}) is above maximum ({prop_schema['maximum']})"
                        )
            else:
                sanitized[name] = value

        # Add missing optional parameters with defaults
        for name, prop_schema in properties.items():
            if name not in sanitized and "default" in prop_schema:
                sanitized[name] = prop_schema["default"]

        valid = len(errors) == 0

        return ValidationResult(valid=valid, sanitized=sanitized, errors=errors, warnings=warnings)

    def _coerce_value(self, value: Any, prop_schema: Dict[str, Any]) -> Any:
        """Coerce single value based on property schema."""
        prop_type = prop_schema.get("type")
        default = prop_schema.get("default")

        # Get bounds if specified
        kwargs: Dict[str, Any] = {}
        if "minimum" in prop_schema:
            kwargs["min_val"] = prop_schema["minimum"]
        if "maximum" in prop_schema:
            kwargs["max_val"] = prop_schema["maximum"]

        return self.coerce_type(value, prop_type, default, **kwargs)

    @classmethod
    def validate_action(cls, params: Dict[str, Any], valid_actions: List[str]) -> Tuple[bool, str]:
        """
        Validate 'action' parameter for integration handlers.

        Args:
            params: Parameters dictionary
            valid_actions: List of valid action values

        Returns:
            Tuple of (is_valid, error_message)
        """
        action = params.get("action")

        if action is None:
            return False, "Missing required parameter: 'action'"

        if not isinstance(action, str):
            return False, f"Parameter 'action' must be a string, got {type(action).__name__}"

        if action not in valid_actions:
            return False, f"Invalid action: '{action}'. Must be one of: {valid_actions}"

        return True, ""


class IntegrationHandlerValidator(ParameterValidator):
    """
    Specialized validator for integration handlers requiring 'action' parameter.

    Usage:
        @validated_handler(actions=["COMBINE", "SEPARATE"])
        def manage_integrations(action, **params):
            ...
    """

    @classmethod
    def validate_integration_params(
        cls, params: Dict[str, Any], actions: List[str]
    ) -> ValidationResult:
        """
        Validate integration handler parameters.

        Args:
            params: Parameters dictionary
            actions: Valid action values

        Returns:
            ValidationResult
        """
        validator = cls()

        # First validate action parameter
        is_valid, error_msg = cls.validate_action(params, actions)

        if not is_valid:
            return ValidationResult(valid=False, errors=[error_msg])

        # Basic schema for integration handlers
        schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": actions},
                "object_name": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["action"],
        }

        return validator.validate(params, schema)


# =============================================================================
# DECORATORS
# =============================================================================


def validated_handler(
    schema: Optional[Dict[str, Any]] = None, actions: Optional[List[str]] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for handler functions with automatic parameter validation.

    Usage:
        @register_handler("manage_physics", schema={...})
        @validated_handler(actions=["RIGID_BODY_ADD", "CLOTH_SIM_SETUP"])
        def manage_physics(action, **params):
            ...

        Or with custom schema:
        @validated_handler(schema={
            "properties": {"count": {"type": "integer", "minimum": 1}},
            "required": ["count"]
        })
        def my_handler(**params):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract params from args/kwargs
            params = kwargs.copy()

            # If first arg is action and there are more args
            if args:
                # Assume first positional arg is action for handler pattern
                params["action"] = args[0]
                # Add remaining args as positional params if any
                if len(args) > 1:
                    params["__args__"] = args[1:]

            # Validate action if actions list provided
            if actions is not None:
                validator = ParameterValidator()
                is_valid, error_msg = validator.validate_action(params, actions)

                if not is_valid:
                    return {"error": error_msg, "code": "VALIDATION_ERROR"}

            # Validate against schema if provided
            if schema is not None:
                validator = ParameterValidator()
                result = validator.validate(params, schema)

                if not result.valid:
                    return {
                        "error": "Validation failed: " + "; ".join(result.errors),
                        "code": "VALIDATION_ERROR",
                        "details": result.errors,
                    }

                # Use sanitized parameters
                params = result.sanitized

            # Call the actual function
            return func(*args, **kwargs)

        # Store validation info on function
        setattr(wrapper, "_validation_schema", schema)
        setattr(wrapper, "_validation_actions", actions)

        return wrapper

    return decorator


def coerce_params(
    **coercions: Callable[[Any], Any],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to coerce specific parameters.

    Usage:
        @coerce_params(count=int, scale=float, enabled=bool)
        def my_handler(count=10, scale=1.0, enabled=True):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Coerce kwargs
            for key, coercer in coercions.items():
                if key in kwargs and kwargs[key] is not None:
                    try:
                        kwargs[key] = coercer(kwargs[key])
                    except (TypeError, ValueError):
                        pass  # Keep original if coercion fails

            return func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================


def validate_params_schema(params: Dict[str, Any], schema: Dict[str, Any]) -> ValidationResult:
    """
    Legacy compatibility function for schema validation.

    Args:
        params: Parameters to validate
        schema: JSON Schema-like validation schema

    Returns:
        ValidationResult
    """
    validator = ParameterValidator()
    return validator.validate(params, schema)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ValidationResult",
    "ParameterValidator",
    "IntegrationHandlerValidator",
    "validated_handler",
    "coerce_params",
    "validate_params_schema",
]
