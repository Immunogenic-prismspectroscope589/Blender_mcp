"""
Unity Collections Handler - V1.0.0 Refactored (SSOT)

Collection management for Unity workflow:
- Create collections
- Move objects between collections
- List collections for UI population

Part of 'unity_handler' modularization.
Implements Rules 1 (SSOT) and 9 (Zero Trust Input).
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import bpy
else:
    try:
        import bpy

        BPY_AVAILABLE = True
    except ImportError:
        BPY_AVAILABLE = False
        bpy = None

from ..core.logging_config import get_logger
from ..core.response_builder import ResponseBuilder
from ..dispatcher import register_handler
from ..core.thread_safety import ensure_main_thread

# SSOT Imports
from ..core.enums import UnityCollectionAction
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "unity_collections",
    schema={
        "type": "object",
        "title": "Unity Collections Manager",
        "description": "Collection management for Unity workflow",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                UnityCollectionAction, "Action to perform"
            ),
            "collection_name": {"type": "string"},
            "params": {"type": "object"},
        },
        "required": ["action"],
    },
    actions=[a.value for a in UnityCollectionAction],
    category="unity",
)
@ensure_main_thread
def unity_collections(action: Optional[str] = None, **params):  # type: ignore[no-untyped-def]
    """
    Handle collection management with safe access.
    """
    if not action:
        # Fallback
        action = params.get("action")

    if not action:
        return ResponseBuilder.error(
            handler="unity_collections",
            action=None,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
            suggestion="Specify an action: create_collection, move_to_collection, list_collections",
        )

    # Validate Action Enum
    validation_error = ValidationUtils.validate_enum(action, UnityCollectionAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="unity_collections", action=action
        )

    collection_name = params.get("collection_name")
    action_params = params.get("params", {})

    if action == UnityCollectionAction.CREATE_COLLECTION.value:
        if not collection_name:
            collection_name = "NewCollection"

        # Check if already exists
        if collection_name in bpy.data.collections:
            return {
                "success": True,
                "collection": collection_name,
                "note": "Collection already exists",
            }

        try:
            collection = bpy.data.collections.new(collection_name)
            if bpy.context.scene.collection:
                bpy.context.scene.collection.children.link(collection)
            else:
                return {"error": "Scene collection not available"}

            return {"success": True, "collection": collection_name}
        except Exception as e:
            return {"error": f"Failed to create collection: {str(e)}"}

    elif action == UnityCollectionAction.MOVE_TO_COLLECTION.value:
        object_name = action_params.get("object")

        if not collection_name:
            return {"error": "collection_name is required"}

        coll = bpy.data.collections.get(collection_name)
        obj = bpy.data.objects.get(object_name)

        if not obj or not coll:
            return {"error": "Object or collection not found"}

        try:
            # Unlink from all collections
            for c in list(obj.users_collection):
                if c and obj.name in c.objects:
                    c.objects.unlink(obj)

            # Link to new collection
            coll.objects.link(obj)
            return {"success": True, "object": object_name, "collection": collection_name}
        except Exception as e:
            return {"error": f"Failed to move object: {str(e)}"}

    elif action == UnityCollectionAction.LIST_COLLECTIONS.value:
        collections = []
        for coll in bpy.data.collections:
            coll_info = {
                "name": coll.name,
                "object_count": len(coll.objects) if coll.objects else 0,
            }
            collections.append(coll_info)

        return {"success": True, "collections": collections, "count": len(collections)}

    else:
        # Should be unreachable
        return ResponseBuilder.error(
            handler="unity_collections",
            action=action,
            error_code="INVALID_ACTION",
            message=f"Unknown collection action: {action}",
        )
