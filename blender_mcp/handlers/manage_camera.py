"""Camera Management Handler for Blender MCP - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

import math

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
import mathutils

from ..dispatcher import register_handler


from ..core.thread_safety import ensure_main_thread
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.enums import CameraAction
from ..core.validation_utils import ValidationUtils
from typing import Any

logger = get_logger()


@register_handler(
    "manage_camera",
    actions=[a.value for a in CameraAction],
    category="general",
    priority=18,
    schema={
        "type": "object",
        "title": "Camera Manager (CORE)",
        "description": (
            "CORE — Create and configure render cameras: focal length, depth of field, "
            "position, look-at targeting.\n\n"
            "Use to set up the render viewpoint before RENDER_FRAME.\n"
            "ACTIONS: CREATE, MODIFY, DELETE, SET_ACTIVE, LOOK_AT, LIST"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                CameraAction, "Camera operation to perform"
            ),
            "camera_name": {"type": "string", "description": "Name of the camera"},
            "location": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x, y, z] position",
            },
            "rotation": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x, y, z] Euler rotation in radians",
            },
            "target": {"type": "string", "description": "Object name to look at or frame"},
            "target_location": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x, y, z] point to look at",
            },
            "focal_length": {
                "type": "number",
                "default": 50.0,
                "description": "Lens focal length in mm",
            },
            "sensor_width": {
                "type": "number",
                "default": 36.0,
                "description": "Sensor width in mm",
            },
            "dof_distance": {"type": "number", "description": "Depth of field focus distance"},
            "f_stop": {
                "type": "number",
                "default": 2.8,
                "description": "F-stop value for depth of field",
            },
            "clip_start": {"type": "number", "default": 0.1},
            "clip_end": {"type": "number", "default": 1000.0},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_camera(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Comprehensive camera management for AAA rendering and Unity workflows.
    """
    validation_error = ValidationUtils.validate_enum(action, CameraAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(validation_error, handler="manage_camera", action=action)

    scene = bpy.context.scene

    # 1. CREATE CAMERA
    if action == CameraAction.CREATE.value:
        cam_name = params.get("camera_name", "Camera")

        # Create camera data
        cam_data = bpy.data.cameras.new(name=cam_name)
        cam_obj = bpy.data.objects.new(name=cam_name, object_data=cam_data)
        bpy.context.collection.objects.link(cam_obj)

        # Set location
        loc = params.get("location", (0, 0, 5))
        cam_obj.location = mathutils.Vector(loc)

        # Set rotation
        if "rotation" in params:
            cam_obj.rotation_euler = mathutils.Euler(params["rotation"])

        # Set lens properties
        if "focal_length" in params:
            cam_data.lens = params["focal_length"]
        if "sensor_width" in params:
            cam_data.sensor_width = params["sensor_width"]

        # Set clipping
        cam_data.clip_start = params.get("clip_start", 0.1)
        cam_data.clip_end = params.get("clip_end", 1000.0)

        # Auto-set as active if requested or if no active camera
        if params.get("set_active", True) or not scene.camera:
            scene.camera = cam_obj

        return ResponseBuilder.success(
            handler="manage_camera",
            action=CameraAction.CREATE.value,
            data={
                "camera": cam_obj.name,
                "location": list(cam_obj.location),  # type: ignore
                "focal_length": cam_data.lens,
                "is_active": scene.camera == cam_obj,
            },
        )

    # 2. SET ACTIVE CAMERA
    elif action == CameraAction.SET_ACTIVE.value:
        cam_name = params.get("camera_name")
        cam_obj = bpy.data.objects.get(cam_name)

        if not cam_obj or cam_obj.type != "CAMERA":
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.SET_ACTIVE.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Camera '{cam_name}' not found",
                details={"camera_name": cam_name},
            )

        scene.camera = cam_obj
        return ResponseBuilder.success(
            handler="manage_camera",
            action=CameraAction.SET_ACTIVE.value,
            data={"active_camera": cam_obj.name},
        )

    # 3. LOOK_AT
    elif action == CameraAction.LOOK_AT.value:
        cam_name = params.get("camera_name")
        cam_obj = bpy.data.objects.get(cam_name) if cam_name else scene.camera

        if not cam_obj or cam_obj.type != "CAMERA":
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.LOOK_AT.value,
                error_code="NO_ACTIVE_OBJECT",
                message="No camera found",
            )

        # Get target location
        target_loc = None
        if "target" in params:
            target_obj = bpy.data.objects.get(params["target"])
            if target_obj:
                target_loc = target_obj.location
        elif "target_location" in params:
            target_loc = mathutils.Vector(params["target_location"])

        if not target_loc:
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.LOOK_AT.value,
                error_code="MISSING_PARAMETER",
                message="No target specified. Provide 'target' or 'target_location'",
            )

        # Point camera at target
        direction = target_loc - cam_obj.location
        rot_quat = direction.to_track_quat("-Z", "Y")
        cam_obj.rotation_euler = rot_quat.to_euler()

        return ResponseBuilder.success(
            handler="manage_camera",
            action=CameraAction.LOOK_AT.value,
            data={
                "camera": cam_obj.name,
                "target": list(target_loc),  # type: ignore
                "rotation": list(cam_obj.rotation_euler),  # type: ignore
            },
        )

    # 4. SET_TRANSFORM
    elif action == CameraAction.SET_TRANSFORM.value:
        cam_name = params.get("camera_name")
        cam_obj = bpy.data.objects.get(cam_name) if cam_name else scene.camera

        if not cam_obj or cam_obj.type != "CAMERA":
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.SET_TRANSFORM.value,
                error_code="NO_ACTIVE_OBJECT",
                message="No camera found",
            )

        if "location" in params:
            cam_obj.location = mathutils.Vector(params["location"])
        if "rotation" in params:
            cam_obj.rotation_euler = mathutils.Euler(params["rotation"])

        return ResponseBuilder.success(
            handler="manage_camera",
            action=CameraAction.SET_TRANSFORM.value,
            data={"location": list(cam_obj.location), "rotation": list(cam_obj.rotation_euler)},  # type: ignore
        )

    # 5. SET_LENS
    elif action == CameraAction.SET_LENS.value:
        cam_name = params.get("camera_name")
        cam_obj = bpy.data.objects.get(cam_name) if cam_name else scene.camera

        if not cam_obj or cam_obj.type != "CAMERA":
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.SET_LENS.value,
                error_code="NO_ACTIVE_OBJECT",
                message="No camera found",
            )

        cam_data = cam_obj.data  # type: ignore

        if "focal_length" in params:
            cam_data.lens = params["focal_length"]
        if "sensor_width" in params:
            cam_data.sensor_width = params["sensor_width"]

        return ResponseBuilder.success(
            handler="manage_camera",
            action=CameraAction.SET_LENS.value,
            data={"focal_length": cam_data.lens, "sensor_width": cam_data.sensor_width},
        )

    # 6. SET_DOF (Depth of Field)
    elif action == CameraAction.SET_DOF.value:
        cam_name = params.get("camera_name")
        cam_obj = bpy.data.objects.get(cam_name) if cam_name else scene.camera

        if not cam_obj or cam_obj.type != "CAMERA":
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.SET_DOF.value,
                error_code="NO_ACTIVE_OBJECT",
                message="No camera found",
            )

        cam_data = cam_obj.data  # type: ignore

        # Enable DOF
        cam_data.dof.use_dof = True

        if "dof_distance" in params:
            cam_data.dof.focus_distance = params["dof_distance"]
        if "f_stop" in params:
            cam_data.dof.aperture_fstop = params["f_stop"]

        # Set focus object if provided
        if "target" in params:
            target_obj = bpy.data.objects.get(params["target"])
            if target_obj:
                cam_data.dof.focus_object = target_obj

        return ResponseBuilder.success(
            handler="manage_camera",
            action=CameraAction.SET_DOF.value,
            data={
                "dof_enabled": cam_data.dof.use_dof,
                "focus_distance": cam_data.dof.focus_distance,
                "f_stop": cam_data.dof.aperture_fstop,
            },
        )

    # 7. FRAME_OBJECT
    elif action == CameraAction.FRAME_OBJECT.value:
        cam_name = params.get("camera_name")
        cam_obj = bpy.data.objects.get(cam_name) if cam_name else scene.camera

        if not cam_obj or cam_obj.type != "CAMERA":
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.FRAME_OBJECT.value,
                error_code="NO_ACTIVE_OBJECT",
                message="No camera found",
            )

        target_name = params.get("target")
        target_obj = bpy.data.objects.get(target_name)

        if not target_obj:
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.FRAME_OBJECT.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Target '{target_name}' not found",
                details={"target_name": target_name},
            )

        # Get target bounds
        if target_obj.type == "MESH":
            # Calculate bounding sphere center and radius
            bbox_corners = [
                target_obj.matrix_world @ mathutils.Vector(corner)
                for corner in target_obj.bound_box
            ]
            center = sum(bbox_corners, mathutils.Vector()) / 8

            # Calculate radius
            max_dist = max((corner - center).length for corner in bbox_corners)

            # Position camera
            cam_data = cam_obj.data  # type: ignore
            focal_length = cam_data.lens
            sensor_width = cam_data.sensor_width

            # Calculate distance to fit object in frame
            # Use math module for trigonometric functions, NOT mathutils.noise
            fov = 2 * math.atan2(sensor_width / 2, focal_length)
            distance = (max_dist * 1.5) / math.tan(fov / 2)

            # Position camera
            direction = (cam_obj.location - center).normalized()
            cam_obj.location = center + direction * distance

            # Look at center
            rot_quat = (center - cam_obj.location).to_track_quat("-Z", "Y")
            cam_obj.rotation_euler = rot_quat.to_euler()

            return ResponseBuilder.success(
                handler="manage_camera",
                action=CameraAction.FRAME_OBJECT.value,
                data={
                    "target": target_name,
                    "distance": distance,
                    "location": list(cam_obj.location),  # type: ignore
                },
            )
        else:
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.FRAME_OBJECT.value,
                error_code="WRONG_OBJECT_TYPE",
                message=f"Target must be a mesh object, got: {target_obj.type}",
            )

    # 8. LIST_CAMERAS
    elif action == CameraAction.LIST_CAMERAS.value:
        cameras = [
            {
                "name": obj.name,
                "is_active": obj == scene.camera,
                "location": list(obj.location),  # type: ignore
                "focal_length": obj.data.lens,  # type: ignore
            }
            for obj in bpy.data.objects
            if obj.type == "CAMERA"
        ]

        return ResponseBuilder.success(
            handler="manage_camera",
            action=CameraAction.LIST_CAMERAS.value,
            data={
                "count": len(cameras),
                "cameras": cameras,
                "active": scene.camera.name if scene.camera else None,
            },
        )

    # 9. DELETE
    elif action == CameraAction.DELETE.value:
        cam_name = params.get("camera_name")
        cam_obj = bpy.data.objects.get(cam_name)

        if not cam_obj or cam_obj.type != "CAMERA":
            return ResponseBuilder.error(
                handler="manage_camera",
                action=CameraAction.DELETE.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Camera '{cam_name}' not found",
                details={"camera_name": cam_name},
            )

        # Remove camera data
        cam_data = cam_obj.data  # type: ignore

        # Delete object
        bpy.data.objects.remove(cam_obj, do_unlink=True)

        # Also remove camera data if no other users
        if cam_data.users == 0:
            bpy.data.cameras.remove(cam_data)

        return ResponseBuilder.success(
            handler="manage_camera", action=CameraAction.DELETE.value, data={"deleted": cam_name}
        )

    return ResponseBuilder.error(
        handler="manage_camera",
        action=action,
        error_code="INVALID_ACTION",
        message=f"Unknown action: {action}",
    )
