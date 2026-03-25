"""AI-Powered Tools for Blender MCP v1.0.0 - V1.0.0 Explainable AI

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking
- EXPLAINABLE AI: EXPLAIN, DRY_RUN, CONFIDENCE patterns

High Mode Philosophy: Maximum power, maximum safety, maximum transparency.
"""

from typing import TYPE_CHECKING, Dict, Any, cast

if TYPE_CHECKING:
    import bpy
    import bmesh
    import mathutils
else:
    try:
        import bpy
        import bmesh
        import mathutils

        BPY_AVAILABLE = True
    except ImportError:
        BPY_AVAILABLE = False
        bpy = None
        bmesh = None
        mathutils = None

from ..core.resolver import resolve_name
from ..core.execution_engine import safe_ops
from ..dispatcher import register_handler

from ..core.thread_safety import ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.execution_safety import god_mode_safe
from ..core.parameter_validator import validated_handler
from ..core.enums import AIToolsAction

logger = get_logger()

# SSOT action source: schema, validation and dispatcher metadata all read from enum.
AI_ACTIONS = [a.value for a in AIToolsAction]
AI_LIGHTING_ACTIONS = {
    AIToolsAction.SMART_LIGHTING.value,
    AIToolsAction.EXPLAIN_SMART_LIGHTING.value,
    AIToolsAction.DRY_RUN_SMART_LIGHTING.value,
    AIToolsAction.CONFIDENCE_SMART_LIGHTING.value,
}


@register_handler(
    "manage_ai_tools",
    actions=AI_ACTIONS,
    category="ai",
    schema={
        "type": "object",
        "title": "AI-Powered Tools (Explainable AI 1.0.0)",
        "description": "Smart automation with EXPLAIN, DRY_RUN, and CONFIDENCE patterns for transparency.",
        "properties": {
            "action": {
                "type": "string",
                "enum": AI_ACTIONS,
                "description": "AI-powered action to perform. EXPLAIN_* returns decision logic, DRY_RUN_* simulates without changes, CONFIDENCE_* returns reliability scores.",
            },
            "object_name": {"type": "string", "description": "Target object"},
            "target_object": {
                "type": "string",
                "description": "Second target object (e.g., for INTELLIGENT_MERGE)",
            },
            "quality": {
                "type": "string",
                "enum": ["LOW", "MEDIUM", "HIGH", "ULTRA"],
                "default": "MEDIUM",
            },
            "preserve_features": {"type": "boolean", "default": True},
            "adaptive": {"type": "boolean", "default": True},
            "target_ratio": {"type": "number", "default": 0.5, "minimum": 0.01, "maximum": 1.0},
            "levels": {"type": "integer", "default": 3, "minimum": 1, "maximum": 5},
        },
        "required": ["action"],
    },
)
@validated_handler(actions=[a.value for a in AIToolsAction])
@ensure_main_thread
def manage_ai_tools(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Super-Tool for AI-powered mesh optimization, retopology, decimation, and intelligent workflow automation.
    Supports EXPLAIN, DRY_RUN, and CONFIDENCE queries.
    """
    action_name = action or ""
    obj_name = params.get("object_name")
    obj = resolve_name(obj_name) if obj_name else bpy.context.active_object

    if not obj and action_name not in AI_LIGHTING_ACTIONS:
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action=action,
            error_code="NO_ACTIVE_OBJECT",
            message="No object specified or found",
        )

    if not action:
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    # Route to appropriate handler
    action_map = {
        # Original actions
        AIToolsAction.SMART_UV_UNWRAP.value: _smart_uv_unwrap,
        AIToolsAction.AUTO_RETOPOLOGY.value: _auto_retopology,
        AIToolsAction.SMART_DECIMATE.value: _smart_decimate,
        AIToolsAction.AI_MATERIAL_SUGGEST.value: _ai_material_suggest,
        AIToolsAction.SMART_LIGHTING.value: _smart_lighting,
        AIToolsAction.AUTO_RIG_SUGGEST.value: _auto_rig_suggest,
        AIToolsAction.SMART_BEVEL.value: _smart_bevel,
        AIToolsAction.INTELLIGENT_MERGE.value: _intelligent_merge,
        AIToolsAction.AUTO_COLLIDER.value: _auto_collider,
        AIToolsAction.AUTO_LOD_GENERATE.value: _auto_lod_generate,
        AIToolsAction.SMART_CLEANUP.value: _smart_cleanup,
        # V1.0.0: Explainable AI
        AIToolsAction.EXPLAIN_SMART_UV_UNWRAP.value: _explain_smart_uv_unwrap,
        AIToolsAction.DRY_RUN_SMART_UV_UNWRAP.value: _dry_run_smart_uv_unwrap,
        AIToolsAction.CONFIDENCE_SMART_UV_UNWRAP.value: _confidence_smart_uv_unwrap,
        AIToolsAction.EXPLAIN_AUTO_RETOPOLOGY.value: _explain_auto_retopology,
        AIToolsAction.DRY_RUN_AUTO_RETOPOLOGY.value: _dry_run_auto_retopology,
        AIToolsAction.CONFIDENCE_AUTO_RETOPOLOGY.value: _confidence_auto_retopology,
        AIToolsAction.EXPLAIN_SMART_DECIMATE.value: _explain_smart_decimate,
        AIToolsAction.DRY_RUN_SMART_DECIMATE.value: _dry_run_smart_decimate,
        AIToolsAction.CONFIDENCE_SMART_DECIMATE.value: _confidence_smart_decimate,
        AIToolsAction.EXPLAIN_AI_MATERIAL_SUGGEST.value: _explain_ai_material_suggest,
        AIToolsAction.CONFIDENCE_AI_MATERIAL_SUGGEST.value: _confidence_ai_material_suggest,
        AIToolsAction.EXPLAIN_SMART_LIGHTING.value: _explain_smart_lighting,
        AIToolsAction.DRY_RUN_SMART_LIGHTING.value: _dry_run_smart_lighting,
        AIToolsAction.CONFIDENCE_SMART_LIGHTING.value: _confidence_smart_lighting,
        AIToolsAction.EXPLAIN_AUTO_RIG_SUGGEST.value: _explain_auto_rig_suggest,
        AIToolsAction.CONFIDENCE_AUTO_RIG_SUGGEST.value: _confidence_auto_rig_suggest,
        AIToolsAction.EXPLAIN_AUTO_LOD_GENERATE.value: _explain_auto_lod_generate,
        AIToolsAction.DRY_RUN_AUTO_LOD_GENERATE.value: _dry_run_auto_lod_generate,
        AIToolsAction.CONFIDENCE_AUTO_LOD_GENERATE.value: _confidence_auto_lod_generate,
    }

    handler = action_map.get(action)
    if handler:
        if action in AI_LIGHTING_ACTIONS:
            return handler(params)  # type: ignore[no-any-return]
        return handler(obj, params)  # type: ignore[no-any-return]

    return ResponseBuilder.error(
        handler="manage_ai_tools",
        action=action,
        error_code="MISSING_PARAMETER",
        message=f"Unknown action: {action}",
    )


# =============================================================================
# ORIGINAL AI ACTIONS (v1.0.0)
# =============================================================================


def _smart_uv_unwrap(obj, params):  # type: ignore[no-untyped-def]
    """AI-optimized UV unwrapping based on mesh analysis."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="SMART_UV_UNWRAP",
            error_code="WRONG_OBJECT_TYPE",
            message="Object must be a mesh",
            details={"expected_type": "MESH", "actual_type": obj.type},
        )

    mesh = obj.data
    total_verts = len(mesh.vertices)
    is_organic = _detect_organic_topology(mesh)

    if is_organic:
        method = "ANGLE_BASED"
        angle_limit = 45.0
    else:
        method = "CONFORMAL"
        angle_limit = 66.0

    bpy.context.view_layer.objects.active = obj
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.object.mode_set(mode="EDIT")
        safe_ops.mesh.select_all(action="SELECT")

        if method == "ANGLE_BASED":
            safe_ops.uv.unwrap(method="ANGLE_BASED", margin=0.02)
        else:
            safe_ops.uv.smart_project(angle_limit=angle_limit)

        safe_ops.object.mode_set(mode="OBJECT")

    return ResponseBuilder.success(
        handler="manage_ai_tools",
        action="SMART_UV_UNWRAP",
        data={"method": method, "is_organic": is_organic, "verts_analyzed": total_verts},
    )


def _detect_organic_topology(mesh):  # type: ignore[no-untyped-def]
    """Detect if mesh has organic (curved) or hard-surface topology."""
    bm = bmesh.new()
    bm.from_mesh(mesh)

    try:
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        sharp_edges = 0
        smooth_edges = 0

        for edge in bm.edges:
            is_sharp = True
            for face in edge.link_faces:
                if face.smooth:
                    is_sharp = False
                    break
            if is_sharp:
                sharp_edges += 1
            else:
                smooth_edges += 1

        total = sharp_edges + smooth_edges
        if total == 0:
            return False

        return (smooth_edges / total) > 0.6
    finally:
        bm.free()


@god_mode_safe(default_return={"error": "Retopology crashed", "code": "CRASH"})
def _auto_retopology(obj, params):  # type: ignore[no-untyped-def]
    """Automatic quad-dominant remeshing with crash protection."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="AUTO_RETOPOLOGY",
            error_code="WRONG_OBJECT_TYPE",
            message="Object must be a mesh",
            details={"expected_type": "MESH", "actual_type": obj.type},
        )

    quality = params.get("quality", "MEDIUM")
    settings = {
        "LOW": {"target_faces": 1000},
        "MEDIUM": {"target_faces": 4000},
        "HIGH": {"target_faces": 10000},
        "ULTRA": {"target_faces": 25000},
    }

    q = settings.get(quality, settings["MEDIUM"])
    bpy.context.view_layer.objects.active = obj

    quad_result = safe_ops.object.quadriflow_remesh(
        use_mesh_symmetry=False,
        use_preserve_sharp=True,
        use_preserve_boundary=True,
        preserve_attributes=True,
        smooth_normals=True,
        mode="FACES",
        target_faces=q["target_faces"],
        target_edge_length=0.0,
        target_ratio=1.0,
    )

    if quad_result.success:
        method = "quadriflow"
    else:
        voxel_result = safe_ops.object.voxel_remesh()
        if voxel_result.success:
            method = "voxel"
        else:
            return ResponseBuilder.error(
                handler="manage_ai_tools",
                action="AUTO_RETOPOLOGY",
                error_code="EXECUTION_ERROR",
                message="Retopology failed",
                details={
                    "quadriflow_error": quad_result.error,
                    "quadriflow_code": quad_result.error_code,
                    "voxel_error": voxel_result.error,
                    "voxel_code": voxel_result.error_code,
                },
            )

    return ResponseBuilder.success(
        handler="manage_ai_tools",
        action="AUTO_RETOPOLOGY",
        data={
            "quality": quality,
            "target_faces": q["target_faces"],
            "method": method,
            "final_verts": len(obj.data.vertices),
        },
    )


def _smart_decimate(obj, params):  # type: ignore[no-untyped-def]
    """Adaptive polygon reduction preserving features."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="SMART_DECIMATE",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for decimation",
        )

    target_ratio = params.get("target_ratio", 0.5)
    preserve_features = params.get("preserve_features", True)
    original_verts = len(obj.data.vertices)

    bpy.context.view_layer.objects.active = obj

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        if preserve_features:
            decimate = obj.modifiers.new(name="SmartDecimate", type="DECIMATE")
            decimate.ratio = target_ratio
            decimate.use_collapse_triangulate = False
            decimate.use_symmetry = True
            safe_ops.object.modifier_apply(modifier="SmartDecimate")
        else:
            decimate = obj.modifiers.new(name="UniformDecimate", type="DECIMATE")
            decimate.ratio = target_ratio
            safe_ops.object.modifier_apply(modifier="UniformDecimate")

    final_verts = len(obj.data.vertices)
    reduction = (1 - final_verts / original_verts) * 100

    return {
        "success": True,
        "original_verts": original_verts,
        "final_verts": final_verts,
        "reduction_percent": round(reduction, 2),
    }


def _ai_material_suggest(obj, params):  # type: ignore[no-untyped-def]
    """Context-aware material suggestions based on object name and shape."""
    name_lower = obj.name.lower()

    material_hints = {
        "metal": ["metal", "steel", "iron", "aluminum", "copper", "brass"],
        "glass": ["glass", "crystal", "window", "lens"],
        "wood": ["wood", "timber", "oak", "pine", "tree"],
        "plastic": ["plastic", "pvc", "rubber", "silicone"],
        "fabric": ["cloth", "fabric", "cotton", "silk", "wool"],
        "stone": ["stone", "rock", "concrete", "brick", "marble"],
        "liquid": ["water", "liquid", "ocean", "river", "lake"],
        "skin": ["skin", "flesh", "organic", "character"],
    }

    detected = []
    for mat_type, keywords in material_hints.items():
        for keyword in keywords:
            if keyword in name_lower:
                detected.append(mat_type)
                break

    if not detected:
        detected = ["plastic"]

    suggestions = []
    for mat_type in detected[:2]:
        mat_name = f"{obj.name}_{mat_type.title()}"
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True

        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            if mat_type == "metal":
                bsdf.inputs["Metallic"].default_value = 1.0  # type: ignore
                bsdf.inputs["Roughness"].default_value = 0.3  # type: ignore
            elif mat_type == "glass":
                bsdf.inputs["Transmission Weight"].default_value = 1.0  # type: ignore
                bsdf.inputs["IOR"].default_value = 1.45  # type: ignore
            elif mat_type == "wood":
                bsdf.inputs["Roughness"].default_value = 0.6  # type: ignore
            elif mat_type == "plastic":
                bsdf.inputs["Roughness"].default_value = 0.2  # type: ignore

        suggestions.append({"type": mat_type, "material": mat_name, "created": True})

    return {"success": True, "detected_types": detected, "suggestions": suggestions}


def _smart_lighting(params):  # type: ignore[no-untyped-def]
    """Auto lighting based on scene analysis."""
    scene = bpy.context.scene

    mesh_count = sum(1 for o in scene.objects if o.type == "MESH")
    has_character = any("char" in o.name.lower() or "body" in o.name.lower() for o in scene.objects)

    if has_character:
        setup = "studio_portrait"
        key_energy = 150
        fill_energy = 50
    elif mesh_count > 10:
        setup = "archviz"
        key_energy = 100
        fill_energy = 30
    else:
        setup = "standard_three_point"
        key_energy = 100
        fill_energy = 30

    key_data = bpy.data.lights.new(name="Smart_Key", type="AREA")
    key_data.energy = key_energy  # type: ignore
    key_obj = bpy.data.objects.new(name="Smart_Key", object_data=key_data)
    scene.collection.objects.link(key_obj)
    key_obj.location = (5, -5, 7)

    fill_data = bpy.data.lights.new(name="Smart_Fill", type="AREA")
    fill_data.energy = fill_energy  # type: ignore
    fill_obj = bpy.data.objects.new(name="Smart_Fill", object_data=fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.location = (-5, -3, 4)

    rim_data = bpy.data.lights.new(name="Smart_Rim", type="SPOT")
    rim_data.energy = key_energy * 0.7  # type: ignore
    rim_obj = bpy.data.objects.new(name="Smart_Rim", object_data=rim_data)
    scene.collection.objects.link(rim_obj)
    rim_obj.location = (0, 5, 6)

    return {
        "success": True,
        "setup_type": setup,
        "lights_created": 3,
        "config": {"key_energy": key_energy, "fill_energy": fill_energy},
    }


def _auto_rig_suggest(obj, params):  # type: ignore[no-untyped-def]
    """Rig suggestions based on mesh topology analysis."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="AUTO_RIG_SUGGEST",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for rig suggestions",
        )

    bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    dimensions = [max(v[i] for v in bbox) - min(v[i] for v in bbox) for i in range(3)]

    height, width, depth = sorted(dimensions, reverse=True)
    ratio = height / max(width, 0.001)

    if ratio > 2.5:
        rig_type = "BIPED"
        bone_count = 28
    elif ratio > 1.5:
        rig_type = "QUADRUPED"
        bone_count = 35
    elif max(dimensions) < 1.0:
        rig_type = "PROP"
        bone_count = 4
    else:
        rig_type = "CUSTOM"
        bone_count = 16

    return {
        "success": True,
        "detected_type": rig_type,
        "suggested_bones": bone_count,
        "dimensions": dimensions,
        "ratio": round(ratio, 2),
        "note": f"Use manage_rig_templates with template='{rig_type}'",
    }


def _smart_bevel(obj, params):  # type: ignore[no-untyped-def]
    """Intelligent bevel weight calculation."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="SMART_BEVEL",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for bevel operations",
        )

    width = params.get("width", 0.02)
    bpy.context.view_layer.objects.active = obj

    bevel = obj.modifiers.new(name="SmartBevel", type="BEVEL")
    bevel.width = width
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = 0.523599
    bevel.segments = 3
    bevel.use_clamp_overlap = True

    return {"success": True, "width": width, "segments": 3, "angle_threshold": 30}


def _intelligent_merge(obj, params):  # type: ignore[no-untyped-def]
    """Smart mesh boolean operations."""
    target_name = params.get("target_object")
    if not target_name:
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="INTELLIGENT_MERGE",
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'target_object'",
            suggestion="Specify the name of the target object to merge with",
        )

    target = resolve_name(target_name)
    if not target:
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="INTELLIGENT_MERGE",
            error_code="OBJECT_NOT_FOUND",
            message=f"Target object not found: '{target_name}'",
            suggestion="Verify the target object name exists in the scene",
        )

    mode = params.get("mode", "UNION")
    bpy.context.view_layer.objects.active = obj

    boolean = obj.modifiers.new(name="IntelliMerge", type="BOOLEAN")
    boolean.operation = mode
    boolean.object = target

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.object.modifier_apply(modifier="IntelliMerge")
    bpy.data.objects.remove(target, do_unlink=True)

    return {"success": True, "mode": mode, "target_removed": True}


def _auto_collider(obj, params):  # type: ignore[no-untyped-def]
    """Generate collision meshes."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="AUTO_COLLIDER",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for collider generation",
        )

    collider_type = params.get("collider_type", "CONVEX_HULL")
    collider = obj.copy()
    collider.data = obj.data.copy()
    collider.name = f"{obj.name}_Collider"
    bpy.context.collection.objects.link(collider)

    if collider_type == "CONVEX_HULL":
        hull = collider.modifiers.new(name="ConvexHull", type="REMESH")
        hull.mode = "VOXEL"
        hull.voxel_size = 0.1
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.object.modifier_apply(modifier="ConvexHull")
    elif collider_type == "BOX":
        bpy.context.view_layer.objects.active = collider
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.object.transform_apply(location=True, rotation=True, scale=True)
        collider.display_type = "WIRE"

    return {"success": True, "collider_name": collider.name, "type": collider_type}


def _auto_lod_generate(obj, params):  # type: ignore[no-untyped-def]
    """Create LOD chain automatically."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="AUTO_LOD_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for LOD generation",
        )

    levels = params.get("levels", 3)
    ratios = [0.5, 0.25, 0.125]
    created = []

    for i, ratio in enumerate(ratios[:levels], 1):
        lod = obj.copy()
        lod.data = obj.data.copy()
        lod.name = f"{obj.name}_LOD{i}"
        bpy.context.collection.objects.link(lod)

        decimate = lod.modifiers.new(name=f"LOD{i}_Decimate", type="DECIMATE")
        decimate.ratio = ratio
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.object.modifier_apply(modifier=f"LOD{i}_Decimate")

        created.append({"name": lod.name, "ratio": ratio, "verts": len(lod.data.vertices)})

    return {"success": True, "lod_chain": created, "original_verts": len(obj.data.vertices)}


def _smart_cleanup(obj, params):  # type: ignore[no-untyped-def]
    """Intelligent mesh cleanup."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="SMART_CLEANUP",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for cleanup operations",
        )

    actions = []
    bpy.context.view_layer.objects.active = obj
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.object.mode_set(mode="EDIT")
        safe_ops.mesh.select_all(action="SELECT")

        safe_ops.mesh.remove_doubles(threshold=0.0001)
        actions.append("removed_doubles")

        safe_ops.mesh.normals_make_consistent(inside=False)
        actions.append("fixed_normals")

        safe_ops.mesh.delete_loose()
        actions.append("deleted_loose")

        safe_ops.mesh.dissolve_degenerate(threshold=0.0001)
        actions.append("dissolved_degenerate")

        safe_ops.object.mode_set(mode="OBJECT")

    return {"success": True, "actions_performed": actions, "final_verts": len(obj.data.vertices)}


# =============================================================================
# V1.0.0: EXPLAINABLE AI - EXPLAIN PATTERNS
# =============================================================================


def _explain_smart_uv_unwrap(obj, params):  # type: ignore[no-untyped-def]
    """
    EXPLAIN: Describe UV unwrapping strategy without executing.
    Returns decision logic, detected features, and reasoning.
    """
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="EXPLAIN_SMART_UV_UNWRAP",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for UV explanation",
        )

    mesh = obj.data

    # Analysis
    total_verts = len(mesh.vertices)
    total_faces = len(mesh.polygons)
    is_organic = _detect_organic_topology(mesh)

    # Detect seams
    bm = bmesh.new()
    bm.from_mesh(mesh)
    seam_edges = sum(1 for e in bm.edges if e.seam)
    bm.free()

    # UV analysis
    uv_layers = len(mesh.uv_layers)
    has_uv = uv_layers > 0

    if is_organic:
        method = "ANGLE_BASED"
        angle_limit = 45.0
        reasoning = "Mesh has >60% smooth edges, indicating organic topology. Angle-based unwrap better for curved surfaces."
        risk_areas = ["High curvature areas may have stretching"]
        alternative = "CONFORMAL with higher angle limit for flatter areas"
    else:
        method = "CONFORMAL"
        angle_limit = 66.0
        reasoning = "Mesh has sharp edges (>40%), indicating hard-surface topology. Smart project with conformal mapping optimal."
        risk_areas = ["Multiple UV islands may be created"]
        alternative = "ANGLE_BASED for cylindrical parts"

    return {
        "success": True,
        "explanation": {
            "detected_topology": "organic" if is_organic else "hard_surface",
            "detection_confidence": 0.85,
            "selected_method": method,
            "angle_limit": angle_limit,
            "reasoning": reasoning,
            "mesh_stats": {
                "vertices": total_verts,
                "faces": total_faces,
                "existing_seams": seam_edges,
                "uv_layers": uv_layers,
                "has_existing_uvs": has_uv,
            },
            "risk_areas": risk_areas,
            "alternative_methods": [alternative],
            "estimated_uv_islands": max(1, int(total_faces / 100)),
            "packing_efficiency_estimate": "75-85%" if is_organic else "85-95%",
        },
        "recommendations": [
            "Mark additional seams in high-curvature areas if stretching occurs",
            f"Use {method} unwrap with {angle_limit}° angle limit",
            "Run pack islands after unwrap for optimal UV space usage",
        ],
    }


def _explain_auto_retopology(obj, params):  # type: ignore[no-untyped-def]
    """
    EXPLAIN: Describe retopology strategy without executing.
    """
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="EXPLAIN_AUTO_RETOPOLOGY",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for retopology explanation",
        )

    quality = params.get("quality", "MEDIUM")
    settings = {
        "LOW": {"target_faces": 1000, "use_case": "Background objects, mobile games"},
        "MEDIUM": {"target_faces": 4000, "use_case": "Standard game assets"},
        "HIGH": {"target_faces": 10000, "use_case": "Hero characters, cinematics"},
        "ULTRA": {"target_faces": 25000, "use_case": "Film/VFX close-ups"},
    }

    q: Dict[str, Any] = settings.get(quality, settings["MEDIUM"])
    original_faces = len(obj.data.polygons)
    original_verts = len(obj.data.vertices)

    # Analyze features
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    sharp_edges = sum(1 for e in bm.edges if not e.smooth)
    boundary_edges = sum(1 for e in bm.edges if e.is_boundary)

    # Detect risk areas
    risk_areas = []
    if sharp_edges > 50:
        risk_areas.append(f"{sharp_edges} sharp edges - may lose detail")
    if boundary_edges > 0:
        risk_areas.append(f"{boundary_edges} boundary edges - preserve_boundary enabled")
    if original_faces < int(cast(int, q["target_faces"])):
        risk_areas.append("Target faces higher than current - may add geometry")

    bm.free()

    reduction_ratio = original_faces / int(cast(int, q["target_faces"]))

    return {
        "success": True,
        "explanation": {
            "strategy": "Quad-dominant remeshing with feature preservation",
            "algorithm": "Quadriflow (primary) with Voxel fallback",
            "quality_setting": quality,
            "target_faces": q["target_faces"],
            "use_case": q["use_case"],
            "current_mesh": {
                "faces": original_faces,
                "vertices": original_verts,
                "sharp_edges": sharp_edges,
                "boundary_edges": boundary_edges,
            },
            "expected_reduction_ratio": round(reduction_ratio, 2),
            "estimated_final_verts": int(
                original_verts * (int(cast(int, q["target_faces"])) / max(original_faces, 1))
            ),
            "feature_preservation": {
                "preserve_sharp": True,
                "preserve_boundary": boundary_edges > 0,
                "preserve_attributes": True,
                "smooth_normals": True,
            },
            "risk_areas": risk_areas if risk_areas else ["Low risk - standard retopology"],
            "alternative_strategies": [
                "Manual retopology for hero assets",
                "Voxel remesh for organic shapes",
                "Instant Meshes addon for more control",
            ],
        },
        "workflow_recommendation": [
            "1. Review risk areas in mesh",
            "2. Mark critical edge loops if needed",
            "3. Run AUTO_RETOPOLOGY",
            "4. Check result in wireframe mode",
            "5. Use SMOOTH_CLEANUP if artifacts appear",
        ],
    }


def _explain_smart_decimate(obj, params):  # type: ignore[no-untyped-def]
    """EXPLAIN: Describe decimation strategy."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="EXPLAIN_SMART_DECIMATE",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for decimation explanation",
        )

    target_ratio = params.get("target_ratio", 0.5)
    preserve_features = params.get("preserve_features", True)

    original_verts = len(obj.data.vertices)
    original_faces = len(obj.data.polygons)
    estimated_final = int(original_verts * target_ratio)
    reduction = (1 - target_ratio) * 100

    # Analyze mesh for feature preservation
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    sharp_edges = sum(1 for e in bm.edges if not e.smooth)
    total_edges = len(bm.edges)
    sharp_ratio = sharp_edges / max(total_edges, 1)

    bm.free()

    if preserve_features:
        strategy = "Planar decimation with symmetry"
        method_desc = "Preserves sharp edges and planar areas, reduces uniform regions"
        risk = "May create Ngons in complex areas" if sharp_ratio > 0.3 else "Low risk"
    else:
        strategy = "Uniform decimation"
        method_desc = "Even reduction across all faces, faster but loses detail"
        risk = "Will smooth out all details uniformly"

    return {
        "success": True,
        "explanation": {
            "strategy": strategy,
            "method_description": method_desc,
            "preserve_features": preserve_features,
            "target_ratio": target_ratio,
            "reduction_percent": round(reduction, 1),
            "mesh_analysis": {
                "original_vertices": original_verts,
                "original_faces": original_faces,
                "estimated_final_vertices": estimated_final,
                "sharp_edge_ratio": round(sharp_ratio, 2),
                "topology_complexity": (
                    "high" if sharp_ratio > 0.3 else "medium" if sharp_ratio > 0.1 else "low"
                ),
            },
            "risk_assessment": risk,
            "optimization_tips": [
                "Apply modifiers before decimation for best results",
                "Use 0.5 ratio for game-ready assets",
                "Use 0.25 ratio for LODs",
                "Mark sharp edges explicitly if auto-detection fails",
            ],
        },
    }


def _explain_ai_material_suggest(obj, params):  # type: ignore[no-untyped-def]
    """EXPLAIN: Describe material detection logic."""
    name_lower = obj.name.lower()

    material_hints = {
        "metal": (["metal", "steel", "iron", "aluminum", "copper", "brass"], 0.9),
        "glass": (["glass", "crystal", "window", "lens"], 0.95),
        "wood": (["wood", "timber", "oak", "pine", "tree"], 0.85),
        "plastic": (["plastic", "pvc", "rubber", "silicone"], 0.7),
        "fabric": (["cloth", "fabric", "cotton", "silk", "wool"], 0.8),
        "stone": (["stone", "rock", "concrete", "brick", "marble"], 0.85),
        "liquid": (["water", "liquid", "ocean", "river", "lake"], 0.9),
        "skin": (["skin", "flesh", "organic", "character"], 0.75),
    }

    detected = []
    detection_details = []

    for mat_type, (keywords, confidence) in material_hints.items():
        matched_keywords = [k for k in keywords if k in name_lower]
        if matched_keywords:
            detected.append(mat_type)
            detection_details.append(
                {
                    "type": mat_type,
                    "matched_keywords": matched_keywords,
                    "confidence": confidence,
                    "reasoning": f"Object name contains: {', '.join(matched_keywords)}",
                }
            )

    if not detected:
        detected = ["plastic"]
        detection_details.append(
            {
                "type": "plastic",
                "matched_keywords": [],
                "confidence": 0.5,
                "reasoning": "No material keywords detected in name, defaulting to plastic",
            }
        )

    return {
        "success": True,
        "explanation": {
            "detection_method": "Keyword matching on object name",
            "object_name": obj.name,
            "detected_materials": detected,
            "detection_details": detection_details,
            "suggested_pbr_values": {
                "metal": {"metallic": 1.0, "roughness": 0.3, "specular": 0.5},
                "glass": {"transmission": 1.0, "ior": 1.45, "roughness": 0.1},
                "wood": {"roughness": 0.6, "subsurface": 0.0},
                "plastic": {"roughness": 0.2, "specular": 0.5},
                "fabric": {"roughness": 0.8, "sheen": 0.5},
                "stone": {"roughness": 0.9, "specular": 0.1},
                "liquid": {"transmission": 1.0, "ior": 1.33},
                "skin": {"subsurface": 0.1, "roughness": 0.4},
            },
            "limitations": [
                "Detection based solely on object name",
                "Visual analysis not performed",
                "May need manual adjustment",
            ],
            "improvement_suggestions": [
                "Rename object with material keywords for better detection",
                "Use AI_MATERIAL_SUGGEST as starting point, then fine-tune",
            ],
        },
    }


def _explain_smart_lighting(params):  # type: ignore[no-untyped-def]
    """EXPLAIN: Describe lighting setup strategy."""
    scene = bpy.context.scene

    mesh_count = sum(1 for o in scene.objects if o.type == "MESH")
    light_count = sum(1 for o in scene.objects if o.type == "LIGHT")
    has_character = any("char" in o.name.lower() or "body" in o.name.lower() for o in scene.objects)
    has_architecture = any(
        "building" in o.name.lower() or "room" in o.name.lower() or "house" in o.name.lower()
        for o in scene.objects
    )

    if has_character:
        setup = "studio_portrait"
        reasoning = (
            "Character detected in scene - studio portrait lighting optimal for skin and fabric"
        )
        key_energy = 150
        fill_energy = 50
        rim_energy = 105
    elif has_architecture or mesh_count > 10:
        setup = "archviz"
        reasoning = "Architectural scene or complex environment detected - even illumination needed"
        key_energy = 100
        fill_energy = 30
        rim_energy = 70
    else:
        setup = "standard_three_point"
        reasoning = "General scene - standard three-point lighting for good base illumination"
        key_energy = 100
        fill_energy = 30
        rim_energy = 70

    return {
        "success": True,
        "explanation": {
            "detected_scene_type": setup,
            "detection_reasoning": reasoning,
            "scene_analysis": {
                "mesh_objects": mesh_count,
                "existing_lights": light_count,
                "has_character": has_character,
                "has_architecture": has_architecture,
            },
            "proposed_setup": {
                "setup_name": setup,
                "lights": [
                    {
                        "name": "Smart_Key",
                        "type": "AREA",
                        "energy": key_energy,
                        "purpose": "Main illumination",
                    },
                    {
                        "name": "Smart_Fill",
                        "type": "AREA",
                        "energy": fill_energy,
                        "purpose": "Fill shadows",
                    },
                    {
                        "name": "Smart_Rim",
                        "type": "SPOT",
                        "energy": rim_energy,
                        "purpose": "Separate from background",
                    },
                ],
                "lighting_ratio": f"Key:Fill = {key_energy / fill_energy:.1f}:1",
            },
            "positioning_strategy": {
                "key_light": "45° angle, camera left, elevated",
                "fill_light": "Opposite side, lower energy, softer",
                "rim_light": "Behind subject, highlighting edges",
            },
            "limitations": [
                "Scene-based detection, not content-aware",
                "May need adjustment for specific art direction",
            ],
        },
    }


def _explain_auto_rig_suggest(obj, params):  # type: ignore[no-untyped-def]
    """EXPLAIN: Describe rig detection logic."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="EXPLAIN_AUTO_RIG_SUGGEST",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for rig explanation",
        )

    bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    dimensions = [max(v[i] for v in bbox) - min(v[i] for v in bbox) for i in range(3)]

    height, width, depth = sorted(dimensions, reverse=True)
    ratio = height / max(width, 0.001)

    # Detailed analysis
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Symmetry detection
    left_verts = sum(1 for v in bm.verts if v.co.x < -0.01)
    right_verts = sum(1 for v in bm.verts if v.co.x > 0.01)
    symmetry_ratio = min(left_verts, right_verts) / max(left_verts, right_verts, 1)
    is_symmetric = symmetry_ratio > 0.8

    bm.free()

    if ratio > 2.5:
        rig_type = "BIPED"
        bone_count = 28
        reasoning = f"Height/width ratio {ratio:.1f} indicates tall vertical structure (humanoid)"
        features = ["spine_chain", "two_legs", "two_arms", "head"]
    elif ratio > 1.5:
        rig_type = "QUADRUPED"
        bone_count = 35
        reasoning = f"Height/width ratio {ratio:.1f} indicates medium proportions (animal-like)"
        features = ["spine_chain", "four_legs", "tail"]
    elif max(dimensions) < 1.0:
        rig_type = "PROP"
        bone_count = 4
        reasoning = f"Small scale object {max(dimensions):.2f}m - simple prop rig sufficient"
        features = ["root_bone", "optional_sub_props"]
    else:
        rig_type = "CUSTOM"
        bone_count = 16
        reasoning = f"Non-standard proportions (ratio {ratio:.1f}) - custom rig recommended"
        features = ["custom_skeleton"]

    return {
        "success": True,
        "explanation": {
            "detection_method": "Dimensional analysis + symmetry check",
            "mesh_dimensions": {
                "height": round(height, 2),
                "width": round(width, 2),
                "depth": round(depth, 2),
                "aspect_ratio": round(ratio, 2),
            },
            "detected_rig_type": rig_type,
            "reasoning": reasoning,
            "symmetry_analysis": {
                "is_symmetric": is_symmetric,
                "symmetry_ratio": round(symmetry_ratio, 2),
                "left_side_verts": left_verts,
                "right_side_verts": right_verts,
            },
            "suggested_rig_structure": {
                "bone_count": bone_count,
                "key_features": features,
                "recommended_template": f"manage_rig_templates with template='{rig_type}'",
            },
            "next_steps": [
                "1. Check symmetry detection accuracy",
                "2. Use suggested template or manual rigging",
                "3. Test skin weights with AUTO_WEIGHT_PAINT",
            ],
        },
    }


def _explain_auto_lod_generate(obj, params):  # type: ignore[no-untyped-def]
    """EXPLAIN: Describe LOD generation strategy."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="EXPLAIN_AUTO_LOD_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for LOD explanation",
        )

    levels = params.get("levels", 3)
    original_verts = len(obj.data.vertices)
    original_faces = len(obj.data.polygons)

    ratios = [0.5, 0.25, 0.125][:levels]
    lod_chain = []

    for i, ratio in enumerate(ratios, 1):
        estimated_verts = int(original_verts * ratio)
        lod_chain.append(
            {
                "level": i,
                "name": f"{obj.name}_LOD{i}",
                "decimate_ratio": ratio,
                "estimated_vertices": estimated_verts,
                "use_case": _get_lod_use_case(i),
            }
        )

    return {
        "success": True,
        "explanation": {
            "strategy": "Decimation-based LOD chain",
            "original_mesh": {"vertices": original_verts, "faces": original_faces},
            "lod_chain": lod_chain,
            "method": "Blender Decimate modifier with collapse mode",
            "feature_preservation": "Planar decimation attempts to preserve shape",
            "recommended_distances": {
                "LOD0": "0-10m (Full detail)",
                "LOD1": "10-30m (Medium detail)",
                "LOD2": "30m+ (Low detail)",
            },
            "alternatives": [
                "Manual LOD creation for hero assets",
                "Geometry Nodes for procedural LOD",
                "Nanite (Unreal) for automatic LOD",
            ],
        },
    }


def _get_lod_use_case(level):  # type: ignore[no-untyped-def]
    """Get use case description for LOD level."""
    cases = {
        1: "Medium distance - gameplay",
        2: "Far distance - background",
        3: "Very far - silhouette only",
        4: "Extremely far - impostor/culled",
        5: "Cull distance",
    }
    return cases.get(level, "Unknown")


# =============================================================================
# V1.0.0: EXPLAINABLE AI - DRY_RUN PATTERNS
# =============================================================================


def _dry_run_smart_uv_unwrap(obj, params):  # type: ignore[no-untyped-def]
    """
    DRY_RUN: Simulate UV unwrap without changing mesh.
    Returns predicted results and statistics.
    """
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="DRY_RUN_SMART_UV_UNWRAP",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for UV dry run",
        )

    mesh = obj.data
    is_organic = _detect_organic_topology(mesh)

    # Simulate UV analysis
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Estimate UV islands
    total_faces = len(bm.faces)
    sharp_edges = sum(1 for e in bm.edges if not e.smooth)
    estimated_islands = max(1, int(total_faces / 50) + int(sharp_edges / 20))

    # Estimate stretching
    stretch_factor = "low" if is_organic else "medium"

    bm.free()

    method = "ANGLE_BASED" if is_organic else "CONFORMAL"

    return {
        "success": True,
        "dry_run": True,
        "simulation": {
            "would_use_method": method,
            "estimated_uv_islands": estimated_islands,
            "estimated_stretching": stretch_factor,
            "estimated_pack_efficiency": "75-85%" if is_organic else "85-95%",
            "current_uv_layers": len(mesh.uv_layers),
            "would_create_new_uv_layer": True,
            "processing_time_estimate": "0.5-2 seconds",
        },
        "warnings": [
            (
                "High curvature areas may have stretching"
                if is_organic
                else "Multiple islands expected"
            )
        ],
        "preview_available": True,
        "note": "Run actual SMART_UV_UNWRAP to apply changes",
    }


def _dry_run_auto_retopology(obj, params):  # type: ignore[no-untyped-def]
    """DRY_RUN: Simulate retopology without modifying mesh."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="DRY_RUN_AUTO_RETOPOLOGY",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for retopology dry run",
        )

    quality = params.get("quality", "MEDIUM")
    settings = {"LOW": 1000, "MEDIUM": 4000, "HIGH": 10000, "ULTRA": 25000}
    target = settings.get(quality, 4000)

    original_verts = len(obj.data.vertices)
    original_faces = len(obj.data.polygons)

    # Predict results
    reduction_ratio = original_faces / target if target > 0 else 1
    predicted_verts = int(original_verts / reduction_ratio)

    # Detect potential issues
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    sharp_count = sum(1 for e in bm.edges if not e.smooth)
    bm.free()

    issues = []
    if sharp_count > 100:
        issues.append(f"{sharp_count} sharp edges may lose definition")
    if original_faces < target:
        issues.append("Target face count higher than current - will subdivide")
    if reduction_ratio > 10:
        issues.append("High reduction ratio - significant detail loss expected")

    return {
        "success": True,
        "dry_run": True,
        "simulation": {
            "algorithm": "Quadriflow (predicted)",
            "fallback": "Voxel remesh if quadriflow fails",
            "current_faces": original_faces,
            "target_faces": target,
            "predicted_final_vertices": predicted_verts,
            "reduction_ratio": round(reduction_ratio, 2),
            "processing_time_estimate": "5-30 seconds",
            "memory_estimate": "50-200MB",
        },
        "potential_issues": issues if issues else ["No major issues detected"],
        "recommendations": [
            "Mark preserve-sharp edges before retopology" if sharp_count > 50 else None,
            "Consider manual retopology for hero assets" if reduction_ratio > 5 else None,
        ],
        "note": "Run EXPLAIN_AUTO_RETOPOLOGY for detailed strategy",
    }


def _dry_run_smart_decimate(obj, params):  # type: ignore[no-untyped-def]
    """DRY_RUN: Simulate decimation and predict results."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="DRY_RUN_SMART_DECIMATE",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for decimation dry run",
        )

    target_ratio = params.get("target_ratio", 0.5)
    preserve_features = params.get("preserve_features", True)

    original_verts = len(obj.data.vertices)
    original_faces = len(obj.data.polygons)
    predicted_verts = int(original_verts * target_ratio)
    reduction_percent = (1 - target_ratio) * 100

    # Feature analysis
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    sharp_edges = sum(1 for e in bm.edges if not e.smooth)
    planar_faces = sum(1 for f in bm.faces if len(f.verts) == 4)
    bm.free()

    return {
        "success": True,
        "dry_run": True,
        "simulation": {
            "method": "Planar decimation" if preserve_features else "Uniform decimation",
            "preserve_features": preserve_features,
            "decimate_ratio": target_ratio,
            "original_vertices": original_verts,
            "original_faces": original_faces,
            "predicted_vertices": predicted_verts,
            "vertex_reduction": f"{reduction_percent:.1f}%",
            "estimated_faces_after": int(original_faces * target_ratio),
            "processing_time": "0.1-1 second",
        },
        "feature_analysis": {
            "sharp_edges_detected": sharp_edges,
            "will_be_preserved": preserve_features,
            "quad_faces": planar_faces,
            "planar_optimization": "Enabled" if preserve_features else "Disabled",
        },
        "visual_impact_prediction": (
            "minimal" if target_ratio > 0.7 else "moderate" if target_ratio > 0.4 else "significant"
        ),
    }


def _dry_run_smart_lighting(params):  # type: ignore[no-untyped-def]
    """DRY_RUN: Preview lighting setup without creating lights."""
    scene = bpy.context.scene

    mesh_count = sum(1 for o in scene.objects if o.type == "MESH")
    existing_lights = [o for o in scene.objects if o.type == "LIGHT"]
    has_character = any("char" in o.name.lower() for o in scene.objects)

    if has_character:
        setup = "studio_portrait"
        lights = [
            {"name": "Smart_Key", "type": "AREA", "energy": 150, "location": (5, -5, 7)},
            {"name": "Smart_Fill", "type": "AREA", "energy": 50, "location": (-5, -3, 4)},
            {"name": "Smart_Rim", "type": "SPOT", "energy": 105, "location": (0, 5, 6)},
        ]
    else:
        setup = "standard_three_point"
        lights = [
            {"name": "Smart_Key", "type": "AREA", "energy": 100, "location": (5, -5, 7)},
            {"name": "Smart_Fill", "type": "AREA", "energy": 30, "location": (-5, -3, 4)},
            {"name": "Smart_Rim", "type": "SPOT", "energy": 70, "location": (0, 5, 6)},
        ]

    return {
        "success": True,
        "dry_run": True,
        "simulation": {
            "setup_type": setup,
            "lights_would_create": len(lights),
            "existing_lights_in_scene": len(existing_lights),
            "proposed_lights": lights,
        },
        "scene_analysis": {
            "mesh_objects": mesh_count,
            "has_character": has_character,
            "existing_lights": [o.name for o in existing_lights],
        },
        "warnings": [
            (
                f"{len(existing_lights)} lights already exist - may conflict"
                if existing_lights
                else None
            )
        ],
        "note": "Run SMART_LIGHTING to actually create lights",
    }


def _dry_run_auto_lod_generate(obj, params):  # type: ignore[no-untyped-def]
    """DRY_RUN: Preview LOD chain without creating objects."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="DRY_RUN_AUTO_LOD_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for LOD dry run",
        )

    levels = params.get("levels", 3)
    ratios = [0.5, 0.25, 0.125][:levels]

    original_verts = len(obj.data.vertices)
    original_faces = len(obj.data.polygons)

    lod_preview = []
    for i, ratio in enumerate(ratios, 1):
        lod_preview.append(
            {
                "level": i,
                "name": f"{obj.name}_LOD{i}",
                "decimate_ratio": ratio,
                "predicted_vertices": int(original_verts * ratio),
                "predicted_faces": int(original_faces * ratio),
                "file_size_estimate": f"{int((ratio**1.5) * 100)}% of original",
            }
        )

    return {
        "success": True,
        "dry_run": True,
        "simulation": {
            "original_mesh": {"vertices": original_verts, "faces": original_faces},
            "lod_chain_preview": lod_preview,
            "total_objects_would_create": levels,
            "naming_pattern": f"{obj.name}_LOD[1-{levels}]",
        },
        "storage_impact": f"Total size ~{sum(int(cast(int, layer['predicted_vertices'])) for layer in lod_preview) / max(original_verts, 1):.1f}x original",
        "note": "Run AUTO_LOD_GENERATE to create actual LOD objects",
    }


# =============================================================================
# V1.0.0: EXPLAINABLE AI - CONFIDENCE PATTERNS
# =============================================================================


def _confidence_smart_uv_unwrap(obj, params):  # type: ignore[no-untyped-def]
    """
    CONFIDENCE: Calculate reliability score for UV unwrapping.
    Returns 0-1 confidence score with factor breakdown.
    """
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="CONFIDENCE_SMART_UV_UNWRAP",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for UV confidence check",
        )

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Factor 1: Mesh complexity
    total_faces = len(bm.faces)
    complexity_score = (
        1.0
        if total_faces < 1000
        else 0.9
        if total_faces < 5000
        else 0.7
        if total_faces < 20000
        else 0.5
    )

    # Factor 2: Topology regularity
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    ngon_ratio = ngons / max(total_faces, 1)
    topology_score = 1.0 - (ngon_ratio * 0.5)

    # Factor 3: Organic vs hard-surface clarity
    sharp_edges = sum(1 for e in bm.edges if not e.smooth)
    smooth_edges = sum(1 for e in bm.edges if e.smooth)
    total_edges = sharp_edges + smooth_edges
    if total_edges > 0:
        edge_ratio = max(sharp_edges, smooth_edges) / total_edges
        clarity_score = 0.5 + (edge_ratio * 0.5)
    else:
        clarity_score = 0.5

    # Factor 4: Existing UV quality
    has_uv = len(mesh.uv_layers) > 0
    if has_uv:
        # Check existing UV quality
        uv_score = 0.7  # Conservative if UVs exist
    else:
        uv_score = 1.0  # No existing UVs to conflict

    bm.free()

    # Calculate overall confidence
    weights = {"complexity": 0.25, "topology": 0.3, "clarity": 0.25, "uv": 0.2}
    overall = (
        complexity_score * weights["complexity"]
        + topology_score * weights["topology"]
        + clarity_score * weights["clarity"]
        + uv_score * weights["uv"]
    )

    return {
        "success": True,
        "confidence": round(overall, 2),
        "reliability": "high" if overall > 0.8 else "medium" if overall > 0.6 else "low",
        "factors": {
            "mesh_complexity": {
                "score": round(complexity_score, 2),
                "weight": weights["complexity"],
            },
            "topology_quality": {"score": round(topology_score, 2), "weight": weights["topology"]},
            "topology_clarity": {"score": round(clarity_score, 2), "weight": weights["clarity"]},
            "uv_conflicts": {"score": round(uv_score, 2), "weight": weights["uv"]},
        },
        "recommendation": _get_confidence_recommendation(overall, "SMART_UV_UNWRAP"),
    }


def _confidence_auto_retopology(obj, params):  # type: ignore[no-untyped-def]
    """CONFIDENCE: Calculate reliability score for retopology."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="CONFIDENCE_AUTO_RETOPOLOGY",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for retopology confidence check",
        )

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Factor 1: Current mesh density
    face_count = len(bm.faces)
    quality = params.get("quality", "MEDIUM")
    targets = {"LOW": 1000, "MEDIUM": 4000, "HIGH": 10000, "ULTRA": 25000}
    target = targets.get(quality, 4000)

    if face_count < target:
        density_score = face_count / target
    else:
        reduction = target / face_count
        density_score = 1.0 if reduction > 0.2 else 0.7

    # Factor 2: Sharp edge density (hard to preserve)
    sharp_edges = sum(1 for e in bm.edges if not e.smooth)
    sharp_ratio = sharp_edges / max(len(bm.edges), 1)
    sharp_score = 1.0 - (sharp_ratio * 0.5)

    # Factor 3: Manifold check
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    manifold_score = 1.0 if non_manifold == 0 else 0.7 if non_manifold < 10 else 0.4

    # Factor 4: Symmetry (symmetric meshes retopologize better)
    left = sum(1 for v in bm.verts if v.co.x < -0.01)
    right = sum(1 for v in bm.verts if v.co.x > 0.01)
    sym_ratio = min(left, right) / max(left, right, 1)
    symmetry_score = 0.7 + (sym_ratio * 0.3)

    bm.free()

    weights = {"density": 0.2, "sharp": 0.3, "manifold": 0.3, "symmetry": 0.2}
    overall = (
        density_score * weights["density"]
        + sharp_score * weights["sharp"]
        + manifold_score * weights["manifold"]
        + symmetry_score * weights["symmetry"]
    )

    return {
        "success": True,
        "confidence": round(overall, 2),
        "reliability": "high" if overall > 0.8 else "medium" if overall > 0.6 else "low",
        "factors": {
            "density_appropriateness": {
                "score": round(density_score, 2),
                "weight": weights["density"],
            },
            "sharp_edge_preservation": {"score": round(sharp_score, 2), "weight": weights["sharp"]},
            "manifold_integrity": {
                "score": round(manifold_score, 2),
                "weight": weights["manifold"],
            },
            "symmetry": {"score": round(symmetry_score, 2), "weight": weights["symmetry"]},
        },
        "risk_factors": [
            f"{non_manifold} non-manifold edges" if non_manifold > 0 else None,
            f"{sharp_edges} sharp edges to preserve" if sharp_edges > 50 else None,
        ],
        "recommendation": _get_confidence_recommendation(overall, "AUTO_RETOPOLOGY"),
    }


def _confidence_smart_decimate(obj, params):  # type: ignore[no-untyped-def]
    """CONFIDENCE: Calculate reliability for decimation."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="CONFIDENCE_SMART_DECIMATE",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for decimation confidence check",
        )

    target_ratio = params.get("target_ratio", 0.5)
    preserve_features = params.get("preserve_features", True)

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    # Factor 1: Decimation ratio
    if target_ratio > 0.7:
        ratio_score = 0.95
    elif target_ratio > 0.4:
        ratio_score = 0.85
    elif target_ratio > 0.2:
        ratio_score = 0.7
    else:
        ratio_score = 0.5

    # Factor 2: Feature preservation capability
    sharp_edges = sum(1 for e in bm.edges if not e.smooth)
    if preserve_features:
        feature_score = 0.9 if sharp_edges < 100 else 0.75 if sharp_edges < 500 else 0.6
    else:
        feature_score = 0.8  # Uniform decimation is more predictable

    # Factor 3: Topology suitability
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    ngon_ratio = ngons / max(len(bm.faces), 1)
    topo_score = 1.0 - (ngon_ratio * 0.3)

    bm.free()

    weights = {"ratio": 0.3, "feature": 0.4, "topology": 0.3}
    overall = (
        ratio_score * weights["ratio"]
        + feature_score * weights["feature"]
        + topo_score * weights["topology"]
    )

    return {
        "success": True,
        "confidence": round(overall, 2),
        "reliability": "high" if overall > 0.8 else "medium" if overall > 0.6 else "low",
        "decimation_ratio": target_ratio,
        "preserve_features": preserve_features,
        "factors": {
            "ratio_appropriateness": {"score": round(ratio_score, 2), "weight": weights["ratio"]},
            "feature_preservation": {
                "score": round(feature_score, 2),
                "weight": weights["feature"],
            },
            "topology_suitability": {"score": round(topo_score, 2), "weight": weights["topology"]},
        },
        "visual_impact": (
            "minimal" if target_ratio > 0.7 else "moderate" if target_ratio > 0.4 else "significant"
        ),
        "recommendation": _get_confidence_recommendation(overall, "SMART_DECIMATE"),
    }


def _confidence_ai_material_suggest(obj, params):  # type: ignore[no-untyped-def]
    """CONFIDENCE: Calculate reliability for material suggestion."""
    name_lower = obj.name.lower()

    material_hints = {
        "metal": (["metal", "steel", "iron", "aluminum", "copper", "brass"], 0.9),
        "glass": (["glass", "crystal", "window", "lens"], 0.95),
        "wood": (["wood", "timber", "oak", "pine"], 0.85),
        "plastic": (["plastic", "pvc", "rubber"], 0.7),
        "fabric": (["cloth", "fabric", "cotton"], 0.8),
        "stone": (["stone", "rock", "concrete"], 0.85),
        "liquid": (["water", "liquid", "ocean"], 0.9),
        "skin": (["skin", "flesh", "character"], 0.75),
    }

    # Find matches
    matches = []
    for mat_type, (keywords, base_confidence) in material_hints.items():
        matched = [k for k in keywords if k in name_lower]
        if matched:
            matches.append(
                {
                    "type": mat_type,
                    "keywords": matched,
                    "confidence": base_confidence * (0.8 + 0.2 * len(matched)),
                }
            )

    if matches:
        best_match = max(matches, key=lambda x: float(cast(float, x["confidence"])))
        overall = min(float(cast(float, best_match["confidence"])), 0.95)
        detection_method = "keyword_match"
    else:
        overall = 0.5
        detection_method = "default_fallback"

    return {
        "success": True,
        "confidence": round(overall, 2),
        "reliability": "high" if overall > 0.8 else "medium" if overall > 0.6 else "low",
        "detection_method": detection_method,
        "matched_materials": matches,
        "limitation": "Detection based solely on object name, not visual analysis",
        "recommendation": "Verify visually and adjust PBR values as needed",
    }


def _confidence_smart_lighting(params):  # type: ignore[no-untyped-def]
    """CONFIDENCE: Calculate reliability for lighting setup."""
    scene = bpy.context.scene

    mesh_count = sum(1 for o in scene.objects if o.type == "MESH")
    has_character = any("char" in o.name.lower() for o in scene.objects)
    has_architecture = any(
        "building" in o.name.lower() or "room" in o.name.lower() for o in scene.objects
    )
    existing_lights = sum(1 for o in scene.objects if o.type == "LIGHT")

    # Factor 1: Scene clarity
    if has_character or has_architecture:
        clarity_score = 0.9
    elif mesh_count > 0:
        clarity_score = 0.8
    else:
        clarity_score = 0.4

    # Factor 2: Light conflict potential
    if existing_lights == 0:
        conflict_score = 1.0
    elif existing_lights < 3:
        conflict_score = 0.8
    else:
        conflict_score = 0.6

    # Factor 3: Scene complexity
    if mesh_count < 5:
        complexity_score = 0.95
    elif mesh_count < 20:
        complexity_score = 0.85
    else:
        complexity_score = 0.75

    weights = {"clarity": 0.4, "conflict": 0.3, "complexity": 0.3}
    overall = (
        clarity_score * weights["clarity"]
        + conflict_score * weights["conflict"]
        + complexity_score * weights["complexity"]
    )

    return {
        "success": True,
        "confidence": round(overall, 2),
        "reliability": "high" if overall > 0.8 else "medium" if overall > 0.6 else "low",
        "scene_factors": {
            "scene_clarity": {"score": round(clarity_score, 2), "weight": weights["clarity"]},
            "light_conflicts": {"score": round(conflict_score, 2), "weight": weights["conflict"]},
            "scene_complexity": {
                "score": round(complexity_score, 2),
                "weight": weights["complexity"],
            },
        },
        "scene_analysis": {
            "mesh_objects": mesh_count,
            "existing_lights": existing_lights,
            "detected_character": has_character,
            "detected_architecture": has_architecture,
        },
        "recommendation": _get_confidence_recommendation(overall, "SMART_LIGHTING"),
    }


def _confidence_auto_rig_suggest(obj, params):  # type: ignore[no-untyped-def]
    """CONFIDENCE: Calculate reliability for rig suggestion."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="CONFIDENCE_AUTO_RIG_SUGGEST",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for rig confidence check",
        )

    bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    dimensions = [max(v[i] for v in bbox) - min(v[i] for v in bbox) for i in range(3)]
    height, width, depth = sorted(dimensions, reverse=True)
    ratio = height / max(width, 0.001)

    # Factor 1: Proportion clarity
    if ratio > 3 or ratio < 0.5:
        clarity_score = 0.9  # Very tall or very flat = clear
    elif ratio > 2 or ratio < 0.7:
        clarity_score = 0.8
    else:
        clarity_score = 0.6  # Cube-like = ambiguous

    # Factor 2: Symmetry (symmetric meshes are easier to rig)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    left = sum(1 for v in bm.verts if v.co.x < -0.01)
    right = sum(1 for v in bm.verts if v.co.x > 0.01)
    sym_ratio = min(left, right) / max(left, right, 1)
    symmetry_score = 0.7 + (sym_ratio * 0.3)
    bm.free()

    # Factor 3: Topology quality
    vertex_count = len(obj.data.vertices)
    if vertex_count < 1000:
        topo_score = 0.9
    elif vertex_count < 10000:
        topo_score = 0.8
    else:
        topo_score = 0.7

    weights = {"clarity": 0.4, "symmetry": 0.35, "topology": 0.25}
    overall = (
        clarity_score * weights["clarity"]
        + symmetry_score * weights["symmetry"]
        + topo_score * weights["topology"]
    )

    return {
        "success": True,
        "confidence": round(overall, 2),
        "reliability": "high" if overall > 0.8 else "medium" if overall > 0.6 else "low",
        "dimensions": {
            "height": round(height, 2),
            "width": round(width, 2),
            "depth": round(depth, 2),
            "aspect_ratio": round(ratio, 2),
        },
        "factors": {
            "proportion_clarity": {"score": round(clarity_score, 2), "weight": weights["clarity"]},
            "symmetry": {"score": round(symmetry_score, 2), "weight": weights["symmetry"]},
            "topology_quality": {"score": round(topo_score, 2), "weight": weights["topology"]},
        },
        "recommendation": _get_confidence_recommendation(overall, "AUTO_RIG_SUGGEST"),
    }


def _confidence_auto_lod_generate(obj, params):  # type: ignore[no-untyped-def]
    """CONFIDENCE: Calculate reliability for LOD generation."""
    if obj.type != "MESH":
        return ResponseBuilder.error(
            handler="manage_ai_tools",
            action="CONFIDENCE_AUTO_LOD_GENERATE",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Object '{obj.name}' is type '{obj.type}', expected 'MESH'",
            suggestion="Select a mesh object for LOD confidence check",
        )

    vertex_count = len(obj.data.vertices)
    levels = params.get("levels", 3)

    # Factor 1: Mesh density
    if vertex_count > 10000:
        density_score = 0.95  # High density = good for LODs
    elif vertex_count > 2000:
        density_score = 0.85
    elif vertex_count > 500:
        density_score = 0.7
    else:
        density_score = 0.5  # Already low poly

    # Factor 2: Level appropriateness
    if levels <= 3:
        level_score = 0.95
    elif levels == 4:
        level_score = 0.85
    else:
        level_score = 0.7

    # Factor 3: Decimation suitability
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    ngon_ratio = ngons / max(len(bm.faces), 1)
    decimate_score = 1.0 - (ngon_ratio * 0.3)
    bm.free()

    weights = {"density": 0.4, "levels": 0.3, "decimation": 0.3}
    overall = (
        density_score * weights["density"]
        + level_score * weights["levels"]
        + decimate_score * weights["decimation"]
    )

    return {
        "success": True,
        "confidence": round(overall, 2),
        "reliability": "high" if overall > 0.8 else "medium" if overall > 0.6 else "low",
        "original_vertices": vertex_count,
        "requested_levels": levels,
        "factors": {
            "mesh_density": {"score": round(density_score, 2), "weight": weights["density"]},
            "level_appropriateness": {"score": round(level_score, 2), "weight": weights["levels"]},
            "decimation_suitability": {
                "score": round(decimate_score, 2),
                "weight": weights["decimation"],
            },
        },
        "warning": "Low vertex count - LODs may not be necessary" if vertex_count < 500 else None,
        "recommendation": _get_confidence_recommendation(overall, "AUTO_LOD_GENERATE"),
    }


def _get_confidence_recommendation(confidence, action):  # type: ignore[no-untyped-def]
    """Get recommendation based on confidence score."""
    if confidence > 0.85:
        return f"High confidence - proceed with {action}"
    elif confidence > 0.7:
        return "Good confidence - proceed, but review results"
    elif confidence > 0.5:
        return f"Moderate confidence - consider EXPLAIN_{action} first"
    else:
        return "Low confidence - manual approach recommended"
