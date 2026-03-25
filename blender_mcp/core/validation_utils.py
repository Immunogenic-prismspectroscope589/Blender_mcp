from enum import Enum
from typing import Any, Dict, Optional, Type, Union

from .error_protocol import ErrorProtocol, create_error

ValidationErrorDict = Dict[str, Any]


class ValidationUtils:
    """
    Centralized validation logic and schema generation.
    Enforces SSOT by generating schemas directly from Enums.
    """

    @staticmethod
    def generate_enum_schema(enum_class: Type[Enum], description: str = "") -> Dict[str, Any]:
        """Generate JSON schema for an Enum."""
        return {
            "type": "string",
            "enum": [e.value for e in enum_class],
            "description": description or f"One of {[e.value for e in enum_class]}",
        }

    @staticmethod
    def validate_enum(
        value: Any, enum_class: Type[Enum], field_name: str
    ) -> Optional[ValidationErrorDict]:
        """Validate that a value exists in an Enum."""
        allowed_values = [e.value for e in enum_class]
        if value not in allowed_values:
            return create_error(
                ErrorProtocol.INVALID_PARAMETER_VALUE,
                custom_message=(
                    f"Invalid value for '{field_name}': {value}. Expected one of: {allowed_values}"
                ),
                details={"value": value, "allowed_values": allowed_values},
                field=field_name,
            )
        return None

    @staticmethod
    def validate_range(
        value: Union[int, float],
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        field_name: str = "value",
    ) -> Optional[ValidationErrorDict]:
        """Validate numeric range."""
        if min_val is not None and value < min_val:
            return create_error(
                ErrorProtocol.INVALID_PARAMETER_VALUE,
                custom_message=(f"Value for '{field_name}' must be >= {min_val}. Got: {value}"),
                field=field_name,
            )
        if max_val is not None and value > max_val:
            return create_error(
                ErrorProtocol.INVALID_PARAMETER_VALUE,
                custom_message=(f"Value for '{field_name}' must be <= {max_val}. Got: {value}"),
                field=field_name,
            )
        return None

    @staticmethod
    def validate_type(
        value: Any, expected_type: Type[Any], field_name: str
    ) -> Optional[ValidationErrorDict]:
        """Strict type validation."""
        if not isinstance(value, expected_type):
            return create_error(
                ErrorProtocol.INVALID_PARAMETER_TYPE,
                custom_message=(
                    f"Invalid type for '{field_name}'. Expected "
                    f"{expected_type.__name__}, got {type(value).__name__}"
                ),
                field=field_name,
                expected_type=expected_type.__name__,
                actual_type=type(value).__name__,
            )
        return None

    @staticmethod
    def coerce_int(
        value: Any,
        default: int,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
    ) -> int:
        """Safe integer coercion with bounds."""
        try:
            result = int(float(value))  # Handle string floats like "1.0"
            if min_val is not None:
                result = max(result, min_val)
            if max_val is not None:
                result = min(result, max_val)
            return result
        except (ValueError, TypeError):
            return default

    @staticmethod
    def parse_vector(
        value: Any, default: tuple[float, float, float] = (0.0, 0.0, 0.0), is_scale: bool = False
    ) -> tuple[float, float, float]:
        """Safely parse array or float into a 3D vector tuple."""
        if value is None:
            return default
        try:
            if isinstance(value, (list, tuple)):
                if len(value) >= 3:
                    return (float(value[0]), float(value[1]), float(value[2]))
                elif len(value) == 2:
                    z_val = 1.0 if is_scale else 0.0
                    return (float(value[0]), float(value[1]), z_val)
                elif len(value) == 1:
                    return (float(value[0]), float(value[0]), float(value[0]))
            elif isinstance(value, (int, float, str)):
                val = float(value)
                return (val, val, val)
        except (ValueError, TypeError):
            pass
        return default
