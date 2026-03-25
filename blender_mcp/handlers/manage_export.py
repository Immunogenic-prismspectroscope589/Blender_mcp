import contextlib
import os

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
from ..dispatcher import register_handler
from ..core.parameter_validator import validated_handler
from ..core.enums import ExportAction
from ..core.thread_safety import ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils
from ..utils.error_handler import mcp_tool_handler
from ..utils.path_validator import PathValidator
from typing import Any

logger = get_logger()

# =============================================================================
# STAFF+ EXPORT STRATEGY
# =============================================================================


@contextlib.contextmanager
def SafeExportStrategy(use_selection=False, apply_modifiers=True):  # type: ignore[no-untyped-def]
    """
    Staff+ Reliability Pattern: Safe Export Context.

    Problem: Exporting objects with active Boolean/GeoNodes modifiers often crashes
             GLTF/FBX exporters due to UV/Vertex count mismatches during evaluation.

    Solution:
    1. Duplicate target objects.
    2. Convert duplicates to MESH (Applies ALL modifiers destructively).
    3. Select ONLY duplicates.
    4. Yield control for Export.
    5. Cleanup (Delete duplicates).
    """
    # 1. Identify Targets
    if use_selection:
        targets = [
            o
            for o in bpy.context.selected_objects
            if o.type in ["MESH", "CURVE", "SURFACE", "FONT", "META"]
        ]
    else:
        targets = [
            o
            for o in bpy.context.scene.objects
            if o.type in ["MESH", "CURVE", "SURFACE", "FONT", "META"]
        ]

    if not targets:
        yield  # Nothing to export
        return

    # Store original selection to restore later
    original_selection = bpy.context.selected_objects
    original_active = bpy.context.active_object

    exported_objects = []

    try:
        # 1.0.0 Fix: Wrap all bpy.ops calls in temp_override for context safety
        # RCA: SafeExportStrategy calls bpy.ops.object.* which need VIEW_3D context
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            # 2. Deselect All
            ContextManagerV3.deselect_all_objects()

            # 3. Duplicate & Convert
            for obj in targets:
                # Duplicate
                new_obj = obj.copy()
                new_obj.data = obj.data.copy()
                bpy.context.collection.objects.link(new_obj)
                bpy.context.view_layer.update()

                # Select for conversion
                new_obj.select_set(True)
                bpy.context.view_layer.objects.active = new_obj

                if apply_modifiers:
                    # Convert to Mesh (Applies modifiers)
                    # 1.0.0 Fix: Instead of bpy.ops.object.convert(target='MESH') which crashes
                    # Blender 5.0 depending on the active context and multithreading, we use
                    # depsgraph evaluation to bake a mesh safely.
                    if new_obj.type != "MESH" or len(new_obj.modifiers) > 0:
                        try:
                            depsgraph = bpy.context.evaluated_depsgraph_get()
                            obj_eval = new_obj.evaluated_get(depsgraph)
                            mesh_data = bpy.data.meshes.new_from_object(
                                obj_eval, preserve_all_data_layers=True, depsgraph=depsgraph
                            )

                            # Replace old data with baked mesh and clear modifiers
                            old_data = new_obj.data
                            new_obj.modifiers.clear()
                            new_obj.data = mesh_data

                            # Cleanup old data if needed (garbage collection usually handles it)
                            if old_data and old_data.users == 0:
                                try:
                                    bpy.data.meshes.remove(old_data)
                                except Exception as e_rm:
                                    print(f"[MCP] Warning: GC Failed to remove old mesh {e_rm}")

                        except Exception as e:
                            print(
                                f"[MCP] Warning: Failed to evaluate/bake mesh for {new_obj.name}: {e}"
                            )

                exported_objects.append(new_obj)

            # 4. Final Selection State for Exporter
            # Force UI Context sync BEFORE modifying selections to prevent 0xc0000005 crash
            if bpy:
                bpy.context.view_layer.update()

                # Exporters usually operate on "Selected Objects"
                # Use explicit selection iteration instead of global operator
                for o in list(bpy.context.selected_objects):
                    try:
                        o.select_set(False)
                    except Exception:
                        pass

            for obj in exported_objects:
                obj.select_set(True)

            # Yield to Exporter
            yield

    finally:
        # 5. Cleanup
        # Delete temporary objects
        if exported_objects:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.object.delete()

        # Restore Selection
        for obj in original_selection:
            try:
                obj.select_set(True)
            except:
                pass

        if original_active:
            bpy.context.view_layer.objects.active = original_active


@register_handler(
    "manage_export",
    actions=[a.value for a in ExportAction],
    category="general",
    priority=25,
    schema={
        "type": "object",
        "title": "Export Manager (CORE)",
        "description": (
            "CORE — Export scene to GLTF/GLB, FBX, OBJ, STL with safe mode (auto-bake modifiers).\n\n"
            "safe_mode=True (default) duplicates objects and applies modifiers before export to prevent "
            "crashes. Set safe_mode=False only for simple scenes without boolean/geonode modifiers.\n"
            "ACTIONS: EXPORT_GLTF, EXPORT_FBX, EXPORT_OBJ, EXPORT_STL"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(ExportAction, "Export format."),
            "filepath": {"type": "string", "description": "Output path."},
            "use_selection": {
                "type": "boolean",
                "default": False,
                "description": "Export only selected objects.",
            },
            "safe_mode": {
                "type": "boolean",
                "default": True,
                "description": "If True, duplicates and bakes mesh before export. Slower but prevents crashes.",
            },
            "params": {
                "type": "object",
                "description": "Format specific parameters.",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["GLB", "GLTF_SEPARATE", "GLTF_EMBEDDED"],
                        "description": "GLTF export format",
                    },
                    "use_draco": {
                        "type": "boolean",
                        "description": "Enable Draco compression (GLTF only). Alias: draco_compression",
                    },
                    "draco_compression": {
                        "type": "boolean",
                        "description": "Enable Draco compression (alternative name)",
                    },
                    "draco_level": {
                        "type": "integer",
                        "default": 6,
                        "minimum": 0,
                        "maximum": 10,
                        "description": "Draco compression level (0=fast, 10=best)",
                    },
                    "draco_quantization": {
                        "type": "integer",
                        "default": 14,
                        "description": "Position quantization bits",
                    },
                    "axis_forward": {
                        "type": "string",
                        "default": "-Z",
                        "description": "Forward axis (FBX/OBJ)",
                    },
                    "axis_up": {
                        "type": "string",
                        "default": "Y",
                        "description": "Up axis (FBX/OBJ)",
                    },
                },
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in ExportAction])
@mcp_tool_handler
def manage_export(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Advanced Export Handling with Staff+ Safe Mode.
    """
    # Sanitize Path with strict Validator
    try:
        filepath = PathValidator.validate_and_prepare(params.get("filepath"))
    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_export",
            action=action,
            error_code="INVALID_PATH",
            message=str(e),
        )

    # Staff+ Default: Safe Mode IS ON by default for complex scenes
    safe_mode = params.get("safe_mode", True)
    use_selection = params.get("use_selection", False)
    extra_params = params.get("params", {})

    # Verify Permissions (Staff+ Hardening)
    dir_name = os.path.dirname(filepath)
    if not os.path.exists(dir_name):
        try:
            os.makedirs(dir_name, exist_ok=True)
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_export",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Permission Denied: Cannot create '{dir_name}'. Error: {e}",
                details={"filepath": filepath, "directory": dir_name},
            )

    try:
        # Define the export operation
        # 1.0.0 Fix: Wrap ALL export bpy.ops in temp_override for context safety
        def run_export():  # type: ignore[no-untyped-def]
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                if action == ExportAction.EXPORT_GLTF.value:
                    export_format = extra_params.get("format", "GLB")

                    # Normalize Draco parameter names (accept both use_draco and draco_compression)
                    use_draco = extra_params.get("use_draco") or extra_params.get(
                        "draco_compression", False
                    )

                    # Additional Draco parameters for fine control
                    draco_quantization = extra_params.get(
                        "draco_quantization", 14
                    )  # Default 14-bit

                    # Build export kwargs
                    gltf_kwargs = {
                        "filepath": filepath,
                        "export_format": export_format,
                        "use_selection": True,  # Always True inside SafeContext
                        "export_apply": True,
                        "export_image_format": "AUTO",  # Blender 5.0+ Strict Compliance
                    }

                    # Add Draco if requested
                    if use_draco:
                        gltf_kwargs["export_draco_mesh_compression_enable"] = True

                        try:
                            d_level = max(0, min(10, int(extra_params.get("draco_level", 6))))
                        except (TypeError, ValueError):
                            d_level = 6
                        gltf_kwargs["export_draco_mesh_compression_level"] = d_level

                        try:
                            d_quant = max(0, min(30, int(draco_quantization)))
                        except (TypeError, ValueError):
                            d_quant = 14
                        gltf_kwargs["export_draco_position_quantization"] = d_quant

                        gltf_kwargs["export_draco_normal_quantization"] = extra_params.get(
                            "draco_normal_quant", 10
                        )
                        gltf_kwargs["export_draco_texcoord_quantization"] = extra_params.get(
                            "draco_texcoord_quant", 12
                        )

                    safe_ops.export_scene.gltf(**gltf_kwargs)

                    return {
                        "format": "GLTF",
                        "draco": bool(use_draco),
                        "draco_level": extra_params.get("draco_level", 6) if use_draco else None,
                    }

                elif action == ExportAction.EXPORT_FBX.value:
                    safe_ops.export_scene.fbx(
                        filepath=filepath,
                        use_selection=True,
                        use_mesh_modifiers=True,
                        axis_forward=extra_params.get("axis_forward", "-Z"),
                        axis_up=extra_params.get("axis_up", "Y"),
                    )
                    return {"format": "FBX"}

                elif action == ExportAction.EXPORT_OBJ.value:
                    safe_ops.export_scene.obj(
                        filepath=filepath,
                        use_selection=True,
                        use_mesh_modifiers=True,
                    )
                    return {"format": "OBJ"}

                else:
                    raise ValueError(f"Unknown Export Action: {action}")

        # EXECUTE WITH STRATEGY
        if safe_mode:
            print("[MCP] Safe Export Mode: Duplicating and Baking Meshes...")
            with SafeExportStrategy(use_selection=use_selection, apply_modifiers=True):
                result = run_export()
        else:
            # Unsafe / Fast Mode (Direct Export)
            # We must respect use_selection logic here manually since context manager handled it above
            # Actually, standard operators handle use_selection param directly.
            # But wait, our run_export wrapper hardcoded use_selection=True for the SafeContext.
            # We need to adapt run_export slightly or just rely on the operators params.

            # Simple fallback for unsafe mode:
            # 1.0.0 Fix: Wrap in temp_override for context safety
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                if action == ExportAction.EXPORT_GLTF.value:
                    safe_ops.export_scene.gltf(filepath=filepath, use_selection=use_selection)
                elif action == ExportAction.EXPORT_FBX.value:
                    safe_ops.export_scene.fbx(filepath=filepath, use_selection=use_selection)
                elif action == ExportAction.EXPORT_OBJ.value:
                    try:
                        # Blender 5.x+ new operator
                        safe_ops.wm.obj_export(
                            filepath=filepath,
                            export_selected_objects=use_selection,
                            apply_modifiers=True,
                        )
                    except AttributeError:
                        # Fallback for older Blender versions
                        safe_ops.export_scene.obj(
                            filepath=filepath, use_selection=use_selection, use_mesh_modifiers=True
                        )

            result = {"format": action.split("_")[1], "mode": "UNSAFE_FAST"}

        return ResponseBuilder.success(
            handler="manage_export", action=action, data={"path": filepath, "details": result}
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_export",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Export Failed: {str(e)}",
            details={"filepath": filepath, "error": str(e)},
        )
