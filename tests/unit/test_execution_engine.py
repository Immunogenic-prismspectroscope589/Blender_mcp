"""
Unit tests for ExecutionEngine — policy enforcement, operator safety checks,
and ExecutionResult dataclass.

No bpy required — bpy is mocked.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

bpy_mock = MagicMock()
bpy_mock.app.version = (5, 0, 0)
sys.modules.setdefault("bpy", bpy_mock)
sys.modules.setdefault("mathutils", MagicMock())

from blender_mcp.core.execution_engine import (
    ExecutionResult,
    ExecutionEngine,
    ExecutionPolicy,
    ExecutionMode,
    DiffLevel,
    SafeOps,
    safe_execute,
    require_context,
    safe_mode_set,
)


# ---------------------------------------------------------------------------
# ExecutionResult tests
# ---------------------------------------------------------------------------


class TestExecutionResult:
    def test_success_to_dict(self) -> None:
        r = ExecutionResult(success=True, result={"count": 5})
        d = r.to_dict()
        assert d["success"] is True
        assert d["result"]["count"] == 5
        assert "error" not in d

    def test_error_to_dict(self) -> None:
        r = ExecutionResult(
            success=False,
            error="boom",
            error_code="TEST_ERR",
            alternatives=["try A", "try B"],
        )
        d = r.to_dict()
        assert d["success"] is False
        assert d["error"] == "boom"
        assert d["code"] == "TEST_ERR"
        assert d["alternatives"] == ["try A", "try B"]

    def test_error_to_dict_no_code(self) -> None:
        r = ExecutionResult(success=False, error="fail")
        d = r.to_dict()
        assert d["code"] == "EXECUTION_ERROR"

    def test_error_to_dict_no_alternatives(self) -> None:
        r = ExecutionResult(success=False, error="fail", error_code="E")
        d = r.to_dict()
        assert "alternatives" not in d

    def test_to_error_dict_alias(self) -> None:
        r = ExecutionResult(success=False, error="err")
        assert r.to_error_dict() == r.to_dict()


# ---------------------------------------------------------------------------
# ExecutionPolicy tests
# ---------------------------------------------------------------------------


class TestExecutionPolicy:
    def teardown_method(self) -> None:
        # Reset singleton to default after each test
        ExecutionPolicy._instance = None

    def test_default_mode_is_read_write(self) -> None:
        policy = ExecutionPolicy.get()
        assert policy.mode == ExecutionMode.READ_WRITE

    def test_default_diff_level_is_transform(self) -> None:
        policy = ExecutionPolicy.get()
        assert policy.diff_level == DiffLevel.TRANSFORM

    def test_set_mode(self) -> None:
        ExecutionPolicy.set_mode(ExecutionMode.READ_ONLY)
        assert ExecutionPolicy.get().mode == ExecutionMode.READ_ONLY

    def test_set_diff_level(self) -> None:
        ExecutionPolicy.set_diff_level(DiffLevel.FULL)
        assert ExecutionPolicy.get().diff_level == DiffLevel.FULL

    def test_singleton_pattern(self) -> None:
        a = ExecutionPolicy.get()
        b = ExecutionPolicy.get()
        assert a is b


# ---------------------------------------------------------------------------
# ExecutionEngine operator safety tests
# ---------------------------------------------------------------------------


class TestOperatorSafety:
    def test_dangerous_operator_blocked(self) -> None:
        result = ExecutionEngine.execute("mesh.loopcut_slide")
        assert result.success is False
        assert result.error_code == "MODAL_OPERATOR_BLOCKED"

    def test_dangerous_operator_with_alternatives(self) -> None:
        result = ExecutionEngine.execute("mesh.loopcut_slide")
        assert result.alternatives is not None
        assert len(result.alternatives) > 0

    def test_dangerous_allowed_when_flag_set(self) -> None:
        """allow_dangerous=True bypasses the dangerous check."""
        # Will fail at operator lookup since it's mocked, but should NOT be
        # blocked at the dangerous check stage
        result = ExecutionEngine.execute("mesh.loopcut_slide", allow_dangerous=True)
        # Should fail for a different reason (operator lookup or poll), not MODAL_OPERATOR_BLOCKED
        assert result.error_code != "MODAL_OPERATOR_BLOCKED"

    def test_ui_dependent_operator_blocked(self) -> None:
        result = ExecutionEngine.execute("outliner.collection_new")
        assert result.success is False
        assert result.error_code == "MODAL_OPERATOR_BLOCKED"

    def test_scene_destructive_blocked(self) -> None:
        result = ExecutionEngine.execute("wm.quit_blender")
        assert result.success is False
        assert result.error_code == "MODAL_OPERATOR_BLOCKED"


class TestOperatorSafetyCheck:
    def test_safe_operator(self) -> None:
        is_safe, reason = ExecutionEngine.is_safe("mesh.primitive_cube_add")
        assert is_safe is True
        assert reason is None

    def test_modal_operator_unsafe(self) -> None:
        is_safe, reason = ExecutionEngine.is_safe("mesh.loopcut_slide")
        assert is_safe is False
        assert "Modal" in reason or "UI" in reason

    def test_ui_dependent_unsafe(self) -> None:
        is_safe, reason = ExecutionEngine.is_safe("outliner.collection_new")
        assert is_safe is False

    def test_scene_destructive_unsafe(self) -> None:
        is_safe, reason = ExecutionEngine.is_safe("wm.quit_blender")
        assert is_safe is False
        assert "crash" in reason.lower()


class TestReadOnlyPolicy:
    def teardown_method(self) -> None:
        ExecutionPolicy._instance = None

    def test_mutation_blocked_in_read_only(self) -> None:
        ExecutionPolicy.set_mode(ExecutionMode.READ_ONLY)
        result = ExecutionEngine.execute("mesh.primitive_cube_add")
        assert result.success is False
        assert result.error_code == "POLICY_VIOLATION_READ_ONLY"

    def test_non_mutation_allowed_in_read_only(self) -> None:
        """Operators not in MUTATION_OPERATORS should pass policy check."""
        ExecutionPolicy.set_mode(ExecutionMode.READ_ONLY)
        # "object.mode_set" is not in MUTATION_OPERATORS
        result = ExecutionEngine.execute("object.mode_set", params={"mode": "EDIT"})
        # May fail for other reasons (mock), but should NOT be POLICY_VIOLATION_READ_ONLY
        assert result.error_code != "POLICY_VIOLATION_READ_ONLY"


# ---------------------------------------------------------------------------
# _get_operator tests
# ---------------------------------------------------------------------------


class TestGetOperator:
    def test_invalid_path_format(self) -> None:
        assert ExecutionEngine._get_operator("invalid_no_dot") is None

    def test_three_parts_invalid(self) -> None:
        assert ExecutionEngine._get_operator("a.b.c") is None


# ---------------------------------------------------------------------------
# ExecutionEngine.execute_batch tests
# ---------------------------------------------------------------------------


class TestExecuteBatch:
    def test_batch_stops_on_error(self) -> None:
        """With stop_on_error=True, batch stops at first failure."""
        operations = [
            ("mesh.loopcut_slide", {}),  # blocked
            ("mesh.primitive_cube_add", {}),  # should never run
        ]
        results = ExecutionEngine.execute_batch(operations, stop_on_error=True)
        assert len(results) == 1
        assert results[0].success is False

    def test_batch_continues_on_error(self) -> None:
        """With stop_on_error=False, batch processes all operations."""
        operations = [
            ("mesh.loopcut_slide", {}),  # blocked
            ("wm.quit_blender", {}),  # also blocked
        ]
        results = ExecutionEngine.execute_batch(operations, stop_on_error=False)
        assert len(results) == 2
        assert all(not r.success for r in results)


# ---------------------------------------------------------------------------
# safe_execute decorator tests
# ---------------------------------------------------------------------------


class TestSafeExecuteDecorator:
    def test_catches_exception(self) -> None:
        @safe_execute()
        def failing_func():
            raise ValueError("test error")

        result = failing_func()
        assert result["success"] is False
        assert "test error" in result["error"]
        assert result["error_type"] == "ValueError"

    def test_passes_through_on_success(self) -> None:
        @safe_execute()
        def ok_func():
            return {"data": 42}

        result = ok_func()
        assert result["data"] == 42

    def test_custom_fallback_result(self) -> None:
        @safe_execute(fallback_result={"fallback": True})
        def failing_func():
            raise RuntimeError("crash")

        result = failing_func()
        assert result["fallback"] is True
        assert result["success"] is False


# ---------------------------------------------------------------------------
# SafeOps proxy tests
# ---------------------------------------------------------------------------


class TestSafeOps:
    def test_proxy_returns_execution_result(self) -> None:
        """SafeOps.category.method() should return an ExecutionResult."""
        safe = SafeOps()
        # This will try to execute "mesh.loopcut_slide" which is blocked
        result = safe.mesh.loopcut_slide()
        assert isinstance(result, ExecutionResult)
        assert result.success is False

    def test_proxy_singleton(self) -> None:
        a = SafeOps()
        b = SafeOps()
        assert a is b
