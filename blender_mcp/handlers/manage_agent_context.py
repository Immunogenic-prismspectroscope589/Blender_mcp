"""
Agent Context Handler for Blender MCP 1.0.0

Provides Meta-Cognitive Introspection (RAG Context) capabilities for the Agent.
Allows the agent to search and understand available tools without blowing up
the context window.
"""

from typing import Any, Dict, Optional
from ..core.enums import AgentContextAction
from ..core.response_builder import ResponseBuilder
from ..core.validation_utils import ValidationUtils
from ..core.tool_discovery import ToolCatalog
from ..dispatcher import register_handler
from ..core.parameter_validator import validated_handler

# Instantiate the catalog once
_catalog = ToolCatalog()


@register_handler(
    "manage_agent_context",
    actions=[a.value for a in AgentContextAction],
    category="utility",
    priority=6,
    schema={
        "type": "object",
        "title": "Agent Context — Self-Discovery & Quick-Start Primer",
        "description": (
            "TIER 1 DISCOVERY — The agent's self-awareness tool. Call GET_PRIMER first when starting a new session "
            "to understand the essential workflow, critical warnings, and tool priorities.\n\n"
            "Actions:\n"
            "  GET_PRIMER         — Quick-start guide: essential tools, workflow steps, scene_perception_pattern (call first!)\n"
            "  GET_TACTICS        — Assembly tactics, model type patterns, quality checklist for drone/vehicle/character\n"
            "  SEARCH_TOOLS       — Semantic search over all registered tools by keyword\n"
            "  GET_TOOL_CATALOG   — Full or category-filtered tool catalog\n"
            "  GET_ACTION_HELP    — Full schema + valid actions for a specific tool\n\n"
            "Designed to preserve context window: never dumps all tools at once."
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                AgentContextAction, "Context search action"
            ),
            "query": {
                "type": "string",
                "description": "Search term for tools (e.g., 'rig', 'export to unity'). Required for SEARCH_TOOLS.",
            },
            "category": {
                "type": "string",
                "description": "Optional category filter for GET_TOOL_CATALOG (e.g., 'animation', 'export').",
            },
            "tool_name": {
                "type": "string",
                "description": "Specific tool/handler name for GET_ACTION_HELP (e.g., 'manage_animation').",
            },
            "action_name": {
                "type": "string",
                "description": "Action name if getting help for a specific action (e.g., 'INSERT_KEYFRAME').",
            },
        },
        "required": ["action"],
    },
)
@validated_handler(actions=[a.value for a in AgentContextAction])
def manage_agent_context(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Agent Context RAG endpoints.
    Allows the agent to dynamically search for tools and actions.
    """
    if not action:
        return ResponseBuilder.error(
            handler="manage_agent_context",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == AgentContextAction.GET_PRIMER.value:
        return _get_primer()

    if action == AgentContextAction.SEARCH_TOOLS.value:
        query = params.get("query")
        if not query:
            return ResponseBuilder.error(
                handler="manage_agent_context",
                action=action,
                error_code="MISSING_PARAMETER",
                message="Missing 'query' parameter.",
            )
        return _search_tools(query)

    elif action == AgentContextAction.GET_TOOL_CATALOG.value:
        category = params.get("category")
        return _get_tool_catalog(category)

    elif action == AgentContextAction.GET_ACTION_HELP.value:
        tool_name = params.get("tool_name")
        action_name = params.get("action_name")
        if not tool_name:
            return ResponseBuilder.error(
                handler="manage_agent_context",
                action=action,
                error_code="MISSING_PARAMETER",
                message="Missing 'tool_name' parameter.",
            )
        return _get_action_help(tool_name, action_name)

    elif action == AgentContextAction.GET_TACTICS.value:
        return _get_tactics()

    return ResponseBuilder.error(
        handler="manage_agent_context",
        action=action,
        error_code="MISSING_PARAMETER",
        message=f"Unknown action: {action}",
    )


def _get_primer() -> dict[str, Any]:
    """Return a structured quick-start guide for agents connecting to this MCP server."""
    primer: Dict[str, Any] = {
        "title": "Blender MCP — Agent Quick-Start Primer",
        "version": "1.0.0",
        "architecture": "Claude ↔ stdio_bridge.py (stdio MCP) ↔ TCP:9879 ↔ Blender Addon ↔ bpy API",
        "essential_workflow": {
            "step_1_create_or_modify": {
                "tool": "execute_blender_code",
                "description": (
                    "PRIMARY tool for all creation/modification. Full bpy Python API access. "
                    "ALWAYS use bpy.data API (not bpy.ops) for object creation to avoid context errors."
                ),
                "good_pattern": (
                    "me = bpy.data.meshes.new('MyMesh'); obj = bpy.data.objects.new('MyObj', me); "
                    "bpy.context.scene.collection.objects.link(obj); obj.location = (1, 2, 3)"
                ),
                "bad_pattern": "bpy.ops.mesh.primitive_cube_add()  # Fails without correct context",
            },
            "step_2_inspect_scene": {
                "tool": "get_scene_graph",
                "action": "GET_OBJECTS_FLAT",
                "description": (
                    "Fast world-space overview of ALL objects. Returns world_location, dimensions, parent, "
                    "geometry_center_world, origin_offset_warning. "
                    "CRITICAL: Use world_location — NOT location (which is parent-relative and shows [0,0,0] for parented objects)."
                ),
            },
            "step_3_visual_verify": {
                "tool": "get_viewport_screenshot_base64",
                "description": (
                    "Capture viewport images returned as base64 directly to Claude's context. "
                    "Use views=['FRONT','TOP','RIGHT','ISOMETRIC'] for full 4-angle inspection. "
                    "Use frame=N to capture at a specific animation frame."
                ),
            },
            "step_4_object_detail": {
                "tool": "get_object_info",
                "description": (
                    "Deep per-object inspection: world_location, world_bounding_box, geometry_center_world, "
                    "origin_offset (to detect origin ≠ geometry center issues), animation_data (action name, "
                    "fcurves — warns if transforms will be overridden by animation)."
                ),
            },
            "step_5_discover_more": {
                "tool": "manage_agent_context",
                "actions": ["SEARCH_TOOLS", "GET_TOOL_CATALOG", "GET_ACTION_HELP"],
                "description": (
                    "PRIMARY: get_scene_graph action=GET_OBJECTS_FLAT — fast, ALL objects, world+local+hierarchy. "
                    "DETAIL: get_object_info name=X — deep per-object analysis. "
                    "DISCOVER: SEARCH_TOOLS/GET_TOOL_CATALOG for specialized tools."
                ),
            },
        },
        "critical_warnings": [
            "NEVER use 'location' from get_scene_graph — it is LOCAL (parent-relative) and shows [0,0,0] for parented objects.",
            "ALWAYS use 'world_location' for absolute scene coordinates.",
            "execute_code is DEPRECATED — always use execute_blender_code.",
            "If object.animation_data is set, manual rotation/location writes are overridden each frame. "
            "Call obj.animation_data_clear() before setting transforms.",
            "If 'origin_offset_warning' is true in GET_OBJECTS_FLAT/get_object_info, the object's pivot "
            "is not at its geometry center — rotations will orbit around the wrong point.",
            "For parenting: use world coordinates for placement, then re-parent. "
            "After parenting, child.location becomes parent-relative.",
        ],
        "common_agent_mistakes": [
            {
                "mistake": "Using get_scene_graph 'location' as world position",
                "fix": "Use 'world_location' field or GET_OBJECTS_FLAT action",
            },
            {
                "mistake": "Setting rotation_euler then it resets next frame",
                "fix": "Check animation_data in get_object_info; call obj.animation_data_clear() first",
            },
            {
                "mistake": "Object parts appear detached after assembly",
                "fix": "Check origin_offset_warning in get_object_info — origin may not be at geometry center",
            },
            {
                "mistake": "bpy.ops.* fails with context error",
                "fix": "Use bpy.data API instead: bpy.data.objects.new() / mesh.from_pydata() etc.",
            },
            {
                "mistake": "Screenshot shows wrong frame or wrong angle",
                "fix": "Use frame=N param to set frame, use views=['FRONT','TOP','RIGHT'] for multi-angle",
            },
        ],
        "tier1_tools": [
            {
                "name": "execute_blender_code",
                "priority": 1,
                "role": "Primary code execution — full bpy API",
            },
            {
                "name": "get_scene_graph",
                "priority": 2,
                "role": "Primary scene survey — GET_OBJECTS_FLAT for fast world-position + hierarchy overview",
            },
            {
                "name": "get_viewport_screenshot_base64",
                "priority": 3,
                "role": "Visual feedback — multi-angle with views=[], frame=N for specific frame",
            },
            {
                "name": "get_object_info",
                "priority": 4,
                "role": "Deep per-object inspection incl. animation_data + geometry_center",
            },
            {
                "name": "manage_agent_context",
                "priority": 6,
                "role": "Self-discovery — GET_PRIMER, SEARCH_TOOLS, GET_ACTION_HELP, GET_TACTICS",
            },
            {
                "name": "list_all_tools",
                "priority": 7,
                "role": "Full tool listing — use intent= for filtered results",
            },
        ],
        "scene_perception_pattern": {
            "description": (
                "Use this pattern when world_location=[0,0,0] for multiple objects "
                "(common with drones, vehicles, character rigs with origins at world center)."
            ),
            "step_1": (
                "GET_OBJECTS_FLAT → first. origin_offset_warning=True olan → "
                "mesh is NOT at world_location. Use geometry_center_world for actual position."
            ),
            "step_2": (
                "world_location=[0,0,0] is NORMAL for parented rigs. "
                "Use geometry_center_world for spatial reasoning. "
                "execute_blender_code: verts_world = [obj.matrix_world @ v.co for v in obj.data.vertices]"
            ),
            "step_3": (
                "get_viewport_screenshot_base64 → visual confirmation of actual object placement"
            ),
            "key_insight": (
                "world_location = ORIGIN (pivot point, often at [0,0,0] for parented objects). "
                "geometry_center_world = WHERE THE MESH ACTUALLY IS. "
                "Always use geometry_center_world for parented/rigged objects."
            ),
            "example_code": (
                "obj = bpy.data.objects['Drone_Arm_L']\n"
                "verts_world = [obj.matrix_world @ v.co for v in obj.data.vertices]\n"
                "xs = [v.x for v in verts_world]\n"
                "ys = [v.y for v in verts_world]\n"
                "zs = [v.z for v in verts_world]\n"
                "print(f'X: {min(xs):.3f} to {max(xs):.3f}')\n"
                "print(f'Y: {min(ys):.3f} to {max(ys):.3f}')\n"
                "print(f'Z: {min(zs):.3f} to {max(zs):.3f}')"
            ),
        },
    }
    return ResponseBuilder.success(
        handler="manage_agent_context",
        action="GET_PRIMER",
        data=primer,
    )


def _search_tools(query: str) -> dict[str, Any]:
    """RAG-style semantic search over available tools.

    Searches HANDLER_METADATA (the live dispatcher registry) directly so results
    reflect all registered handlers, then falls back to ToolCatalog for fuzzy matching.
    """
    from ..dispatcher import HANDLER_METADATA

    tokens = [t.lower() for t in query.split() if t]
    if not tokens:
        return ResponseBuilder.error(
            handler="manage_agent_context",
            action="SEARCH_TOOLS",
            error_code="QUERY_TOO_SHORT",
            message="Query is empty. Provide at least one keyword.",
        )

    matches = []
    seen: set = set()

    # Primary: search HANDLER_METADATA (always populated from @register_handler)
    for handler_name, meta in HANDLER_METADATA.items():
        name_lower = handler_name.lower()
        desc_lower = str(meta.get("description", "")).lower()
        category_lower = str(meta.get("category", "")).lower()
        actions_lower = " ".join(str(a) for a in meta.get("actions", [])).lower()
        combined = f"{name_lower} {desc_lower} {category_lower} {actions_lower}"
        if any(t in combined for t in tokens):
            if handler_name not in seen:
                seen.add(handler_name)
                matches.append(
                    {
                        "tool_name": handler_name,
                        "category": meta.get("category", ""),
                        "description": str(meta.get("description", ""))[:120],
                        "actions": meta.get("actions", [])[:10],
                    }
                )

    # Secondary: ToolCatalog fuzzy search for additional results
    catalog_results = _catalog.search(query)
    for tool_name, score in catalog_results[:10]:
        if tool_name not in seen:
            seen.add(tool_name)
            tool_info = _catalog.get_tool(tool_name)
            if tool_info:
                catalog_match: Dict[str, Any] = {
                    "tool_name": tool_name,
                    "category": tool_info.category,
                    "description": tool_info.description[:120],
                    "actions": [a.name for a in tool_info.actions][:10],
                    "fuzzy_score": round(float(score), 2),
                }
                matches.append(catalog_match)

    if not matches:
        return ResponseBuilder.error(
            handler="manage_agent_context",
            action="SEARCH_TOOLS",
            error_code="NOT_FOUND",
            message=f"No tools found matching: {query!r}. Try broader terms or use GET_TOOL_CATALOG.",
        )

    return ResponseBuilder.success(
        handler="manage_agent_context",
        action="SEARCH_TOOLS",
        data={"query": query, "matches_found": len(matches), "top_matches": matches[:10]},
    )


def _get_tool_catalog(category: Optional[str]) -> dict[str, Any]:
    """Get the full catalog or a specific category — sourced from HANDLER_METADATA."""
    from ..dispatcher import HANDLER_METADATA

    tools_out: Dict[str, Any] = {}
    categories_seen: set = set()

    for handler_name, meta in HANDLER_METADATA.items():
        cat = str(meta.get("category", "general"))
        categories_seen.add(cat)
        if category and cat != category:
            continue
        tools_out[handler_name] = {
            "description": str(meta.get("description", ""))[:200],
            "category": cat,
            "priority": meta.get("priority", 100),
            "actions": meta.get("actions", []),
            "action_count": len(meta.get("actions", [])),
        }

    if category and not tools_out:
        return ResponseBuilder.error(
            handler="manage_agent_context",
            action="GET_TOOL_CATALOG",
            error_code="CATEGORY_NOT_FOUND",
            message=(
                f"No tools found in category '{category}'. "
                f"Available categories: {sorted(categories_seen)}"
            ),
        )

    return ResponseBuilder.success(
        handler="manage_agent_context",
        action="GET_TOOL_CATALOG",
        data={
            "category_filtered": category is not None,
            "category": category,
            "total_tools": len(tools_out),
            "available_categories": sorted(categories_seen),
            "tools": tools_out,
        },
    )


def _get_action_help(tool_name: str, action_name: Optional[str]) -> dict[str, Any]:
    """Get specific documentation/schema for a given tool/action — from HANDLER_METADATA."""
    from ..dispatcher import HANDLER_METADATA

    meta = HANDLER_METADATA.get(tool_name)
    if not meta:
        # Try to find similar tool name for helpful error
        close = [n for n in HANDLER_METADATA if tool_name.lower() in n.lower()]
        hint = f" Did you mean: {close[:3]}?" if close else ""
        return ResponseBuilder.error(
            handler="manage_agent_context",
            action="GET_ACTION_HELP",
            error_code="NOT_FOUND",
            message=f"Tool '{tool_name}' not registered.{hint}",
        )

    actions = meta.get("actions", [])
    schema = meta.get("schema", {})
    response_data: Dict[str, Any] = {
        "tool_name": tool_name,
        "category": meta.get("category", ""),
        "priority": meta.get("priority", 100),
        "actions": actions,
        "schema": schema,
    }

    if action_name:
        if action_name not in actions:
            return ResponseBuilder.error(
                handler="manage_agent_context",
                action="GET_ACTION_HELP",
                error_code="INVALID_ACTION",
                message=(
                    f"Action '{action_name}' is not valid for tool '{tool_name}'. "
                    f"Available: {actions}"
                ),
            )
        response_data["action_focused"] = action_name
        response_data["note"] = f"Action {action_name} is supported by {tool_name}."

    return ResponseBuilder.success(
        handler="manage_agent_context", action="GET_ACTION_HELP", data=response_data
    )


def _get_tactics() -> dict[str, Any]:
    """Return model assembly tactics and common workflow patterns for agents."""
    tactics: Dict[str, Any] = {
        "title": "Blender MCP — Agent Tactics Guide",
        "model_assembly_tactics": {
            "ground_truth_first": (
                "Run get_scene_graph GET_OBJECTS_FLAT immediately after scene load. "
                "Check geometry_center_world (not world_location) for mesh position. "
                "world_location=[0,0,0] is NORMAL for parented objects — not a bug. "
                "origin_offset_warning=True → pivot is far from geometry center — use geometry_center_world."
            ),
            "verify_with_vertices": (
                "For origin_offset objects, verify actual positions with: "
                "verts_world = [obj.matrix_world @ v.co for v in obj.data.vertices]. "
                "This gives true world-space vertex positions regardless of origin."
            ),
            "screenshot_after_each": (
                "After each major change, call get_viewport_screenshot_base64. "
                "Use target_object='ObjectName' for focused inspection. "
                "views=['ISOMETRIC','FRONT','TOP'] for full assembly check."
            ),
            "never_use_render_render": (
                "NEVER use bpy.ops.render.render() in execute_blender_code — "
                "it freezes Blender's main thread and the MCP server stops responding. "
                "Use manage_rendering action=RENDER_FRAME instead."
            ),
            "checkpoint_before_risky": (
                "Before destructive operations (delete objects, apply modifiers, bake), "
                "call manage_history PUSH_CHECKPOINT with a descriptive label."
            ),
            "assembly_check": (
                "Use get_scene_graph ANALYZE_ASSEMBLY to get a scored report "
                "of origin offsets, gaps, overlaps, and non-manifold edges. "
                "Score >= 90 is production-ready."
            ),
        },
        "common_model_types": {
            "vehicle_drone": (
                "Parts typically share a parent Empty at world origin. "
                "All children show world_location=[0,0,0] but geometry is offset. "
                "Use geometry_center_world (from get_scene_graph GET_OBJECTS_FLAT) "
                "or check vertices directly with matrix_world @ v.co."
            ),
            "character_rig": (
                "Armature parent + mesh children. Origins usually at world center. "
                "Use POSE_MODE for bone transforms. "
                "obj.location is meaningless for children — use matrix_world."
            ),
            "architectural": (
                "Large coordinate scales (building = 20m+). Set unit_system METRIC early. "
                "origin_offset common for architectural elements. "
                "Use get_scene_graph GET_SPATIAL_REPORT for per-object bounds."
            ),
            "prop_static": (
                "Should have origin at geometry center for correct rotation pivot. "
                "Run ANALYZE_ASSEMBLY — any origin_offset_warning means rotations look wrong. "
                "Fix: bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')."
            ),
        },
        "quality_checklist": [
            "All origins within 0.01m of geometry center (no origin_offset_warning) — "
            "use ANALYZE_ASSEMBLY to verify",
            "No non-manifold edges (ANALYZE_ASSEMBLY score >= 90) — "
            "non-manifold = not watertight, causes 3D print/render issues",
            "All MESH objects have material_count > 0 — use GET_OBJECTS_FLAT to check",
            "World location verified via geometry_center_world for all parented objects",
            "Animation frames verified with get_viewport_screenshot_base64 frame=N",
        ],
        "scene_perception_quick_ref": {
            "flat_list": "get_scene_graph GET_OBJECTS_FLAT — includes origin_offset_warning + hierarchy",
            "hierarchy": "get_scene_graph GET_OBJECTS_FLAT — children/matrix_world/location_local included",
            "single_object": "get_object_info — deep per-object analysis",
            "assembly_health": "get_scene_graph ANALYZE_ASSEMBLY — scored report",
            "visual": "get_viewport_screenshot_base64 — base64 image for AI vision",
        },
    }
    return ResponseBuilder.success(
        handler="manage_agent_context",
        action="GET_TACTICS",
        data=tactics,
    )
