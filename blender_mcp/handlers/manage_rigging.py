"""
Rigging Handler for Blender MCP 1.0.0 (Refactored)

Features:
- Armature creation/editing
- Bone manipulation
- Weight painting
- Constraint management
- Auto-rigging helpers

High Mode Philosophy: Robust rigging that survives animation.
"""

from typing import Any, Dict, Optional

try:
    import bpy
    import mathutils

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None

from ..dispatcher import register_handler
from ..core.resolver import resolve_name
from ..core.thread_safety import ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3, SafeModeContext
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.enums import RiggingAction, ConstraintType, Mode
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_rigging",
    actions=[a.value for a in RiggingAction],
    category="rigging",
    priority=20,
    schema={
        "type": "object",
        "title": "Rigging Manager (CORE)",
        "description": (
            "CORE — Armature and bone rigging: create armatures, add/position bones, "
            "set IK targets, weight painting prep.\n\n"
            "Use for character and vehicle rigging workflows.\n"
            "ACTIONS: CREATE_ARMATURE, ADD_BONE, MODIFY_BONE, RENAME_BONE, SET_IK_TARGET, "
            "APPLY_SKIN_WEIGHTS, PARENT_TO_BONE"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(RiggingAction, "Operation to perform."),
            "armature_name": {
                "type": "string",
                "description": "Name of armature object (default: active).",
            },
            "bone_name": {"type": "string", "description": "Target bone name."},
            "new_bone_name": {"type": "string", "description": "Name for new/extruded bone."},
            "head": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Head position [x,y,z].",
            },
            "tail": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Tail position [x,y,z].",
            },
            "length": {"type": "number", "description": "Length of extrusion."},
            "axis": {
                "type": "string",  # "X", "Y", "Z"
                "description": "Axis for extrusion.",
            },
            "constraint_type": ValidationUtils.generate_enum_schema(
                ConstraintType, "Type of constraint to add."
            ),
            "target": {"type": "string", "description": "Target object for constraint."},
            "subtarget": {
                "type": "string",
                "description": "Sub-target (bone/vertex group) for constraint.",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_rigging(
    action: Optional[str] = None, armature_name: Optional[str] = None, **params: Any
) -> Dict[str, Any]:
    """
    Manage rigging operations: Create bones, extrude, symmetrize, constrain.
    """
    # 1. Validate Action
    validation_error = ValidationUtils.validate_enum(action, RiggingAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(validation_error, handler="manage_rigging", action=action)

    # 2. Resolve Armature (unless creating or generating metarig)
    if action not in (RiggingAction.CREATE.value, RiggingAction.GENERATE_METARIG.value):
        armature = resolve_name(armature_name) if armature_name else bpy.context.active_object
        if not armature or armature.type != "ARMATURE":
            return ResponseBuilder.error(
                handler="manage_rigging",
                action=action,
                error_code="OBJECT_NOT_FOUND",
                message=f"Armature not found: {armature_name or '(active object)'}",
                suggestion="Create an armature first or select one.",
            )
        # Update resolved name for consistent return
        armature_name = armature.name
    else:
        armature = None  # Will be created

    # 3. Dispatch
    try:
        if action == RiggingAction.CREATE.value:
            return _handle_create(armature_name, **params)

        elif action == RiggingAction.EXTRUDE.value:
            return _handle_extrude(armature, params)  # Pass object, not name

        elif action == RiggingAction.SYMMETRIZE.value:
            return _handle_symmetrize(armature, params)

        elif action == RiggingAction.DISCONNECT.value:
            return _handle_disconnect(armature, params)

        elif action == RiggingAction.TRANSFORM_BONE.value:
            return _handle_transform_bone(armature, params)

        elif action == RiggingAction.CONSTRAINT.value:
            return _handle_constraint(armature, params)

        elif action == RiggingAction.GENERATE_METARIG.value:
            return _handle_generate_metarig(params)

        return ResponseBuilder.error(
            handler="manage_rigging",
            action=action,
            error_code="INVALID_ACTION",
            message=f"Action not implemented: {action}",
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return ResponseBuilder.error(
            handler="manage_rigging",
            action=action,
            error_code="EXECUTION_ERROR",
            message=f"Rigging operation failed: {str(e)}",
        )


# =============================================================================
# INTERNAL HANDLERS
# =============================================================================


def _handle_generate_metarig(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heuristically generates a Rigify MetaRig based on a given mesh bounding box,
    and then invokes rigify.generate to create the final functional rig.
    """
    import addon_utils
    import mathutils

    # 1. Ensure Rigify is enabled
    is_enabled, is_loaded = addon_utils.check("rigify")
    if not is_enabled:
        addon_utils.enable("rigify", default_set=True)

    target_name = params.get("target")
    obj = resolve_name(target_name) if target_name else bpy.context.active_object

    meshes = []
    if obj:
        if obj.type == "MESH":
            meshes.append(obj)
        elif obj.type == "ARMATURE":
            # Fix: Parent/Child Mesh Search Heuristic for OBA Linkage
            for child in obj.children:
                if child.type == "MESH" and child not in meshes:
                    meshes.append(child)

            for o in bpy.data.objects:
                if o.type == "MESH" and o not in meshes:
                    if o.parent == obj:
                        meshes.append(o)
                    else:
                        for mod in o.modifiers:
                            if mod.type == "ARMATURE" and mod.object == obj:
                                meshes.append(o)
                                break

    if not meshes:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="GENERATE_METARIG",
            error_code="INVALID_TARGET",
            message=f"Valid mesh target required for heuristic rigging. Could not resolve meshes from: {obj.name if obj else 'None'}",
        )

    # For center/bounding box calculations, we combine all meshes
    global_bbox = []
    for m in meshes:
        local_b = [mathutils.Vector(v) for v in m.bound_box]
        global_bbox.extend([m.matrix_world @ v for v in local_b])

    min_z = min(v.z for v in global_bbox)
    max_z = max(v.z for v in global_bbox)
    height = max_z - min_z

    center_x = sum(v.x for v in global_bbox) / 8.0
    center_y = sum(v.y for v in global_bbox) / 8.0

    # 3. Spawn MetaRig
    ContextManagerV3.deselect_all_objects()

    try:
        # standard human metarig
        bpy.ops.object.armature_human_metarig_add()
    except AttributeError:
        # Fallback if the operator is not registered somehow
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="GENERATE_METARIG",
            error_code="RIGIFY_ERROR",
            message="Rigify addon could not establish armature_human_metarig_add operator.",
        )

    metarig = bpy.context.active_object
    if not metarig:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="GENERATE_METARIG",
            error_code="SPAWN_FAILED",
            message="Failed to spawn MetaRig object.",
        )

    # 4. Scale and Position Heuristics
    # Human metarig defaults to ~2.0 blender units tall
    scale_factor = max(0.01, height / 2.0)

    metarig.location = (center_x, center_y, min_z)
    metarig.scale = (scale_factor, scale_factor, scale_factor)

    # Apply transform so rigify math works
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # 5. Generate Advanced Rig
    try:
        with SafeModeContext(metarig, "OBJECT"):
            bpy.ops.pose.rigify_generate()

        new_rig = bpy.data.objects.get("rig")

        # Parent Meshes to Rig with automatic weights
        if new_rig and meshes:
            ContextManagerV3.deselect_all_objects()
            new_rig.select_set(True)
            bpy.context.view_layer.objects.active = new_rig

            for m in meshes:
                m.select_set(True)
                # Clear old vertex groups to avoid ARMATURE_AUTO karmaşası
                m.vertex_groups.clear()
                # Clear old armature modifiers
                for mod in m.modifiers:
                    if mod.type == "ARMATURE":
                        m.modifiers.remove(mod)

            with SafeModeContext(new_rig, "OBJECT"):
                bpy.ops.object.parent_set(type="ARMATURE_AUTO")

        return ResponseBuilder.success(
            handler="manage_rigging",
            action="GENERATE_METARIG",
            data={
                "target_meshes": [m.name for m in meshes],
                "metarig": metarig.name,
                "generated_rig": new_rig.name if new_rig else None,
                "height_estimate": height,
            },
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="GENERATE_METARIG",
            error_code="GENERATION_FAILED",
            message=f"Rigify generation failed: {str(e)}",
        )


def _handle_create(name_input: Optional[str], **params: Any) -> Dict[str, Any]:
    """Create a new armature with a root bone."""
    name = name_input or "Armature"

    # Check if exists
    if name in bpy.data.objects:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="CREATE",
            error_code="NAME_COLLISION",
            message=f"Object '{name}' already exists.",
        )

    try:
        # Create Data
        arm_data = bpy.data.armatures.new(name=name)
        obj = bpy.data.objects.new(name, arm_data)
        bpy.context.collection.objects.link(obj)

        # Step 10.1.3: Ensure selection state for proper EDIT mode switching
        if (
            bpy.context.view_layer.objects.active is not None
            and bpy.context.view_layer.objects.active.mode != "OBJECT"
        ):
            bpy.ops.object.mode_set(mode="OBJECT")

        ContextManagerV3.deselect_all_objects()
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Add root bone if requested
        bone_name = params.get("bone_name", "Root")
        head = params.get("head", [0, 0, 0])
        tail = params.get("tail", [0, 0, 1])

        with SafeModeContext(Mode.EDIT.value, obj):
            bone = arm_data.edit_bones.new(bone_name)
            bone.head = head
            bone.tail = tail

        return ResponseBuilder.success(
            handler="manage_rigging",
            action="CREATE",
            data={"armature_name": obj.name, "root_bone": bone_name, "head": head, "tail": tail},
            affected_objects=[{"name": obj.name, "type": "ARMATURE", "changes": ["created"]}],
        )

    except Exception as e:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="CREATE",
            error_code="EXECUTION_ERROR",
            message=f"Failed to create armature: {str(e)}",
        )


def _handle_extrude(armature: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Extrude a bone from an existing one."""
    parent_name = params.get("bone_name")
    new_name = params.get("new_bone_name")
    length = params.get("length", 1.0)
    axis = params.get("axis", "Z")  # Local axis

    if not parent_name:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="EXTRUDE",
            error_code="MISSING_PARAMETER",
            message="bone_name (parent) is required for extrusion.",
        )

    with SafeModeContext(Mode.EDIT.value, armature):
        eb = armature.data.edit_bones.get(parent_name)
        if not eb:
            return ResponseBuilder.error(
                handler="manage_rigging",
                action="EXTRUDE",
                error_code="BONE_NOT_FOUND",
                message=f"Parent bone '{parent_name}' not found.",
            )

        # Calculate new tail
        # Simple extrusion along global axis for now, or local if complex math used
        # For robustness in this MCP, we'll keep it simple: relative to tail

        # Create new bone
        new_bone = armature.data.edit_bones.new(new_name or f"{parent_name}_ext")
        new_bone.head = eb.tail

        # Calculate offset
        offset = mathutils.Vector((0, 0, 0))
        if axis.upper() == "X":
            offset.x = length
        elif axis.upper() == "Y":
            offset.y = length
        elif axis.upper() == "Z":
            offset.z = length

        new_bone.tail = new_bone.head + offset
        new_bone.parent = eb
        new_bone.use_connect = True

        final_name = new_bone.name
        head_co = [c for c in new_bone.head]
        tail_co = [c for c in new_bone.tail]

    return ResponseBuilder.success(
        handler="manage_rigging",
        action="EXTRUDE",
        data={
            "parent": parent_name,
            "new_bone": final_name,
            "length": length,
            "head": head_co,
            "tail": tail_co,
        },
    )


def _handle_symmetrize(armature: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Symmetrize bones x-axis."""
    with SafeModeContext(Mode.EDIT.value, armature):
        bpy.ops.armature.select_all(action="SELECT")
        bpy.ops.armature.symmetrize(direction="NEGATIVE_X")

    return {"success": True, "message": "Symmetrized armature on X-Axis"}


def _handle_disconnect(armature: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Disconnect a bone from parent but keep parenting relationship."""
    bone_name = params.get("bone_name")

    if not bone_name:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="DISCONNECT",
            error_code="MISSING_PARAMETER",
            message="bone_name is required.",
        )

    with SafeModeContext(Mode.EDIT.value, armature):
        eb = armature.data.edit_bones.get(bone_name)
        if not eb:
            return ResponseBuilder.error(
                handler="manage_rigging",
                action="DISCONNECT",
                error_code="BONE_NOT_FOUND",
                message=f"Bone '{bone_name}' not found.",
            )

        eb.use_connect = False

    return {"success": True, "disconnected": bone_name}


def _handle_transform_bone(armature: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Move bone head/tail in Edit Mode."""
    bone_name = params.get("bone_name")
    head = params.get("head")
    tail = params.get("tail")

    if not bone_name:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="TRANSFORM_BONE",
            error_code="MISSING_PARAMETER",
            message="bone_name is required.",
        )

    with SafeModeContext(Mode.EDIT.value, armature):
        eb = armature.data.edit_bones.get(bone_name)
        if not eb:
            return ResponseBuilder.error(
                handler="manage_rigging",
                action="TRANSFORM_BONE",
                error_code="BONE_NOT_FOUND",
                message=f"Bone '{bone_name}' not found.",
            )

        if head:
            eb.head = head
        if tail:
            eb.tail = tail

    return {"success": True, "message": f"Transformed bone {bone_name}"}


def _handle_constraint(armature: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Add a constraint to a bone in Pose Mode."""
    bone_name = params.get("bone_name")
    constraint_type = params.get("constraint_type")

    if not bone_name or not constraint_type:
        return ResponseBuilder.error(
            handler="manage_rigging",
            action="CONSTRAINT",
            error_code="MISSING_PARAMETER",
            message="bone_name and constraint_type are required.",
        )

    # ValidationUtils type check for constraint_type
    c_validation = ValidationUtils.validate_enum(constraint_type, ConstraintType, "constraint_type")
    if c_validation:
        # Fallback for old string usage or partial match if needed, but strict is better
        return ResponseBuilder.from_error(
            c_validation, handler="manage_rigging", action="CONSTRAINT"
        )

    target_obj_name = params.get("target")
    subtarget = params.get("subtarget")  # e.g., bone name in target armature

    target_obj = None
    if target_obj_name:
        target_obj = resolve_name(target_obj_name)
        if not target_obj:
            return ResponseBuilder.error(
                handler="manage_rigging",
                action="CONSTRAINT",
                error_code="OBJECT_NOT_FOUND",
                message=f"Target object '{target_obj_name}' not found.",
            )

    with SafeModeContext(Mode.POSE.value, armature):
        pbone = armature.pose.bones.get(bone_name)
        if not pbone:
            return ResponseBuilder.error(
                handler="manage_rigging",
                action="CONSTRAINT",
                error_code="BONE_NOT_FOUND",
                message=f"Pose Bone '{bone_name}' not found.",
            )

        # Add constraint
        # Use constraint_type string directly as it should match Blender types (usually upper case)
        # Some mapping might be needed if Enums diverge from Blender API strings

        try:
            constr = pbone.constraints.new(type=constraint_type)
            if target_obj:
                if hasattr(constr, "target"):
                    constr.target = target_obj
                if hasattr(constr, "subtarget") and subtarget:
                    constr.subtarget = subtarget

            return {
                "success": True,
                "constraint": constr.name,
                "type": constraint_type,
                "bone": bone_name,
            }
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_rigging",
                action="CONSTRAINT",
                error_code="EXECUTION_ERROR",
                message=f"Failed to add constraint: {str(e)}",
            )
