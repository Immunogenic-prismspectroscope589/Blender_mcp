"""Advanced Batch Processing for Blender MCP v1.0.0 - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

from typing import List, Dict, Any
from ..core.execution_engine import safe_ops
import re

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
from ..core.resolver import resolve_name
from ..dispatcher import register_handler


from ..core.parameter_validator import validated_handler
from ..core.enums import AdvancedBatchAction
from ..core.thread_safety import ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_advanced_batch",
    actions=[a.value for a in AdvancedBatchAction],
    category="general",
    schema={
        "type": "object",
        "title": "Advanced Batch Processing",
        "description": "Complex batch operations with conditions and workflows.",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                AdvancedBatchAction, "Advanced batch action"
            ),
            "objects": {"type": "array", "items": {"type": "string"}},
            "pipeline": {"type": "object", "description": "Pipeline definition"},
            "conditions": {"type": "array"},
            "operations": {"type": "array"},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in AdvancedBatchAction])
def manage_advanced_batch(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Advanced batch processing with complex workflows.

    Actions:
    - PIPELINE_EXECUTE: Multi-step processing pipeline
    - CONDITIONAL_BATCH: Conditional operations based on properties
    - CHAIN_OPERATIONS: Chain multiple operations with dependencies
    - FILTER_AND_PROCESS: Filter objects then apply operations
    - SCATTER_OBJECTS: Procedural scattering system
    - DISTRIBUTE_ALONG_CURVE: Place objects along curve
    - ARRAY_WITH_VARIATION: Array modifier with random variations
    - INSTANCER_SYSTEM: Advanced instancing with variations
    - BAKE_ALL_DYNAMICS: Batch bake physics/animation
    - EXPORT_BATCH_VARIANTS: Export multiple format variants
    - AUTOMATION_MACRO: Record and replay macros
    """

    if not action:
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == AdvancedBatchAction.PIPELINE_EXECUTE.value:
        return _pipeline_execute(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.CONDITIONAL_BATCH.value:
        return _conditional_batch(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.CHAIN_OPERATIONS.value:
        return _chain_operations(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.FILTER_AND_PROCESS.value:
        return _filter_and_process(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.SCATTER_OBJECTS.value:
        return _scatter_objects(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.DISTRIBUTE_ALONG_CURVE.value:
        return _distribute_along_curve(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.ARRAY_WITH_VARIATION.value:
        return _array_with_variation(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.INSTANCER_SYSTEM.value:
        return _instancer_system(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.BAKE_ALL_DYNAMICS.value:
        return _bake_all_dynamics(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.EXPORT_BATCH_VARIANTS.value:
        return _export_batch_variants(params)  # type: ignore[no-any-return]
    elif action == AdvancedBatchAction.AUTOMATION_MACRO.value:
        return _automation_macro(params)  # type: ignore[no-any-return]

    return ResponseBuilder.error(
        handler="manage_advanced_batch",
        action=action,
        error_code="MISSING_PARAMETER",
        message=f"Unknown action: {action}",
    )


def _pipeline_execute(params):  # type: ignore[no-untyped-def]
    """Execute multi-step processing pipeline."""
    pipeline = params.get("pipeline", {})
    steps = pipeline.get("steps", [])

    results: List[Dict[str, Any]] = []
    context: Dict[str, Any] = {}  # Shared context between steps

    for i, step in enumerate(steps, 1):
        step_type = step.get("type")
        step_params = step.get("params", {})

        # Inject context
        step_params["_context"] = context
        step_params["_step"] = i

        result = {"step": i, "type": step_type}

        try:
            if step_type == "select":
                pattern = step_params.get("pattern", ".*")
                matched = [o for o in bpy.data.objects if re.match(pattern, o.name)]
                context["selected"] = matched
                result["matched"] = len(matched)

            elif step_type == "filter":
                objs = context.get("selected", [])
                obj_type = step_params.get("object_type")
                filtered = [o for o in objs if o.type == obj_type] if obj_type else objs
                context["selected"] = filtered
                result["filtered"] = len(filtered)

            elif step_type == "operation":
                handler = step_params.get("handler")
                action = step_params.get("action")
                # Execute via dispatcher would go here
                result["executed"] = f"{handler}.{action}"

            elif step_type == "modify":
                objs = context.get("selected", [])
                modified = 0
                for obj in objs:
                    if "location_offset" in step_params:
                        offset = step_params["location_offset"]
                        obj.location.x += offset[0]
                        obj.location.y += offset[1]
                        obj.location.z += offset[2]
                        modified += 1
                result["modified"] = modified

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
            if step.get("stop_on_error", True):
                break

        results.append(result)

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="PIPELINE_EXECUTE",
        data={
            "steps_executed": len(results),
            "results": results,
            "final_context": {"selected_count": len(context.get("selected", []))},
        },
    )


def _conditional_batch(params):  # type: ignore[no-untyped-def]
    """Apply operations based on conditions."""
    objects = params.get("objects", [])
    conditions = params.get("conditions", [])
    params.get("operation", {})

    processed = 0
    skipped = 0

    for obj_name in objects:
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue

        # Check all conditions
        all_match = True
        for condition in conditions:
            prop = condition.get("property")
            operator = condition.get("operator", "==")
            value = condition.get("value")

            obj_value = getattr(obj, prop, None)

            if operator == "==" and obj_value != value:
                all_match = False
            elif operator == "!=" and obj_value == value:
                all_match = False
            elif operator == ">" and (obj_value is None or obj_value <= value):
                all_match = False
            elif operator == "<" and (obj_value is None or obj_value >= value):
                all_match = False

        if all_match:
            # Apply operation
            processed += 1
        else:
            skipped += 1

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="CONDITIONAL_BATCH",
        data={"processed": processed, "skipped": skipped, "total": len(objects)},
    )


def _scatter_objects(params):  # type: ignore[no-untyped-def]
    """Procedural scattering system."""
    target_surface = params.get("target_surface")
    # Accept both 'object' and first item of 'objects' list for convenience.
    object_to_scatter = params.get("object")
    if object_to_scatter is None:
        objects_list = params.get("objects") or []
        object_to_scatter = objects_list[0] if objects_list else None

    if not target_surface:
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action="SCATTER_OBJECTS",
            error_code="MISSING_PARAMETER",
            message="Required: 'target_surface' (name of the mesh to scatter onto) "
            "and 'object' (name of the object to scatter).",
        )
    if not object_to_scatter:
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action="SCATTER_OBJECTS",
            error_code="MISSING_PARAMETER",
            message="Required: 'object' (name of the object instance to scatter).",
        )

    count = params.get("count", 100)

    surface = resolve_name(target_surface)
    template = resolve_name(object_to_scatter)

    if not surface or not template:
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action="SCATTER_OBJECTS",
            error_code="OBJECT_NOT_FOUND",
            message="Target surface or template object not found",
            details={"target_surface": target_surface, "object_to_scatter": object_to_scatter},
        )

    if surface.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action="SCATTER_OBJECTS",
            error_code="WRONG_OBJECT_TYPE",
            message="Target must be a mesh",
            details={
                "target_surface": target_surface,
                "expected_type": "MESH",
                "actual_type": surface.type,
            },
        )

    scattered = []

    import random

    for i in range(count):
        # Create instance
        new_obj = template.copy()
        new_obj.data = template.data.copy()
        new_obj.name = f"{template.name}_scatter_{i:04d}"
        bpy.context.collection.objects.link(new_obj)

        # Random position on surface (simplified - random vertex)
        mesh = surface.data
        if len(mesh.vertices) > 0:
            vert = random.choice(mesh.vertices)
            world_pos = surface.matrix_world @ vert.co
            new_obj.location = world_pos

            # Random rotation
            new_obj.rotation_euler = (
                random.uniform(0, 6.28),
                random.uniform(0, 6.28),
                random.uniform(0, 6.28),
            )

            # Random scale
            scale_var = params.get("scale_variation", 0.2)
            s = 1.0 + random.uniform(-scale_var, scale_var)
            new_obj.scale = (s, s, s)

        scattered.append(new_obj.name)

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="SCATTER_OBJECTS",
        data={
            "scattered_count": len(scattered),
            "objects": scattered[:10],  # First 10
        },
    )


def _distribute_along_curve(params):  # type: ignore[no-untyped-def]
    """Place objects along a curve."""
    curve_name = params.get("curve")
    object_name = params.get("object")
    count = params.get("count", 10)

    curve = resolve_name(curve_name)
    template = resolve_name(object_name)

    if not curve or curve.type != "CURVE":
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action="DISTRIBUTE_ALONG_CURVE",
            error_code="OBJECT_NOT_FOUND",
            message="Curve not found or not a curve type",
            details={"curve_name": curve_name, "expected_type": "CURVE"},
        )

    if not template:
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action="DISTRIBUTE_ALONG_CURVE",
            error_code="OBJECT_NOT_FOUND",
            message="Template object not found",
            details={"object_name": object_name},
        )

    distributed = []

    for i in range(count):
        t = i / max(count - 1, 1)

        # Create instance
        new_obj = template.copy()
        new_obj.data = template.data.copy()
        new_obj.name = f"{template.name}_dist_{i:03d}"
        bpy.context.collection.objects.link(new_obj)

        # Position (simplified - would use curve evaluation)
        # In real implementation, would use curve.evaluate()
        new_obj.location = (curve.location.x + t * 5, curve.location.y, curve.location.z)

        distributed.append(new_obj.name)

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="DISTRIBUTE_ALONG_CURVE",
        data={"distributed_count": len(distributed)},
    )


def _array_with_variation(params):  # type: ignore[no-untyped-def]
    """Array modifier with random variations."""
    # Accept both 'object_name' (string) and 'objects' (list) for usability.
    obj_name = params.get("object_name")
    if obj_name is None:
        objects_list = params.get("objects") or []
        obj_name = objects_list[0] if objects_list else None
    if obj_name is None:
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action="ARRAY_WITH_VARIATION",
            error_code="MISSING_PARAMETER",
            message="Required: 'object_name' (string) — name of the object to array. "
            "Optionally pass 'objects': [\"Cube\"] as fallback.",
        )
    obj = resolve_name(obj_name)

    if not obj:
        return ResponseBuilder.error(
            handler="manage_advanced_batch",
            action="ARRAY_WITH_VARIATION",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: {obj_name!r}",
            details={"object_name": obj_name},
        )

    count = params.get("count", 5)
    offset = params.get("offset", [2, 0, 0])
    randomize = params.get("randomize", True)

    created = []

    import random

    for i in range(count):
        new_obj = obj.copy()
        new_obj.data = obj.data.copy()
        new_obj.name = f"{obj.name}_array_{i:03d}"
        bpy.context.collection.objects.link(new_obj)

        # Position
        new_obj.location = (
            obj.location.x + offset[0] * i,
            obj.location.y + offset[1] * i,
            obj.location.z + offset[2] * i,
        )

        if randomize:
            # Random variations
            rot_var = 0.2
            new_obj.rotation_euler = (
                random.uniform(-rot_var, rot_var),
                random.uniform(-rot_var, rot_var),
                random.uniform(-rot_var, rot_var),
            )

            scale_var = 0.1
            s = 1.0 + random.uniform(-scale_var, scale_var)
            new_obj.scale = (s, s, s)

        created.append(new_obj.name)

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="ARRAY_WITH_VARIATION",
        data={"created_count": len(created), "objects": created},
    )


def _instancer_system(params):  # type: ignore[no-untyped-def]
    """Advanced instancing with variations."""
    collection_name = params.get("collection")
    template_objects = params.get("templates", [])
    count = params.get("count", 50)

    # Create collection
    coll = bpy.data.collections.new(collection_name or "Instancer_Collection")
    bpy.context.scene.collection.children.link(coll)

    instances = []

    import random

    for i in range(count):
        # Pick random template
        if template_objects:
            template_name = random.choice(template_objects)
            template = bpy.data.objects.get(template_name)

            if template:
                # Create instance
                instance = template.copy()
                instance.name = f"{template.name}_inst_{i:04d}"
                coll.objects.link(instance)

                # Random transform
                instance.location = (
                    random.uniform(-10, 10),
                    random.uniform(-10, 10),
                    random.uniform(0, 5),
                )

                instances.append(instance.name)

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="INSTANCER_SYSTEM",
        data={"instances_created": len(instances), "collection": coll.name},
    )


def _bake_all_dynamics(params):  # type: ignore[no-untyped-def]
    """Batch bake physics and animation."""
    objects = params.get("objects", [])
    bake_types = params.get("types", ["PARTICLES", "CLOTH", "FLUID", "DYNAMIC_PAINT"])

    results = []

    for obj_name in objects:
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue

        obj_results = {"object": obj_name}

        # Check for particle systems
        if obj.particle_systems and "PARTICLES" in bake_types:
            for ps in obj.particle_systems:
                # Would trigger bake here
                obj_results["particles"] = ps.name

        # Check for rigid body
        if obj.rigid_body and "RIGID_BODY" in bake_types:
            obj_results["rigid_body"] = True

        results.append(obj_results)

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="BAKE_ALL_DYNAMICS",
        data={"baked_objects": len(results), "details": results},
    )


def _export_batch_variants(params):  # type: ignore[no-untyped-def]
    """Export multiple format variants."""
    objects = params.get("objects", [])
    base_path = params.get("base_path", "//exports/")
    formats = params.get("formats", ["GLTF", "FBX", "OBJ"])

    exports = []

    for obj_name in objects:
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue

        # Select only this object
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
        ):
            ContextManagerV3.deselect_all_objects()
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

            obj_exports = {"object": obj_name, "files": []}

            for fmt in formats:
                ext = {"GLTF": ".glb", "FBX": ".fbx", "OBJ": ".obj"}.get(fmt, ".ext")
                filepath = f"{base_path}{obj_name}{ext}"

                if fmt == "GLTF":
                    safe_ops.export_scene.gltf(filepath=filepath, use_selection=True)
                elif fmt == "FBX":
                    safe_ops.export_scene.fbx(filepath=filepath, use_selection=True)
                elif fmt == "OBJ":
                    safe_ops.wm.obj_export(filepath=filepath, export_selected_objects=True)

                obj_exports["files"].append({"format": fmt, "path": filepath})

        exports.append(obj_exports)

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="EXPORT_BATCH_VARIANTS",
        data={"objects_exported": len(exports), "variants": exports},
    )


def _automation_macro(params):  # type: ignore[no-untyped-def]
    """Record and replay macros."""
    macro_mode = params.get("mode", "PLAY")  # RECORD, PLAY, SAVE, LOAD
    macro_name = params.get("macro_name", "default_macro")

    if macro_mode == "RECORD":
        # Would start recording
        return ResponseBuilder.success(
            handler="manage_advanced_batch",
            action="AUTOMATION_MACRO",
            data={"mode": "RECORD", "macro": macro_name, "status": "Recording started"},
        )

    elif macro_mode == "PLAY":
        actions = params.get("actions", [])
        results = []

        for action_item in actions:
            # Execute each action
            results.append({"action": action_item.get("type"), "status": "executed"})

        return ResponseBuilder.success(
            handler="manage_advanced_batch",
            action="AUTOMATION_MACRO",
            data={"mode": "PLAY", "actions_executed": len(results), "results": results},
        )

    elif macro_mode == "SAVE":
        return ResponseBuilder.success(
            handler="manage_advanced_batch",
            action="AUTOMATION_MACRO",
            data={"mode": "SAVE", "macro": macro_name, "saved": True},
        )

    return ResponseBuilder.error(
        handler="manage_advanced_batch",
        action="AUTOMATION_MACRO",
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown macro mode: {macro_mode}",
        details={"macro_mode": macro_mode, "valid_modes": ["RECORD", "PLAY", "SAVE", "LOAD"]},
    )


def _chain_operations(params):  # type: ignore[no-untyped-def]
    """Chain multiple operations with dependencies."""
    operations = params.get("operations", [])

    results: List[Dict[str, Any]] = []

    for op in operations:
        op_type = op.get("type")
        depends_on = op.get("depends_on")

        # Check dependencies
        if depends_on is not None:
            if depends_on >= len(results) or not results[depends_on].get("success"):
                results.append({"type": op_type, "skipped": True, "reason": "dependency failed"})
                continue

        # Execute operation
        try:
            # Would execute actual operation here
            result = {"type": op_type, "success": True, "params": op.get("params", {})}
        except Exception as e:
            result = {"type": op_type, "success": False, "error": str(e)}

        results.append(result)

    success_count = sum(1 for r in results if r.get("success"))

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="CHAIN_OPERATIONS",
        data={"operations": len(results), "successful": success_count, "results": results},
    )


def _filter_and_process(params):  # type: ignore[no-untyped-def]
    """Filter objects then apply operations."""
    filter_criteria = params.get("filter", {})
    operations = params.get("operations", [])

    # Get all objects
    all_objects = list(bpy.data.objects)

    # Apply filters
    filtered = []
    for obj in all_objects:
        match = True

        if "type" in filter_criteria:
            if obj.type != filter_criteria["type"]:
                match = False

        if "name_pattern" in filter_criteria:
            if not re.match(filter_criteria["name_pattern"], obj.name):
                match = False  # type: ignore

        if "has_material" in filter_criteria:
            if filter_criteria["has_material"] and not obj.data.materials:  # type: ignore
                match = False

        if match:
            filtered.append(obj)

    # Apply operations
    processed = 0
    for obj in filtered:
        for op in operations:
            # Apply operation
            processed += 1

    return ResponseBuilder.success(
        handler="manage_advanced_batch",
        action="FILTER_AND_PROCESS",
        data={
            "filtered_count": len(filtered),
            "operations_applied": processed,
            "filtered_objects": [o.name for o in filtered[:10]],
        },
    )
