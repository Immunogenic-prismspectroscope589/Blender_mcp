"""
Mock Integration Tests for P11 Runtime Incident Replay
Simulates Blender responses to verify test logic without a live Blender instance.

Mock responses mirror the real Blender wire format:
    {"status": "success", "result": {"status": "OK", "data": {...}}}
"""

import sys
import os
import pytest  # type: ignore[import-not-found]
from unittest.mock import MagicMock

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from tests.integration.test_incident_replay_p11 import (
    test_t002_sculpt_brush_clay_strips,
    test_t003_t004_bake_operations,
    test_t005_render_timeout_budget,
    test_t006_screenshot_policy,
    test_t008_pose_mirror_auto_resolve,
    test_t007_gltf_image_format,
    test_t009_compositor_lifecycle,
    test_t010_simulation_presets,
    test_t011_sequencer_media,
    test_t012_render_engine_normalization,
    test_t013_eevee_next_setup,
    test_t014_geonodes_deterministic_link,
)


def _ok(data: dict) -> dict:
    """Wrap data in the real Blender response envelope."""
    return {"status": "success", "result": {"status": "OK", "data": data}}


@pytest.fixture
def bridge():
    """Mock bridge that returns responses matching the real Blender wire format."""
    mock_bridge = MagicMock()

    def side_effect(command):
        tool = command.get("tool")
        params = command.get("params", {})
        action = params.get("action")

        # T002
        if tool == "manage_sculpting" and action == "SET_BRUSH":
            return _ok({"brush": "Clay Strips"})

        # T003/T004
        if tool == "manage_bake" and action == "BAKE":
            return {"status": "success", "result": {"status": "OK", "data": {}}}

        # T005
        if tool == "manage_rendering" and action == "RENDER_FRAME":
            return _ok({"render_time": 0.5})

        # T006 — uses get_viewport_screenshot_base64 tool
        if tool == "get_viewport_screenshot_base64":
            return _ok({"image_data": "base64string...", "width": 256, "height": 256})

        # T007
        if tool == "manage_export_pipeline" and action == "EXPORT_GLTF":
            return _ok({"filepath": "//test_export.glb"})

        # T008
        if tool == "manage_animation_advanced" and action == "POSE_MIRROR":
            return _ok({"rig": "TestRig", "mirrored": True})

        # T009
        if tool == "manage_compositing" and action == "ADD_NODE":
            return _ok({"node": "Blur Node", "created": True})

        # T010 — PRESET_SMOKE_FIRE (valid action)
        if tool == "manage_simulation_presets" and action == "PRESET_SMOKE_FIRE":
            return _ok({"preset": "PRESET_SMOKE_FIRE"})

        # T011 — LIST_STRIPS (valid action)
        if tool == "manage_sequencer" and action == "LIST_STRIPS":
            return _ok({"strips": []})

        # T012
        if tool == "manage_rendering" and action == "SET_ENGINE":
            return _ok({"engine": "CYCLES"})
        if tool == "manage_render_optimization" and action == "OPTIMIZE_SAMPLES":
            return _ok({"optimized_samples": 128})

        # T013 — SETUP_EEVEE_NEXT (valid action)
        if tool == "manage_eevee_next" and action == "SETUP_EEVEE_NEXT":
            return _ok({"engine": "BLENDER_EEVEE_NEXT"})

        # T014
        if tool == "manage_geometry_nodes":
            if action == "CREATE_TREE":
                return _ok({"tree": "GeoNodes"})
            if action == "ADD_NODE":
                return _ok({"node": "MathNode"})
            if action == "LINK_NODES":
                return _ok({"linked": True})

        # Default success for setup steps
        return {"status": "success", "result": {"status": "OK", "data": {}}}

    mock_bridge.send_to_blender.side_effect = side_effect
    return mock_bridge


def test_mock_t002(bridge):
    test_t002_sculpt_brush_clay_strips(bridge)


def test_mock_t003_t004(bridge):
    test_t003_t004_bake_operations(bridge)


def test_mock_t005(bridge):
    test_t005_render_timeout_budget(bridge)


def test_mock_t006(bridge):
    test_t006_screenshot_policy(bridge)


def test_mock_t007(bridge):
    test_t007_gltf_image_format(bridge)


def test_mock_t008(bridge):
    test_t008_pose_mirror_auto_resolve(bridge)


def test_mock_t009(bridge):
    test_t009_compositor_lifecycle(bridge)


def test_mock_t010(bridge):
    test_t010_simulation_presets(bridge)


def test_mock_t011(bridge):
    test_t011_sequencer_media(bridge)


def test_mock_t012(bridge):
    test_t012_render_engine_normalization(bridge)


def test_mock_t013(bridge):
    test_t013_eevee_next_setup(bridge)


def test_mock_t014(bridge):
    test_t014_geonodes_deterministic_link(bridge)
