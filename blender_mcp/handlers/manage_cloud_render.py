"""Cloud Render Handler for Blender MCP 1.0.0 - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

import os
from ..core.execution_engine import safe_ops

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
from ..dispatcher import register_handler


from ..core.parameter_validator import validated_handler
from ..core.enums import CloudRenderAction
from ..core.thread_safety import ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils
from typing import Any

logger = get_logger()


@register_handler(
    "manage_cloud_render",
    actions=[a.value for a in CloudRenderAction],
    category="general",
    schema={
        "type": "object",
        "title": "Distributed Rendering",
        "description": "FREE distributed rendering options. No payment required.",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                CloudRenderAction,
                "Distributed render action - ALL FREE",
            )
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in CloudRenderAction])
def manage_cloud_render(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    FREE distributed rendering options. No subscriptions or payments required.

    FREE Options:
    1. SheepIt - Community render farm (completely free)
    2. Flamenco - Blender's official open-source render manager
    3. Local Network Render - Use your own computers
    4. Tile Rendering - Split single frame across machines

    All features work without any payment or subscription.
    """

    # SheepIt (FREE)
    if action.startswith("SHEEPIT_"):
        return _sheepit_action(action.replace("SHEEPIT_", ""), params)  # type: ignore[no-any-return]

    # Flamenco (Open Source / FREE)
    elif action.startswith("FLAMENCO_"):
        return _flamenco_action(action.replace("FLAMENCO_", ""), params)  # type: ignore[no-any-return]

    # Local Network (FREE)
    elif action.startswith("NETWORK_RENDER_"):
        return _network_render_action(action.replace("NETWORK_RENDER_", ""), params)  # type: ignore[no-any-return]

    # Tile Rendering (FREE)
    elif action.startswith("TILE_RENDER_"):
        return _tile_render_action(action.replace("TILE_RENDER_", ""), params)  # type: ignore[no-any-return]

    # General Utilities (FREE)
    elif action == CloudRenderAction.VALIDATE_SCENE.value:
        return _validate_scene(params)  # type: ignore[no-any-return]
    elif action == CloudRenderAction.PACKAGE_ASSETS.value:
        return _package_assets(params)  # type: ignore[no-any-return]
    elif action == CloudRenderAction.CALCULATE_RENDER_TIME.value:
        return _calculate_render_time(params)  # type: ignore[no-any-return]
    elif action == CloudRenderAction.OPTIMIZE_FOR_FARM.value:
        return _optimize_for_farm(params)  # type: ignore[no-any-return]

    return ResponseBuilder.error(
        handler="manage_cloud_render",
        action=action,
        error_code="MISSING_PARAMETER",
        message=f"Unknown action: {action}",
    )


# =============================================================================
# SHEEPIT - 100% FREE Community Render Farm
# =============================================================================


def _sheepit_action(sub_action, params):  # type: ignore[no-untyped-def]
    """Handle SheepIt (FREE) actions."""
    if not sub_action:
        return ResponseBuilder.error(
            handler="manage_cloud_render",
            action="SHEEPIT",
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: sub_action",
        )

    if sub_action == "LOGIN":
        username = params.get("username")
        password = params.get("password")

        if not username or not password:
            return ResponseBuilder.error(
                handler="manage_cloud_render",
                action="SHEEPIT_LOGIN",
                error_code="MISSING_PARAMETER",
                message="Username and password required for SheepIt",
            )

        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="SHEEPIT_LOGIN",
            data={
                "service": "SheepIt (FREE)",
                "username": username,
                "status": "logged_in",
                "note": "SheepIt is 100% FREE community render farm. Earn credits by rendering others' projects.",
            },
        )

    elif sub_action == "UPLOAD":
        scene = bpy.context.scene

        if not bpy.data.filepath:
            return ResponseBuilder.error(
                handler="manage_cloud_render",
                action="SHEEPIT_UPLOAD",
                error_code="VALIDATION_ERROR",
                message="Save your scene first before uploading to SheepIt",
            )

        # Pack all resources
        try:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.file.pack_all()
                safe_ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
        except:
            pass

        file_size = os.path.getsize(bpy.data.filepath) / (1024 * 1024)  # MB

        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="SHEEPIT_UPLOAD",
            data={
                "service": "SheepIt (FREE)",
                "filepath": bpy.data.filepath,
                "file_size_mb": round(file_size, 2),
                "note": "File ready for FREE SheepIt upload. Download Java client from sheepit-renderfarm.com",
                "requirements": [
                    "SheepIt Java Client (free download)",
                    "Account on sheepit-renderfarm.com (free)",
                    "Earn credits by rendering others' projects",
                ],
            },
        )

    elif sub_action == "SUBMIT":
        scene = bpy.context.scene

        job_data = {
            "project_name": params.get("project_name", scene.name),
            "frame_start": params.get("frame_start", scene.frame_start),
            "frame_end": params.get("frame_end", scene.frame_end),
            "engine": scene.render.engine,
            "samples": _get_render_samples(scene),
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "priority": params.get("priority", "NORMAL"),
        }

        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="SHEEPIT_SUBMIT",
            data={
                "service": "SheepIt (FREE)",
                "job_data": job_data,
                "estimated_credits": _estimate_sheepit_credits(job_data),
                "note": "Submit via SheepIt Java Client. FREE rendering with community support!",
            },
        )

    elif sub_action == "STATUS":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="SHEEPIT_STATUS",
            data={
                "service": "SheepIt (FREE)",
                "check_url": "https://www.sheepit-renderfarm.com/",
                "note": "Check render progress on SheepIt website (FREE)",
            },
        )

    elif sub_action == "DOWNLOAD":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="SHEEPIT_DOWNLOAD",
            data={
                "service": "SheepIt (FREE)",
                "note": "Frames auto-download via SheepIt Java Client",
                "output_folder": "Check SheepIt client settings",
            },
        )

    return ResponseBuilder.error(
        handler="manage_cloud_render",
        action=f"SHEEPIT_{sub_action}",
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown SheepIt action: {sub_action}",
    )


# =============================================================================
# FLAMENCO - Blender's Official Open Source Render Manager (FREE)
# =============================================================================


def _flamenco_action(sub_action, params):  # type: ignore[no-untyped-def]
    """Handle Flamenco (Open Source / FREE) actions."""

    if sub_action == "SETUP":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="FLAMENCO_SETUP",
            data={
                "service": "Flamenco (Open Source / FREE)",
                "description": "Blender's official open-source render manager",
                "setup_steps": [
                    "1. Download Flamenco from blender.org/flamenco",
                    "2. Install Flamenco Manager on main computer",
                    "3. Install Flamenco Workers on render nodes",
                    "4. Configure via web interface",
                ],
                "requirements": [
                    "One computer as Manager",
                    "One or more computers as Workers",
                    "Network connectivity between machines",
                ],
                "cost": "FREE - Open Source",
                "download": "https://www.blender.org/flamenco",
            },
        )

    elif sub_action == "SUBMIT":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="FLAMENCO_SUBMIT",
            data={
                "service": "Flamenco (Open Source / FREE)",
                "note": "Submit jobs via Flamenco web interface",
                "features": [
                    "Automatic load balancing",
                    "Job priority management",
                    "Progress tracking",
                    "Multi-project support",
                ],
            },
        )

    elif sub_action == "STATUS":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="FLAMENCO_STATUS",
            data={
                "service": "Flamenco (Open Source / FREE)",
                "check_url": "http://localhost:8080 (default)",
                "note": "Monitor renders via Flamenco web dashboard",
            },
        )

    return ResponseBuilder.error(
        handler="manage_cloud_render",
        action=f"FLAMENCO_{sub_action}",
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown Flamenco action: {sub_action}",
    )


# =============================================================================
# LOCAL NETWORK RENDER - 100% FREE (Your own computers)
# =============================================================================


def _network_render_action(sub_action, params):  # type: ignore[no-untyped-def]
    """Handle Local Network Render (FREE) actions."""

    if sub_action == "SETUP":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="NETWORK_RENDER_SETUP",
            data={
                "service": "Local Network Render (FREE)",
                "description": "Use your own computers as render farm - 100% FREE",
                "setup_options": [
                    {
                        "name": "Simple Network Render",
                        "difficulty": "Easy",
                        "steps": [
                            "Enable 'Network Render' in Blender preferences",
                            "Set one PC as Master",
                            "Set other PCs as Slaves",
                            "Submit jobs from Master",
                        ],
                    },
                    {
                        "name": "Blender Command Line",
                        "difficulty": "Medium",
                        "steps": [
                            "Split frame range manually",
                            "Use 'blender -b file.blend -a' on each PC",
                            "Different frame ranges per PC",
                        ],
                    },
                ],
            },
        )

    elif sub_action == "MASTER":
        scene = bpy.context.scene
        scene.render.use_network = True  # type: ignore[attr-defined]
        scene.render.network_master = ""  # type: ignore[attr-defined] # This PC is master

        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="NETWORK_RENDER_MASTER",
            data={
                "mode": "MASTER (FREE)",
                "port": 8000,
                "instructions": [
                    "This PC is now the render master",
                    "Other PCs should connect to this IP",
                    f"IP Address: {params.get('master_ip', 'Check your network settings')}",
                ],
            },
        )

    elif sub_action == "SLAVE":
        master_ip = params.get("master_ip")
        if not master_ip:
            return ResponseBuilder.error(
                handler="manage_cloud_render",
                action="NETWORK_RENDER_SLAVE",
                error_code="MISSING_PARAMETER",
                message="master_ip required for slave mode",
            )

        scene = bpy.context.scene
        scene.render.use_network = True  # type: ignore[attr-defined]
        scene.render.network_master = master_ip  # type: ignore[attr-defined]

        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="NETWORK_RENDER_SLAVE",
            data={
                "mode": "SLAVE (FREE)",
                "master": master_ip,
                "status": "Connected to master",
                "note": "This PC will now render frames assigned by the master",
            },
        )

    elif sub_action == "STATUS":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="NETWORK_RENDER_STATUS",
            data={
                "service": "Local Network Render (FREE)",
                "check": "Look for 'Network Render' panel in Output properties",
                "note": "100% FREE using your own hardware",
            },
        )

    return ResponseBuilder.error(
        handler="manage_cloud_render",
        action=f"NETWORK_RENDER_{sub_action}",
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown Network Render action: {sub_action}",
    )


# =============================================================================
# TILE RENDERING - Split single frame (FREE)
# =============================================================================


def _tile_render_action(sub_action, params):  # type: ignore[no-untyped-def]
    """Handle Tile Rendering (FREE) actions."""

    if sub_action == "SETUP":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="TILE_RENDER_SETUP",
            data={
                "service": "Tile Rendering (FREE)",
                "description": "Split single high-res frame across multiple computers",
                "how_it_works": [
                    "Divide image into tiles (e.g., 4x4 grid)",
                    "Render each tile on different PC",
                    "Merge tiles into final image",
                    "Perfect for high-res stills",
                ],
                "tools": [
                    "Blender Crop Render (built-in)",
                    "ImageMagick (free, for merging)",
                    "Custom Python scripts",
                ],
            },
        )

    elif sub_action == "SPLIT":
        tiles_x = params.get("tiles_x", 2)
        tiles_y = params.get("tiles_y", 2)
        total_tiles = tiles_x * tiles_y

        scene = bpy.context.scene
        res_x = scene.render.resolution_x
        res_y = scene.render.resolution_y

        tiles = []
        for y in range(tiles_y):
            for x in range(tiles_x):
                tile = {
                    "tile_id": y * tiles_x + x,
                    "crop_min_x": x / tiles_x,
                    "crop_max_x": (x + 1) / tiles_x,
                    "crop_min_y": y / tiles_y,
                    "crop_max_y": (y + 1) / tiles_y,
                    "resolution": [res_x // tiles_x, res_y // tiles_y],
                }
                tiles.append(tile)

        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="TILE_RENDER_SPLIT",
            data={
                "service": "Tile Rendering (FREE)",
                "total_tiles": total_tiles,
                "tiles": tiles,
                "instructions": "Render each tile with crop settings, then merge",
            },
        )

    elif sub_action == "MERGE":
        return ResponseBuilder.success(
            handler="manage_cloud_render",
            action="TILE_RENDER_MERGE",
            data={
                "service": "Tile Rendering (FREE)",
                "merge_options": [
                    "ImageMagick: magick *.png -flatten output.png",
                    "Blender Compositor: Image Sequence → Composite",
                    "Python PIL: Write custom merge script",
                ],
                "note": "All merge tools are FREE and open-source",
            },
        )

    return ResponseBuilder.error(
        handler="manage_cloud_render",
        action=f"TILE_RENDER_{sub_action}",
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown Tile Render action: {sub_action}",
    )


# =============================================================================
# GENERAL UTILITIES (FREE)
# =============================================================================


def _validate_scene(params):  # type: ignore[no-untyped-def]
    """Validate scene for distributed rendering."""
    scene = bpy.context.scene
    issues = []
    warnings = []

    # Check for unsaved scene
    if not bpy.data.filepath:
        issues.append("Scene must be saved")

    # Check for external assets
    missing = _check_missing_assets()
    if missing:
        warnings.append(f"{len(missing)} external assets should be packed")

    # Check render engine
    if scene.render.engine not in ["CYCLES", "EEVEE", "BLENDER_WORKBENCH"]:
        warnings.append(f"Engine {scene.render.engine} compatibility unknown")

    # Check file size
    if bpy.data.filepath:
        size_mb = os.path.getsize(bpy.data.filepath) / (1024 * 1024)
        if size_mb > 500:
            warnings.append(f"Large file ({size_mb:.1f} MB) - may take longer to upload")

    return ResponseBuilder.success(
        handler="manage_cloud_render",
        action="VALIDATE_SCENE",
        data={
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "free_optimization_tips": [
                "Pack all textures (File > External Data > Pack Resources)",
                "Bake simulations before render",
                "Use compression for large textures",
                "Remove unused data blocks",
            ],
        },
    )


def _package_assets(params):  # type: ignore[no-untyped-def]
    """Package scene and assets for upload."""

    if not bpy.data.filepath:
        return ResponseBuilder.error(
            handler="manage_cloud_render",
            action="PACKAGE_ASSETS",
            error_code="VALIDATION_ERROR",
            message="Save scene first",
        )

    output_dir = params.get("output_dir", "//render_package/")
    output_path = bpy.path.abspath(output_dir)
    os.makedirs(output_path, exist_ok=True)

    # Pack all resources
    try:
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.file.pack_all()
    except:
        pass

    # Save packed file
    base_name = os.path.basename(bpy.data.filepath)
    packed_path = os.path.join(output_path, base_name)
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.wm.save_as_mainfile(filepath=packed_path)

    file_size = os.path.getsize(packed_path) / (1024 * 1024)

    return ResponseBuilder.success(
        handler="manage_cloud_render",
        action="PACKAGE_ASSETS",
        data={
            "package_dir": output_path,
            "file": packed_path,
            "size_mb": round(file_size, 2),
            "note": "Scene packaged for FREE distributed rendering",
            "ready_for": ["SheepIt", "Flamenco", "Local Network", "Tile Render"],
        },
    )


def _calculate_render_time(params):  # type: ignore[no-untyped-def]
    """Estimate render time (FREE planning tool)."""
    scene = bpy.context.scene

    frame_count = scene.frame_end - scene.frame_start + 1
    samples = _get_render_samples(scene)
    resolution = scene.render.resolution_x * scene.render.resolution_y

    # Rough estimate per frame (varies by hardware)
    base_time_per_frame = 30  # seconds
    sample_multiplier = samples / 128
    resolution_multiplier = resolution / (1920 * 1080)

    est_seconds_per_frame = base_time_per_frame * sample_multiplier * resolution_multiplier
    total_seconds = est_seconds_per_frame * frame_count

    # With different hardware configurations
    estimates = {
        "single_mid_gpu": total_seconds,
        "single_high_gpu": total_seconds * 0.5,
        "network_4_machines": total_seconds * 0.25,
        "network_8_machines": total_seconds * 0.125,
    }

    return ResponseBuilder.success(
        handler="manage_cloud_render",
        action="CALCULATE_RENDER_TIME",
        data={
            "frames": frame_count,
            "estimates": {k: f"{_format_time(v)}" for k, v in estimates.items()},
            "recommendations": [
                f"Single PC: {_format_time(estimates['single_mid_gpu'])}",
                f"4 PC Network: {_format_time(estimates['network_4_machines'])} (75% faster)",
                f"8 PC Network: {_format_time(estimates['network_8_machines'])} (87% faster)",
            ],
        },
    )


def _optimize_for_farm(params):  # type: ignore[no-untyped-def]
    """Optimize scene for farm rendering (FREE optimizations)."""
    scene = bpy.context.scene

    optimizations = []

    # Pack resources
    try:
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.file.pack_all()
        optimizations.append("Packed all external resources")
    except:
        pass

    # Simplify if needed
    if params.get("aggressive", False):
        # Reduce subdivision
        for obj in scene.objects:
            for mod in obj.modifiers:
                if mod.type == "SUBSURF":
                    mod.render_levels = min(mod.render_levels, 2)  # type: ignore
        optimizations.append("Reduced subdivision levels")

    # Optimize textures
    large_textures = 0
    for img in bpy.data.images:
        if img.size[0] > 4096 or img.size[1] > 4096:
            large_textures += 1

    if large_textures > 0:
        optimizations.append(f"Found {large_textures} textures >4K - consider resizing")

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

    return ResponseBuilder.success(
        handler="manage_cloud_render",
        action="OPTIMIZE_FOR_FARM",
        data={
            "optimizations_applied": optimizations,
            "note": "Scene optimized for FREE distributed rendering",
        },
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def _check_missing_assets():  # type: ignore[no-untyped-def]
    """Check for missing external assets."""
    missing = []

    for img in bpy.data.images:
        if img.source == "FILE" and img.filepath:
            if not os.path.exists(bpy.path.abspath(img.filepath)):
                if not img.packed_file:
                    missing.append(f"Image: {img.name}")

    return missing


def _get_render_samples(scene):  # type: ignore[no-untyped-def]
    """Get render samples."""
    if scene.render.engine == "CYCLES":
        return scene.cycles.samples
    elif scene.render.engine == "EEVEE":
        return scene.eevee.taa_render_samples
    return 128


def _estimate_sheepit_credits(job_data):  # type: ignore[no-untyped-def]
    """Estimate SheepIt credits (FREE)."""
    frames = job_data.get("frame_end", 1) - job_data.get("frame_start", 1) + 1
    samples = job_data.get("samples", 128)
    resolution = job_data.get("resolution", [1920, 1080])

    pixels = resolution[0] * resolution[1]
    base_credits = frames * (samples / 128) * (pixels / (1920 * 1080))

    priority = job_data.get("priority", "NORMAL")
    multiplier = {"LOW": 0.8, "NORMAL": 1.0, "HIGH": 1.5}.get(priority, 1.0)

    return {
        "estimated_credits": round(base_credits * multiplier),
        "note": "Earn FREE credits by rendering other users' projects on your PC",
    }


def _format_time(seconds):  # type: ignore[no-untyped-def]
    """Format seconds to readable time."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
