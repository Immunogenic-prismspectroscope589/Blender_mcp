from typing import Any, Dict, List, Optional, Tuple, cast, TYPE_CHECKING

import bpy

from ..dispatcher import register_handler
from ..core.resolver import resolve_name
from ..core.execution_engine import safe_ops
from ..core.response_builder import ResponseBuilder
from ..core.semantic_memory import get_semantic_memory
from ..core.context_manager_v3 import ContextManagerV3
from ..core.validation_utils import ValidationUtils
from typing import Iterable, Literal


if TYPE_CHECKING:
    from ..core.semantic_memory import SemanticSceneMemory
    from bpy.types import (
        SubsurfModifier,
        WireframeModifier,
        LaplacianSmoothModifier,
        SolidifyModifier,
        MirrorModifier,
        BooleanModifier,
    )
from ..core.enums import ModelingAction


def safe_mode(mode: str, obj_name: str) -> Tuple[bool, str]:
    """Safely switch object mode with context override."""
    obj = resolve_name(obj_name)
    if not obj:
        return False, f"Object not found: {obj_name}"
    try:
        ContextManagerV3.set_active_object(obj)
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D",
            active_object=obj,
            selected_objects=[obj],
        ):
            safe_ops.object.mode_set(mode=mode)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def get_spatial_state_safe(obj_name: str) -> Optional[Dict[str, Any]]:
    from ..core.thread_safety import execute_on_main_thread
    from ..core.resolver import resolve_name
    from .manage_scene_comprehension import (
        _get_spatial_report,
    )  # file still named manage_scene_comprehension.py

    def _fetch() -> Optional[Dict[str, Any]]:
        obj = resolve_name(obj_name)
        if obj:
            res = _get_spatial_report(obj)
            context = res.get("data", {}).get("spatial_context")
            return cast(Optional[Dict[str, Any]], context)
        return None

    return cast(Optional[Dict[str, Any]], execute_on_main_thread(_fetch))


@register_handler(
    "manage_modeling",
    priority=16,
    schema={
        "type": "object",
        "title": "Modeling Manager (CORE)",
        "description": (
            "CORE — 3D modeling: create primitives (Cube/Sphere/Cylinder), apply modifiers "
            "(Array/Bevel/Mirror/Subdivision/Solidify), mesh editing (Extrude/Loop Cut), "
            "booleans (Union/Difference/Intersect), and placement utilities.\n\n"
            "TIP: For complex custom geometry, use execute_blender_code with bmesh API for full control.\n"
            "ACTIONS: ADD_PRIMITIVE, ADD_MODIFIER, APPLY_MODIFIER, BOOLEAN, EXTRUDE, LOOP_CUT, "
            "PLACE_RELATIVE_TO, ALIGN_TO, SNAP_TO_GROUND"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(ModelingAction, "Operation to perform."),
            "object_name": {"type": "string", "description": "Target object name."},
            "name": {
                "type": "string",
                "description": "Alternative to object_name for creating primitives.",
            },
            # PLACE_RELATIVE_TO Params
            "object_to_move": {
                "type": "string",
                "description": "Object to move in PLACE_RELATIVE_TO",
            },
            "anchor_object": {
                "type": "string",
                "description": "Object to align to in PLACE_RELATIVE_TO",
            },
            "anchor_point": {
                "type": "string",
                "description": "Part of anchor to snap to (e.g. positive_Y_end, center, negative_Z_end)",
            },
            "snap_point": {
                "type": "string",
                "description": "Part of object to snap. WARNING: 'center' snaps the geometric center causing overlap - use 'negative_y_end' (etc.) to place flush.",
            },
            "offset": {"type": "number", "description": "Offset distance from anchor point"},
            # Primitive Params
            "primitive_type": {
                "type": "string",
                "enum": [
                    "CUBE",
                    "BOX",
                    "SPHERE",
                    "UV_SPHERE",
                    "BALL",
                    "CYLINDER",
                    "TUBE",
                    "PLANE",
                    "QUAD",
                    "MONKEY",
                    "SUZANNE",
                    "TORUS",
                    "DONUT",
                ],
                "description": "Object type. Supports synonyms (e.g., 'BOX'='CUBE', 'BALL'='SPHERE').",
            },
            "location": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x,y,z]",
            },
            "rotation": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x,y,z] radians",
            },
            "scale": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x,y,z]",
            },
            # Modifier Params
            "modifier_type": {
                "type": "string",
                "description": "Modifier type (e.g. SUBSURF, BEVEL, ARRAY).",
            },
            "modifier_name": {"type": "string"},
            "modifier_params": {
                "type": "object",
                "description": "Key-value pairs for modifier settings.",
            },
            # Mesh Edit Params
            "mesh_operation": {
                "type": "string",
                "enum": [
                    "EXTRUDE",
                    "INSET",
                    "BEVEL",
                    "SUBDIVIDE",
                    "LOOP_CUT",
                    "DELETE",
                    "FILL",
                    "MERGE",
                    "SMOOTH",
                    "AUTO_SMOOTH",
                    "RECALCULATE_NORMALS",
                ],
                "description": "Specific mesh edit operation.\nEXTRUDE: Extend geometry.\nINSET: Create inner faces.\nBEVEL (CHAMFER): Round edges.\nSUBDIVIDE: Add resolution.\nLOOP_CUT (EDGE_LOOP): Add edge loops.\nMERGE (WELD): Remove doubles/distances.\nSMOOTH: Shade smooth.\nAUTO_SMOOTH: Add Smooth by Angle modifier.",
            },
            "edit_params": {
                "type": "object",
                "description": "Parameters for mesh operation (e.g. offset, cuts).",
            },
            # Preset Params
            "preset_name": {
                "type": "string",
                "description": "Preset to apply (e.g. SMOOTH_SUBD).",
            },
            # Validation-First Workflow Params
            "validate_params": {
                "type": "object",
                "description": "Parameters for VALIDATE action (target_action + its params).",
            },
            "preview_params": {
                "type": "object",
                "description": "Parameters for PREVIEW action (target_action + its params).",
            },
            "commit_params": {
                "type": "object",
                "description": "Parameters for COMMIT action (target_action + its params).",
            },
            "skip_backup": {
                "type": "boolean",
                "default": False,
                "description": "Skip automatic backup during COMMIT.",
            },
            # V1.0.0: Semantic Scene Memory Params
            "semantic_tag": {
                "type": "string",
                "description": "Semantic tag to query (e.g., 'hero_character', 'main_camera').",
            },
            "tag_name": {
                "type": "string",
                "description": "Tag name for TAG_OBJECT action.",
            },
            "tag_confidence": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence level for tag (0-1).",
            },
        },
        "required": ["action"],
    },
)
def manage_modeling(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Core modeling and object manipulation toolkit. Handles primitive creation, modifiers, semantic alignment, and mesh validation.
    """
    obj_name_for_report = (
        params.get("object_name") or params.get("object_to_move") or params.get("name")
    )

    # 1. Pre-state (Spatial Wrapper)
    pre_state = None
    if obj_name_for_report and action not in [
        ModelingAction.VALIDATE.value,
        ModelingAction.PREVIEW.value,
        ModelingAction.QUERY_SEMANTIC.value,
    ]:
        pre_state = get_spatial_state_safe(obj_name_for_report)

    # 2. Execute
    result = _manage_modeling_impl(action, **params)

    # 3. Post-state (Spatial Wrapper)
    if obj_name_for_report and isinstance(result, dict) and result.get("success"):
        post_state = get_spatial_state_safe(obj_name_for_report)
        if post_state or pre_state:
            result["spatial_context_before"] = pre_state
            result["spatial_context_after"] = post_state
            if post_state and "human_readable" in post_state:
                result["spatial_feedback"] = post_state["human_readable"]
                result["note"] = "Review the 'spatial_feedback' block to verify your placement."

    return result


def _manage_modeling_impl(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Super-Tool for Modeling, Modifiers, and Mesh Editing.

    Validation-First Workflow
    -------------------------------
    All actions support 3-step workflow for safety:

    1. VALIDATE: Check parameters without side effects
       → Returns: valid (bool), errors (list), normalized_params

    2. PREVIEW: Simulate operation, show expected result
       → Returns: preview_data (vertices, faces, modifiers that would change)

    3. COMMIT: Execute operation (with optional dry-run first)
       → Returns: Standard success response with undo_info

    Example:
        # Step 1: Validate
        manage_modeling(action="VALIDATE", validate_params={
            "target_action": "BOOLEAN_UNION",
            "object_name": "Cube",
            "modifier_params": {"object": "Sphere"}
        })

        # Step 2: Preview (if validation passed)
        manage_modeling(action="PREVIEW", preview_params={...})

        # Step 3: Commit (if preview looks good)
        manage_modeling(action="COMMIT", commit_params={...})
    """
    # Validation-First Workflow Entry Points
    # ==================================================

    if action == ModelingAction.VALIDATE.value:
        return _handle_validate(params.get("validate_params", {}))

    if action == ModelingAction.PREVIEW.value:
        return _handle_preview(params.get("preview_params", {}))

    if action == ModelingAction.COMMIT.value:
        return _handle_commit(
            params.get("commit_params", {}), skip_backup=params.get("skip_backup", False)
        )

    # V1.0.0: Semantic Scene Memory Entry Points
    # ==================================================

    if action == ModelingAction.QUERY_SEMANTIC.value:
        return _handle_query_semantic(params.get("semantic_tag"), params)

    if action == ModelingAction.TAG_OBJECT.value:
        return _handle_tag_object(
            params.get("object_name"), params.get("tag_name"), params.get("tag_confidence", 1.0)
        )

    # Standard action validation
    if not action:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="UNKNOWN",
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
            recoverable=True,
            suggestion="Provide an action like ADD_PRIMITIVE, TRANSFORM, etc.",
        )

    if action == ModelingAction.PLACE_RELATIVE_TO.value:
        return _handle_place_relative_to(params)

    if action == ModelingAction.ADD_PRIMITIVE.value:
        raw_type = params.get("primitive_type", "CUBE").upper()

        # Synonym Mapping
        p_type = raw_type
        if raw_type in ["BOX"]:
            p_type = "CUBE"
        elif raw_type in ["BALL", "UV_SPHERE"]:
            p_type = "SPHERE"
        elif raw_type in ["TUBE"]:
            p_type = "CYLINDER"
        elif raw_type in ["QUAD"]:
            p_type = "PLANE"
        elif raw_type in ["SUZANNE"]:
            p_type = "MONKEY"
        elif raw_type in ["DONUT"]:
            p_type = "TORUS"
        loc = params.get("location", (0, 0, 0))
        rot = params.get("rotation", (0, 0, 0))
        scale = params.get("scale", (1, 1, 1))

        try:
            # Blender 5.x compatibility: Some primitives don't accept 'scale' parameter
            # Strategy: Create with location/rotation only, then apply scale
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                if p_type == "CUBE":
                    size = params.get("size", 2.0)
                    safe_ops.mesh.primitive_cube_add(location=loc, rotation=rot, size=size)
                elif p_type == "SPHERE":
                    radius = params.get("radius", 1.0)
                    safe_ops.mesh.primitive_uv_sphere_add(location=loc, rotation=rot, radius=radius)
                elif p_type == "CYLINDER":
                    radius = params.get("radius", 1.0)
                    depth = params.get("depth", 2.0)
                    safe_ops.mesh.primitive_cylinder_add(
                        location=loc, rotation=rot, radius=radius, depth=depth
                    )
                elif p_type == "PLANE":
                    size = params.get("size", 2.0)
                    safe_ops.mesh.primitive_plane_add(location=loc, rotation=rot, size=size)
                elif p_type == "MONKEY":
                    size = params.get("size", 2.0)
                    safe_ops.mesh.primitive_monkey_add(location=loc, rotation=rot, size=size)
                elif p_type == "TORUS":
                    major_radius = params.get("major_radius", 1.0)
                    minor_radius = params.get("minor_radius", 0.25)
                    safe_ops.mesh.primitive_torus_add(
                        location=loc,
                        rotation=rot,
                        major_radius=major_radius,
                        minor_radius=minor_radius,
                    )

            obj = bpy.context.active_object

            # Apply scale after creation for primitives that don't accept scale parameter
            if scale != (1, 1, 1):
                obj.scale = scale

            # STAFF+ REFAC: Locale Hardening
            # If no name is provided, FORCE the internal English type name to avoid "Küre", "Würfel" etc.
            target_name = params.get("object_name") or params.get("name")
            if not target_name:
                # e.g. "Sphere" instead of localized default
                target_name = p_type.title().replace("_", " ")

            obj.name = target_name

            # V1.0.0: Update semantic memory
            try:
                sem = get_semantic_memory()
                sem.initialize()
                sem.set_last_created(obj.name)
                # Auto-tag based on primitive type
                if p_type in ["CUBE", "SPHERE", "CYLINDER", "PLANE", "TORUS"]:
                    sem.tag_object(obj.name, "primitive_shape", confidence=0.9, source="auto")
            except Exception:
                pass  # Semantic memory is optional

            # V1.0.0: Standardized response with ResponseBuilder
            return ResponseBuilder.success(
                handler="manage_modeling",
                action="ADD_PRIMITIVE",
                data={
                    "object_name": obj.name,
                    "primitive_type": p_type,
                    "scale": list(cast(Iterable[float], obj.scale)),
                    "location": list(cast(Iterable[float], obj.location)),
                    "rotation": list(cast(Iterable[float], obj.rotation_euler)),
                },
                affected_objects=[{"name": obj.name, "type": "MESH", "changes": ["created"]}],
                next_steps=[
                    {
                        "description": "Apply modifiers to refine geometry",
                        "suggested_tool": "manage_modeling",
                        "suggested_action": "ADD_MODIFIER",
                    },
                    {
                        "description": "Edit mesh in edit mode",
                        "suggested_tool": "manage_modeling",
                        "suggested_action": "EDIT_MESH",
                    },
                ],
            )
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action="ADD_PRIMITIVE",
                error_code="EXECUTION_ERROR",
                message=str(e),
                recoverable=False,
                suggestion="Check primitive type and parameters",
                next_steps=[
                    {
                        "description": "Try with different parameters",
                        "suggested_tool": "manage_modeling",
                        "suggested_action": "ADD_PRIMITIVE",
                    }
                ],
            )

    # Resolve Object
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name) if obj_name else bpy.context.active_object
    if not obj:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action=action,
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: '{obj_name}'",
            suggestion="Check object name or select an active object",
        )

    # MODIFIERS
    if action == ModelingAction.ADD_MODIFIER.value:
        m_type = params.get("modifier_type")
        if not m_type:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action="ADD_MODIFIER",
                error_code="MISSING_PARAMETER",
                message="Missing required parameter: 'modifier_type'",
                suggestion="Specify modifier_type (e.g., SUBSURF, BEVEL, ARRAY, MIRROR)",
            )
        mod = obj.modifiers.new(name=m_type.title(), type=m_type)

        m_params = params.get("modifier_params", {})
        for k, v in m_params.items():
            if hasattr(mod, k):
                try:
                    # If the property is a PointerProperty pointing to an Object, we must resolve it.
                    # Mypy doesn't know about bl_rna structure details heavily dynamically
                    prop_rna = (
                        getattr(mod.bl_rna.properties, k, None) if hasattr(mod, "bl_rna") else None
                    )
                    if (
                        prop_rna
                        and getattr(prop_rna, "type", "") == "POINTER"
                        and getattr(prop_rna, "fixed_type", "") == "Object"
                    ):
                        target_obj = resolve_name(v)  # Resolve string name to object
                        if target_obj:
                            setattr(mod, k, target_obj)
                        else:
                            print(
                                f"[MCP] Warning: Could not resolve object '{v}' for modifier '{k}'"
                            )
                    else:
                        # Standard Set
                        setattr(mod, k, v)
                except Exception as e:
                    print(f"[MCP] Warning: Failed to set modifier param '{k}': {e}")
        # V1.0.0: Standardized response
        return ResponseBuilder.success(
            handler="manage_modeling",
            action="ADD_MODIFIER",
            data={
                "object_name": obj.name,
                "modifier_name": mod.name,
                "modifier_type": m_type,
                "parameters_applied": list(m_params.keys()),
            },
            affected_objects=[
                {"name": obj.name, "type": obj.type, "changes": [f"modifier_added:{mod.name}"]}
            ],
            next_steps=[
                {
                    "description": "Apply modifier to make changes permanent",
                    "suggested_tool": "manage_modeling",
                    "suggested_action": "APPLY_MODIFIER",
                }
            ],
        )

    if action == ModelingAction.APPLY_MODIFIER.value:
        m_name = params.get("modifier_name")
        if not m_name:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action="APPLY_MODIFIER",
                error_code="MISSING_PARAMETER",
                message="Missing required parameter: 'modifier_name'",
                suggestion="Specify the name of the modifier to apply",
            )
        bpy.context.view_layer.objects.active = obj
        try:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.object.modifier_apply(modifier=m_name)

            # V1.0.0: Standardized response
            return ResponseBuilder.success(
                handler="manage_modeling",
                action="APPLY_MODIFIER",
                data={"object_name": obj.name, "modifier_applied": m_name},
                affected_objects=[
                    {"name": obj.name, "type": obj.type, "changes": [f"modifier_applied:{m_name}"]}
                ],
                undo_info={
                    "undo_steps": 1,
                    "undo_message": f"Apply Modifier {m_name}",
                    "backup_created": False,
                },
            )
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action="APPLY_MODIFIER",
                error_code="EXECUTION_ERROR",
                message=str(e),
                suggestion="Ensure modifier exists and object is active",
            )

    # 4. EDIT MESH
    if action == ModelingAction.EDIT_MESH.value:
        if obj.type != "MESH":
            return ResponseBuilder.error(
                handler="manage_modeling",
                action="EDIT_MESH",
                error_code="WRONG_OBJECT_TYPE",
                message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
                suggestion="Select a mesh object for mesh editing operations",
            )

        op = params.get("mesh_operation")
        ep = params.get("edit_params", {})

        # High Mode Safety: Use safe_mode wrapper
        success, msg = safe_mode("EDIT", obj.name)
        if not success:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action="EDIT_MESH",
                error_code="MODE_SWITCH_FAILED",
                message=f"Failed to switch to EDIT mode: {msg}",
                suggestion="Ensure the object is not hidden or locked",
            )

        try:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                # Select all first for operations that need selection
                safe_ops.mesh.select_all(action="SELECT")

                if op == "EXTRUDE":
                    safe_ops.mesh.extrude_context()
                    offset = ep.get("offset", (0, 0, 0.1))
                    safe_ops.transform.translate(value=offset)
                elif op == "INSET":
                    safe_ops.mesh.inset(thickness=ep.get("thickness", 0.01))
                elif op in ["BEVEL", "CHAMFER"]:
                    safe_ops.mesh.bevel(
                        offset=ep.get("offset", 0.1), segments=ep.get("segments", 1)
                    )
                elif op == "SUBDIVIDE":
                    safe_ops.mesh.subdivide(number_cuts=ep.get("cuts", 1))
                elif op in ["LOOP_CUT", "EDGE_LOOP"]:
                    cuts = ep.get("cuts", 1)
                    safe_ops.mesh.subdivide(number_cuts=cuts, quadcorner="INNERVERT")
                    return {
                        "success": True,
                        "operation": op,
                        "note": "Loop cut replaced with subdivide for safety",
                    }
                elif op == "DELETE":
                    safe_ops.mesh.delete(type=ep.get("type", "VERT"))
                elif op == "FILL":
                    safe_ops.mesh.fill()
                elif op in ["MERGE", "WELD"]:
                    safe_ops.mesh.remove_doubles(threshold=ep.get("distance", 0.0001))
                elif op == "SMOOTH":
                    safe_ops.mesh.faces_shade_smooth()
                elif op == "AUTO_SMOOTH":
                    from ..core.versioning import BlenderCompatibility

                    if BlenderCompatibility.use_auto_smooth_modifier():
                        mod_gn = obj.modifiers.new(name="Smooth by Angle", type="NODES")
                        # We need to cast to Any or specific Nodes modifier type if possible, but 'NODES' returns Modifier in stubs
                        # cast(Any, mod_gn) to access 'node_group'
                        cast(Any, mod_gn).node_group = bpy.data.node_groups.get("Smooth by Angle")
                        if not cast(Any, mod_gn).node_group:
                            pass
                    else:
                        # Fallback for older Blender versions, check if property exists on mesh
                        if hasattr(obj.data, "use_auto_smooth"):
                            setattr(obj.data, "use_auto_smooth", True)
                elif op == "RECALCULATE_NORMALS":
                    safe_ops.mesh.normals_make_consistent(inside=False)

            return {"success": True, "operation": op}
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action="EDIT_MESH",
                error_code="EXECUTION_ERROR",
                message=f"Mesh edit operation failed: {str(e)}",
            )
        finally:
            # High Mode Safety: Always return to object mode safely
            safe_mode("OBJECT", obj.name)

    # 5. PRESETS
    if action == ModelingAction.APPLY_PRESET.value:
        pset = params.get("preset_name")
        if pset == "SMOOTH_SUBD":
            mod_sub = cast("SubsurfModifier", obj.modifiers.new("Subsurf", "SUBSURF"))
            mod_sub.levels = 2
            if hasattr(obj.data, "polygons"):
                for p in cast(Any, obj.data).polygons:
                    p.use_smooth = True
        elif pset == "WIREFRAME":
            obj.modifiers.new("Wire", "WIREFRAME")
        elif pset == "WIREFRAME_THICK":
            mod_wire = cast("WireframeModifier", obj.modifiers.new("Wire", "WIREFRAME"))
            mod_wire.thickness = 0.05
            mod_wire.use_boundary = True
            mod_wire.use_replace = False
        elif pset == "SMOOTH_LAPLACIAN":
            mod_lap = cast(
                "LaplacianSmoothModifier", obj.modifiers.new("Laplacian Smooth", "LAPLACIANSMOOTH")
            )
            mod_lap.iterations = 5
            mod_lap.lambda_factor = 0.5
        elif pset == "SOLIDIFY":
            mod_sol = cast("SolidifyModifier", obj.modifiers.new("Solidify", "SOLIDIFY"))
            mod_sol.thickness = 0.01
        elif pset == "MIRROR_X":
            mod_mir = cast("MirrorModifier", obj.modifiers.new("Mirror", "MIRROR"))
            mod_mir.use_axis[0] = True
        return {"success": True, "preset": pset}

    # 5.5 PLACEMENT & ALIGNMENT
    if action == ModelingAction.PRECISE_PLACEMENT.value:
        location = params.get("location")
        rotation = params.get("rotation")
        scale = params.get("scale")
        if location:
            obj.location = tuple(location)
        if rotation:
            obj.rotation_euler = tuple(rotation)
        if scale:
            obj.scale = tuple(scale)
        return ResponseBuilder.success(
            handler="manage_modeling",
            action="PRECISE_PLACEMENT",
            data={"object": obj.name, "location": location, "rotation": rotation, "scale": scale},
            affected_objects=[
                {"name": obj.name, "type": obj.type, "changes": ["transforms_updated"]}
            ],
        )

    if action == ModelingAction.ALIGN_TO_TARGET.value:
        target_name = (
            params.get("target")
            or params.get("edit_params", {}).get("target")
            or params.get("modifier_params", {}).get("object")
        )
        target = resolve_name(target_name)
        if not target:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action="ALIGN_TO_TARGET",
                error_code="OBJECT_NOT_FOUND",
                message="Target object not found for alignment",
            )

        alignment = params.get("edit_params", {}).get("alignment", "CENTER")
        if alignment == "CENTER":
            obj.location = target.location.copy()

        return ResponseBuilder.success(
            handler="manage_modeling",
            action="ALIGN_TO_TARGET",
            data={"object": obj.name, "target": target.name, "alignment": alignment},
            affected_objects=[
                {"name": obj.name, "type": obj.type, "changes": ["aligned_to_target"]}
            ],
        )

    if action == ModelingAction.SET_OFFSET.value:
        offset = params.get("edit_params", {}).get("offset", [0, 0, 0])
        try:
            obj.location[0] += offset[0]
            obj.location[1] += offset[1]
            obj.location[2] += offset[2]
        except (IndexError, TypeError):
            pass

        return ResponseBuilder.success(
            handler="manage_modeling",
            action="SET_OFFSET",
            data={"object": obj.name, "offset": offset},
            affected_objects=[{"name": obj.name, "type": obj.type, "changes": ["location_offset"]}],
        )

    # 6. BOOLEAN OPERATIONS
    if action.startswith("BOOLEAN_") or action.startswith("SMART_BOOLEAN_"):
        is_smart = "SMART" in action
        mode = action.replace("SMART_", "").split("_")[1]  # UNION, DIFFERENCE, INTERSECT

        target_name = params.get("object_name")  # The main object
        tool_name = params.get("modifier_params", {}).get("object")  # The cutter/addition

        if not tool_name:
            # Fallback: check edit_params for 'target'
            tool_name = params.get("edit_params", {}).get("target")

        if not target_name or not tool_name:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action=action,
                error_code="MISSING_PARAMETER",
                message="Boolean operations require 'object_name' and 'modifier_params.object' (the cutter)",
                suggestion="Provide both the base object and the boolean tool object",
            )

        base_obj = resolve_name(target_name)
        tool_obj = resolve_name(tool_name)

        if not base_obj or not tool_obj:
            return ResponseBuilder.error(
                handler="manage_modeling",
                action=action,
                error_code="OBJECT_NOT_FOUND",
                message=f"Boolean object not found: base='{target_name}', tool='{tool_name}'",
                suggestion="Verify both object names exist in the scene",
            )

        mod = base_obj.modifiers.new(name="Boolean", type="BOOLEAN")
        mod.operation = mode
        mod.object = tool_obj

        # Smart Solver Strategy
        # FAST is better for performance, EXACT is better for complex geometry
        mod.solver = "FAST"

        # Auto-apply for destructive workflow if requested
        apply = params.get("apply", True)

        if is_smart or apply:
            bpy.context.view_layer.objects.active = base_obj
            try:
                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    safe_ops.object.modifier_apply(modifier=mod.name)
            except Exception as fast_error:
                print(f"[MCP] Boolean FAST solver failed, retrying with EXACT: {fast_error}")
                mod_retry = cast(
                    "BooleanModifier", base_obj.modifiers.new(name="Boolean_Retry", type="BOOLEAN")
                )
                mod_retry.operation = cast(Literal["INTERSECT", "UNION", "DIFFERENCE"], mode)
                mod_retry.object = tool_obj
                mod_retry.solver = "EXACT"
                try:
                    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                        safe_ops.object.modifier_apply(modifier=mod_retry.name)
                except Exception as exact_error:
                    return ResponseBuilder.error(
                        handler="manage_modeling",
                        action=action,
                        error_code="EXECUTION_ERROR",
                        message=f"Boolean operation failed with both FAST and EXACT solvers: {str(exact_error)}",
                        suggestion="Check geometry validity — overlapping or non-manifold meshes may cause boolean failures",
                    )

            # Often we want to delete or hide the cutter
            try:
                bpy.data.objects.remove(tool_obj, do_unlink=True)
            except:
                pass  # Already gone?

            return {
                "success": True,
                "operation": action,
                "message": "Smart Boolean applied and tool object removed",
            }

        return {"success": True, "operation": action, "modifier": mod.name}

    return ResponseBuilder.error(
        handler="manage_modeling",
        action=action,
        error_code="INVALID_ACTION",
        message=f"Unknown action: '{action}'",
        suggestion="Valid actions: ADD_PRIMITIVE, TRANSFORM, ADD_MODIFIER, APPLY_MODIFIER, EDIT_MESH, APPLY_PRESET, BOOLEAN_UNION/DIFFERENCE/INTERSECT, VALIDATE, PREVIEW, COMMIT, QUERY_SEMANTIC, TAG_OBJECT",
    )


# =============================================================================
# V1.0.0: VALIDATION-FIRST WORKFLOW IMPLEMENTATION
# =============================================================================


def _handle_validate(validate_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate parameters for a target action without side effects.

    Returns structured validation report with:
    - valid: bool - whether params are valid
    - errors: list - detailed error messages
    - warnings: list - non-critical issues
    - normalized_params: cleaned parameters ready for use
    - estimated_impact: {vertices, faces, modifiers} affected
    """
    target_action = validate_params.get("target_action")

    if not target_action:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="VALIDATE",
            error_code="MISSING_PARAMETER",
            message="validate_params must include 'target_action'",
            recoverable=True,
        )

    errors: List[str] = []
    warnings: List[str] = []
    normalized: Dict[str, Any] = {}

    # Primitive type validation
    if target_action == "ADD_PRIMITIVE":
        p_type = validate_params.get("primitive_type", "CUBE").upper()
        synonym_map = {
            "BOX": "CUBE",
            "BALL": "SPHERE",
            "UV_SPHERE": "SPHERE",
            "TUBE": "CYLINDER",
            "QUAD": "PLANE",
            "SUZANNE": "MONKEY",
            "DONUT": "TORUS",
        }
        normalized["primitive_type"] = synonym_map.get(p_type, p_type)
        valid_primitives = ["CUBE", "SPHERE", "CYLINDER", "PLANE", "MONKEY", "TORUS"]
        if normalized["primitive_type"] not in valid_primitives:
            errors.append(f"Invalid primitive_type: {p_type}")

    # Object name resolution validation
    obj_name = validate_params.get("object_name")
    if obj_name:
        obj = resolve_name(obj_name)
        if obj:
            normalized["object_name"] = obj.name  # Use resolved name
            # Check if operation is compatible with object type
            if target_action in [
                ModelingAction.EDIT_MESH.value,
                ModelingAction.ADD_MODIFIER.value,
                ModelingAction.APPLY_MODIFIER.value,
            ]:
                if obj.type != "MESH":
                    errors.append(f"Operation '{target_action}' requires MESH, got {obj.type}")
        else:
            if target_action != "ADD_PRIMITIVE":  # ADD_PRIMITIVE creates new object
                warnings.append(f"Object '{obj_name}' not found, will use active object")

    # Modifier type validation
    if target_action == "ADD_MODIFIER":
        m_type = validate_params.get("modifier_type")
        if not m_type:
            errors.append("modifier_type is required for ADD_MODIFIER")
        else:
            normalized["modifier_type"] = m_type.upper()

    # Boolean validation
    if "BOOLEAN" in target_action:
        base = validate_params.get("object_name")
        tool = validate_params.get("modifier_params", {}).get("object")
        if not base:
            errors.append("object_name (base object) is required for boolean operations")
        if not tool:
            errors.append("modifier_params.object (tool object) is required for boolean operations")
        if base and tool:
            base_obj = resolve_name(base)
            tool_obj = resolve_name(tool)
            if not base_obj:
                errors.append(f"Base object '{base}' not found")
            if not tool_obj:
                errors.append(f"Tool object '{tool}' not found")
            if base_obj and tool_obj:
                # Check for self-intersection
                if base_obj == tool_obj:
                    errors.append("Base and tool objects cannot be the same")

    # Build validation response
    is_valid = len(errors) == 0

    return ResponseBuilder.validation_report(
        handler="manage_modeling",
        action="VALIDATE",
        target_action=target_action,
        valid=is_valid,
        errors=errors,
        warnings=warnings,
        normalized_params=normalized if is_valid else None,
        next_steps=[
            (
                {
                    "description": "Preview the operation",
                    "suggested_action": "PREVIEW",
                    "suggested_params": {"preview_params": validate_params},
                    "condition": "if validation passed",
                }
                if is_valid
                else {
                    "description": "Fix validation errors",
                    "suggested_action": "",
                    "suggestion": "Review and correct the reported errors",
                }
            )
        ],
    )


def _handle_preview(preview_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate operation and return expected results without side effects.

    Returns preview data with:
    - simulation_result: expected outcome
    - affected_objects: objects that would be modified
    - geometry_changes: {vertices_before, vertices_after, faces_before, faces_after}
    - warnings: potential issues detected
    """
    target_action = preview_params.get("target_action")

    if not target_action:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="PREVIEW",
            error_code="MISSING_PARAMETER",
            message="preview_params must include 'target_action'",
            recoverable=True,
        )

    # First validate
    validation = _handle_validate(preview_params)
    if not validation.get("valid", False):
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="PREVIEW",
            error_code="VALIDATION_FAILED",
            message="Cannot preview: validation failed",
            details={"validation_errors": validation.get("errors", [])},
            recoverable=True,
            suggestion="Fix validation errors before previewing",
        )

    # Simulate operation
    simulation: Dict[str, Any] = {
        "action": target_action,
        "would_create_objects": [],
        "would_modify_objects": [],
        "would_delete_objects": [],
        "geometry_changes": {},
        "modifiers_added": [],
        "estimated_time_ms": 0,
    }

    obj_name = preview_params.get("object_name")
    obj = resolve_name(obj_name) if obj_name else bpy.context.active_object

    if target_action == "ADD_PRIMITIVE":
        p_type = preview_params.get("primitive_type", "CUBE").upper()
        simulation["would_create_objects"].append(
            {
                "name": preview_params.get("object_name") or p_type.title(),
                "type": "MESH",
                "estimated_vertices": {
                    "CUBE": 8,
                    "SPHERE": 482,
                    "CYLINDER": 64,
                    "PLANE": 4,
                    "MONKEY": 500,
                    "TORUS": 576,
                }.get(p_type, 8),
                "estimated_faces": {
                    "CUBE": 6,
                    "SPHERE": 512,
                    "CYLINDER": 32,
                    "PLANE": 1,
                    "MONKEY": 250,
                    "TORUS": 576,
                }.get(p_type, 6),
            }
        )
        simulation["estimated_time_ms"] = 10

    elif target_action == "ADD_MODIFIER":
        m_type = preview_params.get("modifier_type", "SUBSURF")
        if obj and obj.type == "MESH":
            mesh_data = getattr(obj, "data", None)
            if (
                mesh_data is None
                or not hasattr(mesh_data, "vertices")
                or not hasattr(mesh_data, "polygons")
            ):
                return ResponseBuilder.error(
                    handler="manage_modeling",
                    action="PREVIEW",
                    error_code="NO_MESH_DATA",
                    message=f"Object '{obj.name}' has no mesh data",
                    recoverable=True,
                )
            verts = len(mesh_data.vertices)
            faces = len(mesh_data.polygons)
            simulation["would_modify_objects"].append(
                {"name": obj.name, "changes": [f"modifier_added:{m_type}"]}
            )
            # Estimate geometry impact
            if m_type == "SUBSURF":
                levels = preview_params.get("modifier_params", {}).get("levels", 2)
                multiplier = 4**levels
                simulation["geometry_changes"][obj.name] = {
                    "vertices_before": verts,
                    "vertices_after": verts * multiplier,
                    "faces_before": faces,
                    "faces_after": faces * multiplier,
                }
            simulation["modifiers_added"].append(m_type)
        simulation["estimated_time_ms"] = 50

    elif "BOOLEAN" in target_action:
        base = preview_params.get("object_name")
        tool = preview_params.get("modifier_params", {}).get("object")
        base_obj = resolve_name(base) if base else None
        tool_obj = resolve_name(tool) if tool else None
        if base_obj:
            simulation["would_modify_objects"].append(
                {"name": base_obj.name, "changes": ["boolean_operation", f"tool_used:{tool}"]}
            )
        if tool_obj and preview_params.get("apply", True):
            simulation["would_delete_objects"].append(tool_obj.name)
        simulation["estimated_time_ms"] = 200
        simulation["warnings"] = ["Boolean operations are computationally expensive"]

    elif target_action == "EDIT_MESH":
        op = preview_params.get("mesh_operation")
        if obj and obj.type == "MESH":
            mesh_data = getattr(obj, "data", None)
            if (
                mesh_data is None
                or not hasattr(mesh_data, "vertices")
                or not hasattr(mesh_data, "polygons")
            ):
                return ResponseBuilder.error(
                    handler="manage_modeling",
                    action="PREVIEW",
                    error_code="NO_MESH_DATA",
                    message=f"Object '{obj.name}' has no mesh data",
                    recoverable=True,
                )
            verts = len(mesh_data.vertices)
            faces = len(mesh_data.polygons)
            simulation["would_modify_objects"].append(
                {"name": obj.name, "changes": [f"mesh_edited:{op}"]}
            )
            # Rough estimates
            if op == "EXTRUDE":
                simulation["geometry_changes"][obj.name] = {
                    "vertices_change": "+100% (duplicated)",
                    "faces_change": "+50% (new sides)",
                }
            elif op == "SUBDIVIDE":
                cuts = preview_params.get("edit_params", {}).get("cuts", 1)
                simulation["geometry_changes"][obj.name] = {
                    "faces_change": f"×{4**cuts} (subdivision)"
                }
        simulation["estimated_time_ms"] = 30

    return ResponseBuilder.preview_report(
        handler="manage_modeling",
        action="PREVIEW",
        target_action=target_action,
        simulation=simulation,
        normalized_params=validation.get("normalized_params"),
        next_steps=[
            {
                "description": "Execute the operation",
                "suggested_action": "COMMIT",
                "suggested_params": {"commit_params": preview_params},
                "warning": "This will modify your scene",
            },
            {
                "description": "Re-validate with different parameters",
                "suggested_action": "VALIDATE",
                "suggested_params": {"validate_params": preview_params},
            },
        ],
    )


def _handle_commit(commit_params: Dict[str, Any], skip_backup: bool = False) -> Dict[str, Any]:
    """
    Execute validated and previewed operation.

    Optional dry-run first, then commit.
    Includes automatic backup unless skip_backup=True.
    """
    target_action: Optional[str] = commit_params.get("target_action")

    if not target_action:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="COMMIT",
            error_code="MISSING_PARAMETER",
            message="commit_params must include 'target_action'",
            recoverable=True,
        )

    # Validate first (always)
    validation: Dict[str, Any] = _handle_validate(commit_params)
    if not validation.get("valid", False):
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="COMMIT",
            error_code="VALIDATION_FAILED",
            message="Cannot commit: validation failed",
            details={"validation_errors": validation.get("errors", [])},
            recoverable=True,
        )

    # Check for dry-run mode
    if commit_params.get("dry_run"):
        preview: Dict[str, Any] = _handle_preview(commit_params)
        return ResponseBuilder.success(
            handler="manage_modeling",
            action="COMMIT",
            data={
                "dry_run": True,
                "preview": preview.get("simulation"),
                "message": "Dry run complete. Remove 'dry_run' to execute.",
            },
        )

    # Create backup point (unless skipped)
    backup_info: Optional[Dict[str, Any]] = None
    if not skip_backup:
        try:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.ed.undo_push(message=f"Before {target_action}")
            backup_info = {
                "undo_point_created": True,
                "undo_message": f"Before {target_action}",
                "recovery_available": True,
            }
        except Exception as e:
            backup_info = {
                "undo_point_created": False,
                "warning": f"Could not create undo point: {e}",
            }

    # Execute the actual action
    # We call manage_modeling recursively with the target action
    result: Dict[str, Any] = _manage_modeling_impl(**commit_params)

    # Enhance result with commit metadata
    if isinstance(result, dict) and result.get("success"):
        result["commit_metadata"] = {
            "validated": True,
            "backup_info": backup_info,
            "execution_mode": "commit",
        }
        # Add undo information
        if backup_info and backup_info.get("undo_point_created"):
            result["undo_info"] = {
                "undo_steps": 1,
                "undo_message": f"Undo {target_action}",
                "backup_created": True,
            }

    if isinstance(result, dict):
        return result
    return ResponseBuilder.error(  # type: ignore[unreachable]
        handler="manage_modeling",
        action="COMMIT",
        error_code="INVALID_RESPONSE",
        message="Commit action returned non-dict response",
        recoverable=False,
    )


# =============================================================================
# V1.0.0: SEMANTIC SCENE MEMORY HANDLERS
# =============================================================================


def _handle_query_semantic(semantic_tag: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query scene using semantic tags instead of exact names.

    Examples:
        "hero_character" → main character object
        "main_camera" → primary camera
        "ground_plane" → floor/ground
        "lights" → all light objects
        "selected_objects" → current selection
    """
    if not semantic_tag:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="QUERY_SEMANTIC",
            error_code="MISSING_PARAMETER",
            message="semantic_tag is required",
            recoverable=True,
            suggestion="Use tags like 'hero_character', 'main_camera', 'ground_plane'",
        )

    try:
        sem: "SemanticSceneMemory" = get_semantic_memory()
        sem.initialize()

        # Try single object resolution
        obj: Optional[bpy.types.Object] = sem.resolve(semantic_tag)
        if obj:
            sem.update_access(obj.name)
            return ResponseBuilder.success(
                handler="manage_modeling",
                action="QUERY_SEMANTIC",
                data={
                    "semantic_tag": semantic_tag,
                    "resolved_object": obj.name,
                    "object_type": obj.type,
                    "match_type": "single",
                },
                affected_objects=[{"name": obj.name, "type": obj.type}],
            )

        # Try multiple objects
        objects: List[bpy.types.Object] = sem.resolve_multiple(semantic_tag)
        if objects:
            return ResponseBuilder.success(
                handler="manage_modeling",
                action="QUERY_SEMANTIC",
                data={
                    "semantic_tag": semantic_tag,
                    "resolved_count": len(objects),
                    "resolved_objects": [o.name for o in objects],
                    "match_type": "multiple",
                },
                affected_objects=[{"name": o.name, "type": o.type} for o in objects],
            )

        # Tag exists but no matching objects
        tag_info: Dict[str, Any] = sem.get_tag_info(semantic_tag)
        if tag_info.get("auto_detected"):
            return ResponseBuilder.success(
                handler="manage_modeling",
                action="QUERY_SEMANTIC",
                data={
                    "semantic_tag": semantic_tag,
                    "resolved_object": None,
                    "tag_info": tag_info,
                    "match_type": "none",
                    "message": f"Tag '{semantic_tag}' is valid but no matching objects found",
                },
                warnings=[
                    {
                        "message": f"No objects match semantic tag '{semantic_tag}'",
                        "suggestion": "Create an object or use TAG_OBJECT to assign this tag",
                    }
                ],
            )

        # Unknown tag
        all_tags: List[str] = sem.list_all_tags()
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="QUERY_SEMANTIC",
            error_code="SEMANTIC_TAG_NOT_FOUND",
            message=f"Unknown semantic tag: '{semantic_tag}'",
            recoverable=True,
            suggestion=f"Known tags include: {', '.join(all_tags[:10])}...",
            details={
                "requested_tag": semantic_tag,
                "available_tags_count": len(all_tags),
                "similar_tags": [
                    t
                    for t in all_tags
                    if semantic_tag.lower() in t.lower() or t.lower() in semantic_tag.lower()
                ][:5],
            },
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="QUERY_SEMANTIC",
            error_code="EXECUTION_ERROR",
            message=str(e),
            recoverable=False,
        )


def _handle_tag_object(
    obj_name: Optional[str], tag_name: Optional[str], confidence: float = 1.0
) -> Dict[str, Any]:
    """
    Manually assign a semantic tag to an object.

    This allows users to mark objects for semantic retrieval:
        TAG_OBJECT("MyCharacter", "hero_character")
        TAG_OBJECT("Sun.001", "key_light")
    """
    if not obj_name or not tag_name:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="TAG_OBJECT",
            error_code="MISSING_PARAMETER",
            message="Both object_name and tag_name are required",
            recoverable=True,
        )

    obj = resolve_name(obj_name)
    if not obj:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="TAG_OBJECT",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{obj_name}' not found",
            recoverable=True,
        )

    try:
        sem = get_semantic_memory()
        sem.initialize()
        sem.tag_object(obj.name, tag_name, confidence=confidence, source="user")

        return ResponseBuilder.success(
            handler="manage_modeling",
            action="TAG_OBJECT",
            data={
                "object_name": obj.name,
                "tag_assigned": tag_name,
                "confidence": confidence,
                "object_tags": sem.get_tags(obj.name),
            },
            affected_objects=[
                {"name": obj.name, "type": obj.type, "changes": [f"tag_added:{tag_name}"]}
            ],
            next_steps=[
                {
                    "description": f"Use '{tag_name}' to reference this object",
                    "suggested_tool": "any",
                    "example": f"object_name='{tag_name}' instead of object_name='{obj.name}'",
                }
            ],
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_modeling",
            action="TAG_OBJECT",
            error_code="EXECUTION_ERROR",
            message=str(e),
            recoverable=False,
        )


def _handle_place_relative_to(params: Dict[str, Any]) -> Dict[str, Any]:
    from ..core.thread_safety import execute_on_main_thread
    from ..core.resolver import resolve_name
    from mathutils import Vector

    def execution() -> Dict[str, Any]:
        obj_to_move_name = params.get("object_to_move")
        anchor_name = params.get("anchor_object")
        anchor_point = params.get("anchor_point", "center")
        snap_point = params.get("snap_point", "center")
        offset = float(params.get("offset", 0.0))

        if not obj_to_move_name or not anchor_name:
            return cast(
                Dict[str, Any],
                ResponseBuilder.error(
                    handler="manage_modeling",
                    action="PLACE_RELATIVE_TO",
                    error_code="MISSING_PARAMETER",
                    message="'object_to_move' and 'anchor_object' are required.",
                ),
            )

        obj = resolve_name(str(obj_to_move_name))
        anchor = resolve_name(str(anchor_name))

        if not obj or not anchor:
            return cast(
                Dict[str, Any],
                ResponseBuilder.error(
                    handler="manage_modeling",
                    action="PLACE_RELATIVE_TO",
                    error_code="OBJECT_NOT_FOUND",
                    message="Objects not found.",
                ),
            )

        # RSK-161 mitigation: Immediate evaluation
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        anchor_eval = anchor.evaluated_get(depsgraph)

        def _get_local_axis_from_string(point_str: str) -> Vector:
            axis_map = {
                "positive_x": Vector((1.0, 0.0, 0.0)),
                "negative_x": Vector((-1.0, 0.0, 0.0)),
                "positive_y": Vector((0.0, 1.0, 0.0)),
                "negative_y": Vector((0.0, -1.0, 0.0)),
                "positive_z": Vector((0.0, 0.0, 1.0)),
                "negative_z": Vector((0.0, 0.0, -1.0)),
            }
            p_lower = point_str.lower()
            for key, vec in axis_map.items():
                if key in p_lower:
                    return vec.copy()

            # ADR-016-02 Fallback to +Z to prevent Null Vector
            import logging

            logger = logging.getLogger("manage_modeling")
            logger.warning(
                f"Unknown axis string '{point_str}' in PLACE_RELATIVE_TO, falling back to +Z"
            )
            return Vector((0.0, 0.0, 1.0))

        def get_local_point_in_world(eval_obj: Any, point_type: str) -> Vector:
            # 1. Gather all 8 corners strictly in local space
            bounds = [Vector(c) for c in eval_obj.bound_box]
            min_x = min(c.x for c in bounds)
            max_x = max(c.x for c in bounds)
            min_y = min(c.y for c in bounds)
            max_y = max(c.y for c in bounds)
            min_z = min(c.z for c in bounds)
            max_z = max(c.z for c in bounds)

            # 2. ADR-016-01: Scale Sign Inversion Limit Swaping
            scale = eval_obj.matrix_world.to_scale()
            if scale.x < 0:
                min_x, max_x = max_x, min_x
            if scale.y < 0:
                min_y, max_y = max_y, min_y
            if scale.z < 0:
                min_z, max_z = max_z, min_z

            center_local = Vector(((min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2))
            p = point_type.lower()

            target_local = center_local.copy()

            if p != "center":
                if "positive_x" in p:
                    target_local.x = max_x
                elif "negative_x" in p:
                    target_local.x = min_x

                if "positive_y" in p:
                    target_local.y = max_y
                elif "negative_y" in p:
                    target_local.y = min_y

                if "positive_z" in p:
                    target_local.z = max_z
                elif "negative_z" in p:
                    target_local.z = min_z

            # 3. Last step: Transform local point to world via matrix_world exactly
            return cast(Vector, eval_obj.matrix_world @ target_local)

        try:
            anchor_world_pos = get_local_point_in_world(anchor_eval, str(anchor_point))
            snap_world_pos = get_local_point_in_world(obj_eval, str(snap_point))

            # 4. Mathutils Extract Anchor's Normal explicitly
            local_anchor_axis = _get_local_axis_from_string(anchor_point)
            anchor_rot_mat = anchor_eval.matrix_world.to_3x3()
            anchor_world_dir = (anchor_rot_mat @ local_anchor_axis).normalized()

            # 5. Base move (brings snap point exactly on top of anchor point)
            translation_base = anchor_world_pos - snap_world_pos

            # 6. Final offset mathematically follows the direction normal.
            if offset != 0.0:
                translation = translation_base + (anchor_world_dir * offset)
            else:
                translation = translation_base

            obj.location += translation

            # ADR-016-03: Concurrency Update & Depsgraph Refresh
            bpy.context.view_layer.update()
            bpy.context.evaluated_depsgraph_get()

            return cast(
                Dict[str, Any],
                ResponseBuilder.success(
                    handler="manage_modeling",
                    action="PLACE_RELATIVE_TO",
                    data={
                        "moved_object": obj.name,
                        "translation_vector": [
                            round(translation.x, 4),
                            round(translation.y, 4),
                            round(translation.z, 4),
                        ],
                    },
                ),
            )
        except Exception as e:
            return cast(
                Dict[str, Any],
                ResponseBuilder.error(
                    handler="manage_modeling",
                    action="PLACE_RELATIVE_TO",
                    error_code="MATH_ERROR",
                    message=str(e),
                ),
            )

    return cast(Dict[str, Any], execute_on_main_thread(execution))
