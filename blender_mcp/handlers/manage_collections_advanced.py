"""
Advanced Collection & Scene Management Handler for Blender MCP - V1.0.0 Refactored (SSOT)

Safe, thread-aware operations with strict typing and enum-based actions.
Implements Rules 1 (SSOT), 2 (Strict Typing), and 9 (Zero Trust Input).
"""

from typing import Dict, Any, Optional

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..dispatcher import register_handler
from ..core.thread_safety import ensure_main_thread
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger

# SSOT Imports
from ..core.enums import CollectionAction
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_collections_advanced",
    category="general",
    priority=40,
    schema={
        "type": "object",
        "title": "Advanced Collection Manager (STANDARD)",
        "description": (
            "STANDARD — Manage collection hierarchies, view layers, render visibility, "
            "holdout, indirect-only, and asset marking.\n\n"
            "Use to organize scene objects by type/purpose. Collections control render "
            "visibility and can be toggled per view layer.\n"
            "ACTIONS: CREATE, CREATE_HIERARCHY, SET_COLLECTION_VISIBILITY, "
            "SET_RENDER_VISIBILITY, SET_HOLDOUT, CREATE_VIEW_LAYER, MARK_ASSET"
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "CREATE",
                    "CREATE_HIERARCHY",
                    "SET_COLLECTION_VISIBILITY",
                    "SET_COLLECTION_EXCLUDE",
                    "MOVE_TO_COLLECTION_HIERARCHY",
                    "CREATE_VIEW_LAYER",
                    "SET_VIEW_LAYER_VISIBILITY",
                    "COPY_VIEW_LAYER",
                    "SET_RENDER_VISIBILITY",
                    "SET_HOLDOUT",
                    "SET_INDIRECT_ONLY",
                    "CREATE_ASSET",
                    "MARK_ASSET",
                    "CLEAR_ASSET",
                ],
                "description": "Advanced collection operation",
            },
            "collection_name": {"type": "string"},
            "parent_collection": {
                "type": "string",
                "description": "Parent collection name (optional)",
            },
            "hierarchy": {"type": "object", "description": "Nested collection structure"},
            "view_layer": {"type": "string", "description": "View layer name"},
            "object_name": {"type": "string"},
            "visible": {"type": "boolean"},
            "exclude": {"type": "boolean"},
            "holdout": {"type": "boolean"},
            "indirect_only": {"type": "boolean"},
            "asset_type": {
                "type": "string",
                "enum": ["OBJECT", "COLLECTION", "MATERIAL"],
                "description": "Type of asset to create",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for the asset",
            },
        },
        "required": ["action"],
    },
    actions=[
        "CREATE",
        "CREATE_HIERARCHY",
        "SET_COLLECTION_VISIBILITY",
        "SET_COLLECTION_EXCLUDE",
        "MOVE_TO_COLLECTION_HIERARCHY",
        "CREATE_VIEW_LAYER",
        "SET_VIEW_LAYER_VISIBILITY",
        "COPY_VIEW_LAYER",
        "SET_RENDER_VISIBILITY",
        "SET_HOLDOUT",
        "SET_INDIRECT_ONLY",
        "CREATE_ASSET",
        "MARK_ASSET",
        "CLEAR_ASSET",
    ],
)
@ensure_main_thread
def manage_collections_advanced(action: Optional[str] = None, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    """
    Advanced collection and view layer management for complex scenes.
    """
    # 1. Zero Trust Input Validation
    if not action:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=None,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    # Validate Action Enum
    validation_error = ValidationUtils.validate_enum(action, CollectionAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_collections_advanced", action=action
        )

    scene = bpy.context.scene

    try:
        # Dispatch to specific logic blocks
        if action == CollectionAction.CREATE.value:
            return _handle_create_collection(scene, **params)

        elif action == CollectionAction.CREATE_HIERARCHY.value:
            return _handle_create_hierarchy(scene, **params)

        elif action == CollectionAction.SET_COLLECTION_VISIBILITY.value:
            return _handle_visible_set(scene, **params)

        elif action == CollectionAction.SET_COLLECTION_EXCLUDE.value:
            return _handle_exclude_set(scene, **params)

        elif action == CollectionAction.MOVE_TO_COLLECTION_HIERARCHY.value:
            return _handle_move_hierarchy(scene, **params)

        elif action == CollectionAction.CREATE_VIEW_LAYER.value:
            return _handle_create_view_layer(scene, **params)

        elif action == CollectionAction.SET_VIEW_LAYER_VISIBILITY.value:
            return _handle_view_layer_visibility(scene, **params)

        elif action == CollectionAction.COPY_VIEW_LAYER.value:
            return _handle_copy_view_layer(scene, **params)

        elif action == CollectionAction.SET_RENDER_VISIBILITY.value:
            return _handle_render_visibility(scene, **params)

        elif action == CollectionAction.SET_HOLDOUT.value:
            return _handle_holdout(scene, **params)

        elif action == CollectionAction.SET_INDIRECT_ONLY.value:
            return _handle_indirect_only(scene, **params)

        elif action == CollectionAction.CREATE_ASSET.value:
            return _handle_create_asset(**params)

        elif action == CollectionAction.MARK_ASSET.value:
            return _handle_mark_asset(**params)

        elif action == CollectionAction.CLEAR_ASSET.value:
            return _handle_clear_asset(**params)

        else:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=action,
                error_code="INVALID_ACTION",
                message=f"Unknown action: {action}",
            )

    except Exception as e:
        logger.error(f"manage_collections_advanced.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=action,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


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


def _handle_create_collection(scene: Any, **params: Any) -> Dict[str, Any]:
    import bpy

    name = params.get("collection_name") or params.get("name")
    parent_name = params.get("parent", None)
    color_tag = params.get("color_tag", "NONE")  # NONE/RED/ORANGE/YELLOW/GREEN/BLUE/VIOLET/PINK

    if not name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.CREATE.value,
            error_code="MISSING_PARAMETER",
            message="'name' parametresi zorunlu",
        )

    # Duplicate kontrolü
    if bpy.data.collections.get(name):
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.CREATE.value,
            error_code="ALREADY_EXISTS",
            message=f"'{name}' adında bir collection zaten var",
        )

    # Collection oluştur
    new_coll = bpy.data.collections.new(name)

    # Color tag (Blender 3.2+)
    if hasattr(new_coll, "color_tag"):
        new_coll.color_tag = color_tag

    # Parent belirle
    if parent_name:
        parent = _resolve_collection(parent_name)
        if parent is None:
            # Collection oluşturuldu ama parent bulunamadı — root'a bağla
            bpy.context.scene.collection.children.link(new_coll)
            return ResponseBuilder.success(
                handler="manage_collections_advanced",
                action=CollectionAction.CREATE.value,
                data={
                    "collection": name,
                    "parent": bpy.context.scene.collection.name,
                    "warning": f"Parent '{parent_name}' bulunamadı, root'a bağlandı.",
                },
            )
        parent.children.link(new_coll)
    else:
        bpy.context.scene.collection.children.link(new_coll)

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.CREATE.value,
        data={
            "collection": name,
            "parent": parent_name or bpy.context.scene.collection.name,
            "color_tag": color_tag,
        },
    )


def _handle_create_hierarchy(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    hierarchy = params.get("hierarchy", {})
    if not hierarchy:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.CREATE_HIERARCHY.value,
            error_code="MISSING_PARAMETER",
            message="hierarchy structure is required",
        )

    created = []

    def create_recursive(parent_coll, struct, path=""):  # type: ignore[no-untyped-def]
        for name, children in struct.items():
            # Create collection
            if name not in bpy.data.collections:
                new_coll = bpy.data.collections.new(name)
            else:
                new_coll = bpy.data.collections[name]

            if new_coll.name not in parent_coll.children:
                parent_coll.children.link(new_coll)

            created.append(f"{path}/{name}" if path else name)

            # Recurse if children exist
            if isinstance(children, dict) and children:
                create_recursive(new_coll, children, f"{path}/{name}" if path else name)

    # Start from scene collection or specified parent
    parent_name = params.get("parent_collection")
    if parent_name:
        parent = bpy.data.collections.get(parent_name)
        if not parent:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.CREATE_HIERARCHY.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Parent collection not found: {parent_name}",
            )
    else:
        parent = scene.collection

    create_recursive(parent, hierarchy)

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.CREATE_HIERARCHY.value,
        data={"created": len(created), "collections": created},
    )


def _handle_visible_set(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    coll_name = params.get("collection_name")
    visible = params.get("visible", True)

    if not coll_name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_COLLECTION_VISIBILITY.value,
            error_code="MISSING_PARAMETER",
            message="collection_name is required",
        )

    coll = bpy.data.collections.get(coll_name)
    if not coll:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_COLLECTION_VISIBILITY.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Collection not found: {coll_name}",
        )

    coll.hide_viewport = not visible

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.SET_COLLECTION_VISIBILITY.value,
        data={"collection": coll_name, "visible": visible},
    )


def _handle_exclude_set(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    coll_name = params.get("collection_name")
    exclude = params.get("exclude", True)
    view_layer_name = params.get("view_layer")

    if not coll_name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_COLLECTION_EXCLUDE.value,
            error_code="MISSING_PARAMETER",
            message="collection_name is required",
        )

    # Get view layer
    if view_layer_name:
        view_layer = scene.view_layers.get(view_layer_name)
        if not view_layer:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.SET_COLLECTION_EXCLUDE.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"View layer not found: {view_layer_name}",
            )
    else:
        view_layer = bpy.context.view_layer

    # Find layer collection recursive
    def find_layer_collection(layer_coll, name):  # type: ignore[no-untyped-def]
        if layer_coll.collection.name == name:
            return layer_coll
        for child in layer_coll.children:
            result = find_layer_collection(child, name)
            if result:
                return result
        return None

    layer_collection = find_layer_collection(view_layer.layer_collection, coll_name)

    if not layer_collection:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_COLLECTION_EXCLUDE.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Collection '{coll_name}' not found in view layer",
        )

    layer_collection.exclude = exclude

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.SET_COLLECTION_EXCLUDE.value,
        data={"collection": coll_name, "excluded": exclude, "view_layer": view_layer.name},
    )


def _handle_move_hierarchy(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    obj_name = params.get("object_name")
    hierarchy_path = params.get("hierarchy", [])

    if not obj_name or not hierarchy_path:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.MOVE_TO_COLLECTION_HIERARCHY.value,
            error_code="MISSING_PARAMETER",
            message="object_name and hierarchy path (list) required",
        )

    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.MOVE_TO_COLLECTION_HIERARCHY.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: {obj_name}",
        )

    # Navigate/create hierarchy
    current_coll = scene.collection
    path_taken = []

    for coll_name in hierarchy_path:
        # Try to find existing
        next_coll = None
        for child in current_coll.children:
            if child.name == coll_name:
                next_coll = child
                break

        # Create if not found
        if not next_coll:
            next_coll = bpy.data.collections.new(coll_name)
            current_coll.children.link(next_coll)

        current_coll = next_coll
        path_taken.append(coll_name)

    # Remove from other collections
    for coll in obj.users_collection:
        coll.objects.unlink(obj)

    # Link to target
    current_coll.objects.link(obj)

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.MOVE_TO_COLLECTION_HIERARCHY.value,
        data={"object": obj_name, "path": " > ".join(path_taken)},
    )


def _handle_create_view_layer(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    name = params.get("view_layer")
    if not name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.CREATE_VIEW_LAYER.value,
            error_code="MISSING_PARAMETER",
            message="view_layer name is required",
        )

    if name in scene.view_layers:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.CREATE_VIEW_LAYER.value,
            error_code="INVALID_PARAMETER_VALUE",
            message=f"View layer '{name}' already exists",
        )

    new_layer = scene.view_layers.new(name)

    if params.get("copy_from"):
        source = scene.view_layers.get(params["copy_from"])
        if source:
            new_layer.use_pass_combined = source.use_pass_combined
            new_layer.use_pass_z = source.use_pass_z
            new_layer.use_pass_normal = source.use_pass_normal
            new_layer.use_pass_diffuse_color = source.use_pass_diffuse_color
            new_layer.use_pass_glossy_color = source.use_pass_glossy_color

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.CREATE_VIEW_LAYER.value,
        data={"view_layer": name},
    )


def _handle_view_layer_visibility(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    view_layer_name = params.get("view_layer")
    if not view_layer_name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_VIEW_LAYER_VISIBILITY.value,
            error_code="MISSING_PARAMETER",
            message="view_layer is required",
        )

    view_layer = scene.view_layers.get(view_layer_name)
    if not view_layer:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_VIEW_LAYER_VISIBILITY.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"View layer not found: {view_layer_name}",
        )

    # Configure passes
    if params.get("use_pass_combined") is not None:
        view_layer.use_pass_combined = params["use_pass_combined"]
    if params.get("use_pass_z") is not None:
        view_layer.use_pass_z = params["use_pass_z"]
    if params.get("use_pass_normal") is not None:
        view_layer.use_pass_normal = params["use_pass_normal"]
    if params.get("use_pass_diffuse") is not None:
        view_layer.use_pass_diffuse_direct = params["use_pass_diffuse"]
    if params.get("use_pass_glossy") is not None:
        view_layer.use_pass_glossy_direct = params["use_pass_glossy"]
    if params.get("use_pass_emit") is not None:
        view_layer.use_pass_emit = params["use_pass_emit"]
    if params.get("use_pass_shadow") is not None:
        view_layer.use_pass_shadow = params["use_pass_shadow"]
    if params.get("use_pass_ambient_occlusion") is not None:
        view_layer.use_pass_ambient_occlusion = params["use_pass_ambient_occlusion"]

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.SET_VIEW_LAYER_VISIBILITY.value,
        data={"view_layer": view_layer_name, "updated": True},
    )


def _handle_copy_view_layer(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    source_name = params.get("source_view_layer")
    target_name = params.get("target_view_layer")

    if not source_name or not target_name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.COPY_VIEW_LAYER.value,
            error_code="MISSING_PARAMETER",
            message="source_view_layer and target_view_layer are required",
        )

    source = scene.view_layers.get(source_name)
    if not source:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.COPY_VIEW_LAYER.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Source view layer not found: {source_name}",
        )

    if target_name in scene.view_layers:
        target = scene.view_layers[target_name]
    else:
        target = scene.view_layers.new(target_name)

    # Copy settings
    target.use_pass_combined = source.use_pass_combined
    target.use_pass_z = source.use_pass_z
    target.use_pass_normal = source.use_pass_normal
    target.use_pass_diffuse_color = source.use_pass_diffuse_color
    target.use_pass_glossy_color = source.use_pass_glossy_color
    target.use_pass_emit = source.use_pass_emit
    target.use_pass_shadow = source.use_pass_shadow
    target.use_pass_ambient_occlusion = source.use_pass_ambient_occlusion

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.COPY_VIEW_LAYER.value,
        data={"copied_from": source_name, "copied_to": target_name},
    )


def _handle_render_visibility(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    coll_name = params.get("collection_name")
    visible = params.get("visible", True)

    if not coll_name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_RENDER_VISIBILITY.value,
            error_code="MISSING_PARAMETER",
            message="collection_name is required",
        )

    coll = bpy.data.collections.get(coll_name)
    if not coll:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_RENDER_VISIBILITY.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Collection not found: {coll_name}",
        )

    coll.hide_render = not visible

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.SET_RENDER_VISIBILITY.value,
        data={"collection": coll_name, "render_visible": visible},
    )


def _handle_holdout(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    coll_name = params.get("collection_name")
    holdout = params.get("holdout", True)
    view_layer_name = params.get("view_layer")

    if not coll_name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_HOLDOUT.value,
            error_code="MISSING_PARAMETER",
            message="collection_name is required",
        )

    # Re-use finder logic? Or duplicate small logic to keep decoupled
    if view_layer_name:
        view_layer = scene.view_layers.get(view_layer_name)
        if not view_layer:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.SET_HOLDOUT.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"View layer not found: {view_layer_name}",
            )
    else:
        view_layer = bpy.context.view_layer

    def find_layer_collection(layer_coll, name):  # type: ignore[no-untyped-def]
        if layer_coll.collection.name == name:
            return layer_coll
        for child in layer_coll.children:
            result = find_layer_collection(child, name)
            if result:
                return result
        return None

    layer_collection = find_layer_collection(view_layer.layer_collection, coll_name)

    if not layer_collection:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_HOLDOUT.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Collection '{coll_name}' not found in view layer",
        )

    layer_collection.holdout = holdout

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.SET_HOLDOUT.value,
        data={"collection": coll_name, "holdout": holdout},
    )


def _handle_indirect_only(scene, **params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    # Similar to holdout
    coll_name = params.get("collection_name")
    indirect = params.get("indirect_only", True)
    view_layer_name = params.get("view_layer")

    if not coll_name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_INDIRECT_ONLY.value,
            error_code="MISSING_PARAMETER",
            message="collection_name is required",
        )

    if view_layer_name:
        view_layer = scene.view_layers.get(view_layer_name)
        if not view_layer:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.SET_INDIRECT_ONLY.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"View layer not found: {view_layer_name}",
            )
    else:
        view_layer = bpy.context.view_layer

    def find_layer_collection(layer_coll, name):  # type: ignore[no-untyped-def]
        if layer_coll.collection.name == name:
            return layer_coll
        for child in layer_coll.children:
            result = find_layer_collection(child, name)
            if result:
                return result
        return None

    layer_collection = find_layer_collection(view_layer.layer_collection, coll_name)

    if not layer_collection:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.SET_INDIRECT_ONLY.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Collection '{coll_name}' not found in view layer",
        )

    layer_collection.indirect_only = indirect

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.SET_INDIRECT_ONLY.value,
        data={"collection": coll_name, "indirect_only": indirect},
    )


def _handle_create_asset(**params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    asset_type = params.get("asset_type", "OBJECT")
    name = params.get("name")

    if asset_type == "OBJECT":
        obj_name = params.get("object_name")
        if not obj_name:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.CREATE_ASSET.value,
                error_code="MISSING_PARAMETER",
                message="object_name is required for object asset",
            )

        obj = bpy.data.objects.get(obj_name)
        if not obj:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.CREATE_ASSET.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Object not found: {obj_name}",
            )

        obj.asset_mark()
        if name:
            obj.asset_data.name = name  # type: ignore[attr-defined, unused-ignore]

        if params.get("tags"):
            for tag in params["tags"]:
                obj.asset_data.tags.new(tag, skip_if_exists=True)

        return ResponseBuilder.success(
            handler="manage_collections_advanced",
            action=CollectionAction.CREATE_ASSET.value,
            data={"asset": obj_name, "type": "OBJECT"},
        )

    elif asset_type == "COLLECTION":
        coll_name = params.get("collection_name")
        if not coll_name:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.CREATE_ASSET.value,
                error_code="MISSING_PARAMETER",
                message="collection_name is required for collection asset",
            )

        coll = bpy.data.collections.get(coll_name)
        if not coll:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.CREATE_ASSET.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Collection not found: {coll_name}",
            )

        coll.asset_mark()
        if name:
            coll.asset_data.name = name  # type: ignore[attr-defined, unused-ignore]

        return ResponseBuilder.success(
            handler="manage_collections_advanced",
            action=CollectionAction.CREATE_ASSET.value,
            data={"asset": coll_name, "type": "COLLECTION"},
        )

    elif asset_type == "MATERIAL":
        mat_name = params.get("material_name")
        if not mat_name:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.CREATE_ASSET.value,
                error_code="MISSING_PARAMETER",
                message="material_name is required for material asset",
            )

        mat = bpy.data.materials.get(mat_name)
        if not mat:
            return ResponseBuilder.error(
                handler="manage_collections_advanced",
                action=CollectionAction.CREATE_ASSET.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Material not found: {mat_name}",
            )

        mat.asset_mark()

        return ResponseBuilder.success(
            handler="manage_collections_advanced",
            action=CollectionAction.CREATE_ASSET.value,
            data={"asset": mat_name, "type": "MATERIAL"},
        )

    return ResponseBuilder.error(
        handler="manage_collections_advanced",
        action=CollectionAction.CREATE_ASSET.value,
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown asset type: {asset_type}",
    )


def _handle_mark_asset(**params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    obj_name = params.get("object_name")
    coll_name = params.get("collection_name")
    mat_name = params.get("material_name")

    marked = []

    if obj_name:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            obj.asset_mark()
            marked.append(f"Object: {obj_name}")

    if coll_name:
        coll = bpy.data.collections.get(coll_name)
        if coll:
            coll.asset_mark()
            marked.append(f"Collection: {coll_name}")

    if mat_name:
        mat = bpy.data.materials.get(mat_name)
        if mat:
            mat.asset_mark()
            marked.append(f"Material: {mat_name}")

    return ResponseBuilder.success(
        handler="manage_collections_advanced",
        action=CollectionAction.MARK_ASSET.value,
        data={"marked": marked},
    )


def _handle_clear_asset(**params) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    obj_name = params.get("object_name")

    if not obj_name:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.CLEAR_ASSET.value,
            error_code="MISSING_PARAMETER",
            message="object_name is required",
        )

    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.CLEAR_ASSET.value,
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: {obj_name}",
        )

    if obj.asset_clear():  # type: ignore[func-returns-value, unused-ignore]
        return ResponseBuilder.success(
            handler="manage_collections_advanced",
            action=CollectionAction.CLEAR_ASSET.value,
            data={"cleared": obj_name},
        )
    else:
        return ResponseBuilder.error(
            handler="manage_collections_advanced",
            action=CollectionAction.CLEAR_ASSET.value,
            error_code="VALIDATION_ERROR",
            message=f"Object '{obj_name}' was not marked as asset",
        )
