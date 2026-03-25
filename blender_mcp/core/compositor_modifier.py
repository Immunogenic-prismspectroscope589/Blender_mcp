"""
Compositor Modifier Module for Blender MCP 1.0.0

Implements:
- Compositor Modifiers for per-object post-processing
- VSE compositor modifier strips
- Real-time effects
- Filter chains

High Mode Philosophy: Post-processing without boundaries.
"""

import time
from typing import Dict, Any, List, Optional, Union, cast
from dataclasses import dataclass
from enum import Enum

try:
    import bpy
    import mathutils

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
    mathutils: Any = None  # type: ignore[no-redef]

from .error_protocol import ErrorProtocol, create_error
from .logging_config import get_logger

logger = get_logger()


class CompositorEffectType(Enum):
    """Compositor effect types."""

    BLOOM = "BLOOM"
    GLARE = "GLARE"
    BLUR = "BLUR"
    SHARPEN = "SHARPEN"
    COLOR_CORRECTION = "COLOR_CORRECTION"
    CURVES = "CURVES"
    HUE_SATURATION = "HUE_SATURATION"
    WHITE_BALANCE = "WHITE_BALANCE"
    TONEMAP = "TONEMAP"
    CHROMATIC_ABERRATION = "CHROMATIC_ABERRATION"
    VIGNETTE = "VIGNETTE"


class GlareType(Enum):
    """Glare effect types."""

    GHOSTS = "GHOSTS"
    STREAKS = "STREAKS"
    SIMPLEAR = "SIMPLE_STAR"
    FOG_GLOW = "FOG_GLOW"


@dataclass
class EffectSettings:
    """Base effect settings."""

    intensity: float = 1.0
    enabled: bool = True


class CompositorModifierManager:
    """
    Manage Compositor Modifiers for objects and VSE strips.

    Unlike the global compositor, Compositor Modifiers apply effects
    directly to individual objects or VSE strips.
    """

    @staticmethod
    def add_modifier(
        obj: Any,
        effect: Union[str, CompositorEffectType],
        settings: Optional[Dict[str, Any]] = None,
        node_group_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add Compositor Modifier to object.

        Args:
            obj: Target object
            effect: Effect type or name
            settings: Effect-specific settings
            node_group_name: Custom node group name
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            if isinstance(effect, str):
                effect = CompositorEffectType(effect.upper())

            # Create modifier (1.0.0 Fix for Blender 5.0+ API Drift)
            # "COMPOSITOR" object modifier type does not exist in Blender 5.0+.
            # obj.modifiers.new() raises RuntimeError (not TypeError) for invalid types.
            mod_name = f"Compositor_{effect.value}"
            try:
                mod = obj.modifiers.new(name=mod_name, type="COMPOSITOR")
            except (TypeError, RuntimeError):
                # 1.0.0 Fix: Fallback for Blender 5 Realtime Compositor Proxy (Bug 25)
                scene = getattr(bpy.context, "scene", None)
                if not scene:
                    return create_error(
                        ErrorProtocol.NO_CONTEXT,
                        custom_message="No active scene found for Compositor fallback.",
                    )

                result = RealTimeEffectManager.add_viewport_effect(scene, effect.value, settings)

                if not result.get("success", False):
                    return create_error(
                        ErrorProtocol.API_CHANGED,
                        custom_message="Modifier type 'COMPOSITOR' not found and Viewport Proxy fallback failed.",
                    )

                return {
                    "success": True,
                    "object": obj.name,
                    "modifier": "SCENE_COMPOSITOR_PROXY",
                    "effect": effect.value,
                    "note": "Blender 5.0 fallback: Used Realtime Compositor instead of object modifier.",
                }

            # Create or get node group
            if not node_group_name:
                node_group_name = f"Comp_{effect.value}_{obj.name}"

            if node_group_name in bpy.data.node_groups:
                node_group = bpy.data.node_groups[node_group_name]
            else:
                node_group = CompositorModifierManager._create_effect_node_group(
                    node_group_name, effect, settings
                )

            mod.node_group = node_group

            return {
                "success": True,
                "object": obj.name,
                "modifier": mod.name,
                "effect": effect.value,
                "node_group": node_group.name,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Compositor modifier failed: {str(e)}",
            )

    @staticmethod
    def _create_effect_node_group(
        name: str, effect: CompositorEffectType, settings: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Create node group for specific effect."""
        node_group = bpy.data.node_groups.new(name=name, type="CompositorNodeTree")

        nodes = node_group.nodes
        links = node_group.links

        # Clear default
        nodes.clear()

        # Input/Output — node group context requires NodeGroupInput/Output, not CompositorNodeComposite
        comp_in = cast(Any, nodes.new("NodeGroupInput"))
        comp_in.location = (0, 0)

        comp_out = cast(Any, nodes.new("NodeGroupOutput"))
        comp_out.location = (600, 0)

        last_node = comp_in
        current_x = 200

        if effect == CompositorEffectType.BLOOM:
            node = cast(Any, nodes.new("CompositorNodeGlare"))
            node.glare_type = "BLOOM"
            node.threshold = settings.get("threshold", 0.3) if settings else 0.3
            node.size = settings.get("size", 7) if settings else 7
            node.location = (current_x, 0)
            links.new(last_node.outputs[0], node.inputs[0])
            last_node = node

        elif effect == CompositorEffectType.GLARE:
            node = cast(Any, nodes.new("CompositorNodeGlare"))
            glare_type = settings.get("glare_type", "STREAKS") if settings else "STREAKS"
            node.glare_type = glare_type
            node.threshold = settings.get("threshold", 0.5) if settings else 0.5
            node.streaks = settings.get("streaks", 4) if settings else 4
            node.location = (current_x, 0)
            links.new(last_node.outputs[0], node.inputs[0])
            last_node = node

        elif effect == CompositorEffectType.BLUR:
            node = cast(Any, nodes.new("CompositorNodeBlur"))
            node.filter_type = "GAUSS"
            node.size_x = settings.get("size", 10) if settings else 10
            node.size_y = settings.get("size", 10) if settings else 10
            node.location = (current_x, 0)
            links.new(last_node.outputs[0], node.inputs[0])
            last_node = node

        elif effect == CompositorEffectType.SHARPEN:
            node = cast(Any, nodes.new("CompositorNodeFilter"))
            node.filter_type = "SHARPEN"
            node.location = (current_x, 0)
            links.new(last_node.outputs[0], node.inputs[1])
            last_node = node

        elif effect == CompositorEffectType.COLOR_CORRECTION:
            node = cast(Any, nodes.new("CompositorNodeColorCorrection"))
            node.red.highlight = settings.get("red", 1.0) if settings else 1.0
            node.green.highlight = settings.get("green", 1.0) if settings else 1.0
            node.blue.highlight = settings.get("blue", 1.0) if settings else 1.0
            node.location = (current_x, 0)
            links.new(last_node.outputs[0], node.inputs[1])
            last_node = node

        elif effect == CompositorEffectType.CURVES:
            node = cast(Any, nodes.new("CompositorNodeHueSat"))
            node.location = (current_x, 0)
            node.color_saturation = settings.get("saturation", 1.0) if settings else 1.0
            node.color_value = settings.get("value", 1.0) if settings else 1.0
            links.new(last_node.outputs[0], node.inputs[1])
            last_node = node

        elif effect == CompositorEffectType.CHROMATIC_ABERRATION:
            # Separate channels
            sep = cast(Any, nodes.new("CompositorNodeSepRGBA"))
            sep.location = (current_x, 0)

            # Offset R and B channels
            shift_r = cast(Any, nodes.new("CompositorNodeTranslate"))
            shift_r.location = (current_x + 200, 100)
            shift_r.inputs["X"].default_value = -5

            shift_b = cast(Any, nodes.new("CompositorNodeTranslate"))
            shift_b.location = (current_x + 200, -100)
            shift_b.inputs["X"].default_value = 5

            # Combine
            comb = cast(Any, nodes.new("CompositorNodeCombRGBA"))
            comb.location = (current_x + 400, 0)

            links.new(last_node.outputs[0], sep.inputs[0])
            links.new(sep.outputs[0], shift_r.inputs[0])  # R
            links.new(sep.outputs[1], comb.inputs[1])  # G (no shift)
            links.new(sep.outputs[2], shift_b.inputs[0])  # B
            links.new(shift_r.outputs[0], comb.inputs[0])
            links.new(shift_b.outputs[0], comb.inputs[2])

            last_node = comb

        elif effect == CompositorEffectType.VIGNETTE:
            # Ellipse mask
            ellipse = cast(Any, nodes.new("CompositorNodeEllipseMask"))
            ellipse.location = (current_x, -100)
            ellipse.width = 0.8
            ellipse.height = 0.8

            # Blur mask
            blur = cast(Any, nodes.new("CompositorNodeBlur"))
            blur.location = (current_x + 200, -100)
            blur.filter_type = "GAUSS"
            blur.size_x = 100
            blur.size_y = 100

            # Mix
            mix = cast(Any, nodes.new("CompositorNodeMixRGB"))
            mix.location = (current_x + 400, 0)
            mix.blend_type = "MULTIPLY"
            mix.inputs[2].default_value = (0, 0, 0, 1)

            links.new(ellipse.outputs[0], blur.inputs[0])
            links.new(blur.outputs[0], mix.inputs[0])  # Factor
            links.new(last_node.outputs[0], mix.inputs[1])  # Image

            last_node = mix

        # Connect to output
        links.new(last_node.outputs[0], comp_out.inputs[0])

        return node_group

    @staticmethod
    def remove_modifier(obj: Any, modifier_name: str) -> Dict[str, Any]:
        """
        Remove Compositor Modifier from object.
        """
        try:
            mod = obj.modifiers.get(modifier_name)
            if not mod:
                return create_error(ErrorProtocol.OBJECT_NOT_FOUND, object_name=modifier_name)

            obj.modifiers.remove(mod)

            return {"success": True, "object": obj.name, "removed": modifier_name}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Remove modifier failed: {str(e)}"
            )

    @staticmethod
    def create_effect_chain(obj: Any, effects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create chain of compositor effects.

        Args:
            effects: List of effect configs
                [{"effect": "BLOOM", "settings": {...}}, ...]
        """
        try:
            results = []
            for i, effect_config in enumerate(effects):
                effect = effect_config.get("effect")
                settings = effect_config.get("settings", {})
                if effect is None:
                    effect = CompositorEffectType.BLOOM.value

                result = CompositorModifierManager.add_modifier(
                    obj, effect, settings, node_group_name=f"CompChain_{obj.name}_{i}"
                )
                results.append(result)

            return {
                "success": True,
                "object": obj.name,
                "effects_added": len(results),
                "results": results,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Effect chain failed: {str(e)}"
            )


class VSECompositorManager:
    """
    Manage Compositor effects in Video Sequence Editor.
    """

    @staticmethod
    def add_compositor_strip(
        scene: Any,
        frame_start: int,
        frame_end: int,
        channel: int = 1,
        effect_type: str = "BLOOM",
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add compositor strip to VSE.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Ensure sequence editor exists
            if not scene.sequence_editor:
                scene.sequence_editor_create()

            # Create adjustment layer or use scene
            # For compositor strips, we need a scene strip
            # First, create a scene for the compositor effect
            effect_scene_name = f"CompEffect_{effect_type}_{time.time()}"
            effect_scene = bpy.data.scenes.new(name=effect_scene_name)

            # Setup compositor in effect scene
            effect_scene.use_nodes = True
            tree = effect_scene.node_tree
            if not tree:
                return create_error(
                    ErrorProtocol.EXECUTION_ERROR,
                    custom_message="Failed to get compositor node tree",
                )

            nodes = tree.nodes
            links = tree.links

            nodes.clear()

            # Create render layer and composite
            render_layers = nodes.new("CompositorNodeRLayers")
            composite = nodes.new("CompositorNodeComposite")

            # Add effect
            if effect_type == "BLOOM":
                effect_node = nodes.new("CompositorNodeGlare")
                cast(Any, effect_node).glare_type = "FOG_GLOW"
                cast(Any, effect_node).threshold = (
                    settings.get("threshold", 0.3) if settings else 0.3
                )
                links.new(render_layers.outputs[0], effect_node.inputs[0])
                links.new(effect_node.outputs[0], composite.inputs[0])
            elif effect_type == "BLUR":
                effect_node = nodes.new("CompositorNodeBlur")
                cast(Any, effect_node).size_x = settings.get("size", 10) if settings else 10
                cast(Any, effect_node).size_y = settings.get("size", 10) if settings else 10
                links.new(render_layers.outputs[0], effect_node.inputs[0])
                links.new(effect_node.outputs[0], composite.inputs[0])
            else:
                links.new(render_layers.outputs[0], composite.inputs[0])

            # Add scene strip
            seq_editor = scene.sequence_editor
            strip = seq_editor.sequences.new_scene(
                name=f"Comp_{effect_type}",
                scene=effect_scene,
                channel=channel,
                frame_start=frame_start,
            )
            strip.frame_final_duration = frame_end - frame_start

            return {
                "success": True,
                "scene": effect_scene_name,
                "strip": strip.name,
                "channel": channel,
                "effect": effect_type,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"VSE compositor strip failed: {str(e)}",
            )


class RealTimeEffectManager:
    """
    Manage real-time compositor effects.
    """

    @staticmethod
    def setup_realtime_compositor(scene: Any, enabled: bool = True) -> Dict[str, Any]:
        """
        Enable real-time compositor for viewport.
        """
        try:
            # Enable real-time compositor (Blender 5.0+)
            if hasattr(scene, "use_nodes_realtime_compositor"):
                scene.use_nodes_realtime_compositor = enabled

                return {"success": True, "realtime_compositor": enabled, "mode": "viewport"}
            else:
                return create_error(
                    ErrorProtocol.NOT_IMPLEMENTED,
                    custom_message="Real-time compositor not available",
                )

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Real-time compositor setup failed: {str(e)}",
            )

    @staticmethod
    def add_viewport_effect(
        scene: Any, effect_type: str, settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add effect to viewport compositor.
        Dual-path: Blender 5.0 uses scene.compositing_node_group; 4.x uses scene.use_nodes.
        """
        try:
            import bpy as _bpy

            # --- Blender 5.0 path ---
            if hasattr(scene, "compositing_node_group"):
                tree = scene.compositing_node_group
                if tree is None:
                    tree = _bpy.data.node_groups.new("MCPCompositor", "CompositorNodeTree")
                    scene.compositing_node_group = tree
                    # Create output node + socket
                    out_node = tree.nodes.new(type="NodeGroupOutput")
                    out_node.location = (600, 0)
                    if hasattr(tree, "interface"):
                        tree.interface.new_socket(
                            name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
                        )

                nodes = tree.nodes
                links = tree.links

                # Find or create input / output nodes
                input_node = next((n for n in nodes if n.type == "GROUP_INPUT"), None)
                output_node = next((n for n in nodes if n.type == "GROUP_OUTPUT"), None)
                if output_node is None:
                    output_node = nodes.new(type="NodeGroupOutput")
                    output_node.location = (600, 0)

                if effect_type == "BLOOM":
                    glare = nodes.new("CompositorNodeGlare")
                    # Blender 5.0: glare_type removed — now an input socket named 'Type'
                    if hasattr(glare, "glare_type"):
                        glare.glare_type = "BLOOM"
                    elif "Type" in glare.inputs:
                        glare.inputs["Type"].default_value = "BLOOM"
                    glare.location = (200, 0)
                    # Wire: input_node → glare → output_node (if input exists)
                    if input_node and input_node.outputs and output_node.inputs:
                        links.new(input_node.outputs[0], glare.inputs[0])
                        links.new(glare.outputs[0], output_node.inputs[0])
                    elif output_node.inputs:
                        # No input node yet; wire glare directly to output
                        links.new(glare.outputs[0], output_node.inputs[0])

            # --- Blender 4.x fallback ---
            else:
                if not scene.use_nodes:
                    scene.use_nodes = True

                tree = scene.node_tree
                nodes = tree.nodes
                links = tree.links

                composite = next((n for n in nodes if n.type == "COMPOSITE"), None)
                render_layers = next((n for n in nodes if n.type == "R_LAYERS"), None)

                if not composite:
                    composite = nodes.new("CompositorNodeComposite")
                    composite.location = (400, 0)
                if not render_layers:
                    render_layers = nodes.new("CompositorNodeRLayers")
                    render_layers.location = (-400, 0)
                    links.new(render_layers.outputs[0], composite.inputs[0])

                if effect_type == "BLOOM":
                    glare = nodes.new("CompositorNodeGlare")
                    # Blender 5.0: glare_type removed — now an input socket named 'Type'
                    if hasattr(glare, "glare_type"):
                        glare.glare_type = "BLOOM"
                    elif "Type" in glare.inputs:
                        glare.inputs["Type"].default_value = "BLOOM"
                    glare.location = (0, 0)
                    # Insert between current source → composite
                    for link in list(links):
                        if link.to_node == composite:
                            old_out = link.from_socket
                            links.remove(link)
                            links.new(old_out, glare.inputs[0])
                            break
                    links.new(glare.outputs[0], composite.inputs[0])

            # Enable real-time compositor if available
            if hasattr(scene, "use_nodes_realtime_compositor"):
                scene.use_nodes_realtime_compositor = True

            return {"success": True, "scene": scene.name, "effect": effect_type, "viewport": True}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Viewport effect failed: {str(e)}"
            )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CompositorModifierManager",
    "VSECompositorManager",
    "RealTimeEffectManager",
    "CompositorEffectType",
    "GlareType",
]
