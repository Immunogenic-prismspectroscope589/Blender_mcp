"""
Blender 5.0+ Advanced Features Module for Blender MCP 1.0.0

Implements cutting-edge Blender 5.0 features:
- Action Slots & Layered Animation
- Geometry Nodes Bundles & Closures
- Simulation Zones
- Compositor Modifiers
- Eevee Next Render Engine
- View Layer Overrides

High Mode Philosophy: Harness Blender 5.0's full power.
"""

from typing import Dict, Any, List, Optional, Tuple, Union, cast

try:
    import bpy
    import bmesh

    # import mathutils # REMOVED F401
    # from mathutils import Vector, Matrix, Euler, Quaternion # REMOVED F401

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
    bmesh: Any = None  # type: ignore[no-redef]
    mathutils = None

from .context_manager_v3 import ContextManagerV3
from .error_protocol import ErrorProtocol, create_error
from .logging_config import get_logger

logger = get_logger()


# =============================================================================
# ACTION SLOTS (Blender 5.0 Animation System)
# =============================================================================


class ActionSlotManager:
    """
    Manage Blender 5.0 Action Slots for layered animation.

    Action Slots allow a single Action to animate multiple data blocks
    with different slots for each target.
    """

    @staticmethod
    def create_action_with_slots(action_name: str, slot_configs: List[Dict]) -> Dict[str, Any]:
        """
        Create a new Action with multiple slots.

        Args:
            action_name: Name for the new Action
            slot_configs: List of slot configurations
                [{"name": "Slot1", "target_id": "Object", "data_path": "location"}, ...]

        Returns:
            Action data with slots
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Create or get action
            if action_name in bpy.data.actions:
                action = bpy.data.actions[action_name]
            else:
                action = bpy.data.actions.new(name=action_name)

            created_slots = []

            for config in slot_configs:
                slot_name = config.get("name", "Slot")
                # Blender 5.0+ API: requires id_type (1.0.0 Fix)
                id_type = config.get("id_type") or config.get("target_id") or "OBJECT"

                # Create slot if not exists
                if slot_name not in action.slots:
                    try:
                        # Try with id_type first
                        slot = action.slots.new(name=slot_name, id_type=id_type.upper())

                    except TypeError:
                        # Fallback for different API iterations
                        slot = action.slots.new(name=slot_name)

                else:
                    slot = action.slots[slot_name]

                created_slots.append(
                    {
                        "name": getattr(
                            slot, "name_display", getattr(slot, "identifier", slot_name)
                        ),
                        "id_type": getattr(slot, "id_type", id_type),
                        "identifier": getattr(slot, "identifier", ""),
                    }
                )

            return {"success": True, "action_name": action.name, "slots": created_slots}

        except Exception as e:
            logger.error(f"Failed to create action slots: {e}")
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Action slot creation failed: {str(e)}",
            )

    @staticmethod
    def assign_action_slot(obj: Any, action_name: str, slot_name: str) -> Dict[str, Any]:
        """
        Assign specific action slot to object.

        Args:
            obj: Target object
            action_name: Action name
            slot_name: Slot name within action
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            action = bpy.data.actions.get(action_name)
            if not action:
                return create_error(
                    ErrorProtocol.OBJECT_NOT_FOUND,
                    object_name=action_name,
                    custom_message=f"Action '{action_name}' not found",
                )

            slot = action.slots.get(slot_name)

            if not slot:
                available = [s.name for s in action.slots]

                return create_error(
                    ErrorProtocol.OBJECT_NOT_FOUND,
                    object_name=slot_name,
                    custom_message=f"Slot '{slot_name}' not found in action",
                    available_options=available,
                )

            # Ensure animation data
            if not obj.animation_data:
                obj.animation_data_create()

            # Assign action and slot
            obj.animation_data.action = action
            obj.animation_data.action_slot = slot

            return {"success": True, "object": obj.name, "action": action_name, "slot": slot_name}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Failed to assign action slot: {str(e)}",
            )

    @staticmethod
    def insert_keyframe_to_slot(
        obj: Any, data_path: str, frame: int, value: Union[float, Tuple], index: int = -1
    ) -> Dict[str, Any]:
        """
        Insert keyframe to object's current action slot.
        """
        try:
            if not obj.animation_data or not obj.animation_data.action_slot:
                return create_error(
                    ErrorProtocol.NO_CONTEXT, custom_message="Object has no active action slot"
                )

            if index >= 0:
                obj.keyframe_insert(data_path=data_path, index=index, frame=frame)
            else:
                obj.keyframe_insert(data_path=data_path, frame=frame)

            return {"success": True, "object": obj.name, "data_path": data_path, "frame": frame}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Keyframe insertion failed: {str(e)}"
            )


# =============================================================================
# GEOMETRY NODES ADVANCED (Bundles & Closures)
# =============================================================================


class GeometryNodesAdvanced:
    """
    Advanced Geometry Nodes operations for Blender 5.0

    Supports:
    - Bundles (combine multiple data streams)
    - Closures (higher-level abstractions)
    - Simulation Zones
    - Procedural asset generation
    """

    @staticmethod
    def create_bundle_node_tree(name: str) -> Dict[str, Any]:
        """
        Create a Geometry Node tree that uses Bundle sockets.

        Bundles allow combining Geometry + Selection + Material Index
        into a single socket connection.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Create node group
            node_group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")

            # Create interface with bundle sockets
            cast(Any, node_group.interface).new_socket(
                name="Bundle", in_out="INPUT", socket_type="NodeSocketBundle"
            )
            cast(Any, node_group.interface).new_socket(
                name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
            )

            nodes = node_group.nodes
            links = node_group.links

            # Add nodes
            group_in = nodes.new("NodeGroupInput")
            group_out = nodes.new("NodeGroupOutput")

            # Bundle separate node (extract data from bundle)
            bundle_sep = nodes.new("GeometryNodeSeparateBundle")

            # Connect
            links.new(group_in.outputs[0], bundle_sep.inputs[0])
            links.new(bundle_sep.outputs[0], group_out.inputs[0])  # Geometry output

            return {"success": True, "node_group": name, "type": "bundle_tree"}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Bundle tree creation failed: {str(e)}",
            )

    @staticmethod
    def create_simulation_zone(
        obj: Any, node_tree_name: str, state_items: List[Dict]
    ) -> Dict[str, Any]:
        """
        Create Simulation Zone in Geometry Nodes.

        Simulation Zones enable iterative solvers for physics and growth simulations.

        Args:
            obj: Object with Geometry Nodes modifier
            node_tree_name: Name for new node tree
            state_items: State variables to track across frames
                [{"type": "FLOAT", "name": "Velocity"}, ...]
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Create node tree
            node_group = bpy.data.node_groups.new(name=node_tree_name, type="GeometryNodeTree")

            nodes = node_group.nodes
            links = node_group.links

            # Create simulation input/output nodes
            sim_in = nodes.new("GeometryNodeSimulationInput")
            sim_in.location = (-200, 0)

            sim_out = nodes.new("GeometryNodeSimulationOutput")
            sim_out.location = (200, 0)

            # CRITICAL: Pair the nodes
            sim_in.pair_with_output(sim_out)

            # Add state items
            created_states = []
            for item in state_items:
                item_type = item.get("type", "FLOAT")
                item_name = item.get("name", "State")

                sim_out.state_items.new(item_type, item_name)

                created_states.append({"type": item_type, "name": item_name})

            # Setup basic flow
            group_in = nodes.new("NodeGroupInput")
            group_out = nodes.new("NodeGroupOutput")

            # Connect geometry flow
            links.new(group_in.outputs[0], sim_in.inputs[0])
            links.new(sim_in.outputs[0], sim_out.inputs[0])
            links.new(sim_out.outputs[0], group_out.inputs[0])

            # Apply to object
            if obj.type == "MESH":
                mod = obj.modifiers.new(name="Simulation", type="NODES")
                mod.node_group = node_group

            return {
                "success": True,
                "node_tree": node_tree_name,
                "state_items": created_states,
                "paired": True,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Simulation zone creation failed: {str(e)}",
            )

    @staticmethod
    def create_closure_node_group(name: str, closure_logic: Dict) -> Dict[str, Any]:
        """
        Create a Closure-based node group.

        Closures allow logic injection into node groups, similar to
        passing functions as arguments in programming.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            node_group = bpy.data.node_groups.new(name=name, type="GeometryNodeTree")

            # Create closure input/output zone
            closure_input = node_group.nodes.new("GeometryNodeClosureInput")
            closure_output = node_group.nodes.new("GeometryNodeClosureOutput")

            # Setup interface
            cast(Any, node_group.interface).new_socket(
                name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
            )
            cast(Any, node_group.interface).new_socket(
                name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
            )

            return {
                "success": True,
                "node_group": name,
                "type": "closure",
                "closure_input": closure_input.name,
                "closure_output": closure_output.name,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Closure creation failed: {str(e)}"
            )


# =============================================================================
# COMPOSITOR MODIFIER (Blender 5.0 Feature)
# =============================================================================


class CompositorModifierManager:
    """
    Manage Compositor Modifiers for per-object post-processing.

    Unlike global compositor, this applies effects directly to objects
    or VSE strips via modifier stack.
    """

    @staticmethod
    def add_compositor_modifier(
        obj: Any, effect_type: str, node_group_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add Compositor Modifier to object.

        Args:
            obj: Target object
            effect_type: Effect preset ("BLOOM", "GLARE", "COLOR_CORRECTION", etc.)
            node_group_name: Custom node group name (optional)
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Create modifier
            mod = obj.modifiers.new(name=f"Compositor_{effect_type}", type="COMPOSITOR")

            # Create or get node group
            if node_group_name and node_group_name in bpy.data.node_groups:
                node_group = bpy.data.node_groups[node_group_name]
            else:
                node_group = bpy.data.node_groups.new(
                    name=f"CompEffect_{effect_type}",
                    type="CompositorNodeTree",
                )

                # Setup effect based on type
                if effect_type == "BLOOM":
                    CompositorModifierManager._setup_bloom_nodes(node_group)
                elif effect_type == "GLARE":
                    CompositorModifierManager._setup_glare_nodes(node_group)
                elif effect_type == "COLOR_CORRECTION":
                    CompositorModifierManager._setup_color_correction_nodes(node_group)

            mod.node_group = node_group

            return {
                "success": True,
                "object": obj.name,
                "modifier": mod.name,
                "effect": effect_type,
                "node_group": node_group.name,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Compositor modifier failed: {str(e)}",
            )

    @staticmethod
    def _setup_bloom_nodes(node_group: Any) -> None:
        """Setup bloom effect nodes."""
        nodes = node_group.nodes
        links = node_group.links

        # Clear default
        nodes.clear()

        # Create nodes
        comp_in = nodes.new("CompositorNodeComposite")
        comp_in.location = (0, 0)

        bloom = nodes.new("CompositorNodeGlare")
        bloom.glare_type = "BLOOM"
        bloom.location = (200, 0)

        comp_out = nodes.new("CompositorNodeComposite")
        comp_out.location = (400, 0)

        # Link
        links.new(comp_in.outputs[0], bloom.inputs[0])
        links.new(bloom.outputs[0], comp_out.inputs[0])

    @staticmethod
    def _setup_glare_nodes(node_group: Any) -> None:
        """Setup glare effect nodes."""
        nodes = node_group.nodes
        links = node_group.links

        nodes.clear()

        comp_in = nodes.new("CompositorNodeComposite")
        glare = nodes.new("CompositorNodeGlare")
        glare.glare_type = "STREAKS"
        comp_out = nodes.new("CompositorNodeComposite")

        links.new(comp_in.outputs[0], glare.inputs[0])
        links.new(glare.outputs[0], comp_out.inputs[0])

    @staticmethod
    def _setup_color_correction_nodes(node_group: Any) -> None:
        """Setup color correction nodes."""
        nodes = node_group.nodes
        links = node_group.links

        nodes.clear()

        comp_in = nodes.new("CompositorNodeComposite")
        color_corr = nodes.new("CompositorNodeColorCorrection")
        comp_out = nodes.new("CompositorNodeComposite")

        links.new(comp_in.outputs[0], color_corr.inputs[0])
        links.new(color_corr.outputs[0], comp_out.inputs[0])


# =============================================================================
# EEVEE NEXT RENDER ENGINE
# =============================================================================


class EeveeNextManager:
    """
    Manage Eevee Next render engine settings for Blender 5.0

    Eevee Next replaces the old Eevee with raytracing and better performance.
    """

    RAYTRACING_PRESETS = {
        "LOW": {"ray_count": 4, "step_count": 8, "denoise": True},
        "MEDIUM": {"ray_count": 8, "step_count": 16, "denoise": True},
        "HIGH": {"ray_count": 16, "step_count": 32, "denoise": True},
        "PRODUCTION": {"ray_count": 32, "step_count": 64, "denoise": True},
    }

    @staticmethod
    def setup_eevee_next(scene: Any, preset: str = "HIGH") -> Dict[str, Any]:
        """
        Configure Eevee Next with preset.

        Args:
            scene: Scene to configure
            preset: "LOW", "MEDIUM", "HIGH", "PRODUCTION"
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Set engine
            scene.render.engine = "BLENDER_EEVEE"

            # Get preset
            settings = EeveeNextManager.RAYTRACING_PRESETS.get(
                preset, EeveeNextManager.RAYTRACING_PRESETS["HIGH"]
            )

            # Configure Eevee Next
            eevee = scene.eevee

            # Raytracing settings
            if hasattr(eevee, "ray_tracing_options"):
                eevee.ray_tracing_options.enabled = True
                eevee.ray_tracing_options.ray_count = settings["ray_count"]
                eevee.ray_tracing_options.step_count = settings["step_count"]

            # Screen space effects
            if hasattr(eevee, "use_ssr"):
                eevee.use_ssr = True
            if hasattr(eevee, "use_gtao"):
                eevee.use_gtao = True
            if hasattr(eevee, "gtao_distance"):
                eevee.gtao_distance = 0.5

            # Shadows
            if hasattr(eevee, "shadow_ray_count"):
                eevee.shadow_ray_count = settings["ray_count"] // 2
            if hasattr(eevee, "shadow_step_count"):
                eevee.shadow_step_count = settings["step_count"] // 2

            # TAA
            eevee.taa_render_samples = 64
            eevee.use_taa_reprojection = True

            return {
                "success": True,
                "engine": "BLENDER_EEVEE_NEXT",
                "preset": preset,
                "ray_count": settings["ray_count"],
                "step_count": settings["step_count"],
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Eevee Next setup failed: {str(e)}"
            )

    @staticmethod
    def set_view_layer_override(view_layer: Any, material_name: str) -> Dict[str, Any]:
        """
        Set material override for view layer (Clay render, etc.)
        """
        try:
            mat = bpy.data.materials.get(material_name)
            if not mat:
                return create_error(ErrorProtocol.NO_MATERIAL, object_name=material_name)

            view_layer.material_override = mat

            return {
                "success": True,
                "view_layer": view_layer.name,
                "override_material": material_name,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"View layer override failed: {str(e)}",
            )


# =============================================================================
# VIEW LAYER OVERRIDES
# =============================================================================


class ViewLayerOverrideManager:
    """
    Manage View Layer overrides for World, Materials, and Samples.
    """

    @staticmethod
    def create_clay_render_setup(scene: Any, view_layer_name: str = "Clay") -> Dict[str, Any]:
        """
        Create a clay render view layer with material override.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # We need to know which scene belongs to this view layer
            # Heuristic: try finding it in current context first
            if not bpy.context.window:
                return create_error(ErrorProtocol.NO_CONTEXT)

            # Create or get view layer
            if view_layer_name in scene.view_layers:
                view_layer = scene.view_layers[view_layer_name]
            else:
                view_layer = scene.view_layers.new(name=view_layer_name)

            # Create clay material if not exists
            clay_mat_name = "CLAY_MATERIAL"
            if clay_mat_name not in bpy.data.materials:
                mat = bpy.data.materials.new(name=clay_mat_name)
                mat.use_nodes = True
                nodes = cast(Any, mat.node_tree).nodes
                nodes.clear()

                # Simple diffuse
                bsdf = nodes.new("ShaderNodeBsdfDiffuse")
                cast(Any, bsdf.inputs["Color"]).default_value = (0.8, 0.8, 0.8, 1)

                output = nodes.new("ShaderNodeOutputMaterial")
                cast(Any, mat.node_tree).links.new(bsdf.outputs[0], output.inputs[0])

            # Set override
            view_layer.material_override = bpy.data.materials[clay_mat_name]

            return {
                "success": True,
                "view_layer": view_layer_name,
                "material_override": clay_mat_name,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Clay render setup failed: {str(e)}"
            )

    @staticmethod
    def set_world_override(view_layer: Any, world_name: str) -> Dict[str, Any]:
        """Set world override for view layer."""
        try:
            world = bpy.data.worlds.get(world_name)
            if not world:
                return create_error(ErrorProtocol.OBJECT_NOT_FOUND, object_name=world_name)

            view_layer.world_override = world

            return {"success": True, "view_layer": view_layer.name, "world_override": world_name}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"World override failed: {str(e)}"
            )


# =============================================================================
# HEADLESS MODE MANAGER
# =============================================================================


class HeadlessModeManager:
    """
    Manage headless/background mode operations.

    Critical for CI/CD, cloud rendering, and server-side automation.
    """

    @staticmethod
    def is_headless() -> bool:
        """Check if running in background mode."""
        if not BPY_AVAILABLE:
            return True
        return bool(getattr(bpy.app, "background", False))

    @staticmethod
    def ensure_context_for_headless() -> Dict[str, Any]:
        """
        Ensure minimal context exists for headless operations.
        Creates default scene if needed.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Check if we have a valid scene
            if not bpy.context.scene:
                # Create default scene
                scene = bpy.data.scenes.new("Scene")
                if bpy.context.window:
                    bpy.context.window.scene = scene

            # Ensure view layer
            scene = bpy.context.scene

            if not scene.view_layers:
                scene.view_layers.new(name="ViewLayer")

            # Ensure collection
            if not scene.collection:
                collection = bpy.data.collections.new("Collection")
                scene.collection.children.link(collection)

            scene_name = "Unknown"
            if bpy.context.scene:
                scene_name = bpy.context.scene.name

            return {
                "success": True,
                "scene": scene_name,
                "headless": bpy.app.background,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.NO_CONTEXT, custom_message=f"Headless context setup failed: {str(e)}"
            )

    @staticmethod
    def render_headless(
        scene: Any, output_path: str, frame: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Render in headless mode with proper setup.
        """
        try:
            # Set output
            scene.render.filepath = output_path

            # Set frame if provided
            if frame is not None:
                scene.frame_set(frame)

            # Disable audio (headless fix)
            scene.render.use_audio = False

            # Render
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                bpy.ops.render.render(write_still=True)

            return {"success": True, "output": output_path, "frame": scene.frame_current}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Headless render failed: {str(e)}"
            )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ActionSlotManager",
    "GeometryNodesAdvanced",
    "CompositorModifierManager",
    "EeveeNextManager",
    "ViewLayerOverrideManager",
    "HeadlessModeManager",
]
