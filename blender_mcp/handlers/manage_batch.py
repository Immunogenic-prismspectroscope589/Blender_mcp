"""Batch Operations Handler for Blender MCP - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

from ..core.execution_engine import safe_ops

from typing import Dict, List, Any
import re

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
from ..dispatcher import register_handler


from ..core.parameter_validator import validated_handler
from ..core.enums import BatchAction
from ..core.thread_safety import ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_batch",
    actions=[a.value for a in BatchAction],
    category="general",
    priority=45,
    schema={
        "type": "object",
        "title": "Batch Operations (STANDARD)",
        "description": (
            "STANDARD — Process multiple objects simultaneously: batch rename, duplicate, "
            "set material, add modifier, set visibility, apply transforms.\n\n"
            "Use selection list or regex pattern to target objects. Much faster than "
            "looping individual manage_objects calls.\n"
            "ACTIONS: RENAME, DUPLICATE, SET_MATERIAL, ADD_MODIFIER, REMOVE_MODIFIER, "
            "SET_VISIBILITY, APPLY_TRANSFORMS, DELETE"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(BatchAction, "Batch operation"),
            "selection": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of object names to process (empty = all selected)",
            },
            "pattern": {"type": "string", "description": "Regex pattern for name matching"},
            "name_prefix": {"type": "string", "description": "Prefix for rename operation"},
            "name_suffix": {"type": "string", "description": "Suffix for rename operation"},
            "duplicate_count": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 100,
                "description": "Number of duplicates to create",
            },
            "duplicate_linked": {
                "type": "boolean",
                "default": False,
                "description": "Create linked duplicates",
            },
            "duplicate_offset": {
                "type": "array",
                "items": {"type": "number"},
                "default": [1.0, 0.0, 0.0],
                "description": "Offset for each duplicate [x, y, z]",
            },
            "modifier_type": {"type": "string", "description": "Modifier type for add/remove"},
            "material_name": {"type": "string", "description": "Material to assign"},
            "decimate_ratio": {"type": "number", "default": 0.5, "minimum": 0, "maximum": 1},
            "visibility": {"type": "boolean", "description": "Visibility state"},
            "object_type": {"type": "string", "description": "Object type for selection"},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in BatchAction])
def manage_batch(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Batch process multiple objects for efficient workflows.
    """

    # Get target objects
    if params.get("selection"):
        targets = [bpy.data.objects.get(name) for name in params["selection"]]
        targets = [o for o in targets if o is not None]
    elif params.get("pattern"):
        pattern = re.compile(params["pattern"])
        targets = [o for o in bpy.data.objects if pattern.search(o.name)]
    else:
        targets = list(bpy.context.selected_objects)

    if not targets:
        return ResponseBuilder.error(
            handler="manage_batch",
            action=action,
            error_code="OBJECT_NOT_FOUND",
            message="No objects selected or matched",
        )

    results: Dict[str, List[Any]] = {"processed": [], "skipped": [], "errors": []}

    # 1. RENAME
    if not action:
        return ResponseBuilder.error(
            handler="manage_batch",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == BatchAction.RENAME.value:
        prefix = params.get("name_prefix", "")
        suffix = params.get("name_suffix", "")

        for i, obj in enumerate(targets):
            old_name = obj.name
            new_name = f"{prefix}{obj.name}{suffix}"

            # Handle duplicates
            base_name = new_name
            counter = 1
            while new_name in bpy.data.objects and bpy.data.objects[new_name] != obj:
                new_name = f"{base_name}.{counter:03d}"
                counter += 1

            obj.name = new_name
            results["processed"].append({"old": old_name, "new": new_name})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="RENAME",
            data={"renamed": len(results["processed"]), "results": results},
        )

    # 2. DELETE
    elif action == BatchAction.DELETE.value:
        for obj in targets:
            try:
                name = obj.name
                bpy.data.objects.remove(obj, do_unlink=True)
                results["processed"].append(name)
            except Exception as e:
                results["errors"].append({"object": obj.name, "error": str(e)})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="DELETE",
            data={"deleted": len(results["processed"]), "errors": results["errors"]},
        )

    # 3. DUPLICATE / COPY / CLONE
    elif action in (BatchAction.DUPLICATE.value, BatchAction.COPY.value, BatchAction.CLONE.value):
        """
        Duplicate selected objects with smart naming and offset.
        Supports: duplicate_count, duplicate_linked, duplicate_offset
        """
        count = max(1, min(100, int(params.get("duplicate_count", 1))))
        linked = params.get("duplicate_linked", False)
        offset = params.get("duplicate_offset", [1.0, 0.0, 0.0])

        # Ensure offset is a list of 3 numbers
        if not isinstance(offset, (list, tuple)) or len(offset) < 3:
            offset = [1.0, 0.0, 0.0]

        for obj in targets:
            for i in range(count):
                try:
                    # Create duplicate
                    if linked:
                        new_obj = obj.copy()
                        new_obj.data = obj.data  # Share data
                    else:
                        new_obj = obj.copy()
                        if obj.data:
                            new_obj.data = obj.data.copy()

                    # Generate unique name
                    base_name = obj.name
                    if "_dup" not in base_name and "_copy" not in base_name:
                        new_name = f"{base_name}_dup"
                    else:
                        new_name = base_name

                    # Ensure unique name
                    counter = 1
                    final_name = new_name
                    while final_name in bpy.data.objects:
                        final_name = f"{new_name}.{counter:03d}"
                        counter += 1

                    new_obj.name = final_name

                    # Link to collection
                    bpy.context.collection.objects.link(new_obj)

                    # Apply offset
                    new_obj.location = (
                        obj.location[0] + offset[0] * (i + 1),
                        obj.location[1] + offset[1] * (i + 1),
                        obj.location[2] + offset[2] * (i + 1),
                    )

                    results["processed"].append(
                        {"original": obj.name, "duplicate": new_obj.name, "index": i + 1}
                    )

                except Exception as e:
                    results["errors"].append({"object": obj.name, "index": i + 1, "error": str(e)})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="DUPLICATE",
            data={
                "duplicated": len(results["processed"]),
                "count_per_object": count,
                "linked": linked,
                "results": results["processed"],
                "errors": results["errors"] if results["errors"] else None,
            },
        )

    # 4. APPLY_MODIFIERS
    elif action == BatchAction.APPLY_MODIFIERS.value:
        modifier_type = params.get("modifier_type")

        for obj in targets:
            if obj.type != "MESH":
                results["skipped"].append({"object": obj.name, "reason": "Not a mesh"})
                continue

            bpy.context.view_layer.objects.active = obj
            applied = []

            for mod in list(obj.modifiers):
                if modifier_type and mod.type != modifier_type:
                    continue

                try:
                    with ContextManagerV3.temp_override(
                        area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                    ):
                        safe_ops.object.modifier_apply(modifier=mod.name)
                    applied.append(mod.name)
                except Exception as e:
                    results["errors"].append(
                        {"object": obj.name, "modifier": mod.name, "error": str(e)}
                    )

            if applied:
                results["processed"].append({"object": obj.name, "modifiers": applied})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="APPLY_MODIFIERS",
            data={"applied": len(results["processed"]), "results": results},
        )

    # 4. REMOVE_MODIFIERS
    elif action == BatchAction.REMOVE_MODIFIERS.value:
        modifier_type = params.get("modifier_type")

        for obj in targets:
            removed = []
            for mod in list(obj.modifiers):
                if modifier_type and mod.type != modifier_type:
                    continue
                obj.modifiers.remove(mod)
                removed.append(mod.name)

            if removed:
                results["processed"].append({"object": obj.name, "removed": removed})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="REMOVE_MODIFIERS",
            data={"processed": len(results["processed"])},
        )

    # 5. ADD_MODIFIER
    elif action == BatchAction.ADD_MODIFIER.value:
        modifier_type = params.get("modifier_type")
        if not modifier_type:
            return ResponseBuilder.error(
                handler="manage_batch",
                action="ADD_MODIFIER",
                error_code="MISSING_PARAMETER",
                message="modifier_type is required",
            )

        for obj in targets:
            if obj.type != "MESH":
                continue

            mod = obj.modifiers.new(name=modifier_type, type=modifier_type)

            # Set common properties
            if modifier_type == "DECIMATE" and params.get("decimate_ratio"):
                mod.ratio = params["decimate_ratio"]  # type: ignore
            elif modifier_type == "SUBSURF":
                mod.levels = params.get("subsurf_levels", 2)  # type: ignore
            elif modifier_type == "BEVEL":
                mod.width = params.get("bevel_width", 0.02)  # type: ignore

            results["processed"].append({"object": obj.name, "modifier": mod.name})

        return ResponseBuilder.success(
            handler="manage_batch", action="ADD_MODIFIER", data={"added": len(results["processed"])}
        )

    # 6. SET_MATERIAL / ASSIGN
    elif action in (BatchAction.SET_MATERIAL.value, BatchAction.ASSIGN.value):
        mat_name = params.get("material_name")
        if not mat_name:
            return ResponseBuilder.error(
                handler="manage_batch",
                action=action,
                error_code="MISSING_PARAMETER",
                message="material_name is required",
            )

        mat = bpy.data.materials.get(mat_name)
        if not mat:
            return ResponseBuilder.error(
                handler="manage_batch",
                action=action,
                error_code="NO_MATERIAL",
                message=f"Material not found: {mat_name}",
                details={"material_name": mat_name},
            )

        slot_index = params.get("slot_index", 0)
        clear_existing = params.get("clear_existing", False)

        for obj in targets:
            if obj.type != "MESH":
                results["skipped"].append({"object": obj.name, "reason": "Not a mesh"})
                continue

            # Clear existing if requested
            if clear_existing and obj.data.materials:  # type: ignore
                obj.data.materials.clear()  # type: ignore

            # Ensure enough material slots
            while len(obj.material_slots) <= slot_index:
                obj.data.materials.append(None)  # type: ignore

            obj.material_slots[slot_index].material = mat
            results["processed"].append(obj.name)

        action_name = "assigned" if action == BatchAction.ASSIGN.value else "material_set"
        return ResponseBuilder.success(
            handler="manage_batch",
            action=action,
            data={action_name: len(results["processed"]), "skipped": len(results["skipped"])},
        )

    # 7. CLEAR_MATERIALS
    elif action == BatchAction.CLEAR_MATERIALS.value:
        for obj in targets:
            obj.data.materials.clear()  # type: ignore
            results["processed"].append(obj.name)

        return ResponseBuilder.success(
            handler="manage_batch",
            action="CLEAR_MATERIALS",
            data={"cleared": len(results["processed"])},
        )

    # 8. SMART_UV_UNWRAP
    elif action == BatchAction.SMART_UV_UNWRAP.value:
        angle_limit = params.get("angle_limit", 66.0)
        island_margin = params.get("island_margin", 0.02)

        for obj in targets:
            if obj.type != "MESH":
                continue

            bpy.context.view_layer.objects.active = obj
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
            ):
                safe_ops.object.mode_set(mode="EDIT")
                safe_ops.mesh.select_all(action="SELECT")

                try:
                    safe_ops.uv.smart_project(angle_limit=angle_limit, island_margin=island_margin)
                    results["processed"].append(obj.name)
                except Exception as e:
                    results["errors"].append({"object": obj.name, "error": str(e)})
                finally:
                    safe_ops.object.mode_set(mode="OBJECT")

        return ResponseBuilder.success(
            handler="manage_batch",
            action="SMART_UV_UNWRAP",
            data={"unwrapped": len(results["processed"])},
        )

    # 9. TRIANGULATE
    elif action == BatchAction.TRIANGULATE.value:
        for obj in targets:
            if obj.type != "MESH":
                continue

            # Add triangulate modifier and apply
            mod = obj.modifiers.new(name="Triangulate", type="TRIANGULATE")
            mod.quad_method = "BEAUTY"  # type: ignore
            mod.ngon_method = "BEAUTY"  # type: ignore

            bpy.context.view_layer.objects.active = obj
            try:
                with ContextManagerV3.temp_override(
                    area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                ):
                    safe_ops.object.modifier_apply(modifier=mod.name)
                results["processed"].append(obj.name)
            except Exception as e:
                obj.modifiers.remove(mod)
                results["errors"].append({"object": obj.name, "error": str(e)})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="TRIANGULATE",
            data={"triangulated": len(results["processed"])},
        )

    # 10. DECIMATE
    elif action == BatchAction.DECIMATE.value:
        ratio = params.get("decimate_ratio", 0.5)

        for obj in targets:
            if obj.type != "MESH":
                continue

            mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
            mod.ratio = ratio  # type: ignore

            bpy.context.view_layer.objects.active = obj
            try:
                with ContextManagerV3.temp_override(
                    area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                ):
                    safe_ops.object.modifier_apply(modifier=mod.name)
                results["processed"].append(obj.name)
            except Exception as e:
                obj.modifiers.remove(mod)
                results["errors"].append({"object": obj.name, "error": str(e)})

        return ResponseBuilder.success(
            handler="manage_batch", action="DECIMATE", data={"decimated": len(results["processed"])}
        )

    # 11. ORIGIN_TO_GEOMETRY
    elif action == BatchAction.ORIGIN_TO_GEOMETRY.value:
        for obj in targets:
            bpy.context.view_layer.objects.active = obj
            try:
                with ContextManagerV3.temp_override(
                    area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                ):
                    safe_ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
                results["processed"].append(obj.name)
            except Exception as e:
                results["errors"].append({"object": obj.name, "error": str(e)})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="ORIGIN_TO_GEOMETRY",
            data={"processed": len(results["processed"])},
        )

    # 12. APPLY_SCALE
    elif action == BatchAction.APPLY_SCALE.value:
        for obj in targets:
            bpy.context.view_layer.objects.active = obj
            try:
                with ContextManagerV3.temp_override(
                    area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                ):
                    safe_ops.object.transform_apply(scale=True, location=False, rotation=False)
                results["processed"].append(obj.name)
            except Exception as e:
                results["errors"].append({"object": obj.name, "error": str(e)})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="APPLY_SCALE",
            data={"processed": len(results["processed"])},
        )

    # 13. MAKE_INSTANCES_REAL
    elif action == BatchAction.MAKE_INSTANCES_REAL.value:
        for obj in targets:
            if not obj.instance_type == "COLLECTION":
                results["skipped"].append(
                    {"object": obj.name, "reason": "Not a collection instance"}
                )
                continue

            bpy.context.view_layer.objects.active = obj
            try:
                with ContextManagerV3.temp_override(
                    area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                ):
                    safe_ops.object.duplicates_make_real()
                results["processed"].append(obj.name)
            except Exception as e:
                results["errors"].append({"object": obj.name, "error": str(e)})

        return ResponseBuilder.success(
            handler="manage_batch",
            action="MAKE_INSTANCES_REAL",
            data={"realized": len(results["processed"])},
        )

    # 14. JOIN_MESHES
    elif action == BatchAction.JOIN_MESHES.value:
        mesh_objects = [o for o in targets if o.type == "MESH"]

        if len(mesh_objects) < 2:
            return ResponseBuilder.error(
                handler="manage_batch",
                action="JOIN_MESHES",
                error_code="VALIDATION_ERROR",
                message="Need at least 2 mesh objects to join",
            )

        # Select all target meshes
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=mesh_objects[0], selected_objects=mesh_objects
        ):
            ContextManagerV3.deselect_all_objects()
            for obj in mesh_objects:
                obj.select_set(True)

            # Set active to first
            bpy.context.view_layer.objects.active = mesh_objects[0]

            try:
                safe_ops.object.join()
            except Exception as e:
                return ResponseBuilder.error(
                    handler="manage_batch",
                    action="JOIN_MESHES",
                    error_code="EXECUTION_ERROR",
                    message=f"Join failed: {str(e)}",
                    details={"exception": str(e)},
                )

        return ResponseBuilder.success(
            handler="manage_batch",
            action="JOIN_MESHES",
            data={"joined_into": mesh_objects[0].name, "joined_count": len(mesh_objects)},
        )

    # 15. PARENT_TO_EMPTY
    elif action == BatchAction.PARENT_TO_EMPTY.value:
        empty_name = params.get("empty_name", "Batch_Parent")

        # Create or get empty
        empty = bpy.data.objects.get(empty_name)
        if not empty:
            empty = bpy.data.objects.new(empty_name, None)
            bpy.context.collection.objects.link(empty)
            empty.empty_display_size = 2

        for obj in targets:
            if obj == empty:
                continue
            obj.parent = empty
            results["processed"].append(obj.name)

        return ResponseBuilder.success(
            handler="manage_batch",
            action="PARENT_TO_EMPTY",
            data={"parented": len(results["processed"]), "parent": empty_name},
        )

    # 16. SET_VISIBILITY
    elif action == BatchAction.SET_VISIBILITY.value:
        visibility = params.get("visibility", True)

        for obj in targets:
            obj.hide_viewport = not visibility
            obj.hide_render = not visibility
            results["processed"].append(obj.name)

        return ResponseBuilder.success(
            handler="manage_batch",
            action="SET_VISIBILITY",
            data={"visibility_set": len(results["processed"]), "visible": visibility},
        )

    # 17. SELECT_BY_NAME
    elif action == BatchAction.SELECT_BY_NAME.value:
        pattern_str = params.get("pattern")
        if not pattern_str:
            return ResponseBuilder.error(
                handler="manage_batch",
                action="SELECT_BY_NAME",
                error_code="MISSING_PARAMETER",
                message="pattern is required",
            )

        regex = re.compile(str(pattern_str))
        matched = []

        ContextManagerV3.deselect_all_objects()

        for obj in bpy.data.objects:
            if regex.search(obj.name):
                # Isolate visibility to active View Layer
                if not obj.hide_get() and getattr(obj, "visible_get", lambda: True)():
                    try:
                        obj.select_set(True)
                        matched.append(obj.name)
                    except RuntimeError as e:
                        logger.warning(f"Batch select_set failed on {obj.name}: {e}")

        return ResponseBuilder.success(
            handler="manage_batch",
            action="SELECT_BY_NAME",
            data={"matched": len(matched), "selected": matched},
        )

    # 18. SELECT_BY_TYPE
    elif action == BatchAction.SELECT_BY_TYPE.value:
        obj_type = params.get("object_type")
        if not obj_type:
            return ResponseBuilder.error(
                handler="manage_batch",
                action="SELECT_BY_TYPE",
                error_code="MISSING_PARAMETER",
                message="object_type is required",
            )

        ContextManagerV3.deselect_all_objects()

        matched = []

        for obj in bpy.data.objects:
            if obj.type == obj_type:
                # Isolate visibility to active View Layer
                if not obj.hide_get() and getattr(obj, "visible_get", lambda: True)():
                    try:
                        obj.select_set(True)
                        matched.append(obj.name)
                    except RuntimeError as e:
                        logger.warning(f"Batch select_set failed on {obj.name}: {e}")

        return ResponseBuilder.success(
            handler="manage_batch",
            action="SELECT_BY_TYPE",
            data={"matched": len(matched), "selected": matched},
        )

    return ResponseBuilder.error(
        handler="manage_batch",
        action=action,
        error_code="MISSING_PARAMETER",
        message=f"Unknown action: {action}",
    )
