"""
Geometry Nodes Management Handler for Blender MCP - V1.0.0 Refactored (SSOT)

Fixes:
- Implements GeometryNodeAction Enum (SSOT)
- Enhanced node tree creation
- Robust validation

High Mode Philosophy: Maximum power, maximum safety.
"""

from typing import Any, Dict, Optional, Tuple

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.thread_safety import ensure_main_thread
from ..core.error_protocol import ErrorProtocol
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.universal_coercion import ParameterNormalizer
from ..dispatcher import register_handler

# SSOT Imports
from ..core.enums import GeometryNodeAction
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_geometry_nodes",
    actions=[a.value for a in GeometryNodeAction],
    category="geometry",
    priority=22,
    schema={
        "type": "object",
        "title": "Geometry Nodes Manager (CORE)",
        "description": (
            "CORE — Create and manage procedural Geometry Node trees: add nodes, connect sockets, "
            "set input values, apply as modifiers.\n\n"
            "Use for non-destructive procedural modeling. Prefer execute_blender_code for complex node graphs.\n"
            "ACTIONS: CREATE_TREE, ADD_NODE, CONNECT_NODES, SET_INPUT_VALUE, APPLY_MODIFIER, LIST_TREES"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(GeometryNodeAction, "Operation"),
            "object_name": {"type": "string", "description": "Target object name"},
            "tree_name": {"type": "string", "description": "Name for new tree"},
            "node_type": {
                "type": "string",
                "description": "Node type identifier (e.g., 'GeometryNodeMeshToPoints')",
            },
            "node_name": {"type": "string", "description": "Existing node name"},
            "from_node": {"type": "string", "description": "Source node name"},
            "to_node": {"type": "string", "description": "Target node name"},
            "socket_index_from": {"type": "integer", "default": 0},
            "socket_index_to": {"type": "integer", "default": 0},
            "input_name": {"type": "string", "description": "Input name on modifier"},
            "value": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                    {"type": "boolean"},
                    {"type": "array"},
                ],
                "description": "Value to set (auto-converted)",
            },
            "location": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Node location [x, y]",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_geometry_nodes(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Geometry Nodes Tools with enhanced error handling.
    """
    if not action:
        # Fallback
        action = params.get("action")

    if not action:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action="UNKNOWN",
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="Missing required parameter: 'action'",
        )

    # Validate Action Enum
    validation_error = ValidationUtils.validate_enum(action, GeometryNodeAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_geometry_nodes", action=action
        )

    # Normalize parameters
    # Note: ParameterNormalizer might need the schema attached to the function
    params = ParameterNormalizer.normalize(params, manage_geometry_nodes._handler_schema)

    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name) if obj_name else bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=action,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message="Object not found or not specified",
            details={"object_name": obj_name},
        )

    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=action,
            error_code=ErrorProtocol.WRONG_OBJECT_TYPE,
            message=f"Object {obj.name} is not a mesh (type: {obj.type})",
            details={"object_name": obj.name, "expected_type": "MESH", "actual_type": obj.type},
        )

    # Route to handler
    try:
        if action == GeometryNodeAction.CREATE_TREE.value:
            return _handle_create_tree(obj, params)
        elif action == GeometryNodeAction.ADD_NODE.value:
            return _handle_add_node(obj, params)
        elif action == GeometryNodeAction.LINK_NODES.value:
            return _handle_link_nodes(obj, params)
        elif action == GeometryNodeAction.SET_INPUT_VALUE.value:
            return _handle_set_input_value(obj, params)
        elif action == GeometryNodeAction.LIST_NODES.value:
            return _handle_list_nodes(obj, params)
        elif action == GeometryNodeAction.DELETE_NODE.value:
            return _handle_delete_node(obj, params)
        else:
            return ResponseBuilder.error(
                handler="manage_geometry_nodes",
                action=action,
                error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_geometry_nodes.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=action,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=str(e),
        )


def _get_or_create_modifier(obj: Any, mod_name: str = "GeometryNodes") -> Tuple[Any, bool]:
    """Get existing Geometry Nodes modifier or create new one."""
    for m in obj.modifiers:
        if m.type == "NODES":
            return m, False

    mod = obj.modifiers.new(name=mod_name, type="NODES")
    return mod, True


def _get_tree(mod: Any) -> Optional[Any]:
    """Get node tree from modifier."""
    if not mod:
        return None
    return mod.node_group


def _handle_create_tree(obj: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle CREATE_TREE action."""
    tree_name = params.get("tree_name", "GeoNodes")

    mod, is_new = _get_or_create_modifier(obj)

    if not mod:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.CREATE_TREE.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message="Failed to create Geometry Nodes modifier",
        )

    # Create new tree or use existing
    if not mod.node_group:
        tree = bpy.data.node_groups.new(name=tree_name, type="GeometryNodeTree")  # type: ignore
        mod.node_group = tree

        # Add Input/Output nodes
        in_node = tree.nodes.new("NodeGroupInput")
        out_node = tree.nodes.new("NodeGroupOutput")
        in_node.location.x = -200
        out_node.location.x = 200

        # Link geometry through
        if hasattr(in_node, "outputs") and hasattr(out_node, "inputs"):
            if "Geometry" in in_node.outputs and "Geometry" in out_node.inputs:
                tree.links.new(in_node.outputs["Geometry"], out_node.inputs["Geometry"])

        return ResponseBuilder.success(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.CREATE_TREE.value,
            data={"tree": tree.name, "modifier": mod.name, "created": True},
        )
    else:
        return ResponseBuilder.success(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.CREATE_TREE.value,
            data={
                "tree": mod.node_group.name,
                "modifier": mod.name,
                "created": False,
                "note": "Tree already exists",
            },
        )


_GEONODE_ALIASES: Dict[str, str] = {
    "MATH": "ShaderNodeMath",
    "VECTOR_MATH": "ShaderNodeVectorMath",
    "SET_POSITION": "GeometryNodeSetPosition",
    "MESH_TO_POINTS": "GeometryNodeMeshToPoints",
    "JOIN_GEOMETRY": "GeometryNodeJoinGeometry",
    "TRANSFORM": "GeometryNodeTransform",
    "BOUNDING_BOX": "GeometryNodeBoundBox",
    "INPUT_BOOL": "FunctionNodeInputBool",
    "INPUT_INT": "FunctionNodeInputInt",
    "INPUT_FLOAT": "FunctionNodeInputFloat",
}


def _handle_add_node(obj: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle ADD_NODE action."""
    mod, _ = _get_or_create_modifier(obj)

    if not mod or not mod.node_group:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.ADD_NODE.value,
            error_code=ErrorProtocol.NO_MESH_DATA,
            message="No Geometry Nodes modifier/tree found. Use CREATE_TREE first.",
        )

    tree = mod.node_group
    n_type = params.get("node_type")

    if not n_type:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.ADD_NODE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="node_type is required",
            details={"parameter": "node_type"},
        )

    # Accept short names like "MATH" in addition to full bl_idnames
    n_type = _GEONODE_ALIASES.get(n_type.upper(), n_type)

    try:
        node = tree.nodes.new(type=n_type)

        # Set custom name if provided
        if params.get("node_name"):
            node.name = params["node_name"]

        # Set location if provided
        if params.get("location"):
            loc = params["location"]
            if len(loc) >= 2:
                node.location = (loc[0], loc[1])

        return ResponseBuilder.success(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.ADD_NODE.value,
            data={"node": node.name, "type": n_type, "location": list(node.location)},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.ADD_NODE.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to add node: {str(e)}",
            details={"error": str(e)},
        )


def _handle_link_nodes(obj: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle LINK_NODES action."""
    mod, _ = _get_or_create_modifier(obj)

    if not mod or not mod.node_group:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.LINK_NODES.value,
            error_code=ErrorProtocol.NO_MESH_DATA,
            message="No Geometry Nodes modifier/tree found",
        )

    tree = mod.node_group
    f_name = params.get("from_node")
    t_name = params.get("to_node")

    if not f_name or not t_name:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.LINK_NODES.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="from_node and to_node are required",
            details={"from_node": f_name, "to_node": t_name},
        )

    f_node = tree.nodes.get(f_name)
    t_node = tree.nodes.get(t_name)

    if not f_node or not t_node:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.LINK_NODES.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message="One or both nodes not found",
            details={
                "from_node": f_name,
                "to_node": t_name,
                "from_found": f_node is not None,
                "to_found": t_node is not None,
            },
        )

    try:
        socket_from_idx = _resolve_socket_index(f_node.outputs, params.get("socket_index_from", 0))
        socket_to_idx = _resolve_socket_index(t_node.inputs, params.get("socket_index_to", 0))

        # Get sockets
        if socket_from_idx < len(f_node.outputs) and socket_to_idx < len(t_node.inputs):
            tree.links.new(f_node.outputs[socket_from_idx], t_node.inputs[socket_to_idx])
            return ResponseBuilder.success(
                handler="manage_geometry_nodes",
                action=GeometryNodeAction.LINK_NODES.value,
                data={"linked": True, "from_node": f_name, "to_node": t_name},
            )
        else:
            return ResponseBuilder.error(
                handler="manage_geometry_nodes",
                action=GeometryNodeAction.LINK_NODES.value,
                error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
                message="Invalid socket indices",
                details={
                    "socket_from_idx": socket_from_idx,
                    "socket_to_idx": socket_to_idx,
                    "available_from": len(f_node.outputs),
                    "available_to": len(t_node.inputs),
                },
            )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.LINK_NODES.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to link nodes: {str(e)}",
            details={"error": str(e)},
        )


def _resolve_socket_index(sockets: Any, key: Any) -> int:
    """
    Resolve socket index from integer index or string name.

    Args:
        sockets: Collection of NodeSocket
        key: Integer index or String name

    Returns:
        int: The resolved index

    Raises:
        ValueError: If key is invalid or not found
    """
    if isinstance(key, int):
        if 0 <= key < len(sockets):
            return key
        raise ValueError(f"Socket index {key} out of range (0-{len(sockets) - 1})")

    if isinstance(key, str):
        # Deterministic search: Use first match
        for i, socket in enumerate(sockets):
            if socket.name == key:
                # Log warning if duplicate names exist? (Optional, skipping for perf/simplicity as per plan)
                # But we could check if there are others. For now, first match is standard Blender behavior.
                return i

        # Also check identifier (rarely used but possible)
        for i, socket in enumerate(sockets):
            if socket.identifier == key:
                return i

        raise ValueError(f"Socket with name '{key}' not found")

    raise ValueError(f"Invalid socket key type: {type(key)}")


def _handle_set_input_value(obj: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle SET_INPUT_VALUE action."""
    mod, _ = _get_or_create_modifier(obj)

    if not mod:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.NO_MESH_DATA,
            message="No Geometry Nodes modifier found",
        )

    inp_name = params.get("input_name")
    val = params.get("value")

    if not inp_name:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="input_name is required",
            details={"parameter": "input_name"},
        )

    if val is None:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="value is required",
            details={"parameter": "value"},
        )

    try:
        # Try to find input on modifier
        if hasattr(mod, "inputs") and inp_name in mod.inputs:
            mod.inputs[inp_name].default_value = val
            return ResponseBuilder.success(
                handler="manage_geometry_nodes",
                action=GeometryNodeAction.SET_INPUT_VALUE.value,
                data={"input": inp_name, "value": val},
            )

        # Try accessing as attribute
        if hasattr(mod, inp_name):
            setattr(mod, inp_name, val)
            return ResponseBuilder.success(
                handler="manage_geometry_nodes",
                action=GeometryNodeAction.SET_INPUT_VALUE.value,
                data={"input": inp_name, "value": val},
            )

        # Try accessing via key (for custom properties)
        if inp_name in mod:
            mod[inp_name] = val
            return ResponseBuilder.success(
                handler="manage_geometry_nodes",
                action=GeometryNodeAction.SET_INPUT_VALUE.value,
                data={"input": inp_name, "value": val},
            )

        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
            message=f"Input '{inp_name}' not found on modifier",
            details={
                "input_name": inp_name,
                "available_inputs": [i.name for i in mod.inputs] if hasattr(mod, "inputs") else [],
            },
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to set input value: {str(e)}",
            details={"error": str(e)},
        )


def _handle_list_nodes(obj: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle LIST_NODES action."""
    mod, _ = _get_or_create_modifier(obj)

    if not mod or not mod.node_group:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.LIST_NODES.value,
            error_code=ErrorProtocol.NO_MESH_DATA,
            message="No Geometry Nodes modifier/tree found",
        )

    tree = mod.node_group
    nodes = []

    for node in tree.nodes:
        node_info = {
            "name": node.name,
            "type": node.type,
            "bl_idname": node.bl_idname,
            "location": list(node.location),
        }

        # Add input/output counts
        if hasattr(node, "inputs"):
            node_info["inputs"] = len(node.inputs)
        if hasattr(node, "outputs"):
            node_info["outputs"] = len(node.outputs)

        nodes.append(node_info)

    return ResponseBuilder.success(
        handler="manage_geometry_nodes",
        action=GeometryNodeAction.LIST_NODES.value,
        data={"tree": tree.name, "count": len(nodes), "nodes": nodes},
    )


def _handle_delete_node(obj: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle DELETE_NODE action."""
    mod, _ = _get_or_create_modifier(obj)

    if not mod or not mod.node_group:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.DELETE_NODE.value,
            error_code=ErrorProtocol.NO_MESH_DATA,
            message="No Geometry Nodes modifier/tree found",
        )

    tree = mod.node_group
    node_name = params.get("node_name")

    if not node_name:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.DELETE_NODE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="node_name is required",
            details={"parameter": "node_name"},
        )

    node = tree.nodes.get(node_name)
    if not node:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.DELETE_NODE.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Node not found: {node_name}",
            details={"node_name": node_name},
        )

    try:
        tree.nodes.remove(node)
        return ResponseBuilder.success(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.DELETE_NODE.value,
            data={"deleted": node_name},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes",
            action=GeometryNodeAction.DELETE_NODE.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to delete node: {str(e)}",
            details={"error": str(e)},
        )
