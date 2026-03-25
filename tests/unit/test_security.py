"""
Unit tests for SecurityManager — validates High Mode (all actions permitted).

No bpy required — bpy is mocked.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

bpy_mock = MagicMock()
bpy_mock.app.version = (5, 0, 0)
sys.modules.setdefault("bpy", bpy_mock)
sys.modules.setdefault("mathutils", MagicMock())

from blender_mcp.core.security import SecurityManager


class TestSecurityManagerHighMode:
    def test_validate_action_always_true(self) -> None:
        """High Mode: all actions are permitted."""
        assert SecurityManager.validate_action("execute_blender_code", "EXECUTE") is True

    def test_validate_action_dangerous_tool(self) -> None:
        assert SecurityManager.validate_action("manage_scene", "DELETE_ALL") is True

    def test_validate_action_unknown_tool(self) -> None:
        assert SecurityManager.validate_action("nonexistent_tool", "ANYTHING") is True

    def test_validate_action_empty_strings(self) -> None:
        assert SecurityManager.validate_action("", "") is True

    def test_is_safe_mode_returns_bool(self) -> None:
        """is_safe_mode should return a bool regardless of mock state."""
        result = SecurityManager.is_safe_mode()
        assert isinstance(result, bool)
