"""
get_local_transforms — LOCAL (parent-relative) transform inspector.

Shows location, rotation, scale in local (parent-relative) space.
Use get_scene_graph GET_OBJECTS_FLAT for world/geometry coordinates.
"""

from typing import Any

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..dispatcher import register_handler
from ..core.response_builder import ResponseBuilder
from ..core.thread_safety import ensure_main_thread


@register_handler(
    "get_local_transforms",
    priority=40,
    category="inspection",
    schema={
        "type": "object",
        "title": "Local / Parent-Relative Transforms",
        "description": (
            "STANDARD — Shows LOCAL (parent-relative) coordinates for objects.\n"
            "LOCAL = relative to parent. If parent is at world origin, local ≈ world.\n"
            "location=[0,0,0] is NORMAL for parented rig bones/meshes.\n"
            "Use get_scene_graph GET_OBJECTS_FLAT for world/geometry coordinates.\n"
            "ACTIONS: GET_LOCAL — returns location, rotation_euler, scale in local space."
        ),
        "properties": {
            "action": {"type": "string", "enum": ["GET_LOCAL"]},
            "object_name": {
                "type": "string",
                "description": "Object name (default: active object).",
            },
        },
        "required": ["action"],
    },
    actions=["GET_LOCAL"],
)
@ensure_main_thread
def get_local_transforms(action: str | None = None, **params: Any) -> dict[str, Any]:
    """Return LOCAL (parent-relative) transform data for an object."""
    obj_name = params.get("object_name")
    if obj_name:
        # Use direct name lookup — avoids StructRNA-freed issues from fuzzy resolver
        obj = bpy.data.objects.get(obj_name) if BPY_AVAILABLE else None
    else:
        obj = bpy.context.active_object if BPY_AVAILABLE else None

    if not obj:
        return ResponseBuilder.error(
            handler="get_local_transforms",
            action=action,
            error_code="OBJECT_NOT_FOUND",
            message="No object specified or no active object. Pass object_name parameter.",
        )

    try:
        _ = obj.name  # StructRNA validity guard
    except ReferenceError:
        return ResponseBuilder.error(
            handler="get_local_transforms",
            action=action,
            error_code="OBJECT_FREED",
            message="Object no longer exists in Blender memory (StructRNA freed).",
        )

    return ResponseBuilder.success(
        handler="get_local_transforms",
        action="GET_LOCAL",
        data={
            "object": obj.name,
            "parent": obj.parent.name if obj.parent else None,
            "location_local": [round(v, 6) for v in obj.location],
            "rotation_euler_local": [round(v, 6) for v in obj.rotation_euler],
            "rotation_degrees_local": [round(v * 57.2958, 4) for v in obj.rotation_euler],
            "scale_local": [round(v, 6) for v in obj.scale],
            "note": (
                "These are LOCAL (parent-relative) coordinates. "
                "location=[0,0,0] is NORMAL for objects parented to a rig/empty at origin. "
                "For world position, use get_scene_graph GET_OBJECTS_FLAT -> geometry_center_world."
            ),
        },
    )
