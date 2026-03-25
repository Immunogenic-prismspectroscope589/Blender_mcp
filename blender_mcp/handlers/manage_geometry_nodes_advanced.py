"""
Advanced Geometry Nodes Handler for Blender MCP 1.0.0 Refactored (SSOT)

Fixes:
- Implements GeometryNodeAdvancedAction Enum (SSOT)
- Robust validation

High Mode: Procedural power unlimited.
"""

from typing import Optional

from ..core.thread_safety import ensure_main_thread
from ..dispatcher import register_handler
from ..core.error_protocol import ErrorProtocol
from ..core.response_builder import ResponseBuilder
from ..core.geometry_nodes_advanced import (
    SimulationZoneBuilder,
    BundleManager,
    ClosureManager,
    ProceduralAssetBuilder,
    ZoneNodeBuilder,
)
from ..core.versioning import BlenderCompatibility

# SSOT Imports
from ..core.enums import GeometryNodeAdvancedAction
from ..core.validation_utils import ValidationUtils

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None


@register_handler(
    "manage_geometry_nodes_advanced",
    actions=[a.value for a in GeometryNodeAdvancedAction],
    schema={
        "type": "object",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                GeometryNodeAdvancedAction, "Advanced operation"
            ),
            "object_name": {"type": "string"},
            "object_index": {"type": "integer"},
            "node_tree_name": {"type": "string"},
            # Simulation params
            "particle_count": {"type": "integer", "default": 1000},
            "lifetime": {"type": "integer", "default": 100},
            "gravity": {"type": "number", "default": 9.81},
            "diffusion_rate": {"type": "number", "default": 0.1},
            "decay_rate": {"type": "number", "default": 0.01},
            "iterations": {"type": "integer", "default": 10},
            "target_edge_length": {"type": "number", "default": 1.0},
            # State items for simulation
            "state_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["FLOAT", "INT", "VECTOR", "ROTATION", "BOOLEAN"],
                        },
                        "name": {"type": "string"},
                    },
                },
            },
            # Bundle params
            "bundle_attributes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "data_type": {"type": "string"}},
                },
            },
            # Closure params
            "input_types": {"type": "array"},
            "output_types": {"type": "array"},
            # Procedural params
            "blocks_x": {"type": "integer", "default": 5},
            "blocks_y": {"type": "integer", "default": 5},
            "street_width": {"type": "number", "default": 2.0},
            "tree_count": {"type": "integer", "default": 100},
            "area_size": {"type": "number", "default": 100.0},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_geometry_nodes_advanced(action: Optional[str] = None, **params):  # type: ignore[no-untyped-def]
    """
    Advanced Geometry Nodes operations for Blender 5.0.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes_advanced",
            action=action or "UNKNOWN",
            error_code=ErrorProtocol.NO_CONTEXT,
            message="Blender not available",
        )

    if not action:
        action = params.get("action")

    if not action:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes_advanced",
            action="UNKNOWN",  # Cannot assume action
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    # Validate Action Enum
    validation_error = ValidationUtils.validate_enum(action, GeometryNodeAdvancedAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_geometry_nodes_advanced", action=action
        )

    # Get target object
    obj = None
    if "object_name" in params:
        obj = bpy.data.objects.get(params.get("object_name"))
    elif "object_index" in params:
        obj = BlenderCompatibility.get_object_by_index(int(params.get("object_index", 0)))

    node_tree_name = params.get("node_tree_name", f"AdvancedGN_{action}")

    try:
        # Simulation Zones
        if action == GeometryNodeAdvancedAction.CREATE_PARTICLE_SIMULATION.value:
            return SimulationZoneBuilder.create_particle_simulation(
                obj,
                node_tree_name,
                particle_count=params.get("particle_count", 1000),
                lifetime=params.get("lifetime", 100),
                gravity=params.get("gravity", 9.81),
            )

        elif action == GeometryNodeAdvancedAction.CREATE_DIFFUSION_SIMULATION.value:
            return SimulationZoneBuilder.create_diffusion_simulation(
                obj,
                node_tree_name,
                diffusion_rate=params.get("diffusion_rate", 0.1),
                decay_rate=params.get("decay_rate", 0.01),
            )

        elif action == GeometryNodeAdvancedAction.CREATE_RELAXATION_ZONE.value:
            return SimulationZoneBuilder.create_relaxation_zone(
                obj,
                node_tree_name,
                iterations=params.get("iterations", 10),
                target_edge_length=params.get("target_edge_length", 1.0),
            )

        # Bundles
        elif action == GeometryNodeAdvancedAction.CREATE_BUNDLE_PIPELINE.value:
            result = BundleManager.create_bundle_node_group(node_tree_name)

            # Add custom attributes if specified
            if "bundle_attributes" in params:
                node_group = bpy.data.node_groups.get(node_tree_name)
                if node_group:
                    for attr in params["bundle_attributes"]:
                        BundleManager.add_bundle_attribute(
                            node_group, attr.get("name"), attr.get("data_type", "FLOAT")
                        )

            return result

        # Closures
        elif action == GeometryNodeAdvancedAction.CREATE_CLOSURE.value:
            input_types = params.get("input_types", [])
            output_types = params.get("output_types", [])
            return ClosureManager.create_closure_node_group(
                node_tree_name, input_types=input_types, output_types=output_types
            )

        # Procedural Assets
        elif action == GeometryNodeAdvancedAction.CREATE_PROCEDURAL_CITY.value:
            result = ProceduralAssetBuilder.create_procedural_city(
                node_tree_name,
                blocks_x=params.get("blocks_x", 5),
                blocks_y=params.get("blocks_y", 5),
                street_width=params.get("street_width", 2.0),
            )

            # Apply to object if provided
            if obj and obj.type == "MESH":
                mod = obj.modifiers.new(name="ProceduralCity", type="NODES")
                mod.node_group = bpy.data.node_groups.get(node_tree_name)  # type: ignore[attr-defined, unused-ignore]

            return result

        elif action == GeometryNodeAdvancedAction.CREATE_PROCEDURAL_FOREST.value:
            result = ProceduralAssetBuilder.create_procedural_forest(
                node_tree_name,
                tree_count=params.get("tree_count", 100),
                area_size=params.get("area_size", 100.0),
            )

            if obj and obj.type == "MESH":
                mod = obj.modifiers.new(name="ProceduralForest", type="NODES")
                mod.node_group = bpy.data.node_groups.get(node_tree_name)  # type: ignore[attr-defined, unused-ignore]

            return result

        # Zone Builders
        elif action == GeometryNodeAdvancedAction.CREATE_REPEAT_ZONE.value:
            node_tree = bpy.data.node_groups.get(node_tree_name)
            if not node_tree:
                # Create new tree
                node_tree = bpy.data.node_groups.new(name=node_tree_name, type="GeometryNodeTree")  # type: ignore[arg-type, unused-ignore]

            return ZoneNodeBuilder.create_repeat_zone(
                node_tree, iterations=params.get("iterations", 10)
            )

        elif action == GeometryNodeAdvancedAction.CREATE_FOREACH_ZONE.value:
            node_tree = bpy.data.node_groups.get(node_tree_name)
            if not node_tree:
                node_tree = bpy.data.node_groups.new(name=node_tree_name, type="GeometryNodeTree")  # type: ignore[arg-type, unused-ignore]

            return ZoneNodeBuilder.create_foreach_zone(
                node_tree, element_type=params.get("element_type", "GEOMETRY")
            )

        else:
            return ResponseBuilder.error(
                handler="manage_geometry_nodes_advanced",
                action=action,
                error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
                message=f"Unknown geometry nodes action: {action}",
                details={"field": "action"},
            )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_geometry_nodes_advanced",
            action=action,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Geometry nodes operation failed: {str(e)}",
        )
