"""
Unit tests for ErrorCode enum and create_error() factory.

No bpy required — pure Python.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

sys.modules.setdefault("bpy", MagicMock())
sys.modules.setdefault("mathutils", MagicMock())

from blender_mcp.core.error_protocol import ErrorCode, create_error


def test_errorcode_has_object_not_found() -> None:
    assert ErrorCode.OBJECT_NOT_FOUND.value == "OBJECT_NOT_FOUND"


def test_errorcode_has_execution_error() -> None:
    assert ErrorCode.EXECUTION_ERROR.value == "EXECUTION_ERROR"


def test_errorcode_has_validation_error() -> None:
    assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"


def test_errorcode_has_poll_failed() -> None:
    assert ErrorCode.POLL_FAILED.value == "POLL_FAILED"


def test_create_error_with_enum() -> None:
    result = create_error(ErrorCode.OBJECT_NOT_FOUND)
    assert result["code"] == "OBJECT_NOT_FOUND"


def test_create_error_with_string() -> None:
    result = create_error("MY_CUSTOM_CODE")
    assert result["code"] == "MY_CUSTOM_CODE"


def test_create_error_message_override() -> None:
    result = create_error(ErrorCode.EXECUTION_ERROR, message="custom message")
    assert result["message"] == "custom message"


def test_create_error_custom_message_alias() -> None:
    result = create_error(ErrorCode.EXECUTION_ERROR, custom_message="alias message")
    assert result["message"] == "alias message"


def test_create_error_kwargs_merged() -> None:
    result = create_error(ErrorCode.VALIDATION_ERROR, message="bad", field="name")
    assert result["field"] == "name"


def test_create_error_details_kwarg() -> None:
    result = create_error(ErrorCode.EXECUTION_ERROR, message="err", details={"key": "val"})
    assert result["details"] == {"key": "val"}


def test_create_error_returns_dict() -> None:
    result = create_error("ANY_CODE")
    assert isinstance(result, dict)
    assert "code" in result
    assert "message" in result


def test_create_error_no_message_uses_enum_name() -> None:
    """When no message is provided, enum name (or value) is used as fallback."""
    result = create_error(ErrorCode.OBJECT_NOT_FOUND)
    # The fallback uses .name or .value — either is acceptable
    assert result["message"]  # non-empty
