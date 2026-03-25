"""
Tool Groups Handler for Blender MCP 1.0.0

Provides workflow-based tool grouping for easier discovery.
Groups 64 handlers into logical workflows.
"""

from typing import List, Dict, Any, cast
from ..core.thread_safety import ensure_main_thread
from ..dispatcher import register_handler
from ..core.parameter_validator import validated_handler
from ..core.enums import ToolGroupsAction
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils

logger = get_logger()


# Predefined workflow groups
TOOL_GROUPS = {
    "SCENE_SETUP": {
        "name": "Scene Setup",
        "description": "Initialize and configure new scenes",
        "icon": "SCENE",
        "handlers": [
            "manage_scene",
            "manage_camera",
            "manage_light",
            "manage_collections_advanced",
        ],
        "typical_actions": [
            {"handler": "manage_scene", "action": "NEW_SCENE", "description": "Create new scene"},
            {"handler": "manage_camera", "action": "CREATE", "description": "Add camera"},
            {
                "handler": "manage_light",
                "action": "SETUP_THREE_POINT",
                "description": "Setup lighting",
            },
            {
                "handler": "manage_collections_advanced",
                "action": "CREATE",
                "description": "Organize collections",
            },
        ],
    },
    "MODELING_WORKFLOW": {
        "name": "Modeling Workflow",
        "description": "Complete mesh modeling pipeline",
        "icon": "MESH",
        "handlers": [
            "manage_modeling",
            "manage_bmesh_edit",
            "manage_sculpting",
            "manage_uvs",
            "manage_uv_advanced",
        ],
        "typical_actions": [
            {
                "handler": "manage_modeling",
                "action": "ADD_PRIMITIVE",
                "description": "Start with primitive",
            },
            {
                "handler": "manage_sculpting",
                "action": "ENTER_MODE",
                "description": "Sculpt details",
            },
            {
                "handler": "manage_bmesh_edit",
                "action": "SUBDIVIDE",
                "description": "Refine topology",
            },
            {"handler": "manage_uvs", "action": "UNWRAP", "description": "UV mapping"},
        ],
    },
    "RETARGET_RETOPOLOGY": {
        "name": "Retopology & Optimization",
        "description": "Mesh optimization and cleanup",
        "icon": "MESH_DATA",
        "handlers": ["manage_ai_tools", "manage_bmesh_edit", "manage_modeling"],
        "typical_actions": [
            {
                "handler": "manage_ai_tools",
                "action": "EXPLAIN_AUTO_RETOPOLOGY",
                "description": "Analyze retopology strategy",
            },
            {
                "handler": "manage_ai_tools",
                "action": "DRY_RUN_AUTO_RETOPOLOGY",
                "description": "Preview retopology",
            },
            {
                "handler": "manage_ai_tools",
                "action": "AUTO_RETOPOLOGY",
                "description": "Auto retopologize",
            },
            {
                "handler": "manage_ai_tools",
                "action": "SMART_DECIMATE",
                "description": "Optimize polygon count",
            },
        ],
    },
    "MATERIAL_WORKFLOW": {
        "name": "Materials & Texturing",
        "description": "Create and apply materials",
        "icon": "MATERIAL",
        "handlers": ["manage_materials", "manage_bake", "manage_uvs", "manage_ai_tools"],
        "typical_actions": [
            {
                "handler": "manage_ai_tools",
                "action": "AI_MATERIAL_SUGGEST",
                "description": "Get material suggestions",
            },
            {"handler": "manage_materials", "action": "CREATE", "description": "Create material"},
            {
                "handler": "manage_uvs",
                "action": "UNWRAP",
                "description": "Smart UV Project",
            },
            {"handler": "manage_bake", "action": "BAKE_NORMAL", "description": "Bake normal maps"},
        ],
    },
    "CHARACTER_WORKFLOW": {
        "name": "Character Creation",
        "description": "Complete character pipeline",
        "icon": "ARMATURE",
        "handlers": [
            "manage_modeling",
            "manage_sculpting",
            "manage_ai_tools",
            "manage_uvs",
            "manage_materials",
            "manage_rigging",
            "manage_animation",
        ],
        "typical_actions": [
            {"handler": "manage_modeling", "action": "ADD_PRIMITIVE", "description": "Base mesh"},
            {
                "handler": "manage_sculpting",
                "action": "ENTER_MODE",
                "description": "Sculpt character",
            },
            {
                "handler": "manage_ai_tools",
                "action": "AUTO_RETOPOLOGY",
                "description": "Game-ready topology",
            },
            {"handler": "manage_rigging", "action": "CREATE", "description": "Create rig base"},
            {
                "handler": "manage_animation",
                "action": "INSERT_KEYFRAME",
                "description": "Create poses",
            },
        ],
    },
    "ANIMATION_WORKFLOW": {
        "name": "Animation",
        "description": "Animate and rig objects",
        "icon": "ANIM",
        "handlers": [
            "manage_rigging",
            "manage_constraints",
            "manage_drivers",
            "manage_animation",
            "manage_animation_advanced",
            "manage_mocap",
        ],
        "typical_actions": [
            {"handler": "manage_rigging", "action": "CREATE", "description": "Create skeleton"},
            {"handler": "manage_rigging", "action": "EXTRUDE", "description": "Extend bone chain"},
            {
                "handler": "manage_constraints",
                "action": "ADD_CONSTRAINT",
                "description": "Add IK/FK",
            },
            {"handler": "manage_animation", "action": "INSERT_KEYFRAME", "description": "Animate"},
            {
                "handler": "manage_animation_advanced",
                "action": "WALK_CYCLE_GENERATE",
                "description": "Procedural animation",
            },
        ],
    },
    "RENDERING_WORKFLOW": {
        "name": "Rendering & Output",
        "description": "Setup rendering and export",
        "icon": "RENDER",
        "handlers": [
            "manage_camera",
            "manage_light",
            "manage_rendering",
            "manage_render_optimization",
            "manage_eevee_next",
            "manage_bake",
            "manage_compositing",
        ],
        "typical_actions": [
            {"handler": "manage_camera", "action": "FRAME_OBJECT", "description": "Frame subject"},
            {
                "handler": "manage_render_optimization",
                "action": "OPTIMIZE_SAMPLES",
                "description": "Optimize for render",
            },
            {
                "handler": "manage_rendering",
                "action": "SET_QUALITY_PRESET",
                "description": "Set quality",
            },
            {"handler": "manage_rendering", "action": "RENDER_FRAME", "description": "Render"},
        ],
    },
    "GAME_EXPORT": {
        "name": "Game Engine Export",
        "description": "Export for Unity/Unreal",
        "icon": "EXPORT",
        "handlers": ["manage_export_pipeline", "manage_bake", "manage_ai_tools", "manage_export"],
        "typical_actions": [
            {
                "handler": "manage_ai_tools",
                "action": "AUTO_LOD_GENERATE",
                "description": "Generate LODs",
            },
            {"handler": "manage_bake", "action": "BAKE_NORMAL", "description": "Bake maps"},
            {
                "handler": "manage_export_pipeline",
                "action": "VALIDATE_FOR_EXPORT",
                "description": "Validate scene",
            },
            {
                "handler": "manage_export_pipeline",
                "action": "EXPORT_GLTF_DRACO",
                "description": "Export with compression",
            },
        ],
    },
    "PHYSICS_SIMULATION": {
        "name": "Physics & Simulation",
        "description": "Add physics effects",
        "icon": "PHYSICS",
        "handlers": ["manage_physics", "manage_simulation_presets"],
        "typical_actions": [
            {
                "handler": "manage_simulation_presets",
                "action": "PRESET_FABRIC_DRAPE",
                "description": "Cloth simulation",
            },
            {
                "handler": "manage_physics",
                "action": "RIGID_BODY_ADD",
                "description": "Add rigid body",
            },
            {
                "handler": "manage_physics",
                "action": "PARTICLE_HAIR",
                "description": "Hair particles",
            },
        ],
    },
    "AI_EXTERNAL": {
        "name": "AI & External Tools",
        "description": "AI generation and external integrations",
        "icon": "WORLD",
        "handlers": [
            "manage_ai_tools",
            "manage_procedural",
            "integration_hunyuan",
            "integration_hyper3d",
            "integration_polyhaven",
            "integration_sketchfab",
        ],
        "typical_actions": [
            {
                "handler": "integration_hunyuan",
                "action": "GENERATE",
                "description": "Text/Image to 3D (Hunyuan)",
            },
            {
                "handler": "integration_polyhaven",
                "action": "IMPORT_HDRI",
                "description": "Free HDRI",
            },
            {
                "handler": "manage_ai_tools",
                "action": "AUTO_RETOPOLOGY",
                "description": "Auto retopology",
            },
            {
                "handler": "manage_procedural",
                "action": "TERRAIN_GENERATE",
                "description": "Procedural terrain",
            },
        ],
    },
    "SCENE_OPTIMIZATION": {
        "name": "Scene Optimization",
        "description": "Optimize and cleanup scenes",
        "icon": "MODIFIER",
        "handlers": ["manage_profiling", "manage_bmesh_edit", "manage_batch", "manage_ai_tools"],
        "typical_actions": [
            {
                "handler": "manage_profiling",
                "action": "SCENE_STATS",
                "description": "Analyze scene",
            },
            {"handler": "manage_bmesh_edit", "action": "ANALYZE", "description": "Check meshes"},
            {
                "handler": "manage_ai_tools",
                "action": "SMART_CLEANUP",
                "description": "Cleanup mesh",
            },
            {
                "handler": "manage_batch",
                "action": "APPLY_MODIFIERS",
                "description": "Apply all modifiers",
            },
        ],
    },
    "ARCHVIZ_WORKFLOW": {
        "name": "Architectural Visualization",
        "description": "Archviz specific workflow",
        "icon": "MOD_BUILD",
        "handlers": [
            "manage_modeling",
            "manage_procedural",
            "manage_light",
            "manage_camera",
            "manage_render_optimization",
        ],
        "typical_actions": [
            {
                "handler": "manage_procedural",
                "action": "TERRAIN_GENERATE",
                "description": "Environment",
            },
            {
                "handler": "manage_modeling",
                "action": "ADD_PRIMITIVE",
                "description": "Building blocks",
            },
            {"handler": "manage_light", "action": "CREATE", "description": "Sun lighting"},
            {"handler": "manage_camera", "action": "FRAME_OBJECT", "description": "Composition"},
            {
                "handler": "manage_render_optimization",
                "action": "OPTIMIZE_SAMPLES",
                "description": "Optimize",
            },
        ],
    },
}


@register_handler(
    "manage_tool_groups",
    actions=[a.value for a in ToolGroupsAction],
    category="utility",
    priority=60,
    schema={
        "type": "object",
        "title": "Tool Groups — Workflow Discovery (STANDARD)",
        "description": (
            "STANDARD — Organize all handlers into logical workflow groups for task-based discovery.\n\n"
            "Use SUGGEST_GROUP with a task description to find relevant handlers. "
            "Use GET_WORKFLOW for step-by-step guides.\n"
            "ACTIONS: LIST_GROUPS, GET_GROUP, GET_WORKFLOW, SUGGEST_GROUP"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(ToolGroupsAction, "Action to perform"),
            "group_name": {"type": "string", "description": "Group name for GET_GROUP action"},
            "task_description": {
                "type": "string",
                "description": "Task description for SUGGEST_GROUP (e.g., 'I want to create a game character')",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in ToolGroupsAction])
def manage_tool_groups(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Tool Groups - Workflow-based handler organization.

    Groups 64 handlers into 12 logical workflows for easier discovery.

    Actions:
    - LIST_GROUPS: List all available workflow groups
    - GET_GROUP: Get details for a specific group
    - GET_WORKFLOW: Get step-by-step workflow
    - SUGGEST_GROUP: Suggest best group for a task
    """
    if not action:
        return ResponseBuilder.error(
            handler="manage_tool_groups",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == ToolGroupsAction.LIST_GROUPS.value:
        return _list_groups()  # type: ignore[no-any-return]

    elif action == ToolGroupsAction.GET_GROUP.value:
        group_name = params.get("group_name")
        if not group_name:
            return ResponseBuilder.error(
                handler="manage_tool_groups",
                action=action,
                error_code="MISSING_PARAMETER",
                message="Missing 'group_name' parameter",
            )
        return _get_group(group_name)  # type: ignore[no-any-return]

    elif action == ToolGroupsAction.GET_WORKFLOW.value:
        group_name = params.get("group_name")
        if not group_name:
            return ResponseBuilder.error(
                handler="manage_tool_groups",
                action=action,
                error_code="MISSING_PARAMETER",
                message="Missing 'group_name' parameter",
            )
        return _get_workflow(group_name)  # type: ignore[no-any-return]

    elif action == ToolGroupsAction.SUGGEST_GROUP.value:
        task = params.get("task_description")
        if not task:
            return ResponseBuilder.error(
                handler="manage_tool_groups",
                action=action,
                error_code="MISSING_PARAMETER",
                message="Missing 'task_description' parameter",
            )
        return _suggest_group(task)  # type: ignore[no-any-return]

    return ResponseBuilder.error(
        handler="manage_tool_groups",
        action=action,
        error_code="MISSING_PARAMETER",
        message=f"Unknown action: {action}",
    )


def _list_groups():  # type: ignore[no-untyped-def]
    """List all available tool groups."""
    groups_summary = []

    for key, group in TOOL_GROUPS.items():
        groups_summary.append(
            {
                "id": key,
                "name": group["name"],
                "description": group["description"],
                "icon": group.get("icon", "NONE"),
                "handler_count": len(group["handlers"]),
                "handlers": group["handlers"],
            }
        )

    return ResponseBuilder.success(
        handler="manage_tool_groups",
        action="LIST_GROUPS",
        data={
            "total_groups": len(groups_summary),
            "groups": groups_summary,
            "note": "Use GET_GROUP with group_name for detailed info",
        },
    )


def _get_group(group_name):  # type: ignore[no-untyped-def]
    """Get detailed information about a specific group."""
    group = TOOL_GROUPS.get(group_name)

    if not group:
        available = list(TOOL_GROUPS.keys())
        return ResponseBuilder.error(
            handler="manage_tool_groups",
            action="GET_GROUP",
            error_code="OBJECT_NOT_FOUND",
            message=f"Group '{group_name}' not found",
            details={"requested": group_name, "available": available},
            suggestion=f"Available groups: {', '.join(available)}",
        )

    return ResponseBuilder.success(
        handler="manage_tool_groups",
        action="GET_GROUP",
        data={
            "group": {
                "id": group_name,
                "name": group["name"],
                "description": group["description"],
                "icon": group.get("icon", "NONE"),
                "handlers": group["handlers"],
                "handler_count": len(group["handlers"]),
                "typical_actions": group.get("typical_actions", []),
            }
        },
    )


def _get_workflow(group_name):  # type: ignore[no-untyped-def]
    """Get step-by-step workflow for a group."""
    group = TOOL_GROUPS.get(group_name)

    if not group:
        available = list(TOOL_GROUPS.keys())
        return ResponseBuilder.error(
            handler="manage_tool_groups",
            action="GET_WORKFLOW",
            error_code="OBJECT_NOT_FOUND",
            message=f"Group '{group_name}' not found",
            details={"requested": group_name, "available": available},
        )

    steps = cast(List[Dict[str, Any]], group.get("typical_actions", []))

    # Add step numbers
    numbered_steps = [{"step": i + 1, **step} for i, step in enumerate(steps)]

    return ResponseBuilder.success(
        handler="manage_tool_groups",
        action="GET_WORKFLOW",
        data={
            "workflow": {
                "name": group["name"],
                "description": group["description"],
                "total_steps": len(numbered_steps),
                "steps": numbered_steps,
                "estimated_time": f"{len(numbered_steps) * 5}-{len(numbered_steps) * 15} minutes",
            }
        },
    )


def _suggest_group(task_description):  # type: ignore[no-untyped-def]
    """Suggest best group(s) for a task description."""
    task_lower = task_description.lower()

    # Keywords mapping
    keywords = {
        "SCENE_SETUP": ["new scene", "setup", "initialize", "start", "create scene"],
        "MODELING_WORKFLOW": ["model", "mesh", "sculpt", "modeling", "geometry"],
        "RETARGET_RETOPOLOGY": ["retopo", "retopology", "optimize", "decimate", "low poly"],
        "MATERIAL_WORKFLOW": ["material", "texture", "shader", "pbr", "paint"],
        "CHARACTER_WORKFLOW": ["character", "human", "creature", "biped", "npc"],
        "ANIMATION_WORKFLOW": ["animate", "rig", "bone", "keyframe", "motion"],
        "RENDERING_WORKFLOW": ["render", "lighting", "camera", "output", "image"],
        "GAME_EXPORT": ["export", "unity", "unreal", "game", "gltf", "fbx", "lod"],
        "PHYSICS_SIMULATION": ["physics", "cloth", "fluid", "simulation", "particle"],
        "AI_EXTERNAL": ["ai", "generate", "hunyuan", "polyhaven", "download", "import"],
        "SCENE_OPTIMIZATION": ["optimize", "cleanup", "fix", "performance", "memory"],
        "ARCHVIZ_WORKFLOW": ["architecture", "building", "interior", "exterior", "house"],
    }

    # Score each group
    scores = {}
    for group, words in keywords.items():
        score = sum(2 if word in task_lower else 0 for word in words)
        if score > 0:
            scores[group] = score

    # Sort by score
    sorted_groups = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Build suggestions
    suggestions: List[Dict[str, Any]] = []
    for group_name, score in sorted_groups[:3]:  # Top 3
        group_data = TOOL_GROUPS[group_name]
        suggestions.append(
            {
                "group_id": group_name,
                "name": group_data["name"],
                "description": group_data["description"],
                "match_score": score,
                "handlers": cast(List[str], group_data["handlers"])[
                    :10
                ],  # First 10 handlers (Bandwidth increased)
                "handler_count": len(group_data["handlers"]),
            }
        )

    return ResponseBuilder.success(
        handler="manage_tool_groups",
        action="SUGGEST_GROUP",
        data={
            "task": task_description,
            "suggestions": suggestions,
            "primary_suggestion": suggestions[0] if suggestions else None,
            "note": "Use GET_WORKFLOW with group_name for step-by-step guide",
        },
    )
