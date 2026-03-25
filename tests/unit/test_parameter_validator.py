"""
Unit tests for ParameterValidator — type coercion, schema validation, and decorators.

No bpy required — pure Python.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

sys.modules.setdefault("bpy", MagicMock())
sys.modules.setdefault("mathutils", MagicMock())

from blender_mcp.core.parameter_validator import (
    ParameterValidator,
    ValidationResult,
    IntegrationHandlerValidator,
    validate_params_schema,
    validated_handler,
    coerce_params,
)


# ---------------------------------------------------------------------------
# ValidationResult dataclass tests
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_subscript_access(self) -> None:
        vr = ValidationResult(valid=True, sanitized={"x": 1})
        assert vr["valid"] is True
        assert vr["sanitized"] == {"x": 1}

    def test_subscript_set(self) -> None:
        vr = ValidationResult(valid=False)
        vr["valid"] = True
        assert vr.valid is True

    def test_get_with_default(self) -> None:
        vr = ValidationResult(valid=True)
        assert vr.get("nonexistent", "fallback") == "fallback"
        assert vr.get("valid") is True

    def test_contains(self) -> None:
        vr = ValidationResult(valid=True)
        assert "valid" in vr
        assert "nonexistent" not in vr

    def test_to_dict(self) -> None:
        vr = ValidationResult(valid=True, sanitized={"a": 1}, errors=[], warnings=["w1"])
        d = vr.to_dict()
        assert d["valid"] is True
        assert d["sanitized"] == {"a": 1}
        assert d["warnings"] == ["w1"]


# ---------------------------------------------------------------------------
# Type coercion tests
# ---------------------------------------------------------------------------


class TestCoerceInt:
    def test_int_from_int(self) -> None:
        assert ParameterValidator.coerce_int(5) == 5

    def test_int_from_float(self) -> None:
        assert ParameterValidator.coerce_int(3.9) == 3

    def test_int_from_string(self) -> None:
        assert ParameterValidator.coerce_int("42") == 42

    def test_int_from_float_string(self) -> None:
        assert ParameterValidator.coerce_int("3.7") == 3

    def test_int_from_bool(self) -> None:
        assert ParameterValidator.coerce_int(True) == 1
        assert ParameterValidator.coerce_int(False) == 0

    def test_int_invalid_returns_default(self) -> None:
        assert ParameterValidator.coerce_int("abc", default=99) == 99

    def test_int_none_returns_default(self) -> None:
        assert ParameterValidator.coerce_int(None, default=10) == 10

    def test_int_bounds_min(self) -> None:
        assert ParameterValidator.coerce_int(-5, min_val=0) == 0

    def test_int_bounds_max(self) -> None:
        assert ParameterValidator.coerce_int(200, max_val=100) == 100

    def test_int_bounds_both(self) -> None:
        assert ParameterValidator.coerce_int(150, min_val=0, max_val=100) == 100
        assert ParameterValidator.coerce_int(-10, min_val=0, max_val=100) == 0


class TestCoerceFloat:
    def test_float_from_int(self) -> None:
        assert ParameterValidator.coerce_float(5) == 5.0

    def test_float_from_string(self) -> None:
        assert ParameterValidator.coerce_float("3.14") == 3.14

    def test_float_invalid_returns_default(self) -> None:
        assert ParameterValidator.coerce_float("xyz", default=1.0) == 1.0

    def test_float_none_returns_default(self) -> None:
        assert ParameterValidator.coerce_float(None, default=2.5) == 2.5

    def test_float_bounds_min(self) -> None:
        assert ParameterValidator.coerce_float(-1.0, min_val=0.0) == 0.0

    def test_float_bounds_max(self) -> None:
        assert ParameterValidator.coerce_float(999.0, max_val=1.0) == 1.0


class TestCoerceBool:
    def test_bool_from_bool(self) -> None:
        assert ParameterValidator.coerce_bool(True) is True
        assert ParameterValidator.coerce_bool(False) is False

    def test_bool_from_string_true(self) -> None:
        for s in ("true", "True", "TRUE", "yes", "YES", "1", "on", "enabled"):
            assert ParameterValidator.coerce_bool(s) is True, f"Failed for {s!r}"

    def test_bool_from_string_false(self) -> None:
        for s in ("false", "False", "no", "0", "off", "disabled"):
            assert ParameterValidator.coerce_bool(s) is False, f"Failed for {s!r}"

    def test_bool_from_int(self) -> None:
        assert ParameterValidator.coerce_bool(1) is True
        assert ParameterValidator.coerce_bool(0) is False

    def test_bool_from_none_uses_default(self) -> None:
        assert ParameterValidator.coerce_bool(None, default=True) is True


class TestCoerceType:
    def test_coerce_string(self) -> None:
        assert ParameterValidator.coerce_type(42, "string") == "42"

    def test_coerce_array(self) -> None:
        assert ParameterValidator.coerce_type((1, 2, 3), "array") == [1, 2, 3]

    def test_coerce_array_none(self) -> None:
        assert ParameterValidator.coerce_type(None, "array") == []

    def test_coerce_object_none(self) -> None:
        assert ParameterValidator.coerce_type(None, "object") == {}

    def test_coerce_unknown_type_passes_through(self) -> None:
        val = [1, 2, 3]
        assert ParameterValidator.coerce_type(val, "custom") is val

    def test_coerce_unknown_type_none_uses_default(self) -> None:
        assert ParameterValidator.coerce_type(None, "custom", default="fallback") == "fallback"


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def setup_method(self) -> None:
        self.validator = ParameterValidator()
        self.schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["START", "STOP"]},
                "count": {"type": "integer", "minimum": 1, "maximum": 100},
                "scale": {"type": "number", "default": 1.0},
                "name": {"type": "string"},
                "enabled": {"type": "boolean", "default": False},
            },
            "required": ["action", "name"],
        }

    def test_valid_params(self) -> None:
        result = self.validator.validate(
            {"action": "START", "name": "test", "count": 5}, self.schema
        )
        assert result.valid is True
        assert result.sanitized["action"] == "START"
        assert result.sanitized["count"] == 5

    def test_missing_required_param(self) -> None:
        result = self.validator.validate({"action": "START"}, self.schema)
        assert result.valid is False
        assert any("name" in e for e in result.errors)

    def test_invalid_enum(self) -> None:
        result = self.validator.validate({"action": "PAUSE", "name": "test"}, self.schema)
        assert result.valid is False
        assert any("PAUSE" in e for e in result.errors)

    def test_below_minimum_clamped(self) -> None:
        """Value below minimum is clamped by coercion, so validation passes with clamped value."""
        result = self.validator.validate(
            {"action": "START", "name": "test", "count": 0}, self.schema
        )
        # ParameterValidator coerces to bounds BEFORE validation → 0 becomes 1
        assert result.valid is True
        assert result.sanitized["count"] == 1

    def test_above_maximum_clamped(self) -> None:
        """Value above maximum is clamped by coercion, so validation passes with clamped value."""
        result = self.validator.validate(
            {"action": "START", "name": "test", "count": 200}, self.schema
        )
        # ParameterValidator coerces to bounds BEFORE validation → 200 becomes 100
        assert result.valid is True
        assert result.sanitized["count"] == 100

    def test_default_values_applied(self) -> None:
        result = self.validator.validate({"action": "START", "name": "test"}, self.schema)
        assert result.valid is True
        assert result.sanitized["scale"] == 1.0
        assert result.sanitized["enabled"] is False

    def test_unknown_param_warns(self) -> None:
        result = self.validator.validate(
            {"action": "START", "name": "test", "extra_field": "val"}, self.schema
        )
        assert result.valid is True
        assert any("extra_field" in w for w in result.warnings)
        assert result.sanitized["extra_field"] == "val"

    def test_non_dict_params_fails(self) -> None:
        result = self.validator.validate("not a dict", self.schema)
        assert result.valid is False
        assert any("dictionary" in e.lower() for e in result.errors)

    def test_type_coercion_string_to_int(self) -> None:
        result = self.validator.validate(
            {"action": "START", "name": "test", "count": "5"}, self.schema
        )
        assert result.valid is True
        assert result.sanitized["count"] == 5
        assert isinstance(result.sanitized["count"], int)

    def test_type_coercion_string_to_bool(self) -> None:
        result = self.validator.validate(
            {"action": "START", "name": "test", "enabled": "true"}, self.schema
        )
        assert result.valid is True
        assert result.sanitized["enabled"] is True

    def test_none_required_param_is_error(self) -> None:
        result = self.validator.validate({"action": "START", "name": None}, self.schema)
        assert result.valid is False


# ---------------------------------------------------------------------------
# validate_action class method tests
# ---------------------------------------------------------------------------


class TestValidateAction:
    def test_valid_action(self) -> None:
        ok, err = ParameterValidator.validate_action({"action": "CREATE"}, ["CREATE", "DELETE"])
        assert ok is True
        assert err == ""

    def test_missing_action(self) -> None:
        ok, err = ParameterValidator.validate_action({}, ["CREATE"])
        assert ok is False
        assert "Missing" in err

    def test_invalid_action(self) -> None:
        ok, err = ParameterValidator.validate_action({"action": "INVALID"}, ["CREATE", "DELETE"])
        assert ok is False
        assert "INVALID" in err

    def test_non_string_action(self) -> None:
        ok, err = ParameterValidator.validate_action({"action": 42}, ["CREATE"])
        assert ok is False
        assert "string" in err.lower()


# ---------------------------------------------------------------------------
# IntegrationHandlerValidator tests
# ---------------------------------------------------------------------------


class TestIntegrationValidator:
    def test_valid_integration_params(self) -> None:
        result = IntegrationHandlerValidator.validate_integration_params(
            {"action": "COMBINE", "name": "test"}, ["COMBINE", "SEPARATE"]
        )
        assert result.valid is True

    def test_invalid_integration_action(self) -> None:
        result = IntegrationHandlerValidator.validate_integration_params(
            {"action": "UNKNOWN"}, ["COMBINE", "SEPARATE"]
        )
        assert result.valid is False

    def test_missing_action_integration(self) -> None:
        result = IntegrationHandlerValidator.validate_integration_params(
            {"name": "test"}, ["COMBINE"]
        )
        assert result.valid is False


# ---------------------------------------------------------------------------
# Legacy compatibility function
# ---------------------------------------------------------------------------


class TestLegacyValidateParamsSchema:
    def test_legacy_function_works(self) -> None:
        schema = {
            "type": "object",
            "properties": {"action": {"type": "string", "enum": ["A"]}},
            "required": ["action"],
        }
        result = validate_params_schema({"action": "A"}, schema)
        assert result.valid is True

    def test_legacy_function_returns_validation_result(self) -> None:
        result = validate_params_schema({}, {"type": "object", "properties": {}})
        assert isinstance(result, ValidationResult)


# ---------------------------------------------------------------------------
# Decorator tests
# ---------------------------------------------------------------------------


class TestValidatedHandlerDecorator:
    def test_decorator_passes_valid_action(self) -> None:
        @validated_handler(actions=["RUN", "STOP"])
        def my_handler(action=None, **params):
            return {"handled": True, "action": action}

        result = my_handler(action="RUN")
        assert result["handled"] is True

    def test_decorator_blocks_invalid_action(self) -> None:
        @validated_handler(actions=["RUN", "STOP"])
        def my_handler(action=None, **params):
            return {"handled": True}

        result = my_handler(action="INVALID")
        assert result.get("code") == "VALIDATION_ERROR"

    def test_decorator_with_schema(self) -> None:
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer", "minimum": 1}},
            "required": ["count"],
        }

        @validated_handler(schema=schema)
        def my_handler(**params):
            return {"ok": True}

        result = my_handler(count=5)
        assert result["ok"] is True

    def test_decorator_schema_missing_required(self) -> None:
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
        }

        @validated_handler(schema=schema)
        def my_handler(**params):
            return {"ok": True}

        result = my_handler()
        assert result.get("code") == "VALIDATION_ERROR"


class TestCoerceParamsDecorator:
    def test_coercion_applied(self) -> None:
        @coerce_params(count=int, scale=float)
        def my_func(count=0, scale=1.0):
            return {"count": count, "scale": scale}

        result = my_func(count="5", scale="2.5")
        assert result["count"] == 5
        assert result["scale"] == 2.5

    def test_coercion_failure_keeps_original(self) -> None:
        @coerce_params(count=int)
        def my_func(count=0):
            return {"count": count}

        result = my_func(count="not_a_number")
        # coercion fails silently, keeps original
        assert result["count"] == "not_a_number"

    def test_coercion_skips_none(self) -> None:
        @coerce_params(count=int)
        def my_func(count=None):
            return {"count": count}

        result = my_func(count=None)
        assert result["count"] is None
