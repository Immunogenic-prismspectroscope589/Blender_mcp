"""
Compositing Node Management Handler for Blender MCP - V1.0.0 Fixed

Fixes from test report:
- Scene.node_tree access now uses safe API compatibility layer
- Blender 5.0+ compositor initialization with proper node tree creation
- Enhanced error context for compositor failures

High Mode Philosophy: Maximum power, maximum safety.
"""

from typing import Dict, Any, Tuple

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
from ..core.enums import CompositingAction
from ..core.validation_utils import ValidationUtils
from ..dispatcher import register_handler
from ..utils.error_handler import mcp_tool_handler

logger = get_logger()


@register_handler(
    "manage_compositing",
    actions=[a.value for a in CompositingAction],
    category="compositing",
    schema={
        "type": "object",
        "title": "Compositor Manager",
        "description": (
            "STANDARD — Compositor node graph manager.\n"
            "ACTIONS: ENABLE_NODES, ADD_NODE, DELETE_NODE, LINK_NODES, UNLINK_NODES, "
            "CLEAR_NODES, LIST_NODES, GET_NODE_INPUTS, GET_NODE_OUTPUTS, "
            "SET_INPUT_VALUE, GET_INPUT_VALUE, AUTO_LAYOUT, CREATE_COMMON_SETUP\n\n"
            "NOTE: Compositor runs post-render. Call ENABLE_NODES first to activate Use Nodes. "
            "Changes affect all renders until disabled. "
            "CREATE_COMMON_SETUP adds Render Layers → Composite → Viewer in one call."
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                CompositingAction, "Operation to perform"
            ),
            "node_type": {
                "type": "string",
                "description": "Blender Node Type identifier (e.g. CompositorNodeBlur)",
            },
            "node_name": {"type": "string", "description": "Existing node name"},
            "new_node_name": {"type": "string", "description": "Custom name for new node"},
            "from_node": {"type": "string"},
            "from_socket": {"type": "integer", "default": 0},
            "from_socket_name": {"type": "string"},
            "to_node": {"type": "string"},
            "to_socket": {"type": "integer", "default": 0},
            "to_socket_name": {"type": "string"},
            "socket_name": {"type": "string"},
            "socket_index": {"type": "integer"},
            "value": {
                "anyOf": [
                    {"type": "number"},
                    {"type": "array", "items": {"type": "number"}},
                    {"type": "boolean"},
                    {"type": "string"},
                ]
            },
            "node_params": {"type": "object"},
            "location": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x, y] location in node editor",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@mcp_tool_handler
def manage_compositing(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Advanced compositor tools with full node introspection and manipulation.

    FIXED: Uses BlenderCompatibility for safe scene.node_tree access
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=action or "UNKNOWN",
            error_code=ErrorProtocol.NO_CONTEXT,
            message="Blender Python API not available",
        )

    validation_error = ValidationUtils.validate_enum(action, CompositingAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_compositing", action=action
        )

    # Normalize parameters
    params = ParameterNormalizer.normalize(params, manage_compositing._handler_schema)

    scene = bpy.context.scene

    # ENABLE_NODES - Initialize compositor
    if action == CompositingAction.ENABLE_NODES.value:
        return _handle_enable_nodes(scene, params)  # type: ignore[no-any-return]

    # Get or create compositor tree
    tree_result = _get_compositor_tree(scene, create=True)
    if not tree_result["success"]:
        return tree_result

    tree = tree_result["tree"]

    # Route to handler
    try:
        if action == CompositingAction.ADD_NODE.value:
            return _handle_add_node(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.DELETE_NODE.value:
            return _handle_delete_node(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.LINK_NODES.value:
            return _handle_link_nodes(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.UNLINK_NODES.value:
            return _handle_unlink_nodes(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.CLEAR_NODES.value:
            return _handle_clear_nodes(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.LIST_NODES.value:
            return _handle_list_nodes(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.GET_NODE_INPUTS.value:
            return _handle_get_node_ios(tree, params, io_kind="inputs")  # type: ignore[no-any-return]
        elif action == CompositingAction.GET_NODE_OUTPUTS.value:
            return _handle_get_node_ios(tree, params, io_kind="outputs")  # type: ignore[no-any-return]
        elif action == CompositingAction.SET_INPUT_VALUE.value:
            return _handle_set_input(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.GET_INPUT_VALUE.value:
            return _handle_get_input(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.AUTO_LAYOUT.value:
            return _handle_auto_layout(tree, params)  # type: ignore[no-any-return]
        elif action == CompositingAction.CREATE_COMMON_SETUP.value:
            return _handle_create_common_setup(tree, params)  # type: ignore[no-any-return]
        else:
            return ResponseBuilder.error(
                handler="manage_compositing",
                action=action,
                error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_compositing.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=action,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=str(e),
        )


def _get_compositor_tree(scene, create=False) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    """
    Get compositor node tree with automatic creation and Blender 5.0+ lifecycle guard.
    In Blender 5.0+, scene.use_nodes = True avoids creating tree instantly.
    """
    # Blender < 5.0 uses node_tree, Blender 5.0+ uses compositing_node_group
    tree = getattr(scene, "node_tree", None) or getattr(scene, "compositing_node_group", None)

    if tree and scene.use_nodes:
        return {"success": True, "tree": tree}

    if not create:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.ENABLE_NODES.value,
            error_code=ErrorProtocol.NO_CONTEXT,
            message="Compositor not enabled. Use ENABLE_NODES action first.",
        )

    try:
        # Step 1: Enable nodes
        scene.use_nodes = True

        # Step 2: Force evaluation or manual creation if missing (Blender 5.0+ headless behavior)
        if not getattr(scene, "node_tree", None) and not getattr(
            scene, "compositing_node_group", None
        ):
            try:
                # Need VIEW_3D to update view layer or run some ops, but let's just try updating:
                bpy.context.view_layer.update()
            except:
                pass

            # If still None, manually create and assign (Blender 5.0+ Node Group approach)
            if not getattr(scene, "node_tree", None) and not getattr(
                scene, "compositing_node_group", None
            ):
                new_tree = bpy.data.node_groups.new(name="Compositor", type="CompositorNodeTree")
                if hasattr(scene, "compositing_node_group"):
                    scene.compositing_node_group = new_tree
                elif hasattr(scene, "node_tree"):
                    # node_tree is usually read-only, but let's fallback if possible
                    try:
                        scene.node_tree = new_tree
                    except AttributeError:
                        pass  # read-only on older versions, shouldn't reach here if it was NONE

        tree = getattr(scene, "node_tree", None) or getattr(scene, "compositing_node_group", None)

        if tree:
            _ensure_basic_nodes(tree)
            return {"success": True, "tree": tree}

        # Final fallback - could occur in headless without proper rendering setups
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.ENABLE_NODES.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message="Could not initialize compositor node tree in current Blender version context.",
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.ENABLE_NODES.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to initialize compositor: {str(e)}",
        )


def _get_or_create_io_nodes(tree: Any) -> Tuple[Any, Any]:
    # Find or create Render Layers / Group Input
    rl = tree.nodes.get("Render Layers") or tree.nodes.get("Group Input")
    if not rl:
        try:
            rl = tree.nodes.new(type="CompositorNodeRLayers")
            rl.name = "Render Layers"
        except RuntimeError:
            rl = tree.nodes.new(type="NodeGroupInput")
            rl.name = "Group Input"
        rl.location = (-300, 0)

    # Find or create Composite / Group Output
    comp = tree.nodes.get("Composite") or tree.nodes.get("Group Output")
    if not comp:
        try:
            comp = tree.nodes.new(type="CompositorNodeComposite")
            comp.name = "Composite"
        except RuntimeError:
            comp = tree.nodes.new(type="NodeGroupOutput")
            comp.name = "Group Output"
        comp.location = (300, 0)

    return rl, comp


def _ensure_basic_nodes(tree):  # type: ignore[no-untyped-def]
    """Ensure Render Layers and Composite nodes exist."""
    rl, comp = _get_or_create_io_nodes(tree)

    # Link if not already linked (Safe access via inputs)
    try:
        comp_in = comp.inputs["Image"] if "Image" in comp.inputs else comp.inputs[0]
        rl_out = rl.outputs["Image"] if "Image" in rl.outputs else rl.outputs[0]

        if not any(link.to_socket == comp_in for link in comp_in.links):
            tree.links.new(rl_out, comp_in)
    except Exception:
        pass


def _handle_enable_nodes(scene, params):  # type: ignore[no-untyped-def]
    """Enable compositor nodes."""
    result = _get_compositor_tree(scene, create=True)
    if result.get("success"):
        return ResponseBuilder.success(
            handler="manage_compositing",
            action=CompositingAction.ENABLE_NODES.value,
            data={
                "message": "Compositing Nodes Enabled",
                "tree_type": (
                    result["tree"].bl_idname
                    if hasattr(result["tree"], "bl_idname")
                    else "CompositorNodeTree"
                ),
            },
        )
    else:
        return result


_COMPOSITOR_NODE_ALIASES: dict[str, str] = {
    "BLUR": "CompositorNodeBlur",
    "GLARE": "CompositorNodeGlare",
    "MIX": "CompositorNodeMixRGB",
    "LEVELS": "CompositorNodeLevels",
    "BRIGHTNESS_CONTRAST": "CompositorNodeBrightContrast",
    "RGB_CURVES": "CompositorNodeCurveRGB",
    "ALPHA_OVER": "CompositorNodeAlphaOver",
    "COLOR_CORRECTION": "CompositorNodeColorCorrection",
    "VIEWER": "CompositorNodeViewer",
    "COMPOSITE": "CompositorNodeComposite",
    "RENDER_LAYERS": "CompositorNodeRLayers",
    "DENOISE": "CompositorNodeDenoise",
    "TONEMAP": "CompositorNodeTonemap",
}


def _handle_add_node(tree, params):  # type: ignore[no-untyped-def]
    """Add a new node."""
    n_type = params.get("node_type")
    if not n_type:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.ADD_NODE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="node_type is required",
            details={"parameter": "node_type"},
        )

    # Accept short names like "BLUR" in addition to full bl_idnames
    n_type = _COMPOSITOR_NODE_ALIASES.get(n_type.upper(), n_type)

    try:
        node = tree.nodes.new(type=n_type)
    except RuntimeError as e:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.ADD_NODE.value,
            error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
            message=f"Invalid node_type '{n_type}': {str(e)}",
            details={"parameter": "node_type", "value": n_type},
        )

    # Apply custom name
    if params.get("new_node_name"):
        node.name = params["new_node_name"]

    # Apply location
    if params.get("location"):
        loc = params["location"]
        node.location = (loc[0], loc[1])

    # Apply params
    n_params = params.get("node_params", {})
    for k, v in n_params.items():
        if hasattr(node, k):
            setattr(node, k, v)
        elif k in node.inputs:
            node.inputs[k].default_value = v

    return ResponseBuilder.success(
        handler="manage_compositing",
        action=CompositingAction.ADD_NODE.value,
        data={
            "node_name": node.name,
            "node_type": node.type,
            "bl_idname": node.bl_idname,
            "created": True,
        },
    )


def _handle_delete_node(tree, params):  # type: ignore[no-untyped-def]
    """Delete a node."""
    node_name = params.get("node_name")
    if not node_name:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.DELETE_NODE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="node_name is required",
            details={"parameter": "node_name"},
        )

    node = tree.nodes.get(node_name)
    if not node:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.DELETE_NODE.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Node not found: {node_name}",
            details={"node_name": node_name},
        )

    tree.nodes.remove(node)
    return ResponseBuilder.success(
        handler="manage_compositing",
        action=CompositingAction.DELETE_NODE.value,
        data={"deleted": node_name},
    )


def _handle_link_nodes(tree, params):  # type: ignore[no-untyped-def]
    """Link two nodes."""
    f_name = params.get("from_node")
    t_name = params.get("to_node")

    f_node = tree.nodes.get(f_name)
    t_node = tree.nodes.get(t_name)

    if not f_node or not t_node:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.LINK_NODES.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message="One or both nodes not found",
            details={"from_node": f_name, "to_node": t_name},
        )

    # Get output socket
    if params.get("from_socket_name"):
        f_socket = f_node.outputs.get(params["from_socket_name"])
    else:
        f_idx = params.get("from_socket", 0)
        f_socket = f_node.outputs[f_idx] if f_idx < len(f_node.outputs) else None

    # Get input socket
    if params.get("to_socket_name"):
        t_socket = t_node.inputs.get(params["to_socket_name"])
    else:
        t_idx = params.get("to_socket", 0)
        t_socket = t_node.inputs[t_idx] if t_idx < len(t_node.inputs) else None

    if not f_socket or not t_socket:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.LINK_NODES.value,
            error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
            message="Invalid socket indices",
            details={
                "from_socket": params.get("from_socket"),
                "to_socket": params.get("to_socket"),
            },
        )

    tree.links.new(f_socket, t_socket)
    return ResponseBuilder.success(
        handler="manage_compositing",
        action=CompositingAction.LINK_NODES.value,
        data={"from": f_name, "to": t_name},
    )


def _handle_unlink_nodes(tree, params):  # type: ignore[no-untyped-def]
    """Unlink a node connection."""
    node_name = params.get("node_name")
    socket_name = params.get("socket_name")

    node = tree.nodes.get(node_name)
    if not node:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.UNLINK_NODES.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Node not found: {node_name}",
            details={"node_name": node_name},
        )

    if socket_name and socket_name in node.inputs:
        socket = node.inputs[socket_name]
    elif params.get("socket_index") is not None:
        idx = params["socket_index"]
        if idx < len(node.inputs):
            socket = node.inputs[idx]
        else:
            return ResponseBuilder.error(
                handler="manage_compositing",
                action=CompositingAction.UNLINK_NODES.value,
                error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
                message="Invalid socket index",
                details={"socket_index": params.get("socket_index")},
            )
    else:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.UNLINK_NODES.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="socket_name or socket_index required",
            details={"parameters": ["socket_name", "socket_index"]},
        )

    # Remove links
    for link in list(socket.links):
        tree.links.remove(link)

    return ResponseBuilder.success(
        handler="manage_compositing",
        action=CompositingAction.UNLINK_NODES.value,
        data={"unlinked": socket.name},
    )


def _handle_clear_nodes(tree, params):  # type: ignore[no-untyped-def]
    """Clear all nodes except basic ones."""
    keep_basic = params.get("keep_basic", True)

    nodes_to_remove = []
    for node in tree.nodes:
        if keep_basic and node.name in ["Render Layers", "Composite"]:
            continue
        nodes_to_remove.append(node)

    for node in nodes_to_remove:
        tree.nodes.remove(node)

    return ResponseBuilder.success(
        handler="manage_compositing",
        action=CompositingAction.CLEAR_NODES.value,
        data={"cleared": len(nodes_to_remove)},
    )


def _handle_list_nodes(tree, params):  # type: ignore[no-untyped-def]
    """List all nodes in the tree."""
    nodes = []
    for node in tree.nodes:
        node_info = {
            "name": node.name,
            "type": node.type,
            "bl_idname": node.bl_idname,
            "location": list(node.location),
        }
        nodes.append(node_info)

    return ResponseBuilder.success(
        handler="manage_compositing",
        action=CompositingAction.LIST_NODES.value,
        data={"nodes": nodes, "count": len(nodes)},
    )


def _handle_get_node_ios(tree, params, io_kind: str):  # type: ignore[no-untyped-def]
    """Return input/output socket metadata for a specific node."""
    action_value = (
        CompositingAction.GET_NODE_INPUTS.value
        if io_kind == "inputs"
        else CompositingAction.GET_NODE_OUTPUTS.value
    )
    node_name = params.get("node_name")
    if not node_name:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=action_value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="node_name is required",
            details={"parameter": "node_name"},
        )

    node = tree.nodes.get(node_name)
    if not node:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=action_value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Node not found: {node_name}",
            details={"node_name": node_name},
        )

    sockets = node.inputs if io_kind == "inputs" else node.outputs
    socket_data = []
    for index, socket in enumerate(sockets):
        socket_data.append(
            {
                "index": index,
                "name": socket.name,
                "type": getattr(socket, "type", "UNKNOWN"),
                "is_linked": bool(getattr(socket, "is_linked", False)),
                "enabled": bool(getattr(socket, "enabled", True)),
            }
        )

    return ResponseBuilder.success(
        handler="manage_compositing",
        action=action_value,
        data={"node_name": node_name, "sockets": socket_data, "count": len(socket_data)},
    )


def _handle_auto_layout(tree, params):  # type: ignore[no-untyped-def]
    """Apply deterministic grid layout for easier node graph readability."""
    spacing_x = int(params.get("spacing_x", 260))
    spacing_y = int(params.get("spacing_y", -220))
    max_rows = max(1, int(params.get("rows", 6)))

    nodes = list(tree.nodes)
    if not nodes:
        return ResponseBuilder.success(
            handler="manage_compositing",
            action=CompositingAction.AUTO_LAYOUT.value,
            data={"moved_nodes": 0},
        )

    def _sort_key(node):  # type: ignore[no-untyped-def]
        # Keep canonical flow anchors stable and deterministic.
        if node.name == "Render Layers":
            return (0, node.name)
        if node.name == "Composite":
            return (2, node.name)
        return (1, node.name)

    ordered_nodes = sorted(nodes, key=_sort_key)
    for idx, node in enumerate(ordered_nodes):
        col = idx // max_rows
        row = idx % max_rows
        node.location = (col * spacing_x, row * spacing_y)

    return ResponseBuilder.success(
        handler="manage_compositing",
        action=CompositingAction.AUTO_LAYOUT.value,
        data={
            "moved_nodes": len(ordered_nodes),
            "spacing_x": spacing_x,
            "spacing_y": spacing_y,
            "rows": max_rows,
        },
    )


def _handle_set_input(tree, params):  # type: ignore[no-untyped-def]
    """Set an input value."""
    node_name = params.get("node_name")
    socket_name = params.get("socket_name")
    value = params.get("value")

    if value is None:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="value is required",
            details={"parameter": "value"},
        )

    node = tree.nodes.get(node_name)
    if not node:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Node not found: {node_name}",
            details={"node_name": node_name},
        )

    socket = node.inputs.get(socket_name) if socket_name else None
    if not socket and params.get("socket_index") is not None:
        idx = params["socket_index"]
        if idx < len(node.inputs):
            socket = node.inputs[idx]

    if not socket:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message="Socket not found",
            details={"available_sockets": [s.name for s in node.inputs]},
        )

    try:
        socket.default_value = value
        return ResponseBuilder.success(
            handler="manage_compositing",
            action=CompositingAction.SET_INPUT_VALUE.value,
            data={"node": node_name, "socket": socket.name, "value": value},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.SET_INPUT_VALUE.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to set value: {str(e)}",
        )


def _handle_get_input(tree, params):  # type: ignore[no-untyped-def]
    """Get an input value."""
    node_name = params.get("node_name")
    socket_name = params.get("socket_name")

    node = tree.nodes.get(node_name)
    if not node:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.GET_INPUT_VALUE.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Node not found: {node_name}",
            details={"node_name": node_name},
        )

    socket = node.inputs.get(socket_name) if socket_name else None
    if not socket and params.get("socket_index") is not None:
        idx = params["socket_index"]
        if idx < len(node.inputs):
            socket = node.inputs[idx]

    if not socket:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.GET_INPUT_VALUE.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message="Socket not found",
            details={"available_sockets": [s.name for s in node.inputs]},
        )

    try:
        val = socket.default_value
        # Convert for JSON serialization
        if hasattr(val, "__iter__") and not isinstance(val, (str, bytes)):
            value_result = list(val)
        else:
            value_result = val

        return ResponseBuilder.success(
            handler="manage_compositing",
            action=CompositingAction.GET_INPUT_VALUE.value,
            data={
                "node": node_name,
                "socket": socket.name,
                "value": value_result,
                "type": socket.type,
            },
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.GET_INPUT_VALUE.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to get value: {str(e)}",
        )


def _handle_create_common_setup(tree, params):  # type: ignore[no-untyped-def]
    """Create common compositor setups."""
    setup_type = params.get("setup_type", "glare")

    rl, comp = _get_or_create_io_nodes(tree)
    comp.location = (600, 0)

    try:
        comp_in = comp.inputs["Image"] if "Image" in comp.inputs else comp.inputs[0]
        rl_out = rl.outputs["Image"] if "Image" in rl.outputs else rl.outputs[0]
    except IndexError:
        return ResponseBuilder.error(
            handler="manage_compositing",
            action=CompositingAction.CREATE_COMMON_SETUP.value,
            error_code="SOCKET_ERROR",
            message="Sockets not found on I/O nodes.",
        )

    if setup_type == "glare":
        # Glare node setup
        glare = tree.nodes.new(type="CompositorNodeGlare")
        glare.location = (150, 100)
        glare.glare_type = "FOG_GLOW"

        tree.links.new(rl_out, glare.inputs["Image"])
        tree.links.new(glare.outputs["Image"], comp_in)

        return ResponseBuilder.success(
            handler="manage_compositing",
            action=CompositingAction.CREATE_COMMON_SETUP.value,
            data={"setup": "glare", "nodes": ["Render Layers", "Glare", "Composite"]},
        )

    elif setup_type == "color_balance":
        # Color balance setup
        cb = tree.nodes.new(type="CompositorNodeColorBalance")
        cb.location = (150, 0)

        tree.links.new(rl_out, cb.inputs["Image"])
        tree.links.new(cb.outputs["Image"], comp_in)

        return ResponseBuilder.success(
            handler="manage_compositing",
            action=CompositingAction.CREATE_COMMON_SETUP.value,
            data={
                "setup": "color_balance",
                "nodes": ["Render Layers", "Color Balance", "Composite"],
            },
        )

    else:
        # Basic setup
        tree.links.new(rl_out, comp_in)
        return ResponseBuilder.success(
            handler="manage_compositing",
            action=CompositingAction.CREATE_COMMON_SETUP.value,
            data={"setup": "basic", "nodes": ["Render Layers", "Composite"]},
        )
