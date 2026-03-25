"""
Unit tests for SemanticSceneMemory — tag-based object resolution, tagging, and queries.

Uses mocked bpy — no real Blender required.
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

from blender_mcp.core.semantic_memory import (
    SemanticTag,
    ObjectMemory,
    SemanticSceneMemory,
    get_semantic_memory,
)


# ---------------------------------------------------------------------------
# SemanticTag tests
# ---------------------------------------------------------------------------


class TestSemanticTag:
    def test_default_values(self) -> None:
        tag = SemanticTag(tag="hero")
        assert tag.tag == "hero"
        assert tag.confidence == 1.0
        assert tag.source == "inferred"
        assert tag.metadata == {}

    def test_custom_values(self) -> None:
        tag = SemanticTag(tag="custom", confidence=0.5, source="user", metadata={"key": "val"})
        assert tag.confidence == 0.5
        assert tag.source == "user"
        assert tag.metadata["key"] == "val"


# ---------------------------------------------------------------------------
# ObjectMemory tests
# ---------------------------------------------------------------------------


class TestObjectMemory:
    def test_add_tag(self) -> None:
        mem = ObjectMemory(name="Cube", object_type="MESH")
        mem.add_tag("hero_character", confidence=0.9, source="ai")
        assert mem.has_tag("hero_character") is True
        assert mem.get_confidence("hero_character") == 0.9

    def test_add_tag_replaces_existing(self) -> None:
        mem = ObjectMemory(name="Cube", object_type="MESH")
        mem.add_tag("hero", confidence=0.5)
        mem.add_tag("hero", confidence=0.9)
        assert len([t for t in mem.tags if t.tag == "hero"]) == 1
        assert mem.get_confidence("hero") == 0.9

    def test_has_tag_false(self) -> None:
        mem = ObjectMemory(name="Cube", object_type="MESH")
        assert mem.has_tag("nonexistent") is False

    def test_get_confidence_missing_tag(self) -> None:
        mem = ObjectMemory(name="Cube", object_type="MESH")
        assert mem.get_confidence("missing") == 0.0


# ---------------------------------------------------------------------------
# SemanticSceneMemory tests
# ---------------------------------------------------------------------------


class TestSemanticSceneMemory:
    def _make_mock_obj(self, name: str, obj_type: str = "MESH", **kwargs) -> MagicMock:
        """Create a mock Blender object."""
        obj = MagicMock()
        obj.name = name
        obj.type = obj_type
        obj.select_get.return_value = kwargs.get("selected", False)
        if obj_type == "LIGHT":
            obj.data = MagicMock()
            obj.data.type = kwargs.get("light_type", "POINT")
        return obj

    def test_tag_object_manual(self) -> None:
        mem = SemanticSceneMemory()
        mem.tag_object("Cube", "hero", confidence=1.0, source="user")
        assert mem.get_tags("Cube") == ["hero"]

    def test_untag_object(self) -> None:
        mem = SemanticSceneMemory()
        mem.tag_object("Cube", "hero")
        mem.tag_object("Cube", "villain")
        mem.untag_object("Cube", "hero")
        assert "hero" not in mem.get_tags("Cube")
        assert "villain" in mem.get_tags("Cube")

    def test_untag_nonexistent_no_error(self) -> None:
        mem = SemanticSceneMemory()
        mem.untag_object("NonExistent", "tag")  # should not raise

    def test_get_tags_empty(self) -> None:
        mem = SemanticSceneMemory()
        assert mem.get_tags("UnknownObj") == []

    def test_get_tag_info_known(self) -> None:
        info = SemanticSceneMemory().get_tag_info("main_camera")
        assert info["auto_detected"] is True
        assert "description" in info

    def test_get_tag_info_user_defined(self) -> None:
        mem = SemanticSceneMemory()
        mem.tag_object("Cube", "my_custom_tag")
        info = mem.get_tag_info("my_custom_tag")
        assert info["auto_detected"] is False
        assert info["objects"] == ["Cube"]

    def test_list_all_tags(self) -> None:
        mem = SemanticSceneMemory()
        tags = mem.list_all_tags()
        # Should include all KNOWN_TAGS at minimum
        assert "main_camera" in tags
        assert "ground_plane" in tags
        assert "hero_character" in tags

    def test_update_access(self) -> None:
        mem = SemanticSceneMemory()
        mem.tag_object("Cube", "test")
        initial_count = mem._memory["Cube"].access_count
        mem.update_access("Cube")
        assert mem._memory["Cube"].access_count == initial_count + 1

    def test_update_access_nonexistent_no_error(self) -> None:
        mem = SemanticSceneMemory()
        mem.update_access("NonExistent")  # should not raise

    def test_set_last_created(self) -> None:
        mem = SemanticSceneMemory()
        mem.tag_object("NewObj", "something")
        mem.set_last_created("NewObj")
        assert mem._last_created == "NewObj"
        assert mem._memory["NewObj"].has_tag("last_created")

    def test_set_last_modified(self) -> None:
        mem = SemanticSceneMemory()
        mem.tag_object("ModObj", "something")
        mem.set_last_modified("ModObj")
        assert mem._last_modified == "ModObj"
        assert mem._memory["ModObj"].has_tag("last_modified")

    def test_index_tag_no_duplicates(self) -> None:
        mem = SemanticSceneMemory()
        mem._index_tag("hero", "Cube")
        mem._index_tag("hero", "Cube")
        assert mem._tag_index["hero"].count("Cube") == 1


# ---------------------------------------------------------------------------
# Resolve tests (with mocked bpy.data.objects)
# ---------------------------------------------------------------------------


class TestResolve:
    def setup_method(self) -> None:
        self.mem = SemanticSceneMemory()
        self.mem._initialized = True  # Skip actual scene scan

    def test_resolve_empty_tag_returns_none(self) -> None:
        assert self.mem.resolve("") is None

    def test_resolve_direct_name_lookup(self) -> None:
        """Direct object name should be resolved via bpy.data.objects."""
        mock_obj = MagicMock()
        mock_obj.name = "Cube"

        # MagicMock's own __contains__ overrides subclass methods, so use a plain
        # dict-wrapper class instead.
        import blender_mcp.core.semantic_memory as sm

        class FakeObjects(dict):
            """dict subclass that supports `in`, `[]`, `.get()`, and iteration."""

            pass

        original_objects = sm.bpy.data.objects
        sm.bpy.data.objects = FakeObjects({"Cube": mock_obj})

        try:
            result = self.mem.resolve("Cube")
            assert result is not None
            assert result.name == "Cube"
        finally:
            sm.bpy.data.objects = original_objects

    def test_resolve_from_tag_index(self) -> None:
        """Tags in _tag_index should resolve to the object."""
        mock_obj = MagicMock()
        mock_obj.name = "Camera"
        self.mem._tag_index["main_camera"] = ["Camera"]
        bpy_mock.data.objects.get = lambda name: mock_obj if name == "Camera" else None
        bpy_mock.data.objects.__contains__ = lambda self_dict, key: key != "main_camera"

        result = self.mem.resolve("main_camera")
        assert result is not None

    def test_resolve_last_created(self) -> None:
        mock_obj = MagicMock()
        mock_obj.name = "NewCube"
        self.mem._last_created = "NewCube"
        bpy_mock.data.objects.get = lambda name: mock_obj if name == "NewCube" else None
        bpy_mock.data.objects.__contains__ = lambda self_dict, key: False

        result = self.mem.resolve("last_created")
        assert result is not None

    def test_resolve_multiple_empty(self) -> None:
        assert self.mem.resolve_multiple("") == []


# ---------------------------------------------------------------------------
# get_semantic_memory singleton
# ---------------------------------------------------------------------------


class TestGetSemanticMemory:
    def test_returns_same_instance(self) -> None:
        import blender_mcp.core.semantic_memory as sm

        sm._semantic_memory = None  # Reset
        a = get_semantic_memory()
        b = get_semantic_memory()
        assert a is b
