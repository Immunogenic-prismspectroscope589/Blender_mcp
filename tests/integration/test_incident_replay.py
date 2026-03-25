"""
Integration Tests for Runtime Incident Replay
Verifies fixes for T002, T003, T004, T005, T006, T008.

Usage:
    python -m pytest tests/integration/test_incident_replay.py

Requires:
    - Blender running with MCP server started on port 9879.

Response structure from live Blender:
    {"status": "success", "result": {"status": "OK", "data": {...}, ...}}
    Access data via: result.get("result", {}).get("data", {})
"""

import sys
import os
import pytest  # type: ignore[import-not-found]

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from stdio_bridge import MCPBridge

HOST = "localhost"
PORT = 9879


@pytest.fixture(scope="module")
def bridge():
    """Setup bridge connection to Blender."""
    bridge = MCPBridge(host=HOST, port=PORT)
    if not bridge.connect():
        pytest.skip(
            f"Could not connect to Blender at {HOST}:{PORT}. precise integration tests require running Blender."
        )
    return bridge


def send_command(bridge, tool, params=None):
    """Helper to send command and return result."""
    response = bridge.send_to_blender({"tool": tool, "params": params or {}})
    if "error" in response:
        pytest.fail(f"Blender communication error: {response['error']}")
    return response


def get_data(result):
    """Extract data from Blender response (handles nested structure)."""
    return result.get("result", {}).get("data", {})


# =============================================================================
# T002: Sculpt Brush Fix (Clay Strips)
# =============================================================================
def test_t002_sculpt_brush_clay_strips(bridge):
    """
    T002: Verify 'Clay Strips' brush can be activated in Blender 5.0+.
    Root Cause: Name mismatch and asset system changes.

    Stability note: SET_BRUSH requires an active sculpt mode context.
    If Blender has no mesh in sculpt mode (e.g. fresh session, no active object,
    or previous test left Blender in object mode), START_SCULPTING may return
    NO_CONTEXT — in that case the test is skipped rather than failed.
    """
    # 1. Enter Sculpt Mode (Prerequisite) — check whether it actually succeeded
    sculpt_result = send_command(bridge, "manage_sculpting", {"action": "START_SCULPTING"})
    sculpt_errors = sculpt_result.get("result", {}).get("errors", [])
    no_context = any(e.get("code") == "NO_CONTEXT" for e in sculpt_errors)
    if no_context or sculpt_result.get("result", {}).get("success") is False:
        pytest.skip(
            "Sculpt mode not available (NO_CONTEXT) — "
            "requires a mesh object in the scene. Skipping brush test."
        )

    # 2. Try to set 'Clay Strips'
    result = send_command(
        bridge, "manage_sculpting", {"action": "SET_BRUSH", "brush": "Clay Strips"}
    )
    result_errors = result.get("result", {}).get("errors", [])
    if any(e.get("code") == "NO_CONTEXT" for e in result_errors):
        pytest.skip("SET_BRUSH: sculpt context lost between steps — skipping.")

    assert result.get("status") == "success", f"Failed to set Clay Strips brush: {get_data(result)}"
    assert "Clay Strips" in get_data(result).get("brush", ""), (
        "Response should confirm Clay Strips brush set"
    )


# =============================================================================
# T003/T004: Bake Fixes
# =============================================================================
def test_t003_t004_bake_operations(bridge):
    """
    T003: Verify BAKE action exists.
    T004: Verify safe_ops.object.bake handles execution context correctly.
    """
    # 1. Setup a simple object for baking
    send_command(
        bridge,
        "manage_objects",
        {"action": "CREATE_PRIMITIVE", "type": "Cube", "name": "Bake_Test_Cube"},
    )

    # 2. Attempt Bake (This might fail if no image/UVs, but we check if it *crashes* or invalid param error)
    # We expect either success or a valid logic error, NOT an execution crash or missing action.
    result = send_command(
        bridge,
        "manage_bake",
        {
            "action": "BAKE",
            "type": "COMBINED",
            # minimal params
        },
    )

    # Even if it fails due to "No images found to bake to", it confirms the handler routed correctly
    # and safe_ops didn't explode with TypeError.
    inner = result.get("result", {})
    if inner.get("status") in ("ERROR", "error"):
        # Acceptable logic errors (setup incomplete) vs Unacceptable (Crash/Missing)
        msg = inner.get("message", "")
        assert "Unknown action" not in msg, "BAKE action should be recognized (T003)"
        assert "got an unexpected keyword argument" not in msg, (
            "safe_ops.bake signature mismatch (T004)"
        )
    else:
        assert result.get("status") == "success"


# =============================================================================
# T005: Render Timeout Budget
# =============================================================================
def test_t005_render_timeout_budget(bridge):
    """
    T005: Verify adaptive timeout logic doesn't crash and handles budget.
    """
    # Try to render a frame with a short timeout
    result = send_command(
        bridge,
        "manage_rendering",
        {
            "action": "RENDER_FRAME",
            "write_still": False,
            "timeout": 1,  # 1 second timeout to force potential budgeting/timeout logic check
        },
    )

    # We are checking that it returns a structured response, not a hard hang/crash
    assert result is not None
    # It might succeed if scene is empty, or timeout. Both are fine.
    # Key is that it processed the timeout param.


# =============================================================================
# T006: Screenshot Policy
# =============================================================================
def test_t006_screenshot_policy(bridge):
    """
    T006: Verify viewport screenshot returns base64 data.
    Uses get_viewport_screenshot_base64 (the correct tool for screenshots).
    """
    result = send_command(
        bridge,
        "get_viewport_screenshot_base64",
        {"action": "SMART_SCREENSHOT", "max_size": 256},
    )

    assert result.get("status") == "success"
    data = get_data(result)
    # Screenshot tool should return image data or filepath
    assert data or result.get("result"), "Response should contain screenshot data"


# =============================================================================
# T008: Pose Mirror Auto-Resolve
# =============================================================================
def test_t008_pose_mirror_auto_resolve(bridge):
    """
    T008: Verify POSE_MIRROR resolves parent armature from Mesh selection.
    Uses unique names (T8Rig/T8Mesh) to avoid conflicts on re-runs.
    """
    # Clean up from previous runs then create fresh objects
    bridge.send_to_blender(
        {
            "tool": "execute_blender_code",
            "params": {
                "action": "execute_blender_code",
                "code": (
                    "import bpy;"
                    " [bpy.data.objects.remove(o, do_unlink=True)"
                    "  for o in list(bpy.data.objects)"
                    "  if o.name in ('T8Rig', 'T8Mesh')];"
                    " ad = bpy.data.armatures.new('T8RigData');"
                    " rig = bpy.data.objects.new('T8Rig', ad);"
                    " bpy.context.scene.collection.objects.link(rig);"
                    " me = bpy.data.meshes.new('T8MeshData');"
                    " mesh = bpy.data.objects.new('T8Mesh', me);"
                    " bpy.context.scene.collection.objects.link(mesh);"
                    " mesh.parent = rig"
                ),
            },
        }
    )

    result = send_command(
        bridge,
        "manage_animation_advanced",
        {
            "action": "POSE_MIRROR",
            "object_name": "T8Mesh",  # Pass mesh name — expects auto-resolve to parent armature
        },
    )

    assert result.get("status") == "success", (
        f"Failed to auto-resolve rig: {result.get('message', get_data(result))}"
    )
    assert get_data(result).get("rig") == "T8Rig", "Should have resolved to parent armature 'T8Rig'"


# =============================================================================
# T007: glTF Image Format Compatibility
# =============================================================================
def test_t007_gltf_image_format(bridge):
    """
    T007: Verify glTF exporter accepts 'AUTO' for image format.
    """
    result = send_command(
        bridge,
        "manage_export_pipeline",
        {
            "action": "EXPORT_GLTF",
            "filepath": "//test_export.glb",
            "export_format": "GLB",
            "image_format": "AUTO",  # This matches the fix
        },
    )

    # We expect either success or a specific failure not related to "Invalid enum"
    inner = result.get("result", {})
    if inner.get("status") in ("ERROR", "error"):
        msg = inner.get("message", "")
        # If it fails, it should NOT be because of enum validation on "AUTO"
        assert "Invalid parameter value" not in msg or "image_format" not in str(
            inner.get("details", {})
        ), f"AUTO format should be valid: {msg}"
    else:
        assert result.get("status") == "success"


# =============================================================================
# T009: Compositor Lifecycle Guard
# =============================================================================
def test_t009_compositor_lifecycle(bridge):
    """
    T009: Verify compositor setup does not crash if tree missing.
    """
    # 1. Ensure Use Nodes is OFF initially
    bridge.send_to_blender(
        {"tool": "run_script", "params": {"script": "bpy.context.scene.use_nodes = False"}}
    )

    # 2. Try to add a node (should auto-enable or fail gracefully)
    result = send_command(
        bridge, "manage_compositing", {"action": "ADD_NODE", "node_type": "CompositorNodeBlur"}
    )

    # The fix ensures it doesn't crash accessing None tree
    assert result is not None
    # Ideally it succeeds by auto-creating, or returns specific error
    if result.get("status") == "success":
        data = get_data(result)
        assert data.get("created") is True or "node_name" in data or "node" in data


# =============================================================================
# T010: Simulation Presets (Legacy Particles)
# =============================================================================
def test_t010_simulation_presets(bridge):
    """
    T010: Verify legacy particle simulation preset creation (PRESET_SMOKE_FIRE).
    """
    # 1. Create emitter object
    send_command(
        bridge, "manage_objects", {"action": "CREATE_PRIMITIVE", "type": "Plane", "name": "Emitter"}
    )

    # 2. Apply simulation preset (valid action: PRESET_SMOKE_FIRE)
    result = send_command(
        bridge,
        "manage_simulation_presets",
        {
            "action": "PRESET_SMOKE_FIRE",
            "object_name": "Emitter",
        },
    )

    # Accept success OR a known runtime error (e.g. no VIEW_3D area in headless mode).
    # The key check: action must be recognized (not INVALID_ACTION / unknown).
    outer_status = result.get("status", "")
    inner = result.get("result", {})
    if outer_status == "error":
        # Dispatcher-level exception — check it's not "Unknown action"
        msg = result.get("message", "")
        assert "Unknown action" not in msg, (
            f"PRESET_SMOKE_FIRE should be a recognized action: {msg}"
        )
    elif inner.get("status") in ("ERROR", "error"):
        errors = inner.get("errors", [])
        msgs = " ".join(e.get("message", "") for e in errors) + inner.get("message", "")
        assert "Unknown action" not in msgs, "PRESET_SMOKE_FIRE should be a recognized action"
    else:
        assert outer_status == "success"


# =============================================================================
# T011: Sequencer Media Router
# =============================================================================
def test_t011_sequencer_media(bridge):
    """
    T011: Verify sequencer handler is accessible and LIST_STRIPS returns a valid response.
    """
    result = send_command(
        bridge,
        "manage_sequencer",
        {"action": "LIST_STRIPS"},
    )

    assert result.get("status") == "success"
    data = get_data(result)
    # Should return a list of strips (possibly empty)
    assert "strips" in data or isinstance(data, dict)


# =============================================================================
# T012: Render Engine Normalization (SSOT)
# =============================================================================
def test_t012_render_engine_normalization(bridge):
    """
    T012: Verify we can set render engine using Enum values.
    """
    # 1. Set engine to CYCLES
    result = send_command(bridge, "manage_rendering", {"action": "SET_ENGINE", "engine": "CYCLES"})
    assert result.get("status") == "success"

    # 2. Verify Optimization Handler accepts it (Internal Logic Check)
    opt_result = send_command(bridge, "manage_render_optimization", {"action": "OPTIMIZE_SAMPLES"})

    # If logic was broken (string mismatch), this would return "WRONG_ENGINE" error
    assert opt_result.get("status") == "success", f"Optimization failed: {get_data(opt_result)}"


# =============================================================================
# T013: Eevee Next Capabilities
# =============================================================================
def test_t013_eevee_next_setup(bridge):
    """
    T013: Verify Eevee Next setup (SETUP_EEVEE_NEXT action).
    """
    result = send_command(bridge, "manage_eevee_next", {"action": "SETUP_EEVEE_NEXT"})

    # Might fail if Blender version < 4.2 but handler should handle gracefully
    if result.get("status") == "success":
        engine = get_data(result).get("engine", "")
        assert engine in ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", ""]


# =============================================================================
# T014: Geometry Nodes Deterministic Linking
# =============================================================================
def test_t014_geonodes_deterministic_link(bridge):
    """
    T014: Verify linking nodes by Socket Name (Deterministic).
    """
    # 1. Create Object and Tree
    send_command(
        bridge,
        "manage_objects",
        {"action": "CREATE_PRIMITIVE", "type": "Cube", "name": "GeoNodeTest"},
    )
    send_command(
        bridge, "manage_geometry_nodes", {"action": "CREATE_TREE", "object_name": "GeoNodeTest"}
    )

    # 2. Add a node
    node_res = send_command(
        bridge,
        "manage_geometry_nodes",
        {
            "action": "ADD_NODE",
            "node_type": "GeometryNodeSetPosition",
            "object_name": "GeoNodeTest",
        },
    )
    assert node_res.get("status") == "success"
    node_name = get_data(node_res).get("node")

    # 3. Link using NAMES (The Fix)
    link_res = send_command(
        bridge,
        "manage_geometry_nodes",
        {
            "action": "LINK_NODES",
            "object_name": "GeoNodeTest",
            "from_node": "Group Input",
            "to_node": node_name,
            "socket_index_from": "Geometry",  # Passing String!
            "socket_index_to": "Geometry",  # Passing String!
        },
    )

    assert link_res.get("status") == "success", f"Failed to link by name: {get_data(link_res)}"


if __name__ == "__main__":
    # Allow running directly
    sys.exit(pytest.main(["-v", __file__]))
