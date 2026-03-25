"""
Manage Bake - V1.0.0 Refactored

Safe, thread-aware texture baking operations with:
- Thread safety (main thread execution for bake ops)
- Context validation via ContextManagerV3
- Crash prevention for bake operations
- Structured error handling with ErrorProtocol
- Blender 5.0+ compatibility

High Mode Philosophy: Maximum power, maximum safety.
"""

from ..core.execution_engine import safe_ops
import contextlib

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.thread_safety import execute_on_main_thread, ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3, SafeModeContext
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.versioning import BlenderCompatibility
from ..dispatcher import register_handler
from ..core.enums import BakeAction
from ..core.constants import BakingDefaults
from typing import Any, Tuple, Optional

logger = get_logger()


@register_handler(
    "manage_bake",
    schema={
        "type": "object",
        "title": "Bake Manager",
        "description": (
            "STANDARD — Texture baking manager.\n"
            "ACTIONS: BAKE, BAKE_NORMAL, BAKE_AO, BAKE_DIFFUSE, BAKE_GLOSSY, BAKE_SHADOW, "
            "BAKE_EMISSION, BAKE_LIGHTMAP, BAKE_DISPLACEMENT, BAKE_COMBINED, "
            "SETUP_MATERIALS, CREATE_IMAGE, CONFIGURE, SETUP_BAKE_SCENE, "
            "PREPARE_LOW_POLY, CREATE_BAKE_MATERIAL\n\n"
            "PREREQUISITE: Object must have a material with an Image Texture node selected (as target). "
            "Object must have a UV map. High-poly to low-poly bake requires both objects in scene.\n"
            "TIP: Use BAKE_COMBINED for full PBR bake. Set margin (default 16px) to avoid seam bleeding. "
            "Call SETUP_BAKE_SCENE first for automatic scene preparation."
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": [e.value for e in BakeAction],
                "description": "Bake operation to perform",
            },
            "high_poly": {
                "type": "string",
                "description": "High poly object name (for normal/displacement)",
            },
            "low_poly": {"type": "string", "description": "Low poly object name"},
            "cage": {"type": "string", "description": "Cage object name (optional)"},
            "cage_extrusion": {
                "type": "number",
                "default": BakingDefaults.DEFAULT_CAGE_EXTRUSION,
                "description": "Cage extrusion distance",
            },
            "output_image": {"type": "string", "description": "Output image name"},
            "output_path": {"type": "string", "description": "Export path for baked texture"},
            "resolution": {
                "type": "integer",
                "default": BakingDefaults.DEFAULT_RESOLUTION,
                "description": "Texture resolution",
            },
            "samples": {
                "type": "integer",
                "default": BakingDefaults.DEFAULT_SAMPLES,
                "description": "Bake samples",
            },
            "margin": {
                "type": "integer",
                "default": BakingDefaults.DEFAULT_MARGIN,
                "description": "Bake margin in pixels",
            },
            "use_cage": {"type": "boolean", "default": False},
            "normal_space": {
                "type": "string",
                "enum": ["TANGENT", "OBJECT", "WORLD"],
                "default": "TANGENT",
            },
            "normal_r": {"type": "string", "enum": ["POS_X", "NEG_X"], "default": "POS_X"},
            "normal_g": {"type": "string", "enum": ["POS_Y", "NEG_Y"], "default": "POS_Y"},
            "normal_b": {"type": "string", "enum": ["POS_Z", "NEG_Z"], "default": "POS_Z"},
            "ao_distance": {
                "type": "number",
                "default": BakingDefaults.DEFAULT_AO_DISTANCE,
                "description": "AO ray distance",
            },
            "ao_inside": {"type": "boolean", "default": False, "description": "AO inside mode"},
            "pass_filter": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Pass filter for combined bake (e.g., ['DIFFUSE', 'GLOSSY'])",
            },
        },
        "required": ["action"],
    },
    actions=[e.value for e in BakeAction],
    category="baking",
)
@ensure_main_thread
def manage_bake(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    AAA baking pipeline for texture generation with Blender 5.0+ compatibility.

    Key improvements:
    - Thread safety for all bake operations
    - Proper context overrides for Blender 5.0+
    - Automatic type coercion for parameters
    - Better error messages with ErrorProtocol
    - Validation before bake operations

    CRITICAL: All bpy.ops.bake calls execute on main thread.
    """
    if not action:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="UNKNOWN",
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    # Coerce integer parameters
    params["resolution"] = _coerce_int(
        params.get("resolution", BakingDefaults.DEFAULT_RESOLUTION),
        default=BakingDefaults.DEFAULT_RESOLUTION,
        min_val=BakingDefaults.MIN_RESOLUTION,
        max_val=BakingDefaults.MAX_RESOLUTION,
    )
    params["samples"] = _coerce_int(
        params.get("samples", BakingDefaults.DEFAULT_SAMPLES),
        default=BakingDefaults.DEFAULT_SAMPLES,
        min_val=BakingDefaults.MIN_SAMPLES,
        max_val=BakingDefaults.MAX_SAMPLES,
    )
    params["margin"] = _coerce_int(
        params.get("margin", BakingDefaults.DEFAULT_MARGIN),
        default=BakingDefaults.DEFAULT_MARGIN,
        min_val=BakingDefaults.MIN_MARGIN,
        max_val=BakingDefaults.MAX_MARGIN,
    )

    try:
        if action == BakeAction.BAKE:
            return _handle_bake(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.CREATE_IMAGE:
            return _handle_create_image(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.SETUP_MATERIALS:
            return _handle_setup_materials(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.CONFIGURE:
            return _handle_configure(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.SETUP_BAKE_SCENE:
            return _handle_setup_bake_scene(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.PREPARE_LOW_POLY:
            return _handle_prepare_low_poly(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.CREATE_BAKE_MATERIAL:
            return _handle_create_bake_material(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_NORMAL:
            return _handle_bake_normal(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_AO:
            return _handle_bake_ao(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_LIGHTMAP:
            return _handle_bake_lightmap(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_COMBINED:
            return _handle_bake_combined(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_DIFFUSE:
            return _handle_bake_diffuse(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_GLOSSY:
            return _handle_bake_glossy(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_SHADOW:
            return _handle_bake_shadow(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_DISPLACEMENT:
            return _handle_bake_displacement(**params)  # type: ignore[no-any-return]
        elif action == BakeAction.BAKE_EMISSION:
            return _handle_bake_emission(**params)  # type: ignore[no-any-return]
        else:
            return ResponseBuilder.error(
                handler="manage_bake",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_bake.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_bake", action=action, error_code="EXECUTION_ERROR", message=str(e)
        )


# =============================================================================
# PARAMETER VALIDATION HELPERS
# =============================================================================


def _coerce_int(value, default=0, min_val=None, max_val=None):  # type: ignore[no-untyped-def]
    """Coerce value to integer with bounds."""
    try:
        result = int(float(value))
        if min_val is not None:
            result = max(result, min_val)
        if max_val is not None:
            result = min(result, max_val)
        return result
    except (TypeError, ValueError):
        return default


def _ensure_cycles(scene):  # type: ignore[no-untyped-def]
    """Helper to ensure Cycles render engine."""
    if scene.render.engine != "CYCLES":
        scene.render.engine = "CYCLES"
        return True
    return False


def _get_or_create_image(name, resolution, alpha=False):  # type: ignore[no-untyped-def]
    """Helper to get or create image."""
    if name in bpy.data.images:
        img = bpy.data.images[name]
        # Resize if needed
        if img.size[0] != resolution or img.size[1] != resolution:
            img.scale(resolution, resolution)
        return img
    else:
        return bpy.data.images.new(
            name=name, width=resolution, height=resolution, alpha=alpha, float_buffer=True
        )


def _ensure_image_node_selected(obj):  # type: ignore[no-untyped-def]
    """Ensure an image texture node is selected for baking."""
    if not obj or not obj.data.materials:
        return False

    for mat in obj.data.materials:
        if mat and mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    node.select = True
                    mat.node_tree.nodes.active = node
                    return True
    return False


@contextlib.contextmanager
def _prepare_bake_visibility(objects):  # type: ignore[no-untyped-def]
    """Ensure objects are visible for baking and restore state afterwards."""
    restore_state = {}

    # 1. Store state and force visibility
    for obj in objects:
        if not obj:
            continue
        restore_state[obj] = {"hide_viewport": obj.hide_viewport, "hide_render": obj.hide_render}
        obj.hide_viewport = False
        obj.hide_render = False

    try:
        yield
    finally:
        # 2. Restore state
        for obj, state in restore_state.items():
            try:
                obj.hide_viewport = state["hide_viewport"]
                obj.hide_render = state["hide_render"]
            except ReferenceError:
                pass


def _execute_bake_with_context(scene, bake_type, **kwargs):  # type: ignore[no-untyped-def]
    """Execute bake with proper context override for Blender 5.0+ on main thread."""

    # Extract object references for visibility handling from kwargs or context
    # We mainly need to ensure active and selected objects are visible
    target_objects = list(
        set(
            [o for o in bpy.context.selected_objects]
            + ([bpy.context.active_object] if bpy.context.active_object else [])
        )
    )

    # Bug 26 Fix: Dynamic timeout heuristic for high-poly baking operations
    total_verts = sum(
        len(o.data.vertices)
        for o in target_objects
        if o and o.type == "MESH" and hasattr(o, "data") and hasattr(o.data, "vertices")
    )
    # Base timeout 600s + 120s per 100k vertices
    dynamic_timeout = 600.0 + (total_verts / 100000.0) * 120.0

    def do_bake() -> Tuple[bool, Optional[str]]:
        try:
            # Use ContextManagerV3 for reliable context preparation (1.0.0 Fix)
            # RCA: Bake requires properties/image editor context and valid objects
            with ContextManagerV3.temp_override(area_type="IMAGE_EDITOR", scene=scene):
                with _prepare_bake_visibility(target_objects):
                    # Force EXEC_DEFAULT for headless operation
                    safe_ops.object.bake(_exec_context="EXEC_DEFAULT", type=bake_type, **kwargs)
            return True, None
        except Exception as e:
            return False, str(e)

    return execute_on_main_thread(do_bake, timeout=dynamic_timeout)


# =============================================================================
# SETUP ACTIONS
# =============================================================================


def _handle_setup_bake_scene(**params):  # type: ignore[no-untyped-def]
    """Setup scene for baking."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="SETUP_BAKE_SCENE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="SETUP_BAKE_SCENE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    try:
        was_changed = _ensure_cycles(scene)

        # Configure bake settings
        scene.cycles.bake_type = "DIFFUSE"
        scene.render.bake.margin = params.get("margin", BakingDefaults.DEFAULT_MARGIN)
        scene.cycles.samples = params.get("samples", BakingDefaults.DEFAULT_SAMPLES)

        # Disable caustics for cleaner bakes
        scene.cycles.caustics_reflective = False
        scene.cycles.caustics_refractive = False

        return ResponseBuilder.success(
            handler="manage_bake",
            action="SETUP_BAKE_SCENE",
            data={
                "message": "Scene configured for baking",
                "engine_changed": was_changed,
                "samples": scene.cycles.samples,
                "blender_50_plus": BlenderCompatibility.is_blender5(),
            },
        )
    except Exception as e:
        logger.error(f"SETUP_BAKE_SCENE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_bake",
            action="SETUP_BAKE_SCENE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_prepare_low_poly(**params):  # type: ignore[no-untyped-def]
    """Prepare low poly object for baking (add UVs, setup material)."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="PREPARE_LOW_POLY",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("low_poly")
    if not obj_name:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="PREPARE_LOW_POLY",
            error_code="MISSING_PARAMETER",
            message="low_poly object name is required",
        )

    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="PREPARE_LOW_POLY",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{obj_name}' not found",
        )

    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_bake",
            action="PREPARE_LOW_POLY",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Expected MESH, got {obj.type}",
        )

    def prepare_uvs():  # type: ignore[no-untyped-def]
        # Ensure UV map
        if not obj.data.uv_layers:  # type: ignore
            obj.data.uv_layers.new(name="UVMap")  # type: ignore

        # Smart UV unwrap if no UVs or forced
        if params.get("unwrap", True):
            ContextManagerV3.set_active_object(obj)

            # Enter edit mode safely
            with SafeModeContext("EDIT", obj) as success:
                if not success:
                    return ResponseBuilder.error(
                        handler="manage_bake",
                        action="PREPARE_LOW_POLY",
                        error_code="MODE_SWITCH_FAILED",
                        message="Cannot enter edit mode",
                    )

                with ContextManagerV3.temp_override(
                    area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                ):
                    safe_ops.mesh.select_all(action="SELECT")
                    safe_ops.uv.smart_project(angle_limit=66)

        return ResponseBuilder.success(
            handler="manage_bake",
            action="PREPARE_LOW_POLY",
            data={
                "object": obj_name,
                "uv_layers": [uv_layer.name for uv_layer in obj.data.uv_layers],  # type: ignore
            },
        )

    try:
        return execute_on_main_thread(prepare_uvs, timeout=60.0)
    except Exception as e:
        logger.error(f"PREPARE_LOW_POLY failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_bake",
            action="PREPARE_LOW_POLY",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_create_bake_material(**params):  # type: ignore[no-untyped-def]
    """Create a material with an image texture node for baking."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_BAKE_MATERIAL",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("low_poly")
    image_name = params.get("output_image", "BakeTexture")
    resolution = params.get("resolution", BakingDefaults.DEFAULT_RESOLUTION)

    if not obj_name:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_BAKE_MATERIAL",
            error_code="MISSING_PARAMETER",
            message="low_poly object name is required",
        )

    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_BAKE_MATERIAL",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{obj_name}' not found",
        )

    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_BAKE_MATERIAL",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Expected MESH, got {obj.type}",
        )

    try:
        # Create or get image
        image = _get_or_create_image(image_name, resolution, alpha=True)

        # Create material
        mat_name = params.get("material_name", f"{obj_name}_BakeMat")
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
        else:
            mat = bpy.data.materials.new(name=mat_name)

        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()

        # Add nodes
        output = nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (300, 0)

        diffuse = nodes.new(type="ShaderNodeBsdfDiffuse")
        diffuse.location = (0, 0)

        tex_image = nodes.new(type="ShaderNodeTexImage")
        tex_image.location = (-300, 0)
        tex_image.image = image
        tex_image.select = True  # Select for baking

        # Link nodes
        mat.node_tree.links.new(diffuse.outputs[0], output.inputs[0])
        mat.node_tree.links.new(tex_image.outputs[0], diffuse.inputs[0])

        # Assign material to object
        if len(obj.data.materials) == 0:  # type: ignore
            obj.data.materials.append(mat)  # type: ignore
        else:
            obj.data.materials[0] = mat  # type: ignore

        return ResponseBuilder.success(
            handler="manage_bake",
            action="CREATE_BAKE_MATERIAL",
            data={"material": mat.name, "image": image.name, "resolution": resolution},
        )
    except Exception as e:
        logger.error(f"CREATE_BAKE_MATERIAL failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_BAKE_MATERIAL",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


# =============================================================================
# BAKE OPERATIONS - All require Cycles and main thread execution
# =============================================================================


def _handle_bake_normal(**params):  # type: ignore[no-untyped-def]
    """Bake normal map with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_NORMAL",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_NORMAL",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly = _setup_bake_objects(params)
    if isinstance(low_poly, dict) and not low_poly.get("success", True):
        return low_poly

    high_poly_name = params.get("high_poly")
    high_poly = bpy.data.objects.get(high_poly_name) if high_poly_name else None

    scene.cycles.bake_type = "NORMAL"
    scene.render.bake.normal_space = params.get("normal_space", "TANGENT")
    scene.render.bake.normal_r = params.get("normal_r", "POS_X")
    scene.render.bake.normal_g = params.get("normal_g", "POS_Y")
    scene.render.bake.normal_b = params.get("normal_b", "POS_Z")

    if high_poly:
        # Selected to active bake
        high_poly.select_set(True)
        success, error = _execute_bake_with_context(
            scene,
            "NORMAL",
            pass_filter=set(),
            filepath=params.get("output_path", ""),
            save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
            use_selected_to_active=True,
            margin=scene.render.bake.margin,
        )
    else:
        # Single object bake
        success, error = _execute_bake_with_context(
            scene,
            "NORMAL",
            pass_filter=set(),
            filepath=params.get("output_path", ""),
            save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
        )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_NORMAL",
            data={
                "type": "NORMAL",
                "normal_space": scene.render.bake.normal_space,
                "output": params.get("output_image", "Internal"),
            },
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_NORMAL",
            error_code="EXECUTION_ERROR",
            message=f"Normal bake failed: {error}",
        )


def _handle_bake_ao(**params):  # type: ignore[no-untyped-def]
    """Bake ambient occlusion with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_AO",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_AO",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly = _setup_bake_objects(params)
    if isinstance(low_poly, dict) and not low_poly.get("success", True):
        return low_poly

    scene.cycles.bake_type = "AO"
    ao_distance = params.get("ao_distance", BakingDefaults.DEFAULT_AO_DISTANCE)
    bake = scene.render.bake
    # Blender 5.0 removed BakeSettings.ao_distance (Blender Internal era property).
    # BakeSettings.max_ray_distance is the closest Blender 5.0+ equivalent.
    if hasattr(bake, "ao_distance"):
        bake.ao_distance = ao_distance  # Blender < 5.0 legacy path
    elif hasattr(bake, "max_ray_distance"):
        bake.max_ray_distance = ao_distance  # Blender 5.0+
    # ao_inside was a Blender Internal renderer property removed in Blender 5.0.
    # Cycles has no equivalent concept; silently skip on 5.0+.
    if hasattr(bake, "ao_inside"):
        bake.ao_inside = params.get("ao_inside", False)

    success, error = _execute_bake_with_context(
        scene,
        "AO",
        pass_filter=set(),
        filepath=params.get("output_path", ""),
        save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
    )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_AO",
            data={
                "type": "AO",
                "distance": ao_distance,
                "output": params.get("output_image", "Internal"),
            },
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_AO",
            error_code="EXECUTION_ERROR",
            message=f"AO bake failed: {error}",
        )


def _handle_bake_lightmap(**params):  # type: ignore[no-untyped-def]
    """Bake lightmap with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_LIGHTMAP",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_LIGHTMAP",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly = _setup_bake_objects(params)
    if isinstance(low_poly, dict) and not low_poly.get("success", True):
        return low_poly

    scene.cycles.bake_type = "DIFFUSE"

    success, error = _execute_bake_with_context(
        scene,
        "DIFFUSE",
        pass_filter=set(),
        filepath=params.get("output_path", ""),
        save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
    )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_LIGHTMAP",
            data={
                "type": "LIGHTMAP",
                "note": "Diffuse lighting only (use for lightmap)",
                "output": params.get("output_image", "Internal"),
            },
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_LIGHTMAP",
            error_code="EXECUTION_ERROR",
            message=f"Lightmap bake failed: {error}",
        )


def _handle_bake_combined(**params):  # type: ignore[no-untyped-def]
    """Bake combined with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_COMBINED",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_COMBINED",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly = _setup_bake_objects(params)
    if isinstance(low_poly, dict) and not low_poly.get("success", True):
        return low_poly

    high_poly_name = params.get("high_poly")
    high_poly = bpy.data.objects.get(high_poly_name) if high_poly_name else None

    scene.cycles.bake_type = "COMBINED"

    # Configure pass filter
    pass_filter = set(params.get("pass_filter", []))

    if high_poly:
        high_poly.select_set(True)
        success, error = _execute_bake_with_context(
            scene,
            "COMBINED",
            pass_filter=pass_filter,
            filepath=params.get("output_path", ""),
            save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
            use_selected_to_active=True,
            margin=scene.render.bake.margin,
        )
    else:
        success, error = _execute_bake_with_context(
            scene,
            "COMBINED",
            pass_filter=pass_filter,
            filepath=params.get("output_path", ""),
            save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
        )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_COMBINED",
            data={
                "type": "COMBINED",
                "pass_filter": list(pass_filter),
                "output": params.get("output_image", "Internal"),
            },
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_COMBINED",
            error_code="EXECUTION_ERROR",
            message=f"Combined bake failed: {error}",
        )


def _handle_bake_diffuse(**params):  # type: ignore[no-untyped-def]
    """Bake diffuse with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DIFFUSE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DIFFUSE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly = _setup_bake_objects(params)
    if isinstance(low_poly, dict) and not low_poly.get("success", True):
        return low_poly

    scene.cycles.bake_type = "DIFFUSE"

    success, error = _execute_bake_with_context(
        scene,
        "DIFFUSE",
        pass_filter=set(),
        filepath=params.get("output_path", ""),
        save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
    )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_DIFFUSE",
            data={"type": "DIFFUSE", "output": params.get("output_image", "Internal")},
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DIFFUSE",
            error_code="EXECUTION_ERROR",
            message=f"Diffuse bake failed: {error}",
        )


def _handle_bake_glossy(**params):  # type: ignore[no-untyped-def]
    """Bake glossy with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_GLOSSY",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_GLOSSY",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly = _setup_bake_objects(params)
    if isinstance(low_poly, dict) and not low_poly.get("success", True):
        return low_poly

    scene.cycles.bake_type = "GLOSSY"

    success, error = _execute_bake_with_context(
        scene,
        "GLOSSY",
        pass_filter=set(),
        filepath=params.get("output_path", ""),
        save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
    )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_GLOSSY",
            data={"type": "GLOSSY", "output": params.get("output_image", "Internal")},
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_GLOSSY",
            error_code="EXECUTION_ERROR",
            message=f"Glossy bake failed: {error}",
        )


def _handle_bake_shadow(**params):  # type: ignore[no-untyped-def]
    """Bake shadow with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_SHADOW",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_SHADOW",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly = _setup_bake_objects(params)
    if isinstance(low_poly, dict) and not low_poly.get("success", True):
        return low_poly

    scene.cycles.bake_type = "SHADOW"

    success, error = _execute_bake_with_context(
        scene,
        "SHADOW",
        pass_filter=set(),
        filepath=params.get("output_path", ""),
        save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
    )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_SHADOW",
            data={"type": "SHADOW", "output": params.get("output_image", "Internal")},
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_SHADOW",
            error_code="EXECUTION_ERROR",
            message=f"Shadow bake failed: {error}",
        )


def _handle_bake_displacement(**params):  # type: ignore[no-untyped-def]
    """Bake displacement with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DISPLACEMENT",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DISPLACEMENT",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly_name = params.get("low_poly")
    if not low_poly_name:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DISPLACEMENT",
            error_code="MISSING_PARAMETER",
            message="low_poly object is required for displacement baking",
        )

    low_poly = bpy.data.objects.get(low_poly_name)
    if not low_poly:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DISPLACEMENT",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{low_poly_name}' not found",
        )

    high_poly_name = params.get("high_poly")
    if not high_poly_name:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DISPLACEMENT",
            error_code="MISSING_PARAMETER",
            message="high_poly object is required for displacement baking",
        )

    high_poly = bpy.data.objects.get(high_poly_name)
    if not high_poly:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DISPLACEMENT",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{high_poly_name}' not found",
        )

    # Setup objects for baking
    def setup():  # type: ignore[no-untyped-def]
        ContextManagerV3.deselect_all_objects()
        low_poly.select_set(True)
        bpy.context.view_layer.objects.active = low_poly
        _ensure_image_node_selected(low_poly)

    execute_on_main_thread(setup, timeout=10.0)

    scene.cycles.bake_type = "DISPLACEMENT"

    high_poly.select_set(True)
    success, error = _execute_bake_with_context(
        scene,
        "DISPLACEMENT",
        pass_filter=set(),
        filepath=params.get("output_path", ""),
        save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
        use_selected_to_active=True,
        margin=scene.render.bake.margin,
    )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_DISPLACEMENT",
            data={"type": "DISPLACEMENT", "output": params.get("output_image", "Internal")},
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_DISPLACEMENT",
            error_code="EXECUTION_ERROR",
            message=f"Displacement bake failed: {error}",
        )


def _handle_bake_emission(**params):  # type: ignore[no-untyped-def]
    """Bake emission with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_EMISSION",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_EMISSION",
            error_code="NO_SCENE",
            message="No scene available",
        )

    _ensure_cycles(scene)

    low_poly = _setup_bake_objects(params)
    if isinstance(low_poly, dict) and not low_poly.get("success", True):
        return low_poly

    scene.cycles.bake_type = "EMIT"

    success, error = _execute_bake_with_context(
        scene,
        "EMIT",
        pass_filter=set(),
        filepath=params.get("output_path", ""),
        save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
    )

    if success:
        return ResponseBuilder.success(
            handler="manage_bake",
            action="BAKE_EMISSION",
            data={"type": "EMISSION", "output": params.get("output_image", "Internal")},
        )
    else:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE_EMISSION",
            error_code="EXECUTION_ERROR",
            message=f"Emission bake failed: {error}",
        )


def _setup_bake_objects(params: dict[str, Any]) -> Any:
    """
    Bake için low_poly ve opsiyonel high_poly objelerini hazırlar.
    low_poly ZORUNLU, high_poly opsiyonel (sadece normal bake için gerekli).
    """
    import bpy

    low_poly_name = params.get("low_poly") or params.get("target") or params.get("object")

    # ✅ Erken ve açıklayıcı validasyon
    if not low_poly_name:
        return {
            "success": False,
            "error_code": "MISSING_PARAMETER",
            "message": ("'low_poly' parametresi zorunludur. Bake alınacak hedef objeyi belirtin."),
            "example": {
                "action": "BAKE_NORMAL",
                "low_poly": "Drone_LP",
                "high_poly": "Drone_HP",  # Normal bake için
                "image_name": "NormalMap",
                "resolution": 2048,
            },
        }

    low_poly = bpy.data.objects.get(low_poly_name)
    if low_poly is None:
        return {
            "success": False,
            "error_code": "OBJECT_NOT_FOUND",
            "message": f"low_poly obje bulunamadı: '{low_poly_name}'",
            "available_meshes": [o.name for o in bpy.data.objects if o.type == "MESH"],
        }

    if low_poly.type != "MESH":
        return {
            "success": False,
            "error_code": "INVALID_TYPE",
            "message": f"low_poly MESH tipi olmalı. Mevcut tip: {low_poly.type}",
        }

    scene = ContextManagerV3.get_scene()
    if scene:
        scene.render.bake.margin = params.get("margin", BakingDefaults.DEFAULT_MARGIN)
        scene.cycles.samples = params.get("samples", BakingDefaults.DEFAULT_SAMPLES)

        # Use cage if specified
        if params.get("use_cage") and params.get("cage"):
            cage_obj = bpy.data.objects.get(params["cage"])
            if cage_obj:
                scene.render.bake.cage_object = cage_obj
                scene.render.bake.use_cage = True
        else:
            scene.render.bake.use_cage = False
            scene.render.bake.cage_extrusion = params.get(
                "cage_extrusion", BakingDefaults.DEFAULT_CAGE_EXTRUSION
            )

    # Image node kontrolü — bake çalışmadan önce zorunlu
    has_bake_node = False
    for mat_slot in low_poly.material_slots:
        if mat_slot.material and mat_slot.material.use_nodes:
            for node in mat_slot.material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node == mat_slot.material.node_tree.nodes.active:
                    has_bake_node = True
                    break

    if not has_bake_node:
        # Otomatik image node oluştur
        image_name = params.get("image_name", f"Bake_{low_poly_name}")
        resolution = int(params.get("resolution", 1024))
        _auto_create_bake_node(low_poly, image_name, resolution)

    def setup() -> None:
        ContextManagerV3.deselect_all_objects()
        low_poly.select_set(True)
        bpy.context.view_layer.objects.active = low_poly

    execute_on_main_thread(setup, timeout=10.0)

    return low_poly


def _auto_create_bake_node(obj: Any, image_name: str, resolution: int) -> None:
    """Low_poly objesine otomatik bake image node ekler."""
    import bpy

    image = bpy.data.images.get(image_name)
    if not image:
        image = bpy.data.images.new(image_name, width=resolution, height=resolution)
        image.generated_color = (0, 0, 0, 1)

    for mat_slot in obj.material_slots:
        if not mat_slot.material:
            continue
        if not mat_slot.material.use_nodes:
            mat_slot.material.use_nodes = True

        nodes = mat_slot.material.node_tree.nodes
        # Mevcut bake node'u temizle
        existing = [n for n in nodes if n.type == "TEX_IMAGE" and n.name.startswith("_bake_")]
        for n in existing:
            nodes.remove(n)

        img_node = nodes.new("ShaderNodeTexImage")
        img_node.name = "_bake_target"
        img_node.image = image
        img_node.location = (-300, -200)
        nodes.active = img_node  # Active node = bake hedefi


# =============================================================================
# GENERIC BAKE / CONFIGURE / CREATE_IMAGE / SETUP_MATERIALS
# These actions were defined in BakeAction enum but lacked handler branches.
# =============================================================================


def _handle_bake(**params):  # type: ignore[no-untyped-def]
    """
    Generic bake action: bakes the specified type on the active object.
    Wraps any Cycles bake type (DIFFUSE, GLOSSY, NORMAL, etc.) via the 'bake_type' parameter.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    bake_type = params.pop("bake_type", "COMBINED").upper()
    valid_types = {
        "COMBINED",
        "DIFFUSE",
        "GLOSSY",
        "TRANSMISSION",
        "SUBSURFACE",
        "AO",
        "SHADOW",
        "NORMAL",
        "UV",
        "ROUGHNESS",
        "EMIT",
        "ENVIRONMENT",
        "POSITION",
    }
    if bake_type not in valid_types:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE",
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Invalid bake_type '{bake_type}'. Valid: {sorted(valid_types)}",
        )

    try:
        _ensure_cycles(scene)

        low_poly = _setup_bake_objects(params)
        if isinstance(low_poly, dict) and not low_poly.get("success", True):
            return low_poly

        scene.cycles.bake_type = bake_type
        samples = params.pop("samples", None)
        if samples:
            scene.cycles.samples = int(samples)

        margin = params.pop("margin", BakingDefaults.DEFAULT_MARGIN)
        scene.render.bake.margin = margin

        success, error = _execute_bake_with_context(
            scene,
            bake_type,
            pass_filter=set(),
            filepath=params.get("output_path", ""),
            save_mode="INTERNAL" if not params.get("output_path") else "EXTERNAL",
        )

        if success:
            return ResponseBuilder.success(
                handler="manage_bake",
                action="BAKE",
                data={
                    "type": bake_type,
                    "samples": scene.cycles.samples,
                    "margin": margin,
                },
            )
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE",
            error_code="EXECUTION_ERROR",
            message=f"Bake ({bake_type}) failed: {error}",
        )
    except Exception as e:
        logger.error(f"BAKE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_bake",
            action="BAKE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_create_image(**params):  # type: ignore[no-untyped-def]
    """
    Create a bake target image in bpy.data.images.
    Ensures the image is correctly sized and named for baking output.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_IMAGE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    image_name = params.get("image_name", "BakeTarget")
    width = int(params.get("width", BakingDefaults.DEFAULT_RESOLUTION))
    height = int(params.get("height", BakingDefaults.DEFAULT_RESOLUTION))
    color = params.get("color", (0.0, 0.0, 0.0, 1.0))
    use_alpha = params.get("use_alpha", True)
    is_float = params.get("is_float", False)

    if width < 1 or width > BakingDefaults.MAX_RESOLUTION:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_IMAGE",
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Width must be 1-{BakingDefaults.MAX_RESOLUTION}, got {width}",
        )
    if height < 1 or height > BakingDefaults.MAX_RESOLUTION:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_IMAGE",
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Height must be 1-{BakingDefaults.MAX_RESOLUTION}, got {height}",
        )

    try:
        existing = bpy.data.images.get(image_name)
        if existing:
            bpy.data.images.remove(existing)

        image = bpy.data.images.new(
            name=image_name,
            width=width,
            height=height,
            alpha=use_alpha,
            float_buffer=is_float,
        )
        image.generated_color = color if len(color) == 4 else (*color, 1.0)

        return ResponseBuilder.success(
            handler="manage_bake",
            action="CREATE_IMAGE",
            data={
                "image_name": image.name,
                "width": width,
                "height": height,
                "is_float": is_float,
                "use_alpha": use_alpha,
            },
        )
    except Exception as e:
        logger.error(f"CREATE_IMAGE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CREATE_IMAGE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_setup_materials(**params):  # type: ignore[no-untyped-def]
    """
    Setup materials on target object for baking.
    Creates a principled BSDF material with an image texture node ready for bake output.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="SETUP_MATERIALS",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    from ..core.resolver import resolve_name

    obj_name = params.get("object_name") or params.get("target")
    obj = (
        resolve_name(obj_name)
        if obj_name
        else (bpy.context.active_object if hasattr(bpy, "context") else None)
    )

    if not obj:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="SETUP_MATERIALS",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{obj_name}' not found",
        )
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_bake",
            action="SETUP_MATERIALS",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Expected MESH, got {obj.type}",
        )

    image_name = params.get("image_name", "BakeTarget")
    resolution = int(params.get("resolution", BakingDefaults.DEFAULT_RESOLUTION))

    try:
        image = bpy.data.images.get(image_name)
        if not image:
            image = bpy.data.images.new(
                name=image_name, width=resolution, height=resolution, alpha=True
            )

        mat_name = params.get("material_name", f"{obj.name}_BakeMat")
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(name=mat_name)

        mat.use_nodes = True
        nodes = mat.node_tree.nodes

        tex_node = None
        for node in nodes:
            if node.type == "TEX_IMAGE":
                tex_node = node  # type: ignore
                break

        if not tex_node:
            tex_node = nodes.new(type="ShaderNodeTexImage")
            tex_node.location = (-300, 0)

        tex_node.image = image  # type: ignore
        tex_node.select = True
        nodes.active = tex_node

        if len(obj.data.materials) == 0:  # type: ignore[union-attr]
            obj.data.materials.append(mat)  # type: ignore[union-attr]
        else:
            assigned = False
            for i, existing_mat in enumerate(obj.data.materials):  # type: ignore[union-attr]
                if existing_mat and existing_mat.name == mat_name:
                    assigned = True
                    break
            if not assigned:
                obj.data.materials.append(mat)  # type: ignore[union-attr]

        return ResponseBuilder.success(
            handler="manage_bake",
            action="SETUP_MATERIALS",
            data={
                "object": obj.name,
                "material": mat.name,
                "image": image.name,
                "resolution": resolution,
            },
        )
    except Exception as e:
        logger.error(f"SETUP_MATERIALS failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_bake",
            action="SETUP_MATERIALS",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_configure(**params):  # type: ignore[no-untyped-def]
    """
    Configure bake settings on the current scene (samples, margin, pass filters, etc.)
    without executing a bake. Allows fine-tuning before calling BAKE or type-specific actions.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CONFIGURE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CONFIGURE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    try:
        was_changed = _ensure_cycles(scene)
        applied_settings: dict = {"engine_changed": was_changed}

        if "samples" in params:
            scene.cycles.samples = int(params["samples"])
            applied_settings["samples"] = scene.cycles.samples

        if "margin" in params:
            scene.render.bake.margin = int(params["margin"])
            applied_settings["margin"] = scene.render.bake.margin

        if "margin_type" in params:
            margin_type = params["margin_type"].upper()
            if margin_type in {"EXTEND", "ADJACENT_FACES"}:
                scene.render.bake.margin_type = margin_type
                applied_settings["margin_type"] = margin_type

        if "use_clear" in params:
            scene.render.bake.use_clear = bool(params["use_clear"])
            applied_settings["use_clear"] = scene.render.bake.use_clear

        if "use_selected_to_active" in params:
            scene.render.bake.use_selected_to_active = bool(params["use_selected_to_active"])
            applied_settings["use_selected_to_active"] = scene.render.bake.use_selected_to_active

        if "cage_extrusion" in params:
            scene.render.bake.cage_extrusion = float(params["cage_extrusion"])
            applied_settings["cage_extrusion"] = scene.render.bake.cage_extrusion

        if "max_ray_distance" in params:
            scene.render.bake.max_ray_distance = float(params["max_ray_distance"])
            applied_settings["max_ray_distance"] = scene.render.bake.max_ray_distance

        return ResponseBuilder.success(
            handler="manage_bake",
            action="CONFIGURE",
            data=applied_settings,
        )
    except Exception as e:
        logger.error(f"CONFIGURE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_bake",
            action="CONFIGURE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )
