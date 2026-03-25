"""
Universal Parameter Coercion System for Blender MCP 1.0.0

High Mode Philosophy: No parameter should fail due to type mismatch.
Smart conversion, fuzzy matching, automatic recovery.

Features:
- Automatic type coercion (int/float/bool/enum)
- Fuzzy enum matching
- Array/sequence normalization
- Blender 5.0+ compatibility
- Comprehensive error context
"""

from typing import Any, Dict, List, Optional, Sequence, cast
from dataclasses import dataclass, field

try:
    import bpy

    _ = bpy  # Silence F401

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False


@dataclass
class CoercionResult:
    """Result of parameter coercion."""

    success: bool
    value: Optional[Any] = None
    original_value: Optional[Any] = None
    target_type: str = ""
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class TypeCoercer:
    """
    Universal type coercion for Blender MCP parameters.

    Handles:
    - Primitive types (int, float, bool, str)
    - Enums with fuzzy matching
    - Arrays/sequences
    - Blender-specific types (vectors, colors)
    """

    # Boolean true values (case-insensitive)
    BOOL_TRUE = {"true", "yes", "on", "1", "enabled", "active"}
    BOOL_FALSE = {"false", "no", "off", "0", "disabled", "inactive"}

    @classmethod
    def coerce(
        cls,
        value: Any,
        target_type: str,
        enum_values: Optional[List[str]] = None,
        constraints: Optional[Dict] = None,
    ) -> CoercionResult:
        """
        Coerce a value to the target type.

        Args:
            value: Original value
            target_type: Target type ('int', 'float', 'bool', 'enum', 'array', etc.)
            enum_values: Valid enum values for enum type
            constraints: Additional constraints (min, max, etc.)

        Returns:
            CoercionResult with success status and coerced value
        """
        original = value
        constraints = constraints or {}

        try:
            if target_type == "bool":
                result = cls._coerce_bool(value)
            elif target_type == "int":
                result = cls._coerce_int(value, constraints)
            elif target_type == "float":
                result = cls._coerce_float(value, constraints)
            elif target_type == "enum":
                result = cls._coerce_enum(value, enum_values or [])
            elif target_type == "array":
                result = cls._coerce_array(value, constraints)
            elif target_type == "str":
                result = cls._coerce_string(value)
            elif target_type == "vector":
                result = cls._coerce_vector(value, constraints)
            elif target_type == "color":
                result = cls._coerce_color(value)
            else:
                return CoercionResult(
                    success=False,
                    original_value=original,
                    target_type=target_type,
                    error=f"Unknown target type: {target_type}",
                )

            result.original_value = original
            result.target_type = target_type
            return result

        except Exception as e:
            return CoercionResult(
                success=False,
                original_value=original,
                target_type=target_type,
                error=f"Coercion failed: {str(e)}",
            )

    @classmethod
    def _coerce_bool(cls, value: Any) -> CoercionResult:
        """Coerce to boolean."""
        if isinstance(value, bool):
            return CoercionResult(success=True, value=value)

        if isinstance(value, (int, float)):
            return CoercionResult(success=True, value=bool(value))

        if isinstance(value, str):
            lower = value.lower().strip()
            if lower in cls.BOOL_TRUE:
                return CoercionResult(success=True, value=True)
            elif lower in cls.BOOL_FALSE:
                return CoercionResult(success=True, value=False)
            else:
                # Try to interpret as number
                try:
                    return CoercionResult(success=True, value=bool(float(value)))
                except ValueError:
                    return CoercionResult(success=False, error=f"Cannot coerce '{value}' to bool")

        return CoercionResult(success=False, error=f"Cannot coerce {type(value).__name__} to bool")

    @classmethod
    def _coerce_int(cls, value: Any, constraints: Dict) -> CoercionResult:
        """Coerce to integer."""
        warnings = []

        if isinstance(value, bool):
            value = 1 if value else 0
            warnings.append("Boolean converted to int")

        if isinstance(value, str):
            # Remove common suffixes
            cleaned = value.strip().replace(",", "").replace("_", "")
            try:
                # Try int first
                value = int(cleaned)
            except ValueError:
                # Try float then truncate
                try:
                    value = float(cleaned)
                    warnings.append(f"Float '{cleaned}' truncated to int")
                except ValueError:
                    return CoercionResult(success=False, error=f"Cannot convert '{value}' to int")

        if isinstance(value, float):
            if abs(value - int(value)) > 0.001:
                warnings.append(f"Float {value} truncated to {int(value)}")
            value = int(value)

        # Apply constraints
        if "min" in constraints:
            value = max(value, constraints["min"])
        if "max" in constraints:
            value = min(value, constraints["max"])

        return CoercionResult(success=True, value=value, warnings=warnings)

    @classmethod
    def _coerce_float(cls, value: Any, constraints: Dict) -> CoercionResult:
        """Coerce to float."""
        warnings = []

        if isinstance(value, bool):
            value = 1.0 if value else 0.0
            warnings.append("Boolean converted to float")

        if isinstance(value, str):
            cleaned = value.strip().replace(",", "").replace("_", "")
            try:
                value = float(cleaned)
            except ValueError:
                return CoercionResult(success=False, error=f"Cannot convert '{value}' to float")

        value = float(value)

        # Apply constraints
        if "min" in constraints:
            value = max(value, constraints["min"])
        if "max" in constraints:
            value = min(value, constraints["max"])

        return CoercionResult(success=True, value=value, warnings=warnings)

    @classmethod
    def _coerce_enum(cls, value: Any, enum_values: List[str]) -> CoercionResult:
        """
        Coerce to enum with fuzzy matching.

        Supports:
        - Exact match
        - Case-insensitive match
        - Partial match
        - Common aliases
        """
        if not enum_values:
            return CoercionResult(success=False, error="No enum values provided")

        str_value = str(value).strip()

        # 1. Exact match
        if str_value in enum_values:
            return CoercionResult(success=True, value=str_value)

        # 2. Case-insensitive match
        lower_value = str_value.lower()
        for enum_val in enum_values:
            if enum_val.lower() == lower_value:
                return CoercionResult(
                    success=True,
                    value=enum_val,
                    warnings=[f"Case corrected: {value} -> {enum_val}"],
                )

        # 3. Partial match
        matches = []
        for enum_val in enum_values:
            if lower_value in enum_val.lower() or enum_val.lower() in lower_value:
                matches.append(enum_val)

        if len(matches) == 1:
            return CoercionResult(
                success=True, value=matches[0], warnings=[f"Fuzzy matched: {value} -> {matches[0]}"]
            )
        elif len(matches) > 1:
            return CoercionResult(
                success=False, error=f"Ambiguous value '{value}'. Did you mean: {matches}?"
            )

        # 4. No match
        return CoercionResult(
            success=False, error=f"Invalid value '{value}'. Valid options: {enum_values}"
        )

    @classmethod
    def _coerce_array(cls, value: Any, constraints: Dict) -> CoercionResult:
        """Coerce to array/sequence."""
        warnings = []

        # Handle string representation of array
        if isinstance(value, str):
            # Try to parse JSON-like array
            import json

            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # Try comma-separated
                parts = value.replace("[", "").replace("]", "").split(",")
                try:
                    value = [float(p.strip()) for p in parts if p.strip()]
                except ValueError:
                    return CoercionResult(success=False, error=f"Cannot parse array from '{value}'")

        # Ensure it's a sequence
        if not isinstance(value, (list, tuple)):
            value = [value]

        # Coerce elements
        item_type = constraints.get("item_type", "float")
        coerced = []
        for item in value:
            result = cls.coerce(item, item_type, constraints=constraints)
            if result.success:
                coerced.append(result.value)
            else:
                return CoercionResult(
                    success=False, error=f"Array item coercion failed: {result.error}"
                )

        # Validate length
        min_len = constraints.get("min_items")
        max_len = constraints.get("max_items")

        if min_len and len(coerced) < min_len:
            return CoercionResult(
                success=False, error=f"Array too short: {len(coerced)} < {min_len}"
            )
        if max_len and len(coerced) > max_len:
            coerced = coerced[:max_len]
            warnings.append(f"Array truncated to {max_len} items")

        return CoercionResult(success=True, value=coerced, warnings=warnings)

    @classmethod
    def _coerce_string(cls, value: Any) -> CoercionResult:
        """Coerce to string."""
        return CoercionResult(success=True, value=str(value))

    @classmethod
    def _coerce_vector(cls, value: Any, constraints: Dict) -> CoercionResult:
        """Coerce to 3D vector."""
        result = cls._coerce_array(value, {"item_type": "float", "min_items": 3, "max_items": 3})
        if result.success:
            return result
        return CoercionResult(success=False, error=f"Cannot coerce to vector: {result.error}")

    @classmethod
    def _coerce_color(cls, value: Any) -> CoercionResult:
        """Coerce to RGBA color."""
        result = cls._coerce_array(value, {"item_type": "float", "min_items": 3, "max_items": 4})
        if result.success:
            if not isinstance(result.value, list):
                return CoercionResult(
                    success=False,
                    error="Cannot coerce to color: internal conversion did not produce a list",
                )
            color_values = list(result.value)
            # Ensure 4 components (RGBA)
            if len(color_values) == 3:
                color_values.append(1.0)  # Add alpha
            return CoercionResult(success=True, value=color_values, warnings=result.warnings)
        return CoercionResult(success=False, error=f"Cannot coerce to color: {result.error}")


class ParameterNormalizer:
    """
    Normalizes parameters across all handlers.

    Provides:
    - Schema-based validation
    - Type coercion
    - Default value injection
    - Cross-handler consistency
    """

    # Common parameter name mappings (synonyms)
    SYNONYMS = {
        "object": ["object_name", "obj", "target", "name"],
        "location": ["loc", "position", "pos", "translate"],
        "rotation": ["rot", "rotate", "euler"],
        "scale": ["size", "sz", "sc"],
        "strength": ["power", "intensity", "amount"],
        "radius": ["size", "width", "diameter"],
        "enable": ["active", "on", "toggle", "use"],
    }

    @classmethod
    def normalize(cls, params: Dict, schema: Optional[Dict] = None) -> Dict:
        """
        Normalize parameters according to schema.

        Args:
            params: Raw parameters
            schema: JSON schema for validation

        Returns:
            Normalized parameters
        """
        normalized = {}

        # Get schema properties if available
        schema_props = schema.get("properties", {}) if schema else {}

        # Handle synonyms with schema awareness (1.0.0 Fix)
        for key, value in params.items():
            # 1. Check if key is already a valid schema property
            if key in schema_props:
                normalized[key] = value
                continue

            # 2. Try to find if this is a synonym for a schema property
            found_canonical = False
            for prop_name in schema_props:
                # Get synonyms for this schema property
                synonyms = []
                for canon, syns in cls.SYNONYMS.items():
                    if canon == prop_name:
                        synonyms = syns
                        break
                    elif prop_name in syns:
                        synonyms = [canon] + [s for s in syns if s != prop_name]
                        break

                if key.lower().strip() in [s.lower() for s in synonyms]:
                    normalized[prop_name] = value
                    found_canonical = True
                    break

            if not found_canonical:
                # 3. Fallback to default canonical name
                canonical = cls._get_canonical_name(key)
                normalized[canonical] = value

        # Apply schema constraints (coercion, defaults)
        if schema:
            normalized = cls._apply_schema(normalized, schema)

        return normalized

    @classmethod
    def _get_canonical_name(cls, name: str) -> str:
        """Get canonical parameter name from synonym."""
        name_lower = name.lower().strip()

        for canonical, synonyms in cls.SYNONYMS.items():
            if name_lower == canonical:
                return canonical
            if name_lower in [s.lower() for s in synonyms]:
                return canonical

        return name

    @classmethod
    def _apply_schema(cls, params: Dict, schema: Dict) -> Dict:
        """Apply schema constraints and defaults."""
        result = params.copy()

        properties = schema.get("properties", {})
        schema.get("required", [])

        # Apply defaults
        for prop_name, prop_schema in properties.items():
            if prop_name not in result and "default" in prop_schema:
                result[prop_name] = prop_schema["default"]

        # Coerce types
        for prop_name, prop_schema in properties.items():
            if prop_name in result:
                target_type = prop_schema.get("type", "str")

                # Map JSON schema types to coercion types
                type_map = {
                    "integer": "int",
                    "number": "float",
                    "boolean": "bool",
                    "string": "str",
                    "array": "array",
                }

                coercion_type = type_map.get(target_type, target_type)

                # Get constraints
                constraints = {}
                if "minimum" in prop_schema:
                    constraints["min"] = prop_schema["minimum"]
                if "maximum" in prop_schema:
                    constraints["max"] = prop_schema["maximum"]
                if "enum" in prop_schema:
                    constraints["enum"] = prop_schema["enum"]

                # Coerce
                coercion = TypeCoercer.coerce(
                    result[prop_name],
                    coercion_type,
                    enum_values=prop_schema.get("enum"),
                    constraints=constraints,
                )

                if coercion.success:
                    result[prop_name] = coercion.value
                else:
                    # Keep original but log warning
                    result[f"_{prop_name}_coercion_error"] = coercion.error

        return result


class BlenderTypeAdapter:
    """
    Adapts Python types to Blender-specific types.
    """

    @staticmethod
    def to_vector(value: Any, size: int = 3) -> Any:
        """Convert to Blender Vector."""
        if BPY_AVAILABLE:
            from mathutils import Vector

            result = TypeCoercer.coerce(
                value,
                "array",
                constraints={"item_type": "float", "min_items": size, "max_items": size},
            )
            if result.success:
                return Vector(cast(Sequence[float], result.value))
        return value

    @staticmethod
    def to_euler(value: Any) -> Any:
        """Convert to Blender Euler."""
        if BPY_AVAILABLE:
            from mathutils import Euler

            result = TypeCoercer.coerce(
                value, "array", constraints={"item_type": "float", "min_items": 3, "max_items": 3}
            )
            if result.success:
                return Euler(cast(Sequence[float], result.value))
        return value

    @staticmethod
    def to_color(value: Any) -> Any:
        """Convert to Blender color (RGBA tuple)."""
        result = TypeCoercer.coerce(value, "color")
        if result.success and isinstance(result.value, (list, tuple)):
            return tuple(result.value)
        return value


# Convenience functions
def coerce_parameter(value: Any, target_type: str, **kwargs: Any) -> Any:
    """Quick coerce function."""
    result = TypeCoercer.coerce(value, target_type, **kwargs)
    return result.value if result.success else value


def normalize_parameters(params: Dict, schema: Optional[Dict] = None) -> Dict:
    """Quick normalize function."""
    return ParameterNormalizer.normalize(params, schema)


__all__ = [
    "TypeCoercer",
    "ParameterNormalizer",
    "BlenderTypeAdapter",
    "CoercionResult",
    "coerce_parameter",
    "normalize_parameters",
]
