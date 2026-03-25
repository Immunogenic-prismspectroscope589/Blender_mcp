"""
Unit tests for ResponseBuilder and ResponseTimer.

No bpy required — pure Python logic tests.
"""

from __future__ import annotations

import sys
import os
import time
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

sys.modules.setdefault("bpy", MagicMock())
sys.modules.setdefault("mathutils", MagicMock())

from blender_mcp.core.response_builder import ResponseBuilder, ResponseTimer


# ---------------------------------------------------------------------------
# success() tests
# ---------------------------------------------------------------------------


def test_success_returns_ok_status() -> None:
    result = ResponseBuilder.success("manage_test", "DO_THING")
    assert result["status"] == "OK"
    assert result["success"] is True


def test_success_has_all_required_keys() -> None:
    result = ResponseBuilder.success("manage_test", "DO_THING")
    for key in (
        "status",
        "success",
        "summary",
        "data",
        "metadata",
        "warnings",
        "errors",
        "undo_info",
        "next_steps",
    ):
        assert key in result, f"Missing key: {key}"


def test_success_metadata_fields() -> None:
    result = ResponseBuilder.success("manage_test", "DO_THING")
    meta = result["metadata"]
    for key in ("handler", "action", "version", "timestamp"):
        assert key in meta, f"Missing metadata key: {key}"
    assert meta["handler"] == "manage_test"
    assert meta["action"] == "DO_THING"
    assert meta["version"] == "1.0.0"


def test_success_data_passthrough() -> None:
    result = ResponseBuilder.success("h", "A", data={"x": 1, "y": 2})
    assert result["data"]["x"] == 1
    assert result["data"]["y"] == 2


def test_success_summary_uses_data_summary_key() -> None:
    result = ResponseBuilder.success("h", "A", data={"summary": "My custom summary"})
    assert result["summary"] == "My custom summary"


def test_success_summary_count_key() -> None:
    result = ResponseBuilder.success("h", "A", data={"count": 5})
    assert "5" in result["summary"]


def test_success_state_diff_changes_summary() -> None:
    result = ResponseBuilder.success(
        "h", "A", state_diff={"added": ["ObjA", "ObjB"], "removed": ["ObjC"]}
    )
    assert "2 added" in result["summary"]
    assert "1 deleted" in result["summary"]


def test_success_errors_list_is_empty() -> None:
    result = ResponseBuilder.success("h", "A")
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# error() tests
# ---------------------------------------------------------------------------


def test_error_returns_error_status() -> None:
    result = ResponseBuilder.error("h", "A", "OBJECT_NOT_FOUND", "not found")
    assert result["status"] == "ERROR"
    assert result["success"] is False


def test_error_has_errors_list() -> None:
    result = ResponseBuilder.error("h", "A", "OBJECT_NOT_FOUND", "not found")
    errors = result["errors"]
    assert len(errors) >= 1
    entry = errors[0]
    for key in ("code", "message", "recoverable", "suggestion"):
        assert key in entry, f"Missing error entry key: {key}"


def test_error_auto_suggestion_object_not_found() -> None:
    result = ResponseBuilder.error("h", "A", "OBJECT_NOT_FOUND", "missing")
    suggestion = result["errors"][0]["suggestion"]
    assert "GET_OBJECTS_FLAT" in suggestion


def test_error_next_steps_auto_populated() -> None:
    result = ResponseBuilder.error("h", "A", "OBJECT_NOT_FOUND", "missing")
    assert len(result["next_steps"]) > 0


def test_error_from_dict_input() -> None:
    """from_error() parses dict with 'code' and 'error' keys."""
    err_dict = {"code": "MY_CODE", "error": "something went wrong", "suggestion": "try again"}
    result = ResponseBuilder.from_error(err_dict, handler="h", action="A")
    assert result["status"] == "ERROR"
    errors = result["errors"]
    assert errors[0]["code"] == "MY_CODE"
    assert "something went wrong" in errors[0]["message"]


def test_error_from_exception_input() -> None:
    """from_error() uses type name as code for plain exceptions."""
    exc = ValueError("test exception")
    result = ResponseBuilder.from_error(exc, handler="h", action="A")
    assert result["status"] == "ERROR"
    assert result["errors"][0]["code"] == "VALUEERROR"


# ---------------------------------------------------------------------------
# partial() tests
# ---------------------------------------------------------------------------


def test_partial_returns_partial_status() -> None:
    result = ResponseBuilder.partial(
        "h",
        "A",
        data={"x": 1},
        completed_steps=["step1"],
        failed_steps=[{"name": "step2", "error": "oops"}],
    )
    assert result["status"] == "PARTIAL"
    assert result["success"] is True
    assert "completed_steps" in result


# ---------------------------------------------------------------------------
# warning() tests
# ---------------------------------------------------------------------------


def test_warning_returns_warning_status() -> None:
    result = ResponseBuilder.warning(
        "h",
        "A",
        data={"x": 1},
        warnings=[{"code": "W1", "message": "be careful", "severity": "low"}],
    )
    assert result["status"] == "WARNING"
    assert result["success"] is True


# ---------------------------------------------------------------------------
# mutation helper tests
# ---------------------------------------------------------------------------


def test_add_affected_object_appends() -> None:
    result = ResponseBuilder.success("h", "A")
    ResponseBuilder.add_affected_object(result, "Cube", "MESH", ["location"])
    assert len(result["affected_objects"]) == 1
    assert result["affected_objects"][0]["name"] == "Cube"


def test_add_warning_appends() -> None:
    result = ResponseBuilder.success("h", "A")
    ResponseBuilder.add_warning(result, "W1", "watch out", severity="low")
    # Filter out any psutil memory warnings that may have been added
    user_warnings = [w for w in result["warnings"] if w.get("code") == "W1"]
    assert len(user_warnings) == 1
    assert user_warnings[0]["message"] == "watch out"


# ---------------------------------------------------------------------------
# ResponseTimer tests
# ---------------------------------------------------------------------------


def test_response_timer_measures_duration() -> None:
    with ResponseTimer() as t:
        time.sleep(0.02)
    assert t.duration_ms >= 5.0, f"Expected >= 5ms, got {t.duration_ms:.2f}ms"


def test_response_timer_get_duration_returns_float() -> None:
    with ResponseTimer() as t:
        pass
    assert isinstance(t.get_duration(), float)
