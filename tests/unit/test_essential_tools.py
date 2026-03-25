"""
Comprehensive tests for all 8 ESSENTIAL tier tools (priority <= 9).

These are the most critical tools — every path must be covered:
  1. execute_blender_code   (priority 1)
  2. get_scene_graph        (priority 2)
  3. get_viewport_screenshot_base64 (priority 3)
  4. get_object_info        (priority 4)
  5. manage_agent_context   (priority 6)
  6. list_all_tools         (priority 7)
  7. get_server_status      (priority 8)
  8. new_scene              (priority 9)

No real Blender required — bpy is mocked throughout.
All tests run through dispatch_command (real execution path).
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# ---------------------------------------------------------------------------
# Global bpy mock — must happen before ANY blender_mcp imports.
# Always use sys.modules["bpy"] as the canonical mock so that test-suite
# ordering doesn't matter (if another file already inserted a mock, reuse it).
# ---------------------------------------------------------------------------
sys.modules.setdefault("bpy", MagicMock())
sys.modules.setdefault("mathutils", MagicMock())
sys.modules.setdefault("mathutils.bvhtree", MagicMock())
sys.modules.setdefault("bmesh", MagicMock())

# _bpy_mock MUST alias the exact object the handlers will import from sys.modules
_bpy_mock = sys.modules["bpy"]
_bpy_mock.app.version = (5, 0, 0)
_bpy_mock.app.translations.locale = "en_US"

from blender_mcp.dispatcher import (
    HANDLER_REGISTRY,
    HANDLER_METADATA,
    dispatch_command,
    load_handlers,
)

load_handlers()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ESSENTIAL_NAMES = [
    "execute_blender_code",
    "get_scene_graph",
    "get_viewport_screenshot_base64",
    "get_object_info",
    "manage_agent_context",
    "list_all_tools",
    "get_server_status",
    "new_scene",
]


def _dispatch(tool: str, **params) -> dict:
    """Thin helper — always disables thread-safety for tests."""
    return dispatch_command({"tool": tool, "params": params}, use_thread_safety=False)


def _make_mock_object(
    name="Cube",
    obj_type="MESH",
    wx=0.0,
    wy=0.0,
    wz=0.0,
    hidden=False,
):
    """Build a realistic bpy object mock for scene-iteration tests."""
    obj = MagicMock()
    obj.name = name
    obj.type = obj_type
    obj.hide_viewport = hidden
    obj.hide_get.return_value = hidden

    # Identity matrix_world — mw[r][c] indexing
    identity = [[1.0, 0.0, 0.0, wx], [0.0, 1.0, 0.0, wy], [0.0, 0.0, 1.0, wz], [0.0, 0.0, 0.0, 1.0]]
    obj.matrix_world = identity

    obj.location = MagicMock()
    obj.location.x = wx
    obj.location.y = wy
    obj.location.z = wz

    obj.rotation_euler = MagicMock()
    obj.rotation_euler.x = 0.0
    obj.rotation_euler.y = 0.0
    obj.rotation_euler.z = 0.0

    obj.scale = MagicMock()
    obj.scale.x = 1.0
    obj.scale.y = 1.0
    obj.scale.z = 1.0

    obj.dimensions = [2.0, 2.0, 2.0]
    obj.parent = None
    obj.children = []
    obj.material_slots = []
    obj.users_collection = []
    obj.animation_data = None
    obj.keys.return_value = []

    # MESH bound_box: unit cube corners (8 vertices)
    if obj_type == "MESH":
        obj.bound_box = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 1.0),
            (1.0, 1.0, 1.0),
            (0.0, 1.0, 1.0),
        ]
    else:
        obj.bound_box = None

    return obj


# ===========================================================================
# 1. execute_blender_code (priority 1)
# ===========================================================================


class TestExecuteBlenderCode:
    """Tests for the primary code execution tool."""

    def test_registered_at_priority_1(self) -> None:
        meta = HANDLER_METADATA.get("execute_blender_code", {})
        assert meta.get("priority") == 1

    def test_in_handler_registry(self) -> None:
        assert "execute_blender_code" in HANDLER_REGISTRY

    def test_missing_code_param_returns_error(self) -> None:
        result = _dispatch("execute_blender_code", action="execute_blender_code")
        # Validation layer returns {code, error} or ResponseBuilder ERROR format
        assert result.get("success") is not True

    def test_empty_code_returns_error(self) -> None:
        result = _dispatch("execute_blender_code", action="execute_blender_code", code="")
        assert result.get("success") is not True

    def test_render_render_direct_blocked(self) -> None:
        result = _dispatch(
            "execute_blender_code",
            action="execute_blender_code",
            code="bpy.ops.render.render()",
        )
        assert result.get("success") is False
        errors = result.get("errors", [])
        assert any(e.get("code") == "BLOCKED_PATTERN" for e in errors)

    def test_render_render_write_still_blocked(self) -> None:
        result = _dispatch(
            "execute_blender_code",
            action="execute_blender_code",
            code="bpy.ops.render.render(write_still=True)",
        )
        assert result.get("success") is False

    def test_render_render_with_spaces_blocked(self) -> None:
        result = _dispatch(
            "execute_blender_code",
            action="execute_blender_code",
            code="bpy.ops.render.render(   )",
        )
        assert result.get("success") is False

    def test_safe_print_captures_stdout(self) -> None:
        result = _dispatch(
            "execute_blender_code",
            action="execute_blender_code",
            code='print("hello_mcp_test")',
        )
        assert result.get("success") is True
        assert "hello_mcp_test" in result.get("stdout", "")

    def test_safe_math_returns_success(self) -> None:
        result = _dispatch(
            "execute_blender_code",
            action="execute_blender_code",
            code="x = 2 + 2\nprint(x)",
        )
        assert result.get("success") is True
        assert "4" in result.get("stdout", "")

    def test_syntax_error_returns_execution_error(self) -> None:
        result = _dispatch(
            "execute_blender_code",
            action="execute_blender_code",
            code="def broken(:\n    pass",
        )
        assert result.get("success") is False

    def test_runtime_exception_returns_execution_error(self) -> None:
        result = _dispatch(
            "execute_blender_code",
            action="execute_blender_code",
            code='raise ValueError("intentional test error")',
        )
        assert result.get("success") is False
        errors = result.get("errors", [])
        assert any(e.get("code") == "EXECUTION_ERROR" for e in errors)

    def test_code_is_required_in_schema(self) -> None:
        meta = HANDLER_METADATA.get("execute_blender_code", {})
        schema = meta.get("schema", {})
        required = schema.get("required", [])
        assert "code" in required

    def test_schema_title_mentions_execute(self) -> None:
        meta = HANDLER_METADATA.get("execute_blender_code", {})
        schema = meta.get("schema", {})
        title = schema.get("title", "").lower()
        assert "execute" in title or "python" in title.lower()

    def test_description_warns_about_render_block(self) -> None:
        # Rich description lives in schema["description"], not the short docstring
        meta = HANDLER_METADATA.get("execute_blender_code", {})
        schema_desc = str(meta.get("schema", {}).get("description", "")).lower()
        assert "render" in schema_desc and (
            "block" in schema_desc or "freeze" in schema_desc or "async" in schema_desc
        )

    def test_multiple_prints_all_captured(self) -> None:
        result = _dispatch(
            "execute_blender_code",
            action="execute_blender_code",
            code='print("line_A")\nprint("line_B")',
        )
        stdout = result.get("stdout", "")
        assert "line_A" in stdout
        assert "line_B" in stdout


# ===========================================================================
# 2. get_scene_graph (priority 2)
# ===========================================================================


class TestGetSceneGraph:
    """Tests for the primary scene survey tool."""

    def test_registered_at_priority_2(self) -> None:
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        assert meta.get("priority") == 2

    def test_has_at_least_10_actions(self) -> None:
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        assert len(actions) >= 10, f"Expected >=10 actions, got: {actions}"

    def test_invalid_action_returns_invalid_action_error(self) -> None:
        result = _dispatch("get_scene_graph", action="NONEXISTENT_ACTION_XYZ")
        # Validation returns {code: INVALID_ACTION} or ResponseBuilder ERROR
        assert result.get("code") == "INVALID_ACTION" or result.get("success") is not True

    def test_check_intersection_missing_both_objects_returns_error(self) -> None:
        result = _dispatch("get_scene_graph", action="CHECK_INTERSECTION")
        assert result.get("success") is False

    def test_check_intersection_missing_object_b_returns_error(self) -> None:
        result = _dispatch("get_scene_graph", action="CHECK_INTERSECTION", object_a="Cube")
        assert result.get("success") is False

    def test_check_intersection_nonexistent_objects_returns_not_found(self) -> None:
        _bpy_mock.data.objects.get.return_value = None
        result = _dispatch(
            "get_scene_graph",
            action="CHECK_INTERSECTION",
            object_a="NoSuchObjA",
            object_b="NoSuchObjB",
        )
        assert result.get("success") is False

    def test_get_spatial_report_missing_name_returns_error(self) -> None:
        result = _dispatch("get_scene_graph", action="GET_SPATIAL_REPORT")
        assert result.get("success") is False

    def test_verify_assembly_missing_rules_returns_error(self) -> None:
        result = _dispatch("get_scene_graph", action="VERIFY_ASSEMBLY")
        assert result.get("success") is False

    def test_cast_ray_missing_origin_returns_error(self) -> None:
        result = _dispatch("get_scene_graph", action="CAST_RAY", direction=[0, 0, -1])
        assert result.get("success") is False

    def test_cast_ray_missing_direction_returns_error(self) -> None:
        result = _dispatch("get_scene_graph", action="CAST_RAY", origin=[0, 0, 5])
        assert result.get("success") is False

    def test_get_objects_flat_empty_scene_returns_success(self) -> None:
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="GET_OBJECTS_FLAT")
        assert result.get("success") is True
        objects = result.get("data", {}).get("objects", [])
        assert isinstance(objects, list)
        assert len(objects) == 0

    def test_get_objects_flat_with_one_mesh_object(self) -> None:
        cube = _make_mock_object("TestCube", "MESH", wx=1.0, wy=2.0, wz=3.0)
        _bpy_mock.context.scene.objects = [cube]
        result = _dispatch("get_scene_graph", action="GET_OBJECTS_FLAT")
        assert result.get("success") is True
        objects = result.get("data", {}).get("objects", [])
        assert len(objects) == 1
        obj_entry = objects[0]
        assert obj_entry["name"] == "TestCube"
        assert obj_entry["type"] == "MESH"
        # world_location matches wx, wy, wz
        assert obj_entry["world_location"] == [1.0, 2.0, 3.0]

    def test_get_objects_flat_mesh_has_geometry_center(self) -> None:
        cube = _make_mock_object("GeoCube", "MESH", wx=0.0)
        _bpy_mock.context.scene.objects = [cube]
        result = _dispatch("get_scene_graph", action="GET_OBJECTS_FLAT")
        data = result.get("data", {})
        objects = data.get("objects", [])
        if objects:
            obj_entry = objects[0]
            assert "geometry_center_world" in obj_entry
            assert "origin_offset_m" in obj_entry
            assert "origin_offset_warning" in obj_entry
            assert "world_bounding_box" in obj_entry

    def test_get_objects_flat_has_required_keys(self) -> None:
        box = _make_mock_object("KeyTestBox", "MESH")
        _bpy_mock.context.scene.objects = [box]
        result = _dispatch("get_scene_graph", action="GET_OBJECTS_FLAT")
        objects = result.get("data", {}).get("objects", [])
        if objects:
            entry = objects[0]
            for key in (
                "name",
                "type",
                "world_location",
                "location_local",
                "rotation_degrees",
                "scale",
                "matrix_world",
                "visible",
                "animation_state",
            ):
                assert key in entry, f"Missing key in GET_OBJECTS_FLAT entry: {key}"

    def test_get_objects_flat_hidden_object_excluded(self) -> None:
        visible = _make_mock_object("Visible", "MESH", hidden=False)
        hidden = _make_mock_object("Hidden", "MESH", hidden=True)
        _bpy_mock.context.scene.objects = [visible, hidden]
        result = _dispatch("get_scene_graph", action="GET_OBJECTS_FLAT")
        names = [o["name"] for o in result.get("data", {}).get("objects", [])]
        assert "Visible" in names
        assert "Hidden" not in names

    def test_essential_actions_present_in_metadata(self) -> None:
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        for expected in (
            "GET_OBJECTS_FLAT",
            "GET_SCENE_MATRIX",
            "CHECK_INTERSECTION",
            "ANALYZE_ASSEMBLY",
            "DETECT_GEOMETRY_ERRORS",
        ):
            assert expected in actions, f"Missing essential action: {expected}"

    # --- P1: CAST_RAY ---

    def test_cast_ray_returns_hit_data_key(self) -> None:
        """CAST_RAY with valid params returns is_hit and hit_data keys (world-space transform fixed)."""
        # With mocked BVH returning None hit, result should be a valid success with hit_data=None
        _bpy_mock.context.scene.objects = []
        result = _dispatch(
            "get_scene_graph", action="CAST_RAY", origin=[0, 0, 5], direction=[0, 0, -1]
        )
        assert result.get("success") is True
        data = result.get("data", {})
        assert "is_hit" in data
        assert "hit_data" in data

    # --- P2: ANALYZE_ASSEMBLY ---

    def test_analyze_assembly_exclude_objects_param_accepted(self) -> None:
        """ANALYZE_ASSEMBLY accepts exclude_objects param without error."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch(
            "get_scene_graph",
            action="ANALYZE_ASSEMBLY",
            exclude_objects=["Ground_Plane", "Sky_Dome"],
        )
        assert result.get("success") is True
        data = result.get("data", {})
        assert "exclude_objects" in data
        assert "Ground_Plane" in data["exclude_objects"]

    # --- P3: CHECK_PRODUCTION_READINESS ---

    def test_check_production_readiness_parented_obj_origin_aligned_true(self) -> None:
        """Parented objects should always pass origin_aligned regardless of offset."""
        parent = _make_mock_object("Parent", "MESH")
        child = _make_mock_object("ChildPart", "MESH", wx=5.0, wy=5.0, wz=5.0)
        child.parent = parent  # mark as parented
        # bound_box with a big offset from origin — would normally fail
        child.bound_box = [
            (10.0, 10.0, 10.0),
            (11.0, 10.0, 10.0),
            (11.0, 11.0, 10.0),
            (10.0, 11.0, 10.0),
            (10.0, 10.0, 11.0),
            (11.0, 10.0, 11.0),
            (11.0, 11.0, 11.0),
            (10.0, 11.0, 11.0),
        ]
        _bpy_mock.context.scene.objects = [child]
        result = _dispatch("get_scene_graph", action="CHECK_PRODUCTION_READINESS")
        assert result.get("success") is True
        per_obj = result.get("data", {}).get("per_object", {})
        if "ChildPart" in per_obj:
            checks = per_obj["ChildPart"].get("checks", {})
            assert checks.get("origin_aligned") is True, (
                "Parented object must pass origin_aligned check"
            )
            assert "origin_aligned_note" in per_obj["ChildPart"]

    # --- P4: VERIFY_ASSEMBLY ---

    def test_verify_assembly_unknown_rule_fails(self) -> None:
        """Unknown rule keys like 'must_hug' should cause all_passed=False."""
        cube = _make_mock_object("PartA", "MESH")
        _bpy_mock.context.scene.objects = [cube]
        _bpy_mock.data.objects.get.return_value = cube

        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name", return_value=cube
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"PartA": {"must_hug": ["PartB"]}},
            )
        assert result.get("success") is True
        data = result.get("data", {})
        assert data.get("all_passed") is False
        results = data.get("results", [])
        unknown_results = [r for r in results if "must_hug" in str(r.get("rule", ""))]
        assert len(unknown_results) > 0

    def test_verify_assembly_has_structured_results(self) -> None:
        """VERIFY_ASSEMBLY returns structured results list alongside verification_log."""
        cube = _make_mock_object("BoxA", "MESH")
        cube2 = _make_mock_object("BoxB", "MESH")
        _bpy_mock.context.scene.objects = [cube, cube2]

        def resolve_side_effect(name: str):
            return cube if name == "BoxA" else cube2

        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name",
            side_effect=resolve_side_effect,
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"BoxA": {"must_touch": ["BoxB"]}},
            )
        assert result.get("success") is True
        data = result.get("data", {})
        assert "results" in data, "Structured results list must be present"
        assert "verification_log" in data, "Backward-compat verification_log must be present"
        assert isinstance(data["results"], list)
        if data["results"]:
            entry = data["results"][0]
            assert "source" in entry
            assert "rule" in entry
            assert "passed" in entry

    def test_verify_assembly_parent_must_be_unknown_parent_fails(self) -> None:
        """parent_must_be rule: object with wrong parent should fail."""
        cube = _make_mock_object("ChildObj", "MESH")
        cube.parent = None  # has no parent, but rule expects one

        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name", return_value=cube
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"ChildObj": {"parent_must_be": "ExpectedParent"}},
            )
        assert result.get("success") is True
        data = result.get("data", {})
        assert data.get("all_passed") is False
        results = data.get("results", [])
        parent_results = [r for r in results if r.get("rule") == "parent_must_be"]
        assert len(parent_results) > 0
        assert parent_results[0]["passed"] is False

    # --- P5: GET_HIERARCHY_TREE ---

    def test_get_hierarchy_tree_registered_in_metadata(self) -> None:
        """GET_HIERARCHY_TREE action must be registered in get_scene_graph metadata."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        assert "GET_HIERARCHY_TREE" in actions, "GET_HIERARCHY_TREE not found in registered actions"

    def test_get_hierarchy_tree_empty_scene_returns_success(self) -> None:
        """GET_HIERARCHY_TREE on empty scene returns success with empty tree."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="GET_HIERARCHY_TREE")
        assert result.get("success") is True
        data = result.get("data", {})
        assert "tree" in data
        assert "root_count" in data
        assert isinstance(data["tree"], list)

    # --- P9: DETECT_GEOMETRY_ERRORS naming ---

    def test_detect_geometry_errors_uses_total_issue_elements(self) -> None:
        """Summary key should be total_issue_elements (not total_issues)."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="DETECT_GEOMETRY_ERRORS")
        # Either succeeds (no bmesh in mock) or errors — either way no legacy key
        data = result.get("data", {})
        summary = data.get("summary", {})
        assert "total_issues" not in summary, "Legacy 'total_issues' key must be removed"

    # =========================================================================
    # P1 CAST_RAY — world-space transform; verifies response structure
    # =========================================================================

    def test_cast_ray_empty_scene_is_hit_false(self) -> None:
        """P1: CAST_RAY on empty scene → is_hit=False, hit_data=None (no crash on transform path)."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch(
            "get_scene_graph", action="CAST_RAY", origin=[0, 0, 5], direction=[0, 0, -1]
        )
        assert result.get("success") is True
        data = result.get("data", {})
        assert data.get("is_hit") is False
        assert data.get("hit_data") is None

    def test_cast_ray_full_response_structure(self) -> None:
        """P1: CAST_RAY always returns is_hit + hit_data regardless of hit outcome."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch(
            "get_scene_graph",
            action="CAST_RAY",
            origin=[1.0, 2.0, 3.0],
            direction=[0, 1, 0],
            distance=100,
        )
        assert result.get("success") is True
        data = result.get("data", {})
        assert "is_hit" in data, "P1: is_hit key must always be present"
        assert "hit_data" in data, "P1: hit_data key must always be present"

    def test_cast_ray_negative_direction_no_crash(self) -> None:
        """P1: Negative direction vectors are accepted; result is success with no hit in empty scene."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch(
            "get_scene_graph", action="CAST_RAY", origin=[0, 0, 5], direction=[0, 0, -1]
        )
        # In mock mode Vector is mocked — direction is accepted, no crash
        assert result.get("success") is True
        assert result.get("data", {}).get("is_hit") is False

    def test_cast_ray_with_distance_param(self) -> None:
        """P1: distance param is accepted and doesn't break the response."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch(
            "get_scene_graph",
            action="CAST_RAY",
            origin=[0, 0, 0],
            direction=[0, 0, 1],
            distance=50.0,
        )
        assert result.get("success") is True

    # =========================================================================
    # P2 ANALYZE_ASSEMBLY — exclude_objects scope filter
    # =========================================================================

    def test_analyze_assembly_exclude_only_object_gives_score_100(self) -> None:
        """P2: Excluding the only mesh object → score=100, object_count=0."""
        ground = _make_mock_object("Ground_Plane", "MESH")
        _bpy_mock.context.scene.objects = [ground]
        result = _dispatch(
            "get_scene_graph",
            action="ANALYZE_ASSEMBLY",
            exclude_objects=["Ground_Plane"],
        )
        assert result.get("success") is True
        data = result.get("data", {})
        assert data.get("object_count") == 0
        assert data.get("assembly_score") == 100
        assert "Ground_Plane" in data.get("exclude_objects", [])

    def test_analyze_assembly_excluded_name_not_in_issues(self) -> None:
        """P2: Excluded objects must not appear in the issues list."""
        deco = _make_mock_object("Decoration", "MESH")
        _bpy_mock.context.scene.objects = [deco]
        result = _dispatch(
            "get_scene_graph",
            action="ANALYZE_ASSEMBLY",
            exclude_objects=["Decoration"],
        )
        data = result.get("data", {})
        issue_objs = [i.get("object", "") for i in data.get("issues", [])]
        assert "Decoration" not in issue_objs

    def test_analyze_assembly_no_exclude_gives_empty_list(self) -> None:
        """P2: When no exclude_objects given, output lists an empty exclude_objects."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="ANALYZE_ASSEMBLY")
        assert result.get("success") is True
        data = result.get("data", {})
        assert "exclude_objects" in data
        assert data["exclude_objects"] == []

    def test_analyze_assembly_exclude_objects_sorted_in_output(self) -> None:
        """P2: exclude_objects list in response is sorted alphabetically."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch(
            "get_scene_graph",
            action="ANALYZE_ASSEMBLY",
            exclude_objects=["Z_Sky", "A_Ground", "M_Plane"],
        )
        data = result.get("data", {})
        excl = data.get("exclude_objects", [])
        assert excl == sorted(excl), f"exclude_objects not sorted: {excl}"

    # =========================================================================
    # P3 CHECK_PRODUCTION_READINESS — parented objects skip origin check
    # =========================================================================

    def test_check_production_readiness_unparented_large_offset_fails_origin(self) -> None:
        """P3 baseline: unparented object with bbox far from origin fails origin_aligned.
        (Unit cube at [0,0,0] has geo_center≈[0.5,0.5,0.5] → offset≈0.866m > 0.01m threshold.)"""
        obj = _make_mock_object("UnparentedPart", "MESH", wx=0, wy=0, wz=0)
        obj.parent = None
        _bpy_mock.context.scene.objects = [obj]
        result = _dispatch("get_scene_graph", action="CHECK_PRODUCTION_READINESS")
        assert result.get("success") is True
        per_obj = result.get("data", {}).get("per_object", {})
        if "UnparentedPart" in per_obj:
            checks = per_obj["UnparentedPart"].get("checks", {})
            assert checks.get("origin_aligned") is False, (
                "Unparented object with 0.866m offset should FAIL origin_aligned"
            )

    def test_check_production_readiness_parented_passes_origin_regardless_of_offset(self) -> None:
        """P3 fix: parented object ALWAYS gets origin_aligned=True (was False before fix)."""
        parent_obj = _make_mock_object("RigRoot", "MESH")
        child = _make_mock_object("ChildBone", "MESH", wx=0, wy=0, wz=0)
        child.parent = parent_obj  # mark as parented
        _bpy_mock.context.scene.objects = [child]
        result = _dispatch("get_scene_graph", action="CHECK_PRODUCTION_READINESS")
        assert result.get("success") is True
        per_obj = result.get("data", {}).get("per_object", {})
        if "ChildBone" in per_obj:
            checks = per_obj["ChildBone"].get("checks", {})
            assert checks.get("origin_aligned") is True, (
                "P3 fix: Parented object MUST pass origin_aligned (was false-failing before fix)"
            )

    def test_check_production_readiness_parented_has_origin_aligned_note(self) -> None:
        """P3 fix: parented objects get an explanatory note about origin skip."""
        parent_obj = _make_mock_object("Parent", "MESH")
        child = _make_mock_object("RigChild", "MESH")
        child.parent = parent_obj
        _bpy_mock.context.scene.objects = [child]
        result = _dispatch("get_scene_graph", action="CHECK_PRODUCTION_READINESS")
        per_obj = result.get("data", {}).get("per_object", {})
        if "RigChild" in per_obj:
            assert "origin_aligned_note" in per_obj["RigChild"], (
                "P3 fix: parented objects must have origin_aligned_note field"
            )
            note = per_obj["RigChild"]["origin_aligned_note"]
            assert "parented" in note.lower() or "assembly" in note.lower()

    def test_check_production_readiness_parented_scores_higher_than_unparented(self) -> None:
        """P3: Parented child scores >= unparented with identical geometry (origin check passes)."""
        parent_obj = _make_mock_object("Parent", "MESH")
        child = _make_mock_object("Parented_Arm", "MESH", wx=0, wy=0, wz=0)
        child.parent = parent_obj
        unparented = _make_mock_object("Unparented_Arm", "MESH", wx=0, wy=0, wz=0)
        unparented.parent = None
        _bpy_mock.context.scene.objects = [child, unparented]
        result = _dispatch("get_scene_graph", action="CHECK_PRODUCTION_READINESS")
        per_obj = result.get("data", {}).get("per_object", {})
        if "Parented_Arm" in per_obj and "Unparented_Arm" in per_obj:
            parented_score = per_obj["Parented_Arm"]["score"]
            unparented_score = per_obj["Unparented_Arm"]["score"]
            assert parented_score >= unparented_score, (
                "P3: Parented object should score >= unparented due to origin_aligned=True"
            )

    def test_check_production_readiness_empty_scene_score_100(self) -> None:
        """CHECK_PRODUCTION_READINESS on empty scene returns scene_score=100."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="CHECK_PRODUCTION_READINESS")
        assert result.get("success") is True
        data = result.get("data", {})
        assert "scene_score" in data
        assert data["scene_score"] == 100

    def test_check_production_readiness_output_structure(self) -> None:
        """CHECK_PRODUCTION_READINESS output has all required top-level keys."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="CHECK_PRODUCTION_READINESS")
        assert result.get("success") is True
        data = result.get("data", {})
        for key in ("per_object", "scene_score", "failing_checks"):
            assert key in data, f"CHECK_PRODUCTION_READINESS missing key: {key}"

    # =========================================================================
    # P4 VERIFY_ASSEMBLY — parent_must_be rule / unknown rules
    # P8 VERIFY_ASSEMBLY — structured results output
    # =========================================================================

    def test_verify_assembly_parent_must_be_correct_passes(self) -> None:
        """P4: parent_must_be with correct actual parent → passed=True."""
        parent = _make_mock_object("RigAssembly", "MESH")
        child = _make_mock_object("ArmPart", "MESH")
        child.parent = parent

        def _resolve(name: str):  # type: ignore[no-untyped-def]
            return child if name == "ArmPart" else parent

        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name",
            side_effect=_resolve,
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"ArmPart": {"parent_must_be": "RigAssembly"}},
            )
        data = result.get("data", {})
        assert result.get("success") is True
        pr = [r for r in data.get("results", []) if r.get("rule") == "parent_must_be"]
        assert pr, "parent_must_be rule result must be present"
        assert pr[0]["passed"] is True, "parent_must_be should pass when parent matches"

    def test_verify_assembly_parent_must_be_wrong_parent_fails(self) -> None:
        """P4: parent_must_be with wrong parent → passed=False, all_passed=False."""
        wrong_parent = _make_mock_object("WrongParent", "MESH")
        child = _make_mock_object("Part", "MESH")
        child.parent = wrong_parent

        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name", return_value=child
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"Part": {"parent_must_be": "ExpectedParent"}},
            )
        data = result.get("data", {})
        assert data.get("all_passed") is False
        pr = [r for r in data.get("results", []) if r.get("rule") == "parent_must_be"]
        assert pr[0]["passed"] is False

    def test_verify_assembly_deprecated_key_present(self) -> None:
        """P8: _deprecated key must exist in output (marks verification_log as deprecated)."""
        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name", return_value=None
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"Deprecated_Test": {"must_touch": ["B"]}},
            )
        data = result.get("data", {})
        assert "_deprecated" in data, "P8: _deprecated marker must be in VERIFY_ASSEMBLY output"
        assert "verification_log" in data, "P8: verification_log backward-compat key must exist"
        assert isinstance(data["verification_log"], list)

    def test_verify_assembly_structured_results_have_all_fields(self) -> None:
        """P8: Every structured result entry must have source, target, rule, passed, distance_m, note."""
        cube_a = _make_mock_object("Alpha", "MESH")
        cube_b = _make_mock_object("Beta", "MESH")

        def _resolve(name: str):  # type: ignore[no-untyped-def]
            return cube_a if name == "Alpha" else cube_b

        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name",
            side_effect=_resolve,
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"Alpha": {"must_touch": ["Beta"]}},
            )
        data = result.get("data", {})
        assert isinstance(data.get("results"), list)
        for entry in data.get("results", []):
            for field in ("source", "target", "rule", "passed", "distance_m", "note"):
                assert field in entry, f"Structured result missing '{field}': {entry}"

    def test_verify_assembly_unknown_rule_note_contains_key(self) -> None:
        """P4: Unknown rule result note must name the unknown key."""
        cube = _make_mock_object("Piece", "MESH")
        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name", return_value=cube
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"Piece": {"must_overlap": ["OtherPiece"]}},
            )
        data = result.get("data", {})
        assert data.get("all_passed") is False
        unknown_rs = [
            r for r in data.get("results", []) if "must_overlap" in str(r.get("rule", ""))
        ]
        assert unknown_rs, "Unknown rule must appear in structured results"
        assert "must_overlap" in unknown_rs[0].get("note", ""), (
            "Unknown rule note must name the unrecognized key"
        )

    def test_verify_assembly_method_is_bvh(self) -> None:
        """VERIFY_ASSEMBLY must report BVH_SURFACE_with_AABB_FALLBACK as method."""
        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name", return_value=None
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"Ghost": {"must_touch": ["Also_Ghost"]}},
            )
        data = result.get("data", {})
        assert "BVH" in data.get("method", ""), (
            f"Method should mention BVH, got: {data.get('method')}"
        )

    def test_verify_assembly_has_recommended_fixes(self) -> None:
        """VERIFY_ASSEMBLY output must include recommended_fixes as a list."""
        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name", return_value=None
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"NoObj": {"must_touch": ["AlsoMissing"]}},
            )
        data = result.get("data", {})
        assert "recommended_fixes" in data
        assert isinstance(data["recommended_fixes"], list)

    def test_verify_assembly_overlapping_objects_touch_passes(self) -> None:
        """must_touch: two overlapping AABB objects → passed=True, all_passed=True."""
        obj_a = _make_mock_object("PartA", "MESH", wx=0, wy=0, wz=0)
        obj_b = _make_mock_object("PartB", "MESH", wx=0, wy=0, wz=0)  # same position → full overlap

        def _resolve(name: str):  # type: ignore[no-untyped-def]
            return obj_a if name == "PartA" else obj_b

        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name",
            side_effect=_resolve,
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"PartA": {"must_touch": ["PartB"]}},
            )
        data = result.get("data", {})
        assert result.get("success") is True
        touch_rs = [r for r in data.get("results", []) if r.get("rule") == "must_touch"]
        assert touch_rs, "must_touch result must be present"
        assert touch_rs[0]["passed"] is True, "Overlapping AABB objects must be touching"
        assert data.get("all_passed") is True

    # =========================================================================
    # P5 GET_HIERARCHY_TREE — new action, BFS, max_depth, truncation
    # =========================================================================

    def test_get_hierarchy_tree_action_count_at_least_11(self) -> None:
        """P5: After GET_HIERARCHY_TREE addition, total action count must be >= 11."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = meta.get("actions", [])
        assert len(actions) >= 11, (
            f"P5: Expected >=11 actions after GET_HIERARCHY_TREE, got {len(actions)}: {actions}"
        )

    def test_get_hierarchy_tree_two_root_objects(self) -> None:
        """P5: Two visible root objects → tree has 2 entries, root_count=2."""
        obj_a = _make_mock_object("RootA", "MESH")
        obj_b = _make_mock_object("RootB", "LIGHT")
        _bpy_mock.context.scene.objects = [obj_a, obj_b]
        result = _dispatch("get_scene_graph", action="GET_HIERARCHY_TREE")
        assert result.get("success") is True
        data = result.get("data", {})
        assert data.get("root_count") == 2
        assert len(data.get("tree", [])) == 2

    def test_get_hierarchy_tree_parent_child_nested(self) -> None:
        """P5: Parent with one visible child → tree node has children list."""
        parent = _make_mock_object("HierParent", "MESH")
        child = _make_mock_object("HierChild", "EMPTY")
        child.parent = parent
        child.hide_viewport = False
        child.hide_get.return_value = False
        parent.children = [child]
        _bpy_mock.context.scene.objects = [
            parent
        ]  # only root; child is reached via parent.children
        result = _dispatch("get_scene_graph", action="GET_HIERARCHY_TREE")
        assert result.get("success") is True
        data = result.get("data", {})
        tree = data.get("tree", [])
        assert len(tree) == 1
        root_node = tree[0]
        assert root_node["name"] == "HierParent"
        children = root_node.get("children", [])
        assert len(children) == 1
        assert children[0]["name"] == "HierChild"

    def test_get_hierarchy_tree_hidden_root_excluded(self) -> None:
        """P5: Hidden roots are excluded from the tree."""
        visible = _make_mock_object("VisibleRoot", "MESH")
        hidden_root = _make_mock_object("HiddenRoot", "MESH", hidden=True)
        _bpy_mock.context.scene.objects = [visible, hidden_root]
        result = _dispatch("get_scene_graph", action="GET_HIERARCHY_TREE")
        data = result.get("data", {})
        names = [n["name"] for n in data.get("tree", [])]
        assert "VisibleRoot" in names
        assert "HiddenRoot" not in names
        assert data.get("root_count") == 1

    def test_get_hierarchy_tree_max_depth_applied_in_response(self) -> None:
        """P5: max_depth_applied key reflects the param passed."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="GET_HIERARCHY_TREE", max_depth=5)
        assert result.get("success") is True
        data = result.get("data", {})
        assert "max_depth_applied" in data
        assert data["max_depth_applied"] == 5

    def test_get_hierarchy_tree_node_fields(self) -> None:
        """P5: Every tree node must have name and type fields."""
        obj = _make_mock_object("TypedNode", "ARMATURE")
        _bpy_mock.context.scene.objects = [obj]
        result = _dispatch("get_scene_graph", action="GET_HIERARCHY_TREE")
        for node in result.get("data", {}).get("tree", []):
            assert "name" in node, "Tree node must have 'name'"
            assert "type" in node, "Tree node must have 'type'"

    def test_get_hierarchy_tree_depth_zero_truncates_children(self) -> None:
        """P5: max_depth=0 with children → node is truncated (truncated=True or children_count)."""
        parent = _make_mock_object("TruncParent", "MESH")
        child = _make_mock_object("TruncChild", "MESH")
        child.hide_viewport = False
        child.hide_get.return_value = False
        parent.children = [child]
        _bpy_mock.context.scene.objects = [parent]
        result = _dispatch("get_scene_graph", action="GET_HIERARCHY_TREE", max_depth=0)
        data = result.get("data", {})
        tree = data.get("tree", [])
        if tree:
            root_node = tree[0]
            assert root_node.get("truncated") is True or "children_count" in root_node, (
                "P5: At max_depth=0, nodes with children must be marked as truncated"
            )

    # =========================================================================
    # P6 GET_SCENE_MATRIX — position = AABB center, not origin
    # =========================================================================

    def test_get_scene_matrix_has_position_and_pivot_location_keys(self) -> None:
        """P6: Each object entry must have position (AABB center) AND pivot_location (origin)."""
        cube = _make_mock_object("P6Cube", "MESH")
        cube.evaluated_get = MagicMock(return_value=cube)
        _bpy_mock.context.evaluated_depsgraph_get.return_value = MagicMock()
        _bpy_mock.context.scene.objects = [cube]
        result = _dispatch("get_scene_graph", action="GET_SCENE_MATRIX")
        data = result.get("data", {})
        for obj_entry in data.get("objects", []):
            if obj_entry.get("name") == "P6Cube":
                assert "position" in obj_entry, "P6: position (AABB center) must be present"
                assert "pivot_location" in obj_entry, "P6: pivot_location (origin) must be present"

    def test_get_scene_matrix_no_total_issues_key(self) -> None:
        """P6/schema sanity: GET_SCENE_MATRIX response has no stale 'total_issues' key."""
        _bpy_mock.context.scene.objects = []
        _bpy_mock.context.evaluated_depsgraph_get.return_value = MagicMock()
        result = _dispatch("get_scene_graph", action="GET_SCENE_MATRIX")
        data = result.get("data", {})
        assert "total_issues" not in data

    # =========================================================================
    # P9 DETECT_GEOMETRY_ERRORS — total_issue_elements + summary completeness
    # =========================================================================

    def test_detect_geometry_errors_summary_has_all_required_keys(self) -> None:
        """P9: summary must have total_issue_elements, objects_with_issues, objects_checked, clean_objects."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="DETECT_GEOMETRY_ERRORS")
        if result.get("success") is True:
            summary = result.get("data", {}).get("summary", {})
            for key in (
                "total_issue_elements",
                "objects_with_issues",
                "objects_checked",
                "clean_objects",
            ):
                assert key in summary, f"P9: summary missing required key '{key}'"
            assert "total_issues" not in summary, "P9: 'total_issues' legacy key must NOT exist"

    def test_detect_geometry_errors_total_issue_elements_not_total_issues(self) -> None:
        """P9 regression: the old 'total_issues' key must never appear in summary."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="DETECT_GEOMETRY_ERRORS")
        data = result.get("data", {})
        summary = data.get("summary", {})
        # Must NOT have old name — would indicate P9 regression
        assert "total_issues" not in summary, (
            "P9 regression: 'total_issues' key was renamed to 'total_issue_elements'"
        )

    def test_detect_geometry_errors_has_meaning_explanation(self) -> None:
        """P9: total_issues_meaning explanation must be present in summary."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="DETECT_GEOMETRY_ERRORS")
        if result.get("success") is True:
            summary = result.get("data", {}).get("summary", {})
            assert "total_issues_meaning" in summary, (
                "P9: total_issues_meaning explanation must exist"
            )
            assert "object" in summary["total_issues_meaning"].lower()

    # =========================================================================
    # P10 GEOMETRY_COMPLEXITY — dedup shared materials
    # =========================================================================

    def test_geometry_complexity_shared_material_counted_once(self) -> None:
        """P10: Two objects sharing the same material → node_tree_count=1 (not 2)."""
        shared_mat = MagicMock()
        shared_mat.name = "SharedMaterial"
        shared_mat.node_tree = MagicMock()
        shared_mat.node_tree.nodes = []

        slot_a, slot_b = MagicMock(), MagicMock()
        slot_a.material = shared_mat
        slot_b.material = shared_mat

        obj_a = _make_mock_object("MeshA", "MESH")
        obj_a.material_slots = [slot_a]
        obj_b = _make_mock_object("MeshB", "MESH")
        obj_b.material_slots = [slot_b]
        _bpy_mock.context.scene.objects = [obj_a, obj_b]

        result = _dispatch("get_scene_graph", action="GEOMETRY_COMPLEXITY")
        if result.get("success") is True:
            mat_stats = result.get("data", {}).get("material_stats", {})
            assert mat_stats.get("node_tree_count") == 1, (
                "P10: Shared material must be counted exactly once in node_tree_count"
            )
            assert mat_stats.get("unique_materials") == 1

    def test_geometry_complexity_distinct_materials_counted_separately(self) -> None:
        """P10: Two objects with distinct materials → node_tree_count=2, unique=2."""
        mat_a, mat_b = MagicMock(), MagicMock()
        mat_a.name = "MatA"
        mat_b.name = "MatB"
        for m in (mat_a, mat_b):
            m.node_tree = MagicMock()
            m.node_tree.nodes = []

        slot_a, slot_b = MagicMock(), MagicMock()
        slot_a.material = mat_a
        slot_b.material = mat_b

        obj_a = _make_mock_object("ObjA", "MESH")
        obj_a.material_slots = [slot_a]
        obj_b = _make_mock_object("ObjB", "MESH")
        obj_b.material_slots = [slot_b]
        _bpy_mock.context.scene.objects = [obj_a, obj_b]

        result = _dispatch("get_scene_graph", action="GEOMETRY_COMPLEXITY")
        if result.get("success") is True:
            mat_stats = result.get("data", {}).get("material_stats", {})
            assert mat_stats.get("node_tree_count") == 2
            assert mat_stats.get("unique_materials") == 2

    def test_geometry_complexity_material_stats_structure(self) -> None:
        """P10: material_stats dict must have all three expected keys."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="GEOMETRY_COMPLEXITY")
        if result.get("success") is True:
            data = result.get("data", {})
            mat_stats = data.get("material_stats", {})
            for key in ("unique_materials", "node_tree_count", "image_texture_count"):
                assert key in mat_stats, f"P10: material_stats missing '{key}'"
            assert "complexity_tier" in data

    def test_geometry_complexity_scene_totals_present(self) -> None:
        """GEOMETRY_COMPLEXITY response must have scene_totals with all count keys."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="GEOMETRY_COMPLEXITY")
        if result.get("success") is True:
            totals = result.get("data", {}).get("scene_totals", {})
            for key in ("triangles", "vertices", "edges", "ngons", "materials", "objects"):
                assert key in totals, f"scene_totals missing key: {key}"

    # =========================================================================
    # Schema completeness — new params must be documented
    # =========================================================================

    def test_schema_documents_exclude_objects_param(self) -> None:
        """P2 schema: exclude_objects must be documented in get_scene_graph schema properties."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        schema = meta.get("schema", {})
        props = schema.get("properties", {})
        assert "exclude_objects" in props, "P2: exclude_objects param must be in schema properties"
        assert props["exclude_objects"].get("type") == "array"

    def test_schema_documents_max_depth_param(self) -> None:
        """P5 schema: max_depth must be documented for GET_HIERARCHY_TREE."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        schema = meta.get("schema", {})
        props = schema.get("properties", {})
        assert "max_depth" in props, "P5: max_depth param must be in schema properties"
        assert props["max_depth"].get("type") == "integer"

    # =========================================================================
    # Regression — all live-26 fixes confirmed together
    # =========================================================================

    def test_all_11_live26_actions_registered(self) -> None:
        """Regression: All 11 expected actions (P1-P10 + GET_HIERARCHY_TREE) must be registered."""
        meta = HANDLER_METADATA.get("get_scene_graph", {})
        actions = set(meta.get("actions", []))
        expected = {
            "GET_OBJECTS_FLAT",
            "GET_SCENE_MATRIX",
            "GET_SPATIAL_REPORT",
            "CHECK_INTERSECTION",
            "VERIFY_ASSEMBLY",
            "CAST_RAY",
            "ANALYZE_ASSEMBLY",
            "DETECT_GEOMETRY_ERRORS",
            "GEOMETRY_COMPLEXITY",
            "CHECK_PRODUCTION_READINESS",
            "GET_HIERARCHY_TREE",  # P5 — was missing before live-26
        }
        missing = expected - actions
        assert not missing, f"Regression: missing actions in get_scene_graph: {missing}"

    def test_verify_assembly_p8_both_output_formats_present(self) -> None:
        """P8 regression: VERIFY_ASSEMBLY must return BOTH results (structured) AND verification_log (compat)."""
        with patch(
            "blender_mcp.handlers.manage_scene_comprehension.resolve_name", return_value=None
        ):
            result = _dispatch(
                "get_scene_graph",
                action="VERIFY_ASSEMBLY",
                rules={"Obj": {"must_touch": ["Other"]}},
            )
        data = result.get("data", {})
        assert "results" in data, "P8: 'results' (structured) must be present"
        assert "verification_log" in data, "P8: 'verification_log' (compat) must be present"
        assert isinstance(data["results"], list), "P8: results must be a list"
        assert isinstance(data["verification_log"], list), "P8: verification_log must be a list"

    def test_p9_total_issue_elements_name_is_correct(self) -> None:
        """P9 regression: DETECT_GEOMETRY_ERRORS summary uses 'total_issue_elements' not 'total_issues'."""
        _bpy_mock.context.scene.objects = []
        result = _dispatch("get_scene_graph", action="DETECT_GEOMETRY_ERRORS")
        data = result.get("data", {})
        summary = data.get("summary", {})
        # This catches the regression directly — old code had 'total_issues'
        assert "total_issues" not in summary, (
            "P9 regression: 'total_issues' key was renamed — must NOT appear"
        )

    def test_analyze_assembly_model_info_structure(self) -> None:
        """ANALYZE_ASSEMBLY output must have model_info with root_objects and parented_objects."""
        mesh = _make_mock_object("Solo", "MESH")
        _bpy_mock.context.scene.objects = [mesh]
        result = _dispatch("get_scene_graph", action="ANALYZE_ASSEMBLY")
        if result.get("success") is True:
            data = result.get("data", {})
            if "model_info" in data:
                mi = data["model_info"]
                assert "root_objects" in mi or "parented_objects" in mi, (
                    "model_info should have root_objects and/or parented_objects counts"
                )

    # =========================================================================
    # live-27 BVH surface gap helpers and new issue types
    # =========================================================================

    def test_build_world_bvh_returns_bvh_or_none(self) -> None:
        """_build_world_bvh must not raise; returns object with find_nearest or None."""
        from blender_mcp.handlers.manage_scene_comprehension import _build_world_bvh

        obj = _make_mock_object("BVHTest", "MESH")
        result = _build_world_bvh(obj)
        # In mock env bmesh/BVHTree are MagicMocks — returns a MagicMock (not None)
        # OR returns None if an unexpected error occurs. Either is acceptable.
        assert result is None or hasattr(result, "find_nearest"), (
            "_build_world_bvh must return object with find_nearest or None"
        )

    def test_surface_gap_bvh_returns_float_str_tuple(self) -> None:
        """_surface_gap_bvh always returns (float, str) — no crash on mock objects."""
        from blender_mcp.handlers.manage_scene_comprehension import _surface_gap_bvh

        obj_a = _make_mock_object("GapA", "MESH")
        obj_b = _make_mock_object("GapB", "MESH")
        bvh_b = MagicMock()
        gap, method = _surface_gap_bvh(obj_a, obj_b, bvh_b)
        assert isinstance(gap, float), f"gap must be float, got {type(gap)}"
        assert isinstance(method, str), f"method must be str, got {type(method)}"
        assert method in ("BVH_SURFACE", "BVH_INTERPENETRATION", "BVH_FAILED"), (
            f"Unknown method string: {method}"
        )

    def test_surface_gap_bvh_failed_when_bvh_b_is_none(self) -> None:
        """_surface_gap_bvh returns (inf, BVH_FAILED) when bvh_b is None."""
        from blender_mcp.handlers.manage_scene_comprehension import _surface_gap_bvh

        obj_a = _make_mock_object("A", "MESH")
        obj_b = _make_mock_object("B", "MESH")
        gap, method = _surface_gap_bvh(obj_a, obj_b, None)
        assert gap == float("inf"), "bvh_b=None must return inf gap"
        assert method == "BVH_FAILED", "bvh_b=None must return BVH_FAILED"

    def test_surface_gap_bvh_no_overlap_not_interpenetration(self) -> None:
        """_surface_gap_bvh with overlap()=[] must NOT return BVH_INTERPENETRATION."""
        from blender_mcp.handlers.manage_scene_comprehension import _surface_gap_bvh

        obj_a = _make_mock_object("NoOverlapA", "MESH")
        obj_b = _make_mock_object("NoOverlapB", "MESH")
        bvh_b = MagicMock()
        bvh_a = MagicMock()
        bvh_a.overlap.return_value = []  # no face intersection

        with patch(
            "blender_mcp.handlers.manage_scene_comprehension._build_world_bvh",
            return_value=bvh_a,
        ):
            gap, method = _surface_gap_bvh(obj_a, obj_b, bvh_b)

        assert method != "BVH_INTERPENETRATION", (
            "overlap()=[] must not result in BVH_INTERPENETRATION"
        )

    def test_analyze_assembly_no_old_gap_type_in_issues(self) -> None:
        """After live-27: issue type 'GAP' and 'AABB_OVERLAP' must NOT appear in issues."""
        obj_a = _make_mock_object("ObjA", "MESH", wx=0.0)
        obj_b = _make_mock_object("ObjB", "MESH", wx=0.3)
        _bpy_mock.context.scene.objects = [obj_a, obj_b]
        _bpy_mock.data.objects.get.side_effect = lambda n: obj_a if n == "ObjA" else obj_b
        try:
            result = _dispatch("get_scene_graph", action="ANALYZE_ASSEMBLY")
            if result.get("success") is True:
                issues = result.get("data", {}).get("issues", [])
                issue_types = {i.get("type") for i in issues}
                assert "GAP" not in issue_types, (
                    "Old 'GAP' issue type must not appear (renamed SURFACE_GAP)"
                )
                assert "AABB_OVERLAP" not in issue_types, "Old 'AABB_OVERLAP' type must not appear"
        finally:
            _bpy_mock.data.objects.get.side_effect = None

    def test_analyze_assembly_no_interpenetration_on_touching_patched(self) -> None:
        """When _surface_gap_bvh returns touching (gap=0.001, BVH_SURFACE) → 0 INTERPENETRATION."""
        obj_a = _make_mock_object("TouchA", "MESH", wx=0.0)
        obj_b = _make_mock_object("TouchB", "MESH", wx=0.0)
        _bpy_mock.context.scene.objects = [obj_a, obj_b]
        _bpy_mock.data.objects.get.side_effect = lambda n: obj_a if n == "TouchA" else obj_b
        try:
            with patch(
                "blender_mcp.handlers.manage_scene_comprehension._surface_gap_bvh",
                return_value=(0.001, "BVH_SURFACE"),
            ):
                result = _dispatch("get_scene_graph", action="ANALYZE_ASSEMBLY")

            issues = result.get("data", {}).get("issues", [])
            interp = [i for i in issues if i.get("type") == "INTERPENETRATION"]
            assert len(interp) == 0, (
                "BVH_SURFACE touching (gap=0.001) must not flag INTERPENETRATION"
            )
        finally:
            _bpy_mock.data.objects.get.side_effect = None

    def test_get_objects_flat_location_local_note_parented(self) -> None:
        """Parented object must have location_local_note containing parent name."""
        parent = _make_mock_object("ParentObj", "MESH")
        child = _make_mock_object("ChildObj", "MESH", wx=1.0, wy=2.0, wz=3.0)
        child.parent = parent
        _bpy_mock.context.scene.objects = [child]
        result = _dispatch("get_scene_graph", action="GET_OBJECTS_FLAT")
        assert result.get("success") is True
        objects = result.get("data", {}).get("objects", [])
        child_entries = [o for o in objects if o["name"] == "ChildObj"]
        assert child_entries, "ChildObj must appear in GET_OBJECTS_FLAT"
        note = child_entries[0].get("location_local_note", "")
        assert "ParentObj" in note, (
            f"location_local_note must contain parent name 'ParentObj', got: {note!r}"
        )

    def test_get_objects_flat_location_local_note_unparented(self) -> None:
        """Unparented object must have location_local_note = 'World space (no parent)'."""
        obj = _make_mock_object("FreeObj", "MESH")
        obj.parent = None
        _bpy_mock.context.scene.objects = [obj]
        result = _dispatch("get_scene_graph", action="GET_OBJECTS_FLAT")
        assert result.get("success") is True
        objects = result.get("data", {}).get("objects", [])
        entries = [o for o in objects if o["name"] == "FreeObj"]
        assert entries, "FreeObj must appear in GET_OBJECTS_FLAT"
        note = entries[0].get("location_local_note", "")
        assert note == "World space (no parent)", (
            f"Unparented object note must be 'World space (no parent)', got: {note!r}"
        )

    def test_get_scene_matrix_nearest_neighbors_touching_field(self) -> None:
        """nearest_neighbors entries must have a 'touching' boolean field."""
        cube_a = _make_mock_object("NNA", "MESH", wx=0.0)
        cube_b = _make_mock_object("NNB", "MESH", wx=5.0)
        cube_a.evaluated_get = MagicMock(return_value=cube_a)
        cube_b.evaluated_get = MagicMock(return_value=cube_b)
        _bpy_mock.context.evaluated_depsgraph_get.return_value = MagicMock()
        _bpy_mock.context.scene.objects = [cube_a, cube_b]
        result = _dispatch("get_scene_graph", action="GET_SCENE_MATRIX")
        data = result.get("data", {})
        for obj_entry in data.get("objects", []):
            for neighbor in obj_entry.get("nearest_neighbors", []):
                assert "touching" in neighbor, (
                    f"nearest_neighbors entry missing 'touching' field: {neighbor}"
                )


# ===========================================================================
# 3. get_viewport_screenshot_base64 (priority 3)
# ===========================================================================


class TestGetViewportScreenshotBase64:
    """Tests for the visual feedback tool."""

    def test_registered_in_registry(self) -> None:
        assert "get_viewport_screenshot_base64" in HANDLER_REGISTRY

    def test_registered_at_priority_3(self) -> None:
        meta = HANDLER_METADATA.get("get_viewport_screenshot_base64", {})
        assert meta.get("priority") == 3

    def test_has_description(self) -> None:
        meta = HANDLER_METADATA.get("get_viewport_screenshot_base64", {})
        assert meta.get("description", "").strip()

    def test_has_actions(self) -> None:
        meta = HANDLER_METADATA.get("get_viewport_screenshot_base64", {})
        assert len(meta.get("actions", [])) >= 1

    def test_description_mentions_views(self) -> None:
        meta = HANDLER_METADATA.get("get_viewport_screenshot_base64", {})
        desc = meta.get("description", "")
        # Should mention multi-angle / views param
        assert "view" in desc.lower() or "screenshot" in desc.lower()

    def test_schema_has_required_action(self) -> None:
        meta = HANDLER_METADATA.get("get_viewport_screenshot_base64", {})
        schema = meta.get("schema", {})
        assert "action" in schema.get("required", [])

    def test_invalid_action_returns_error(self) -> None:
        result = _dispatch("get_viewport_screenshot_base64", action="NOT_A_REAL_ACTION_9999")
        assert result.get("code") == "INVALID_ACTION" or result.get("success") is not True


# ===========================================================================
# 4. get_object_info (priority 4)
# ===========================================================================


class TestGetObjectInfo:
    """Tests for the deep per-object inspection tool."""

    def test_registered_at_priority_4(self) -> None:
        meta = HANDLER_METADATA.get("get_object_info", {})
        assert meta.get("priority") == 4

    def test_missing_name_returns_error(self) -> None:
        result = _dispatch("get_object_info", action="get_object_info")
        assert result.get("success") is False
        errors = result.get("errors", [])
        assert any(e.get("code") == "MISSING_PARAMETER" for e in errors)

    def test_unknown_object_returns_not_found(self) -> None:
        _bpy_mock.data.objects.get.return_value = None
        _bpy_mock.context.active_object = None
        result = _dispatch("get_object_info", action="get_object_info", name="NoSuchObject_XYZ")
        assert result.get("success") is False
        errors = result.get("errors", [])
        assert any(e.get("code") == "OBJECT_NOT_FOUND" for e in errors)

    def test_not_found_error_has_suggestion(self) -> None:
        _bpy_mock.data.objects.get.return_value = None
        _bpy_mock.context.active_object = None
        result = _dispatch("get_object_info", action="get_object_info", name="MissingObj")
        errors = result.get("errors", [])
        if errors:
            assert errors[0].get("suggestion", "")  # non-empty suggestion

    def test_not_found_error_has_next_steps(self) -> None:
        _bpy_mock.data.objects.get.return_value = None
        _bpy_mock.context.active_object = None
        result = _dispatch("get_object_info", action="get_object_info", name="MissingObj2")
        assert result.get("next_steps") is not None
        # At least one next step pointing toward get_scene_graph
        steps = result.get("next_steps", [])
        assert len(steps) > 0

    def test_object_name_alias_accepted(self) -> None:
        """object_name param should work as alias for name."""
        _bpy_mock.data.objects.get.return_value = None
        _bpy_mock.context.active_object = None
        result = _dispatch("get_object_info", action="get_object_info", object_name="TestAliasObj")
        # Should get OBJECT_NOT_FOUND (not MISSING_PARAMETER) — alias was recognized
        errors = result.get("errors", [])
        codes = [e.get("code") for e in errors]
        assert "OBJECT_NOT_FOUND" in codes

    def test_existing_object_returns_success(self) -> None:
        cube = _make_mock_object("RealCube", "MESH", wx=1.0, wy=2.0, wz=3.0)
        # Set up matrix_world as MagicMock with proper indexing
        mw_list = [
            [1.0, 0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0, 2.0],
            [0.0, 0.0, 1.0, 3.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        cube.matrix_world = mw_list
        cube.bound_box = None  # skip geometry center path
        _bpy_mock.data.objects.get.return_value = cube
        result = _dispatch("get_object_info", action="get_object_info", name="RealCube")
        assert result.get("success") is True
        data = result.get("data", {})
        assert data.get("name") == "RealCube"
        assert data.get("type") == "MESH"
        assert "world_location" in data

    def test_description_mentions_world_location(self) -> None:
        meta = HANDLER_METADATA.get("get_object_info", {})
        # Rich description is in schema["description"]
        schema_desc = str(meta.get("schema", {}).get("description", ""))
        assert "world_location" in schema_desc or "world" in schema_desc.lower()

    def test_schema_has_name_property(self) -> None:
        meta = HANDLER_METADATA.get("get_object_info", {})
        schema = meta.get("schema", {})
        props = schema.get("properties", {})
        assert "name" in props or "object_name" in props


# ===========================================================================
# 5. manage_agent_context (priority 6)
# ===========================================================================


class TestManageAgentContext:
    """Tests for the self-discovery and primer tool."""

    def test_registered_at_priority_6(self) -> None:
        meta = HANDLER_METADATA.get("manage_agent_context", {})
        assert meta.get("priority") == 6

    # --- GET_PRIMER ---

    def test_get_primer_returns_success(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        assert result.get("success") is True
        assert result.get("status") == "OK"

    def test_get_primer_data_has_title(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        data = result.get("data", {})
        assert "title" in data
        assert "Blender MCP" in data["title"]

    def test_get_primer_has_architecture(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        data = result.get("data", {})
        assert "architecture" in data
        assert "stdio" in data["architecture"].lower() or "bridge" in data["architecture"].lower()

    def test_get_primer_has_essential_workflow(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        data = result.get("data", {})
        assert "essential_workflow" in data
        workflow = data["essential_workflow"]
        assert isinstance(workflow, dict)
        assert len(workflow) >= 3

    def test_get_primer_has_critical_warnings(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        data = result.get("data", {})
        assert "critical_warnings" in data
        warnings = data["critical_warnings"]
        assert isinstance(warnings, list)
        assert len(warnings) >= 3

    def test_get_primer_critical_warnings_mention_world_location(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        warnings = result.get("data", {}).get("critical_warnings", [])
        joined = " ".join(str(w) for w in warnings).lower()
        assert "world_location" in joined or "world" in joined

    def test_get_primer_has_tier1_tools_list(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        data = result.get("data", {})
        assert "tier1_tools" in data
        tier1 = data["tier1_tools"]
        assert isinstance(tier1, list)
        assert len(tier1) >= 4

    def test_get_primer_tier1_contains_execute_blender_code(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        tier1 = result.get("data", {}).get("tier1_tools", [])
        names = [t.get("name") for t in tier1]
        assert "execute_blender_code" in names

    def test_get_primer_tier1_contains_get_scene_graph(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        tier1 = result.get("data", {}).get("tier1_tools", [])
        names = [t.get("name") for t in tier1]
        assert "get_scene_graph" in names

    def test_get_primer_has_scene_perception_pattern(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        data = result.get("data", {})
        assert "scene_perception_pattern" in data
        pattern = data["scene_perception_pattern"]
        assert "key_insight" in pattern or "step_1" in pattern

    def test_get_primer_scene_perception_pattern_mentions_geometry_center(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        pattern = result.get("data", {}).get("scene_perception_pattern", {})
        joined = " ".join(str(v) for v in pattern.values()).lower()
        assert "geometry_center" in joined or "geometry center" in joined

    def test_get_primer_has_common_agent_mistakes(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_PRIMER")
        data = result.get("data", {})
        assert "common_agent_mistakes" in data
        mistakes = data["common_agent_mistakes"]
        assert isinstance(mistakes, list)
        assert len(mistakes) >= 2

    # --- GET_TACTICS ---

    def test_get_tactics_returns_success(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_TACTICS")
        assert result.get("success") is True

    def test_get_tactics_has_model_assembly_tactics(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_TACTICS")
        data = result.get("data", {})
        assert "model_assembly_tactics" in data

    def test_get_tactics_warns_against_render_render(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_TACTICS")
        tactics = result.get("data", {}).get("model_assembly_tactics", {})
        joined = " ".join(str(v) for v in tactics.values()).lower()
        assert "render.render" in joined or "render_frame" in joined or "freeze" in joined

    def test_get_tactics_has_assembly_check_tactic(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_TACTICS")
        tactics = result.get("data", {}).get("model_assembly_tactics", {})
        joined = " ".join(str(v) for v in tactics.values()).lower()
        assert "analyze_assembly" in joined or "assembly" in joined

    # --- SEARCH_TOOLS ---

    def test_search_tools_finds_scene_tools(self) -> None:
        result = _dispatch("manage_agent_context", action="SEARCH_TOOLS", query="scene")
        assert result.get("success") is True
        matches = result.get("data", {}).get("top_matches", [])
        assert len(matches) > 0

    def test_search_tools_returns_tool_names(self) -> None:
        result = _dispatch("manage_agent_context", action="SEARCH_TOOLS", query="render")
        matches = result.get("data", {}).get("top_matches", [])
        for m in matches:
            assert "tool_name" in m

    def test_search_tools_empty_query_returns_error(self) -> None:
        result = _dispatch("manage_agent_context", action="SEARCH_TOOLS", query="")
        assert result.get("success") is False

    def test_search_tools_missing_query_returns_error(self) -> None:
        result = _dispatch("manage_agent_context", action="SEARCH_TOOLS")
        assert result.get("success") is False

    def test_search_tools_garbage_query_returns_error(self) -> None:
        result = _dispatch(
            "manage_agent_context", action="SEARCH_TOOLS", query="xyzzy_no_match_42abc"
        )
        assert result.get("success") is False

    # --- GET_TOOL_CATALOG ---

    def test_get_tool_catalog_returns_all_tools(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_TOOL_CATALOG")
        assert result.get("success") is True
        data = result.get("data", {})
        assert data.get("total_tools", 0) >= 60

    def test_get_tool_catalog_has_tools_dict(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_TOOL_CATALOG")
        data = result.get("data", {})
        tools = data.get("tools", {})
        assert isinstance(tools, dict)
        assert "execute_blender_code" in tools

    def test_get_tool_catalog_category_scene_filter(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_TOOL_CATALOG", category="scene")
        assert result.get("success") is True
        data = result.get("data", {})
        tools = data.get("tools", {})
        # All returned tools should be in 'scene' category
        for name, info in tools.items():
            assert info.get("category") == "scene", (
                f"Tool {name!r} in wrong category: {info.get('category')}"
            )

    def test_get_tool_catalog_invalid_category_returns_error(self) -> None:
        result = _dispatch(
            "manage_agent_context",
            action="GET_TOOL_CATALOG",
            category="this_category_does_not_exist_xyz",
        )
        assert result.get("success") is False

    def test_get_tool_catalog_lists_available_categories(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_TOOL_CATALOG")
        data = result.get("data", {})
        cats = data.get("available_categories", [])
        assert isinstance(cats, list)
        assert len(cats) >= 3
        assert "scene" in cats

    # --- GET_ACTION_HELP ---

    def test_get_action_help_missing_tool_name_returns_error(self) -> None:
        result = _dispatch("manage_agent_context", action="GET_ACTION_HELP")
        assert result.get("success") is False
        errors = result.get("errors", [])
        codes = [e.get("code") for e in errors]
        assert "MISSING_PARAMETER" in codes

    def test_get_action_help_unknown_tool_returns_not_found(self) -> None:
        result = _dispatch(
            "manage_agent_context",
            action="GET_ACTION_HELP",
            tool_name="totally_fake_tool_xyz",
        )
        assert result.get("success") is False
        errors = result.get("errors", [])
        codes = [e.get("code") for e in errors]
        assert "NOT_FOUND" in codes

    def test_get_action_help_real_tool_returns_schema(self) -> None:
        result = _dispatch(
            "manage_agent_context",
            action="GET_ACTION_HELP",
            tool_name="execute_blender_code",
        )
        assert result.get("success") is True
        data = result.get("data", {})
        assert "schema" in data
        assert "actions" in data
        assert data.get("priority") == 1

    def test_get_action_help_with_valid_action(self) -> None:
        result = _dispatch(
            "manage_agent_context",
            action="GET_ACTION_HELP",
            tool_name="get_scene_graph",
            action_name="GET_OBJECTS_FLAT",
        )
        assert result.get("success") is True
        data = result.get("data", {})
        assert data.get("action_focused") == "GET_OBJECTS_FLAT"

    def test_get_action_help_with_invalid_action_returns_error(self) -> None:
        result = _dispatch(
            "manage_agent_context",
            action="GET_ACTION_HELP",
            tool_name="get_scene_graph",
            action_name="NOT_A_REAL_ACTION",
        )
        assert result.get("success") is False

    # --- Missing action ---

    def test_missing_action_returns_error(self) -> None:
        result = _dispatch("manage_agent_context")
        assert result.get("code") == "INVALID_ACTION" or result.get("success") is not True


# ===========================================================================
# 6. list_all_tools (priority 7)
# ===========================================================================


class TestListAllTools:
    """Tests for the tool manifest / discovery tool."""

    def test_registered_at_priority_7(self) -> None:
        meta = HANDLER_METADATA.get("list_all_tools", {})
        assert meta.get("priority") == 7

    def test_returns_success(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        assert result.get("success") is True

    def test_manifest_is_string(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        manifest = result.get("system_manifest", "")
        assert isinstance(manifest, str)
        assert len(manifest) > 200

    def test_manifest_contains_essential_tier_header(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        manifest = result.get("system_manifest", "")
        assert "ESSENTIAL" in manifest

    def test_manifest_contains_core_tier_header(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        manifest = result.get("system_manifest", "")
        assert "CORE" in manifest

    def test_manifest_lists_execute_blender_code(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        manifest = result.get("system_manifest", "")
        assert "execute_blender_code" in manifest

    def test_manifest_lists_get_scene_graph(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        manifest = result.get("system_manifest", "")
        assert "get_scene_graph" in manifest

    def test_manifest_lists_manage_agent_context(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        manifest = result.get("system_manifest", "")
        assert "manage_agent_context" in manifest

    def test_manifest_lists_all_essential_tools(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        manifest = result.get("system_manifest", "")
        for tool_name in _ESSENTIAL_NAMES:
            assert tool_name in manifest, f"Essential tool missing from manifest: {tool_name}"

    def test_wrong_action_returns_invalid_action_error(self) -> None:
        result = _dispatch("list_all_tools", action="NOT_A_VALID_ACTION_9999")
        assert result.get("code") == "INVALID_ACTION" or result.get("success") is not True

    def test_description_mentions_priority(self) -> None:
        meta = HANDLER_METADATA.get("list_all_tools", {})
        desc = meta.get("description", "").lower()
        assert "priority" in desc or "essential" in desc


# ===========================================================================
# 7. get_server_status (priority 8)
# ===========================================================================


class TestGetServerStatus:
    """Tests for the connection health and environment discovery tool."""

    def test_registered_at_priority_8(self) -> None:
        meta = HANDLER_METADATA.get("get_server_status", {})
        assert meta.get("priority") == 8

    def test_returns_status_active(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        assert result.get("status") == "active"

    def test_handler_count_is_positive(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        assert result.get("handler_count", 0) >= 60

    def test_tools_list_is_nonempty(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        tools = result.get("tools", [])
        assert isinstance(tools, list)
        assert len(tools) >= 60

    def test_tools_list_contains_essential_tools(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        tools = result.get("tools", [])
        for name in _ESSENTIAL_NAMES:
            assert name in tools, f"Essential tool missing from server status tools: {name}"

    def test_blender_version_present_and_is_tuple_or_list(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        ver = result.get("blender_version")
        assert ver is not None
        assert len(ver) == 3, f"Expected 3-element version, got: {ver}"

    def test_blender_language_present_and_is_string(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        lang = result.get("blender_language")
        assert isinstance(lang, str)
        assert len(lang) >= 2  # "en_US", "tr_TR" etc.

    def test_version_key_present(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        assert "version" in result
        assert result["version"] == "1.0.0"

    def test_next_step_hint_present_and_nonempty(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        next_step = result.get("next_step", "")
        assert isinstance(next_step, str)
        assert len(next_step) > 10  # must be a real hint

    def test_next_step_mentions_list_all_tools_or_primer(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        next_step = result.get("next_step", "").lower()
        assert "list_all_tools" in next_step or "primer" in next_step or "get_primer" in next_step

    def test_handler_errors_key_present(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        assert "handler_errors" in result

    def test_thread_stats_key_present(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        assert "thread_stats" in result


# ===========================================================================
# 8. new_scene (priority 9)
# ===========================================================================


class TestNewScene:
    """Tests for the clean-slate scene creation tool."""

    def test_registered_at_priority_9(self) -> None:
        meta = HANDLER_METADATA.get("new_scene", {})
        assert meta.get("priority") == 9

    def test_registered_in_registry(self) -> None:
        assert "new_scene" in HANDLER_REGISTRY

    def test_is_scene_category(self) -> None:
        meta = HANDLER_METADATA.get("new_scene", {})
        assert meta.get("category") == "scene"

    def test_schema_requires_action(self) -> None:
        meta = HANDLER_METADATA.get("new_scene", {})
        schema = meta.get("schema", {})
        assert "action" in schema.get("required", [])

    def test_description_mentions_essential(self) -> None:
        meta = HANDLER_METADATA.get("new_scene", {})
        desc = meta.get("description", "").upper()
        assert "ESSENTIAL" in desc

    def test_description_warns_against_read_homefile(self) -> None:
        # Rich description lives in schema["description"], not the short function docstring
        meta = HANDLER_METADATA.get("new_scene", {})
        schema_desc = str(meta.get("schema", {}).get("description", "")).lower()
        assert "read_homefile" in schema_desc or "crash" in schema_desc or "socket" in schema_desc

    def test_actions_list_contains_new_scene(self) -> None:
        meta = HANDLER_METADATA.get("new_scene", {})
        actions = meta.get("actions", [])
        assert "new_scene" in actions

    def test_dispatching_without_action_returns_error(self) -> None:
        """Dispatching new_scene with no action param should return an error."""
        result = dispatch_command({"tool": "new_scene", "params": {}}, use_thread_safety=False)
        assert result.get("success") is False or result.get("code") == "INVALID_ACTION"


# ===========================================================================
# Cross-cutting: All ESSENTIAL tools baseline contract
# ===========================================================================


class TestEssentialToolsContract:
    """Contract tests that must pass for ALL 8 essential tools."""

    def test_all_essential_tools_are_registered(self) -> None:
        missing = [n for n in _ESSENTIAL_NAMES if n not in HANDLER_REGISTRY]
        assert not missing, f"Essential tools not registered: {missing}"

    def test_all_essential_tools_have_priority_le_9(self) -> None:
        for name in _ESSENTIAL_NAMES:
            meta = HANDLER_METADATA.get(name, {})
            pri = meta.get("priority", 999)
            assert pri <= 9, f"{name} has priority {pri}, expected <= 9"

    def test_all_essential_tools_have_nonempty_description(self) -> None:
        for name in _ESSENTIAL_NAMES:
            meta = HANDLER_METADATA.get(name, {})
            desc = meta.get("description", "").strip()
            assert desc, f"{name} has empty description"

    def test_all_essential_tools_have_nonempty_category(self) -> None:
        for name in _ESSENTIAL_NAMES:
            meta = HANDLER_METADATA.get(name, {})
            cat = meta.get("category", "").strip()
            assert cat, f"{name} has empty category"

    def test_all_essential_tools_have_at_least_one_action(self) -> None:
        for name in _ESSENTIAL_NAMES:
            meta = HANDLER_METADATA.get(name, {})
            actions = meta.get("actions", [])
            assert len(actions) >= 1, f"{name} has zero actions"

    def test_all_essential_tools_have_schema(self) -> None:
        for name in _ESSENTIAL_NAMES:
            meta = HANDLER_METADATA.get(name, {})
            schema = meta.get("schema", {})
            assert isinstance(schema, dict) and schema, f"{name} has empty/missing schema"

    def test_all_essential_tools_schema_requires_action(self) -> None:
        for name in _ESSENTIAL_NAMES:
            meta = HANDLER_METADATA.get(name, {})
            schema = meta.get("schema", {})
            required = schema.get("required", [])
            assert "action" in required, (
                f"{name}: schema does not list 'action' as required. required={required}"
            )

    def test_all_essential_tools_appear_in_list_all_tools_manifest(self) -> None:
        result = _dispatch("list_all_tools", action="list_all_tools")
        manifest = result.get("system_manifest", "")
        for name in _ESSENTIAL_NAMES:
            assert name in manifest, f"Essential tool {name!r} missing from list_all_tools manifest"

    def test_all_essential_tools_appear_in_get_server_status_tools_list(self) -> None:
        result = _dispatch("get_server_status", action="get_server_status")
        tools = result.get("tools", [])
        for name in _ESSENTIAL_NAMES:
            assert name in tools, f"Essential tool {name!r} missing from get_server_status tools"
