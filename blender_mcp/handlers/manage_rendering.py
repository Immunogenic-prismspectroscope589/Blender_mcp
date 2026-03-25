"""
Manage Rendering - V1.0.0 Fixed

Fixes from test report:
- Extended timeout support (300s for frame, 3600s for animation)
- Better timeout error handling with progress info
- Enhanced parameter coercion for resolution/samples
- Async render operation support

High Mode Philosophy: Maximum power, maximum safety.
"""

import time
import uuid
from typing import Dict, Any, Optional, cast, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from bpy.types import Scene, Object

from ..core.render_eevee_next import EeveeNextManager, RaytracingQualityPreset

try:
    import bpy
    import mathutils

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.versioning import BlenderCompatibility
from ..core.thread_safety import execute_on_main_thread, ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.universal_coercion import TypeCoercer, ParameterNormalizer
from ..dispatcher import register_handler
from ..core.enums import RenderAction, RenderEngine, RenderQualityPreset
from ..core.validation_utils import ValidationUtils
from ..core.job_manager import AsyncJobManager
import os


logger = get_logger()

# Blender uses "JPEG", not "JPG". Normalize user-facing aliases to Blender identifiers.
_FORMAT_MAP: dict = {"PNG": "PNG", "JPG": "JPEG", "JPEG": "JPEG", "WEBP": "WEBP"}
# MIME types for __mcp_image_data__ inline image delivery.
_FORMAT_MIME: dict = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}

# Hard limit for inline __mcp_image_data__ in get_viewport_screenshot (1 MB).
_INLINE_IMAGE_MAX_BYTES = 1 * 1024 * 1024


class RenderTimeout(Enum):
    """Timeout configurations for different render types."""

    FRAME_DEFAULT = 300.0  # 5 minutes
    FRAME_EXTENDED = 600.0  # 10 minutes for high quality
    ANIMATION_DEFAULT = 3600.0  # 1 hour
    ANIMATION_EXTENDED = 7200.0  # 2 hours
    VIEWPORT_CAPTURE = 30.0  # 30 seconds


@register_handler(
    "manage_rendering",
    schema={
        "type": "object",
        "title": "Render Manager",
        "description": (
            "CORE — Configure render settings and execute renders.\n"
            "ACTIONS: SET_ENGINE, SET_RESOLUTION, SET_SAMPLES, SET_QUALITY_PRESET, "
            "RENDER_FRAME (aka RENDER_STILL), RENDER_ANIMATION\n\n"
            "RENDER_FRAME and RENDER_ANIMATION run as non-blocking background subprocesses — "
            "they return a job_id immediately. Use manage_jobs(LIST_JOBS) to monitor progress "
            "and manage_jobs(CANCEL_JOB, job_id=...) to stop a running render.\n"
            "Always provide 'filepath' to control where frames are saved; "
            "if omitted, output is redirected to the system temp directory automatically.\n\n"
            "NOTE: Do NOT use bpy.ops.render.render() in execute_blender_code — it freezes Blender "
            "and the MCP server stops responding. Use RENDER_FRAME here instead."
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(RenderAction, "Operation to perform"),
            "engine": ValidationUtils.generate_enum_schema(RenderEngine, "Render Engine"),
            "device": {
                "type": "string",
                "enum": ["CPU", "GPU"],
                "description": "Compute Device (Cycles only)",
            },
            "raytracing": {
                "type": "boolean",
                "default": False,
                "description": "Enable Raytracing (Eevee Next only)",
            },
            "resolution_x": {"type": "integer", "description": "Width pixels"},
            "resolution_y": {"type": "integer", "description": "Height pixels"},
            "samples": {"type": "integer", "description": "Render samples"},
            "filepath": {
                "type": "string",
                "description": (
                    "Output file/directory path. REQUIRED for RENDER_ANIMATION and RENDER_FRAME "
                    "to control where frames land. Example: 'C:/renders/my_anim/frame_'. "
                    "If omitted, output is auto-redirected to the system temp directory — "
                    "frames will NOT appear on Desktop or other unexpected locations."
                ),
            },
            "auto_camera": {
                "type": "boolean",
                "default": False,
                "description": "Auto-create camera if none exists",
            },
            "quality_preset": ValidationUtils.generate_enum_schema(
                RenderQualityPreset, "Preset for resolution and samples"
            ),
            "extended_timeout": {
                "type": "boolean",
                "default": False,
                "description": "Use extended timeout for long renders",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Custom timeout in seconds (overrides defaults)",
            },
            "async_execution": {
                "type": "boolean",
                "default": False,
                "description": "Run render in background process (non-blocking)",
            },
        },
        "required": ["action"],
    },
    actions=[a.value for a in RenderAction],
    category="rendering",
)
@ensure_main_thread
def manage_rendering(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Super-Tool for Rendering control with extended timeout support.

    Actions:
        - SET_ENGINE: Set render engine (CYCLES, BLENDER_EEVEE_NEXT, etc.)
        - SET_RESOLUTION: Set render resolution
        - SET_SAMPLES: Set render samples
        - RENDER_FRAME: Render single frame with timeout handling
        - RENDER_ANIMATION: Render animation with timeout handling
        - SET_QUALITY_PRESET: Apply quality preset

    Timeout Control:
        - Use extended_timeout=True for 10min/2hour timeouts
        - Or specify timeout_seconds for custom timeout
    """
    validation_error = ValidationUtils.validate_enum(action, RenderAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_rendering", action=action
        )

    # Normalize parameters
    try:
        # Avoid schema validation error if normalize passes schemas that don't matched relaxed typing
        # But we still want type coercion
        params = ParameterNormalizer.normalize(params, manage_rendering._handler_schema)
    except Exception as e:
        logger.warning(f"Parameter normalization warning: {e}")

    # Route to handler
    try:
        if action == RenderAction.SET_ENGINE.value:
            return _handle_set_engine(**params)
        elif action == RenderAction.SET_RESOLUTION.value:
            return _handle_set_resolution(**params)
        elif action == RenderAction.SET_SAMPLES.value:
            return _handle_set_samples(**params)
        elif action in (RenderAction.RENDER_FRAME.value, RenderAction.RENDER_STILL.value):
            return _handle_render_frame(**params)
        elif action == RenderAction.RENDER_ANIMATION.value:
            return _handle_render_animation(**params)
        elif action == RenderAction.SET_QUALITY_PRESET.value:
            return _handle_set_quality_preset(**params)
        else:
            return ResponseBuilder.error(
                handler="manage_rendering",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_rendering.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_rendering", action=action, error_code="EXECUTION_ERROR", message=str(e)
        )


def _get_timeout(params: Dict[str, Any], default_timeout: float) -> float:
    """Get timeout value from params or use default."""
    if "timeout_seconds" in params:
        return float(params["timeout_seconds"])
    if params.get("extended_timeout", False):
        if default_timeout == RenderTimeout.FRAME_DEFAULT.value:
            return RenderTimeout.FRAME_EXTENDED.value
        return RenderTimeout.ANIMATION_EXTENDED.value
    return default_timeout


def _estimate_render_budget(scene: "Scene") -> Dict[str, Any]:
    """
    Estimate render complexity and determine if adaptive degradation is needed.
    Returns budget assessment with risk level and recommended adjustments.
    """
    engine = cast(str, scene.render.engine)
    res_x = scene.render.resolution_x
    res_y = scene.render.resolution_y
    res_pct = scene.render.resolution_percentage / 100.0
    effective_pixels = int(res_x * res_pct) * int(res_y * res_pct)

    samples = 128
    if engine == RenderEngine.CYCLES.value:
        samples = getattr(scene.cycles, "samples", 128)

    complexity_score = (effective_pixels / 1_000_000.0) * (samples / 128.0)

    if complexity_score > 50.0:
        risk = "HIGH"
    elif complexity_score > 15.0:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "risk": risk,
        "complexity_score": round(complexity_score, 2),
        "effective_resolution": f"{int(res_x * res_pct)}x{int(res_y * res_pct)}",
        "samples": samples,
        "engine": engine,
    }


def _apply_adaptive_degradation(scene: "Scene", budget: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply adaptive quality reduction when render budget risk is HIGH and
    no explicit extended_timeout was provided. Reduces samples and resolution
    percentage to fit within default timeout budget.
    Returns dict of adjustments applied (empty if none needed).
    """
    if budget["risk"] != "HIGH":
        return {}

    adjustments: Dict[str, Any] = {}
    engine = cast(str, scene.render.engine)

    if engine == RenderEngine.CYCLES.value:
        original_samples = scene.cycles.samples
        if original_samples > 256:
            clamped = min(original_samples, 256)
            scene.cycles.samples = clamped
            adjustments["samples_clamped"] = {"from": original_samples, "to": clamped}

    res_pct = scene.render.resolution_percentage
    if res_pct > 100:
        scene.render.resolution_percentage = 100
        adjustments["resolution_percentage_clamped"] = {"from": res_pct, "to": 100}

    return adjustments


# moved to top of file or handled (see next step)


def _handle_set_engine(**params: Any) -> Dict[str, Any]:
    """Handle SET_ENGINE action with Eevee Next Raytracing support."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_ENGINE.value,
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_ENGINE.value,
            error_code="NO_SCENE",
            message="No scene available",
        )

    try:
        eng = params.get("engine", RenderEngine.CYCLES.value)

        # EEVEE identifier changed between Blender versions:
        #   Blender 4.2–4.x: "BLENDER_EEVEE_NEXT"
        #   Blender 5.0+:    "BLENDER_EEVEE"
        # Whichever alias the caller uses, auto-detect the one that works at runtime.
        if eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            _eevee_candidates = (
                ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"]
                if eng == "BLENDER_EEVEE_NEXT"
                else ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"]
            )
            for _candidate in _eevee_candidates:
                try:
                    scene.render.engine = _candidate
                    eng = _candidate  # remember which one worked
                    break
                except (TypeError, AttributeError):
                    continue
        else:
            scene.render.engine = eng

        # Device Config (Cycles)
        if eng == RenderEngine.CYCLES.value:
            dev = params.get("device", "GPU")
            scene.cycles.device = dev

        # Eevee Raytracing Configuration (Blender 4.2+ / 5.0+)
        if eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE") and params.get("raytracing", False):
            try:
                EeveeNextManager.setup_raytracing(scene, quality=RaytracingQualityPreset.HIGH.value)
                logger.info(f"Activated Eevee Raytracing (High Quality) on engine '{eng}'")
            except Exception as e:
                logger.warning(f"Failed to setup Eevee raytracing: {e}")

        return ResponseBuilder.success(
            handler="manage_rendering",
            action=RenderAction.SET_ENGINE.value,
            data={
                "engine": eng,
                "version_info": f"Blender {BlenderCompatibility.VERSION_MAJOR}.{BlenderCompatibility.VERSION_MINOR}",
                "raytracing": (
                    params.get("raytracing", False) if eng == "BLENDER_EEVEE_NEXT" else None
                ),
            },
        )
    except Exception as e:
        logger.error(f"SET_ENGINE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_ENGINE.value,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_set_resolution(**params: Any) -> Dict[str, Any]:
    """Handle SET_RESOLUTION action."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_RESOLUTION.value,
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_RESOLUTION.value,
            error_code="NO_SCENE",
            message="No scene available",
        )

    try:
        x = params.get("resolution_x")
        y = params.get("resolution_y")

        # Coerce to int
        if x is not None:
            coerced_x = TypeCoercer.coerce(x, "int")
            if coerced_x.success:
                scene.render.resolution_x = coerced_x.value

        if y is not None:
            coerced_y = TypeCoercer.coerce(y, "int")
            if coerced_y.success:
                scene.render.resolution_y = coerced_y.value

        return ResponseBuilder.success(
            handler="manage_rendering",
            action=RenderAction.SET_RESOLUTION.value,
            data={"resolution": [scene.render.resolution_x, scene.render.resolution_y]},
        )
    except Exception as e:
        logger.error(f"SET_RESOLUTION failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_RESOLUTION.value,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_set_samples(**params: Any) -> Dict[str, Any]:
    """Handle SET_SAMPLES action."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_SAMPLES.value,
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_SAMPLES.value,
            error_code="NO_SCENE",
            message="No scene available",
        )

    try:
        s = params.get("samples", 128)

        # Coerce to int
        coerced = TypeCoercer.coerce(s, "int")
        if not coerced.success:
            return ResponseBuilder.error(
                handler="manage_rendering",
                action=RenderAction.SET_SAMPLES.value,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Invalid samples value: {s}",
            )

        samples = coerced.value

        # Set Cycles samples
        try:
            if hasattr(scene, "cycles"):
                scene.cycles.samples = samples
        except Exception as e:
            logger.warning(f"Could not set Cycles samples: {e}")

        # Set Eevee samples (version dependent)
        try:
            if hasattr(scene, "eevee"):
                if hasattr(scene.eevee, "taa_render_samples"):
                    scene.eevee.taa_render_samples = samples
                elif hasattr(scene.eevee, "render_samples"):
                    scene.eevee.render_samples = samples
        except Exception as e:
            logger.warning(f"Could not set Eevee samples: {e}")

        return ResponseBuilder.success(
            handler="manage_rendering",
            action=RenderAction.SET_SAMPLES.value,
            data={"samples": samples, "engine": scene.render.engine},
        )
    except Exception as e:
        logger.error(f"SET_SAMPLES failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_SAMPLES.value,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_set_quality_preset(**params: Any) -> Dict[str, Any]:
    """Handle SET_QUALITY_PRESET action."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_QUALITY_PRESET.value,
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_QUALITY_PRESET.value,
            error_code="NO_SCENE",
            message="No scene available",
        )

    try:
        preset = params.get("quality_preset", RenderQualityPreset.DRAFT.value)

        validation_error = ValidationUtils.validate_enum(
            preset, RenderQualityPreset, "quality_preset"
        )
        if validation_error:
            return ResponseBuilder.from_error(
                validation_error,
                handler="manage_rendering",
                action=RenderAction.SET_QUALITY_PRESET.value,
            )

        presets = {
            RenderQualityPreset.DRAFT.value: {"res_x": 960, "res_y": 540, "samples": 32},
            RenderQualityPreset.HD_READY.value: {"res_x": 1280, "res_y": 720, "samples": 64},
            RenderQualityPreset.FULL_HD.value: {"res_x": 1920, "res_y": 1080, "samples": 128},
            RenderQualityPreset.ULTRA_4K.value: {"res_x": 3840, "res_y": 2160, "samples": 512},
            RenderQualityPreset.PRODUCTION.value: {"res_x": 1920, "res_y": 1080, "samples": 1024},
        }

        if preset in presets:
            p = presets[preset]
            scene.render.resolution_x = p["res_x"]
            scene.render.resolution_y = p["res_y"]

            if hasattr(scene, "cycles"):
                scene.cycles.samples = p["samples"]

        return ResponseBuilder.success(
            handler="manage_rendering",
            action=RenderAction.SET_QUALITY_PRESET.value,
            data={"preset": preset, "settings": presets.get(preset, {})},
        )
    except Exception as e:
        logger.error(f"SET_QUALITY_PRESET failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.SET_QUALITY_PRESET.value,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_render_frame(**params: Any) -> Dict[str, Any]:
    """
    Handle RENDER_FRAME action with extended timeout support.

    FIXED: Extended timeout support for long renders (high quality, 4K, etc.)
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.RENDER_FRAME.value,
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.RENDER_FRAME.value,
            error_code="NO_SCENE",
            message="No scene available",
        )

    from ..utils.path import get_safe_path

    try:
        path = params.get("filepath")
        if path:
            scene.render.filepath = get_safe_path(path)

        # Auto-camera feature
        auto_camera = params.get("auto_camera", False)
        if auto_camera and not scene.camera:
            cam_obj = _create_auto_camera()
            scene.camera = cam_obj
            logger.info(f"Auto-created camera: {cam_obj.name}")

        # Check camera exists
        if not scene.camera:
            return ResponseBuilder.error(
                handler="manage_rendering",
                action=RenderAction.RENDER_FRAME.value,
                error_code="NO_ACTIVE_OBJECT",
                message="No camera in scene. Use auto_camera=true to create one automatically.",
            )

        # Determine timeout (used implicitly via RenderTimeout defaults)
        _get_timeout(params, RenderTimeout.FRAME_DEFAULT.value)

        # Pre-render budget assessment and adaptive degradation
        budget = _estimate_render_budget(scene)
        adaptive_adjustments: Dict[str, Any] = {}
        if budget["risk"] == "HIGH" and not params.get("extended_timeout", False):
            if not params.get("force_quality", False):
                adaptive_adjustments = _apply_adaptive_degradation(scene, budget)
                logger.warning(
                    f"Render budget HIGH (score={budget['complexity_score']}). "
                    f"Applied adaptive degradation: {adaptive_adjustments}. "
                    f"Use extended_timeout=true or force_quality=true to override."
                )

        # RENDER_FRAME ALWAYS runs async (subprocess), same as RENDER_ANIMATION.
        # bpy.ops.render.render() blocks the entire Blender main thread for the full
        # render duration, freezing the MCP socket timer queue — no safe sync path exists.
        # _submit_async_render() saves a temp .blend and launches a headless Blender
        # subprocess, returning a job_id immediately so the main thread stays free.
        return _submit_async_render(scene, params, is_animation=False)

    except Exception as e:
        logger.error(f"RENDER_FRAME failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.RENDER_FRAME.value,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


_VIDEO_CONTAINERS = {
    ".mp4": ("FFMPEG", "MPEG4", "H264"),
    ".mkv": ("FFMPEG", "MKV", "H264"),
    ".mov": ("FFMPEG", "QUICKTIME", "H264"),
    ".avi": ("FFMPEG", "AVI", "H264"),
    ".webm": ("FFMPEG", "WEBM", "VORBIS"),
}


def _configure_output_format(scene: Any, filepath: str) -> None:
    """Auto-configure render output format based on filepath extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in _VIDEO_CONTAINERS:
        return
    container, fmt, codec = _VIDEO_CONTAINERS[ext]
    try:
        scene.render.image_settings.file_format = container
        scene.render.ffmpeg.format = fmt
        scene.render.ffmpeg.codec = codec
        scene.render.ffmpeg.audio_codec = "AAC"
        logger.info(f"_configure_output_format: set {container}/{fmt}/{codec} for {ext}")
    except Exception as e:
        logger.warning(f"_configure_output_format: could not set FFMPEG params: {e}")


def _handle_render_animation(**params: Any) -> Dict[str, Any]:
    """
    Handle RENDER_ANIMATION action with extended timeout support.

    FIXED: Extended timeout (up to 2 hours) for long animation renders
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.RENDER_ANIMATION.value,
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.RENDER_ANIMATION.value,
            error_code="NO_SCENE",
            message="No scene available",
        )

    from ..utils.path import get_safe_path

    try:
        path = params.get("filepath")
        if path:
            safe_path = get_safe_path(path)
            scene.render.filepath = safe_path
            # Auto-configure FFMPEG codec for video container formats
            _configure_output_format(scene, safe_path)

        # Check camera exists
        if not scene.camera and not params.get("auto_camera", False):
            return ResponseBuilder.error(
                handler="manage_rendering",
                action=RenderAction.RENDER_ANIMATION.value,
                error_code="NO_ACTIVE_OBJECT",
                message="No camera in scene. Use auto_camera=true or create one.",
            )

        # Auto-create camera if needed
        if params.get("auto_camera", False) and not scene.camera:
            cam_obj = _create_auto_camera()
            scene.camera = cam_obj

        # RENDER_ANIMATION ALWAYS runs async.
        # bpy.ops.render.render(animation=True) blocks the entire Blender main thread,
        # freezing the UI and the MCP socket server — there is no safe synchronous path.
        # _submit_async_render launches a headless Blender subprocess instead.
        return _submit_async_render(scene, params, is_animation=True)

    except Exception as e:
        logger.error(f"RENDER_ANIMATION failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_rendering",
            action=RenderAction.RENDER_ANIMATION.value,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _submit_async_render(
    scene: "Scene", params: Dict[str, Any], is_animation: bool = False
) -> Dict[str, Any]:
    """
    Submit a render job to the background AsyncJobManager.
    Saves a temporary copy of the current file to ensure state is captured.

    SAFETY: Always passes -o to the subprocess to make the output path explicit.
    If the scene's current render.filepath is empty or relative (e.g. //), or if
    no filepath was provided in params, output is redirected to a dedicated temp
    subdirectory to prevent renders silently writing to unexpected locations
    (Desktop, Blender install dir, etc.).
    """
    import tempfile

    # 1. Resolve output path BEFORE saving the temp file.
    # Priority: explicit param > scene's absolute path > safe temp fallback.
    raw_output = getattr(scene.render, "filepath", "") or ""
    explicit_filepath = params.get("filepath")

    # Determine if the current scene path is safe (absolute & user-intended).
    # Relative paths start with "//" in Blender notation or "./" on disk.
    _is_safe_abs = (
        bool(raw_output)
        and not raw_output.startswith("//")
        and not raw_output.startswith("./")
        and os.path.isabs(raw_output)
    )

    if not _is_safe_abs:
        # Scene has no explicit absolute path → redirect to a per-job temp subdir
        # so frames never land in Desktop, Blender install dir, or cwd.
        timestamp = int(time.time())
        safe_out_dir = os.path.join(
            tempfile.gettempdir(), f"blender_render_{timestamp}_{uuid.uuid4().hex[:6]}"
        )
        os.makedirs(safe_out_dir, exist_ok=True)
        # Blender appends #### + extension automatically; base name = "frame_"
        output_path = os.path.join(safe_out_dir, "frame_")
        if not explicit_filepath:
            logger.info(
                f"_submit_async_render: scene.render.filepath {raw_output!r} is relative/empty — "
                f"redirecting output to temp dir: {safe_out_dir}"
            )
    else:
        output_path = raw_output

    timestamp = int(time.time())

    # 2. Save temp .blend
    temp_filename = f"async_render_{timestamp}_{uuid.uuid4().hex[:8]}.blend"
    temp_path = os.path.join(tempfile.gettempdir(), temp_filename)

    try:
        bpy.ops.wm.save_as_mainfile(filepath=temp_path, copy=True, compress=True)
        logger.info(f"Saved temp file for async render: {temp_path}")
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action="ASYNC_SUBMIT",
            error_code="SAVE_FAILED",
            message=f"Failed to save temp file for async render: {e}",
        )

    # 3. Construct Command
    # Always include -o so the subprocess output is explicit regardless of what
    # path is embedded in the saved .blend. This prevents "ghost" renders to
    # previously-set paths (Desktop etc.) when no new filepath is provided.
    cmd = [bpy.app.binary_path, "-b", temp_path, "-o", output_path]

    if is_animation:
        cmd.append("-a")
        job_type = "Animation"
    else:
        cmd.extend(["-f", str(scene.frame_current)])
        job_type = "Frame"

    # 4. Submit Job
    try:
        job_name = f"Render {job_type} - {scene.name}"
        job_id = AsyncJobManager.submit_job(
            command=cmd,
            cwd=tempfile.gettempdir(),
            name=job_name,
            metadata={
                "blend_file": temp_path,
                "scene": scene.name,
                "output": output_path,
            },
        )

        return ResponseBuilder.success(
            handler="manage_rendering",
            action="ASYNC_SUBMIT",
            data={
                "job_id": job_id,
                "status": "QUEUED",
                "message": f"Async render submitted: {job_name}",
                "output": output_path,
                "temp_file": temp_path,
                "tip": "Use manage_jobs action=LIST_JOBS to monitor, CANCEL_JOB to stop.",
            },
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_rendering",
            action="ASYNC_SUBMIT",
            error_code="SUBMISSION_FAILED",
            message=f"Failed to submit async job: {e}",
        )


def _create_auto_camera() -> "Object":
    """Create a default camera positioned to frame the scene."""

    def create_and_position() -> "Object":
        cam_data = bpy.data.cameras.new(name="AutoRenderCamera")
        cam_obj = bpy.data.objects.new(name="AutoRenderCamera", object_data=cam_data)
        bpy.context.collection.objects.link(cam_obj)

        # Position camera
        active_obj = ContextManagerV3.get_active_object()
        if active_obj and active_obj.type == "MESH":
            bbox = [
                active_obj.matrix_world @ mathutils.Vector(corner)
                for corner in active_obj.bound_box
            ]
            center = sum(bbox, mathutils.Vector()) / 8
            max_dist = max((corner - center).length for corner in bbox)

            cam_obj.location = center + mathutils.Vector((max_dist * 2, -max_dist * 2, max_dist))
            _ = center - cam_obj.location
        return cam_obj

    # Cast to Object because execute_on_main_thread returns Any
    return cast("Object", execute_on_main_thread(create_and_position, timeout=10.0))


# =============================================================================
# ALIAS WRAPPERS
# =============================================================================


@register_handler(
    "render_frame",
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["render_frame"],
                "default": "render_frame",
                "description": "Alias action",
            },
            "filepath": {"type": "string"},
        },
        "required": ["action"],
    },
)
def render_frame_alias(**params: Any) -> Dict[str, Any]:
    """Alias for manage_rendering(action='RENDER_FRAME')"""
    return manage_rendering(action=RenderAction.RENDER_FRAME.value, **params)


@register_handler(
    "render_animation",
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["render_animation"],
                "default": "render_animation",
                "description": "Alias action",
            },
            "filepath": {"type": "string"},
        },
        "required": ["action"],
    },
)
def render_animation_alias(**params: Any) -> Dict[str, Any]:
    """Alias for manage_rendering(action='RENDER_ANIMATION')"""
    return manage_rendering(action=RenderAction.RENDER_ANIMATION.value, **params)


# =============================================================================
# VIEWPORT CAPTURE
# =============================================================================

_VALID_CAPTURE_ANGLES: frozenset = frozenset(
    {"FRONT", "BACK", "TOP", "BOTTOM", "LEFT", "RIGHT", "PERSP", "ISOMETRIC"}
)

_VALID_SHADING_TYPES: frozenset = frozenset({"SOLID", "MATERIAL", "RENDERED", "WIREFRAME"})

# Valid values for the view_direction parameter (single-shot directional capture).
_VALID_VIEW_DIRECTIONS: frozenset = frozenset(
    {
        "FRONT",
        "BACK",
        "LEFT",
        "RIGHT",
        "TOP",
        "BOTTOM",
        "PERSPECTIVE",
        "ISOMETRIC",
        "CLOSE_FRONT",
        "CLOSE_TOP",
        "AERIAL",
    }
)

# (mode, view_axis_type_or_None, distance_multiplier_relative_to_current)
_VIEW_DIRECTION_MAP: dict = {
    "FRONT": ("AXIS", "FRONT", 1.0),
    "BACK": ("AXIS", "BACK", 1.0),
    "LEFT": ("AXIS", "LEFT", 1.0),
    "RIGHT": ("AXIS", "RIGHT", 1.0),
    "TOP": ("AXIS", "TOP", 1.0),
    "BOTTOM": ("AXIS", "BOTTOM", 1.0),
    "PERSPECTIVE": ("PERSP", None, 1.0),
    "ISOMETRIC": ("ISO", None, 1.0),
    "CLOSE_FRONT": ("AXIS", "FRONT", 0.35),
    "CLOSE_TOP": ("AXIS", "TOP", 0.35),
    "AERIAL": ("AXIS", "TOP", 3.5),
}


def _apply_view_direction(
    scene: Any,
    view_direction: str,
    target_object_name: Optional[str] = None,
    distance: Optional[float] = None,
) -> Optional[dict]:
    """Set 3D viewport to a preset direction. Returns saved state or None.
    Must be called on the main thread. Caller is responsible for restoring
    the state via _restore_view_state().
    """
    import math as _math

    try:
        import mathutils as _mu
    except ImportError:
        _mu = None  # type: ignore[assignment]

    region3d = None
    space3d = None
    for area in bpy.context.window.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D" and hasattr(space, "region_3d"):
                    space3d = space
                    region3d = space.region_3d
                    break
        if region3d:
            break

    if not region3d:
        logger.warning("_apply_view_direction: no VIEW_3D region_3d found")
        return None

    saved: dict = {
        "view_perspective": region3d.view_perspective,
        "view_rotation": region3d.view_rotation.copy(),
        "view_distance": float(region3d.view_distance),
        "view_location": region3d.view_location.copy(),
        "lens": getattr(space3d, "lens", None) if space3d else None,
    }

    direction = view_direction.upper()
    mode, axis, dist_mult = _VIEW_DIRECTION_MAP.get(direction, ("PERSP", None, 1.0))

    try:
        if mode == "AXIS" and axis:
            with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
                bpy.ops.view3d.view_axis(type=axis)
        elif mode == "PERSP":
            region3d.view_perspective = "PERSP"
            with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
                bpy.ops.view3d.view_all(use_all_regions=False)
        elif mode == "ISO" and _mu:
            # Standard isometric: 45° yaw, ~55° pitch (Euler XYZ)
            region3d.view_perspective = "ORTHO"
            iso_euler = _mu.Euler((_math.radians(55.0), 0.0, _math.radians(45.0)), "XYZ")
            region3d.view_rotation = iso_euler.to_quaternion()
            with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
                bpy.ops.view3d.view_all(use_all_regions=False)
    except Exception as e:
        logger.warning(f"_apply_view_direction({direction}): set view failed: {e}")

    if target_object_name:
        try:
            target_obj = bpy.data.objects.get(target_object_name)
            if target_obj:
                for o in bpy.context.view_layer.objects:
                    o.select_set(False)
                target_obj.select_set(True)
                bpy.context.view_layer.objects.active = target_obj
                with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
                    bpy.ops.view3d.view_selected(use_all_regions=False)
                # Smart distance: compute from bounding box diagonal so object fills the viewport
                if distance is None and region3d:
                    try:
                        import mathutils as _mu_bd

                        bb = [
                            target_obj.matrix_world @ _mu_bd.Vector(c) for c in target_obj.bound_box
                        ]
                        diag = (
                            (max(c.x for c in bb) - min(c.x for c in bb)) ** 2
                            + (max(c.y for c in bb) - min(c.y for c in bb)) ** 2
                            + (max(c.z for c in bb) - min(c.z for c in bb)) ** 2
                        ) ** 0.5
                        optimal = max(diag * 2.0, 0.3)
                        region3d.view_distance = optimal
                    except Exception as _bd_err:
                        logger.warning(
                            f"_apply_view_direction: bbox distance calc failed: {_bd_err}"
                        )
        except Exception as e:
            logger.warning(
                f"_apply_view_direction: view_selected({target_object_name}) failed: {e}"
            )

    if distance is not None and distance > 0:
        try:
            region3d.view_distance = float(distance)
        except Exception as e:
            logger.warning(f"_apply_view_direction: set view_distance={distance} failed: {e}")
    elif dist_mult != 1.0:
        try:
            region3d.view_distance = region3d.view_distance * dist_mult
        except Exception as e:
            logger.warning(f"_apply_view_direction: scale view_distance failed: {e}")

    return saved


def _restore_view_state(saved: dict) -> None:
    """Restore viewport state saved by _apply_view_direction."""
    try:
        for area in bpy.context.window.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D" and hasattr(space, "region_3d"):
                        r3d = space.region_3d
                        r3d.view_perspective = saved["view_perspective"]
                        r3d.view_rotation = saved["view_rotation"]
                        r3d.view_distance = saved["view_distance"]
                        r3d.view_location = saved["view_location"]
                        if saved.get("lens") is not None and hasattr(space, "lens"):
                            space.lens = saved["lens"]
                        return
    except Exception as e:
        logger.warning(f"_restore_view_state failed: {e}")


def _set_viewport_shading(shading_type: str) -> Optional[str]:
    """Set 3D viewport shading mode. Returns the previous shading type, or None if not found."""
    try:
        for area in bpy.context.window.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D" and hasattr(space, "shading"):
                        old: Optional[str] = getattr(space.shading, "type", None)
                        space.shading.type = shading_type
                        return old
    except Exception as e:
        logger.warning(f"_set_viewport_shading({shading_type}) failed: {e}")
    return None


def _frame_scene_in_viewport(scene: Any) -> None:
    """Frame viewport on all visible MESH objects using full scene AABB (tight framing).

    Computes the overall world-space AABB for all visible MESH objects, then sets
    view_location to the AABB center and view_distance to half-diagonal * 1.4.
    This produces a tight, consistent frame regardless of scene complexity.
    Falls back to view_all if no MESH objects are found.
    """
    try:
        mesh_objs = [o for o in scene.objects if o.type == "MESH" and not o.hide_viewport]

        if not mesh_objs:
            # No mesh objects — fall back to view_all
            try:
                with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
                    bpy.ops.view3d.view_all(use_all_regions=False)
            except Exception:
                pass
            return

        # Compute overall scene AABB in world space (all 8 corners of each object)
        scene_min = [float("inf"), float("inf"), float("inf")]
        scene_max = [float("-inf"), float("-inf"), float("-inf")]

        for obj in mesh_objs:
            try:
                _ = obj.name  # StructRNA guard
                mw = obj.matrix_world
                for corner in obj.bound_box:
                    wx = (
                        mw[0][0] * corner[0]
                        + mw[0][1] * corner[1]
                        + mw[0][2] * corner[2]
                        + mw[0][3]
                    )
                    wy = (
                        mw[1][0] * corner[0]
                        + mw[1][1] * corner[1]
                        + mw[1][2] * corner[2]
                        + mw[1][3]
                    )
                    wz = (
                        mw[2][0] * corner[0]
                        + mw[2][1] * corner[1]
                        + mw[2][2] * corner[2]
                        + mw[2][3]
                    )
                    scene_min[0] = min(scene_min[0], wx)
                    scene_min[1] = min(scene_min[1], wy)
                    scene_min[2] = min(scene_min[2], wz)
                    scene_max[0] = max(scene_max[0], wx)
                    scene_max[1] = max(scene_max[1], wy)
                    scene_max[2] = max(scene_max[2], wz)
            except (ReferenceError, Exception):
                continue

        if scene_min[0] == float("inf"):
            return  # No valid objects processed

        centroid = (
            (scene_min[0] + scene_max[0]) / 2,
            (scene_min[1] + scene_max[1]) / 2,
            (scene_min[2] + scene_max[2]) / 2,
        )
        # Half-diagonal of the overall scene AABB — accounts for actual object extents
        half_diag = (
            (scene_max[0] - scene_min[0]) ** 2
            + (scene_max[1] - scene_min[1]) ** 2
            + (scene_max[2] - scene_min[2]) ** 2
        ) ** 0.5 / 2
        # 1.4x half-diagonal: tight framing with small margin, clamped to [0.5, 50]
        view_dist = max(min(half_diag * 1.4, 50.0), 0.5)

        try:
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type == "VIEW_3D":
                        for space in area.spaces:
                            if space.type == "VIEW_3D":
                                rv3d = space.region_3d
                                if rv3d is not None:
                                    rv3d.view_location = mathutils.Vector(centroid)
                                    rv3d.view_distance = view_dist
                                break
        except Exception as _ze:
            logger.debug(f"_frame_scene_in_viewport: set view failed (non-fatal): {_ze}")
    except Exception as e:
        logger.warning(f"_frame_scene_in_viewport failed: {e}")


def _frame_two_objects_in_viewport(
    scene: Any, name_a: str, name_b: str, gap_m: float | None = None
) -> Any:
    """Frame the viewport to encompass the union AABB of two named objects.

    When gap_m is provided (meters), uses gap-midpoint framing:
      - centroid = midpoint between the two object AABB centers (not union AABB centroid)
      - view_dist = max_obj_half_size * 2.0 + gap_m * 3.0  (adaptive zoom based on gap size)
    Otherwise: union AABB centroid + half_diag * 1.6.

    Returns (centroid, view_dist) tuple on success, False on failure.
    Falls back to scene framing if either object is not found.
    """
    try:
        obj_a = bpy.data.objects.get(name_a) if BPY_AVAILABLE else None
        obj_b = bpy.data.objects.get(name_b) if BPY_AVAILABLE else None

        if not obj_a or not obj_b:
            missing = []
            if not obj_a:
                missing.append(name_a)
            if not obj_b:
                missing.append(name_b)
            logger.warning(f"_frame_two_objects: objects not found: {missing}")
            _frame_scene_in_viewport(scene)
            return False

        # Compute union AABB for both objects in world space
        union_min = [float("inf"), float("inf"), float("inf")]
        union_max = [float("-inf"), float("-inf"), float("-inf")]

        for obj in (obj_a, obj_b):
            try:
                _ = obj.name  # StructRNA guard
                mw = obj.matrix_world
                for corner in obj.bound_box:
                    wx = (
                        mw[0][0] * corner[0]
                        + mw[0][1] * corner[1]
                        + mw[0][2] * corner[2]
                        + mw[0][3]
                    )
                    wy = (
                        mw[1][0] * corner[0]
                        + mw[1][1] * corner[1]
                        + mw[1][2] * corner[2]
                        + mw[1][3]
                    )
                    wz = (
                        mw[2][0] * corner[0]
                        + mw[2][1] * corner[1]
                        + mw[2][2] * corner[2]
                        + mw[2][3]
                    )
                    union_min[0] = min(union_min[0], wx)
                    union_min[1] = min(union_min[1], wy)
                    union_min[2] = min(union_min[2], wz)
                    union_max[0] = max(union_max[0], wx)
                    union_max[1] = max(union_max[1], wy)
                    union_max[2] = max(union_max[2], wz)
            except (ReferenceError, Exception):
                continue

        if union_min[0] == float("inf"):
            return False

        union_centroid = (
            (union_min[0] + union_max[0]) / 2,
            (union_min[1] + union_max[1]) / 2,
            (union_min[2] + union_max[2]) / 2,
        )
        half_diag = (
            (union_max[0] - union_min[0]) ** 2
            + (union_max[1] - union_min[1]) ** 2
            + (union_max[2] - union_min[2]) ** 2
        ) ** 0.5 / 2

        if gap_m is not None:
            # Gap-midpoint mode: focus between the two object AABB centers, adaptive zoom.
            # Compute each object's AABB center and max half-size for zoom formula.
            centers = []
            max_half_sizes = []
            for obj in (obj_a, obj_b):
                try:
                    _ = obj.name  # StructRNA guard
                    mw = obj.matrix_world
                    mn_obj = [float("inf")] * 3
                    mx_obj = [float("-inf")] * 3
                    for corner in obj.bound_box:
                        wx = (
                            mw[0][0] * corner[0]
                            + mw[0][1] * corner[1]
                            + mw[0][2] * corner[2]
                            + mw[0][3]
                        )
                        wy = (
                            mw[1][0] * corner[0]
                            + mw[1][1] * corner[1]
                            + mw[1][2] * corner[2]
                            + mw[1][3]
                        )
                        wz = (
                            mw[2][0] * corner[0]
                            + mw[2][1] * corner[1]
                            + mw[2][2] * corner[2]
                            + mw[2][3]
                        )
                        mn_obj[0] = min(mn_obj[0], wx)
                        mx_obj[0] = max(mx_obj[0], wx)
                        mn_obj[1] = min(mn_obj[1], wy)
                        mx_obj[1] = max(mx_obj[1], wy)
                        mn_obj[2] = min(mn_obj[2], wz)
                        mx_obj[2] = max(mx_obj[2], wz)
                    centers.append(tuple((mn_obj[k] + mx_obj[k]) / 2 for k in range(3)))
                    max_half_sizes.append(max((mx_obj[k] - mn_obj[k]) for k in range(3)) / 2)
                except (ReferenceError, Exception):
                    pass
            if len(centers) == 2:
                centroid = tuple((centers[0][k] + centers[1][k]) / 2 for k in range(3))  # type: ignore[assignment]
                max_half = max(max_half_sizes[0], max_half_sizes[1], 0.05)
                view_dist = max(max_half * 2.0 + gap_m * 3.0, 0.05)
            else:
                centroid = union_centroid
                view_dist = max(min(half_diag * 1.6, 50.0), 0.3)
        else:
            centroid = union_centroid
            view_dist = max(min(half_diag * 1.6, 50.0), 0.3)

        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            rv3d = space.region_3d
                            if rv3d is not None:
                                rv3d.view_location = mathutils.Vector(centroid)
                                rv3d.view_distance = view_dist
                            break
        return (centroid, view_dist)
    except Exception as e:
        logger.warning(f"_frame_two_objects_in_viewport failed: {e}")
        return False


def _reapply_frame_center(centroid: tuple, view_dist: float) -> None:
    """Re-apply a pre-computed view center/distance to all VIEW_3D regions.

    Used after _apply_view_direction (which calls view_all/view_axis and resets view_location)
    to restore the two-object union AABB framing.
    """
    try:
        if not BPY_AVAILABLE:
            return
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            rv3d = space.region_3d
                            if rv3d is not None:
                                rv3d.view_location = mathutils.Vector(centroid)
                                rv3d.view_distance = float(view_dist)
                            break
    except Exception as e:
        logger.warning(f"_reapply_frame_center failed: {e}")


def _resize_image_to_max_size(filepath: str, max_size: int) -> None:
    """Load image file, scale longest side to max_size, save in-place, and unload from bpy.data."""
    try:
        img = bpy.data.images.load(filepath, check_existing=False)
        try:
            w, h = img.size
            if w > max_size or h > max_size:
                aspect = w / max(h, 1)
                if w >= h:
                    new_w, new_h = max_size, max(1, int(max_size / aspect))
                else:
                    new_h, new_w = max_size, max(1, int(max_size * aspect))
                img.scale(new_w, new_h)
            img.save()
        finally:
            bpy.data.images.remove(img)
    except Exception as e:
        logger.warning(f"_resize_image_to_max_size failed: {e}")


def _do_opengl_capture(scene: Any, filepath: str) -> bool:
    """Run render.opengl and write to filepath. Must be called on the main thread."""
    scene.render.filepath = filepath
    try:
        with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
            safe_ops.render.opengl(write_still=True, view_context=True)
        return True
    except Exception as e:
        logger.warning(f"opengl view_context=True failed: {e}")
    try:
        with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
            safe_ops.render.opengl(write_still=True, view_context=False)
        return True
    except Exception as e2:
        logger.error(f"opengl view_context=False fallback failed: {e2}")
        return False


def _capture_angles(angles: list, base_path: str, scene: Any) -> dict:
    """
    Capture one screenshot per angle. Must be called on the main thread.
    Returns {angle: filepath} for each successfully captured angle.
    Saves and restores the original view state.
    """
    results: dict = {}

    # Find SpaceView3D.region_3d
    region3d = None
    for area in bpy.context.window.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if hasattr(space, "region_3d"):
                    region3d = space.region_3d
                    break
        if region3d:
            break

    if not region3d:
        logger.error("_capture_angles: no VIEW_3D region_3d found")
        return results

    # Save original view state
    orig_perspective = region3d.view_perspective
    orig_rotation = region3d.view_rotation.copy()
    orig_distance = float(region3d.view_distance)
    orig_location = region3d.view_location.copy()

    try:
        stem, ext = os.path.splitext(base_path)
        if not ext:
            ext = ".png"

        for raw_angle in angles:
            angle = raw_angle.upper()
            if angle not in _VALID_CAPTURE_ANGLES:
                logger.warning(f"_capture_angles: unknown angle '{angle}', skipping")
                continue

            angle_filepath = f"{stem}_{angle.lower()}{ext}"

            # Set view for this angle
            try:
                if angle == "ISOMETRIC":
                    import math as _math

                    try:
                        import mathutils as _mu_ca
                    except ImportError:
                        _mu_ca = None  # type: ignore[assignment]
                    region3d.view_perspective = "ORTHO"
                    if _mu_ca:
                        iso_euler = _mu_ca.Euler(
                            (_math.radians(55.0), 0.0, _math.radians(45.0)), "XYZ"
                        )
                        region3d.view_rotation = iso_euler.to_quaternion()
                elif angle == "PERSP":
                    region3d.view_perspective = "PERSP"
                else:
                    with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
                        bpy.ops.view3d.view_axis(type=angle)
            except Exception as e:
                logger.warning(f"_capture_angles: set view({angle}) failed: {e}, skipping")
                continue

            # Auto-frame scene after each angle change for consistent framing
            try:
                with ContextManagerV3.temp_override(area_type="VIEW_3D", scene=scene):
                    bpy.ops.view3d.view_all(use_all_regions=False)
            except Exception as e:
                logger.warning(f"_capture_angles: view_all({angle}) failed: {e}")

            # Capture this angle
            ok = _do_opengl_capture(scene, angle_filepath)
            if ok:
                results[angle] = angle_filepath
    finally:
        # Restore original view state (best effort)
        try:
            region3d.view_perspective = orig_perspective
            region3d.view_rotation = orig_rotation
            region3d.view_distance = orig_distance
            region3d.view_location = orig_location
        except Exception as restore_err:
            logger.warning(f"_capture_angles: view restore failed: {restore_err}")

    return results


def _apply_max_size(scene: Any, max_size: int) -> tuple:
    """Scale render resolution to fit max_size, preserving aspect. Returns (orig_x, orig_y, orig_pct)."""
    orig_x = int(getattr(scene.render, "resolution_x", 1920))
    orig_y = int(getattr(scene.render, "resolution_y", 1080))
    orig_pct = int(getattr(scene.render, "resolution_percentage", 100))
    if orig_x > max_size or orig_y > max_size:
        aspect = orig_x / max(orig_y, 1)
        if orig_x >= orig_y:
            scene.render.resolution_x = max_size
            scene.render.resolution_y = max(1, int(max_size / aspect))
        else:
            scene.render.resolution_y = max_size
            scene.render.resolution_x = max(1, int(max_size * aspect))
    scene.render.resolution_percentage = 100
    return orig_x, orig_y, orig_pct


@register_handler(
    "get_viewport_screenshot",
    priority=10,
    schema={
        "type": "object",
        "title": "Get Viewport Screenshot",
        "description": (
            "Capture viewport screenshot(s). Returns file path(s) and inline base64 preview images. "
            "For multi-angle base64 output use get_viewport_screenshot_base64 (TIER 1, priority 3). "
            "Supports angles=['FRONT','TOP','RIGHT','ISOMETRIC'] for batch capture — all returned as images. "
            "Use frame=N to capture at a specific animation frame."
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_viewport_screenshot"],
                "default": "get_viewport_screenshot",
                "description": "Action to perform",
            },
            "filepath": {"type": "string", "description": "Output file path (optional)"},
            "max_size": {"type": "integer", "description": "Max pixel dimension (default 800)"},
            "format": {
                "type": "string",
                "enum": ["PNG", "JPG", "JPEG", "WEBP"],
                "description": "Image format (default PNG). JPG and JPEG are equivalent.",
            },
            "angles": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["FRONT", "BACK", "TOP", "BOTTOM", "LEFT", "RIGHT", "PERSP"],
                },
                "description": "Capture from multiple angles. If omitted, captures current view.",
            },
            "shading": {
                "type": "string",
                "enum": ["SOLID", "MATERIAL", "RENDERED", "WIREFRAME"],
                "default": "MATERIAL",
                "description": "Viewport shading mode (default MATERIAL for colored output).",
            },
            "frame_scene": {
                "type": "boolean",
                "default": True,
                "description": "Auto-frame all scene objects in the viewport before capture (default true).",
            },
            "view_direction": {
                "type": "string",
                "enum": [
                    "FRONT",
                    "BACK",
                    "LEFT",
                    "RIGHT",
                    "TOP",
                    "BOTTOM",
                    "PERSPECTIVE",
                    "ISOMETRIC",
                    "CLOSE_FRONT",
                    "CLOSE_TOP",
                    "AERIAL",
                ],
                "description": (
                    "Set viewport to a preset direction before capture. "
                    "FRONT/BACK/LEFT/RIGHT/TOP/BOTTOM: orthographic axis views. "
                    "PERSPECTIVE: free perspective view. ISOMETRIC: isometric view. "
                    "CLOSE_FRONT/CLOSE_TOP: tight close-up (0.35x distance). AERIAL: high bird's-eye (3.5x). "
                    "Must be a SINGLE string — use 'angles' for multi-view batch capture. "
                    "Passing a list will return an INVALID_PARAMETER error."
                ),
            },
            "target_object": {
                "type": "string",
                "description": (
                    "RECOMMENDED — Exact object name to zoom into before capture. "
                    "Disables frame_scene auto-framing and focuses tightly on this object's bounding box. "
                    "Example: target_object='Drone_Body_Shell' with view_direction='ISOMETRIC'. "
                    "Without this, the entire scene is framed (parts appear tiny in complex scenes)."
                ),
            },
            "distance": {
                "type": "number",
                "description": "Viewport camera distance in Blender units (overrides preset distance multiplier).",
            },
            "output_mode": {
                "type": "string",
                "enum": ["both", "base64_only", "file_only"],
                "default": "both",
                "description": (
                    "Output mode: 'both' (base64+filepath), 'base64_only' (no filepath returned), "
                    "'file_only' (no base64 encoding — faster for large captures)."
                ),
            },
        },
        "required": ["action"],
    },
)
def get_viewport_screenshot(**params: Any) -> Dict[str, Any]:
    """
    Capture viewport screenshot(s) and return file path(s).

    Params:
        filepath (str): Output path. Auto-generated in temp dir if omitted.
        max_size (int): Max pixel dimension (default 800). Preserves aspect ratio.
        format (str): 'PNG' or 'JPG' (default 'PNG').
        angles (list[str]): Multi-angle capture — e.g. ["FRONT", "TOP", "PERSP"].
        shading (str): Viewport shading — SOLID, MATERIAL (default), RENDERED, WIREFRAME.
        frame_scene (bool): Auto-frame scene objects before capture (default True).

    Returns:
        Single angle: {filepath: "..."} | Multi-angle: {filepaths: {angle: "..."}}
    """
    import tempfile
    import traceback

    from ..utils.path import get_safe_path

    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="get_viewport_screenshot",
            action="CAPTURE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    if bpy.app.background:
        return ResponseBuilder.error(
            handler="get_viewport_screenshot",
            action="CAPTURE",
            error_code="HEADLESS_NOT_SUPPORTED",
            message="Viewport screenshot requires a window system. Not available in headless/background mode. Use RENDER_FRAME instead.",
        )

    try:
        max_size = int(params.get("max_size", 800))
        user_path = params.get("filepath")
        img_format = _FORMAT_MAP.get(params.get("format", "PNG").upper(), "PNG")
        angles = params.get("angles")
        shading = str(params.get("shading", "MATERIAL")).upper()
        if shading not in _VALID_SHADING_TYPES:
            shading = "MATERIAL"
        frame_scene = bool(params.get("frame_scene", True))
        output_mode = str(params.get("output_mode", "both")).lower()
        if output_mode not in ("both", "base64_only", "file_only"):
            output_mode = "both"

        # view_direction — single-shot directional capture (list input is explicitly blocked)
        view_direction_raw = params.get("view_direction")
        if isinstance(view_direction_raw, list):
            return ResponseBuilder.error(
                handler="get_viewport_screenshot",
                action="CAPTURE",
                error_code="INVALID_PARAMETER",
                message=(
                    "view_direction must be a single string (e.g. 'FRONT'), not a list. "
                    "For multi-angle batch capture use the 'angles' parameter instead."
                ),
            )
        view_direction = str(view_direction_raw).upper() if view_direction_raw else None
        if view_direction and view_direction not in _VALID_VIEW_DIRECTIONS:
            return ResponseBuilder.error(
                handler="get_viewport_screenshot",
                action="CAPTURE",
                error_code="INVALID_PARAMETER",
                message=(
                    f"Invalid view_direction '{view_direction}'. "
                    f"Valid values: {sorted(_VALID_VIEW_DIRECTIONS)}"
                ),
            )
        target_object_name = params.get("target_object")
        raw_distance = params.get("distance")
        view_distance = float(raw_distance) if raw_distance is not None else None

        # Resolve base filepath
        if user_path:
            try:
                parent = os.path.dirname(os.path.abspath(user_path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
                base_filepath = user_path
            except OSError as e:
                logger.warning(f"Failed to create dir for '{user_path}': {e}. Using safe path.")
                base_filepath = get_safe_path(user_path)
        else:
            base_filepath = os.path.join(tempfile.gettempdir(), f"mcp_view_{int(time.time())}.png")

        scene = ContextManagerV3.get_scene()
        if not scene:
            return ResponseBuilder.error(
                handler="get_viewport_screenshot",
                action="CAPTURE",
                error_code="NO_SCENE",
                message="No scene available",
            )

        orig_format = getattr(scene.render.image_settings, "file_format", "PNG")
        scene.render.image_settings.file_format = img_format

        # Set viewport shading and optionally frame scene
        # Skip auto-frame when target_object is set — _apply_view_direction handles focus
        old_shading = _set_viewport_shading(shading)
        if frame_scene and not target_object_name:
            _frame_scene_in_viewport(scene)

        # Apply view direction preset (saves original state for restore in finally)
        saved_view = None
        if view_direction:
            saved_view = _apply_view_direction(
                scene, view_direction, target_object_name, view_distance
            )
        elif target_object_name or view_distance is not None:
            # target_object/distance without explicit direction — focus from current perspective
            saved_view = _apply_view_direction(
                scene, "PERSPECTIVE", target_object_name, view_distance
            )

        try:
            if angles:
                # --- Multi-angle capture ---
                angle_list = [str(a) for a in angles]
                n = max(1, len(angle_list))

                def do_multi() -> dict:
                    return _capture_angles(angle_list, base_filepath, scene)

                filepaths = cast(
                    dict,
                    execute_on_main_thread(
                        do_multi,
                        timeout=RenderTimeout.VIEWPORT_CAPTURE.value * n,
                    ),
                )

                if not filepaths:
                    return ResponseBuilder.error(
                        handler="get_viewport_screenshot",
                        action="CAPTURE",
                        error_code="EXECUTION_ERROR",
                        message="No angles could be captured",
                    )

                # Encode each captured image as base64 for AI vision display
                import base64 as _b64

                images_list = []
                for _angle, _path in filepaths.items():
                    if os.path.exists(_path):
                        try:
                            _resize_image_to_max_size(_path, max_size)
                            with open(_path, "rb") as _fh:
                                images_list.append(
                                    {
                                        "data": _b64.b64encode(_fh.read()).decode("utf-8"),
                                        "mime": _FORMAT_MIME.get(img_format, "image/png"),
                                        "label": _angle,
                                    }
                                )
                        except Exception as _enc_err:
                            logger.warning(f"angles base64 encode failed for {_angle}: {_enc_err}")

                return ResponseBuilder.success(
                    handler="get_viewport_screenshot",
                    action="CAPTURE",
                    data={
                        "filepaths": filepaths,
                        "angles": list(filepaths.keys()),
                        "__mcp_images__": images_list,
                    },
                )

            else:
                # --- Single capture (current view, view_context=True = viewport shading) ---
                def do_single() -> bool:
                    return _do_opengl_capture(scene, base_filepath)

                success = cast(
                    bool,
                    execute_on_main_thread(do_single, timeout=RenderTimeout.VIEWPORT_CAPTURE.value),
                )

                if not success:
                    return ResponseBuilder.error(
                        handler="get_viewport_screenshot",
                        action="CAPTURE",
                        error_code="EXECUTION_ERROR",
                        message="Viewport capture failed",
                    )

                # Resize main capture to max_size (view_context=True uses screen resolution).
                if max_size and max_size > 0:
                    _resize_image_to_max_size(base_filepath, max_size)

                # Build response based on output_mode (single capture — no double render).
                import base64 as _b64

                result_data: dict = {
                    "shading": shading,
                    "view_direction": view_direction or "CURRENT",
                }
                if output_mode in ("both", "file_only"):
                    result_data["filepath"] = base_filepath
                if output_mode in ("both", "base64_only"):
                    try:
                        with open(base_filepath, "rb") as _fh:
                            _b64_data = _b64.b64encode(_fh.read()).decode("utf-8")
                        result_data["__mcp_image_data__"] = _b64_data
                        result_data["__mcp_image_mime__"] = _FORMAT_MIME.get(
                            img_format, "image/png"
                        )
                    except Exception as _ie:
                        logger.warning(f"Base64 encode failed: {_ie}")

                return ResponseBuilder.success(
                    handler="get_viewport_screenshot",
                    action="CAPTURE",
                    data=result_data,
                )

        finally:
            # Restore view direction, render format and viewport shading
            if saved_view is not None:
                _restore_view_state(saved_view)
            scene.render.image_settings.file_format = orig_format
            if old_shading is not None:
                _set_viewport_shading(old_shading)

    except Exception as e:
        traceback.print_exc()
        return ResponseBuilder.error(
            handler="get_viewport_screenshot",
            action="CAPTURE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


@register_handler(
    "get_viewport_screenshot_base64",
    priority=3,
    schema={
        "type": "object",
        "title": "Get Viewport Screenshot (TIER 1 — Visual Feedback)",
        "description": (
            "ESSENTIAL (priority=3) — Viewport capture tool. Saves image to disk and returns the file path.\n"
            "AI can view the image file using the Read tool on the returned filepath.\n"
            "Set base64=true to also write a JSON file containing the base64-encoded image.\n\n"
            "*** ALWAYS SPECIFY target_object FOR OBJECT SHOTS ***\n"
            "Without target_object the viewport frames THE ENTIRE SCENE — parts will appear tiny.\n"
            "With target_object the viewport zooms directly to that object's bounding box.\n\n"
            "USAGE EXAMPLES:\n"
            "  # Single object — isometric PBR shot\n"
            '  {"action":"get_viewport_screenshot_base64","target_object":"Drone_Arm_01","view_direction":"ISOMETRIC"}\n'
            "  # Scene overview — solid shading, top view\n"
            '  {"action":"get_viewport_screenshot_base64","view_direction":"TOP","shading":"SOLID"}\n'
            "  # Multi-angle batch (3 images in one call)\n"
            '  {"action":"get_viewport_screenshot_base64","target_object":"Body","views":["ISOMETRIC","FRONT","TOP"]}\n'
            "  # Two-object gap inspection — union AABB zoom\n"
            '  {"action":"get_viewport_screenshot_base64","target_objects":["Arm_01","MotorPod_01"],"view_direction":"ISOMETRIC"}\n'
            "  # Two-object gap inspection — gap-midpoint zoom (tight, 2mm gap)\n"
            '  {"action":"get_viewport_screenshot_base64","target_objects":["Prop_Hub","Prop_Blade"],"gap_focus_m":0.002,"view_direction":"FRONT"}\n'
            "  # Close-up detail shot\n"
            '  {"action":"get_viewport_screenshot_base64","target_object":"MotorPod_01","view_direction":"CLOSE_FRONT","shading":"MATERIAL"}\n'
            "  # Bird's-eye aerial overview\n"
            '  {"action":"get_viewport_screenshot_base64","view_direction":"AERIAL","shading":"SOLID"}\n'
            "  # Quick scene check\n"
            '  {"action":"SMART_SCREENSHOT"}\n'
            "  # Save base64 JSON sidecar file\n"
            '  {"action":"get_viewport_screenshot_base64","target_object":"Body","base64":true}\n'
            "  # Specific animation frame, high-res\n"
            '  {"action":"get_viewport_screenshot_base64","frame":24,"max_size":1024}\n\n'
            "PARAMETERS:\n"
            "  target_object  RECOMMENDED — Object name to zoom into (disables frame_scene).\n"
            "  target_objects — ['ObjA','ObjB']: frame union AABB of both objects (gap inspection).\n"
            "  gap_focus_m    — Gap in meters for tight gap-midpoint zoom (use with target_objects).\n"
            "                   Get from ANALYZE_ASSEMBLY issue.gap_m. 0.002=2mm→tight, 0.02=20mm→moderate.\n"
            "  view_direction — ISOMETRIC|FRONT|BACK|TOP|BOTTOM|LEFT|RIGHT|CLOSE_FRONT|CLOSE_TOP|AERIAL|PERSPECTIVE\n"
            "  views          — Multi-angle list: ['ISOMETRIC','FRONT','TOP'] → all images in one call\n"
            "  shading        — MATERIAL (default, PBR) | SOLID (geometry only, faster) | WIREFRAME\n"
            "  max_size       — 512 (default). 256=quick, 1024=detail. Keep ≤512 to avoid payload bloat.\n"
            "  frame_scene    — True (default): auto-frame whole scene. Ignored when target_object is set.\n"
            "  frame          — Animation frame to capture (e.g. frame=24). Scene restores after.\n"
            "  base64         — False (default). If true, saves base64 JSON sidecar and returns its path.\n\n"
            "BEST PRACTICES:\n"
            "  ✓ Always use target_object when inspecting a specific part\n"
            "  ✓ Assembly overview: views=['ISOMETRIC','TOP','FRONT','RIGHT'] (no target_object)\n"
            "  ✓ Gap inspection: target_objects=['A','B'], gap_focus_m=<issue.gap_m>, view_direction='FRONT'\n"
            "  ✓ Detail shot: target_object='PartName', view_direction='CLOSE_FRONT'\n"
            "  ✓ Quick: action='SMART_SCREENSHOT'\n"
            "  ✗ Do NOT use RENDERED shading (slow; MATERIAL is sufficient)\n"
            "  ✗ Do NOT combine views and view_direction in same call"
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_viewport_screenshot_base64", "SMART_SCREENSHOT"],
                "default": "get_viewport_screenshot_base64",
                "description": (
                    "Action to perform. "
                    "SMART_SCREENSHOT: auto-selects view and zoom based on scene context. "
                    "get_viewport_screenshot_base64: standard capture with full parameter control."
                ),
            },
            "base64": {
                "type": "boolean",
                "default": False,
                "description": (
                    "If true, encodes the captured image as base64 and saves it to a JSON file. "
                    "Returns base64_filepath in the response. Default: image file only, no base64."
                ),
            },
            "return_base64": {
                "type": "boolean",
                "default": False,
                "description": "Deprecated alias for base64. Use base64=true instead.",
            },
            "filepath": {
                "type": "string",
                "description": (
                    "Output file save path (optional). "
                    "If omitted the image is auto-saved to the system temp directory and "
                    "the actual path is returned in the response. "
                    "Example: 'C:/renders/my_model_preview.png'"
                ),
            },
            "max_size": {
                "type": "integer",
                "description": "Max pixel dimension (default 512). Keep small to avoid payload bloat.",
            },
            "format": {
                "type": "string",
                "enum": ["PNG", "JPG", "JPEG", "WEBP"],
                "description": "Image format (default PNG). JPG and JPEG are equivalent.",
            },
            "shading": {
                "type": "string",
                "enum": ["SOLID", "MATERIAL", "RENDERED", "WIREFRAME"],
                "default": "MATERIAL",
                "description": "Viewport shading mode (default MATERIAL for colored output).",
            },
            "frame_scene": {
                "type": "boolean",
                "default": True,
                "description": "Auto-frame all scene objects in the viewport before capture (default true).",
            },
            "view_direction": {
                "type": "string",
                "enum": [
                    "FRONT",
                    "BACK",
                    "LEFT",
                    "RIGHT",
                    "TOP",
                    "BOTTOM",
                    "PERSPECTIVE",
                    "ISOMETRIC",
                    "CLOSE_FRONT",
                    "CLOSE_TOP",
                    "AERIAL",
                ],
                "description": (
                    "Set viewport to a preset direction before capture. "
                    "FRONT/BACK/LEFT/RIGHT/TOP/BOTTOM: orthographic axis views. "
                    "PERSPECTIVE: free perspective view. ISOMETRIC: isometric view. "
                    "CLOSE_FRONT/CLOSE_TOP: tight close-up (0.35x distance). AERIAL: high bird's-eye (3.5x). "
                    "Must be a SINGLE string — for multi-view batch use get_viewport_screenshot with 'angles'. "
                    "Passing a list will return an INVALID_PARAMETER error."
                ),
            },
            "target_object": {
                "type": "string",
                "description": (
                    "RECOMMENDED — Exact object name to zoom into before capture. "
                    "Disables frame_scene auto-framing and focuses tightly on this object's bounding box. "
                    "Example: target_object='Drone_Body_Shell' with view_direction='ISOMETRIC'. "
                    "Without this, the entire scene is framed (parts appear tiny in complex scenes)."
                ),
            },
            "target_objects": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 2,
                "description": (
                    "Frame BOTH objects at once — useful for joint/gap/connection inspection. "
                    "Pass exactly 2 object names: ['ObjectA', 'ObjectB']. "
                    "Viewport zooms to the union AABB of both objects. "
                    "Combine with view_direction for angle control: "
                    "view_direction='ISOMETRIC' rotates to isometric while keeping both objects centered. "
                    "view_direction='FRONT'/'TOP'/'RIGHT' for orthographic directional shots. "
                    "Example: target_objects=['Drone_Arm_01','Drone_MotorPod_01'], view_direction='ISOMETRIC'. "
                    "Cannot be combined with target_object (target_object takes priority if both set)."
                ),
            },
            "distance": {
                "type": "number",
                "description": "Viewport camera distance in Blender units (overrides preset distance multiplier).",
            },
            "views": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "FRONT",
                        "BACK",
                        "LEFT",
                        "RIGHT",
                        "TOP",
                        "BOTTOM",
                        "PERSPECTIVE",
                        "ISOMETRIC",
                        "CLOSE_FRONT",
                        "CLOSE_TOP",
                        "AERIAL",
                    ],
                },
                "description": (
                    "Capture from multiple directions in one call — returns ALL images for AI vision. "
                    "Do NOT combine with view_direction. "
                    "Example: ['ISOMETRIC','FRONT','TOP'] → 3 images shown to Claude. "
                    "Each image uses target_object + frame_scene settings."
                ),
            },
            "gap_focus_m": {
                "type": "number",
                "description": (
                    "Gap distance in meters for gap-midpoint zoom mode (used with target_objects). "
                    "Focuses viewport on midpoint between the two object AABB centers with adaptive zoom: "
                    "view_dist = max_obj_half_size × 2 + gap_m × 3. "
                    "Example: gap_focus_m=0.002 (2mm gap) → tight; gap_focus_m=0.02 (20mm) → moderate. "
                    "Get gap_m from ANALYZE_ASSEMBLY issue.gap_m field."
                ),
            },
            "frame": {
                "type": "integer",
                "description": (
                    "Animation frame to jump to before capturing. "
                    "Useful to verify a specific animation state (e.g. frame=1, frame=24, frame=100). "
                    "Scene is restored to original frame after capture."
                ),
            },
        },
        "required": ["action"],
    },
)
def get_viewport_screenshot_base64(**params: Any) -> Dict[str, Any]:
    """
    Capture viewport screenshot and save to disk. Returns the file path.

    Default: saves image file, returns filepath. No base64 in response.
    base64=true: also encodes image as base64, saves to a JSON file, returns base64_filepath.

    Params:
        filepath (str): Output path. Auto-generated in temp dir if omitted.
        max_size (int): Max pixel dimension (default 512).
        format (str): 'PNG', 'JPEG'/'JPG', or 'WEBP' (default 'PNG').
        shading (str): Viewport shading — SOLID, MATERIAL (default), RENDERED, WIREFRAME.
        frame_scene (bool): Auto-frame scene objects before capture (default True).
        base64 (bool): If True, save base64 to a JSON file and include path in response.

    Returns:
        {filepath: "...", format: "...", resolution: [...], shading: "..."}
        + base64_filepath: "..." if base64=true
    """
    import base64
    import tempfile
    import traceback

    from ..utils.path import get_safe_path

    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="get_viewport_screenshot_base64",
            action="CAPTURE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    if bpy.app.background:
        return ResponseBuilder.error(
            handler="get_viewport_screenshot_base64",
            action="CAPTURE",
            error_code="HEADLESS_NOT_SUPPORTED",
            message="Viewport screenshot requires a window system. Not available in headless/background mode.",
        )

    # SMART_SCREENSHOT: auto-select view direction and zoom based on scene context
    if params.get("action") == "SMART_SCREENSHOT":
        try:
            active_obj = getattr(bpy.context, "active_object", None)
            selected_objs = list(getattr(bpy.context, "selected_objects", []))
            if active_obj and len(selected_objs) == 1:
                # Single object selected — zoom in close
                params = {
                    **params,
                    "target_object": params.get("target_object", active_obj.name),
                    "view_direction": params.get("view_direction", "CLOSE_FRONT"),
                    "shading": params.get("shading", "MATERIAL"),
                    "max_size": params.get("max_size", 512),
                }
            else:
                # Multiple or no selection — frame all, faster solid shading
                params = {
                    **params,
                    "shading": params.get("shading", "SOLID"),
                    "max_size": params.get("max_size", 512),
                    "frame_scene": params.get("frame_scene", True),
                }
        except Exception:
            pass  # Fall through to default capture on any context error

    # base64 param — opt-in: saves base64 to a JSON file and returns its path
    use_base64 = bool(params.get("base64") or params.get("return_base64", False))

    try:
        max_size = int(params.get("max_size", 512))
        user_path = params.get("filepath")
        img_format = _FORMAT_MAP.get(params.get("format", "PNG").upper(), "PNG")
        shading = str(params.get("shading", "MATERIAL")).upper()
        if shading not in _VALID_SHADING_TYPES:
            shading = "MATERIAL"
        frame_scene = bool(params.get("frame_scene", True))
        target_object_name = params.get("target_object")
        target_objects_list = params.get("target_objects")
        raw_distance = params.get("distance")
        view_distance = float(raw_distance) if raw_distance is not None else None

        scene = ContextManagerV3.get_scene()
        if not scene:
            return ResponseBuilder.error(
                handler="get_viewport_screenshot_base64",
                action="CAPTURE",
                error_code="NO_SCENE",
                message="No scene available",
            )

        # --- FRAME CONTROL: jump to requested animation frame before capture ---
        requested_frame = params.get("frame")
        original_frame = scene.frame_current
        if requested_frame is not None:
            scene.frame_set(int(requested_frame))

        # --- TWO-OBJECT FRAMING: frame union AABB of two objects ---
        two_obj_frame: tuple | None = (
            None  # (centroid, view_dist) for re-apply after view_direction
        )
        gap_focus_m_raw = params.get("gap_focus_m")
        gap_focus_m: float | None = float(gap_focus_m_raw) if gap_focus_m_raw is not None else None
        if (
            not target_object_name
            and isinstance(target_objects_list, list)
            and len(target_objects_list) == 2
        ):
            frame_result = _frame_two_objects_in_viewport(
                scene,
                str(target_objects_list[0]),
                str(target_objects_list[1]),
                gap_m=gap_focus_m,
            )
            if frame_result:
                two_obj_frame = frame_result  # type: ignore[assignment]

        # --- MULTI-VIEW MODE: views=[...] captures multiple angles, returns __mcp_images__ ---
        views_list = params.get("views")
        if views_list and isinstance(views_list, list):
            import base64 as _b64mv

            orig_format_mv = getattr(scene.render.image_settings, "file_format", "PNG")
            scene.render.image_settings.file_format = img_format
            old_shading_mv = _set_viewport_shading(shading)
            if frame_scene and not target_object_name and not target_objects_list:
                _frame_scene_in_viewport(scene)
            images_list_mv: list = []
            base_stem = os.path.join(
                tempfile.gettempdir(),
                f"mcp_view_mv_{int(time.time())}",
            )
            try:
                for vd in views_list:
                    vd_upper = str(vd).upper()
                    if vd_upper not in _VALID_VIEW_DIRECTIONS:
                        logger.warning(f"views: skipping invalid direction '{vd_upper}'")
                        continue
                    vd_path = f"{base_stem}_{vd_upper.lower()}.png"
                    saved_vd = _apply_view_direction(
                        scene, vd_upper, target_object_name, view_distance
                    )
                    # Re-apply two-object framing center after view_direction resets viewport position
                    if two_obj_frame and not target_object_name:
                        _reapply_frame_center(two_obj_frame[0], two_obj_frame[1])
                    try:

                        def _do_cap_vd(p: str = vd_path) -> bool:
                            return _do_opengl_capture(scene, p)

                        success_vd = cast(
                            bool,
                            execute_on_main_thread(
                                _do_cap_vd, timeout=RenderTimeout.VIEWPORT_CAPTURE.value
                            ),
                        )
                        if success_vd and os.path.exists(vd_path):
                            _resize_image_to_max_size(vd_path, max_size)
                            with open(vd_path, "rb") as _fh:
                                images_list_mv.append(
                                    {
                                        "data": _b64mv.b64encode(_fh.read()).decode("utf-8"),
                                        "mime": _FORMAT_MIME.get(img_format, "image/png"),
                                        "label": vd_upper,
                                    }
                                )
                    finally:
                        if saved_vd:
                            _restore_view_state(saved_vd)
            finally:
                scene.render.image_settings.file_format = orig_format_mv
                if old_shading_mv is not None:
                    _set_viewport_shading(old_shading_mv)
                # Restore animation frame if it was changed
                if requested_frame is not None:
                    scene.frame_set(original_frame)
            return ResponseBuilder.success(
                handler="get_viewport_screenshot_base64",
                action="CAPTURE",
                data={
                    "views": [img["label"] for img in images_list_mv],
                    "image_count": len(images_list_mv),
                    "__mcp_images__": images_list_mv,
                },
            )

        # --- SINGLE VIEW MODE (original behaviour) ---

        # view_direction — single-shot directional capture (list input is explicitly blocked)
        view_direction_raw = params.get("view_direction")
        if isinstance(view_direction_raw, list):
            return ResponseBuilder.error(
                handler="get_viewport_screenshot_base64",
                action="CAPTURE",
                error_code="INVALID_PARAMETER",
                message=(
                    "view_direction must be a single string (e.g. 'FRONT'), not a list. "
                    "For multi-angle capture use the 'views' parameter instead: "
                    "views=['FRONT','TOP','ISOMETRIC']"
                ),
            )
        view_direction = str(view_direction_raw).upper() if view_direction_raw else None
        if view_direction and view_direction not in _VALID_VIEW_DIRECTIONS:
            return ResponseBuilder.error(
                handler="get_viewport_screenshot_base64",
                action="CAPTURE",
                error_code="INVALID_PARAMETER",
                message=(
                    f"Invalid view_direction '{view_direction}'. "
                    f"Valid values: {sorted(_VALID_VIEW_DIRECTIONS)}"
                ),
            )

        # Resolve filepath
        if user_path:
            try:
                parent = os.path.dirname(os.path.abspath(user_path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
                filepath = user_path
            except OSError as e:
                logger.warning(f"Failed to create dir for '{user_path}': {e}. Using safe path.")
                filepath = get_safe_path(user_path)
        else:
            filepath = os.path.join(tempfile.gettempdir(), f"mcp_view_b64_{int(time.time())}.png")

        orig_format = getattr(scene.render.image_settings, "file_format", "PNG")
        scene.render.image_settings.file_format = img_format

        # Set viewport shading and optionally frame scene
        # Skip auto-frame when target_object or target_objects is set
        old_shading = _set_viewport_shading(shading)
        if frame_scene and not target_object_name and not target_objects_list:
            _frame_scene_in_viewport(scene)

        # Apply view direction preset (saves original state for restore in finally)
        saved_view = None
        if view_direction:
            saved_view = _apply_view_direction(
                scene, view_direction, target_object_name, view_distance
            )
            # Re-apply two-object framing center after view_direction resets viewport position
            if two_obj_frame and not target_object_name:
                _reapply_frame_center(two_obj_frame[0], two_obj_frame[1])
        elif target_object_name or view_distance is not None:
            saved_view = _apply_view_direction(
                scene, "PERSPECTIVE", target_object_name, view_distance
            )

        try:

            def do_capture() -> bool:
                return _do_opengl_capture(scene, filepath)

            success = cast(
                bool,
                execute_on_main_thread(do_capture, timeout=RenderTimeout.VIEWPORT_CAPTURE.value),
            )

            if not success:
                return ResponseBuilder.error(
                    handler="get_viewport_screenshot_base64",
                    action="CAPTURE",
                    error_code="EXECUTION_ERROR",
                    message="Viewport capture failed",
                )

            if not os.path.exists(filepath):
                return ResponseBuilder.error(
                    handler="get_viewport_screenshot_base64",
                    action="CAPTURE",
                    error_code="FILE_NOT_FOUND",
                    message=f"Captured file not found: {filepath}",
                )

            # Resize to max_size (view_context=True captures at full screen resolution)
            if max_size and max_size > 0:
                _resize_image_to_max_size(filepath, max_size)

            img = bpy.data.images.get(os.path.basename(filepath))
            actual_res = list(img.size) if img else [max_size, max_size]

            response_data: Dict[str, Any] = {
                "filepath": filepath,
                "format": img_format,
                "shading": shading,
                "view_direction": view_direction or "CURRENT",
                "resolution": actual_res,
            }

            # Always encode base64 for inline delivery (tool is named *_base64).
            # use_base64=True additionally writes a JSON sidecar file.
            MAX_BASE64_FILE_SIZE = 1 * 1024 * 1024  # 1 MB hard limit
            file_size = os.path.getsize(filepath)
            if file_size > MAX_BASE64_FILE_SIZE:
                if use_base64:
                    return ResponseBuilder.error(
                        handler="get_viewport_screenshot_base64",
                        action="CAPTURE",
                        error_code="FILE_TOO_LARGE",
                        message=(
                            f"Captured image ({file_size / 1024:.0f} KB) exceeds 1 MB limit. "
                            f"Reduce max_size (currently {max_size}px)."
                        ),
                    )
                # For default calls, skip inline data but keep filepath in response
            else:
                with open(filepath, "rb") as fh:
                    b64_data = base64.b64encode(fh.read()).decode("utf-8")
                response_data["__mcp_image_data__"] = b64_data
                response_data["__mcp_image_mime__"] = _FORMAT_MIME.get(img_format, "image/png")
                if use_base64:
                    import json as _json

                    b64_json_path = os.path.splitext(filepath)[0] + "_b64.json"
                    with open(b64_json_path, "w") as jf:
                        _json.dump(
                            {
                                "base64": b64_data,
                                "mime": _FORMAT_MIME.get(img_format, "image/png"),
                                "filepath": filepath,
                            },
                            jf,
                        )
                    response_data["base64_filepath"] = b64_json_path

            return ResponseBuilder.success(
                handler="get_viewport_screenshot_base64",
                action="CAPTURE",
                data=response_data,
            )

        finally:
            # Restore view direction, render format and viewport shading
            if saved_view is not None:
                _restore_view_state(saved_view)
            scene.render.image_settings.file_format = orig_format
            if old_shading is not None:
                _set_viewport_shading(old_shading)
            # Restore animation frame if it was changed
            if requested_frame is not None:
                scene.frame_set(original_frame)

    except Exception as e:
        traceback.print_exc()
        return ResponseBuilder.error(
            handler="get_viewport_screenshot_base64",
            action="CAPTURE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )
