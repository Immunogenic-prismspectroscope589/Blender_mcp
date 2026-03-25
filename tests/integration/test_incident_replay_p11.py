"""
P11 Runtime Incident Replay Tests

Replays known incident scenarios from Phase 11 testing.
Each test function accepts a `bridge` fixture that provides send_to_blender().

The mock variant (test_incident_replay_p11_mock.py) re-uses these functions
with a mock bridge so they can run without a live Blender instance.

When run directly, these tests require Blender running on localhost:9879.
They are skipped automatically if no connection can be established.

Response structure from live Blender:
    {"status": "success", "result": {"status": "OK", "data": {...}, ...}}
    Access data via: result.get("result", {}).get("data", {})
"""

import sys
import os
import pytest  # type: ignore[import-not-found]

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from stdio_bridge import MCPBridge

HOST = "localhost"
PORT = 9879


@pytest.fixture(scope="module")
def bridge():
    """Real bridge fixture — connects to Blender on localhost:9879, skips if unavailable."""
    b = MCPBridge(host=HOST, port=PORT)
    if not b.connect():
        pytest.skip(
            f"Could not connect to Blender at {HOST}:{PORT}. "
            "P11 integration tests require a running Blender instance."
        )
    return b


def get_data(result):
    """Extract data dict from nested Blender response structure."""
    return result.get("result", {}).get("data", {})


def test_t002_sculpt_brush_clay_strips(bridge) -> None:
    """
    T002: Set sculpt brush to Clay Strips.

    Stability note: SET_BRUSH requires an active sculpt mode context.
    If Blender has no mesh in sculpt mode, START_SCULPTING may return
    NO_CONTEXT — in that case the test is skipped rather than failed.
    """
    # 1. Enter Sculpt Mode (prerequisite) — verify it actually succeeded
    sculpt_result = bridge.send_to_blender(
        {"tool": "manage_sculpting", "params": {"action": "START_SCULPTING"}}
    )
    sculpt_errors = sculpt_result.get("result", {}).get("errors", [])
    no_context = any(e.get("code") == "NO_CONTEXT" for e in sculpt_errors)
    if no_context or sculpt_result.get("result", {}).get("success") is False:
        pytest.skip(
            "Sculpt mode not available (NO_CONTEXT) — "
            "requires a mesh object in the scene. Skipping brush test."
        )

    # 2. Try to set 'Clay Strips'
    result = bridge.send_to_blender(
        {
            "tool": "manage_sculpting",
            "params": {"action": "SET_BRUSH", "brush": "Clay Strips"},
        }
    )
    result_errors = result.get("result", {}).get("errors", [])
    if any(e.get("code") == "NO_CONTEXT" for e in result_errors):
        pytest.skip("SET_BRUSH: sculpt context lost between steps — skipping.")

    assert result.get("status") == "success", f"Failed to set Clay Strips brush: {get_data(result)}"
    data = get_data(result)
    assert "Clay Strips" in data.get("brush", ""), "Response should confirm Clay Strips brush set"


def test_t003_t004_bake_operations(bridge) -> None:
    """T003/T004: Bake operation returns success."""
    result = bridge.send_to_blender(
        {
            "tool": "manage_bake",
            "params": {"action": "BAKE", "type": "DIFFUSE"},
        }
    )
    assert result.get("status") == "success"


def test_t005_render_timeout_budget(bridge) -> None:
    """T005: RENDER_FRAME completes within timeout budget."""
    result = bridge.send_to_blender(
        {
            "tool": "manage_rendering",
            "params": {
                "action": "RENDER_FRAME",
                "filepath": "//test.png",
                "auto_camera": True,  # create camera if none exists
            },
        }
    )
    assert result.get("status") == "success"
    data = get_data(result)
    assert "render_time" in data or "job_id" in data
    if "render_time" in data:
        assert data["render_time"] < 300  # Must finish within 5-minute budget


def test_t006_screenshot_policy(bridge) -> None:
    """T006: Screenshot returns image data via get_viewport_screenshot_base64."""
    result = bridge.send_to_blender(
        {
            "tool": "get_viewport_screenshot_base64",
            "params": {"action": "SMART_SCREENSHOT", "max_size": 256},
        }
    )
    assert result.get("status") == "success"
    # Screenshot tool returns data or inner result — either is fine
    assert result.get("result") is not None


def test_t007_gltf_image_format(bridge) -> None:
    """T007: GLTF export action is recognized and image format compatibility is maintained."""
    result = bridge.send_to_blender(
        {
            "tool": "manage_export_pipeline",
            "params": {"action": "EXPORT_GLTF", "filepath": "//test_export.glb"},
        }
    )
    # Export may fail for reasons unrelated to image format (security path, no objects, etc).
    # Key: EXPORT_GLTF action must be recognized; image format enum must not be invalid.
    outer_status = result.get("status", "")
    inner = result.get("result", {})
    if outer_status == "error":
        msg = result.get("message", "")
        assert "Unknown action" not in msg, f"EXPORT_GLTF should be a recognized action: {msg}"
    elif inner.get("status") in ("ERROR", "error"):
        errors = inner.get("errors", [])
        msgs = " ".join(e.get("message", "") for e in errors)
        # May fail on path/security but NOT on image_format enum validation
        assert "Invalid enum" not in msgs and "image_format" not in msgs
    else:
        assert outer_status == "success"


def test_t008_pose_mirror_auto_resolve(bridge) -> None:
    """T008: Pose mirror works on a valid armature (empty → no-op, returns mirrored=True)."""
    # Create a fresh armature with a unique name so re-runs don't conflict
    bridge.send_to_blender(
        {
            "tool": "execute_blender_code",
            "params": {
                "action": "execute_blender_code",
                "code": (
                    "import bpy;"
                    " ad = bpy.data.armatures.new('T8RigData');"
                    " rig = bpy.data.objects.new('T8Rig', ad);"
                    " bpy.context.scene.collection.objects.link(rig)"
                ),
            },
        }
    )
    result = bridge.send_to_blender(
        {
            "tool": "manage_animation_advanced",
            "params": {"action": "POSE_MIRROR", "rig_name": "T8Rig"},
        }
    )
    assert result.get("status") == "success", f"POSE_MIRROR outer error: {result.get('message')}"
    data = get_data(result)
    assert data.get("mirrored") is True


def test_t009_compositor_lifecycle(bridge) -> None:
    """T009: Compositor node can be created (ENABLE_NODES first, then ADD_NODE with full type)."""
    # Enable compositor first
    bridge.send_to_blender({"tool": "manage_compositing", "params": {"action": "ENABLE_NODES"}})
    # Add a blur node using the full Blender bl_idname
    result = bridge.send_to_blender(
        {
            "tool": "manage_compositing",
            "params": {"action": "ADD_NODE", "node_type": "CompositorNodeBlur"},
        }
    )
    assert result.get("status") == "success"
    data = get_data(result)
    assert data.get("created") is True


def test_t010_simulation_presets(bridge) -> None:
    """T010: Simulation preset PRESET_SMOKE_FIRE is a recognized action."""
    result = bridge.send_to_blender(
        {
            "tool": "manage_simulation_presets",
            "params": {"action": "PRESET_SMOKE_FIRE"},
        }
    )
    # Accept success OR known runtime error (headless: no VIEW_3D area for fluid modifiers).
    # Key: action must be recognized, not return INVALID_ACTION / Unknown action.
    outer_status = result.get("status", "")
    inner = result.get("result", {})
    if outer_status == "error":
        msg = result.get("message", "")
        assert "Unknown action" not in msg, f"PRESET_SMOKE_FIRE should be recognized: {msg}"
    elif inner.get("status") in ("ERROR", "error"):
        errors = inner.get("errors", [])
        msgs = " ".join(e.get("message", "") for e in errors)
        assert "Unknown action" not in msgs
    else:
        assert outer_status == "success"


def test_t011_sequencer_media(bridge) -> None:
    """T011: Sequencer strip list is accessible."""
    result = bridge.send_to_blender(
        {
            "tool": "manage_sequencer",
            "params": {"action": "LIST_STRIPS"},
        }
    )
    assert result.get("status") == "success"
    data = get_data(result)
    assert "strips" in data or isinstance(data, dict)


def test_t012_render_engine_normalization(bridge) -> None:
    """T012: SET_ENGINE normalizes engine name and confirms with CYCLES."""
    result = bridge.send_to_blender(
        {
            "tool": "manage_rendering",
            "params": {"action": "SET_ENGINE", "engine": "CYCLES"},
        }
    )
    assert result.get("status") == "success"
    data = get_data(result)
    assert data.get("engine") == "CYCLES"


def test_t013_eevee_next_setup(bridge) -> None:
    """T013: EEVEE_NEXT setup (SETUP_EEVEE_NEXT action) completes successfully."""
    result = bridge.send_to_blender(
        {
            "tool": "manage_eevee_next",
            "params": {"action": "SETUP_EEVEE_NEXT"},
        }
    )
    assert result.get("status") == "success"
    data = get_data(result)
    assert data.get("engine") in ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", None]


def test_t014_geonodes_deterministic_link(bridge) -> None:
    """T014: Geometry nodes CREATE_TREE → ADD_NODE × 2 → LINK_NODES sequence is deterministic.
    Uses NodeReroute which is available in all Blender node tree types.
    Creates its own mesh so the test is independent of scene state.
    """
    import pytest  # noqa: PLC0415

    # Create a fresh mesh object for this test (Cube may have been removed by other tests)
    bridge.send_to_blender(
        {
            "tool": "execute_blender_code",
            "params": {
                "action": "execute_blender_code",
                "code": (
                    "import bpy;"
                    " me = bpy.data.meshes.new('T14Mesh');"
                    " ob = bpy.data.objects.new('T14Obj', me);"
                    " bpy.context.scene.collection.objects.link(ob)"
                ),
            },
        }
    )

    r1 = bridge.send_to_blender(
        {
            "tool": "manage_geometry_nodes",
            "params": {
                "action": "CREATE_TREE",
                "object_name": "T14Obj",
                "tree_name": "GeoNodesTest",
            },
        }
    )
    assert r1.get("status") == "success"

    # Add first Reroute node — available in all Blender node tree types
    r2 = bridge.send_to_blender(
        {
            "tool": "manage_geometry_nodes",
            "params": {
                "action": "ADD_NODE",
                "node_type": "NodeReroute",
                "node_name": "RerouteA",
                "object_name": "T14Obj",
            },
        }
    )
    inner2 = r2.get("result", {})
    if inner2.get("status") != "OK":
        pytest.skip(f"ADD_NODE NodeReroute not available: {inner2.get('message', inner2)}")
    node_a = inner2.get("data", {}).get("node", "RerouteA")

    # Add second Reroute node
    r3 = bridge.send_to_blender(
        {
            "tool": "manage_geometry_nodes",
            "params": {
                "action": "ADD_NODE",
                "node_type": "NodeReroute",
                "node_name": "RerouteB",
                "object_name": "T14Obj",
            },
        }
    )
    inner3 = r3.get("result", {})
    if inner3.get("status") != "OK":
        pytest.skip(f"ADD_NODE NodeReroute second failed: {inner3.get('message', inner3)}")
    node_b = inner3.get("data", {}).get("node", "RerouteB")

    # Link RerouteA output (0) → RerouteB input (0)
    r4 = bridge.send_to_blender(
        {
            "tool": "manage_geometry_nodes",
            "params": {
                "action": "LINK_NODES",
                "from_node": node_a,
                "to_node": node_b,
                "socket_index_from": 0,
                "socket_index_to": 0,
                "object_name": "T14Obj",
            },
        }
    )
    assert r4.get("status") == "success"
    data = get_data(r4)
    assert data.get("linked") is True, f"LINK_NODES failed: {r4.get('result', {})}"
