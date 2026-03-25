"""
Dispatch routing tests — verifies that the dispatcher correctly routes
actions, validates params, and returns structured responses.

Uses mocked bpy — no real Blender required.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Patch bpy globally before any blender_mcp imports
bpy_mock = MagicMock()
bpy_mock.app.version = (5, 0, 0)
bpy_mock.app.translations.locale = "en_US"
sys.modules.setdefault("bpy", bpy_mock)
sys.modules.setdefault("mathutils", MagicMock())

# Import dispatcher and load all handlers
from blender_mcp.dispatcher import (
    HANDLER_REGISTRY,
    HANDLER_METADATA,
    dispatch_command,
    load_handlers,
)

# Also mock mathutils sub-modules that handlers may import
sys.modules.setdefault("mathutils.bvhtree", MagicMock())
sys.modules.setdefault("bmesh", MagicMock())

# Load all handlers so the full registry is populated
load_handlers()


class TestHandlerRegistration:
    def test_list_all_tools_is_registered(self) -> None:
        """list_all_tools must be in the registry."""
        assert "list_all_tools" in HANDLER_REGISTRY

    def test_get_server_status_is_registered(self) -> None:
        """get_server_status must be in the registry."""
        assert "get_server_status" in HANDLER_REGISTRY

    def test_list_all_tools_is_essential_priority(self) -> None:
        """list_all_tools must have priority <= 9 (ESSENTIAL tier)."""
        meta = HANDLER_METADATA.get("list_all_tools", {})
        assert meta.get("priority", 100) <= 9, (
            f"list_all_tools priority should be <=9, got {meta.get('priority')}"
        )

    def test_get_server_status_is_essential_priority(self) -> None:
        """get_server_status must have priority <= 9 (ESSENTIAL tier)."""
        meta = HANDLER_METADATA.get("get_server_status", {})
        assert meta.get("priority", 100) <= 9

    def test_execute_blender_code_is_registered(self) -> None:
        assert "execute_blender_code" in HANDLER_REGISTRY

    def test_execute_blender_code_is_priority_1(self) -> None:
        meta = HANDLER_METADATA.get("execute_blender_code", {})
        assert meta.get("priority") == 1, (
            f"execute_blender_code priority should be 1, got {meta.get('priority')}"
        )

    def test_manage_agent_context_is_registered(self) -> None:
        assert "manage_agent_context" in HANDLER_REGISTRY


class TestDispatchRouting:
    def test_unknown_tool_returns_error(self) -> None:
        """Dispatching an unknown tool name returns UNKNOWN_TOOL error."""
        result = dispatch_command(
            {"tool": "nonexistent_tool_xyz", "params": {"action": "DO_THING"}},
            use_thread_safety=False,
        )
        assert result.get("code") == "UNKNOWN_TOOL"

    def test_missing_tool_key_returns_error(self) -> None:
        """Command dict without 'tool' key returns MISSING_TOOL error."""
        result = dispatch_command(
            {"params": {"action": "LIST"}},
            use_thread_safety=False,
        )
        assert result.get("code") == "MISSING_TOOL"

    def test_invalid_action_returns_error(self) -> None:
        """Sending an invalid action to a registered tool returns INVALID_ACTION."""
        # list_all_tools only accepts "list_all_tools" as action
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "NONEXISTENT_ACTION_999"}},
            use_thread_safety=False,
        )
        assert result.get("code") == "INVALID_ACTION"

    def test_list_all_tools_returns_manifest(self) -> None:
        """list_all_tools with correct action returns system_manifest string."""
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        )
        assert result.get("success") is True
        manifest = result.get("system_manifest", "")
        assert isinstance(manifest, str)
        assert len(manifest) > 100, "system_manifest should be a non-trivial string"


class TestManifestFormat:
    def test_manifest_contains_essential_header(self) -> None:
        """System manifest must contain the ESSENTIAL tier header."""
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        )
        manifest = result.get("system_manifest", "")
        assert "ESSENTIAL" in manifest

    def test_manifest_contains_get_server_status(self) -> None:
        """System manifest must mention get_server_status."""
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        )
        manifest = result.get("system_manifest", "")
        assert "get_server_status" in manifest


class TestSceneComprehensionActions:
    def test_get_scene_graph_registered(self) -> None:
        """get_scene_graph (renamed from manage_scene_comprehension) must be in the registry."""
        assert "get_scene_graph" in HANDLER_REGISTRY

    def test_manage_scene_comprehension_no_longer_registered(self) -> None:
        """manage_scene_comprehension is replaced by get_scene_graph (live-24)."""
        assert "manage_scene_comprehension" not in HANDLER_REGISTRY

    def test_analyze_assembly_action_listed(self) -> None:
        """ANALYZE_ASSEMBLY must be in the handler's action list."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        assert "ANALYZE_ASSEMBLY" in actions

    def test_detect_geometry_errors_action_listed(self) -> None:
        """DETECT_GEOMETRY_ERRORS must be in the handler's action list (live-22)."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        assert "DETECT_GEOMETRY_ERRORS" in actions

    def test_geometry_complexity_action_listed(self) -> None:
        """GEOMETRY_COMPLEXITY must be in the handler's action list (live-22)."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        assert "GEOMETRY_COMPLEXITY" in actions

    def test_check_production_readiness_action_listed(self) -> None:
        """CHECK_PRODUCTION_READINESS must be in the handler's action list (live-22)."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        assert "CHECK_PRODUCTION_READINESS" in actions

    def test_get_scene_graph_has_ten_actions(self) -> None:
        """get_scene_graph must have at least 10 actions after live-22."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        assert len(actions) >= 10, f"Expected >=10 actions, got {len(actions)}: {actions}"

    def test_get_scene_graph_is_essential_priority(self) -> None:
        """get_scene_graph must have priority <= 9 (ESSENTIAL tier)."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        assert meta.get("priority", 100) <= 9

    def test_get_local_transforms_registered(self) -> None:
        """get_local_transforms (new in live-24) must be in the registry."""
        assert "get_local_transforms" in HANDLER_REGISTRY
