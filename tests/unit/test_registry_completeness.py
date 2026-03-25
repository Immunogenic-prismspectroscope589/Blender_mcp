"""
Registry completeness tests — verifies that all expected handlers are registered
with correct metadata (priority, description, category, actions).

Uses mocked bpy — no real Blender required.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Patch bpy globally before any blender_mcp imports
bpy_mock = MagicMock()
bpy_mock.app.version = (5, 0, 0)
bpy_mock.app.translations.locale = "en_US"
sys.modules.setdefault("bpy", bpy_mock)
sys.modules.setdefault("mathutils", MagicMock())
sys.modules.setdefault("mathutils.bvhtree", MagicMock())
sys.modules.setdefault("bmesh", MagicMock())

from blender_mcp.dispatcher import HANDLER_REGISTRY, HANDLER_METADATA, load_handlers

load_handlers()

# Expected ESSENTIAL tools (priority <= 9)
_ESSENTIAL_TOOLS = [
    "execute_blender_code",
    "get_scene_graph",
    "get_viewport_screenshot_base64",
    "get_object_info",
    "manage_agent_context",
    "list_all_tools",
    "get_server_status",
    "new_scene",
]


class TestRegistryCount:
    def test_total_handler_count_is_at_least_60(self) -> None:
        assert len(HANDLER_REGISTRY) >= 60, f"Expected >= 60 handlers, got {len(HANDLER_REGISTRY)}"


class TestEssentialTier:
    def test_execute_blender_code_is_priority_1(self) -> None:
        meta = HANDLER_METADATA.get("execute_blender_code", {})
        assert meta.get("priority") == 1, (
            f"execute_blender_code priority should be 1, got {meta.get('priority')}"
        )

    def test_get_scene_graph_is_priority_2(self) -> None:
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        assert meta.get("priority") == 2, (
            f"get_scene_graph priority should be 2, got {meta.get('priority')}"
        )

    def test_all_essential_tools_present(self) -> None:
        missing = [t for t in _ESSENTIAL_TOOLS if t not in HANDLER_REGISTRY]
        assert not missing, f"Missing essential tools: {missing}"

    def test_essential_tier_count(self) -> None:
        """At least 8 handlers should have priority <= 9 (ESSENTIAL tier)."""
        essential = [
            name for name, meta in HANDLER_METADATA.items() if meta.get("priority", 100) <= 9
        ]
        assert len(essential) >= 8, (
            f"Expected >= 8 ESSENTIAL handlers, got {len(essential)}: {essential}"
        )


class TestMetadataQuality:
    def test_all_handlers_have_description(self) -> None:
        missing = [
            name
            for name, meta in HANDLER_METADATA.items()
            if not meta.get("description", "").strip()
        ]
        assert not missing, f"Handlers missing description: {missing}"

    def test_all_handlers_have_category(self) -> None:
        missing = [
            name for name, meta in HANDLER_METADATA.items() if not meta.get("category", "").strip()
        ]
        assert not missing, f"Handlers missing category: {missing}"

    def test_all_handlers_have_at_least_one_action(self) -> None:
        missing = [name for name, meta in HANDLER_METADATA.items() if not meta.get("actions")]
        assert not missing, f"Handlers with empty action list: {missing}"

    def test_no_handler_has_empty_action_list(self) -> None:
        empty = [
            name
            for name, meta in HANDLER_METADATA.items()
            if isinstance(meta.get("actions"), list) and len(meta["actions"]) == 0
        ]
        assert not empty, f"Handlers with zero actions: {empty}"


class TestSpecificHandlers:
    def test_manage_history_registered(self) -> None:
        """manage_history added in live-20."""
        assert "manage_history" in HANDLER_REGISTRY

    def test_get_local_transforms_registered(self) -> None:
        """get_local_transforms added in live-24."""
        assert "get_local_transforms" in HANDLER_REGISTRY

    def test_get_scene_graph_has_correct_name(self) -> None:
        """Must be get_scene_graph, NOT manage_scene_comprehension (renamed in live-24)."""
        assert "get_scene_graph" in HANDLER_REGISTRY
        assert "manage_scene_comprehension" not in HANDLER_REGISTRY

    def test_manage_agent_context_registered(self) -> None:
        assert "manage_agent_context" in HANDLER_REGISTRY

    def test_new_scene_registered(self) -> None:
        assert "new_scene" in HANDLER_REGISTRY
