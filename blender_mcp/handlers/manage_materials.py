"""
Material Management Handler for Blender MCP - V1.0.0 Refactored (SSOT)

Fixes:
- Implements MaterialAction Enum (SSOT)
- enhanced socket value type coercion
- Better Blender version compatibility

High Mode Philosophy: Maximum power, maximum safety.
"""

from typing import Dict, Any, Tuple, Optional

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.resolver import resolve_name
from ..core.thread_safety import ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.universal_coercion import TypeCoercer
from ..dispatcher import register_handler

# SSOT Imports
from ..core.enums import MaterialAction
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_materials",
    actions=[a.value for a in MaterialAction],
    category="material",
    priority=12,
    schema={
        "type": "object",
        "title": "Material Manager (CORE)",
        "description": (
            "CORE — Material creation, PBR configuration, and assignment to objects.\n\n"
            "Use to add color/texture/shader to objects after geometry is created.\n"
            "ACTIONS: CREATE, ASSIGN, SET_PBR_PROPERTY, SET_BASE_COLOR, DELETE, COPY, LIST"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(MaterialAction, "Operation to perform"),
            "material_name": {"type": "string", "description": "Target material name"},
            "object_name": {"type": "string", "description": "Target object to assign material to"},
            "object_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of target objects (for batch assigning)",
            },
            "pbr_property": {
                "type": "string",
                "description": "PBR property (base_color, metallic, roughness, etc.)",
            },
            "value": {
                "anyOf": [
                    {"type": "number"},
                    {"type": "array", "items": {"type": "number"}},
                    {"type": "string"},
                ],
                "description": "Value for PBR property (number, array, or hex color string)",
            },
            "color": {
                "anyOf": [
                    {"type": "array", "items": {"type": "number"}},
                    {"type": "string"},  # hex color support
                ],
                "description": "RGBA color for Base Color [r, g, b, a] or hex string #RRGGBB",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_materials(action: Optional[str] = None, **params):  # type: ignore[no-untyped-def]
    """
    Super-Tool for all Material operations.
    """
    if not action:
        # Fallback
        action = params.get("action")

    if not action:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=None,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    # Validate Action Enum
    validation_error = ValidationUtils.validate_enum(action, MaterialAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_materials", action=action
        )

    # Normalize parameters (Schema has changed to use Enum, but structure is similar)
    # Note: ParameterNormalizer might need the schema, which is attached to the function
    # but since we are inside the function, we can access it via the decorator or just use params directly
    # for simple cases. Here we trust ValidationUtils for the action, and manual checks for others.

    mat_name = params.get("material_name", "Material")

    # Route to handler
    try:
        if action == MaterialAction.CREATE.value:
            return _handle_create(mat_name, params)
        elif action == MaterialAction.LIST.value:
            return _handle_list(params)
        elif action == MaterialAction.DELETE.value:
            return _handle_delete(mat_name, params)
        elif action == MaterialAction.ASSIGN.value:
            return _handle_assign(mat_name, params)
        elif action.startswith("PRESET_"):  # Enum member values start with PRESET_
            # We can check specific enum members if needed, but this covers PRESET_METALLIC, etc.
            if action in [
                MaterialAction.PRESET_METALLIC.value,
                MaterialAction.PRESET_GLASS.value,
                MaterialAction.PRESET_EMISSION.value,
            ]:
                return _handle_preset(action, mat_name, params)
            else:
                # Should be unreachable due to validate_enum
                return ResponseBuilder.error(
                    handler="manage_materials",
                    action=action,
                    error_code="INVALID_ACTION",
                    message=f"Invalid preset: {action}",
                )
        elif action == MaterialAction.SET_PBR.value:
            return _handle_set_pbr(mat_name, params)
        else:
            return ResponseBuilder.error(
                handler="manage_materials",
                action=action,
                error_code="INVALID_ACTION",
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_materials.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_materials", action=action, error_code="EXECUTION_ERROR", message=str(e)
        )


def _handle_create(mat_name: str, params: Dict) -> Dict:
    """Create new material with node setup."""
    try:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True

        # Ensure Principled BSDF node exists
        tree = mat.node_tree
        if not tree:
            return ResponseBuilder.error(
                handler="manage_materials",
                action=MaterialAction.CREATE.value,
                error_code="EXECUTION_ERROR",
                message="Failed to create material node tree",
            )

        # Find or create Principled BSDF
        bsdf = _get_or_create_principled_bsdf(tree)

        # Set initial color if provided
        if "color" in params:
            color = _coerce_color_value(params["color"])
            if color:
                bsdf.inputs["Base Color"].default_value = color

        return ResponseBuilder.success(
            handler="manage_materials",
            action=MaterialAction.CREATE.value,
            data={"material": mat.name, "node_tree": tree is not None},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=MaterialAction.CREATE.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to create material: {str(e)}",
        )


def _handle_list(params: Dict) -> Dict:
    """List all materials."""
    mats = [m.name for m in bpy.data.materials]
    return ResponseBuilder.success(
        handler="manage_materials",
        action=MaterialAction.LIST.value,
        data={"count": len(mats), "materials": mats},
    )


def _handle_delete(mat_name: str, params: Dict) -> Dict:
    """Delete a material."""
    if mat_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[mat_name])
        return ResponseBuilder.success(
            handler="manage_materials",
            action=MaterialAction.DELETE.value,
            data={"deleted": mat_name},
        )
    return ResponseBuilder.error(
        handler="manage_materials",
        action=MaterialAction.DELETE.value,
        error_code="NO_MATERIAL",
        message=f"Material '{mat_name}' not found",
        details={"material_name": mat_name},
    )


def _handle_assign(mat_name: str, params: Dict) -> Dict:
    """Assign material to object(s)."""
    # V1.0.0 Fix: Resolver Violation + Batch Assignment
    obj_names = params.get("object_names", [])
    if "object_name" in params and params["object_name"]:
        obj_names.append(params["object_name"])

    objs = []
    if not obj_names:
        active = ContextManagerV3.get_active_object()
        if active:
            objs.append(active)
    else:
        for name in obj_names:
            resolved = resolve_name(name)
            if resolved:
                objs.append(resolved)

    mat = bpy.data.materials.get(mat_name)

    if not objs or not mat:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=MaterialAction.ASSIGN.value,
            error_code="OBJECT_NOT_FOUND",
            message="Objects or Material not found",
            details={"object_names": obj_names, "material_name": mat_name},
        )

    assigned_to = []

    for obj in objs:
        if not obj.data or not hasattr(obj.data, "materials"):
            continue

        # Fix: Clear existing materials to avoid Z-fighting/bleeding
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        assigned_to.append(obj.name)

    if not assigned_to:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=MaterialAction.ASSIGN.value,
            error_code="WRONG_OBJECT_TYPE",
            message="None of the objects support materials",
            details={"object_names": [o.name for o in objs]},
        )

    return ResponseBuilder.success(
        handler="manage_materials",
        action=MaterialAction.ASSIGN.value,
        data={
            "message": f"Assigned {mat.name} to {len(assigned_to)} objects",
            "assigned_to": assigned_to,
        },
    )


def _handle_preset(action: str, mat_name: str, params: Dict) -> Dict:
    """Handle material presets."""
    try:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True

        bsdf = _get_or_create_principled_bsdf(mat.node_tree)

        if action == MaterialAction.PRESET_METALLIC.value:
            bsdf.inputs["Metallic"].default_value = 1.0
            bsdf.inputs["Roughness"].default_value = 0.2

        elif action == MaterialAction.PRESET_GLASS.value:
            # Blender version compatibility
            _set_socket_safe(bsdf, "Transmission Weight", 1.0, fallback="Transmission")
            _set_socket_safe(bsdf, "IOR", 1.45)
            bsdf.inputs["Roughness"].default_value = 0.0

        elif action == MaterialAction.PRESET_EMISSION.value:
            _set_socket_safe(bsdf, "Emission Color", (1.0, 1.0, 1.0, 1.0), fallback="Emission")
            _set_socket_safe(bsdf, "Emission Strength", 5.0)

        return ResponseBuilder.success(
            handler="manage_materials", action=action, data={"material": mat.name, "preset": action}
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Failed to create preset: {str(e)}",
        )


def _handle_set_pbr(mat_name: str, params: Dict) -> Dict:
    """
    Set PBR properties with automatic type coercion.
    """
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=MaterialAction.SET_PBR.value,
            error_code="NO_MATERIAL",
            message=f"Material '{mat_name}' not found",
            details={"material_name": mat_name},
        )

    if not mat.use_nodes:
        mat.use_nodes = True

    bsdf = _get_or_create_principled_bsdf(mat.node_tree)

    prop = params.get("pbr_property", "")
    if not prop:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=MaterialAction.SET_PBR.value,
            error_code="MISSING_PARAMETER",
            message="pbr_property is required for SET_PBR",
        )

    # Normalize property name
    prop_normalized = prop.lower().replace(" ", "_").replace("-", "_")

    # Find socket with fuzzy matching
    socket = _find_socket_by_name(bsdf, prop_normalized)

    if not socket:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=MaterialAction.SET_PBR.value,
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Socket '{prop}' not found in Principled BSDF",
            details={"pbr_property": prop, "available_sockets": [s.name for s in bsdf.inputs]},
        )

    try:
        # Determine value type and coerce appropriately
        if prop_normalized in ("base_color", "color", "subsurface_color"):
            # FIXED: Handle both array and hex string colors
            color_input = params.get("color") or params.get("value")
            if color_input is None:
                return ResponseBuilder.error(
                    handler="manage_materials",
                    action=MaterialAction.SET_PBR.value,
                    error_code="MISSING_PARAMETER",
                    message="color or value required for base_color property",
                )

            coerced_color = _coerce_color_value(color_input)
            if coerced_color:
                socket.default_value = coerced_color
                return ResponseBuilder.success(
                    handler="manage_materials",
                    action=MaterialAction.SET_PBR.value,
                    data={"property": prop, "value": list(coerced_color)},
                )
            else:
                return ResponseBuilder.error(
                    handler="manage_materials",
                    action=MaterialAction.SET_PBR.value,
                    error_code="INVALID_PARAMETER_VALUE",
                    message=f"Invalid color value: {color_input}",
                    details={"color_input": str(color_input)},
                )

        else:
            # Numeric property
            value_input = params.get("value")
            if value_input is None:
                return ResponseBuilder.error(
                    handler="manage_materials",
                    action=MaterialAction.SET_PBR.value,
                    error_code="MISSING_PARAMETER",
                    message="value required for non-color property",
                )

            # Coerce to float
            coerced = TypeCoercer.coerce(value_input, "float")
            if not coerced.success:
                return ResponseBuilder.error(
                    handler="manage_materials",
                    action=MaterialAction.SET_PBR.value,
                    error_code="INVALID_PARAMETER_TYPE",
                    message=f"Failed to coerce value: {coerced.error}",
                    details={"value": str(value_input)},
                )

            socket.default_value = coerced.value
            return ResponseBuilder.success(
                handler="manage_materials",
                action=MaterialAction.SET_PBR.value,
                data={"property": prop, "value": coerced.value},
            )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_materials",
            action=MaterialAction.SET_PBR.value,
            error_code="EXECUTION_ERROR",
            message=f"Failed to set {prop}: {str(e)}",
            details={"pbr_property": prop, "socket_type": socket.type if socket else "unknown"},
        )


def _get_or_create_principled_bsdf(node_tree) -> Any:  # type: ignore[no-untyped-def]
    """Get existing Principled BSDF or create new one."""
    # Try to find existing
    for node in node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node

    # Create new
    bsdf = node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)

    # Connect to output if needed
    output = node_tree.nodes.get("Material Output")
    if output and "Surface" in output.inputs:
        node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    return bsdf


def _find_socket_by_name(bsdf, name: str) -> Any:  # type: ignore[no-untyped-def]
    """Find socket by name with fuzzy matching."""
    # Common mappings
    name_mappings = {
        "base_color": ["base_color", "base color"],
        "metallic": ["metallic"],
        "roughness": ["roughness"],
        "transmission": ["transmission weight", "transmission"],
        "emission": ["emission color", "emission"],
        "emission_strength": ["emission strength"],
        "ior": ["ior"],
        "alpha": ["alpha"],
    }

    # Check common names
    lookup = name_mappings.get(name, [name])

    for socket_name in lookup:
        for s in bsdf.inputs:
            if s.name.lower().replace(" ", "_") == socket_name:
                return s
            if s.name.lower() == socket_name:
                return s

    # Fallback: direct match
    return bsdf.inputs.get(name) if name in bsdf.inputs else None


def _set_socket_safe(bsdf, name: str, value, fallback: Optional[str] = None):  # type: ignore[no-untyped-def]
    """Set socket value with fallback for version compatibility."""
    socket = bsdf.inputs.get(name)
    if socket:
        socket.default_value = value
    elif fallback:
        socket = bsdf.inputs.get(fallback)
        if socket:
            socket.default_value = value


def _coerce_color_value(color_input) -> Optional[Tuple[float, float, float, float]]:  # type: ignore[no-untyped-def]
    """
    Coerce various color input formats to RGBA tuple.
    """
    if color_input is None:
        return None

    # If already a tuple/list
    if isinstance(color_input, (list, tuple)):
        if len(color_input) == 3:
            return (float(color_input[0]), float(color_input[1]), float(color_input[2]), 1.0)
        elif len(color_input) == 4:
            return (
                float(color_input[0]),
                float(color_input[1]),
                float(color_input[2]),
                float(color_input[3]),
            )
        else:
            return None

    # Hex string
    if isinstance(color_input, str):
        if color_input.startswith("#"):
            hex_str = color_input[1:]
            if len(hex_str) == 6:
                r = int(hex_str[0:2], 16) / 255.0
                g = int(hex_str[2:4], 16) / 255.0
                b = int(hex_str[4:6], 16) / 255.0
                return (r, g, b, 1.0)
            elif len(hex_str) == 8:
                r = int(hex_str[0:2], 16) / 255.0
                g = int(hex_str[2:4], 16) / 255.0
                b = int(hex_str[4:6], 16) / 255.0
                a = int(hex_str[6:8], 16) / 255.0
                return (r, g, b, a)

        # Named colors
        named_colors = {
            "red": (1.0, 0.0, 0.0, 1.0),
            "green": (0.0, 1.0, 0.0, 1.0),
            "blue": (0.0, 0.0, 1.0, 1.0),
            "white": (1.0, 1.0, 1.0, 1.0),
            "black": (0.0, 0.0, 0.0, 1.0),
            "gray": (0.5, 0.5, 0.5, 1.0),
            "yellow": (1.0, 1.0, 0.0, 1.0),
            "cyan": (0.0, 1.0, 1.0, 1.0),
            "magenta": (1.0, 0.0, 1.0, 1.0),
        }
        if color_input.lower() in named_colors:
            return named_colors[color_input.lower()]

    # Try coercion via TypeCoercer
    coerced = TypeCoercer.coerce(color_input, "array")
    if coerced.success and isinstance(coerced.value, (list, tuple)):
        return _coerce_color_value(coerced.value)

    return None
