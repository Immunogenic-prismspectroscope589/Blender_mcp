"""
Unity Objects Handler - V1.0.0 Refactored (SSOT)

Object management commands for Unity workflow:
- Primitive creation (optimized for Unity)
- Transform management
- Parenting and hierarchy
- Origin adjustment
- Visibility control
- Bounding box calculation
- Snapping

Part of 'unity_handler' modularization.
Implements Rules 1 (SSOT) and 9 (Zero Trust Input).
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import bpy
    import mathutils
else:
    try:
        import bpy
        import mathutils

        BPY_AVAILABLE = True
    except ImportError:
        BPY_AVAILABLE = False
        bpy = None
        mathutils = None

from ..core.context_manager_v3 import ContextManagerV3
from ..core.logging_config import get_logger
from ..core.response_builder import ResponseBuilder
from ..dispatcher import register_handler
from ..core.thread_safety import ensure_main_thread
from ..core.execution_engine import safe_ops

# SSOT Imports
from ..core.enums import UnityObjectAction
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@ensure_main_thread
def _create_primitive(params):  # type: ignore[no-untyped-def]
    """Create primitive objects - Complete Blender primitive library"""
    primitive_type = params.get("type", "cube").lower().replace("_", "").replace(" ", "")
    name = params.get("name")
    location = params.get("location", [0, 0, 0])
    size = params.get("size", 2.0)

    ContextManagerV3.deselect_all_objects()

    # BASIC PRIMITIVES
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        if primitive_type in ("cube", "box"):
            safe_ops.mesh.primitive_cube_add(size=size, location=location)

        # SPHERES
        elif primitive_type in ("sphere", "uvsphere", "uv_sphere", "ball"):
            radius = params.get("radius", size / 2)
            safe_ops.mesh.primitive_uv_sphere_add(radius=radius, location=location)
        elif primitive_type in ("icosphere", "ico_sphere", "icoball"):
            radius = params.get("radius", size / 2)
            subdivisions = params.get("subdivisions", 2)
            safe_ops.mesh.primitive_ico_sphere_add(
                radius=radius, subdivisions=subdivisions, location=location
            )

        # CYLINDRICAL
        elif primitive_type in ("cylinder", "tube"):
            radius = params.get("radius", size / 2)
            depth = params.get("depth", size)
            safe_ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location)
        elif primitive_type in ("cone", "pyramid"):
            radius = params.get("radius", size / 2)
            depth = params.get("depth", size)
            safe_ops.mesh.primitive_cone_add(radius1=radius, depth=depth, location=location)

        # TORUS
        elif primitive_type in ("torus", "donut", "ring"):
            major_radius = params.get("major_radius", size)
            minor_radius = params.get("minor_radius", size / 4)
            safe_ops.mesh.primitive_torus_add(
                major_radius=major_radius, minor_radius=minor_radius, location=location
            )

        # PLANES
        elif primitive_type in ("plane", "quad"):
            safe_ops.mesh.primitive_plane_add(size=size, location=location)
        elif primitive_type in ("grid", "meshgrid"):
            x_subdivisions = params.get("x_subdivisions", 10)
            y_subdivisions = params.get("y_subdivisions", 10)
            safe_ops.mesh.primitive_grid_add(
                x_subdivisions=x_subdivisions,
                y_subdivisions=y_subdivisions,
                size=size,
                location=location,
            )
        elif primitive_type in ("circle", "disk"):
            radius = params.get("radius", size / 2)
            vertices = params.get("vertices", 32)
            safe_ops.mesh.primitive_circle_add(radius=radius, vertices=vertices, location=location)

        # SPECIAL
        elif primitive_type in ("monkey", "suzanne", "suzan"):
            radius = params.get("radius", size / 2)
            safe_ops.mesh.primitive_monkey_add(size=radius, location=location)

        # DEFAULT ERROR
        else:
            return {
                "error": f"Unknown primitive type: {primitive_type}. Available: cube, sphere, icosphere, cylinder, cone, torus, plane, grid, circle, monkey"
            }

    obj = bpy.context.active_object
    if name:
        obj.name = name

    return {"success": True, "object_name": obj.name, "type": primitive_type}


def _delete_object(object_name):  # type: ignore[no-untyped-def]
    """Delete an object"""
    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}

    ContextManagerV3.deselect_all_objects()
    obj.select_set(True)
    with ContextManagerV3.temp_override(
        area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
    ):
        safe_ops.object.delete()

    return {"success": True, "deleted": object_name}


def _duplicate_object(object_name, params):  # type: ignore[no-untyped-def]
    """Duplicate an object"""
    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}

    ContextManagerV3.deselect_all_objects()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    linked = params.get("linked", False)

    with ContextManagerV3.temp_override(
        area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
    ):
        if linked:
            safe_ops.object.duplicate_move_linked()
        else:
            safe_ops.object.duplicate_move()

    new_obj = bpy.context.active_object
    return {"success": True, "original": object_name, "new_object": new_obj.name}


def _set_transform(object_name, params):  # type: ignore[no-untyped-def]
    """Set object transform"""
    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}

    if "location" in params:
        obj.location = mathutils.Vector(params["location"])
    if "rotation" in params:
        obj.rotation_euler = mathutils.Vector(params["rotation"])  # type: ignore
    if "scale" in params:
        obj.scale = mathutils.Vector(params["scale"])

    return {"success": True, "object": object_name, "location": list(obj.location)}  # type: ignore


def _apply_transform(object_name, params):  # type: ignore[no-untyped-def]
    """Apply transforms (Ctrl+A)"""
    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}

    ContextManagerV3.deselect_all_objects()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    types = params.get("types", ["LOCATION", "ROTATION", "SCALE"])

    for t in types:
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
        ):
            safe_ops.object.transform_apply(
                location=(t == "LOCATION"), rotation=(t == "ROTATION"), scale=(t == "SCALE")
            )

    return {"success": True, "object": object_name, "applied": types}


def _set_parent(object_name, params):  # type: ignore[no-untyped-def]
    """Set object parent"""
    obj = bpy.data.objects.get(object_name)
    parent_name = params.get("parent")
    keep_transform = params.get("keep_transform", True)

    if not obj:
        return {"error": f"Object not found: {object_name}"}

    if parent_name:
        parent = bpy.data.objects.get(parent_name)
        if not parent:
            return {"error": f"Parent not found: {parent_name}"}

        obj.parent = parent
        if keep_transform:
            obj.matrix_parent_inverse = parent.matrix_world.inverted()
    else:
        obj.parent = None

    return {"success": True, "object": object_name, "parent": parent_name}


def _set_origin(object_name, params):  # type: ignore[no-untyped-def]
    """Set object origin"""
    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}

    ContextManagerV3.deselect_all_objects()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    origin_type = params.get("type", "GEOMETRY_ORIGIN")

    if origin_type == "GEOMETRY_ORIGIN":
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
        ):
            safe_ops.object.origin_set(type="GEOMETRY_ORIGIN")
    elif origin_type == "ORIGIN_CENTER_OF_MASS":
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
        ):
            safe_ops.object.origin_set(type="ORIGIN_CENTER_OF_MASS")
    elif origin_type == "ORIGIN_CURSOR":
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
        ):
            safe_ops.object.origin_set(type="ORIGIN_CURSOR")
    elif origin_type == "ORIGIN_BOTTOM":
        bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
        min_z = min(v.z for v in bbox)
        center_x = (min(v.x for v in bbox) + max(v.x for v in bbox)) / 2
        center_y = (min(v.y for v in bbox) + max(v.y for v in bbox)) / 2

        bpy.context.scene.cursor.location = (center_x, center_y, min_z)
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
        ):
            safe_ops.object.origin_set(type="ORIGIN_CURSOR")

    return {"success": True, "object": object_name, "origin_type": origin_type}


def _set_visibility(object_name, params):  # type: ignore[no-untyped-def]
    """Set object visibility"""
    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}

    hide_viewport = params.get("hide_viewport")
    hide_render = params.get("hide_render")

    if hide_viewport is not None:
        obj.hide_set(hide_viewport)
    if hide_render is not None:
        obj.hide_render = hide_render

    return {"success": True, "object": object_name}


def _get_bounding_box(object_name):  # type: ignore[no-untyped-def]
    """Get world-space bounding box"""
    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}

    bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]

    min_corner = [min(c[i] for c in bbox_corners) for i in range(3)]
    max_corner = [max(c[i] for c in bbox_corners) for i in range(3)]
    dimensions = [max_corner[i] - min_corner[i] for i in range(3)]

    return {
        "success": True,
        "object": object_name,
        "min": min_corner,
        "max": max_corner,
        "dimensions": dimensions,
    }


def _snap_to_target(object_name, params):  # type: ignore[no-untyped-def]
    """Snap object to target surface or location"""
    obj = bpy.data.objects.get(object_name)
    target_name = params.get("target")
    target = bpy.data.objects.get(target_name)

    if not obj or not target:
        return {"error": "Object or Target not found"}

    method = params.get("method", "CLOSEST_POINT")
    offset = params.get("offset", [0, 0, 0])

    if method == "CLOSEST_POINT":
        depsgraph = bpy.context.evaluated_depsgraph_get()
        target_eval = target.evaluated_get(depsgraph)

        success, loc, norm, idx = target_eval.closest_point_on_mesh(obj.location)  # type: ignore

        if success:
            obj.location = loc + mathutils.Vector(offset)
            if params.get("align_rotation", False):
                obj.rotation_euler = norm.to_track_quat("Z", "Y").to_euler()
            return {"success": True, "snapped_to": list(loc)}
        else:
            return {"error": "Could not find closest point"}

    elif method == "CENTER":
        obj.location = target.location + mathutils.Vector(offset)
        return {"success": True, "snapped_to": list(target.location)}  # type: ignore

    return {"error": f"Unknown method: {method}"}


@register_handler(
    "unity_objects",
    schema={
        "type": "object",
        "title": "Unity Objects Manager",
        "description": "Object management commands for Unity workflow",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(UnityObjectAction, "Action to perform"),
            "object_name": {"type": "string"},
            "params": {"type": "object"},
        },
        "required": ["action"],
    },
    actions=[a.value for a in UnityObjectAction],
    category="unity",
)
@ensure_main_thread
def unity_objects(action: Optional[str] = None, **params):  # type: ignore[no-untyped-def]
    """Handle object management commands for Unity workflow"""
    if not action:
        # Fallback for old API if needed, though we discourage it
        action = params.get("action")

    if not action:
        return ResponseBuilder.error(
            handler="unity_objects",
            action=None,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    # Validate Action Enum
    validation_error = ValidationUtils.validate_enum(action, UnityObjectAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(validation_error, handler="unity_objects", action=action)

    object_name = params.get("object_name")
    action_params = params.get("params", {})

    if action == UnityObjectAction.CREATE_PRIMITIVE.value:
        if object_name and not action_params.get("name"):
            action_params["name"] = object_name
        return _create_primitive(action_params)
    elif action == UnityObjectAction.DELETE_OBJECT.value:
        return _delete_object(object_name)
    elif action == UnityObjectAction.DUPLICATE_OBJECT.value:
        return _duplicate_object(object_name, action_params)
    elif action == UnityObjectAction.SET_TRANSFORM.value:
        return _set_transform(object_name, action_params)
    elif action == UnityObjectAction.APPLY_TRANSFORM.value:
        return _apply_transform(object_name, action_params)
    elif action == UnityObjectAction.SET_PARENT.value:
        return _set_parent(object_name, action_params)
    elif action == UnityObjectAction.SET_ORIGIN.value:
        return _set_origin(object_name, action_params)
    elif action == UnityObjectAction.SET_VISIBILITY.value:
        return _set_visibility(object_name, action_params)
    elif action == UnityObjectAction.GET_BOUNDING_BOX.value:
        return _get_bounding_box(object_name)
    elif action == UnityObjectAction.SNAP_TO.value:
        return _snap_to_target(object_name, action_params)
    else:
        # Should be unreachable
        return ResponseBuilder.error(
            handler="unity_objects",
            action=action,
            error_code="INVALID_ACTION",
            message=f"Unknown action: {action}",
        )
