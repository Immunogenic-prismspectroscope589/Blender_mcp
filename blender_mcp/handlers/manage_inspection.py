from typing import List, Any
from ..utils.math import get_aabb

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
from ..dispatcher import register_handler


from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger

logger = get_logger()
# =============================================================================
# MANAGE INSPECTION: Object Introspection
# NOTE: get_scene_graph (priority=2, ESSENTIAL) is registered in manage_scene_comprehension.py (live-24)
# =============================================================================


@register_handler(
    "get_object_info",
    priority=4,
    schema={
        "type": "object",
        "title": "Get Object Info (TIER 1)",
        "description": (
            "TIER 1 INSPECTION — Deep per-object analysis including world-space coordinates, "
            "geometry center, origin offset, and animation override detection.\n\n"
            "KEY FIELDS:\n"
            "• world_location — Absolute world-space origin (parenting-aware). ALWAYS use this.\n"
            "• location — LOCAL (parent-relative). Shows [0,0,0] for many parented objects — DO NOT use.\n"
            "• geometry_center_world — Bounding-box center in world space. "
            "If different from world_location, the object's pivot is offset from its geometry.\n"
            "• origin_offset_m — Distance (meters) between origin and geometry center. "
            ">0.01m = origin_offset_warning=true → rotations will orbit around wrong point.\n"
            "• animation_data — Shows action name + fcurve count + NLA tracks. "
            "If has_animation=true, manual transform writes are OVERRIDDEN each frame. "
            "Fix: execute_blender_code → obj.animation_data_clear() before setting transforms.\n"
            "• world_bounding_box — AABB in world space (MESH only)."
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_object_info"],
                "default": "get_object_info",
            },
            "name": {"type": "string", "description": "Name of the object"},
            "object_name": {
                "type": "string",
                "description": "Alias for name (compatibility)",
            },
        },
        "required": ["action"],
    },
)
def get_object_info(**params):  # type: ignore[no-untyped-def]
    """Get detailed information about a specific object"""
    try:
        import mathutils
    except ImportError:
        mathutils = None  # type: ignore[assignment]

    # Support both 'name' and 'object_name' parameters for compatibility
    name = params.get("name") or params.get("object_name")
    if not name:
        return ResponseBuilder.error(
            handler="get_object_info",
            action="GET_INFO",
            error_code="MISSING_PARAMETER",
            message="Object name required",
        )

    obj = bpy.data.objects.get(name)
    if not obj and name.lower() in ["active", "selected"]:
        obj = bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="get_object_info",
            action="GET_INFO",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: {name}",
        )

    # Basic object info
    _mw = obj.matrix_world
    wx, wy, wz = _mw[0][3], _mw[1][3], _mw[2][3]
    obj_info = {
        "name": obj.name,
        "type": obj.type,
        "location": [obj.location.x, obj.location.y, obj.location.z],  # LOCAL (parent-relative)
        "world_location": [round(wx, 4), round(wy, 4), round(wz, 4)],
        "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
        "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
        "visible": not obj.hide_viewport,
        "parent": obj.parent.name if obj.parent else None,
        "materials": [],
    }

    # Geometry center + origin offset (bounding-box based, lightweight)
    if obj.type == "MESH" and obj.bound_box and mathutils:
        bb = obj.bound_box  # 8 corners in LOCAL space
        lc_x = sum(v[0] for v in bb) / 8
        lc_y = sum(v[1] for v in bb) / 8
        lc_z = sum(v[2] for v in bb) / 8
        wc = _mw @ mathutils.Vector((lc_x, lc_y, lc_z))
        offset = ((wc.x - wx) ** 2 + (wc.y - wy) ** 2 + (wc.z - wz) ** 2) ** 0.5
        obj_info["geometry_center_world"] = [round(wc.x, 4), round(wc.y, 4), round(wc.z, 4)]
        obj_info["origin_offset_m"] = round(offset, 4)
        obj_info["origin_offset_warning"] = offset > 0.01

    # World bounding box
    if obj.type == "MESH":
        try:
            bounding_box = get_aabb(obj)
            obj_info["world_bounding_box"] = bounding_box
        except Exception as e:
            print(f"Error getting AABB: {e}")

    # Animation data — critical for understanding transform override risk
    anim = obj.animation_data
    if anim:
        fcurve_count = len(anim.action.fcurves) if anim.action else 0
        transform_fcurves = []
        if anim.action:
            for fc in anim.action.fcurves:
                if fc.data_path in ("location", "rotation_euler", "scale", "rotation_quaternion"):
                    transform_fcurves.append(f"{fc.data_path}[{fc.array_index}]")
        obj_info["animation_data"] = {
            "has_animation": True,
            "action": anim.action.name if anim.action else None,
            "fcurve_count": fcurve_count,
            "transform_fcurves": transform_fcurves,
            "nla_tracks": len(anim.nla_tracks),
            "warning": (
                "This object has animation data. Manual transform writes (location/rotation/scale) "
                "will be OVERRIDDEN on the next frame evaluation. "
                "Run obj.animation_data_clear() via execute_blender_code before setting transforms."
            )
            if anim.action or anim.nla_tracks
            else None,
        }
    else:
        obj_info["animation_data"] = {"has_animation": False}

    # Material slots
    material_names: List[str] = []
    for slot in obj.material_slots:
        if slot.material:
            material_names.append(slot.material.name)
    obj_info["materials"] = material_names

    # Mesh topology
    if obj.type == "MESH" and obj.data:
        mesh = obj.data
        obj_info["mesh"] = {
            "vertices": len(mesh.vertices),  # type: ignore
            "edges": len(mesh.edges),  # type: ignore
            "polygons": len(mesh.polygons),  # type: ignore
        }

    return ResponseBuilder.success(handler="get_object_info", action="GET_INFO", data=obj_info)
