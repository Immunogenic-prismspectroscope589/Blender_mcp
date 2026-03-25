"""
Unity Export Handler - V1.0.0 Modularized

Export and validation tools for Unity workflow:
- FBX Export (Unity optimized)
- Collection export
- LOD chain export
- Pre-export validation
- Preparation (transforms, pivots)

Part of 'unity_handler' modularization.
"""

import os
from typing import Any

try:
    import bpy
    import mathutils

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.thread_safety import execute_on_main_thread, ensure_main_thread, thread_safe
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.logging_config import get_logger
from ..core.smart_mode_manager import SmartModeManager
from ..dispatcher import register_handler
from ..utils.path import get_safe_path

logger = get_logger()


def is_relative_path(filepath: str) -> bool:
    """Check if path is relative"""
    return not os.path.isabs(filepath)


def get_shared_root() -> str:
    """Get shared root directory"""
    return os.environ.get("MCP_SHARED_ROOT", "C:/Tools/my_mcp/shared")


@register_handler(
    "prepare_for_unity",
    schema={
        "type": "object",
        "title": "Prepare for Unity",
        "description": "Prepare objects for Unity export by applying transforms and adjusting origins.",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["prepare_for_unity"],
                "default": "prepare_for_unity",
                "description": "Action to perform",
            },
            "object_name": {"type": "string", "description": "Name of the object to prepare."},
            "operations": {
                "type": "array",
                "items": {"type": "string", "enum": ["apply_all_transforms", "origin_to_bottom"]},
                "description": "List of operations to perform.",
            },
        },
        "required": ["action", "object_name"],
    },
    category="unity",
)
@ensure_main_thread
def prepare_for_unity(**params: Any) -> dict[str, Any]:
    """
    Prepare objects for Unity export.

    FIXED: Enhanced error handling and mode safety
    """
    object_name = params.get("object_name")
    operations = params.get("operations", ["apply_all_transforms"])

    # In mock/headless quality environments there is no real mode/context.
    if getattr(bpy, "is_mock", False):
        return {
            "success": True,
            "object": object_name,
            "operations": [],
            "skipped": True,
            "reason": "mock_bpy_environment",
        }

    obj = bpy.data.objects.get(object_name)
    if not obj:
        return {"error": f"Object not found: {object_name}"}

    results = []

    try:
        for op in operations:
            if op == "apply_all_transforms":
                with SmartModeManager().mode_context(obj, "OBJECT"):
                    ContextManagerV3.deselect_all_objects()
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    with ContextManagerV3.temp_override(
                        area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                    ):
                        safe_ops.object.transform_apply(location=True, rotation=True, scale=True)
                    results.append("Applied all transforms")

            elif op == "origin_to_bottom":
                with SmartModeManager().mode_context(obj, "OBJECT"):
                    bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
                    min_z = min(v.z for v in bbox)
                    center_x = (min(v.x for v in bbox) + max(v.x for v in bbox)) / 2
                    center_y = (min(v.y for v in bbox) + max(v.y for v in bbox)) / 2

                    bpy.context.scene.cursor.location = (center_x, center_y, min_z)
                    ContextManagerV3.deselect_all_objects()
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    with ContextManagerV3.temp_override(
                        area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                    ):
                        safe_ops.object.origin_set(type="ORIGIN_CURSOR")
                    results.append("Origin set to bottom")

    except Exception as e:
        logger.error(f"prepare_for_unity failed: {e}", exc_info=True)
        return {"error": f"Operation failed: {str(e)}", "completed_operations": results}

    return {"success": True, "object": object_name, "operations": results}


@register_handler(
    "export_unity_fbx",
    schema={
        "type": "object",
        "title": "Export Unity FBX",
        "description": "Export selected objects or scene to FBX with Unity-compatible settings (Y-up, -Z forward, apply transform).",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["export_unity_fbx"],
                "default": "export_unity_fbx",
                "description": "Action to perform",
            },
            "filepath": {
                "type": "string",
                "description": "Output path for the FBX file (absolute or relative to specialized root).",
            },
            "export_mode": {
                "type": "string",
                "enum": ["selected", "all"],
                "default": "selected",
                "description": "Export selected objects only or entire scene.",
            },
        },
        "required": ["action", "filepath"],
    },
    category="unity",
)
@thread_safe(timeout=300.0)
def export_unity_fbx(**params: Any) -> dict[str, Any]:
    """
    Export FBX optimized for Unity.

    FIXED: Thread-safe export with enhanced error handling
    """
    filepath = params.get("filepath")
    export_mode = params.get("export_mode", "selected")

    if not filepath:
        return {
            "error": "filepath parameter is required. Please specify where to save the FBX file."
        }

    # Check if relative path
    if is_relative_path(filepath):
        base_path = get_shared_root()
        filepath = os.path.join(base_path, filepath)

    # Sanitize Path
    filepath = get_safe_path(filepath)
    filepath = os.path.normpath(filepath)
    directory = os.path.dirname(filepath)

    # Ensure directory exists
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception as e:
        return {"error": f"Cannot create directory {directory}: {str(e)}"}

    def export_operation() -> dict[str, Any]:
        original_selection = list(bpy.context.selected_objects)

        try:
            ContextManagerV3.deselect_all_objects()

            if export_mode == "selected":
                for obj in original_selection:
                    if obj and obj.name in bpy.data.objects:
                        obj.select_set(True)
            elif export_mode == "all":
                for obj in bpy.context.scene.objects:
                    if obj.type in ["MESH", "ARMATURE", "EMPTY"]:
                        obj.select_set(True)

            # Check if anything selected
            selected = list(bpy.context.selected_objects)
            if not selected:
                return {"error": "No objects selected for export"}

            # Bug 10 Fix: Enforce active object in view layer physically before export context override
            if selected:
                bpy.context.view_layer.objects.active = selected[0]

            with ContextManagerV3.temp_override(
                area_type="VIEW_3D",
                active_object=selected[0] if selected else None,
                selected_objects=selected,
            ):
                safe_ops.export_scene.fbx(
                    filepath=filepath,
                    use_selection=True,
                    axis_forward="-Z",
                    axis_up="Y",
                    global_scale=1.0,
                    apply_unit_scale=True,
                    use_mesh_modifiers=True,
                    use_tspace=True,
                    mesh_smooth_type="FACE",
                    bake_anim=True,
                    add_leaf_bones=False,
                    primary_bone_axis="Y",
                    secondary_bone_axis="X",
                    path_mode="AUTO",
                )

            exported_objects = [obj.name for obj in bpy.context.selected_objects]
            return {"success": True, "filepath": filepath, "objects": exported_objects}

        finally:
            ContextManagerV3.deselect_all_objects()
            for obj in original_selection:
                if obj and obj.name in bpy.data.objects:
                    obj.select_set(True)

    # Execute on main thread
    try:
        # Strict typing: Cast the result to dict
        result = execute_on_main_thread(export_operation, timeout=300.0)
        if isinstance(result, dict):
            return result
        return {"error": "Invalid result type from main thread execution"}
    except Exception as e:
        return {"error": f"Export failed: {str(e)}"}


def _resolve_collection(name: str) -> Any:
    """
    Collection'ı 4 farklı yöntemle arar.
    Root scene collection için özel durum ele alınır.
    """
    import bpy

    # Yöntem 1: Root scene collection özel isimleri
    ROOT_ALIASES = {
        "scene collection",
        "master collection",
        "scene_collection",
        "master_collection",
        "",
    }
    if name.lower().strip() in ROOT_ALIASES:
        return bpy.context.scene.collection

    # Yöntem 2: bpy.data.collections direkt lookup (case-sensitive)
    coll = bpy.data.collections.get(name)
    if coll:
        return coll

    # Yöntem 3: Case-insensitive arama
    name_lower = name.lower()
    for coll_name, coll_obj in bpy.data.collections.items():
        if coll_name.lower() == name_lower:
            return coll_obj

    # Yöntem 4: Scene hierarchy'de recursive BFS
    import collections
    from typing import Deque, Set

    queue: Deque[Any] = collections.deque([bpy.context.scene.collection])
    visited: Set[str] = set()
    while queue:
        curr = queue.popleft()
        if curr.name in visited:
            continue
        visited.add(curr.name)
        if curr.name.lower() == name_lower:
            return curr
        if getattr(curr, "children", None):
            for child in curr.children:
                queue.append(child)

    return None


def _list_all_collection_names() -> list[str]:
    """Hata mesajında kullanıcıya gösterilecek mevcut collection listesi."""
    import bpy

    names = [bpy.context.scene.collection.name]  # Root her zaman dahil
    names += list(bpy.data.collections.keys())
    return names


@register_handler(
    "export_unity_collection",
    schema={
        "type": "object",
        "title": "Export Unity Collection",
        "description": "Export an entire collection as a single FBX (useful for prefabs).",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["export_unity_collection"],
                "default": "export_unity_collection",
                "description": "Action to perform",
            },
            "collection_name": {
                "type": "string",
                "description": "Name of the collection to export.",
            },
            "filepath": {
                "type": "string",
                "description": "Output path. If omitted, uses default models directory.",
            },
        },
        "required": ["action", "collection_name"],
    },
    category="unity",
)
def export_unity_collection(**params: Any) -> dict[str, Any]:
    """
    Export collection as Unity prefab.

    FIXED: Unity export with _resolve_collection for Scene Collection mapping
    """
    collection_name = params.get("collection_name") or params.get("collection")
    filepath = params.get("filepath")

    collection = _resolve_collection(collection_name or "")

    if collection is None:
        available = _list_all_collection_names()
        return {
            "error_code": "COLLECTION_NOT_FOUND",
            "message": f"Collection bulunamadı: '{collection_name}'. Mevcut collection'lar: {available}",
            "error": f"Collection not found: {collection_name}",
        }

    if not filepath:
        base_path = get_shared_root()
        filepath = os.path.join(base_path, "models", f"{collection_name}.fbx")

    def export_operation() -> dict[str, Any]:
        original_selection = list(bpy.context.selected_objects)

        try:
            ContextManagerV3.deselect_all_objects()

            # Bug 8 Fix: BFS Iterative loop safely collecting all objects
            # without recursive limits (OOM/Stack Overflow) in massive nested hierarchies.
            import collections
            from typing import Set, Deque

            queue: Deque[Any] = collections.deque([collection])
            visited_collections: Set[str] = set()

            while queue:
                curr_col = queue.popleft()
                if curr_col.name in visited_collections:
                    continue
                visited_collections.add(curr_col.name)

                # Enqueue children collections
                if getattr(curr_col, "children", None):
                    for child_col in curr_col.children:
                        if child_col and child_col.name not in visited_collections:
                            queue.append(child_col)

                # Fetch objects in current tier
                if getattr(curr_col, "objects", None):
                    for obj in curr_col.objects:
                        if (
                            obj
                            and obj.name in bpy.data.objects
                            and obj.type in ["MESH", "ARMATURE", "EMPTY"]
                        ):
                            obj.select_set(True)

            selected = list(bpy.context.selected_objects)
            if not selected:
                return {"error": f"No exportable objects in collection: {collection_name}"}

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Bug 10 Fix: Enforce active object in view layer physically
            if selected:
                bpy.context.view_layer.objects.active = selected[0]

            with ContextManagerV3.temp_override(
                area_type="VIEW_3D",
                active_object=selected[0] if selected else None,
                selected_objects=selected,
            ):
                safe_ops.export_scene.fbx(
                    filepath=filepath,
                    use_selection=True,
                    axis_forward="-Z",
                    axis_up="Y",
                    global_scale=1.0,
                    apply_unit_scale=True,
                    use_mesh_modifiers=True,
                    use_tspace=True,
                )

            return {"success": True, "filepath": filepath, "collection": collection_name}

        finally:
            ContextManagerV3.deselect_all_objects()
            for obj in original_selection:
                if obj and obj.name in bpy.data.objects:
                    obj.select_set(True)

    # Execute on main thread
    try:
        result = execute_on_main_thread(export_operation, timeout=300.0)
        if isinstance(result, dict):
            return result
        return {"error": "Invalid result type from main thread execution"}
    except Exception as e:
        return {"error": f"Collection export failed: {str(e)}"}


@register_handler(
    "validate_for_unity",
    schema={
        "type": "object",
        "title": "Validate for Unity",
        "description": "Check objects for Unity compatibility issues (N-gons, missing UVs, unapplied scale, high poly count).",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["validate_for_unity"],
                "default": "validate_for_unity",
                "description": "Action to perform",
            },
            "object_name": {
                "type": "string",
                "description": "Specific object to validate. If omitted, checks selected objects.",
            },
        },
        "required": ["action"],
    },
    category="unity",
)
@ensure_main_thread
def validate_for_unity(**params: Any) -> dict[str, Any]:
    """Validate objects for Unity export"""
    object_name = params.get("object_name")

    if object_name:
        obj = bpy.data.objects.get(object_name)
        objects = [obj] if obj else []
    else:
        objects = list(bpy.context.selected_objects)
        if not objects:
            active = bpy.context.active_object
            if active:
                objects = [active]

    errors = []
    warnings = []
    info = []

    for obj in objects:
        # ADR-011: Strict Type Guard
        # Replaces: if not obj or obj.type != "MESH":
        if not obj or not isinstance(obj.data, bpy.types.Mesh):
            continue

        if obj.scale != mathutils.Vector((1, 1, 1)):
            if any(abs(s - 1.0) > 0.001 for s in obj.scale[:]):
                warnings.append(f"{obj.name}: Scale not applied ({obj.scale})")

        if obj.data and len(obj.data.uv_layers) == 0:
            errors.append(f"{obj.name}: No UV map")

        if obj.data:
            ngons = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)
            if ngons > 0:
                warnings.append(f"{obj.name}: {ngons} ngons (prefer quads/tris)")

        if obj.data:
            tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
            info.append(f"{obj.name}: ~{tris} triangles")
            if tris > 65000:
                errors.append(f"{obj.name}: {tris} tris exceeds Unity limit (65k)")

    return {"errors": errors, "warnings": warnings, "info": info}


@register_handler(
    "export_lod_chain",
    schema={
        "type": "object",
        "title": "Export LOD Chain",
        "description": "Export multiple objects as an LOD chain (LOD0, LOD1, etc.) for Unity.",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["export_lod_chain"],
                "default": "export_lod_chain",
                "description": "Action to perform",
            },
            "base_name": {"type": "string", "description": "Base filename for export."},
            "lod_objects": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Map of LOD levels to object names (e.g. {'LOD0': 'Chair', 'LOD1': 'Chair_Low'}).",
            },
        },
        "required": ["action", "base_name", "lod_objects"],
    },
    category="unity",
)
@thread_safe(timeout=120.0)
def export_lod_chain(**params: Any) -> dict[str, Any]:
    """Export LOD chain for Unity"""
    base_name = params.get("base_name")
    lod_objects = params.get("lod_objects", {})

    if not base_name:
        return {"error": "base_name is required"}

    results = {}
    shared_root = get_shared_root()

    for lod_level, obj_name in lod_objects.items():
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            results[lod_level] = {"error": f"Object not found: {obj_name}"}
            continue

        filepath = f"{shared_root}/models/{base_name}_{lod_level}.fbx"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        def export_single_lod(_obj: Any = obj, _filepath: str = filepath) -> dict[str, Any]:
            ContextManagerV3.deselect_all_objects()
            _obj.select_set(True)
            bpy.context.view_layer.objects.active = _obj

            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=_obj, selected_objects=[_obj]
            ):
                safe_ops.export_scene.fbx(
                    filepath=_filepath,
                    use_selection=True,
                    axis_forward="-Z",
                    axis_up="Y",
                    global_scale=1.0,
                )

            # ADR-011: Strict Type Guard for Tris Calculation
            if _obj.data and isinstance(_obj.data, bpy.types.Mesh):
                tris = sum(len(p.vertices) - 2 for p in _obj.data.polygons)
            else:
                tris = 0
            return {"success": True, "filepath": _filepath, "tris": tris}

        try:
            result = export_single_lod()
            results[lod_level] = result
        except Exception as e:
            results[lod_level] = {"error": str(e)}

    return {"success": True, "base_name": base_name, "lods": results}
