"""
UV Editing Handler for Blender MCP - V1.0.0 Fixed

Fixes from test report:
- PACK scale parameter now properly coerced to boolean
- Enhanced parameter validation
- Better error context

High Mode Philosophy: Maximum power, maximum safety.
"""

try:
    import bpy

    # import bmesh # REMOVED F401

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.thread_safety import ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.universal_coercion import TypeCoercer, ParameterNormalizer
from ..core.smart_mode_manager import SmartModeManager
from ..core.enhanced_recovery import EnhancedRecovery, RetryPolicy
from ..core.validation_utils import ValidationUtils
from ..dispatcher import register_handler

from ..core.parameter_validator import validated_handler
from ..core.enums import UVsAction
from typing import Any

logger = get_logger()


@register_handler(
    "manage_uvs",
    actions=[a.value for a in UVsAction],
    category="uv",
    priority=35,
    schema={
        "type": "object",
        "title": "UV Manager (STANDARD)",
        "description": (
            "STANDARD — Complete UV workflow: unwrap, pack islands, transform, mark seams, "
            "UDIM tiles, UV channel management, export layout.\n\n"
            "Required before baking textures. Use UNWRAP first, then PACK to optimize UV space.\n"
            "ACTIONS: UNWRAP, PACK, TRANSFORM, MARK_SEAM, CLEAR_SEAM, CREATE_CHANNEL, "
            "SET_ACTIVE_CHANNEL, EXPORT_LAYOUT"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(UVsAction, "UV operation to perform"),
            "object_name": {"type": "string", "description": "Target object name"},
            "method": {
                "type": "string",
                "enum": ["SMART", "CONFORMAL", "ANGLE_BASED", "CUBE", "CYLINDER", "SPHERE"],
                "default": "SMART",
                "description": "Unwrap method",
            },
            "margin": {"type": "number", "default": 0.001, "description": "Pack margin (0-1)"},
            # FIXED: Separate parameters for transform vs pack
            "transform_scale": {
                "type": "number",
                "default": 1.0,
                "description": "Transform scale factor (for TRANSFORM action)",
            },
            "pack_scale": {
                "type": "boolean",
                "default": True,
                "description": "Scale islands to fill UV space (for PACK action)",
            },
            "rotation": {
                "type": "number",
                "default": 0.0,
                "description": "Transform rotation (degrees)",
            },
            "offset": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Translate UVs [u, v]",
            },
            "filepath": {"type": "string", "description": "Export file path (.png)"},
            "resolution": {
                "type": "integer",
                "default": 1024,
                "description": "Layout export resolution",
            },
            "channel_name": {"type": "string", "description": "UV channel/map name"},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in UVsAction])
def manage_uvs(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Advanced UV editing with UDIM support and layout export.

    Actions:
        - UNWRAP: Unwrap mesh using various methods
        - PACK: Pack UV islands with proper parameter handling
        - TRANSFORM: Transform UVs (scale, rotate, offset)
        - ADD_SEAM: Mark seams for unwrapping
        - And more...
    """
    if not action:
        return ResponseBuilder.error(
            handler="manage_uvs",
            action="UNKNOWN",
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    # Normalize parameters (handle synonyms, apply defaults)
    params = ParameterNormalizer.normalize(params, manage_uvs._handler_schema)

    # Get object
    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name) if obj_name else ContextManagerV3.get_active_object()

    if not obj or obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_uvs",
            action="UNKNOWN",
            error_code="NO_ACTIVE_OBJECT",
            message="Mesh object not found or not specified",
        )

    # Route to handler
    try:
        if action == UVsAction.UNWRAP.value:
            return _handle_unwrap(obj, params)  # type: ignore[no-any-return]
        elif action == UVsAction.PACK.value:
            return _handle_pack(obj, params)  # type: ignore[no-any-return]
        elif action == UVsAction.TRANSFORM.value:
            return _handle_transform(obj, params)  # type: ignore[no-any-return]
        elif action == UVsAction.ADD_SEAM.value:
            return _handle_add_seam(obj, params)  # type: ignore[no-any-return]
        elif action == UVsAction.CLEAR_SEAM.value:
            return _handle_clear_seam(obj, params)  # type: ignore[no-any-return]
        elif action == UVsAction.NEW_CHANNEL.value:
            return _handle_new_channel(obj, params)  # type: ignore[no-any-return]
        elif action == UVsAction.LIST_CHANNELS.value:
            return _handle_list_channels(obj, params)  # type: ignore[no-any-return]
        elif action == UVsAction.EXPORT_LAYOUT.value:
            return _handle_export_layout(obj, params)  # type: ignore[no-any-return]
        else:
            return ResponseBuilder.error(
                handler="manage_uvs",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_uvs.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_uvs", action=action, error_code="EXECUTION_ERROR", message=str(e)
        )


def _handle_unwrap(obj, params):  # type: ignore[no-untyped-def]
    """Handle UNWRAP action with method selection."""
    method = params.get("method", "SMART")

    def unwrap_operation():  # type: ignore[no-untyped-def]
        with SmartModeManager().mode_context(obj, "EDIT"):
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
            ):
                safe_ops.mesh.select_all(action="SELECT")

                if method == "SMART":
                    angle = params.get("angle_limit", 66.0)
                    margin = params.get("margin", 0.02)
                    safe_ops.uv.smart_project(
                        angle_limit=angle,
                        island_margin=margin,
                        correct_aspect=params.get("correct_aspect", True),
                        scale_to_bounds=params.get("scale_to_bounds", False),
                    )
                elif method == "CUBE":
                    safe_ops.uv.cube_project(
                        cube_size=params.get("cube_size", 1.0),
                        correct_aspect=params.get("correct_aspect", True),
                    )
                elif method == "CYLINDER":
                    safe_ops.uv.cylinder_project(
                        direction=params.get("cylinder_dir", "VIEW_ON_EQUATOR"),
                        correct_aspect=params.get("correct_aspect", True),
                    )
                elif method == "SPHERE":
                    safe_ops.uv.sphere_project(
                        direction=params.get("sphere_dir", "VIEW_ON_POLES"),
                        correct_aspect=params.get("correct_aspect", True),
                    )
                else:  # ANGLE_BASED or CONFORMAL
                    safe_ops.uv.unwrap(
                        method=method,
                        fill_holes=True,
                        correct_aspect=params.get("correct_aspect", True),
                    )

            return {
                "method": method,
                "object": obj.name,
                "uv_layer": obj.data.uv_layers.active.name if obj.data.uv_layers.active else None,
            }

    result = EnhancedRecovery.execute_with_recovery(
        unwrap_operation,
        retry_policy=RetryPolicy(max_attempts=2),
        tool="manage_uvs",
        action="UNWRAP",
        params=params,
    )

    if result.success:
        return ResponseBuilder.success(handler="manage_uvs", action="UNWRAP", data=result.result)
    else:
        return result.error


def _handle_pack(obj, params):  # type: ignore[no-untyped-def]
    """
    Handle PACK action with proper boolean coercion.

    FIX: scale parameter must be boolean for safe_ops.uv.pack_islands
    """
    margin = params.get("margin", 0.001)

    # FIXED: Proper parameter coercion
    # pack_scale should be boolean, not number
    scale_param = params.get("pack_scale", True)
    rotate_param = params.get("rotate", True)

    # Coerce to proper types
    scale_bool = TypeCoercer.coerce(scale_param, "bool").value if scale_param is not None else True
    rotate_bool = (
        TypeCoercer.coerce(rotate_param, "bool").value if rotate_param is not None else True
    )

    def pack_operation():  # type: ignore[no-untyped-def]
        with SmartModeManager().mode_context(obj, "EDIT"):
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
            ):
                safe_ops.uv.select_all(action="SELECT")

                # FIXED: scale must be boolean
                safe_ops.uv.pack_islands(
                    margin=float(margin),
                    rotate=rotate_bool,
                    scale=scale_bool,  # Now properly boolean
                )

            return {"margin": margin, "scale": scale_bool, "rotate": rotate_bool}

    result = EnhancedRecovery.execute_with_recovery(
        pack_operation,
        retry_policy=RetryPolicy(max_attempts=2),
        tool="manage_uvs",
        action="PACK",
        params=params,
    )

    if result.success:
        return ResponseBuilder.success(handler="manage_uvs", action="UV_LAYOUT", data=result.result)
    else:
        return result.error


def _handle_transform(obj, params):  # type: ignore[no-untyped-def]
    """Handle TRANSFORM action."""
    # Use transform_scale, not pack_scale
    scale = params.get("transform_scale", 1.0)
    rotation = params.get("rotation", 0.0)
    offset = params.get("offset", [0, 0])

    def transform_operation():  # type: ignore[no-untyped-def]
        with SmartModeManager().mode_context(obj, "EDIT"):
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
            ):
                # Scale
                if scale != 1.0:
                    safe_ops.transform.resize(value=(scale, scale, 1))

                # Rotate
                if rotation != 0.0:
                    import math

                    rad = math.radians(rotation)
                    safe_ops.transform.rotate(value=rad, orient_axis="Z")

                # Offset
                if offset and (offset[0] != 0 or offset[1] != 0):
                    safe_ops.transform.translate(value=(offset[0], offset[1], 0))

            return {"scale": scale, "rotation": rotation, "offset": offset}

    result = EnhancedRecovery.execute_with_recovery(
        transform_operation,
        retry_policy=RetryPolicy(max_attempts=2),
        tool="manage_uvs",
        action="TRANSFORM",
        params=params,
    )

    if result.success:
        return ResponseBuilder.success(handler="manage_uvs", action="ADD_SEAM", data=result.result)
    else:
        return result.error


def _handle_add_seam(obj, params):  # type: ignore[no-untyped-def]
    """Handle ADD_SEAM action."""

    def seam_operation():  # type: ignore[no-untyped-def]
        with SmartModeManager().mode_context(obj, "EDIT"):
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
            ):
                safe_ops.mesh.mark_seam(clear=False)
            return {"object": obj.name}

    result = EnhancedRecovery.execute_with_recovery(
        seam_operation,
        retry_policy=RetryPolicy(max_attempts=2),
        tool="manage_uvs",
        action="ADD_SEAM",
        params=params,
    )

    if result.success:
        return ResponseBuilder.success(
            handler="manage_uvs", action="CLEAR_SEAM", data=result.result
        )
    else:
        return result.error


def _handle_clear_seam(obj, params):  # type: ignore[no-untyped-def]
    """Handle CLEAR_SEAM action."""

    def seam_operation():  # type: ignore[no-untyped-def]
        with SmartModeManager().mode_context(obj, "EDIT"):
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
            ):
                safe_ops.mesh.mark_seam(clear=True)
            return {"object": obj.name}

    result = EnhancedRecovery.execute_with_recovery(
        seam_operation,
        retry_policy=RetryPolicy(max_attempts=2),
        tool="manage_uvs",
        action="CLEAR_SEAM",
        params=params,
    )

    if result.success:
        return ResponseBuilder.success(
            handler="manage_uvs", action="MARK_FREESTYLE_EDGE", data=result.result
        )
    else:
        return result.error


def _handle_new_channel(obj, params):  # type: ignore[no-untyped-def]
    """Handle NEW_CHANNEL action."""
    channel_name = params.get("channel_name", "UVMap")

    try:
        if channel_name not in obj.data.uv_layers:
            obj.data.uv_layers.new(name=channel_name)
            return ResponseBuilder.success(
                handler="manage_uvs",
                action="NEW_CHANNEL",
                data={"channel": channel_name, "created": True},
            )
        else:
            return ResponseBuilder.success(
                handler="manage_uvs",
                action="NEW_CHANNEL",
                data={"channel": channel_name, "created": False, "note": "Channel already exists"},
            )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_uvs",
            action="NEW_CHANNEL",
            error_code="EXECUTION_ERROR",
            message=f"Failed to create UV channel: {str(e)}",
        )


def _handle_list_channels(obj, params):  # type: ignore[no-untyped-def]
    """Handle LIST_CHANNELS action."""
    try:
        channels = [uv.name for uv in obj.data.uv_layers]
        active = obj.data.uv_layers.active.name if obj.data.uv_layers.active else None
        return ResponseBuilder.success(
            handler="manage_uvs",
            action="LIST_CHANNELS",
            data={"channels": channels, "active": active, "count": len(channels)},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_uvs",
            action="LIST_CHANNELS",
            error_code="EXECUTION_ERROR",
            message=f"Failed to list channels: {str(e)}",
        )


def _handle_export_layout(obj, params):  # type: ignore[no-untyped-def]
    """Handle EXPORT_LAYOUT action."""
    filepath = params.get("filepath")
    if not filepath:
        return ResponseBuilder.error(
            handler="manage_uvs",
            action="EXPORT_LAYOUT",
            error_code="MISSING_PARAMETER",
            message="filepath required for EXPORT_LAYOUT",
        )

    resolution = params.get("resolution", 1024)

    def export_operation():  # type: ignore[no-untyped-def]
        # Ensure we're in object mode for export
        with SmartModeManager().mode_context(obj, "OBJECT"):
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
            ):
                safe_ops.uv.export_layout(
                    filepath=filepath,
                    size=(resolution, resolution),
                    export_all=params.get("export_all", False),
                    modified=params.get("modified", False),
                    format=params.get("format", "PNG"),
                )
            return {"filepath": filepath, "resolution": resolution}

    result = EnhancedRecovery.execute_with_recovery(
        export_operation,
        retry_policy=RetryPolicy(max_attempts=2),
        tool="manage_uvs",
        action="EXPORT_LAYOUT",
        params=params,
    )

    if result.success:
        return ResponseBuilder.success(
            handler="manage_uvs", action="SPHERE_PROJECT", data=result.result
        )
    else:
        return result.error
