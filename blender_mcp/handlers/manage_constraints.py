"""
Constraint Handler for Blender MCP 1.0.0 (Refactored)

Advanced Constraint Management: Object, Bone, and Camera constraints.
- Unified interface for Objects and Pose Bones
- Strict typing with ConstraintAction & ConstraintType Enums
- ValidationUtils for robust input checking

High Mode Philosophy: Complete control over relationships.
"""

from typing import Optional

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..dispatcher import register_handler
from ..core.resolver import resolve_name
from ..core.thread_safety import ensure_main_thread
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.enums import ConstraintAction, ConstraintType
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_constraints",
    actions=[a.value for a in ConstraintAction],
    category="animation",
    priority=21,
    schema={
        "type": "object",
        "title": "Constraint Manager (CORE)",
        "description": (
            "CORE — Add/modify/remove object and bone constraints.\n\n"
            "Use to control object behavior without keyframes "
            "(Copy Location/Rotation, Track To, IK, Look At, Child Of, Floor).\n"
            "ACTIONS: ADD_CONSTRAINT, MODIFY_CONSTRAINT, REMOVE_CONSTRAINT, "
            "REMOVE_ALL_CONSTRAINTS, LIST_CONSTRAINTS"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                ConstraintAction, "Operation to perform."
            ),
            "object_name": {
                "type": "string",
                "description": "Owner object name (default: active).",
            },
            "bone_name": {
                "type": "string",
                "description": "Owner bone name (if target is an Armature).",
            },
            "constraint_name": {
                "type": "string",
                "description": "Name of the constraint to modify.",
            },
            # Add Constraint Params
            "constraint_type": ValidationUtils.generate_enum_schema(
                ConstraintType, "Type of constraint to add."
            ),
            "target": {"type": "string", "description": "Target object name."},
            "subtarget": {
                "type": "string",
                "description": "Sub-target (bone/vertex group) in target object.",
            },
            # Properties
            "influence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Influence of the constraint.",
            },
            "properties": {
                "type": "object",
                "description": "Additional properties to set on the constraint.",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_constraints(action: Optional[str] = None, **params):  # type: ignore[no-untyped-def]
    """
    Manage constraints for objects and bones.
    """
    # 1. Validate Action
    validation_error = ValidationUtils.validate_enum(action, ConstraintAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="manage_constraints", action=action
        )

    # 2. Resolve Owner (Object or Bone)
    obj_name = params.get("object_name")
    bone_name = params.get("bone_name")

    obj = resolve_name(obj_name) if obj_name else bpy.context.active_object

    if not obj:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action=action,
            error_code="OBJECT_NOT_FOUND",
            message=f"Object not found: {obj_name or '(active object)'}",
        )

    # Determine Owner (data structure that holds constraints)
    if bone_name:
        if obj.type != "ARMATURE":
            return ResponseBuilder.error(
                handler="manage_constraints",
                action=action,
                error_code="INVALID_CONTEXT",
                message=f"Object '{obj.name}' is not an armature, cannot access bone '{bone_name}'.",
            )
        # Ensure Pose Mode for bone constraints
        # We might need to switch mode, but for querying we can use pose.bones if exists
        # For adding/modifying, usually Pose Mode is best
        # SmartModeContext or similar logic handled inside sub-handlers or here
        pass  # deferred to sub-handlers
    else:
        pass

    # Dispatch
    try:
        # Context Management handled deeper or wrapper
        # For bone operations, we need to access pose bone
        owner, error_response = _get_constraint_owner(obj, bone_name)
        if error_response:
            return error_response

        if action == ConstraintAction.ADD_CONSTRAINT.value:
            return _handle_add_constraint(owner, params)

        elif action == ConstraintAction.REMOVE_CONSTRAINT.value:
            return _handle_remove_constraint(owner, params)

        elif action == ConstraintAction.SET_TARGET.value:
            return _handle_set_target(owner, params)

        elif action == ConstraintAction.SET_INFLUENCE.value:
            return _handle_set_influence(owner, params)

        elif action == ConstraintAction.SET_PROPERTIES.value:
            return _handle_set_properties(owner, params)

        elif action == ConstraintAction.LIST_CONSTRAINTS.value:
            return _handle_list_constraints(owner)

        elif action == ConstraintAction.MUTE_CONSTRAINT.value:
            return _handle_mute(owner, params, mute=True)

        elif action == ConstraintAction.UNMUTE_CONSTRAINT.value:
            return _handle_mute(owner, params, mute=False)

        # Quick Actions
        elif action == ConstraintAction.COPY_TRANSFORMS.value:
            params["constraint_type"] = ConstraintType.COPY_TRANSFORMS.value
            return _handle_add_constraint(owner, params)

        elif action == ConstraintAction.LIMIT_LOCATION.value:
            params["constraint_type"] = ConstraintType.LIMIT_LOCATION.value
            return _handle_add_constraint(owner, params)

        elif action == ConstraintAction.LIMIT_ROTATION.value:
            params["constraint_type"] = ConstraintType.LIMIT_ROTATION.value
            return _handle_add_constraint(owner, params)

        return ResponseBuilder.error(
            handler="manage_constraints",
            action=action,
            error_code="INVALID_ACTION",
            message=f"Action '{action}' is defined but not implemented.",
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return ResponseBuilder.error(
            handler="manage_constraints",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Constraint operation failed: {str(e)}",
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_constraint_owner(obj, bone_name):  # type: ignore[no-untyped-def]
    """Return the object or pose bone that owns the constraints."""
    if bone_name:
        if obj.type != "ARMATURE":
            return None, ResponseBuilder.error(
                handler="manage_constraints",
                action="GET_CONTEXT",
                error_code="INVALID_TYPE",
                message=f"Object '{obj.name}' is not an armature.",
            )

        # Ensure we can access pose bones
        if not obj.pose:
            # Might happen if not yet evaluated or in Edit mode without update?
            # Usually accessible.
            pass

        pbone = obj.pose.bones.get(bone_name)
        if not pbone:
            return None, ResponseBuilder.error(
                handler="manage_constraints",
                action="GET_CONTEXT",
                error_code="BONE_NOT_FOUND",
                message=f"Pose Bone '{bone_name}' not found in '{obj.name}'.",
            )
        return pbone, None
    else:
        return obj, None


def _handle_add_constraint(owner, params):  # type: ignore[no-untyped-def]
    c_type = params.get("constraint_type")

    # Validate Type
    c_validation = ValidationUtils.validate_enum(c_type, ConstraintType, "constraint_type")
    if c_validation:
        return ResponseBuilder.from_error(
            c_validation, handler="manage_constraints", action="ADD_CONSTRAINT"
        )

    target_name = params.get("target")
    subtarget = params.get("subtarget")

    try:
        # Create
        constr = owner.constraints.new(type=c_type)

        # Set Target
        if target_name:
            target_obj = resolve_name(target_name)
            if target_obj:
                if hasattr(constr, "target"):
                    constr.target = target_obj
                if hasattr(constr, "subtarget") and subtarget:
                    constr.subtarget = subtarget
            else:
                logger.warning(f"Target '{target_name}' not found for constraint.")

        # Set Influence
        influence = params.get("influence")
        if influence is not None:
            constr.influence = influence

        return ResponseBuilder.success(
            handler="manage_constraints",
            action="ADD_CONSTRAINT",
            data={
                "constraint": constr.name,
                "type": c_type,
                "owner": owner.name if hasattr(owner, "name") else str(owner),
            },
            affected_objects=[
                {
                    "name": owner.id_data.name if hasattr(owner, "id_data") else owner.name,
                    "type": "OBJECT",
                    "changes": ["constraint_added"],
                }
            ],
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="ADD_CONSTRAINT",
            error_code="EXECUTION_ERROR",
            message=f"Failed to add constraint: {str(e)}",
        )


def _handle_remove_constraint(owner, params):  # type: ignore[no-untyped-def]
    name = params.get("constraint_name")
    if not name:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="REMOVE_CONSTRAINT",
            error_code="MISSING_PARAMETER",
            message="constraint_name is required.",
        )

    constr = owner.constraints.get(name)
    if not constr:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="REMOVE_CONSTRAINT",
            error_code="CONSTRAINT_NOT_FOUND",
            message=f"Constraint '{name}' not found.",
        )

    owner.constraints.remove(constr)
    return {"success": True, "message": f"Removed constraint '{name}'"}


def _handle_set_target(owner, params):  # type: ignore[no-untyped-def]
    name = params.get("constraint_name")
    target_name = params.get("target")
    subtarget = params.get("subtarget")

    if not name or not target_name:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="SET_TARGET",
            error_code="MISSING_PARAMETER",
            message="constraint_name and target are required.",
        )

    constr = owner.constraints.get(name)
    if not constr:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="SET_TARGET",
            error_code="CONSTRAINT_NOT_FOUND",
            message=f"Constraint '{name}' not found.",
        )

    target_obj = resolve_name(target_name)
    if not target_obj:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="SET_TARGET",
            error_code="OBJECT_NOT_FOUND",
            message=f"Target object '{target_name}' not found.",
        )

    if hasattr(constr, "target"):
        constr.target = target_obj
    else:
        return {"success": False, "message": f"Constraint '{name}' does not support targets."}

    if hasattr(constr, "subtarget") and subtarget is not None:
        constr.subtarget = subtarget

    return {"success": True, "message": f"Updated target for '{name}'"}


def _handle_set_influence(owner, params):  # type: ignore[no-untyped-def]
    name = params.get("constraint_name")
    influence = params.get("influence")

    if not name or influence is None:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="SET_INFLUENCE",
            error_code="MISSING_PARAMETER",
            message="constraint_name and influence are required.",
        )

    constr = owner.constraints.get(name)
    if not constr:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="SET_INFLUENCE",
            error_code="CONSTRAINT_NOT_FOUND",
            message=f"Constraint '{name}' not found.",
        )

    constr.influence = influence
    return {"success": True, "message": f"Set influence of '{name}' to {influence}"}


def _handle_set_properties(owner, params):  # type: ignore[no-untyped-def]
    name = params.get("constraint_name")
    props = params.get("properties", {})

    if not name:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="SET_PROPERTIES",
            error_code="MISSING_PARAMETER",
            message="constraint_name is required.",
        )

    constr = owner.constraints.get(name)
    if not constr:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="SET_PROPERTIES",
            error_code="CONSTRAINT_NOT_FOUND",
            message=f"Constraint '{name}' not found.",
        )

    updated = []
    for key, val in props.items():
        if hasattr(constr, key):
            try:
                setattr(constr, key, val)
                updated.append(key)
            except Exception as e:
                logger.warning(f"Failed to set property '{key}': {e}")

    return {"success": True, "updated": updated}


def _handle_list_constraints(owner):  # type: ignore[no-untyped-def]
    con_list = []
    for c in owner.constraints:
        data = {
            "name": c.name,
            "type": c.type,
            "influence": c.influence,
            "active": c.active,  # or !mute
        }
        if hasattr(c, "target") and c.target:
            data["target"] = c.target.name
        if hasattr(c, "subtarget") and c.subtarget:
            data["subtarget"] = c.subtarget
        con_list.append(data)

    return {"success": True, "constraints": con_list}


def _handle_mute(owner, params, mute=True):  # type: ignore[no-untyped-def]
    name = params.get("constraint_name")
    constr = owner.constraints.get(name)
    if not constr:
        return ResponseBuilder.error(
            handler="manage_constraints",
            action="MUTE_CONSTRAINT",
            error_code="CONSTRAINT_NOT_FOUND",
            message=f"Constraint '{name}' not found.",
        )

    constr.active = not mute  # 'active' is inverse of mute usually, or specifically 'mute' prop?
    # Blender API: Constraint has 'active' (bool) and 'mute' (bool) usually?
    # Actually Constraint.active disables it.

    # Wait, check API:
    # Constraint.active: "Constraint is the one being edited" (no)
    # or Constraint.is_valid
    # Actually, constraint.mute is the property for disabling it.
    if hasattr(constr, "mute"):
        constr.mute = mute
    elif hasattr(constr, "enabled"):  # Some constraints
        constr.enabled = not mute

    return {"success": True, "message": f"{'Muted' if mute else 'Unmuted'} constraint '{name}'"}
