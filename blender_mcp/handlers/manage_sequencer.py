"""
Video Sequence Editor (VSE) Handler for Blender MCP - V1.0.0 Fixed

Fixes from test report:
- Blender 5.0+ API compatibility for sequences access
- Enhanced error handling with sequence_editor initialization
- Proper strip selection handling for Blender 5.x
- Thread-safe VSE operations

High Mode Philosophy: Maximum power, maximum safety.
"""

from typing import Dict, Any
import os

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.thread_safety import execute_on_main_thread, ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.error_protocol import ErrorProtocol
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.universal_coercion import ParameterNormalizer
from ..core.enums import SequencerAction, SequencerBlendType
from ..core.validation_utils import ValidationUtils
from ..dispatcher import register_handler

logger = get_logger()


@register_handler(
    "manage_sequencer",
    actions=[a.value for a in SequencerAction],
    category="sequencer",
    schema={
        "type": "object",
        "title": "Video Sequencer (VSE) Manager",
        "description": (
            "STANDARD — Video Sequence Editor (VSE) manager.\n"
            "ACTIONS: ADD_MOVIE, ADD_SOUND, ADD_IMAGE, ADD_IMAGE_STRIP, CUT, DELETE_STRIP, "
            "SET_VOLUME, LIST_STRIPS, GET_STRIP_INFO, SET_STRIP_RANGE, SET_STRIP_OPACITY, "
            "SET_STRIP_BLEND, MUTE_STRIP, UNMUTE_STRIP, CREATE_META_STRIP, RENDER_PREVIEW\n\n"
            "NOTE: VSE timeline is separate from the 3D scene timeline. "
            "Use channel param (1-32) to place strips on different tracks. "
            "Use RENDER_PREVIEW to render a video clip from the VSE timeline."
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(SequencerAction, "Operation to perform"),
            "filepath": {"type": "string", "description": "Path to media file"},
            "channel": {
                "type": "integer",
                "default": 1,
                "description": "Video/Audio channel (1-32)",
            },
            "frame_start": {"type": "integer", "default": 1, "description": "Start frame"},
            "frame_end": {"type": "integer", "description": "End frame"},
            "strip_name": {"type": "string", "description": "Name of existing strip"},
            "volume": {"type": "number", "default": 1.0, "minimum": 0, "maximum": 10},
            "opacity": {"type": "number", "default": 1.0, "minimum": 0, "maximum": 1},
            "blend_type": ValidationUtils.generate_enum_schema(
                SequencerBlendType, "Blend mode for strips"
            ),
            "cut_frame": {"type": "integer", "description": "Frame number to cut at"},
            "mute": {"type": "boolean", "description": "Mute/unmute strip"},
            "strip_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of strip names for meta strip creation",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_sequencer(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Video Sequence Editor Tools with Blender 5.x API compatibility.

    FIXED: Uses safe sequence_editor access and proper sequences iteration
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=action or "UNKNOWN",
            error_code=ErrorProtocol.NO_CONTEXT,
            message="Blender Python API not available",
        )

    validation_error = ValidationUtils.validate_enum(action, SequencerAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_sequencer", action=action
        )

    # Normalize parameters
    params = ParameterNormalizer.normalize(params, manage_sequencer._handler_schema)

    # Blender 5.0 separates the VSE scene from the active scene via sequencer_scene.
    # Fall back to bpy.context.scene for older builds.
    scene = getattr(bpy.context, "sequencer_scene", None) or bpy.context.scene

    # Initialize sequence editor
    seq_editor_init = _ensure_sequencer_editor(scene)
    if not seq_editor_init["success"]:
        return seq_editor_init["error"]  # type: ignore[no-any-return]

    seq_editor = seq_editor_init["editor"]

    # Route to handler
    try:
        if action == SequencerAction.ADD_MOVIE.value:
            return _handle_add_movie(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.ADD_SOUND.value:
            return _handle_add_sound(seq_editor, params)  # type: ignore[no-any-return]
        elif action in [SequencerAction.ADD_IMAGE.value, SequencerAction.ADD_IMAGE_STRIP.value]:
            return _handle_add_image(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.CUT.value:
            return _handle_cut(seq_editor, scene, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.DELETE_STRIP.value:
            return _handle_delete_strip(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.SET_VOLUME.value:
            return _handle_set_volume(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.LIST_STRIPS.value:
            return _handle_list_strips(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.GET_STRIP_INFO.value:
            return _handle_get_strip_info(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.SET_STRIP_RANGE.value:
            return _handle_set_strip_range(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.SET_STRIP_OPACITY.value:
            return _handle_set_strip_opacity(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.SET_STRIP_BLEND.value:
            return _handle_set_strip_blend(seq_editor, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.MUTE_STRIP.value:
            return _handle_mute_strip(seq_editor, params, mute=True)  # type: ignore[no-any-return]
        elif action == SequencerAction.UNMUTE_STRIP.value:
            return _handle_mute_strip(seq_editor, params, mute=False)  # type: ignore[no-any-return]
        elif action == SequencerAction.CREATE_META_STRIP.value:
            return _handle_create_meta_strip(seq_editor, scene, params)  # type: ignore[no-any-return]
        elif action == SequencerAction.RENDER_PREVIEW.value:
            return _handle_render_preview(scene, params)  # type: ignore[no-any-return]
        else:
            return ResponseBuilder.error(
                handler="manage_sequencer",
                action=action,
                error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_sequencer.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=action,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=str(e),
        )


def _ensure_sequencer_editor(scene) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    """
    Ensure sequence editor exists with Blender 5.x compatibility.

    FIXED: Properly initializes sequence_editor for all Blender versions
    """
    try:
        # Check if sequence editor exists
        if not scene.sequence_editor:
            # Create it - in Blender 5.x this may require different approach
            try:
                # Method 1: Direct assignment
                scene.sequence_editor_create()
            except AttributeError:
                try:
                    # Method 2: Toggle via context

                    # Try to switch to sequencer area
                    for area in bpy.context.screen.areas:
                        if area.type == "SEQUENCE_EDITOR":
                            break
                    else:
                        # No sequencer area, try operator
                        safe_ops.sequencer.editor_toggle()

                    # Now try to create
                    if not scene.sequence_editor:
                        return {
                            "success": False,
                            "error": ResponseBuilder.error(
                                handler="manage_sequencer",
                                action="INIT",
                                error_code=ErrorProtocol.INITIALIZATION_ERROR,
                                message="Could not initialize sequence editor",
                            ),
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "error": ResponseBuilder.error(
                            handler="manage_sequencer",
                            action="INIT",
                            error_code=ErrorProtocol.INITIALIZATION_ERROR,
                            message=f"Failed to create sequence editor: {str(e)}",
                        ),
                    }

        if not scene.sequence_editor:
            return {
                "success": False,
                "error": ResponseBuilder.error(
                    handler="manage_sequencer",
                    action="INIT",
                    error_code=ErrorProtocol.INITIALIZATION_ERROR,
                    message="Sequence editor initialization failed",
                ),
            }

        return {"success": True, "editor": scene.sequence_editor}

    except Exception as e:
        return {
            "success": False,
            "error": ResponseBuilder.error(
                handler="manage_sequencer",
                action="INIT",
                error_code=ErrorProtocol.EXECUTION_ERROR,
                message=f"Error ensuring sequence editor: {str(e)}",
            ),
        }


def _get_sequences(seq_editor):  # type: ignore[no-untyped-def]
    """
    Get sequences collection with Blender 5.x compatibility.

    Blender 5.0 renamed SequenceEditor.sequences → strips (bpy.types.StripsTopLevel).
    Check 'strips' first so Blender 5.0 gets the correct collection; fall back to
    'sequences' for older builds, then 'sequences_all', then direct iteration.
    """
    if not seq_editor:
        return []

    # Blender 5.0+: 'strips' is the canonical name
    if hasattr(seq_editor, "strips"):
        return seq_editor.strips
    # Blender 4.x and older
    if hasattr(seq_editor, "sequences"):
        return seq_editor.sequences
    if hasattr(seq_editor, "sequences_all"):
        return seq_editor.sequences_all
    try:
        return list(seq_editor)
    except Exception:
        return []


def _get_strip(seq_editor, name: str):  # type: ignore[no-untyped-def]
    """Get strip by name with safe access."""
    sequences = _get_sequences(seq_editor)
    if not sequences:
        return None

    try:
        return sequences.get(name)
    except:
        # Fallback: manual search
        for strip in sequences:
            if strip.name == name:
                return strip
        return None


def _handle_add_movie(seq_editor: Any, params: dict[str, Any]) -> dict[str, Any]:
    """Handle ADD_MOVIE action with media-kind validation."""
    from ..utils.path import get_safe_path

    SUPPORTED_VIDEO_FORMATS = {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".mxf",
        ".m4v",
        ".mpg",
        ".mpeg",
        ".wmv",
        ".ogv",
        ".ts",
        ".mts",
        ".flv",
    }

    SUPPORTED_IMAGE_FORMATS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".exr",
        ".tiff",
        ".bmp",
        ".tga",
        ".hdr",
        ".dpx",
    }

    path = params.get("filepath")
    if not path:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_MOVIE.value,
            error_code="MISSING_PARAMETER",
            message="filepath is required",
        )

    path = get_safe_path(path)

    if not os.path.exists(path):
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_MOVIE.value,
            error_code="FILE_NOT_FOUND",
            message=(
                f"Dosya bulunamadı: '{path}'. "
                f"FBX/OBJ gibi 3D model dosyaları video olarak eklenemez. "
                f"3D model için manage_export kullanın."
            ),
        )

    ext = os.path.splitext(path)[1].lower()

    if ext in SUPPORTED_IMAGE_FORMATS:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_MOVIE.value,
            error_code="WRONG_ACTION",
            message=(
                f"'{ext}' bir görüntü formatı. "
                f"Lütfen ADD_IMAGE veya ADD_IMAGE_STRIP action'ını kullanın."
            ),
        )

    if ext not in SUPPORTED_VIDEO_FORMATS:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_MOVIE.value,
            error_code="UNSUPPORTED_FORMAT",
            message=(
                f"'{ext}' desteklenmiyor. "
                f"Desteklenen video formatları: {sorted(SUPPORTED_VIDEO_FORMATS)}"
            ),
        )

    chan = max(1, min(32, params.get("channel", 1)))
    start = params.get("frame_start", 1)

    def add_operation():  # type: ignore[no-untyped-def]
        sequences = _get_sequences(seq_editor)

        # Try API method first
        if hasattr(sequences, "new_movie"):
            strip = sequences.new_movie(
                name=os.path.basename(path), filepath=path, channel=chan, frame_start=start
            )
        else:
            # Fallback: operator
            safe_ops.sequencer.movie_strip_add(filepath=path, frame_start=start, channel=chan)
            # Get last added
            sequences = _get_sequences(seq_editor)
            strip = sequences[-1] if sequences else None

        if not strip:
            raise RuntimeError("Failed to add movie strip")

        return {
            "strip_name": strip.name,
            "type": strip.type,
            "channel": strip.channel,
            "frame_start": strip.frame_start,
            "frame_duration": (
                strip.frame_final_duration
                if hasattr(strip, "frame_final_duration")
                else strip.frame_duration
            ),
            "filepath": path,
        }

    try:
        result = add_operation()
        return ResponseBuilder.success(
            handler="manage_sequencer", action=SequencerAction.ADD_MOVIE.value, data=result
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_MOVIE.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to add movie: {str(e)}",
        )


def _handle_add_sound(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle ADD_SOUND action."""
    from ..utils.path import get_safe_path

    path = params.get("filepath")
    if not path:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_SOUND.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="filepath is required",
        )

    path = get_safe_path(path)
    chan = max(1, min(32, params.get("channel", 2)))
    start = params.get("frame_start", 1)

    def add_operation():  # type: ignore[no-untyped-def]
        sequences = _get_sequences(seq_editor)

        if hasattr(sequences, "new_sound"):
            strip = sequences.new_sound(
                name=os.path.basename(path), filepath=path, channel=chan, frame_start=start
            )
        else:
            safe_ops.sequencer.sound_strip_add(filepath=path, frame_start=start, channel=chan)
            sequences = _get_sequences(seq_editor)
            strip = sequences[-1] if sequences else None

        if not strip:
            raise RuntimeError("Failed to add sound strip")

        return {
            "strip_name": strip.name,
            "type": strip.type,
            "channel": strip.channel,
            "volume": strip.volume if hasattr(strip, "volume") else 1.0,
        }

    try:
        result = add_operation()
        return ResponseBuilder.success(
            handler="manage_sequencer", action=SequencerAction.ADD_SOUND.value, data=result
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_SOUND.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to add sound: {str(e)}",
        )


def _handle_add_image(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle ADD_IMAGE/ADD_IMAGE_STRIP action."""
    from ..utils.path import get_safe_path

    path = params.get("filepath")
    if not path:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_IMAGE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="filepath is required",
        )

    path = get_safe_path(path)
    chan = max(1, min(32, params.get("channel", 1)))
    start = params.get("frame_start", 1)

    # Normalize to forward slashes for Blender's file API
    norm_path = path.replace("\\", "/")

    def add_operation():  # type: ignore[no-untyped-def]
        sequences = _get_sequences(seq_editor)
        strip = None

        # --- Data API path (preferred — no context dependency) ---
        if hasattr(sequences, "new_image"):
            # Blender 5.0 API: new_image(name, filepath, channel, frame_start, fit_method='ADJUST')
            # Blender 4.x API: new_image(name, filepath, channel, frame_start, frame_end=N)
            # Try Blender 5.0 signature first (with fit_method), then 4.x fallbacks.
            for _kwargs in [
                {"fit_method": "ADJUST"},  # Blender 5.0+
                {},  # Neutral (no extra kwargs)
            ]:
                try:
                    strip = sequences.new_image(
                        name=os.path.basename(norm_path),
                        filepath=norm_path,
                        channel=chan,
                        frame_start=start,
                        **_kwargs,
                    )
                    if strip:
                        break
                except TypeError:
                    strip = None
                except Exception as _api_err:
                    logger.warning(f"sequences.new_image({_kwargs}) failed: {_api_err}")
                    strip = None

        if strip:
            # Set duration
            desired_end = params.get("frame_end", start + 24)
            try:
                strip.frame_final_end = desired_end
            except Exception:
                pass
            return {"strip_name": strip.name, "type": strip.type, "filepath": norm_path}

        # --- Operator fallback (requires SEQUENCE_EDITOR area in UI) ---
        logger.warning("new_image() data API failed — trying operator fallback")
        directory = os.path.dirname(os.path.abspath(norm_path)).replace("\\", "/")
        if not directory.endswith("/"):
            directory += "/"
        filename = os.path.basename(norm_path)

        op_result = None
        try:
            with ContextManagerV3.temp_override(area_type="SEQUENCE_EDITOR"):
                # Blender 5.0 (PR#143974): all strip-add operators default to
                # move_strips=True (modal, waits for mouse). Scripts must pass
                # move_strips=False to prevent the operator entering modal mode
                # and returning CANCELLED (or blocking indefinitely).
                op_result = safe_ops.sequencer.image_strip_add(
                    directory=directory,
                    files=[{"name": filename}],
                    frame_start=start,
                    channel=chan,
                    replace_sel=True,
                    move_strips=False,
                )
        except Exception as _op_err:
            logger.error(f"sequencer.image_strip_add operator failed: {_op_err}")

        sequences = _get_sequences(seq_editor)
        strip = list(sequences)[-1] if sequences else None

        if not strip:
            raise RuntimeError(
                f"Failed to add image strip '{filename}'. "
                "Both data API (new_image) and operator paths failed. "
                "Ensure the file exists and Blender has a SEQUENCE_EDITOR area open."
            )

        # Operator path: set duration if provided
        if params.get("frame_end"):
            try:
                strip.frame_final_end = params["frame_end"]
            except Exception:
                pass

        return {"strip_name": strip.name, "type": strip.type, "filepath": norm_path}

    try:
        result = add_operation()
        return ResponseBuilder.success(
            handler="manage_sequencer", action=SequencerAction.ADD_IMAGE.value, data=result
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.ADD_IMAGE.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to add image: {str(e)}",
        )


def _handle_cut(seq_editor, scene, params):  # type: ignore[no-untyped-def]
    """Handle CUT action."""
    strip_name = params.get("strip_name")
    cut_frame = params.get("cut_frame")

    if not strip_name or cut_frame is None:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.CUT.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_name and cut_frame are required",
        )

    strip = _get_strip(seq_editor, strip_name)
    if not strip:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.CUT.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Strip not found: {strip_name}",
        )

    # Ensure cut is within strip range
    frame_end = (
        strip.frame_final_end
        if hasattr(strip, "frame_final_end")
        else strip.frame_start + strip.frame_duration
    )
    if cut_frame <= strip.frame_start or cut_frame >= frame_end:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.CUT.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Cut frame {cut_frame} must be within strip range ({strip.frame_start}-{frame_end})",
        )

    try:
        # Select the strip and cut
        safe_ops.sequencer.select_all(action="DESELECT")
        strip.select = True
        scene.frame_current = int(cut_frame)
        safe_ops.sequencer.split(frame=int(cut_frame), type="SOFT", side="BOTH")

        return ResponseBuilder.success(
            handler="manage_sequencer",
            action=SequencerAction.CUT.value,
            data={"message": f"Cut strip at frame {cut_frame}", "original_strip": strip_name},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.CUT.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to cut: {str(e)}",
        )


def _handle_delete_strip(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle DELETE_STRIP action."""
    name = params.get("strip_name")
    if not name:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.DELETE_STRIP.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_name is required",
        )

    strip = _get_strip(seq_editor, name)
    if not strip:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.DELETE_STRIP.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Strip not found: {name}",
        )

    try:
        sequences = _get_sequences(seq_editor)
        if hasattr(sequences, "remove"):
            sequences.remove(strip)
        else:
            # Fallback: select and delete
            safe_ops.sequencer.select_all(action="DESELECT")
            strip.select = True
            safe_ops.sequencer.delete()

        return ResponseBuilder.success(
            handler="manage_sequencer",
            action=SequencerAction.DELETE_STRIP.value,
            data={"deleted": name},
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.DELETE_STRIP.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to delete: {str(e)}",
        )


def _handle_set_volume(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle SET_VOLUME action."""
    name = params.get("strip_name")
    vol = params.get("volume", 1.0)

    if not name:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_VOLUME.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_name is required",
        )

    strip = _get_strip(seq_editor, name)
    if not strip:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_VOLUME.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Strip not found: {name}",
        )

    if hasattr(strip, "volume"):
        strip.volume = vol
        return ResponseBuilder.success(
            handler="manage_sequencer",
            action=SequencerAction.SET_VOLUME.value,
            data={"strip": name, "volume": strip.volume},
        )
    else:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_VOLUME.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Strip '{name}' does not have volume control",
        )


def _handle_list_strips(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle LIST_STRIPS action."""
    sequences = _get_sequences(seq_editor)
    strips = []

    for strip in sequences:
        strip_info = {
            "name": strip.name,
            "type": strip.type,
            "channel": strip.channel,
            "frame_start": strip.frame_start,
            "frame_end": (
                strip.frame_final_end
                if hasattr(strip, "frame_final_end")
                else strip.frame_start + strip.frame_duration
            ),
            "duration": (
                strip.frame_final_duration
                if hasattr(strip, "frame_final_duration")
                else strip.frame_duration
            ),
            "mute": strip.mute if hasattr(strip, "mute") else False,
        }

        if hasattr(strip, "volume"):
            strip_info["volume"] = strip.volume
        if hasattr(strip, "blend_type"):
            strip_info["blend_type"] = strip.blend_type
        if hasattr(strip, "opacity"):
            strip_info["opacity"] = strip.opacity

        strips.append(strip_info)

    return ResponseBuilder.success(
        handler="manage_sequencer",
        action=SequencerAction.LIST_STRIPS.value,
        data={"count": len(strips), "strips": strips},
    )


def _handle_get_strip_info(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle GET_STRIP_INFO action."""
    name = params.get("strip_name")
    if not name:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.GET_STRIP_INFO.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_name is required",
        )

    strip = _get_strip(seq_editor, name)
    if not strip:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.GET_STRIP_INFO.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Strip not found: {name}",
        )

    info = {
        "name": strip.name,
        "type": strip.type,
        "channel": strip.channel,
        "frame_start": strip.frame_start,
        "frame_end": (
            strip.frame_final_end
            if hasattr(strip, "frame_final_end")
            else strip.frame_start + strip.frame_duration
        ),
        "frame_duration": (
            strip.frame_final_duration
            if hasattr(strip, "frame_final_duration")
            else strip.frame_duration
        ),
        "mute": strip.mute if hasattr(strip, "mute") else False,
        "select": strip.select if hasattr(strip, "select") else False,
    }

    if hasattr(strip, "filepath"):
        info["filepath"] = strip.filepath
    if hasattr(strip, "directory"):
        info["directory"] = strip.directory
    if hasattr(strip, "volume"):
        info["volume"] = strip.volume
    if hasattr(strip, "blend_type"):
        info["blend_type"] = strip.blend_type
    if hasattr(strip, "opacity"):
        info["opacity"] = strip.opacity

    return ResponseBuilder.success(
        handler="manage_sequencer",
        action=SequencerAction.GET_STRIP_INFO.value,
        data={"strip": info},
    )


def _handle_set_strip_range(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle SET_STRIP_RANGE action."""
    name = params.get("strip_name")
    if not name:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_RANGE.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_name is required",
        )

    strip = _get_strip(seq_editor, name)
    if not strip:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_RANGE.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Strip not found: {name}",
        )

    if params.get("frame_start") is not None:
        strip.frame_start = int(params["frame_start"])
    if params.get("frame_end") is not None:
        strip.frame_final_end = int(params["frame_end"])

    return ResponseBuilder.success(
        handler="manage_sequencer",
        action=SequencerAction.SET_STRIP_RANGE.value,
        data={
            "strip": name,
            "frame_start": strip.frame_start,
            "frame_end": (
                strip.frame_final_end
                if hasattr(strip, "frame_final_end")
                else strip.frame_start + strip.frame_duration
            ),
        },
    )


def _handle_set_strip_opacity(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle SET_STRIP_OPACITY action."""
    name = params.get("strip_name")
    opacity = params.get("opacity", 1.0)

    if not name:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_OPACITY.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_name is required",
        )

    strip = _get_strip(seq_editor, name)
    if not strip:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_OPACITY.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Strip not found: {name}",
        )

    if hasattr(strip, "opacity"):
        strip.opacity = opacity
        return ResponseBuilder.success(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_OPACITY.value,
            data={"strip": name, "opacity": strip.opacity},
        )
    elif hasattr(strip, "blend_alpha"):
        strip.blend_alpha = opacity
        return ResponseBuilder.success(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_OPACITY.value,
            data={"strip": name, "blend_alpha": strip.blend_alpha},
        )
    else:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_OPACITY.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Strip '{name}' does not support opacity",
        )


def _handle_set_strip_blend(seq_editor, params):  # type: ignore[no-untyped-def]
    """Handle SET_STRIP_BLEND action."""
    name = params.get("strip_name")
    blend = params.get("blend_type")

    if not name or not blend:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_BLEND.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_name and blend_type are required",
        )

    blend_validation = ValidationUtils.validate_enum(blend, SequencerBlendType, "blend_type")
    if blend_validation:
        return ResponseBuilder.from_error(
            blend_validation,
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_BLEND.value,
        )

    strip = _get_strip(seq_editor, name)
    if not strip:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_BLEND.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Strip not found: {name}",
        )

    if hasattr(strip, "blend_type"):
        try:
            strip.blend_type = blend
            return ResponseBuilder.success(
                handler="manage_sequencer",
                action=SequencerAction.SET_STRIP_BLEND.value,
                data={"strip": name, "blend_type": strip.blend_type},
            )
        except Exception:
            valid_types = [e.value for e in SequencerBlendType]
            return ResponseBuilder.error(
                handler="manage_sequencer",
                action=SequencerAction.SET_STRIP_BLEND.value,
                error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
                message=f"Invalid blend type: {blend}",
                details={"valid_types": valid_types},
            )
    else:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.SET_STRIP_BLEND.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Strip '{name}' does not support blend modes",
        )


def _handle_mute_strip(seq_editor, params, mute=True):  # type: ignore[no-untyped-def]
    """Handle MUTE_STRIP/UNMUTE_STRIP actions."""
    name = params.get("strip_name")
    action_name = SequencerAction.MUTE_STRIP.value if mute else SequencerAction.UNMUTE_STRIP.value

    if not name:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=action_name,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_name is required",
        )

    strip = _get_strip(seq_editor, name)
    if not strip:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=action_name,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message=f"Strip not found: {name}",
        )

    if hasattr(strip, "mute"):
        strip.mute = mute
        return ResponseBuilder.success(
            handler="manage_sequencer", action=action_name, data={"strip": name, "mute": mute}
        )
    else:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=action_name,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Strip '{name}' does not support mute",
        )


def _handle_create_meta_strip(seq_editor, scene, params):  # type: ignore[no-untyped-def]
    """Handle CREATE_META_STRIP action."""
    strip_names = params.get("strip_names", [])
    if not strip_names:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.CREATE_META_STRIP.value,
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="strip_names list is required",
        )

    # Deselect all
    safe_ops.sequencer.select_all(action="DESELECT")

    # Select specified strips
    selected = []
    for name in strip_names:
        strip = _get_strip(seq_editor, name)
        if strip and hasattr(strip, "select"):
            strip.select = True
            selected.append(name)

    if not selected:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.CREATE_META_STRIP.value,
            error_code=ErrorProtocol.OBJECT_NOT_FOUND,
            message="No valid strips found to create meta strip",
        )

    try:
        safe_ops.sequencer.meta_make()

        # Get the newly created meta strip
        meta_strip = None
        for strip in _get_sequences(seq_editor):
            if hasattr(strip, "select") and strip.select and strip.type == "META":
                meta_strip = strip
                break

        return ResponseBuilder.success(
            handler="manage_sequencer",
            action=SequencerAction.CREATE_META_STRIP.value,
            data={
                "message": f"Created meta strip from {len(selected)} strips",
                "selected_strips": selected,
                "meta_strip": meta_strip.name if meta_strip else "Unknown",
            },
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.CREATE_META_STRIP.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Failed to create meta strip: {str(e)}",
        )


def _handle_render_preview(scene, params):  # type: ignore[no-untyped-def]
    """Handle RENDER_PREVIEW action."""
    frame_start = params.get("frame_start", scene.frame_start)
    frame_end = params.get("frame_end", frame_start + 24)
    resolution_percentage = params.get("resolution_percentage", 50)
    filepath = params.get("filepath", "//preview_####")

    # Store original settings
    orig_resolution = scene.render.resolution_percentage
    orig_start = scene.frame_start
    orig_end = scene.frame_end
    orig_filepath = scene.render.filepath

    try:
        # Set preview settings
        scene.render.resolution_percentage = resolution_percentage
        scene.frame_start = int(frame_start)
        scene.frame_end = int(frame_end)
        scene.render.filepath = filepath

        # Render animation
        def render_op():  # type: ignore[no-untyped-def]
            safe_ops.render.render(animation=True)
            return True

        execute_on_main_thread(render_op, timeout=600.0)  # 10 min for preview

        return ResponseBuilder.success(
            handler="manage_sequencer",
            action=SequencerAction.RENDER_PREVIEW.value,
            data={
                "message": f"Rendered preview frames {frame_start}-{frame_end}",
                "filepath": filepath,
                "resolution_percentage": resolution_percentage,
            },
        )
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_sequencer",
            action=SequencerAction.RENDER_PREVIEW.value,
            error_code=ErrorProtocol.EXECUTION_ERROR,
            message=f"Preview render failed: {str(e)}",
        )
    finally:
        # Restore original settings
        scene.render.resolution_percentage = orig_resolution
        scene.frame_start = orig_start
        scene.frame_end = orig_end
        scene.render.filepath = orig_filepath
