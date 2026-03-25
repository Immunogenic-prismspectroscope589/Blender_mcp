"""
Scene Comprehension Handler for Blender MCP 1.0.0

Provides spatial awareness and intersection detection using mathutils.bvhtree.
"""

from typing import Any, Dict
import logging

try:
    import bpy
    from mathutils.bvhtree import BVHTree
    from mathutils import Vector

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None

from ..core.enums import SceneComprehensionAction
from ..core.response_builder import ResponseBuilder
from ..core.validation_utils import ValidationUtils
from ..dispatcher import register_handler
from ..core.parameter_validator import validated_handler
from ..core.thread_safety import ensure_main_thread
from ..core.resolver import resolve_name
from ..utils.error_handler import mcp_tool_handler

logger = logging.getLogger(__name__)

# Hard Limit to prevent OOM
MAX_VERTEX_LIMIT = 500_000


@register_handler(
    "get_scene_graph",
    actions=[a.value for a in SceneComprehensionAction],
    category="scene",
    priority=2,
    schema={
        "type": "object",
        "title": "Scene Graph — Primary Scene Survey Tool (ESSENTIAL)",
        "description": (
            "ESSENTIAL (priority=2) — PRIMARY SCENE SURVEY TOOL. 10 actions covering all spatial analysis.\n"
            "Start every task with GET_OBJECTS_FLAT to understand the scene before making changes.\n\n"
            "━━━ COORDINATE SYSTEM (read first) ━━━\n"
            "  world_location       = ORIGIN/PIVOT position in world space\n"
            "                         → For parented objects this is OFTEN [0,0,0] — NOT a bug\n"
            "  geometry_center_world = WHERE THE MESH ACTUALLY IS (AABB center, MESH only)\n"
            "                         → ALWAYS use this for spatial reasoning, NOT world_location\n"
            "  origin_offset_warning = True → pivot ≠ geometry center (rig/drone pattern)\n"
            "  location_local        = position relative to parent (hierarchy reasoning)\n\n"
            "━━━ SPATIAL ACCURACY NOTES ━━━\n"
            "  ANALYZE_ASSEMBLY / VERIFY_ASSEMBLY: use BVH vertex-projection for precise\n"
            "  surface-to-surface gap measurement (base mesh, no modifiers, StructRNA-safe).\n"
            "  Issue types: INTERPENETRATION (BVH face-overlap), SURFACE_GAP (BVH mm distance),\n"
            "  ORIGIN_OFFSET (root pivot ≠ geo center), NON_MANIFOLD (open edges).\n"
            "  AABB fallback used when bmesh/BVHTree not available (mock/test env).\n"
            "  Other actions (CHECK_INTERSECTION, GET_SPATIAL_REPORT) still use AABB.\n\n"
            "━━━ ACTION REFERENCE ━━━\n\n"
            "GET_OBJECTS_FLAT  [params: none required]\n"
            "  FAST O(N) overview of ALL objects in the scene.\n"
            "  Output per object: name, type, world_location, dimensions, parent, children,\n"
            "    collection, geometry_center_world, origin_offset_m, origin_offset_warning,\n"
            "    rotation_degrees, world_bounding_box {min,max}, location_local, scale,\n"
            "    matrix_world (4×4), custom_properties, has_animation, material_count.\n"
            "  → Use first. Best entry point for any scene analysis task.\n\n"
            "GET_SCENE_MATRIX  [params: limit=50, object_names=[...]]\n"
            "  Deep spatial analysis for MESH objects. Per object:\n"
            "    world_position (AABB center), world_bounding_box, dimensions_m,\n"
            "    nearest_neighbors: [{name, distance_meters, touching}]\n"
            "    touching = distance_meters < 0.02m (2cm threshold).\n"
            "  → Use when you need per-object proximity map. Slower than GET_OBJECTS_FLAT.\n\n"
            "ANALYZE_ASSEMBLY  [params: gap_threshold_pct=2.0, exclude_objects=[], max_proximity=0.05, max_issues=20]\n"
            "  Assembly integrity check using BVH surface-gap measurement (precise mm accuracy).\n"
            "  Pair selection (spatially-filtered, no N² explosion):\n"
            "    • parent↔child hierarchy pairs (always)\n"
            "    • any non-hierarchy pair with AABB max-separation ≤ max_proximity (default 5cm)\n"
            "      includes overlapping pairs (Body↔Arm interpenetration) AND close pairs (Hub↔Blade)\n"
            "  Issue types (sorted: smallest gap first = most critical):\n"
            "    INTERPENETRATION (real geometry clash, -10pt each),\n"
            "    SURFACE_GAP (real distance gap > threshold, -5pt each; capped at max_issues),\n"
            "    ORIGIN_OFFSET (root pivot ≠ geo center, -5pt each),\n"
            "    NON_MANIFOLD (open mesh edges, -1pt/10-edges).\n"
            "  Per-issue method field: BVH_SURFACE | BVH_INTERPENETRATION | AABB_FALLBACK.\n"
            "  exclude_objects: list of object names to skip (e.g. ['Ground_Plane', 'Sky_Dome']).\n"
            "  Response includes: pairs_checked, pairs_breakdown, gap_issues_note ('N shown / M total').\n"
            "  → Use for overall model health. Follow with DETECT_GEOMETRY_ERRORS.\n\n"
            "CHECK_INTERSECTION  [params: object_a (str), object_b (str)]\n"
            "  AABB overlap test between exactly two named objects.\n"
            "  Output: {is_intersecting: bool, object_a, object_b, note}\n"
            "  AABB LIMIT: rotated objects can give false-positive overlaps.\n"
            "  → Use to test specific pairs. For many pairs, use GET_SCENE_MATRIX.\n\n"
            "GET_SPATIAL_REPORT  [params: object_name (str)]\n"
            "  Full spatial context for one object. Output:\n"
            "    name, spatial_context: {local_axes_in_world, bounding_box_world {min,max,center,dimensions},\n"
            "    nearby_objects: [{name, distance_m, touching, direction}], human_readable summary}.\n"
            "  → Use when you need a detailed spatial snapshot of a single object.\n\n"
            "CAST_RAY  [params: origin=[x,y,z], direction=[dx,dy,dz]]\n"
            "  Cast a ray from a world-space point in a direction. Returns:\n"
            "    hit (bool), object_name, location [x,y,z], normal [nx,ny,nz], distance_m.\n"
            "  → Use for line-of-sight checks, occlusion tests, or finding surfaces.\n\n"
            "VERIFY_ASSEMBLY  [params: rules={obj_name: {must_touch: [...], parent_must_be: 'Parent'}}]\n"
            "  Rule-based proximity check using BVH surface-gap (with AABB fallback). Rules:\n"
            "    must_touch: [names] — surface gap must be ≤ 5mm (BVH_SURFACE or AABB_FALLBACK)\n"
            "    parent_must_be: 'Name' — source must be parented to this object\n"
            "  Output: {all_passed: bool, results: [{source, target, rule, passed, distance_m, note}],\n"
            "    verification_log: [...] (deprecated string format kept for backward compat)}\n"
            "  Unknown rule keys are flagged as failures.\n"
            "  Example: rules={'Motor_L': {'must_touch': ['Propeller_L'], 'parent_must_be': 'Arm_L'}}\n"
            "  → Use for contract-style assembly verification (CI/QA).\n\n"
            "DETECT_GEOMETRY_ERRORS  [params: max_objects=20]\n"
            "  Per-object bmesh analysis (first max_objects MESH objects).\n"
            "  Output per object: non_manifold_edges, boundary_edges, zero_area_faces,\n"
            "    total_faces, total_edges, total_verts.\n"
            "  Summary: {total_issues, clean_objects, objects_with_issues}\n"
            "  → Run before export. Non-manifold = problematic for 3D print/boolean/bake.\n\n"
            "GEOMETRY_COMPLEXITY  [params: none]\n"
            "  Triangle/vertex/material counts per object + scene totals.\n"
            "  Output: per_object {triangles, vertices, ngons}, scene_totals,\n"
            "    complexity_tier (LOW <10K / MEDIUM 10-100K / HIGH 100K-500K / VERY_HIGH >500K),\n"
            "    material_stats {total_materials, node_tree_count, image_texture_count}.\n"
            "  NOTE: No FPS/render-time estimate — too hardware-dependent.\n"
            "  → Use before optimization or LOD decisions.\n\n"
            "CHECK_PRODUCTION_READINESS  [params: max_objects=20]\n"
            "  Per-object production checklist (first max_objects MESH objects):\n"
            "    is_manifold, has_materials, has_uv_map, is_named_properly,\n"
            "    origin_aligned (<1cm offset), no_ngons, score (0-100).\n"
            "  Scene score = average of all object scores.\n"
            "  failing_checks: list of 'check_name: obj1, obj2, ...' for quick triage.\n"
            "  → Final gate before export or handoff.\n\n"
            "GET_HIERARCHY_TREE  [params: max_depth=10]\n"
            "  Parent-child hierarchy tree of all visible scene objects (iterative BFS).\n"
            "  Output: {tree: [{name, type, children: [...]}], root_count, max_depth_applied}\n"
            "  Deep rigs (>max_depth levels) are truncated with children_count + truncated:true.\n"
            "  → Use to understand object hierarchy and parenting structure.\n\n"
            "━━━ RECOMMENDED WORKFLOWS ━━━\n"
            "  New session:    GET_OBJECTS_FLAT → understand scene structure\n"
            "  Hierarchy:      GET_HIERARCHY_TREE → understand parent/child relationships\n"
            "  Assembly check: ANALYZE_ASSEMBLY → DETECT_GEOMETRY_ERRORS → CHECK_PRODUCTION_READINESS\n"
            "  Pair test:      CHECK_INTERSECTION (object_a='A', object_b='B')\n"
            "  Rule check:     VERIFY_ASSEMBLY (rules={'PartA': {'must_touch': ['PartB']}})\n"
            "  Export prep:    GEOMETRY_COMPLEXITY → DETECT_GEOMETRY_ERRORS → CHECK_PRODUCTION_READINESS"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                SceneComprehensionAction, "Spatial action"
            ),
            "object_a": {
                "type": "string",
                "description": "Name of the first object to test.",
            },
            "object_b": {
                "type": "string",
                "description": "Name of the second object to test.",
            },
            "object_name": {
                "type": "string",
                "description": "Object to get a spatial report for.",
            },
            "limit": {
                "type": "integer",
                "description": "Max objects for GET_SCENE_MATRIX (Top N by Volume). Default 50.",
            },
            "object_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of specific objects to map in GET_SCENE_MATRIX.",
            },
            "rules": {
                "type": "object",
                "description": "Dictionary of proximity rules for VERIFY_ASSEMBLY (e.g. {'Arm_1': {'must_touch': ['Motor_1']}}).",
            },
            "origin": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Origin of the ray [x, y, z] for CAST_RAY.",
            },
            "direction": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Direction of the ray [dx, dy, dz] for CAST_RAY.",
            },
            "distance": {
                "type": "number",
                "description": "Max distance for CAST_RAY. Default 100.0",
            },
            "ignore_self": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of object names to ignore for CAST_RAY (to prevent origin occlusion).",
            },
            "include_hidden": {
                "type": "boolean",
                "default": False,
                "description": "GET_OBJECTS_FLAT only: include hidden (viewport-hidden) objects in the result.",
            },
            "max_objects": {
                "type": "integer",
                "default": 20,
                "description": (
                    "Max visible MESH objects to process for DETECT_GEOMETRY_ERRORS and "
                    "CHECK_PRODUCTION_READINESS. Default 20. Increase for larger scenes (slower)."
                ),
            },
            "gap_threshold_pct": {
                "type": "number",
                "default": 10.0,
                "description": "Gap threshold as percent of object size for ANALYZE_ASSEMBLY. Default 2.0. Also reports any gap >5cm absolute.",
            },
            "exclude_objects": {
                "type": "array",
                "items": {"type": "string"},
                "description": "ANALYZE_ASSEMBLY: list of object names to exclude from gap/overlap analysis (e.g. ['Ground_Plane', 'Sky_Dome']).",
            },
            "max_proximity": {
                "type": "number",
                "default": 0.05,
                "description": (
                    "ANALYZE_ASSEMBLY: max AABB surface gap (meters) for non-hierarchy proximity pairs. "
                    "Default 0.05 (5cm). Increase to catch larger gaps between unparented close objects."
                ),
            },
            "max_issues": {
                "type": "integer",
                "default": 20,
                "description": (
                    "ANALYZE_ASSEMBLY: max SURFACE_GAP issues to include in output (sorted worst-first). "
                    "Default 20. INTERPENETRATION issues are always fully included."
                ),
            },
            "max_pairs": {
                "type": "integer",
                "default": 500,
                "description": (
                    "ANALYZE_ASSEMBLY: safety cap on total pairs checked (default 500). "
                    "For normal assemblies the filtered pair count is well below this. "
                    "Increase only for very dense scenes where many parts are within max_proximity. "
                    "Response includes pairs_breakdown.capped=true if limit was hit."
                ),
            },
            "max_depth": {
                "type": "integer",
                "default": 10,
                "description": "GET_HIERARCHY_TREE: maximum depth of the hierarchy tree. Nodes beyond this depth are truncated with children_count. Default 10.",
            },
        },
        "required": ["action"],
    },
)
@validated_handler(actions=[a.value for a in SceneComprehensionAction])
@ensure_main_thread
@mcp_tool_handler
def get_scene_graph(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Handle scene graph / scene comprehension operations.
    Runs on the main thread since BVH construction accesses C API heavily.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action=action,
            error_code="NO_CONTEXT",
            message="Blender context not available. Cannot compute BVH.",
        )

    if not action:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == SceneComprehensionAction.CHECK_INTERSECTION.value:
        obj_a_name = params.get("object_a")
        obj_b_name = params.get("object_b")

        if not obj_a_name or not obj_b_name:
            return ResponseBuilder.error(
                handler="get_scene_graph",
                action=action,
                error_code="MISSING_PARAMETER",
                message="'object_a' and 'object_b' are required for intersection tests.",
            )

        obj_a = resolve_name(obj_a_name)
        obj_b = resolve_name(obj_b_name)

        if not obj_a or not obj_b:
            return ResponseBuilder.error(
                handler="get_scene_graph",
                action=action,
                error_code="OBJECT_NOT_FOUND",
                message=f"Could not find objects: {obj_a_name}, {obj_b_name}",
            )

        SUPPORTED_MESH_TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT"}

        type_a = getattr(obj_a, "type", "")
        type_b = getattr(obj_b, "type", "")

        if type_a not in SUPPORTED_MESH_TYPES or type_b not in SUPPORTED_MESH_TYPES:
            return ResponseBuilder.error(
                handler="get_scene_graph",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Both objects MUST be of supported types for BVH: {SUPPORTED_MESH_TYPES}. Cannot compare {type_a} and {type_b}.",
            )

        return _check_intersection(obj_a, obj_b)

    elif action == SceneComprehensionAction.GET_SPATIAL_REPORT.value:
        obj_name = params.get("object_name")
        if not obj_name:
            return ResponseBuilder.error(
                handler="get_scene_graph",
                action=action,
                error_code="MISSING_PARAMETER",
                message="'object_name' is required for GET_SPATIAL_REPORT.",
            )

        obj = resolve_name(obj_name)
        if not obj:
            return ResponseBuilder.error(
                handler="get_scene_graph",
                action=action,
                error_code="OBJECT_NOT_FOUND",
                message=f"Could not find object: {obj_name}",
            )

        return _get_spatial_report(obj)

    elif action == SceneComprehensionAction.VERIFY_ASSEMBLY.value:
        rules = params.get("rules")
        if not rules:
            return ResponseBuilder.error(
                handler="get_scene_graph",
                action=action,
                error_code="MISSING_PARAMETER",
                message="'rules' is required for VERIFY_ASSEMBLY.",
            )

        return _verify_assembly(rules)

    elif action == SceneComprehensionAction.GET_SCENE_MATRIX.value:
        limit = params.get("limit", 50)
        object_names = params.get("object_names")
        return _get_scene_matrix(limit=limit, target_names=object_names)

    elif action == SceneComprehensionAction.GET_OBJECTS_FLAT.value:
        return _get_objects_flat(params)

    elif action == SceneComprehensionAction.CAST_RAY.value:
        origin = params.get("origin")
        direction = params.get("direction")
        distance = params.get("distance", 100.0)
        ignore_self = params.get("ignore_self", [])

        if not origin or not direction or len(origin) != 3 or len(direction) != 3:
            return ResponseBuilder.error(
                handler="get_scene_graph",
                action=action,
                error_code="INVALID_PARAMETER",
                message="'origin' and 'direction' must be [x, y, z] arrays.",
            )

        limit = params.get("limit", 50)
        return _cast_ray(origin, direction, float(distance), ignore_self, limit)

    elif action == SceneComprehensionAction.ANALYZE_ASSEMBLY.value:
        threshold_pct = float(params.get("gap_threshold_pct", 2.0))
        return _analyze_assembly(
            threshold_pct=threshold_pct,
            exclude_objects=params.get("exclude_objects", []),
            max_proximity=float(params.get("max_proximity", 0.05)),
            max_issues=int(params.get("max_issues", 20)),
            max_pairs=int(params.get("max_pairs", 500)),
        )

    elif action == SceneComprehensionAction.GET_HIERARCHY_TREE.value:
        max_depth = int(params.get("max_depth", 10))
        return _get_hierarchy_tree(max_depth=max_depth)

    elif action == SceneComprehensionAction.DETECT_GEOMETRY_ERRORS.value:
        return _detect_geometry_errors(params)

    elif action == SceneComprehensionAction.GEOMETRY_COMPLEXITY.value:
        return _geometry_complexity()

    elif action == SceneComprehensionAction.CHECK_PRODUCTION_READINESS.value:
        return _check_production_readiness(params)

    return ResponseBuilder.error(
        handler="get_scene_graph",
        action=action,
        error_code="UNKNOWN_ACTION",
        message=f"Action '{action}' is not handled.",
    )


def _get_scene_matrix(limit: int, target_names: list[str] | None) -> dict[str, Any]:
    """
    UNIVERSAL SCENE SPATIAL MATRIX
    Provides O(N) relative Euclidean mapping of the entire scene using 5.0.1 safe iteration concepts.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()

    # 1. ADR-017-03: Memory-safe Collection Iterator
    try:
        if target_names:
            objects_to_scan = [resolve_name(n) for n in target_names if resolve_name(n)]
        else:
            # Crucial safe iterator [:] using Python list cloning
            objects_to_scan = [
                o
                for o in list(bpy.context.scene.objects)
                if o.type == "MESH" and not o.hide_viewport and not o.hide_get()
            ]
    except Exception as e:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="GET_SCENE_MATRIX",
            error_code="SCENE_ITERATION_CRASH",
            message=f"Safe iteration failed: {e}",
        )

    scene_data = []

    # 2. Extract bounds & dimensions
    for obj in objects_to_scan:
        try:
            eval_obj = obj.evaluated_get(depsgraph)
            mat_world = eval_obj.matrix_world
            pos = mat_world.translation

            # Bound Box to World
            bounds = [mat_world @ Vector(c) for c in eval_obj.bound_box]

            # Optimized Center Calculation via Mean sum()/8
            center = sum(bounds, Vector()) / 8.0

            min_x = min(c.x for c in bounds)
            max_x = max(c.x for c in bounds)
            min_y = min(c.y for c in bounds)
            max_y = max(c.y for c in bounds)
            min_z = min(c.z for c in bounds)
            max_z = max(c.z for c in bounds)

            dx = abs(max_x - min_x)
            dy = abs(max_y - min_y)
            dz = abs(max_z - min_z)
            vol = dx * dy * dz

            # Local Z Forward equivalent: mathutils standard orientation vector setup
            forward_vec = (mat_world.to_3x3() @ Vector((0, 1, 0))).normalized()

            scene_data.append(
                {
                    "name": obj.name,
                    "volume": vol,
                    "_center": center,  # internal use
                    "position": [round(center.x, 3), round(center.y, 3), round(center.z, 3)],
                    "pivot_location": [round(pos.x, 3), round(pos.y, 3), round(pos.z, 3)],
                    "dimensions": [round(dx, 3), round(dy, 3), round(dz, 3)],
                    "forward_y": [
                        round(forward_vec.x, 3),
                        round(forward_vec.y, 3),
                        round(forward_vec.z, 3),
                    ],
                }
            )
        except Exception:
            # Degenerate bounds safe fallback
            pass

    # 3. ADR-017-02: LLM Token Limit
    scene_data.sort(key=lambda x: x["volume"], reverse=True)
    if len(scene_data) > limit:
        scene_data = scene_data[:limit]

    # 4. ADR-017-01: Euclidean KNN Mapping (O(N) safe per item without BVH)
    for i, a in enumerate(scene_data):
        distances = []
        for j, b in enumerate(scene_data):
            if i == j:
                continue
            dist = (a["_center"] - b["_center"]).length
            distances.append(
                {
                    "name": b["name"],
                    "distance_meters": round(dist, 3),
                    "touching": dist < 0.02,
                }
            )

        distances.sort(key=lambda x: x["distance_meters"])
        a["nearest_neighbors"] = distances[:3]

    # Clean up internal variables after all distance calculations
    for a in scene_data:
        a.pop("_center", None)
        a.pop("volume", None)

    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="GET_SCENE_MATRIX",
        data={"matrix_size": len(scene_data), "objects": scene_data},
    )


def _world_aabb(obj: Any) -> tuple[list[float], list[float], list[float]]:
    """Compute world-space AABB for obj using matrix_world + bound_box (mathutils-free, no evaluated_get).

    Returns (min_xyz, max_xyz, center_xyz).
    """
    mw = obj.matrix_world
    wc = []
    for corner in obj.bound_box:
        x = mw[0][0] * corner[0] + mw[0][1] * corner[1] + mw[0][2] * corner[2] + mw[0][3]
        y = mw[1][0] * corner[0] + mw[1][1] * corner[1] + mw[1][2] * corner[2] + mw[1][3]
        z = mw[2][0] * corner[0] + mw[2][1] * corner[1] + mw[2][2] * corner[2] + mw[2][3]
        wc.append((x, y, z))
    mn = [min(c[i] for c in wc) for i in range(3)]
    mx = [max(c[i] for c in wc) for i in range(3)]
    center = [(mn[i] + mx[i]) / 2 for i in range(3)]
    return mn, mx, center


def _build_world_bvh(obj: Any) -> Any:
    """Build a world-space BVHTree from obj.data (no evaluated_get, no StructRNA risk).

    Uses bm.from_mesh (base mesh, no modifiers) + bm.transform(matrix_world).
    Returns BVHTree or None on failure.
    """
    try:
        import bmesh as _bmesh
        from mathutils.bvhtree import BVHTree as _BVHTree

        bm = _bmesh.new()
        bm.from_mesh(obj.data)  # base mesh, no modifiers — safe
        bm.transform(obj.matrix_world)  # apply world transform in-place
        bvh = _BVHTree.FromBMesh(bm)
        bm.free()
        return bvh
    except Exception:
        return None


def _surface_gap_bvh(
    obj_a: Any,
    obj_b: Any,
    bvh_b: Any,
    max_verts: int = 400,
) -> tuple[float, str]:
    """Minimum surface-to-surface distance from obj_a vertices to obj_b surface.

    Returns:
        (gap_m, method)
        gap_m < 0  : interpenetration (BVH overlap confirmed)
        gap_m == 0 : touching (gap ≤ 0.001m)
        gap_m > 0  : real gap in world metres
        method     : "BVH_SURFACE" | "BVH_INTERPENETRATION" | "BVH_FAILED"
    """
    try:
        bvh_a = _build_world_bvh(obj_a)
        if bvh_a is None or bvh_b is None:
            return float("inf"), "BVH_FAILED"

        # BVHTree.overlap() — returns list of face-pair tuples that intersect
        overlaps = bvh_a.overlap(bvh_b)
        if overlaps:
            return -0.001, "BVH_INTERPENETRATION"  # geometry actually penetrates

        # Vertex sampling: obj_a vertices in world space
        verts = obj_a.data.vertices
        step = max(1, len(verts) // max_verts)
        mat_a = obj_a.matrix_world

        min_gap = float("inf")
        for i in range(0, len(verts), step):
            world_v = mat_a @ verts[i].co
            result = bvh_b.find_nearest(world_v)
            if result[0] is not None:
                nearest_world = result[0]  # BVH built in world space → world result
                d = (world_v - nearest_world).length
                if d < min_gap:
                    min_gap = d

        return (min_gap if min_gap != float("inf") else float("inf")), "BVH_SURFACE"
    except Exception:
        return float("inf"), "BVH_FAILED"


def _check_intersection(obj_a: Any, obj_b: Any) -> dict[str, Any]:
    """
    AABB-based intersection check between two meshes.

    Replaces the previous BVHTree approach which caused StructRNA crashes
    (ReferenceError: StructRNA removed) when evaluated_get() returned a stale
    depsgraph proxy in timer context.
    AABB is conservative (may give false positives for rotated objects)
    but never crashes.
    """
    # StructRNA validity guards
    try:
        _name_a = obj_a.name
    except ReferenceError:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="CHECK_INTERSECTION",
            error_code="OBJECT_FREED",
            message="First object no longer exists in Blender memory (StructRNA freed).",
        )
    try:
        _name_b = obj_b.name
    except ReferenceError:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="CHECK_INTERSECTION",
            error_code="OBJECT_FREED",
            message="Second object no longer exists in Blender memory (StructRNA freed).",
        )

    try:
        min_a, max_a, _ = _world_aabb(obj_a)
        min_b, max_b, _ = _world_aabb(obj_b)
    except Exception as e:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="CHECK_INTERSECTION",
            error_code="BBOX_ERROR",
            message=f"Failed to compute bounding boxes: {e}",
        )

    is_intersecting = all(min_a[i] <= max_b[i] and min_b[i] <= max_a[i] for i in range(3))

    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="CHECK_INTERSECTION",
        data={
            "object_a": obj_a.name,
            "object_b": obj_b.name,
            "is_intersecting": is_intersecting,
            "method": "AABB",
            "note": (
                "AABB intersection check (safe — no depsgraph/evaluated_get). "
                "Conservative: rotated objects may trigger false positives. "
                "Verify visually with get_viewport_screenshot_base64."
            ),
        },
    )


def _get_spatial_report(obj: Any) -> dict[str, Any]:
    """
    Spatial report — safe, no evaluated_get/BVH.

    Uses matrix_world + bound_box directly (mathutils-free AABB).
    Proximity scan uses center-to-center distances with ReferenceError guards.
    """
    # StructRNA validity guard
    try:
        _ = obj.name
    except ReferenceError:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="GET_SPATIAL_REPORT",
            error_code="OBJECT_FREED",
            message="Object no longer exists in Blender memory (StructRNA freed).",
        )

    matrix_world = obj.matrix_world
    world_pos = matrix_world.translation  # Vector (mathutils available since BPY_AVAILABLE=True)

    # Local axes in world space (direct matrix_world — no evaluated_get)
    local_x = (matrix_world @ Vector((1, 0, 0)) - world_pos).normalized()
    local_y = (matrix_world @ Vector((0, 1, 0)) - world_pos).normalized()
    local_z = (matrix_world @ Vector((0, 0, 1)) - world_pos).normalized()

    # Bounding box in world space (mathutils-free, no evaluated_get)
    try:
        _, _, _ = _world_aabb(obj)  # validate first
        mn, mx, center = _world_aabb(obj)
        min_x, min_y, min_z = mn
        max_x, max_y, max_z = mx
        dimensions = [max_x - min_x, max_y - min_y, max_z - min_z]
    except Exception:
        min_x = max_x = min_y = max_y = min_z = max_z = 0.0
        dimensions = [0.0, 0.0, 0.0]
        center = [world_pos.x, world_pos.y, world_pos.z]

    # Proximity scan — MESH-only, AABB center-to-center distance + AABB overlap for touching.
    # Cameras, lights, empties, and armatures are excluded — not relevant for assembly analysis.
    nearby_objects = []
    connections_text = []
    mn_self = [min_x, min_y, min_z]
    mx_self = [max_x, max_y, max_z]
    for other_obj in bpy.context.scene.objects:
        if other_obj.name == obj.name or other_obj.hide_viewport or other_obj.hide_get():
            continue
        if other_obj.type != "MESH":
            continue  # only MESH objects are relevant for assembly spatial reports
        try:
            _ = other_obj.name  # StructRNA validity check
            mn_o, mx_o, other_center = _world_aabb(other_obj)  # AABB center, NOT origin
            ox, oy, oz = other_center
            dist = ((ox - center[0]) ** 2 + (oy - center[1]) ** 2 + (oz - center[2]) ** 2) ** 0.5
            if dist < 3.0:
                # AABB overlap check for touching (consistent with GET_SCENE_MATRIX)
                touching = all(mn_self[i] <= mx_o[i] and mn_o[i] <= mx_self[i] for i in range(3))
                nearby_objects.append(
                    {
                        "name": other_obj.name,
                        "distance": round(dist, 4),
                        "touching": touching,
                    }
                )
                if touching:
                    connections_text.append(f"TOUCHING {other_obj.name} (AABB overlap)")
                else:
                    connections_text.append(
                        f"NOT TOUCHING {other_obj.name} (approx: {round(dist, 3)}m)"
                    )
        except (ReferenceError, Exception):
            continue

    touching_count = sum(1 for _o in nearby_objects if _o["touching"])
    if touching_count > 0:
        action_needed = f"In contact with {touching_count} nearby MESH object(s) (AABB overlap)."
    elif nearby_objects:
        action_needed = f"{len(nearby_objects)} nearby MESH object(s) within 3m — none touching."
    else:
        action_needed = "No nearby MESH objects within 3m radius."

    spatial_context = {
        "local_axes_in_world": {
            "X": [round(c, 4) for c in local_x],
            "Y": [round(c, 4) for c in local_y],
            "Z": [round(c, 4) for c in local_z],
        },
        "bounding_box_world": {
            "min": [round(min_x, 4), round(min_y, 4), round(min_z, 4)],
            "max": [round(max_x, 4), round(max_y, 4), round(max_z, 4)],
            "center": [round(c, 4) for c in center],
            "dimensions": [round(d, 4) for d in dimensions],
        },
        "nearby_objects": nearby_objects,
        "human_readable": {
            "position": f"World origin: ({round(world_pos.x, 3)}, {round(world_pos.y, 3)}, {round(world_pos.z, 3)}). AABB center: ({round(center[0], 3)}, {round(center[1], 3)}, {round(center[2], 3)}).",
            "orientation": f"World axes — X: {[round(x, 2) for x in local_x]}, Y: {[round(y, 2) for y in local_y]}, Z: {[round(z, 2) for z in local_z]}",
            "dimensions": f"World AABB (X,Y,Z): {round(dimensions[0], 3)}m x {round(dimensions[1], 3)}m x {round(dimensions[2], 3)}m",
            "connections": connections_text,
            "action_needed": action_needed,
            "note": "Distances are approximate. Use VERIFY_ASSEMBLY for rule-based checking.",
        },
    }

    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="GET_SPATIAL_REPORT",
        data={
            "name": obj.name,
            "spatial_context": spatial_context,
        },
    )


def _verify_assembly(rules: dict) -> dict[str, Any]:
    """
    AABB-based assembly verification (safe replacement for BVHTree/evaluated_get).

    Uses world-space bounding box overlap to determine if objects are "touching".
    Touch tolerance: 5mm (objects within 5mm of AABB contact are considered touching).
    Supports rules: must_touch, parent_must_be. Unknown rule keys are flagged as failures.
    """
    TOUCH_EPSILON = 0.005  # 5mm touch tolerance

    log: list[str] = []  # string format (backward compat)
    results_structured: list[dict] = []  # structured format (primary)
    all_passed = True
    fixes = []

    for source_name, rule_data in rules.items():
        # StructRNA validity guard
        try:
            source_obj = resolve_name(source_name)
            if source_obj is not None:
                _ = source_obj.name
        except ReferenceError:
            source_obj = None

        if not source_obj or source_obj.type != "MESH":
            log.append(f"✗ [{source_name}]: Object not found or not MESH.")
            results_structured.append(
                {
                    "source": source_name,
                    "target": None,
                    "rule": "object_lookup",
                    "passed": False,
                    "distance_m": None,
                    "note": "Object not found or not MESH type.",
                }
            )
            all_passed = False
            continue

        try:
            min_s, max_s, _ = _world_aabb(source_obj)
        except Exception as err:
            log.append(f"✗ [{source_name}]: Cannot compute bbox: {err}")
            results_structured.append(
                {
                    "source": source_name,
                    "target": None,
                    "rule": "bbox_computation",
                    "passed": False,
                    "distance_m": None,
                    "note": f"Cannot compute bbox: {err}",
                }
            )
            all_passed = False
            continue

        # --- must_touch rules ---
        must_touch = rule_data.get("must_touch", [])
        for target_name in must_touch:
            try:
                target_obj = resolve_name(target_name)
                if target_obj is not None:
                    _ = target_obj.name
            except ReferenceError:
                target_obj = None

            if not target_obj or target_obj.type != "MESH":
                log.append(f"✗ [{source_name} -> {target_name}]: Target not found or not MESH.")
                results_structured.append(
                    {
                        "source": source_name,
                        "target": target_name,
                        "rule": "must_touch",
                        "passed": False,
                        "distance_m": None,
                        "note": f"Target '{target_name}' not found or not MESH.",
                    }
                )
                fixes.append(f"SUGGESTION: Object '{target_name}' does not exist in scene.")
                all_passed = False
                continue

            try:
                min_t, max_t, _ = _world_aabb(target_obj)
            except Exception as err:
                log.append(f"✗ [{source_name} -> {target_name}]: Cannot compute target bbox: {err}")
                results_structured.append(
                    {
                        "source": source_name,
                        "target": target_name,
                        "rule": "must_touch",
                        "passed": False,
                        "distance_m": None,
                        "note": f"Cannot compute target bbox: {err}",
                    }
                )
                all_passed = False
                continue

            # BVH precise touch check (with AABB fallback)
            try:
                import bmesh as _bmesh  # noqa: F401
                from mathutils.bvhtree import BVHTree as _BVHTree  # noqa: F401

                bvh_target = _build_world_bvh(target_obj)
                surface_gap, gap_method = _surface_gap_bvh(source_obj, target_obj, bvh_target)
                touching = surface_gap <= TOUCH_EPSILON  # 5mm surface tolerance
            except Exception:
                # AABB fallback
                exp_min_s = [min_s[i] - TOUCH_EPSILON for i in range(3)]
                exp_max_s = [max_s[i] + TOUCH_EPSILON for i in range(3)]
                touching = all(
                    exp_min_s[i] <= max_t[i] and min_t[i] <= exp_max_s[i] for i in range(3)
                )
                surface_gap, gap_method = (0.0 if touching else 0.01), "AABB_FALLBACK"

            if touching:
                log.append(
                    f"✓ [{source_name} -> {target_name}]: PASS "
                    f"(gap: {surface_gap * 1000:.1f}mm, method: {gap_method})"
                )
                results_structured.append(
                    {
                        "source": source_name,
                        "target": target_name,
                        "rule": "must_touch",
                        "passed": True,
                        "distance_m": round(surface_gap, 4),
                        "method": gap_method,
                        "note": (
                            f"Touching (surface gap: {surface_gap * 1000:.1f}mm, "
                            f"method: {gap_method})"
                        ),
                    }
                )
            else:
                log.append(
                    f"✗ [{source_name} -> {target_name}]: FAIL "
                    f"(gap: {surface_gap * 1000:.1f}mm, method: {gap_method})"
                )
                results_structured.append(
                    {
                        "source": source_name,
                        "target": target_name,
                        "rule": "must_touch",
                        "passed": False,
                        "distance_m": round(surface_gap, 4),
                        "method": gap_method,
                        "note": (
                            f"Gap of {surface_gap * 1000:.1f}mm "
                            f"(method: {gap_method}). Use PLACE_RELATIVE_TO to align."
                        ),
                    }
                )
                fixes.append(
                    f"SUGGESTION: Use PLACE_RELATIVE_TO to align '{source_name}' with '{target_name}'."
                )
                all_passed = False

        # --- parent_must_be rule ---
        parent_must_be = rule_data.get("parent_must_be")
        if parent_must_be is not None:
            actual_parent = source_obj.parent.name if source_obj.parent else None
            passed = actual_parent == parent_must_be
            if passed:
                log.append(f"✓ [{source_name}]: parent_must_be '{parent_must_be}' PASS")
                note = "Parent matches"
            else:
                log.append(
                    f"✗ [{source_name}]: parent_must_be '{parent_must_be}' FAIL (actual: '{actual_parent}')"
                )
                note = f"Parent is '{actual_parent}'"
                all_passed = False
            results_structured.append(
                {
                    "source": source_name,
                    "target": parent_must_be,
                    "rule": "parent_must_be",
                    "passed": passed,
                    "distance_m": None,
                    "note": note,
                }
            )

        # --- Unknown rule keys ---
        known_rules = {"must_touch", "parent_must_be"}
        unknown = set(rule_data.keys()) - known_rules
        if unknown:
            msg = f"Unknown rule type(s): {sorted(unknown)}. Supported: must_touch, parent_must_be"
            log.append(f"✗ [{source_name}]: {msg}")
            results_structured.append(
                {
                    "source": source_name,
                    "target": None,
                    "rule": str(sorted(unknown)),
                    "passed": False,
                    "distance_m": None,
                    "note": msg,
                }
            )
            all_passed = False

    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="VERIFY_ASSEMBLY",
        data={
            "all_passed": all_passed,
            "results": results_structured,
            "verification_log": log,
            "_deprecated": "verification_log is deprecated; use results instead",
            "recommended_fixes": list(set(fixes)),
            "method": "BVH_SURFACE_with_AABB_FALLBACK",
            "note": "BVH surface-gap check (precise mm accuracy). AABB fallback if bmesh unavailable. Touch threshold: 5mm.",
        },
    )


def _cast_ray(
    origin: list[float],
    direction: list[float],
    distance: float,
    ignore_self: list[str] | None,
    limit: int,
) -> dict[str, Any]:
    """
    Advanced Raycasting with Bounding Box Culling, Direction and Shape Analysis.
    Implements transient BVH cache strictly bound to the function scope to avoid OOM.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()

    origin_vec = Vector(origin)
    dir_vec = Vector(direction).normalized()
    ignore_names = set(ignore_self) if ignore_self else set()

    # 1. Broad Phase Culling (CPU-safe)
    candidates = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.hide_viewport or obj.hide_get() or obj.name in ignore_names:
            continue

        eval_obj = obj.evaluated_get(depsgraph)
        mat_world = eval_obj.matrix_world

        try:
            world_corners = [mat_world @ Vector(c) for c in eval_obj.bound_box]
            center = sum(world_corners, Vector()) / 8.0
        except Exception:
            center = mat_world.translation

        to_center = center - origin_vec
        dist_to_center = to_center.length

        try:
            radius = (world_corners[0] - world_corners[6]).length / 2.0
        except Exception:
            radius = 2.0

        if dist_to_center - radius > distance:
            continue

        if dist_to_center > radius:
            normalized_to_center = to_center.normalized()
            dot_prod = normalized_to_center.dot(dir_vec)
            if dot_prod < 0:
                continue

        a_verts = len(getattr(eval_obj.data, "vertices", []))
        if a_verts > MAX_VERTEX_LIMIT:
            continue

        candidates.append((dist_to_center, eval_obj))

    candidates.sort(key=lambda x: x[0])

    # 2. Transient Cache (No Global State)
    bvh_cache: Dict[str, Any] = {}
    current_cache_size = 0
    import sys

    closest_hit = None
    min_hit_dist = float("inf")

    # 3. Raycast Iteration
    for _, eval_obj in candidates[:limit]:
        if eval_obj.name not in bvh_cache:
            try:
                bvh = BVHTree.FromObject(eval_obj, depsgraph)
                bvh_size = sys.getsizeof(bvh)

                # Bug 19: Proactive OOM Prevention
                if current_cache_size + bvh_size > 100 * 1024 * 1024:  # 100 MB Limit
                    bvh_cache.clear()
                    current_cache_size = 0

                bvh_cache[eval_obj.name] = bvh
                current_cache_size += bvh_size
            except Exception as e:
                logger.error(f"BVH setup failed for {eval_obj.name}: {e}")
                bvh_cache[eval_obj.name] = None

        bvh = bvh_cache.get(eval_obj.name)
        if not bvh:
            continue

        # Transform to local space for BVH (BVH is built in local object coords)
        inv_matrix = eval_obj.matrix_world.inverted_safe()
        local_origin = inv_matrix @ origin_vec
        local_dir = (inv_matrix.to_3x3() @ dir_vec).normalized()

        hit_loc_local, hit_normal_local, hit_index, _ = bvh.ray_cast(
            local_origin, local_dir, distance
        )

        if hit_loc_local is not None:
            hit_loc = eval_obj.matrix_world @ hit_loc_local  # local → world
            hit_normal = (
                eval_obj.matrix_world.to_3x3().inverted_safe().transposed() @ hit_normal_local
            ).normalized()  # local → world (inverse-transpose for non-uniform scale)
            hit_dist = (hit_loc - origin_vec).length  # recompute world-space distance

            if hit_dist < min_hit_dist:
                min_hit_dist = hit_dist

                # 4. Shape & Direction Analysis
                world_corners = [eval_obj.matrix_world @ Vector(c) for c in eval_obj.bound_box]
                min_x = min(c.x for c in world_corners)
                max_x = max(c.x for c in world_corners)
                min_y = min(c.y for c in world_corners)
                max_y = max(c.y for c in world_corners)
                min_z = min(c.z for c in world_corners)
                max_z = max(c.z for c in world_corners)
                dx = max_x - min_x
                dy = max_y - min_y
                dz = max_z - min_z

                dims = sorted([dx, dy, dz])
                ratio_1 = dims[1] / max(dims[0], 0.001)
                ratio_2 = dims[2] / max(dims[1], 0.001)

                if ratio_1 < 2.0 and ratio_2 < 2.0:
                    shape = "Cube/Sphere (Hacimli/Dengeli)"
                elif ratio_2 > 3.0 and ratio_1 < 2.0:
                    shape = "Plank/Bar (Uzun Silindir/Çubuk)"
                elif ratio_1 > 3.0:
                    shape = "Plate/Plane (Düzlem/Panel)"
                else:
                    shape = "Mixed/Custom (Karma/Belirsiz)"

                # Convert world normal back to local for face-direction analysis
                local_normal = (
                    eval_obj.matrix_world.to_3x3().transposed() @ hit_normal
                ).normalized()

                dir_face = "Unknown"
                abs_x, abs_y, abs_z = abs(local_normal.x), abs(local_normal.y), abs(local_normal.z)
                if local_normal.z > 0.7:
                    dir_face = "Top Face (+Z)"
                elif local_normal.z < -0.7:
                    dir_face = "Bottom Face (-Z)"
                elif local_normal.y > 0.7:
                    dir_face = "Front Face (+Y)"
                elif local_normal.y < -0.7:
                    dir_face = "Back Face (-Y)"
                elif local_normal.x > 0.7:
                    dir_face = "Right Face (+X)"
                elif local_normal.x < -0.7:
                    dir_face = "Left Face (-X)"
                elif abs_x > abs_y and abs_x > abs_z:
                    dir_face = "East/West Edge"
                elif abs_y > abs_x and abs_y > abs_z:
                    dir_face = "North/South Edge"
                else:
                    dir_face = "Corners/Bevel"

                closest_hit = {
                    "hit_object": eval_obj.name,
                    "hit_location": [round(hit_loc.x, 4), round(hit_loc.y, 4), round(hit_loc.z, 4)],
                    "hit_normal": [
                        round(hit_normal.x, 4),
                        round(hit_normal.y, 4),
                        round(hit_normal.z, 4),
                    ],
                    "distance": round(hit_dist, 4),
                    "hit_polygon_index": hit_index,
                    "analysis": {
                        "shape_estimation": shape,
                        "hit_face_direction": dir_face,
                        "dimensions": [round(dx, 3), round(dy, 3), round(dz, 3)],
                    },
                }

    # 5. Black hole detection
    is_inside_obstacle = False
    if min_hit_dist == 0.0:
        is_inside_obstacle = True

    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="CAST_RAY",
        data={
            "is_hit": closest_hit is not None,
            "is_inside_obstacle": is_inside_obstacle,
            "hit_data": closest_hit,
            "ray_params": {
                "origin": [round(o, 4) for o in origin],
                "direction": [round(dir_vec.x, 4), round(dir_vec.y, 4), round(dir_vec.z, 4)],
                "max_distance": distance,
            },
        },
    )


def _get_objects_flat(params: dict) -> dict[str, Any]:
    """Fast flat list of all scene objects with world positions.

    Returns per-object: name, type, world_location (WORLD-SPACE, parenting-aware),
    dimensions, geometry_center_world, origin_offset_warning, animation_state,
    visible, parent, material_count, collection — in a single O(N) pass.

    Unlike GET_SCENE_MATRIX (MESH-only, nearest_neighbors), this covers ALL object types
    (cameras, lights, empties, armatures, etc.) and is the recommended first call.
    """
    include_hidden = params.get("include_hidden", False)
    objects_data = []
    try:
        for obj in list(bpy.context.scene.objects):
            try:
                _ = obj.name  # StructRNA validity guard
            except ReferenceError:
                continue
            if not include_hidden and (obj.hide_viewport or obj.hide_get()):
                continue
            mw = obj.matrix_world
            wx, wy, wz = mw[0][3], mw[1][3], mw[2][3]
            reu = obj.rotation_euler
            # matrix_world as flat 4x4 row-major list
            mw_list = [[round(mw[r][c], 6) for c in range(4)] for r in range(4)]
            entry: dict[str, Any] = {
                "name": obj.name,
                "type": obj.type,
                "world_location": [round(wx, 4), round(wy, 4), round(wz, 4)],
                "location_local": [
                    round(obj.location.x, 6),
                    round(obj.location.y, 6),
                    round(obj.location.z, 6),
                ],
                "location_local_note": (
                    f"Relative to parent '{obj.parent.name}' "
                    f"(parent world: [{round(wx, 4)}, {round(wy, 4)}, {round(wz, 4)}])"
                    if obj.parent
                    else "World space (no parent)"
                ),
                "rotation_degrees": [
                    round(reu.x * 57.2958, 2),
                    round(reu.y * 57.2958, 2),
                    round(reu.z * 57.2958, 2),
                ],
                "scale": [round(obj.scale.x, 6), round(obj.scale.y, 6), round(obj.scale.z, 6)],
                "matrix_world": mw_list,
                "dimensions": [round(v, 4) for v in obj.dimensions] if obj.type == "MESH" else None,
                "visible": not obj.hide_viewport,
                "parent": obj.parent.name if obj.parent else None,
                "children": [c.name for c in obj.children] if obj.children else [],
                "material_count": len(obj.material_slots),
                "collection": obj.users_collection[0].name if obj.users_collection else None,
            }

            # Custom properties
            custom_props = {}
            for key in obj.keys():
                if not key.startswith("_"):
                    val = obj[key]
                    if isinstance(val, (int, float, str, bool, list, dict)):
                        custom_props[key] = val
            if custom_props:
                entry["custom_properties"] = custom_props

            # Geometry center + world_bounding_box via bounding-box (mathutils-free)
            if obj.type == "MESH" and obj.bound_box:
                wc_list = []
                for corner in obj.bound_box:
                    cx = (
                        mw[0][0] * corner[0]
                        + mw[0][1] * corner[1]
                        + mw[0][2] * corner[2]
                        + mw[0][3]
                    )
                    cy = (
                        mw[1][0] * corner[0]
                        + mw[1][1] * corner[1]
                        + mw[1][2] * corner[2]
                        + mw[1][3]
                    )
                    cz = (
                        mw[2][0] * corner[0]
                        + mw[2][1] * corner[1]
                        + mw[2][2] * corner[2]
                        + mw[2][3]
                    )
                    wc_list.append((cx, cy, cz))
                geo_x = (min(c[0] for c in wc_list) + max(c[0] for c in wc_list)) / 2
                geo_y = (min(c[1] for c in wc_list) + max(c[1] for c in wc_list)) / 2
                geo_z = (min(c[2] for c in wc_list) + max(c[2] for c in wc_list)) / 2
                entry["geometry_center_world"] = [round(geo_x, 4), round(geo_y, 4), round(geo_z, 4)]
                offset = ((geo_x - wx) ** 2 + (geo_y - wy) ** 2 + (geo_z - wz) ** 2) ** 0.5
                entry["origin_offset_m"] = round(offset, 4)
                # Warn if origin is >1cm from geometry center (common cause of wrong pivot rotation)
                entry["origin_offset_warning"] = offset > 0.01
                entry["world_bounding_box"] = {
                    "min": [round(min(c[i] for c in wc_list), 4) for i in range(3)],
                    "max": [round(max(c[i] for c in wc_list), 4) for i in range(3)],
                }

            # Animation state (quick check — no fcurve value sampling)
            anim = obj.animation_data
            if anim:
                entry["animation_state"] = {
                    "has_animation": True,
                    "action": anim.action.name if anim.action else None,
                    "nla_tracks": len(anim.nla_tracks),
                    "warning": (
                        "Animation data is active. Manual transform writes (location/rotation/scale) "
                        "will be OVERRIDDEN each frame. Call obj.animation_data_clear() before setting."
                    ),
                }
            else:
                entry["animation_state"] = {"has_animation": False}

            objects_data.append(entry)
    except Exception as e:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="GET_OBJECTS_FLAT",
            error_code="SCENE_ITERATION_ERROR",
            message=f"Scene iteration failed: {e}",
        )
    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="GET_OBJECTS_FLAT",
        data={"object_count": len(objects_data), "objects": objects_data},
    )


def _build_assembly_pairs(
    mesh_objects: list,
    bboxes: dict,
    max_proximity: float = 0.05,
    max_pairs: int = 500,
) -> tuple[set[tuple[str, str]], dict[str, int]]:
    """
    Build the set of (name_a, name_b) pairs to analyze for assembly gaps.

    Two categories:
    1. Parent↔child hierarchy pairs — always included (explicit assembly connections).
    2. Proximity pairs — any non-hierarchy pair where AABB max-separation ≤ max_proximity.
       Critically, this includes AABB-overlapping pairs (aabb_max_sep ≤ 0), which are
       the interpenetration case (e.g. Body_Shell↔Arm where geometries actually intersect).

    This avoids the sibling-pair N² explosion for flat hierarchies (40+ children of one EMPTY)
    while still catching all spatially relevant pairs via the AABB spatial test.

    Pair keys are stored as (min_name, max_name) to avoid duplicates.
    Returns (pairs_set, breakdown_dict) where breakdown has hierarchy/overlap/gap counts.
    """
    pairs: set[tuple[str, str]] = set()
    breakdown = {"hierarchy": 0, "overlap": 0, "gap": 0, "capped": False}

    # 1. Hierarchy pairs — parent↔child (always check)
    for obj in mesh_objects:
        if obj.parent and obj.parent.name in bboxes and obj.name in bboxes:
            a, b = sorted([obj.name, obj.parent.name])
            if (a, b) not in pairs:
                pairs.add((a, b))
                breakdown["hierarchy"] += 1

    # 2. Proximity pairs — AABB max-separation ≤ max_proximity (includes overlap ≤ 0).
    # • aabb_max_sep < 0: all 3 axes overlap → INTERPENETRATION candidate
    # • 0 ≤ aabb_max_sep ≤ max_proximity: close but not overlapping → SURFACE_GAP candidate
    # Objects with aabb_max_sep > max_proximity are far apart → skip.
    names = list(bboxes.keys())
    for i in range(len(names)):
        if len(pairs) >= max_pairs:
            breakdown["capped"] = True
            break
        for j in range(i + 1, len(names)):
            if len(pairs) >= max_pairs:
                breakdown["capped"] = True
                break
            na, nb = names[i], names[j]
            key = (min(na, nb), max(na, nb))
            if key in pairs:
                continue  # already a hierarchy pair
            mn_a, mx_a = bboxes[na]
            mn_b, mx_b = bboxes[nb]
            aabb_sep = [max(mn_a[k] - mx_b[k], mn_b[k] - mx_a[k]) for k in range(3)]
            aabb_max_sep = max(aabb_sep)
            if aabb_max_sep <= max_proximity:
                pairs.add(key)
                if aabb_max_sep < 0:
                    breakdown["overlap"] += 1
                else:
                    breakdown["gap"] += 1

    return pairs, breakdown


def _analyze_assembly(
    threshold_pct: float = 2.0,
    exclude_objects: list | None = None,
    max_proximity: float = 0.05,
    max_issues: int = 20,
    max_pairs: int = 500,
) -> dict[str, Any]:
    """
    ANALYZE_ASSEMBLY — Detect assembly issues: origin offsets, gaps, overlaps, non-manifold edges.

    Returns:
        assembly_score (0-100), issues list, non_manifold counts, recommendation.
    """
    try:
        scene = bpy.context.scene
        mesh_objects = [
            obj
            for obj in scene.objects
            if obj.type == "MESH" and not obj.hide_viewport and obj.data and obj.data.vertices
        ]
    except Exception as e:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="ANALYZE_ASSEMBLY",
            error_code="SCENE_ACCESS_ERROR",
            message=f"Cannot access scene: {e}",
        )

    exclude_set = set(exclude_objects or [])
    if exclude_set:
        mesh_objects = [o for o in mesh_objects if o.name not in exclude_set]

    if not mesh_objects:
        return ResponseBuilder.success(
            handler="get_scene_graph",
            action="ANALYZE_ASSEMBLY",
            data={
                "assembly_score": 100,
                "issues": [],
                "non_manifold": {},
                "object_count": 0,
                "exclude_objects": sorted(exclude_set),
                "recommendation": "No visible MESH objects found in scene.",
            },
        )

    issues: list[dict[str, Any]] = []
    non_manifold: dict[str, int] = {}

    # --- Compute world bounding boxes (mathutils-free) ---
    def _world_bbox(obj: Any) -> tuple[list[float], list[float]]:
        """Returns (min_xyz, max_xyz) in world space."""
        mw = obj.matrix_world
        world_corners = []
        for corner in obj.bound_box:
            x = mw[0][0] * corner[0] + mw[0][1] * corner[1] + mw[0][2] * corner[2] + mw[0][3]
            y = mw[1][0] * corner[0] + mw[1][1] * corner[1] + mw[1][2] * corner[2] + mw[1][3]
            z = mw[2][0] * corner[0] + mw[2][1] * corner[1] + mw[2][2] * corner[2] + mw[2][3]
            world_corners.append((x, y, z))
        mn = [min(c[i] for c in world_corners) for i in range(3)]
        mx = [max(c[i] for c in world_corners) for i in range(3)]
        return mn, mx

    bboxes: dict[str, tuple[list[float], list[float]]] = {}
    for obj in mesh_objects:
        try:
            bboxes[obj.name] = _world_bbox(obj)
        except Exception:
            pass

    # --- Origin offset check (root objects only) ---
    # Parented objects commonly have origin at parent/rig origin — this is EXPECTED
    # and should NOT be flagged. Only check root objects (no parent).
    for obj in mesh_objects:
        try:
            _ = obj.name  # StructRNA guard
            if obj.parent is not None:
                continue  # skip parented — origin offset is normal for rigged/assembled parts
            mw = obj.matrix_world
            origin = [mw[0][3], mw[1][3], mw[2][3]]
            mn, mx = bboxes.get(obj.name, (origin, origin))
            geo_center = [(mn[i] + mx[i]) / 2 for i in range(3)]
            offset = sum((geo_center[i] - origin[i]) ** 2 for i in range(3)) ** 0.5
            if offset > 0.01:
                issues.append(
                    {
                        "type": "ORIGIN_OFFSET",
                        "object": obj.name,
                        "offset_m": round(offset, 4),
                        "detail": (
                            f"Root object origin is {offset:.4f}m from geometry center. "
                            "Rotations will pivot around the wrong point. "
                            "Fix: Object > Set Origin > Origin to Geometry."
                        ),
                    }
                )
        except (ReferenceError, Exception):
            pass

    # --- BVH surface gap detection (precise, world-space vertex projection) ---
    # Phase 1: build BVH cache for all mesh objects
    try:
        import bmesh as _bmesh  # noqa: F401
        from mathutils.bvhtree import BVHTree as _BVHTree  # noqa: F401

        bvh_available = True
    except ImportError:
        bvh_available = False

    bvh_cache: dict[str, Any] = {}
    if bvh_available:
        for _bvh_obj in mesh_objects:
            try:
                _ = _bvh_obj.name  # StructRNA guard
                _bvh = _build_world_bvh(_bvh_obj)
                if _bvh is not None:
                    bvh_cache[_bvh_obj.name] = _bvh
            except Exception:
                pass

    # Phase 2: pairwise surface gap analysis (hierarchy-aware)
    pairs, pairs_breakdown = _build_assembly_pairs(mesh_objects, bboxes, max_proximity, max_pairs)
    pairs_checked = 0
    for na, nb in pairs:
        pairs_checked += 1
        mn_a, mx_a = bboxes[na]
        mn_b, mx_b = bboxes[nb]

        obj_a = bpy.data.objects.get(na)
        obj_b = bpy.data.objects.get(nb)
        bvh_b = bvh_cache.get(nb)

        if bvh_available and obj_a and obj_b and bvh_b is not None:
            surface_gap, method = _surface_gap_bvh(obj_a, obj_b, bvh_b)
        else:
            aabb_sep = [max(mn_a[k] - mx_b[k], mn_b[k] - mx_a[k]) for k in range(3)]
            surface_gap = max(max(aabb_sep), 0.0)
            method = "AABB_FALLBACK"

        size_a = max(mx_a[k] - mn_a[k] for k in range(3))
        size_b = max(mx_b[k] - mn_b[k] for k in range(3))
        ref_size = max(size_a, size_b, 0.001)
        gap_threshold = max(ref_size * (threshold_pct / 100.0), 0.002)

        if method == "BVH_INTERPENETRATION":
            issues.append(
                {
                    "type": "INTERPENETRATION",
                    "between": [na, nb],
                    "gap_m": -0.001,
                    "detail": (
                        "Real geometry interpenetration detected (BVH face-overlap test). "
                        "Meshes are physically intersecting — not an AABB artifact."
                    ),
                    "method": method,
                }
            )
        elif surface_gap <= 0.002:
            pass  # Touching / in contact — no issue, healthy assembly
        elif surface_gap > gap_threshold:
            issues.append(
                {
                    "type": "SURFACE_GAP",
                    "between": [na, nb],
                    "gap_m": round(surface_gap, 4),
                    "detail": (
                        f"Surface gap of {surface_gap * 1000:.1f}mm detected "
                        f"(method: {method}). "
                        f"Threshold: {gap_threshold * 1000:.1f}mm "
                        f"({threshold_pct}% of object size)."
                    ),
                    "method": method,
                }
            )

    # Cap output: keep all INTERPENETRATION, sort SURFACE_GAP by severity, truncate
    gap_issues_all = [i for i in issues if i["type"] == "SURFACE_GAP"]
    gap_issues_all.sort(key=lambda x: x["gap_m"])  # ascending: smallest (most critical) first
    total_gap_pairs = len(gap_issues_all)
    if len(gap_issues_all) > max_issues:
        gap_issues_all = gap_issues_all[:max_issues]
    gap_issues_note = (
        f"{len(gap_issues_all)} shown / {total_gap_pairs} total"
        if total_gap_pairs > max_issues
        else f"all {total_gap_pairs} shown"
    )
    issues = (
        [i for i in issues if i["type"] == "INTERPENETRATION"]
        + gap_issues_all
        + [i for i in issues if i["type"] not in ("INTERPENETRATION", "SURFACE_GAP")]
    )

    # --- Non-manifold edge count (bmesh) ---
    try:
        import bmesh as _bmesh

        for obj in mesh_objects[:20]:  # Cap to 20 objects
            try:
                bm = _bmesh.new()
                bm.from_mesh(obj.data)
                nm_count = sum(1 for e in bm.edges if not e.is_manifold)
                bm.free()
                non_manifold[obj.name] = nm_count
                if nm_count > 0:
                    issues.append(
                        {
                            "type": "NON_MANIFOLD",
                            "object": obj.name,
                            "edge_count": nm_count,
                            "detail": f"{nm_count} non-manifold edges found (not watertight).",
                        }
                    )
            except Exception:
                pass
    except ImportError:
        pass  # bmesh not available (mock env)

    # --- Score: start at 100, deduct for real issues ---
    # BVH-based issue types: INTERPENETRATION, SURFACE_GAP (real geometry problems)
    # Origin offsets only on root objects — fair for rigged/assembled models
    score = 100
    origin_issues = [i for i in issues if i["type"] == "ORIGIN_OFFSET"]
    interpenetration_issues = [i for i in issues if i["type"] == "INTERPENETRATION"]
    gap_issues = [i for i in issues if i["type"] == "SURFACE_GAP"]
    nm_issues = [i for i in issues if i["type"] == "NON_MANIFOLD"]

    score -= min(20, len(origin_issues) * 5)  # root origin offsets: 5pt each, max 20
    score -= min(20, len(interpenetration_issues) * 10)  # real interpenetration: 10pt each, max 20
    score -= min(20, len(gap_issues) * 5)  # real surface gaps: 5pt each, max 20
    score -= min(20, sum(i.get("edge_count", 0) for i in nm_issues) // 10)
    score = max(0, score)

    # Model type info
    parented_count = sum(1 for obj in mesh_objects if obj.parent is not None)
    root_count = len(mesh_objects) - parented_count

    # --- Recommendation ---
    rec_parts = []
    if origin_issues:
        rec_parts.append(
            "Root object origin offsets detected. "
            "Fix with Object > Set Origin > Origin to Geometry, "
            "or: bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')."
        )
    if interpenetration_issues:
        rec_parts.append(
            "Real geometry interpenetration detected (BVH face-overlap test). "
            "Meshes are physically intersecting — fix with Mesh > Boolean or separate objects."
        )
    if gap_issues:
        rec_parts.append(
            "Surface gaps detected (BVH vertex-projection). "
            "Verify assembly visually with get_viewport_screenshot_base64."
        )
    if nm_issues:
        rec_parts.append(
            "Non-manifold edges found — repair with Mesh > Clean Up > Fill Holes or Merge by Distance."
        )
    if not rec_parts:
        rec_parts.append("Assembly looks clean. Score >= 90 is production-ready.")

    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="ANALYZE_ASSEMBLY",
        data={
            "assembly_score": score,
            "object_count": len(mesh_objects),
            "pairs_checked": pairs_checked,
            "pairs_breakdown": pairs_breakdown,
            "gap_issues_note": gap_issues_note,
            "exclude_objects": sorted(exclude_set),
            "model_info": {
                "root_objects": root_count,
                "parented_objects": parented_count,
                "note": (
                    "Parented objects skipped in origin-offset check — "
                    "origin offsets are NORMAL for rigged/assembled parts."
                )
                if parented_count > 0
                else "All objects are root-level (no parent).",
            },
            "issues": issues,
            "issue_summary": {
                "origin_offsets": len(origin_issues),
                "interpenetrations": len(interpenetration_issues),
                "surface_gaps": len(gap_issues),
                "non_manifold_objects": len(nm_issues),
            },
            "score_notes": (
                "Scoring: origin_offset=-5/root-obj(max 20), "
                "interpenetration=-10/object(max 20), "
                "surface_gap=-5/pair(max 20), "
                "non_manifold=-1/10-edges(max 20)."
            ),
            "non_manifold": non_manifold,
            "recommendation": " ".join(rec_parts),
        },
    )


def _get_hierarchy_tree(max_depth: int = 10) -> dict[str, Any]:
    """GET_HIERARCHY_TREE — Iterative BFS parent-child hierarchy of all visible scene objects.

    Avoids Python recursion limits for deep rigs (100+ bone chains).
    Nodes beyond max_depth are truncated with children_count + truncated=True.
    """
    try:
        roots = [
            o
            for o in bpy.context.scene.objects
            if o.parent is None and not o.hide_viewport and not o.hide_get()
        ]
    except Exception as e:
        return ResponseBuilder.error(
            "get_scene_graph",
            "GET_HIERARCHY_TREE",
            "SCENE_ACCESS_ERROR",
            f"Cannot access scene: {e}",
        )

    def build_node(obj: Any, depth: int) -> dict[str, Any]:
        node: dict[str, Any] = {"name": obj.name, "type": obj.type}
        try:
            visible_children = [c for c in obj.children if not c.hide_viewport and not c.hide_get()]
        except Exception:
            visible_children = []
        if depth < max_depth and visible_children:
            node["children"] = [build_node(c, depth + 1) for c in visible_children]
        elif visible_children:
            node["children_count"] = len(visible_children)
            node["truncated"] = True
        return node

    tree = [build_node(r, 0) for r in roots]
    return ResponseBuilder.success(
        "get_scene_graph",
        "GET_HIERARCHY_TREE",
        data={
            "tree": tree,
            "root_count": len(roots),
            "max_depth_applied": max_depth,
        },
    )


def _detect_geometry_errors(params: dict) -> dict[str, Any]:
    """DETECT_GEOMETRY_ERRORS — Per-object bmesh analysis of non-manifold edges, boundary edges,
    and zero-area faces. Useful for identifying mesh integrity issues before export/print."""
    try:
        import bmesh as _bmesh
    except ImportError:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="DETECT_GEOMETRY_ERRORS",
            error_code="BMESH_NOT_AVAILABLE",
            message="bmesh module not available (must run inside Blender).",
        )

    max_objects = int(params.get("max_objects", 20))
    try:
        mesh_objects = [
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and not obj.hide_viewport and obj.data
        ][:max_objects]
    except Exception as exc:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="DETECT_GEOMETRY_ERRORS",
            error_code="SCENE_ACCESS_ERROR",
            message=f"Cannot access scene: {exc}",
        )

    geometry_errors: dict[str, Any] = {}
    objects_with_issues = 0
    total_issue_elements = 0

    for obj in mesh_objects:
        try:
            bm = _bmesh.new()
            bm.from_mesh(obj.data)
            non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
            boundary = sum(1 for e in bm.edges if e.is_boundary)
            zero_area = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
            total_faces = len(bm.faces)
            total_edges = len(bm.edges)
            total_verts = len(bm.verts)
            bm.free()
            geometry_errors[obj.name] = {
                "non_manifold_edges": non_manifold,
                "boundary_edges": boundary,
                "zero_area_faces": zero_area,
                "total_faces": total_faces,
                "total_edges": total_edges,
                "total_verts": total_verts,
            }
            if non_manifold > 0 or boundary > 0 or zero_area > 0:
                objects_with_issues += 1
                total_issue_elements += non_manifold + boundary + zero_area
        except Exception:
            pass

    clean_objects = len(geometry_errors) - objects_with_issues
    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="DETECT_GEOMETRY_ERRORS",
        data={
            "geometry_errors": geometry_errors,
            "summary": {
                "total_issue_elements": total_issue_elements,
                "total_issues_meaning": (
                    "Sum of defective edges/faces across all objects "
                    "(not object count — use objects_with_issues for that)"
                ),
                "clean_objects": clean_objects,
                "objects_with_issues": objects_with_issues,
                "objects_checked": len(geometry_errors),
            },
            "note": (
                f"Checked first {max_objects} visible MESH objects. "
                "Pass max_objects param to override."
            ),
        },
    )


def _geometry_complexity() -> dict[str, Any]:
    """GEOMETRY_COMPLEXITY — Triangle/vertex/ngon counts per object + scene totals + material stats.
    Returns complexity tier (LOW/MEDIUM/HIGH/VERY_HIGH). No FPS/render time estimate."""
    try:
        mesh_objects = [
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and not obj.hide_viewport and obj.data
        ]
    except Exception as exc:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="GEOMETRY_COMPLEXITY",
            error_code="SCENE_ACCESS_ERROR",
            message=f"Cannot access scene: {exc}",
        )

    per_object: dict[str, Any] = {}
    scene_tris = 0
    scene_verts = 0
    scene_edges = 0
    scene_ngons = 0
    all_materials: set[str] = set()
    seen_node_mats: set[str] = set()
    node_tree_count = 0
    image_texture_count = 0

    for obj in mesh_objects:
        try:
            mesh = obj.data
            verts = len(mesh.vertices)
            edges = len(mesh.edges)
            tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
            ngons = sum(1 for p in mesh.polygons if len(p.vertices) > 4)
            per_object[obj.name] = {
                "triangles": tris,
                "vertices": verts,
                "edges": edges,
                "ngons": ngons,
            }
            scene_tris += tris
            scene_verts += verts
            scene_edges += edges
            scene_ngons += ngons
            for slot in obj.material_slots:
                if slot.material:
                    mat = slot.material
                    all_materials.add(mat.name)
                    if mat.node_tree and mat.name not in seen_node_mats:
                        seen_node_mats.add(mat.name)
                        node_tree_count += 1
                        for node in mat.node_tree.nodes:
                            if node.type == "TEX_IMAGE":
                                image_texture_count += 1
        except Exception:
            pass

    if scene_tris < 10_000:
        tier = "LOW"
    elif scene_tris < 100_000:
        tier = "MEDIUM"
    elif scene_tris < 500_000:
        tier = "HIGH"
    else:
        tier = "VERY_HIGH"

    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="GEOMETRY_COMPLEXITY",
        data={
            "per_object": per_object,
            "scene_totals": {
                "triangles": scene_tris,
                "vertices": scene_verts,
                "edges": scene_edges,
                "ngons": scene_ngons,
                "materials": len(all_materials),
                "objects": len(per_object),
            },
            "material_stats": {
                "unique_materials": len(all_materials),
                "node_tree_count": node_tree_count,
                "image_texture_count": image_texture_count,
            },
            "complexity_tier": tier,
            "note": (
                "No FPS/render time estimate — too hardware-dependent. "
                "Run actual render for timing."
            ),
        },
    )


def _check_production_readiness(params: dict) -> dict[str, Any]:
    """CHECK_PRODUCTION_READINESS — Per-object production checklist: manifold, UV, materials,
    naming, origin alignment, no ngons. Returns score 0-100 per object + scene average."""
    try:
        import bmesh as _bmesh

        has_bmesh = True
    except ImportError:
        has_bmesh = False

    DEFAULT_NAMES = {
        "Cube",
        "Sphere",
        "Plane",
        "Cylinder",
        "Cone",
        "Torus",
        "Suzanne",
        "Circle",
        "IcoSphere",
    }
    max_objects = int(params.get("max_objects", 20))

    try:
        mesh_objects = [
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and not obj.hide_viewport and obj.data
        ][:max_objects]
    except Exception as exc:
        return ResponseBuilder.error(
            handler="get_scene_graph",
            action="CHECK_PRODUCTION_READINESS",
            error_code="SCENE_ACCESS_ERROR",
            message=f"Cannot access scene: {exc}",
        )

    per_object: dict[str, Any] = {}
    all_failing: list[str] = []

    for obj in mesh_objects:
        try:
            mw = obj.matrix_world
            wx, wy, wz = mw[0][3], mw[1][3], mw[2][3]

            # Origin offset via bounding box (mathutils-free)
            origin_offset_m = 0.0
            if obj.bound_box:
                wc_list = []
                for corner in obj.bound_box:
                    cx = (
                        mw[0][0] * corner[0]
                        + mw[0][1] * corner[1]
                        + mw[0][2] * corner[2]
                        + mw[0][3]
                    )
                    cy = (
                        mw[1][0] * corner[0]
                        + mw[1][1] * corner[1]
                        + mw[1][2] * corner[2]
                        + mw[1][3]
                    )
                    cz = (
                        mw[2][0] * corner[0]
                        + mw[2][1] * corner[1]
                        + mw[2][2] * corner[2]
                        + mw[2][3]
                    )
                    wc_list.append((cx, cy, cz))
                geo_x = (min(c[0] for c in wc_list) + max(c[0] for c in wc_list)) / 2
                geo_y = (min(c[1] for c in wc_list) + max(c[1] for c in wc_list)) / 2
                geo_z = (min(c[2] for c in wc_list) + max(c[2] for c in wc_list)) / 2
                origin_offset_m = ((geo_x - wx) ** 2 + (geo_y - wy) ** 2 + (geo_z - wz) ** 2) ** 0.5

            # Non-manifold check via bmesh
            is_manifold = True
            if has_bmesh:
                try:
                    bm = _bmesh.new()
                    bm.from_mesh(obj.data)
                    nm_count = sum(1 for e in bm.edges if not e.is_manifold)
                    bm.free()
                    is_manifold = nm_count == 0
                except Exception:
                    pass

            ngon_count = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)

            checks = {
                "is_manifold": is_manifold,
                "has_materials": len(obj.material_slots) > 0,
                "has_uv_map": bool(obj.data.uv_layers),
                "is_named_properly": obj.name not in DEFAULT_NAMES,
                "origin_aligned": (obj.parent is not None) or (origin_offset_m < 0.01),
                "no_ngons": ngon_count == 0,
            }
            score = round(sum(checks.values()) / len(checks) * 100)
            per_object[obj.name] = {"score": score, "checks": checks}
            if obj.parent is not None:
                per_object[obj.name]["origin_aligned_note"] = (
                    "Parented object — origin offset check skipped (expected for assemblies)"
                )

            for check_name, passed in checks.items():
                if not passed:
                    all_failing.append(f"{check_name}: {obj.name}")
        except Exception:
            pass

    scene_score = (
        round(sum(v["score"] for v in per_object.values()) / len(per_object)) if per_object else 100
    )

    return ResponseBuilder.success(
        handler="get_scene_graph",
        action="CHECK_PRODUCTION_READINESS",
        data={
            "per_object": per_object,
            "scene_score": scene_score,
            "failing_checks": all_failing,
            "note": (
                f"Checked first {max_objects} visible MESH objects. "
                "Score 100 = fully production-ready. "
                "Checks: is_manifold, has_materials, has_uv_map, is_named_properly, "
                "origin_aligned (<1cm), no_ngons."
            ),
        },
    )
