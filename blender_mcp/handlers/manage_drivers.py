"""
Driver Handler for Blender MCP 1.0.0 (Refactored)

Advanced Driver Management: create, edit variables, expressions, and debugging.
- Strict typing with DriverAction Enum
- Safe property path resolution
- Expression validation

High Mode Philosophy: Automate the automation.
"""

from typing import Optional

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..dispatcher import register_handler
from ..core.resolver import resolve_name
from ..core.thread_safety import ensure_main_thread
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.property_resolver import resolve_property_path
from ..core.enums import DriverAction
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_drivers",
    actions=[a.value for a in DriverAction],
    category="animation",
    schema={
        "type": "object",
        "title": "Driver Manager",
        "description": (
            "STANDARD — Blender driver manager (value expressions linking properties).\n"
            "ACTIONS: ADD_DRIVER, REMOVE_DRIVER, SET_EXPRESSION, SET_VARIABLE, "
            "GET_DRIVER_INFO, LIST_DRIVERS, MUTE_DRIVER, UNMUTE_DRIVER, CREATE_FCURVE_DRIVER\n\n"
            "PATTERN: Link property A → property B with expression. "
            "e.g. expression='var*2+offset' drives object rotation from bone location.\n"
            "NOTE: Drivers survive file save. Use for procedural rigs and parameter linking. "
            "Call LIST_DRIVERS to inspect all active drivers on an object."
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(DriverAction, "Operation to perform."),
            "object_name": {
                "type": "string",
                "description": "Target object name (default: active).",
            },
            "property_path": {
                "type": "string",
                "description": "Property to drive (e.g. 'location.x', 'rotation_euler.z').",
            },
            "expression": {
                "type": "string",
                "description": "Python expression for the driver (e.g. 'var + 1.0').",
            },
            "variables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": ["SINGLE_PROP", "TRANSFORMS", "ROTATION_DIFF", "LOC_DIFF"],
                        },
                        "target_id": {
                            "type": "string",
                            "description": "Target Object/Armature Name",
                        },
                        "data_path": {
                            "type": "string",
                            "description": "Source path (e.g. 'location.z')",
                        },
                    },
                },
                "description": "List of variables for the driver.",
            },
            "index": {
                "type": "integer",
                "default": -1,
                "description": "Array index for property (e.g., 0 for X, 1 for Y). If not provided, inferred from path.",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_drivers(action: Optional[str] = None, **params):  # type: ignore[no-untyped-def]
    """
    Manage drivers: Add, remove, set expressions/variables.
    """
    # 1. Validate Action
    validation_error = ValidationUtils.validate_enum(action, DriverAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(validation_error, handler="manage_drivers", action=action)

    # 2. Resolve Object
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name) if obj_name else bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_drivers",
            action=action,
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: {obj_name or '(active object)'}",
        )

    # 3. Resolve Path (for most ops)
    path_input = params.get("property_path")
    index_input = params.get("index", -1)

    data_path = None
    index = -1

    if path_input:
        resolved = resolve_property_path(path_input, obj)
        if resolved:
            if isinstance(resolved, list):
                # Use first one if multiple returned, or handle specific logic
                data_path, index = resolved[0]
            else:
                data_path, index = resolved

            # Override index if explicitly provided
            if index_input != -1:
                index = index_input

    # Dispatch
    try:
        if action == DriverAction.ADD_DRIVER.value:
            if not data_path:
                return ResponseBuilder.error(
                    handler="manage_drivers",
                    action=action,
                    error_code="MISSING_PARAMETER",
                    message="property_path is required and must be valid.",
                )
            return _handle_add_driver(obj, data_path, index, params)

        elif action == DriverAction.REMOVE_DRIVER.value:
            if not data_path:
                return ResponseBuilder.error(
                    handler="manage_drivers",
                    action=action,
                    error_code="MISSING_PARAMETER",
                    message="property_path is required.",
                )
            return _handle_remove_driver(obj, data_path, index)

        elif action == DriverAction.SET_EXPRESSION.value:
            return _handle_set_expression(obj, data_path, index, params)

        elif action == DriverAction.LIST_DRIVERS.value:
            return _handle_list_drivers(obj)

        return ResponseBuilder.error(
            handler="manage_drivers",
            action=action,
            error_code="NOT_IMPLEMENTED",
            message=f"Action '{action}' is defined but not implemented.",
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return ResponseBuilder.error(
            handler="manage_drivers",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Driver operation failed: {str(e)}",
        )


# =============================================================================
# INTERNAL HANDLERS
# =============================================================================


def _handle_add_driver(obj, data_path, index, params):  # type: ignore[no-untyped-def]
    expression = params.get("expression", "frame")  # Default to frame number

    try:
        # Check if driver exists
        # There isn't a direct "check if exists" without iterating, but `driver_add` creates or returns existing.
        # However, it overwrites existing F-Curve if replace=True (implicit)

        # Add Driver F-Curve
        fcurve = obj.driver_add(data_path, index)
        driver = fcurve.driver

        # Set Type
        driver.type = "SCRIPTED"
        driver.expression = expression

        # Setup Variables if provided
        variables = params.get("variables", [])
        _setup_driver_variables(driver, variables)

        return ResponseBuilder.success(
            handler="manage_drivers",
            action="ADD_DRIVER",
            data={
                "object": obj.name,
                "property": data_path,
                "index": index,
                "expression": expression,
                "variables_count": len(variables),
            },
            affected_objects=[{"name": obj.name, "type": obj.type, "changes": ["driver_added"]}],
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_drivers",
            action="ADD_DRIVER",
            error_code="EXECUTION_ERROR",
            message=f"Failed to add driver: {str(e)}",
        )


def _handle_remove_driver(obj, data_path, index):  # type: ignore[no-untyped-def]
    try:
        success = obj.driver_remove(data_path, index)
        if success:
            return ResponseBuilder.success(
                handler="manage_drivers",
                action="REMOVE_DRIVER",
                data={"object": obj.name, "property": data_path, "index": index},
                affected_objects=[
                    {"name": obj.name, "type": obj.type, "changes": ["driver_removed"]}
                ],
            )
        else:
            return ResponseBuilder.error(
                handler="manage_drivers",
                action="REMOVE_DRIVER",
                error_code="DRIVER_NOT_FOUND",
                message=f"No driver found for {data_path}[{index}]",
            )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_drivers",
            action="REMOVE_DRIVER",
            error_code="EXECUTION_ERROR",
            message=f"Failed to remove driver: {str(e)}",
        )


def _handle_set_expression(obj, data_path, index, params):  # type: ignore[no-untyped-def]
    expression = params.get("expression")
    if not expression:
        return ResponseBuilder.error(
            handler="manage_drivers",
            action="SET_EXPRESSION",
            error_code="MISSING_PARAMETER",
            message="expression is required.",
        )

    # Find driver
    if not obj.animation_data:
        return ResponseBuilder.error(
            handler="manage_drivers",
            action="SET_EXPRESSION",
            error_code="DRIVER_NOT_FOUND",
            message="Object has no animation data.",
        )

    fcurve = None
    for fc in obj.animation_data.drivers:
        if fc.data_path == data_path and fc.array_index == index:
            fcurve = fc
            break

    if not fcurve:
        return ResponseBuilder.error(
            handler="manage_drivers",
            action="SET_EXPRESSION",
            error_code="DRIVER_NOT_FOUND",
            message=f"Driver not found for {data_path}[{index}]",
        )

    try:
        fcurve.driver.expression = expression
        return {"success": True, "message": "Expression updated", "expression": expression}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _handle_list_drivers(obj):  # type: ignore[no-untyped-def]
    if not obj.animation_data or not obj.animation_data.drivers:
        return {"success": True, "drivers": []}

    drivers_list = []
    for fc in obj.animation_data.drivers:
        drivers_list.append(
            {
                "data_path": fc.data_path,
                "index": fc.array_index,
                "expression": fc.driver.expression,
                "is_valid": fc.driver.is_valid,
            }
        )

    return {"success": True, "drivers": drivers_list}


def _setup_driver_variables(driver, variables):  # type: ignore[no-untyped-def]
    """Helper to setup driver variables."""
    # clear existing? generic setup keeps them or overwrites if same name
    # For now, we append/overwrite

    for var_data in variables:
        name = var_data.get("name", "var")
        var_type = var_data.get("type", "SINGLE_PROP")

        # Get or create variable
        try:
            var = driver.variables.get(name)
            if not var:
                var = driver.variables.new()
                var.name = name

            var.type = var_type

            # Target setup
            target_id = var_data.get("target_id")
            path = var_data.get("data_path")

            if var_type == "SINGLE_PROP":
                target = var.targets[0]
                target.id = resolve_name(target_id) if target_id else None
                target.data_path = path or ""

            # Add other types as needed (TRANSFORMS, etc.)

        except Exception as e:
            logger.error(f"Failed to setup variable {name}: {e}")
