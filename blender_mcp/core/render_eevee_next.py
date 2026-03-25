"""
Eevee Next Render Engine Module for Blender MCP 1.0.0

Implements:
- Raytracing settings
- Shadow quality
- Screen-space effects
- View Layer overrides
- Performance optimization

High Mode Philosophy: Maximum visual quality, maximum performance.
"""

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


class EeveeNextQualityPreset(Enum):
    """Quality presets for Eevee Next."""

    DRAFT = "DRAFT"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ULTRA = "ULTRA"
    PRODUCTION = "PRODUCTION"


class RaytracingQualityPreset(Enum):
    """Raytracing quality presets."""

    OFF = "OFF"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ULTRA = "ULTRA"


@dataclass
class EeveeNextSettings:
    """Eevee Next render settings configuration."""

    # TAA
    taa_samples: int = 16
    taa_render_samples: int = 64
    use_taa_reprojection: bool = True

    # Raytracing
    raytracing_enabled: bool = True
    ray_count: int = 4
    step_count: int = 12
    denoise_enabled: bool = True

    # Shadows
    shadow_ray_count: int = 3
    shadow_step_count: int = 6
    shadow_resolution: int = 1024

    # Screen Space Reflections
    ssr_enabled: bool = True
    ssr_quality: float = 0.5
    ssr_thickness: float = 0.5

    # Ambient Occlusion (GTAO)
    gtao_enabled: bool = True
    gtao_distance: float = 0.5
    gtao_factor: float = 0.5

    # Volumetrics
    volumetric_enabled: bool = True
    volumetric_samples: int = 64
    volumetric_tile_size: int = 8

    # Subsurface
    sss_samples: int = 4

    # Motion Blur
    motion_blur_enabled: bool = False
    motion_blur_steps: int = 8


class EeveeNextManager:
    """
    Manage Eevee Next render settings.
    """

    PRESETS = {
        EeveeNextQualityPreset.DRAFT: EeveeNextSettings(
            taa_samples=4,
            taa_render_samples=4,
            raytracing_enabled=False,
            ssr_enabled=False,
            gtao_enabled=False,
            volumetric_samples=16,
        ),
        EeveeNextQualityPreset.LOW: EeveeNextSettings(
            taa_samples=8,
            taa_render_samples=16,
            raytracing_enabled=True,
            ray_count=2,
            step_count=8,
            shadow_ray_count=2,
            ssr_quality=0.25,
        ),
        EeveeNextQualityPreset.MEDIUM: EeveeNextSettings(
            taa_samples=16,
            taa_render_samples=32,
            raytracing_enabled=True,
            ray_count=4,
            step_count=12,
            shadow_ray_count=3,
            ssr_quality=0.5,
        ),
        EeveeNextQualityPreset.HIGH: EeveeNextSettings(
            taa_samples=16,
            taa_render_samples=64,
            raytracing_enabled=True,
            ray_count=8,
            step_count=24,
            shadow_ray_count=4,
            ssr_quality=0.75,
            gtao_factor=0.75,
        ),
        EeveeNextQualityPreset.ULTRA: EeveeNextSettings(
            taa_samples=32,
            taa_render_samples=128,
            raytracing_enabled=True,
            ray_count=16,
            step_count=48,
            shadow_ray_count=6,
            ssr_quality=1.0,
            volumetric_samples=128,
        ),
        EeveeNextQualityPreset.PRODUCTION: EeveeNextSettings(
            taa_samples=32,
            taa_render_samples=256,
            raytracing_enabled=True,
            ray_count=32,
            step_count=96,
            shadow_ray_count=8,
            ssr_quality=1.0,
            volumetric_samples=256,
            motion_blur_enabled=True,
        ),
    }

    @staticmethod
    def setup_eevee_next(
        scene: Any,
        preset: Union[str, EeveeNextQualityPreset] = "HIGH",
        custom_settings: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Configure Eevee Next with preset or custom settings.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Set render engine
            scene.render.engine = "BLENDER_EEVEE"

            # Get preset settings
            if isinstance(preset, str):
                preset = EeveeNextQualityPreset(preset.upper())

            settings = EeveeNextManager.PRESETS.get(
                preset, EeveeNextManager.PRESETS[EeveeNextQualityPreset.HIGH]
            )

            # Apply custom overrides
            if custom_settings:
                for key, value in custom_settings.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)

            # Apply to scene
            eevee = scene.eevee

            # TAA
            if hasattr(eevee, "taa_samples"):
                eevee.taa_samples = settings.taa_samples
            if hasattr(eevee, "taa_render_samples"):
                eevee.taa_render_samples = settings.taa_render_samples
            if hasattr(eevee, "use_taa_reprojection"):
                eevee.use_taa_reprojection = settings.use_taa_reprojection

            # Raytracing (Blender 5.0+)
            if hasattr(eevee, "ray_tracing_options"):
                rt = eevee.ray_tracing_options
                # Fallback for attribute name changes in stable 5.0 (1.0.0 Fix)
                if hasattr(rt, "enabled"):
                    rt.enabled = settings.raytracing_enabled
                elif hasattr(rt, "use_raytracing"):
                    rt.use_raytracing = settings.raytracing_enabled
                elif hasattr(eevee, "use_raytracing"):
                    eevee.use_raytracing = settings.raytracing_enabled

                if settings.raytracing_enabled:
                    if hasattr(rt, "ray_count"):
                        rt.ray_count = settings.ray_count
                    if hasattr(rt, "step_count"):
                        rt.step_count = settings.step_count
                    if hasattr(rt, "use_denoise"):
                        rt.use_denoise = settings.denoise_enabled

            # Shadows
            if hasattr(eevee, "shadow_ray_count"):
                eevee.shadow_ray_count = settings.shadow_ray_count
            if hasattr(eevee, "shadow_step_count"):
                eevee.shadow_step_count = settings.shadow_step_count

            # SSR (Removed in 5.0.1 - Handled by Raytracing/ScreenTrace)
            # eevee.use_ssr = settings.ssr_enabled
            # if settings.ssr_enabled:
            #     eevee.ssr_thickness = settings.ssr_thickness

            # GTAO
            if hasattr(eevee, "use_gtao"):
                eevee.use_gtao = settings.gtao_enabled
                if settings.gtao_enabled:
                    if hasattr(eevee, "gtao_distance"):
                        eevee.gtao_distance = settings.gtao_distance
                    if hasattr(eevee, "gtao_factor"):
                        eevee.gtao_factor = settings.gtao_factor

            # Volumetrics
            if hasattr(eevee, "volumetric_enable"):
                eevee.volumetric_enable = settings.volumetric_enabled
                if settings.volumetric_enabled:
                    if hasattr(eevee, "volumetric_samples"):
                        eevee.volumetric_samples = settings.volumetric_samples
                    if hasattr(eevee, "volumetric_tile_size"):
                        eevee.volumetric_tile_size = settings.volumetric_tile_size

            # Subsurface
            if hasattr(eevee, "sss_samples"):
                eevee.sss_samples = settings.sss_samples

            # Motion Blur
            if hasattr(eevee, "use_motion_blur"):
                eevee.use_motion_blur = settings.motion_blur_enabled
            if settings.motion_blur_enabled:
                eevee.motion_blur_steps = settings.motion_blur_steps

            return {
                "success": True,
                "engine": "BLENDER_EEVEE_NEXT",
                "preset": preset.value,
                "settings": {
                    "taa_render_samples": settings.taa_render_samples,
                    "ray_count": settings.ray_count if settings.raytracing_enabled else 0,
                    "shadow_ray_count": settings.shadow_ray_count,
                    "volumetric_samples": settings.volumetric_samples,
                },
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Eevee Next setup failed: {str(e)}"
            )

    @staticmethod
    def setup_raytracing(
        scene: Any, quality: Union[str, RaytracingQualityPreset] = "HIGH"
    ) -> Dict[str, Any]:
        """
        Configure raytracing settings specifically.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            if isinstance(quality, str):
                quality = RaytracingQualityPreset(quality.upper())

            eevee = scene.eevee

            if not hasattr(eevee, "ray_tracing_options"):
                return create_error(
                    ErrorProtocol.NOT_IMPLEMENTED,
                    custom_message="Raytracing not available in this Blender version",
                )

            rt = eevee.ray_tracing_options

            if quality == RaytracingQualityPreset.OFF:
                rt.enabled = False
                return {"success": True, "raytracing": "disabled"}

            rt.enabled = True

            quality_settings = {
                RaytracingQualityPreset.LOW: (2, 8, True),
                RaytracingQualityPreset.MEDIUM: (4, 12, True),
                RaytracingQualityPreset.HIGH: (8, 24, True),
                RaytracingQualityPreset.ULTRA: (16, 48, True),
            }

            ray_count, step_count, denoise = quality_settings.get(quality, (4, 12, True))

            rt.ray_count = ray_count
            rt.step_count = step_count
            rt.use_denoise = denoise

            return {
                "success": True,
                "raytracing_quality": quality.value,
                "ray_count": ray_count,
                "step_count": step_count,
                "denoise": denoise,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Raytracing setup failed: {str(e)}"
            )

    @staticmethod
    def optimize_for_viewport(scene: Any, quality: str = "BALANCED") -> Dict[str, Any]:
        """
        Optimize settings for viewport performance.
        """
        try:
            eevee = scene.eevee

            optimizations = {
                "PERFORMANCE": {
                    "taa_samples": 4,
                    # "use_ssr": False, # Removed in 5.0.1
                    "use_gtao": False,
                    "volumetric_enable": False,
                    "raytracing": False,
                },
                "BALANCED": {
                    "taa_samples": 8,
                    # "use_ssr": True,
                    "use_gtao": True,
                    "volumetric_enable": True,
                    "raytracing": False,
                },
                "QUALITY": {
                    "taa_samples": 16,
                    # "use_ssr": True,
                    "use_gtao": True,
                    "volumetric_enable": True,
                    "raytracing": True,
                },
            }

            opt = optimizations.get(quality, optimizations["BALANCED"])

            eevee.taa_samples = opt["taa_samples"]
            # eevee.use_ssr = opt["use_ssr"]
            if hasattr(eevee, "use_gtao"):
                eevee.use_gtao = opt["use_gtao"]
            eevee.volumetric_enable = opt["volumetric_enable"]

            if hasattr(eevee, "ray_tracing_options"):
                eevee.ray_tracing_options.enabled = opt["raytracing"]

            return {"success": True, "viewport_mode": quality, "settings": opt}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Viewport optimization failed: {str(e)}",
            )


class ViewLayerManager:
    """
    Manage View Layers with overrides and specific settings.
    """

    @staticmethod
    def create_clay_render_view_layer(scene: Any, name: str = "Clay") -> Dict[str, Any]:
        """
        Create view layer optimized for clay/Greybox rendering.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Create view layer
            if name in scene.view_layers:
                vl = scene.view_layers[name]
            else:
                vl = scene.view_layers.new(name=name)

            # Create clay material
            mat_name = "CLAY_MATERIAL"
            if mat_name not in bpy.data.materials:
                mat = bpy.data.materials.new(name=mat_name)
                mat.use_nodes = True
                nodes = cast(Any, mat.node_tree).nodes
                nodes.clear()

                # Simple white diffuse
                bsdf = cast(Any, nodes.new("ShaderNodeBsdfDiffuse"))
                bsdf.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)
                bsdf.inputs["Roughness"].default_value = 0.9

                output = nodes.new("ShaderNodeOutputMaterial")

                mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

            # Set material override
            vl.material_override = bpy.data.materials[mat_name]

            # Disable unnecessary passes for performance
            vl.use_pass_combined = True
            vl.use_pass_z = False
            vl.use_pass_normal = False
            vl.use_pass_diffuse_color = False

            return {
                "success": True,
                "view_layer": name,
                "material_override": mat_name,
                "purpose": "clay_render",
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Clay view layer failed: {str(e)}"
            )

    @staticmethod
    def create_wireframe_view_layer(scene: Any, name: str = "Wireframe") -> Dict[str, Any]:
        """
        Create view layer for wireframe rendering.
        """
        try:
            if name in scene.view_layers:
                vl = scene.view_layers[name]
            else:
                vl = scene.view_layers.new(name=name)

            # Create wireframe material
            mat_name = "WIREFRAME_MATERIAL"
            if mat_name not in bpy.data.materials:
                mat = bpy.data.materials.new(name=mat_name)
                mat.use_nodes = True
                if not mat.node_tree:
                    return create_error(
                        ErrorProtocol.EXECUTION_ERROR, custom_message="Material node tree missing"
                    )
                nodes = mat.node_tree.nodes
                nodes.clear()

                wireframe = cast(Any, nodes.new("ShaderNodeWireframe"))
                wireframe.inputs["Size"].default_value = 0.5

                emission = cast(Any, nodes.new("ShaderNodeEmission"))
                emission.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
                emission.inputs["Strength"].default_value = 1.0

                output = nodes.new("ShaderNodeOutputMaterial")

                mat.node_tree.links.new(wireframe.outputs[0], emission.inputs["Strength"])
                mat.node_tree.links.new(emission.outputs[0], output.inputs[0])

            vl.material_override = bpy.data.materials[mat_name]

            return {
                "success": True,
                "view_layer": name,
                "material_override": mat_name,
                "purpose": "wireframe_render",
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Wireframe view layer failed: {str(e)}",
            )

    @staticmethod
    def set_view_layer_override(view_layer: Any, override_type: str, value: Any) -> Dict[str, Any]:
        """
        Set various overrides for view layer.

        Args:
            override_type: 'material', 'world', 'samples'
            value: Override value
        """
        try:
            if override_type == "material":
                mat = bpy.data.materials.get(value)
                if not mat:
                    return create_error(ErrorProtocol.OBJECT_NOT_FOUND, object_name=value)
                view_layer.material_override = mat

            elif override_type == "world":
                world = bpy.data.worlds.get(value)
                if not world:
                    return create_error(ErrorProtocol.OBJECT_NOT_FOUND, object_name=value)
                view_layer.world_override = world

            elif override_type == "samples":
                view_layer.samples = int(value)

            return {
                "success": True,
                "view_layer": view_layer.name,
                "override_type": override_type,
                "value": value,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"View layer override failed: {str(e)}",
            )


class RenderPassManager:
    """
    Manage render passes for compositing.
    """

    PASS_TYPES = {
        "combined": "use_pass_combined",
        "z": "use_pass_z",
        "mist": "use_pass_mist",
        "normal": "use_pass_normal",
        "diffuse": "use_pass_diffuse_direct",
        "specular": "use_pass_specular_direct",
        "emit": "use_pass_emit",
        "environment": "use_pass_environment",
        "ao": "use_pass_ambient_occlusion",
        "shadow": "use_pass_shadow",
    }

    @staticmethod
    def enable_passes(view_layer: Any, passes: List[str]) -> Dict[str, Any]:
        """
        Enable specific render passes.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            enabled = []
            failed = []

            for pass_name in passes:
                attr = RenderPassManager.PASS_TYPES.get(pass_name.lower())
                if attr and hasattr(view_layer, attr):
                    setattr(view_layer, attr, True)
                    enabled.append(pass_name)
                else:
                    failed.append(pass_name)

            return {
                "success": True,
                "view_layer": view_layer.name,
                "enabled_passes": enabled,
                "failed": failed,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Enable passes failed: {str(e)}"
            )

    @staticmethod
    def setup_cryptomatte(
        view_layer: Any,
        levels: int = 6,
        asset: bool = True,
        material: bool = True,
        object_: bool = True,
    ) -> Dict[str, Any]:
        """
        Setup Cryptomatte for compositing.
        """
        try:
            view_layer.use_pass_cryptomatte = True
            view_layer.pass_cryptomatte_depth = levels
            view_layer.use_pass_cryptomatte_asset = asset
            view_layer.use_pass_cryptomatte_material = material
            view_layer.use_pass_cryptomatte_object = object_

            return {
                "success": True,
                "view_layer": view_layer.name,
                "levels": levels,
                "asset": asset,
                "material": material,
                "object": object_,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Cryptomatte setup failed: {str(e)}"
            )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "EeveeNextManager",
    "ViewLayerManager",
    "RenderPassManager",
    "EeveeNextQualityPreset",
    "RaytracingQualityPreset",
    "EeveeNextSettings",
]
