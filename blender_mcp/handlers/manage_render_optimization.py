"""Render Optimization Handler for Blender MCP 1.0.0 - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

try:
    import bpy
    import mathutils

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    mathutils = None
from ..dispatcher import register_handler
from ..core.parameter_validator import validated_handler
from ..core.enums import RenderOptimizationAction, RenderEngine
from ..core.resolver import resolve_name
from ..core.thread_safety import ensure_main_thread
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils
from typing import Any

logger = get_logger()


@register_handler(
    "manage_render_optimization",
    actions=[a.value for a in RenderOptimizationAction],
    category="general",
    schema={
        "type": "object",
        "title": "Render Optimization",
        "description": "Advanced rendering optimization for faster, cleaner output.",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                RenderOptimizationAction, "Optimization action"
            ),
            "object_name": {"type": "string"},
            "quality_target": {
                "type": "string",
                "enum": ["DRAFT", "PREVIEW", "PRODUCTION", "FINAL"],
                "default": "PRODUCTION",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in RenderOptimizationAction])
def manage_render_optimization(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Advanced rendering optimization tools.

    Actions:
    - OPTIMIZE_SAMPLES: Auto-calculate optimal sample count based on scene
    - DENOISE_SETUP: Configure Intel OID or OptiX denoising
    - ADAPTIVE_SAMPLING: Enable/disable adaptive sampling
    - ADAPTIVE_SUBDIVISION: Setup adaptive subdivision surfaces
    - LIGHT_TREE: Build and enable light tree for faster rendering
    - BAKE_IRRADIANCE: Pre-bake indirect lighting
    - RENDER_REGION: Auto-detect or manual render regions
    - GPU_MEMORY_OPTIMIZE: Optimize for GPU memory limits
    - TILE_SIZE_OPTIMIZE: Optimize tile size for hardware
    - OPTIMIZE_FOR_ANIMATION: Animation-optimized settings
    - OPTIMIZE_FOR_STILL: Still image optimized settings
    """
    scene = bpy.context.scene

    # Sample Optimization
    if not action:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == RenderOptimizationAction.OPTIMIZE_SAMPLES.value:
        return _optimize_samples(scene, params)  # type: ignore[no-any-return]

    # Denoising
    elif action == RenderOptimizationAction.DENOISE_SETUP.value:
        return _denoise_setup(scene, params)  # type: ignore[no-any-return]
    elif action == RenderOptimizationAction.DENOISE_ENABLE.value:
        return _denoise_toggle(scene, True)  # type: ignore[no-any-return]
    elif action == RenderOptimizationAction.DENOISE_DISABLE.value:
        return _denoise_toggle(scene, False)  # type: ignore[no-any-return]

    # Adaptive Sampling
    elif action == RenderOptimizationAction.ADAPTIVE_SAMPLING_ENABLE.value:
        return _adaptive_sampling(scene, True)  # type: ignore[no-any-return]
    elif action == RenderOptimizationAction.ADAPTIVE_SAMPLING_DISABLE.value:
        return _adaptive_sampling(scene, False)  # type: ignore[no-any-return]

    # Adaptive Subdivision
    elif action == RenderOptimizationAction.ADAPTIVE_SUBDIVISION_SETUP.value:
        return _adaptive_subdivision_setup(params)  # type: ignore[no-any-return]

    # Light Tree
    elif action == RenderOptimizationAction.LIGHT_TREE_BUILD.value:
        return _light_tree_build(scene)  # type: ignore[no-any-return]
    elif action == RenderOptimizationAction.LIGHT_TREE_ENABLE.value:
        return _light_tree_toggle(scene, True)  # type: ignore[no-any-return]

    # Irradiance Baking
    elif action == RenderOptimizationAction.BAKE_IRRADIANCE.value:
        return _bake_irradiance(scene, params)  # type: ignore[no-any-return]

    # Render Regions
    elif action == RenderOptimizationAction.RENDER_REGION_AUTO.value:
        return _render_region_auto(scene, params)  # type: ignore[no-any-return]
    elif action == RenderOptimizationAction.RENDER_REGION_SET.value:
        return _render_region_set(scene, params)  # type: ignore[no-any-return]

    # GPU Optimization
    elif action == RenderOptimizationAction.GPU_MEMORY_OPTIMIZE.value:
        return _gpu_memory_optimize(scene, params)  # type: ignore[no-any-return]
    elif action == RenderOptimizationAction.TILE_SIZE_OPTIMIZE.value:
        return _tile_size_optimize(scene, params)  # type: ignore[no-any-return]

    # Preset Optimizations
    elif action == RenderOptimizationAction.OPTIMIZE_FOR_ANIMATION.value:
        return _optimize_for_animation(scene, params)  # type: ignore[no-any-return]
    elif action == RenderOptimizationAction.OPTIMIZE_FOR_STILL.value:
        return _optimize_for_still(scene, params)  # type: ignore[no-any-return]
    elif action == RenderOptimizationAction.PERSISTENT_DATA_ENABLE.value:
        return _persistent_data_enable(scene)  # type: ignore[no-any-return]

    # Resolution
    elif action == RenderOptimizationAction.RESOLUTION_SCALE.value:
        return _resolution_scale(scene, params)  # type: ignore[no-any-return]

    # Reporting
    elif action == RenderOptimizationAction.SAMPLE_OPTIMIZATION_REPORT.value:
        return _sample_optimization_report(scene)  # type: ignore[no-any-return]

    return ResponseBuilder.error(
        handler="manage_render_optimization",
        action=action,
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown action: {action}",
    )


# =============================================================================
# SAMPLE OPTIMIZATION
# =============================================================================


def _optimize_samples(scene, params):  # type: ignore[no-untyped-def]
    """Auto-calculate optimal sample count based on scene complexity."""

    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="OPTIMIZE_SAMPLES",
            error_code="WRONG_ENGINE",
            message=(
                f"Sample optimization requires Cycles. "
                f"Current engine: '{scene.render.engine}'. "
                f"Use manage_rendering(action='SET_ENGINE', engine='CYCLES') first."
            ),
        )

    quality = params.get("quality_target", "PRODUCTION")

    # Analyze scene complexity
    complexity_score = _analyze_scene_complexity(scene)

    # Base samples by quality
    base_samples = {"DRAFT": 32, "PREVIEW": 64, "PRODUCTION": 128, "FINAL": 512}

    base = base_samples.get(quality, 128)

    # Adjust by complexity (0.5 to 2.0 multiplier)
    complexity_multiplier = 0.5 + (complexity_score * 1.5)
    optimal_samples = int(base * complexity_multiplier)

    # Round to nice numbers
    optimal_samples = _round_samples(optimal_samples)

    # Apply
    scene.cycles.samples = optimal_samples

    # Enable adaptive sampling for high complexity
    if complexity_score > 0.7:
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.01

    return {
        "success": True,
        "optimized_samples": optimal_samples,
        "base_samples": base,
        "complexity_multiplier": round(complexity_multiplier, 2),
        "complexity_score": round(complexity_score, 2),
        "adaptive_sampling": scene.cycles.use_adaptive_sampling,
    }


def _analyze_scene_complexity(scene):  # type: ignore[no-untyped-def]
    """Analyze scene complexity (0.0 to 1.0)."""
    score = 0.0

    # Count lights
    light_count = sum(1 for obj in scene.objects if obj.type == "LIGHT")
    score += min(light_count / 10, 0.3)  # Max 0.3 from lights

    # Count mesh objects
    mesh_count = sum(1 for obj in scene.objects if obj.type == "MESH")
    score += min(mesh_count / 50, 0.2)  # Max 0.2 from meshes

    # Check for subsurface scattering
    sss_count = 0
    for mat in bpy.data.materials:
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "SUBSURFACE_SCATTERING":
                    sss_count += 1  # type: ignore
    score += min(sss_count / 5, 0.15)

    # Check for volumetrics
    volume_count = 0
    for mat in bpy.data.materials:
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if "VOLUME" in node.type:
                    volume_count += 1
    score += min(volume_count / 3, 0.15)

    # Check for glass/transparent materials
    glass_count = 0
    for mat in bpy.data.materials:
        if mat.use_nodes:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf and hasattr(bsdf.inputs["Transmission Weight"], "default_value"):
                if bsdf.inputs["Transmission Weight"].default_value > 0:
                    glass_count += 1
    score += min(glass_count / 5, 0.2)

    return min(score, 1.0)


def _round_samples(samples):  # type: ignore[no-untyped-def]
    """Round to nice sample numbers."""
    if samples < 32:
        return 32
    elif samples < 64:
        return 64
    elif samples < 128:
        return 128
    elif samples < 256:
        return 256
    elif samples < 512:
        return 512
    elif samples < 1024:
        return 1024
    elif samples < 2048:
        return 2048
    else:
        return 4096


# =============================================================================
# DENOISING
# =============================================================================


def _denoise_setup(scene, params):  # type: ignore[no-untyped-def]
    """Configure denoising with automatic fallback."""

    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="DENOISE_SETUP",
            error_code="EXECUTION_ERROR",
            message="Denoising setup only works with Cycles",
        )

    denoiser = params.get("denoiser", "OPENIMAGEDENOISE")  # Default to OID for compatibility

    # Enable denoising
    scene.cycles.use_denoising = True

    # Try to set denoiser with fallback
    denoiser_set = None
    fallback_used = False

    if denoiser == "OPTIX":
        try:
            # Try OPTIX first (NVIDIA GPU only)
            scene.cycles.denoiser = "OPTIX"
            denoiser_set = "OPTIX"
        except (TypeError, ValueError) as e:
            # OPTIX not available, fallback to OID
            print(f"[MCP] OPTIX not available, falling back to OpenImageDenoise: {e}")
            try:
                scene.cycles.denoiser = "OPENIMAGEDENOISE"
                denoiser_set = "OPENIMAGEDENOISE"
                fallback_used = True
            except (TypeError, ValueError) as e2:
                return ResponseBuilder.error(
                    handler="manage_render_optimization",
                    action="DENOISE_SETUP",
                    error_code="EXECUTION_ERROR",
                    message=f"No denoiser available: {e2}",
                )
    else:
        # Use requested denoiser or default
        try:
            scene.cycles.denoiser = denoiser
            denoiser_set = denoiser
        except (TypeError, ValueError):
            # Try OID as ultimate fallback
            try:
                scene.cycles.denoiser = "OPENIMAGEDENOISE"
                denoiser_set = "OPENIMAGEDENOISE"
                fallback_used = True
            except (TypeError, ValueError) as e2:
                return ResponseBuilder.error(
                    handler="manage_render_optimization",
                    action="DENOISE_SETUP",
                    error_code="EXECUTION_ERROR",
                    message=f"Could not set denoiser: {e2}",
                )

    # Denoising settings
    input_passes = params.get("input_passes", "RGB_ALBEDO_NORMAL")
    try:
        scene.cycles.denoising_input_passes = input_passes
    except (TypeError, ValueError):
        # Fallback to simpler passes if combination not supported
        scene.cycles.denoising_input_passes = "RGB"

    # Also enable compositor denoising for final output
    from ..core.versioning import BlenderCompatibility

    BlenderCompatibility.ensure_compositor_tree(scene)
    tree = BlenderCompatibility.get_compositor_tree(scene)

    if not tree:
        return {
            "success": False,
            "message": "Could not get compositor tree",
            "denoiser": denoiser_set,
        }

    # Find or create denoise node
    denoise_node = None
    for node in tree.nodes:
        if node.type == "DENOISE":
            denoise_node = node
            break

    if not denoise_node:
        denoise_node = tree.nodes.new(type="CompositorNodeDenoise")

    result = {
        "success": True,
        "denoiser": denoiser_set,
        "input_passes": scene.cycles.denoising_input_passes,
        "compositor_node": denoise_node.name,
    }

    if fallback_used:
        result["note"] = (
            f"Fallback used: requested '{denoiser}' but '{denoiser_set}' was set instead"
        )

    return result


def _denoise_toggle(scene, enable):  # type: ignore[no-untyped-def]
    """Enable/disable denoising."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="DENOISE_ENABLE" if enable else "DENOISE_DISABLE",
            error_code="EXECUTION_ERROR",
            message="Denoising only works with Cycles",
        )

    scene.cycles.use_denoising = enable

    return {
        "success": True,
        "denoising": enable,
        "denoiser": scene.cycles.denoiser if enable else None,
    }


# =============================================================================
# ADAPTIVE SAMPLING
# =============================================================================


def _adaptive_sampling(scene, enable):  # type: ignore[no-untyped-def]
    """Toggle adaptive sampling."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="ADAPTIVE_SAMPLING_ENABLE" if enable else "ADAPTIVE_SAMPLING_DISABLE",
            error_code="EXECUTION_ERROR",
            message="Adaptive sampling only works with Cycles",
        )

    scene.cycles.use_adaptive_sampling = enable

    if enable:
        scene.cycles.adaptive_threshold = 0.01
        scene.cycles.adaptive_min_samples = 0

    return {
        "success": True,
        "adaptive_sampling": enable,
        "threshold": scene.cycles.adaptive_threshold if enable else None,
    }


# =============================================================================
# ADAPTIVE SUBDIVISION
# =============================================================================


def _adaptive_subdivision_setup(params):  # type: ignore[no-untyped-def]
    """Setup adaptive subdivision surfaces."""
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name)

    if not obj or obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="ADAPTIVE_SUBDIVISION_SETUP",
            error_code="WRONG_OBJECT_TYPE",
            message="Must specify a mesh object",
        )

    bpy.context.view_layer.objects.active = obj

    # Add subdivision modifier with adaptive
    subd = obj.modifiers.new(name="Adaptive_Subdivision", type="SUBSURF")
    subd.subdivision_type = "CATMULL_CLARK"
    subd.levels = params.get("preview_levels", 1)
    subd.render_levels = params.get("render_levels", 2)

    # Enable adaptive subdivision in Cycles
    scene = bpy.context.scene
    if scene.render.engine == RenderEngine.CYCLES.value:
        scene.cycles.use_adaptive_subdivision = True  # type: ignore[unreachable]
        scene.cycles.dicing_rate = params.get("dicing_rate", 1.0)

    return {
        "success": True,
        "object": obj.name,
        "adaptive_subdivision": True,
        "render_levels": subd.render_levels,
        "dicing_rate": scene.cycles.dicing_rate if scene.render.engine == "CYCLES" else None,
    }


# =============================================================================
# LIGHT TREE
# =============================================================================


def _light_tree_build(scene):  # type: ignore[no-untyped-def]
    """Build light tree for faster rendering with many lights."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="LIGHT_TREE_BUILD",
            error_code="EXECUTION_ERROR",
            message="Light tree only works with Cycles",
        )

    # Count lights
    light_count = sum(1 for obj in scene.objects if obj.type == "LIGHT")

    # Light tree is most beneficial with many lights
    use_light_tree = light_count > 5

    scene.cycles.use_light_tree = use_light_tree

    if use_light_tree:
        # Auto threshold based on light count
        scene.cycles.light_sampling_threshold = max(0.01, 0.1 / light_count)

    return {
        "success": True,
        "light_tree_enabled": use_light_tree,
        "light_count": light_count,
        "sampling_threshold": scene.cycles.light_sampling_threshold if use_light_tree else None,
    }


def _light_tree_toggle(scene, enable):  # type: ignore[no-untyped-def]
    """Enable/disable light tree."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="LIGHT_TREE_ENABLE",
            error_code="EXECUTION_ERROR",
            message="Light tree only works with Cycles",
        )

    scene.cycles.use_light_tree = enable

    return {"success": True, "light_tree": enable}


# =============================================================================
# IRRADIANCE BAKING
# =============================================================================


def _bake_irradiance(scene, params):  # type: ignore[no-untyped-def]
    """Pre-bake indirect lighting (simplified)."""
    # Note: Full irradiance baking would require complex setup
    # This is a simplified version that enables persistent data

    scene.render.use_persistent_data = True

    return {
        "success": True,
        "persistent_data": True,
        "note": "Persistent data enabled - speeds up animation rendering",
        "full_irradiance_bake": "Use Blender's built-in Light Bake tools for static lighting",
    }


# =============================================================================
# RENDER REGIONS
# =============================================================================


def _render_region_auto(scene, params):  # type: ignore[no-untyped-def]
    """Auto-detect render region based on scene content."""
    # Find bounds of all mesh objects
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    for obj in scene.objects:
        if obj.type == "MESH":
            # Project bounding box to camera
            for corner in obj.bound_box:
                world_pos = obj.matrix_world @ mathutils.Vector(corner)

                # Simple projection (assuming camera at origin looking -Z)
                # In reality, this needs proper camera projection
                screen_x = (world_pos.x + 10) / 20  # Normalize to 0-1
                screen_y = (world_pos.y + 10) / 20

                min_x = min(min_x, screen_x)
                min_y = min(min_y, screen_y)
                max_x = max(max_x, screen_x)
                max_y = max(max_y, screen_y)

    # Clamp to valid range
    min_x = max(0, min(min_x, 1))
    min_y = max(0, min(min_y, 1))
    max_x = max(0, min(max_x, 1))
    max_y = max(0, min(max_y, 1))

    # Enable render region
    scene.render.use_border = True
    scene.render.border_min_x = min_x
    scene.render.border_min_y = min_y
    scene.render.border_max_x = max_x
    scene.render.border_max_y = max_y

    return {
        "success": True,
        "render_region": [min_x, min_y, max_x, max_y],
        "note": "Auto-detected based on object bounds - may need adjustment",
    }


def _render_region_set(scene, params):  # type: ignore[no-untyped-def]
    """Manually set render region."""
    region = params.get("region", [0, 0, 1, 1])  # min_x, min_y, max_x, max_y

    scene.render.use_border = True
    scene.render.border_min_x = region[0]
    scene.render.border_min_y = region[1]
    scene.render.border_max_x = region[2]
    scene.render.border_max_y = region[3]

    return {"success": True, "render_region": region}


# =============================================================================
# GPU OPTIMIZATION
# =============================================================================


def _gpu_memory_optimize(scene, params):  # type: ignore[no-untyped-def]
    """Optimize settings for GPU memory limits."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="GPU_MEMORY_OPTIMIZE",
            error_code="EXECUTION_ERROR",
            message="GPU optimization only works with Cycles",
        )

    raw_vram = params.get("gpu_memory_gb", 8)
    try:
        if isinstance(raw_vram, str):
            import re

            match = re.search(r"[\d\.]+", raw_vram)
            gpu_memory_gb = float(match.group(0)) if match else 8.0
        else:
            gpu_memory_gb = float(raw_vram)
    except (TypeError, ValueError):
        gpu_memory_gb = 8.0

    # Adjust tile size based on VRAM
    if gpu_memory_gb < 4:
        tile_size = 128
        max_bounces = 4
    elif gpu_memory_gb < 8:
        tile_size = 256
        max_bounces = 6
    elif gpu_memory_gb < 12:
        tile_size = 512
        max_bounces = 8
    else:
        tile_size = 2048
        max_bounces = 12

    scene.cycles.tile_size = tile_size
    scene.cycles.max_bounces = max_bounces

    # Optimize textures
    for img in bpy.data.images:
        if img.size[0] > 2048 or img.size[1] > 2048:
            # Flag for potential resize
            pass  # Actual resize would require PIL

    return {
        "success": True,
        "gpu_memory_gb": gpu_memory_gb,
        "tile_size": tile_size,
        "max_bounces": max_bounces,
        "recommendations": [
            "Consider resizing textures >2K if still running out of memory",
            "Use persistent data for animations",
            "Reduce subdivision levels if needed",
        ],
    }


def _tile_size_optimize(scene, params):  # type: ignore[no-untyped-def]
    """Optimize tile size for hardware."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="TILE_SIZE_OPTIMIZE",
            error_code="EXECUTION_ERROR",
            message="Tile optimization only works with Cycles",
        )

    render_device = params.get("device", "GPU")  # GPU or CPU

    if render_device == "GPU":
        # Larger tiles for GPU
        scene.cycles.tile_size = 2048
    else:
        # Smaller tiles for CPU (better cache usage)
        scene.cycles.tile_size = 32

    # Enable progressive refine for better feedback
    scene.cycles.use_progressive_refine = True

    return {
        "success": True,
        "device": render_device,
        "tile_size": scene.cycles.tile_size,
        "progressive_refine": True,
    }


# =============================================================================
# PRESET OPTIMIZATIONS
# =============================================================================


def _optimize_for_animation(scene, params):  # type: ignore[no-untyped-def]
    """Optimize settings for animation rendering."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="OPTIMIZE_FOR_ANIMATION",
            error_code="EXECUTION_ERROR",
            message="Optimization only works with Cycles",
        )

    quality = params.get("quality", "MEDIUM")  # LOW, MEDIUM, HIGH

    settings = {
        "LOW": {"samples": 64, "bounces": 4, "denoise": True},
        "MEDIUM": {"samples": 128, "bounces": 6, "denoise": True},
        "HIGH": {"samples": 256, "bounces": 8, "denoise": False},
    }

    cfg = settings.get(quality, settings["MEDIUM"])

    scene.cycles.samples = cfg["samples"]
    scene.cycles.max_bounces = cfg["bounces"]
    scene.cycles.use_denoising = cfg["denoise"]
    scene.render.use_persistent_data = True

    # Enable motion blur if requested
    if params.get("motion_blur", False):
        scene.render.use_motion_blur = True
        scene.cycles.motion_blur_position = "CENTER"

    return {
        "success": True,
        "optimization": "ANIMATION",
        "quality": quality,
        "samples": cfg["samples"],
        "persistent_data": True,
    }


def _optimize_for_still(scene, params):  # type: ignore[no-untyped-def]
    """Optimize settings for still image rendering."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="OPTIMIZE_FOR_STILL",
            error_code="EXECUTION_ERROR",
            message="Optimization only works with Cycles",
        )

    quality = params.get("quality", "PRODUCTION")

    settings = {
        "DRAFT": {"samples": 128, "bounces": 4, "denoise": True, "adaptive": True},
        "PREVIEW": {"samples": 256, "bounces": 6, "denoise": True, "adaptive": True},
        "PRODUCTION": {"samples": 512, "bounces": 8, "denoise": True, "adaptive": True},
        "FINAL": {"samples": 2048, "bounces": 12, "denoise": False, "adaptive": False},
    }

    cfg = settings.get(quality, settings["PRODUCTION"])

    scene.cycles.samples = cfg["samples"]
    scene.cycles.max_bounces = cfg["bounces"]
    scene.cycles.use_denoising = cfg["denoise"]
    scene.cycles.use_adaptive_sampling = cfg["adaptive"]

    # Disable persistent data for still (not needed)
    scene.render.use_persistent_data = False

    # Larger tiles for faster still rendering
    scene.cycles.tile_size = 512

    return {
        "success": True,
        "optimization": "STILL",
        "quality": quality,
        "samples": cfg["samples"],
        "adaptive_sampling": cfg["adaptive"],
    }


def _persistent_data_enable(scene):  # type: ignore[no-untyped-def]
    """Enable persistent data for faster animation rendering."""
    scene.render.use_persistent_data = True
    return {
        "success": True,
        "persistent_data": True,
        "benefit": "Speeds up animation rendering by keeping data between frames",
    }


# =============================================================================
# RESOLUTION
# =============================================================================


def _resolution_scale(scene, params):  # type: ignore[no-untyped-def]
    """Scale render resolution."""
    scale = params.get("scale", 1.0)  # 0.5 = half res, 2.0 = double res

    base_x = scene.render.resolution_x
    base_y = scene.render.resolution_y

    scene.render.resolution_percentage = int(scale * 100)

    new_x = int(base_x * scale)
    new_y = int(base_y * scale)

    return {
        "success": True,
        "scale_percentage": scene.render.resolution_percentage,
        "base_resolution": [base_x, base_y],
        "effective_resolution": [new_x, new_y],
    }


# =============================================================================
# REPORTING
# =============================================================================


def _sample_optimization_report(scene):  # type: ignore[no-untyped-def]
    """Generate sample optimization report."""
    if scene.render.engine != RenderEngine.CYCLES.value:
        return ResponseBuilder.error(
            handler="manage_render_optimization",
            action="SAMPLE_OPTIMIZATION_REPORT",
            error_code="EXECUTION_ERROR",
            message="Report only works with Cycles",
        )

    # Analyze current settings
    complexity = _analyze_scene_complexity(scene)
    current_samples = scene.cycles.samples
    adaptive = scene.cycles.use_adaptive_sampling
    denoising = scene.cycles.use_denoising

    # Recommendations
    recommendations = []

    if complexity < 0.3 and current_samples > 128:
        recommendations.append("Scene is simple - consider reducing samples to 64-128")

    if complexity > 0.7 and current_samples < 512:
        recommendations.append("Scene is complex - consider increasing samples to 512+")

    if not adaptive and complexity > 0.5:
        recommendations.append("Enable adaptive sampling for complex scenes")

    if not denoising and current_samples < 1024:
        recommendations.append("Enable denoising to reduce sample count needed")

    if scene.cycles.max_bounces > 8 and complexity < 0.5:
        recommendations.append("Reduce max bounces to 4-6 for simple scenes")

    # Estimate render time multiplier
    time_estimate = (current_samples / 128) * (1 + complexity)

    return {
        "success": True,
        "current_samples": current_samples,
        "complexity_score": round(complexity, 2),
        "adaptive_sampling": adaptive,
        "denoising": denoising,
        "estimated_time_multiplier": round(time_estimate, 2),
        "recommendations": recommendations,
        "optimal_samples_estimate": _round_samples(int(128 * (0.5 + complexity * 1.5))),
    }
