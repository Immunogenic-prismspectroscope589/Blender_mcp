"""
BMesh High-Performance Editing Handler for Blender MCP 1.0.0

Uses bmesh module for 1000x faster mesh operations than bpy.ops.

High Mode: Performance is not optional.
"""

from ..core.thread_safety import ensure_main_thread
from ..dispatcher import register_handler
from ..core.response_builder import ResponseBuilder
from ..core.bmesh_operations import BMeshOperations, BMeshTopologyAnalysis, BMeshUVOperations
from ..core.versioning import BlenderCompatibility
from ..core.enums import BMeshAction
from ..core.constants import BMeshDefaults
from ..core.validation_utils import ValidationUtils
from ..utils.error_handler import mcp_tool_handler
from typing import Any

try:
    import bpy
    import bmesh

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None
    bmesh = None


@register_handler(
    "manage_bmesh_edit",
    priority=17,
    schema={
        "type": "object",
        "title": "BMesh Editor (CORE)",
        "description": (
            "CORE — High-performance direct mesh editing via bmesh API: subdivide, extrude, "
            "bevel, inset, dissolve, merge, bridge, UV operations, topology analysis.\n\n"
            "1000x faster than bpy.ops for mesh edits. Prefer over manage_modeling when "
            "performance or precision matters.\n"
            "ACTIONS: SUBDIVIDE, EXTRUDE_FACES, INSET, BEVEL, DISSOLVE, MERGE, BRIDGE, "
            "ANALYZE_TOPOLOGY, UV_UNWRAP"
        ),
        "properties": {
            "action": {"type": "string", "enum": [e.value for e in BMeshAction]},
            "object_name": {"type": "string"},
            "object_index": {"type": "integer"},
            "selected_objects": {"type": "array", "items": {"type": "string"}},
            # Subdivide params
            "cuts": {"type": "integer", "default": BMeshDefaults.DEFAULT_CUTS},
            "use_smooth": {"type": "boolean", "default": False},
            "fractal": {"type": "number", "default": BMeshDefaults.DEFAULT_FRACTAL},
            "along_normal": {"type": "number", "default": 0.0},
            # Extrude params
            "faces": {"type": "array", "items": {"type": "integer"}},
            "normal_offset": {"type": "number", "default": BMeshDefaults.DEFAULT_EXTRUDE_OFFSET},
            "individual": {"type": "boolean", "default": False},
            # Inset params
            "thickness": {"type": "number", "default": BMeshDefaults.DEFAULT_INSET_THICKNESS},
            "depth": {"type": "number", "default": BMeshDefaults.DEFAULT_INSET_DEPTH},
            "use_even_offset": {"type": "boolean", "default": True},
            # Bevel params
            "edges": {"type": "array", "items": {"type": "integer"}},
            "offset": {"type": "number", "default": BMeshDefaults.DEFAULT_BEVEL_OFFSET},
            "offset_pct": {"type": "number", "description": "Legacy percent parameter (Bug 1A)"},
            "offset_type": {
                "type": "string",
                "enum": ["OFFSET", "WIDTH", "DEPTH", "PERCENT"],
                "default": "OFFSET",
            },
            "segments": {"type": "integer", "default": BMeshDefaults.DEFAULT_BEVEL_SEGMENTS},
            "profile": {"type": "number", "default": BMeshDefaults.DEFAULT_BEVEL_PROFILE},
            # Transform params (Bug 1B)
            # Note: "type" must be a string, not a list — ParameterValidator uses it as a dict key.
            # parse_vector() already handles both array and scalar float inputs.
            "translate": {"type": "array", "items": {"type": "number"}},
            "rotate": {"type": "array", "items": {"type": "number"}},
            "scale": {"type": "array", "items": {"type": "number"}},
            # Bridge params
            "edges_1": {"type": "array", "items": {"type": "integer"}},
            "edges_2": {"type": "array", "items": {"type": "integer"}},
            # Bisect params
            "plane_co": {"type": "array", "items": {"type": "number"}},
            "plane_no": {"type": "array", "items": {"type": "number"}},
            "clear_inner": {"type": "boolean", "default": False},
            "clear_outer": {"type": "boolean", "default": False},
            # Smooth params
            "vertices": {"type": "array", "items": {"type": "integer"}},
            "factor": {"type": "number", "default": BMeshDefaults.DEFAULT_SMOOTH_FACTOR},
            "iterations": {"type": "integer", "default": BMeshDefaults.DEFAULT_SMOOTH_ITERATIONS},
            # Merge params
            "distance": {"type": "number", "default": BMeshDefaults.DEFAULT_MERGE_DISTANCE},
            # UV unwrap
            "method": {
                "type": "string",
                "enum": ["ANGLE_BASED", "CONFORMAL"],
                "default": "ANGLE_BASED",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@mcp_tool_handler
def manage_bmesh_edit(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    High-performance mesh editing using BMesh.

    1000x faster than bpy.ops for batch operations.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bmesh_edit",
            action=action,
            error_code="NO_CONTEXT",
            message="Blender Python API not available",
        )

    # Get target object(s)
    obj = None
    if "object_name" in params:
        obj = bpy.data.objects.get(params.get("object_name"))
    elif "object_index" in params:
        obj = BlenderCompatibility.get_object_by_index(params.get("object_index"))
    else:
        # Use active object
        obj = bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_bmesh_edit",
            action=action,
            error_code="OBJECT_INVALID",
            message=f"Object not found: {params.get('object_name')}",
        )

    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_bmesh_edit",
            action=action,
            error_code="OBJECT_INVALID",
            message="Object is not a mesh",
        )

    try:
        if action == BMeshAction.SUBDIVIDE:
            return BMeshOperations.subdivide_mesh(  # type: ignore[no-any-return]
                obj,
                cuts=params.get("cuts", BMeshDefaults.DEFAULT_CUTS),
                use_smooth=params.get("use_smooth", False),
                fractal=params.get("fractal", BMeshDefaults.DEFAULT_FRACTAL),
                along_normal=params.get("along_normal", 0.0),
            )

        elif action == BMeshAction.EXTRUDE:
            return BMeshOperations.extrude_faces(  # type: ignore[no-any-return]
                obj,
                faces_indices=params.get("faces"),
                normal_offset=params.get("normal_offset", BMeshDefaults.DEFAULT_EXTRUDE_OFFSET),
                individual=params.get("individual", False),
            )

        elif action == BMeshAction.INSET:
            return BMeshOperations.inset_faces(  # type: ignore[no-any-return]
                obj,
                faces_indices=params.get("faces"),
                thickness=params.get("thickness", BMeshDefaults.DEFAULT_INSET_THICKNESS),
                depth=params.get("depth", BMeshDefaults.DEFAULT_INSET_DEPTH),
                use_even_offset=params.get("use_even_offset", True),
            )

        elif action == BMeshAction.TRANSFORM:
            # Bug 1B: Safe transform parsing for arrays or single floats
            scale = ValidationUtils.parse_vector(
                params.get("scale"), default=(1.0, 1.0, 1.0), is_scale=True
            )
            translate = ValidationUtils.parse_vector(
                params.get("translate"), default=(0.0, 0.0, 0.0)
            )
            rotate = ValidationUtils.parse_vector(params.get("rotate"), default=(0.0, 0.0, 0.0))
            return BMeshOperations.transform_mesh(  # type: ignore[no-any-return]
                obj,
                translate=translate,
                rotate=rotate,
                scale=scale,
                verts_indices=params.get("vertices"),
            )

        elif action == BMeshAction.BEVEL:
            offset = params.get("offset", BMeshDefaults.DEFAULT_BEVEL_OFFSET)
            offset_type = params.get("offset_type", "OFFSET")

            # Bug 1A Compatibility
            if "offset_pct" in params:
                offset_type = "PERCENT"
                offset = (
                    params.get("offset_pct") / 100.0
                    if bpy.app.version >= (5, 0, 0)
                    else params.get("offset_pct")
                )

            return BMeshOperations.bevel_edges(  # type: ignore[no-any-return]
                obj,
                edges_indices=params.get("edges"),
                offset=offset,
                offset_type=offset_type,
                segments=params.get("segments", BMeshDefaults.DEFAULT_BEVEL_SEGMENTS),
                profile=params.get("profile", BMeshDefaults.DEFAULT_BEVEL_PROFILE),
            )

        elif action == BMeshAction.DISSOLVE:
            return BMeshOperations.dissolve_faces(  # type: ignore[no-any-return]
                obj, faces_indices=params.get("faces"), use_verts=params.get("use_verts", False)
            )

        elif action == BMeshAction.BRIDGE:
            return BMeshOperations.bridge_edge_loops(  # type: ignore[no-any-return]
                obj,
                edges_indices_1=params.get("edges_1", []),
                edges_indices_2=params.get("edges_2", []),
            )

        elif action == BMeshAction.BISECT:
            plane_co = params.get("plane_co", [0, 0, 0])
            plane_no = params.get("plane_no", [0, 0, 1])
            return BMeshOperations.bisect_mesh(  # type: ignore[no-any-return]
                obj,
                plane_co=tuple(plane_co),
                plane_no=tuple(plane_no),
                clear_inner=params.get("clear_inner", False),
                clear_outer=params.get("clear_outer", False),
            )

        elif action == BMeshAction.SMOOTH:
            return BMeshOperations.smooth_vertices(  # type: ignore[no-any-return]
                obj,
                verts_indices=params.get("vertices"),
                factor=params.get("factor", BMeshDefaults.DEFAULT_SMOOTH_FACTOR),
                iterations=params.get("iterations", BMeshDefaults.DEFAULT_SMOOTH_ITERATIONS),
            )

        elif action == BMeshAction.RECALC_NORMALS:
            return BMeshOperations.recalc_normals(  # type: ignore[no-any-return]
                obj, faces_indices=params.get("faces"), inside=params.get("inside", False)
            )

        elif action == BMeshAction.MERGE_BY_DISTANCE:
            return BMeshOperations.merge_by_distance(  # type: ignore[no-any-return]
                obj,
                dist=params.get("distance", BMeshDefaults.DEFAULT_MERGE_DISTANCE),
                verts_indices=params.get("vertices"),
            )

        elif action == BMeshAction.ANALYZE:
            return BMeshTopologyAnalysis.analyze_mesh(obj)  # type: ignore[no-any-return]

        elif action == BMeshAction.SELECT_NON_MANIFOLD:
            return BMeshTopologyAnalysis.select_non_manifold(obj)

        elif action == BMeshAction.UNWRAP:
            return BMeshUVOperations.unwrap_basic(obj, method=params.get("method", "ANGLE_BASED"))

        else:
            return ResponseBuilder.error(
                handler="manage_bmesh_edit",
                action=action,
                error_code="MISSING_PARAMETER",
                message=f"Unknown bmesh action: {action}",
            )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_bmesh_edit",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"BMesh operation failed: {str(e)}",
        )
