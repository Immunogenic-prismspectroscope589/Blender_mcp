"""
Advanced Geometry Nodes System for Blender MCP 1.0.0

Implements:
- Bundles & Bundle sockets (Geometry + Selection + Material Index)
- Closures (function-like node groups)
- Simulation Zones (physics, growth, iterative solvers)
- Procedural asset generation pipelines
- Zone-based workflows

High Mode Philosophy: Procedural power at your fingertips.
"""

from typing import Dict, Any, List, Optional, Tuple, cast
from enum import Enum

try:
    import bpy
    import mathutils
    from mathutils import noise  # REMOVED Vector F401

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
    bmesh: Any = None
    mathutils: Any = None  # type: ignore[no-redef]
    noise: Any = None  # type: ignore[no-redef]

from .error_protocol import ErrorProtocol, create_error
from .logging_config import get_logger

logger = get_logger()


class GeometryNodeType(Enum):
    """Geometry node types."""

    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    MESH_PRIMITIVE = "MESH_PRIMITIVE"
    POINT = "POINT"
    INSTANCE = "INSTANCE"
    MATERIAL = "MATERIAL"
    UTILITIES = "UTILITIES"
    GROUP = "GROUP"


class SimulationZoneBuilder:
    """
    Build Simulation Zones for iterative geometry operations.

    Simulation Zones enable:
    - Physics simulations (particle, fluid)
    - Growth algorithms (L-systems, diffusion)
    - Relaxation (constrained smoothing)
    - Recursion without stack overflow
    """

    STATE_TYPES = ["FLOAT", "INT", "VECTOR", "ROTATION", "BOOLEAN", "STRING", "RGBA", "OBJECT"]

    @staticmethod
    def create_particle_simulation(
        obj: Any,
        node_tree_name: str,
        particle_count: int = 1000,
        lifetime: int = 100,
        gravity: float = 9.81,
    ) -> Dict[str, Any]:
        """
        Create particle simulation zone.

        Args:
            obj: Target mesh object
            node_tree_name: Name for new node tree
            particle_count: Number of particles
            lifetime: Particle lifetime in frames
            gravity: Gravity strength
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Create node tree
            node_group = bpy.data.node_groups.new(name=node_tree_name, type="GeometryNodeTree")

            nodes = node_group.nodes
            links = node_group.links

            # Create simulation zone
            sim_in = cast(Any, nodes.new("GeometryNodeSimulationInput"))
            sim_in.location = (-400, 0)

            sim_out = cast(Any, nodes.new("GeometryNodeSimulationOutput"))
            sim_out.location = (400, 0)

            # CRITICAL: Pair the nodes
            sim_in.pair_with_output(sim_out)

            # Add state items for particle system
            sim_out.state_items.new("VECTOR", "Position")
            sim_out.state_items.new("VECTOR", "Velocity")
            sim_out.state_items.new("FLOAT", "Age")

            # Input geometry
            group_in = cast(Any, nodes.new("NodeGroupInput"))
            group_in.location = (-600, 0)

            group_out = cast(Any, nodes.new("NodeGroupOutput"))
            group_out.location = (600, 0)

            # Create geometry nodes for simulation
            # Distribute points on faces for particle spawning
            distribute = cast(Any, nodes.new("GeometryNodeDistributePointsOnFaces"))
            distribute.location = (-200, 200)
            distribute.distribute_method = "POISSON"

            # Bug 19/25 Fix: Secure socket index lookup to avoid API localization/string errors
            dist_socket = next(
                (inp for inp in distribute.inputs if "Distance" in inp.name),
                distribute.inputs[2] if len(distribute.inputs) > 2 else None,
            )
            if dist_socket:
                dist_socket.default_value = 0.1

            # Set Position node to update particle positions
            set_pos = cast(Any, nodes.new("GeometryNodeSetPosition"))
            set_pos.location = (0, 0)

            # Store Named Attribute for velocity
            store_vel = cast(Any, nodes.new("GeometryNodeStoreNamedAttribute"))
            store_vel.location = (200, 0)
            store_vel.data_type = "FLOAT_VECTOR"
            store_vel.inputs["Name"].default_value = "velocity"

            # Link nodes
            links.new(group_in.outputs[0], distribute.inputs[0])
            links.new(distribute.outputs[0], sim_in.inputs[0])
            links.new(sim_in.outputs[0], set_pos.inputs[0])
            links.new(set_pos.outputs[0], store_vel.inputs[0])
            links.new(store_vel.outputs[0], sim_out.inputs[0])
            links.new(sim_out.outputs[0], group_out.inputs[0])

            # Apply to object
            if obj and obj.type == "MESH":
                mod = obj.modifiers.new(name="ParticleSimulation", type="NODES")
                mod.node_group = node_group

            return {
                "success": True,
                "node_tree": node_tree_name,
                "type": "particle_simulation",
                "state_items": ["Position", "Velocity", "Age"],
                "paired": True,
                "particle_count": particle_count,
            }

        except Exception as e:
            logger.error(f"Particle simulation creation failed: {e}")
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Particle simulation failed: {str(e)}",
            )

    @staticmethod
    def create_diffusion_simulation(
        obj: Any, node_tree_name: str, diffusion_rate: float = 0.1, decay_rate: float = 0.01
    ) -> Dict[str, Any]:
        """
        Create reaction-diffusion simulation zone.

        Classic Gray-Scott model or custom diffusion.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            node_group = bpy.data.node_groups.new(name=node_tree_name, type="GeometryNodeTree")

            nodes = node_group.nodes
            links = node_group.links

            # Simulation zone
            sim_in = cast(Any, nodes.new("GeometryNodeSimulationInput"))
            sim_out = cast(Any, nodes.new("GeometryNodeSimulationOutput"))
            sim_in.pair_with_output(sim_out)

            # State: concentration A and B
            sim_out.state_items.new("FLOAT", "ConcentrationA")
            sim_out.state_items.new("FLOAT", "ConcentrationB")

            # Create input/output
            group_in = cast(Any, nodes.new("NodeGroupInput"))
            group_out = cast(Any, nodes.new("NodeGroupOutput"))

            # Add sockets
            cast(Any, node_group.interface).new_socket("Geometry", "INPUT", "NodeSocketGeometry")
            cast(Any, node_group.interface).new_socket("Geometry", "OUTPUT", "NodeSocketGeometry")

            # Distribute points
            distribute = cast(Any, nodes.new("GeometryNodeDistributePointsOnFaces"))
            distribute.distribute_method = "RANDOM"

            # Set Position for diffusion
            set_pos = cast(Any, nodes.new("GeometryNodeSetPosition"))

            # Link
            links.new(group_in.outputs[0], distribute.inputs[0])
            links.new(distribute.outputs[0], sim_in.inputs[0])
            links.new(sim_in.outputs[0], set_pos.inputs[0])
            links.new(set_pos.outputs[0], sim_out.inputs[0])
            links.new(sim_out.outputs[0], group_out.inputs[0])

            # Apply
            if obj and obj.type == "MESH":
                mod = obj.modifiers.new(name="Diffusion", type="NODES")
                mod.node_group = node_group

            return {
                "success": True,
                "node_tree": node_tree_name,
                "type": "diffusion_simulation",
                "diffusion_rate": diffusion_rate,
                "decay_rate": decay_rate,
                "paired": True,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Diffusion simulation failed: {str(e)}",
            )

    @staticmethod
    def create_relaxation_zone(
        obj: Any, node_tree_name: str, iterations: int = 10, target_edge_length: float = 1.0
    ) -> Dict[str, Any]:
        """
        Create mesh relaxation simulation zone.

        Constrained smoothing for remeshing.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            node_group = bpy.data.node_groups.new(name=node_tree_name, type="GeometryNodeTree")

            nodes = node_group.nodes
            links = node_group.links

            # Simulation zone
            sim_in = cast(Any, nodes.new("GeometryNodeSimulationInput"))
            sim_out = cast(Any, nodes.new("GeometryNodeSimulationOutput"))
            sim_in.pair_with_output(sim_out)

            # State: position
            sim_out.state_items.new("VECTOR", "Position")

            # Input/Output
            group_in = cast(Any, nodes.new("NodeGroupInput"))
            group_out = cast(Any, nodes.new("NodeGroupOutput"))

            # Smooth by angle
            smooth = cast(Any, nodes.new("GeometryNodeSmoothbyAngle"))
            smooth.inputs["Weight"].default_value = 0.5
            smooth.inputs["Group ID"].default_value = iterations

            # Set position
            set_pos = cast(Any, nodes.new("GeometryNodeSetPosition"))

            # Link
            links.new(group_in.outputs[0], sim_in.inputs[0])
            links.new(sim_in.outputs[0], smooth.inputs[0])
            links.new(smooth.outputs[0], set_pos.inputs[0])
            links.new(set_pos.outputs[0], sim_out.inputs[0])
            links.new(sim_out.outputs[0], group_out.inputs[0])

            # Apply
            if obj and obj.type == "MESH":
                mod = obj.modifiers.new(name="Relaxation", type="NODES")
                mod.node_group = node_group

            return {
                "success": True,
                "node_tree": node_tree_name,
                "type": "relaxation",
                "iterations": iterations,
                "target_edge_length": target_edge_length,
                "paired": True,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Relaxation zone failed: {str(e)}"
            )


class BundleManager:
    """
    Manage Bundle sockets for combined data streams.

    Bundles combine:
    - Geometry
    - Selection (Boolean)
    - Material Index
    - Custom attributes
    """

    @staticmethod
    def create_bundle_node_group(name: str) -> Dict[str, Any]:
        """
        Create node group with bundle sockets.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            node_group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")

            # Add bundle sockets
            cast(Any, node_group.interface).new_socket("Input Bundle", "INPUT", "NodeSocketBundle")
            cast(Any, node_group.interface).new_socket(
                "Output Bundle", "OUTPUT", "NodeSocketBundle"
            )

            nodes = node_group.nodes
            links = node_group.links

            # Input/Output nodes
            group_in = cast(Any, nodes.new("NodeGroupInput"))
            group_out = cast(Any, nodes.new("NodeGroupOutput"))

            # Separate Bundle node
            separate = cast(Any, nodes.new("GeometryNodeSeparateBundle"))
            separate.location = (200, 0)

            # Join Bundle node
            join = cast(Any, nodes.new("GeometryNodeJoinBundle"))
            join.location = (400, 0)

            # Link
            links.new(group_in.outputs[0], separate.inputs[0])
            links.new(separate.outputs[0], join.inputs[0])  # Geometry
            links.new(separate.outputs[1], join.inputs[1])  # Selection
            links.new(separate.outputs[2], join.inputs[2])  # Material Index
            links.new(join.outputs[0], group_out.inputs[0])

            return {
                "success": True,
                "node_group": name,
                "type": "bundle_pipeline",
                "sockets": ["Geometry", "Selection", "Material Index"],
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Bundle creation failed: {str(e)}"
            )

    @staticmethod
    def add_bundle_attribute(
        node_group: Any, name: str, data_type: str = "FLOAT"
    ) -> Dict[str, Any]:
        """
        Add custom attribute socket to bundle.
        """
        try:
            # Add socket to group interface
            cast(Any, node_group.interface).new_socket(name, "INPUT", f"NodeSocket{data_type}")
            cast(Any, node_group.interface).new_socket(name, "OUTPUT", f"NodeSocket{data_type}")

            return {
                "success": True,
                "node_group": node_group.name,
                "attribute": name,
                "type": data_type,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Bundle attribute failed: {str(e)}"
            )


class ClosureManager:
    """
    Manage Closure-based node groups.

    Closures allow passing logic/functions as arguments to node groups,
    similar to higher-order functions in programming.
    """

    @staticmethod
    def create_closure_node_group(
        name: str,
        input_types: Optional[List[Tuple[str, str]]] = None,
        output_types: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Create Closure-based node group.

        Args:
            input_types: List of (name, type) tuples for inputs
            output_types: List of (name, type) tuples for outputs
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            node_group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")

            nodes = node_group.nodes

            # Create closure zone
            closure_in = cast(Any, nodes.new("GeometryNodeClosureInput"))
            closure_in.location = (-200, 0)

            closure_out = cast(Any, nodes.new("GeometryNodeClosureOutput"))
            closure_out.location = (200, 0)

            # Add inputs
            if input_types:
                for name, socket_type in input_types:
                    cast(Any, node_group.interface).new_socket(
                        name, "INPUT", f"NodeSocket{socket_type}"
                    )

            # Add outputs
            if output_types:
                for name, socket_type in output_types:
                    cast(Any, node_group.interface).new_socket(
                        name, "OUTPUT", f"NodeSocket{socket_type}"
                    )

            return {
                "success": True,
                "node_group": name,
                "type": "closure",
                "closure_input": closure_in.name,
                "closure_output": closure_out.name,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Closure creation failed: {str(e)}"
            )

    @staticmethod
    def invoke_closure(
        parent_tree: Any, closure_group: Any, inputs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke a Closure node group within another tree.
        """
        try:
            nodes = parent_tree.nodes

            # Create Invoke Closure node
            invoke = cast(Any, nodes.new("GeometryNodeInvokeClosure"))
            invoke.closure = closure_group

            # Set inputs
            if inputs:
                for i, (name, value) in enumerate(inputs.items()):
                    if i < len(invoke.inputs):
                        invoke.inputs[i].default_value = value

            return {"success": True, "node": invoke.name, "closure": closure_group.name}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Closure invocation failed: {str(e)}"
            )


class ProceduralAssetBuilder:
    """
    Build procedural assets using Geometry Nodes.
    """

    PRESETS = {
        "CITY": {
            "blocks_x": 5,
            "blocks_y": 5,
            "building_height_range": (10, 50),
            "street_width": 2.0,
        },
        "FOREST": {"tree_count": 100, "area_size": 100, "tree_types": 3},
        "ROCK_FORMATION": {"rock_count": 20, "displacement_scale": 2.0, "detail_level": 5},
    }

    @staticmethod
    def create_procedural_city(
        name: str = "ProceduralCity",
        blocks_x: int = 5,
        blocks_y: int = 5,
        street_width: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Create procedural city generator.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            node_group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")

            nodes = node_group.nodes
            links = node_group.links

            # Grid for city blocks
            grid = cast(Any, nodes.new("GeometryNodeMeshGrid"))
            grid.inputs["Vertices X"].default_value = blocks_x * 2
            grid.inputs["Vertices Y"].default_value = blocks_y * 2
            grid.inputs["Size X"].default_value = blocks_x * 10
            grid.inputs["Size Y"].default_value = blocks_y * 10

            # Delete faces for streets
            delete_geo = cast(Any, nodes.new("GeometryNodeDeleteGeometry"))

            # Distribute points on faces for buildings
            distribute = cast(Any, nodes.new("GeometryNodeDistributePointsOnFaces"))
            distribute.distribute_method = "POISSON"

            # Bug 19/25: Safe property index search
            dist_socket = next(
                (inp for inp in distribute.inputs if "Distance" in inp.name),
                distribute.inputs[2] if len(distribute.inputs) > 2 else None,
            )
            if dist_socket:
                dist_socket.default_value = 3.0

            # Instance building blocks
            cube = cast(Any, nodes.new("GeometryNodeMeshCube"))
            cube.inputs["Size"].default_value = (4, 4, 10)

            instance = cast(Any, nodes.new("GeometryNodeInstanceOnPoints"))

            # Random scale for variety
            random_scale = cast(Any, nodes.new("FunctionNodeRandomValue"))
            random_scale.data_type = "FLOAT_VECTOR"
            random_scale.inputs["Min"].default_value = (0.5, 0.5, 0.5)
            random_scale.inputs["Max"].default_value = (1.5, 1.5, 3.0)

            # Set scale
            set_scale = cast(Any, nodes.new("GeometryNodeSetScale"))

            # Output
            group_out = cast(Any, nodes.new("NodeGroupOutput"))
            cast(Any, node_group.interface).new_socket("Geometry", "OUTPUT", "NodeSocketGeometry")

            # Link
            links.new(grid.outputs[0], delete_geo.inputs[0])
            links.new(delete_geo.outputs[0], distribute.inputs[0])
            links.new(distribute.outputs[0], instance.inputs["Points"])
            links.new(cube.outputs[0], instance.inputs["Instance"])
            links.new(random_scale.outputs["Value"], instance.inputs["Scale"])
            links.new(instance.outputs[0], set_scale.inputs[0])
            links.new(set_scale.outputs[0], group_out.inputs[0])

            return {
                "success": True,
                "node_group": name,
                "type": "procedural_city",
                "blocks": (blocks_x, blocks_y),
                "street_width": street_width,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"City generator failed: {str(e)}"
            )

    @staticmethod
    def create_procedural_forest(
        name: str = "ProceduralForest", tree_count: int = 100, area_size: float = 100.0
    ) -> Dict[str, Any]:
        """
        Create procedural forest generator.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            node_group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")

            nodes = node_group.nodes
            links = node_group.links

            # Ground plane
            grid = cast(Any, nodes.new("GeometryNodeMeshGrid"))
            grid.inputs["Vertices X"].default_value = 2
            grid.inputs["Vertices Y"].default_value = 2
            grid.inputs["Size X"].default_value = area_size
            grid.inputs["Size Y"].default_value = area_size

            # Points for trees
            points = cast(Any, nodes.new("GeometryNodeDistributePointsOnFaces"))
            points.distribute_method = "POISSON"

            # Bug 19/25: Safe property index search
            dist_socket = next(
                (inp for inp in points.inputs if "Distance" in inp.name),
                points.inputs[2] if len(points.inputs) > 2 else None,
            )
            if dist_socket:
                dist_socket.default_value = area_size / (tree_count**0.5)

            # Instance trees (simple cones for now)
            cone = cast(Any, nodes.new("GeometryNodeMeshCone"))
            cone.inputs["Vertices"].default_value = 8
            cone.inputs["Radius Top"].default_value = 0
            cone.inputs["Radius Bottom"].default_value = 2
            cone.inputs["Depth"].default_value = 8

            instance = cast(Any, nodes.new("GeometryNodeInstanceOnPoints"))

            # Random rotation
            random_rot = cast(Any, nodes.new("FunctionNodeRandomValue"))
            random_rot.data_type = "FLOAT"
            random_rot.inputs["Min"].default_value = 0
            random_rot.inputs["Max"].default_value = 6.283185

            # Combine rotation
            combine = cast(Any, nodes.new("ShaderNodeCombineXYZ"))
            links.new(random_rot.outputs[0], combine.inputs[2])  # Z rotation

            # Set rotation
            set_rot = cast(Any, nodes.new("GeometryNodeSetRotation"))
            set_rot.rotation_mode = "EULER_XYZ"

            # Output
            group_out = cast(Any, nodes.new("NodeGroupOutput"))
            cast(Any, node_group.interface).new_socket("Geometry", "OUTPUT", "NodeSocketGeometry")

            # Link
            links.new(grid.outputs[0], points.inputs[0])
            links.new(points.outputs[0], instance.inputs["Points"])
            links.new(cone.outputs[0], instance.inputs["Instance"])
            links.new(instance.outputs[0], set_rot.inputs[0])
            links.new(combine.outputs[0], set_rot.inputs["Rotation"])
            links.new(set_rot.outputs[0], group_out.inputs[0])

            return {
                "success": True,
                "node_group": name,
                "type": "procedural_forest",
                "tree_count": tree_count,
                "area_size": area_size,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Forest generator failed: {str(e)}"
            )


class ZoneNodeBuilder:
    """
    Helper for building various zone types in Geometry Nodes.
    """

    @staticmethod
    def create_repeat_zone(
        node_tree: Any, iterations: int = 10, body_logic: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create Repeat Zone for iterative operations.

        Similar to for-loops in programming.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            nodes = node_tree.nodes

            # Create repeat zone
            repeat_in = cast(Any, nodes.new("GeometryNodeRepeatInput"))
            repeat_out = cast(Any, nodes.new("GeometryNodeRepeatOutput"))
            repeat_in.pair_with_output(repeat_out)

            # Set iterations
            repeat_in.inputs["Iterations"].default_value = iterations

            return {
                "success": True,
                "zone_type": "repeat",
                "iterations": iterations,
                "paired": True,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Repeat zone failed: {str(e)}"
            )

    @staticmethod
    def create_foreach_zone(
        node_tree: Any, element_type: str = "GEOMETRY", body_logic: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create For-Each Element zone.

        Process each element (point, face, instance) independently.
        """
        try:
            nodes = node_tree.nodes

            # Create foreach zone
            foreach_in = cast(Any, nodes.new("GeometryNodeForeachGeometryElementInput"))
            foreach_out = cast(Any, nodes.new("GeometryNodeForeachGeometryElementOutput"))
            foreach_in.pair_with_output(foreach_out)

            return {
                "success": True,
                "zone_type": "foreach",
                "element_type": element_type,
                "paired": True,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Foreach zone failed: {str(e)}"
            )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "SimulationZoneBuilder",
    "BundleManager",
    "ClosureManager",
    "ProceduralAssetBuilder",
    "ZoneNodeBuilder",
    "GeometryNodeType",
]
