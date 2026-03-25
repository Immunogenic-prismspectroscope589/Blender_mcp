"""
Smart Command Dispatcher for Blender MCP 1.0.0

Central command router with:
- Automatic parameter validation
- Security checks
- Thread-safe execution
- Structured logging
- Enhanced error reporting
- Action auto-discovery
"""

import importlib
import sys
import inspect
import pkgutil
import textwrap
import time
import traceback
from typing import Dict, Any, List, Optional, Callable, cast

from . import handlers
from .core.security import SecurityManager
from .core.parameter_validator import validate_params_schema

# V1.0.0: ResponseBuilder + Semantic Memory + Intent-Based Animation
from .core.thread_safety import ThreadSafety, execute_on_main_thread, is_main_thread
from .core.logging_config import MCPLogger, set_request_context, clear_request_context

from .core.types import HandlerProtocol, HandlerMetadata

# Registry to hold all registered handler functions
HANDLER_REGISTRY: Dict[str, HandlerProtocol] = {}
HANDLER_METADATA: Dict[str, HandlerMetadata] = {}
LOAD_ERRORS: List[str] = []

# Initialize logger
logger = MCPLogger()


def register_handler(
    command_name: str,
    actions: Optional[List[str]] = None,
    schema: Optional[Dict] = None,
    category: str = "general",
    description: Optional[str] = None,
    priority: int = 100,
) -> Callable[[Callable[..., Any]], HandlerProtocol]:
    """
    Decorator to register a function as a handler for a specific command.

    Args:
        command_name: The name of the tool (e.g., "edit_mesh")
        actions: List of valid actions this tool supports
        schema: JSON schema describing parameters
        category: Tool category for organization
        description: Human-readable description
        priority: Sort order for tool listing (lower = shown first).
                  1-9=ESSENTIAL, 10-49=CORE, 50-149=STANDARD, 150+=OPTIONAL/DEPRECATED
    """

    def decorator(func: Callable) -> HandlerProtocol:
        resolved_actions = list(actions or [])

        # If actions are omitted, infer them from schema.properties.action.enum
        # so dispatcher-level action validation remains consistent.
        if not resolved_actions and isinstance(schema, dict):
            action_schema = schema.get("properties", {}).get("action", {})
            enum_values = action_schema.get("enum") if isinstance(action_schema, dict) else None
            if isinstance(enum_values, list) and all(isinstance(v, str) for v in enum_values):
                resolved_actions = enum_values

        # GUARD: Prevent duplicate registrations from different modules.
        # Same-module re-registration is allowed (importlib.reload() case).
        if command_name in HANDLER_REGISTRY:
            existing_module = HANDLER_REGISTRY[command_name].__module__
            new_module = func.__module__
            if existing_module != new_module:
                raise RuntimeError(
                    f"[MCP REGISTRY ERROR] Duplicate handler registration for '{command_name}'\n"
                    f"  Already registered by: {existing_module}\n"
                    f"  Attempting to register from: {new_module}"
                )
            # Same module → importlib.reload() case — silently overwrite

        HANDLER_REGISTRY[command_name] = cast(HandlerProtocol, func)

        # Extract docstring as description
        doc_description = inspect.getdoc(func) or "No description provided."
        final_description = description or doc_description

        HANDLER_METADATA[command_name] = {
            "name": command_name,
            "description": final_description,
            "actions": resolved_actions,
            "schema": schema or {},
            "signature": str(inspect.signature(func)),
            "module": func.__module__,
            "category": category,
            "priority": priority,
        }

        # Attach metadata to function for introspection.
        # Use setattr so static checkers don't require dynamic attributes in Callable protocol.
        setattr(func, "_handler_name", command_name)
        setattr(func, "_handler_actions", resolved_actions)
        setattr(func, "_handler_schema", schema or {})
        setattr(func, "_handler_category", category)

        logger.debug(
            f"Registered handler: {command_name}",
            extra={"tool": command_name, "actions": resolved_actions, "category": category},
        )

        return cast(HandlerProtocol, func)

    return decorator


@register_handler(
    "get_server_status",
    schema={
        "type": "object",
        "title": "Get Server Status (ESSENTIAL)",
        "description": (
            "ESSENTIAL — First call to verify MCP connection and discover Blender environment. "
            "Returns server health, Blender version, UI language, handler count, and guided next steps.\n"
            "ACTIONS: get_server_status"
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_server_status"],
                "default": "get_server_status",
            }
        },
        "required": ["action"],
    },
    priority=8,
)
def get_server_status(**params: Any) -> Dict[str, Any]:
    """
    Diagnostic tool: Checks server health and lists any module loading errors.
    """
    import bpy

    # Get thread safety stats
    thread_stats = ThreadSafety().get_stats()

    # Detect Blender UI language
    blender_language = getattr(getattr(bpy.app, "translations", None), "locale", "en_US") or "en_US"

    return {
        "status": "active",
        "handler_errors": LOAD_ERRORS,
        "handler_count": len(HANDLER_REGISTRY),
        "version": "1.0.0",
        "blender_version": tuple(getattr(bpy.app, "version", (5, 0, 0))),
        "blender_language": blender_language,
        "tools": list(HANDLER_REGISTRY.keys()),
        "thread_stats": thread_stats,
        "next_step": (
            "Call list_all_tools to see all available tools sorted by priority. "
            "Call manage_agent_context with action=GET_PRIMER for the full workflow guide."
        ),
    }


def _format_tool_full(t: Dict[str, Any]) -> str:
    """Format a single tool in full inspect_tools style (used for ESSENTIAL tier)."""
    pri = t.get("priority", 100)
    name = t["name"]
    schema = t.get("schema", {})
    category = t.get("category", "general")
    description = str(t.get("description", "No description.")).strip()
    actions = t.get("actions", [])

    title_val = schema.get("title", name) if isinstance(schema, dict) else name

    lines: List[str] = []
    lines.append(f"[{pri:>3}] ⭐ {name}")
    lines.append(f"      Title    : {title_val}")
    lines.append(f"      Category : {category}")
    lines.append("      Description:")
    wrapped = textwrap.fill(description, width=80, subsequent_indent="       ")
    lines.append(f"       {wrapped}")

    if actions:
        lines.append(f"      Actions  : {', '.join(actions)}")

    # Parameters (skip 'action' param itself)
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required_fields = schema.get("required", []) if isinstance(schema, dict) else []
    param_items = [(k, v) for k, v in props.items() if k != "action" and isinstance(v, dict)]

    if param_items:
        lines.append(f"      Parameters ({len(param_items)}):")
        for idx, (pname, pdef) in enumerate(param_items):
            is_last = idx == len(param_items) - 1
            branch = "└──" if is_last else "├──"
            is_req = pname in required_fields
            tag = "REQ" if is_req else "OPT"
            ptype = pdef.get("type", "any")
            pdesc = pdef.get("description", "")
            enums = pdef.get("enum")
            default = pdef.get("default")
            parts = [f"[{tag}] {pname} ({ptype})"]
            if enums:
                parts.append(f"→ {{{', '.join(str(e) for e in enums)}}}")
            if not is_req and default is not None:
                parts.append(f"[default={default!r}]")
            if pdesc:
                parts.append(f"— {pdesc}")
            lines.append(f"        {branch} {' '.join(parts)}")

    return "\n".join(lines)


def _format_tool_row(idx: int, t: Dict[str, Any]) -> str:
    """Format a single tool as a compact table row (used for CORE/STANDARD/OPTIONAL)."""
    pri = t.get("priority", 100)
    name = t["name"]
    category = t.get("category", "general")
    actions = t.get("actions", [])
    action_str = ", ".join(actions[:4]) + ("…" if len(actions) > 4 else "")
    return f"  {idx:<4} {pri:<5} {name:<42} {category:<14} {action_str}"


def _build_system_manifest(tools_list: List[Any], title: str = "System Tools Manifest") -> str:
    """Helper to build a tiered Markdown manifest of tools.

    ESSENTIAL (priority 1-9)  → full inspect_tools format (title, category, description, params)
    CORE/STANDARD/OPTIONAL    → compact table format (PRI, TOOL NAME, CATEGORY, ACTIONS)

    Tier labels:
      ESSENTIAL (priority 1-9):  Must-use tools for any task
      CORE      (priority 10-49): Important standard tools
      STANDARD  (priority 50-149): All other registered tools
      OPTIONAL  (priority 150+): Deprecated / external integrations
    """
    lines = [f"# {title}"]

    tiers = [
        (1, 9, "ESSENTIAL — Start Here (highest priority)", True),
        (10, 49, "CORE Tools", False),
        (50, 149, "Standard Tools", False),
        (150, 9999, "Optional / Deprecated / Integrations", False),
    ]

    for lo, hi, label, full_format in tiers:
        tier_tools = sorted(
            [t for t in tools_list if lo <= t.get("priority", 100) <= hi],
            key=lambda x: (x.get("priority", 100), x["name"]),
        )
        if not tier_tools:
            continue
        lines.append(f"\n## ▸ {label}")

        if full_format:
            # ESSENTIAL: full detail format
            for t in tier_tools:
                lines.append("")
                lines.append(_format_tool_full(t))
        else:
            # CORE/STANDARD/OPTIONAL: compact table
            lines.append(f"  {'#':<4} {'PRI':<5} {'TOOL NAME':<42} {'CATEGORY':<14} ACTIONS")
            lines.append(f"  {'-' * 4} {'-' * 5} {'-' * 42} {'-' * 14} {'-' * 30}")
            for idx, t in enumerate(tier_tools, 1):
                lines.append(_format_tool_row(idx, t))

    return "\n".join(lines)


@register_handler(
    "list_all_tools",
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_all_tools"],
                "default": "list_all_tools",
            },
            "intent": {"type": "string", "description": "Filter tools by intent"},
            "category": {"type": "string", "description": "Filter tools by category"},
        },
        "required": ["action"],
    },
    priority=7,
    description=(
        "TIER 1 DISCOVERY — List all registered MCP tools with descriptions, actions, and priority tiers.\n\n"
        "Tools are returned in priority order: ESSENTIAL (1-9) → CORE (10-49) → STANDARD (50-149) → OPTIONAL (150+).\n"
        "Use intent='...' to filter by task (e.g., intent='I want to rig a character').\n"
        "Use manage_agent_context GET_PRIMER for a structured quick-start workflow guide."
    ),
)
def list_all_tools(**params: Any) -> Dict[str, Any]:
    """
    List all registered tools with their descriptions and available actions.

    V1.0.0: External integration handlers (integration_*) are always listed last
    to ensure they appear at the final 4 positions.

    V1.0.0: Intent-based filtering to reduce token usage.
             Use intent="I want to rig a character" to get only relevant tools (~15 instead of 64)
    """
    # V1.0.0: Intent-based routing
    intent = params.get("intent")
    category_filter = params.get("category")

    if intent:
        # Use IntentRouter to filter handlers
        try:
            from .core.intent_router import IntentRouter

            routing = IntentRouter.get_relevant_handlers(intent, include_external=True)
            relevant_handlers = set(routing["handlers"])

            # Filter metadata to only relevant handlers
            filtered_metadata = {
                name: meta for name, meta in HANDLER_METADATA.items() if name in relevant_handlers
            }

            filtered_list = sorted(
                list(filtered_metadata.values()),
                key=lambda x: (x.get("priority", 100), x.get("category", "general"), x["name"]),
            )

            # Build response with intent info
            return {
                "count": len(filtered_metadata),
                "intent_matched": True,
                "system_manifest": _build_system_manifest(
                    filtered_list, "Intent Filtered Workflow Manifest"
                ),
                "intent_analysis": {
                    "request": intent,
                    "categories": routing["categories"],
                    "reduction_percent": routing["reduction_percent"],
                    "token_savings": routing["estimated_token_savings"],
                    "handler_count": routing["handler_count"],
                    "total_handlers": routing["total_handlers"],
                },
                "categories": list(
                    set(m.get("category", "general") for m in filtered_metadata.values())
                ),
                "tools": filtered_list,
                "suggested_workflow": IntentRouter.get_suggested_workflow(intent),
            }
        except Exception as e:
            logger.error(f"Intent routing failed: {e}", exc_info=True)
            # Fall back to listing all tools

    # Standard listing (all tools)
    tools_list = []
    external_tools = []

    for name, meta in HANDLER_METADATA.items():
        try:
            if not isinstance(meta, dict) or "name" not in meta:
                logger.warning(f"Invalid metadata for tool '{name}'")  # type: ignore[unreachable]
                continue

            # Apply category filter
            if category_filter and meta.get("category") != category_filter:
                continue

            # Separate external integrations to list them last
            if name.startswith("integration_"):
                external_tools.append(meta)
            else:
                tools_list.append(meta)
        except Exception as e:
            logger.error(f"Error processing metadata for '{name}': {e}")

    # Sort core tools by priority (lower = more essential) then category then name
    sorted_core = sorted(
        tools_list,
        key=lambda x: (x.get("priority", 100), x.get("category", "general"), x["name"]),
    )

    # Sort external tools by priority then name (always at the end via priority 150+)
    sorted_external = sorted(external_tools, key=lambda x: (x.get("priority", 150), x["name"]))

    # Combine: core tools first, then external integrations
    final_list = sorted_core + sorted_external

    # Add tier label prefix to each tool description dynamically
    def _tier_label(priority: int) -> str:
        if priority <= 9:
            return "⭐ ESSENTIAL"
        if priority <= 49:
            return "CORE"
        if priority <= 149:
            return "STANDARD"
        return "OPTIONAL"

    labeled_list = []
    for tool in final_list:
        p = tool.get("priority", 100)
        labeled = dict(tool)
        labeled["tier"] = _tier_label(p)
        labeled_list.append(labeled)

    essential_tools = [t for t in labeled_list if t.get("tier") == "⭐ ESSENTIAL"]

    return {
        "count": len(labeled_list),
        "intent_matched": False,
        "categories": list(set(m.get("category", "general") for m in HANDLER_METADATA.values())),
        "tools": labeled_list,
        "external_integrations": {
            "count": len(sorted_external),
            "names": [t["name"] for t in sorted_external],
            "positions": f"{len(sorted_core) + 1}-{len(labeled_list)} (final 4 positions)",
        },
        "system_manifest": _build_system_manifest(final_list),
        "note": "Use 'intent' parameter for filtered results (e.g., intent='I want to animate a character')",
        "agent_onboarding": {
            "how_to_use_this_mcp": (
                "This MCP controls Blender 5.0+ via bpy API. Tools are ordered by priority: "
                "ESSENTIAL (1-9) first, then CORE, STANDARD, OPTIONAL. "
                "Start with ESSENTIAL tools to orient yourself."
            ),
            "essential_5step_workflow": {
                "step_1": "manage_agent_context GET_PRIMER — full quick-start guide with examples",
                "step_2": "get_scene_graph GET_OBJECTS_FLAT — what objects exist + world positions",
                "step_3": "get_viewport_screenshot_base64 — verify current visual state",
                "step_4": "execute_blender_code — create/modify objects via bpy Python",
                "step_5": "get_viewport_screenshot_base64 — confirm result visually",
            },
            "critical_warnings": [
                "obj.location is LOCAL (parent-relative). Use world_location from GET_OBJECTS_FLAT for absolute position.",
                "Objects with animation_data have transforms reset each frame. Call obj.animation_data_clear() before setting transforms.",
                "bpy.ops.* requires correct context (area type). Prefer bpy.data API inside execute_blender_code.",
                "Origin ≠ geometry center causes wrong rotation pivot. Check origin_offset_warning in GET_OBJECTS_FLAT.",
            ],
            "essential_tools": [t["name"] for t in essential_tools],
            "discovery_tip": (
                "Call manage_agent_context with action=GET_PRIMER for a comprehensive workflow guide. "
                "Call list_all_tools with intent='...' to filter tools by task."
            ),
        },
    }


@register_handler(
    "validate_tool",
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["validate_tool"],
                "default": "validate_tool",
            },
            "tool": {"type": "string", "description": "Tool name to validate"},
            "params": {"type": "object", "description": "Parameters to validate"},
        },
        "required": ["action", "tool"],
    },
)
def validate_tool(**params: Any) -> Dict[str, Any]:
    """
    Validate tool parameters without executing.

    Args:
        tool: Tool name to validate
        params: Parameters to validate

    Returns:
        Validation result with errors if any
    """
    tool_name = params.get("tool")
    tool_params = params.get("params", {})

    if not tool_name:
        return {"valid": False, "error": "Missing 'tool' parameter"}

    if tool_name not in HANDLER_REGISTRY:
        return {"valid": False, "error": f"Unknown tool: {tool_name}"}

    metadata = cast(HandlerMetadata, HANDLER_METADATA.get(tool_name, {}))
    actions = metadata.get("actions", [])
    schema = metadata.get("schema", {})

    errors = []

    # Validate action
    action = tool_params.get("action")
    if actions and action not in actions:
        errors.append(f"Invalid action '{action}'. Valid: {actions}")

    # Validate schema
    if schema:
        result = validate_params_schema(tool_params, schema)
        if not result["valid"]:
            errors.extend(result["errors"])

    if errors:
        return {"valid": False, "errors": errors}

    return {"valid": True, "tool": tool_name, "action": action}


def dispatch_command(
    command: Dict[str, Any], ctx: Optional[Any] = None, use_thread_safety: bool = True
) -> Dict[str, Any]:
    """
    Dispatch a command to the appropriate handler with validation and thread safety.

    V1.0.0: 280+ errors standardized, SmartModeManager, Blender 5.0+ compatibility.

    Args:
        command: Dict with 'tool' and 'params' keys
        ctx: Optional context object
        use_thread_safety: Whether to route execution to main thread

    Returns:
        Handler result or error dict
    """
    tool_name = command.get("tool")
    params = command.get("params", {})
    action = str(params.get("action", "unknown"))

    # Set up logging context
    request_id = set_request_context(
        request_id=command.get("request_id"), tool=tool_name, action=action
    )

    start_time = time.time()

    logger.debug(
        f"Dispatching command: {tool_name}.{action}",
        extra={"tool": tool_name, "action": action, "params": params, "request_id": request_id},
    )

    # Validate tool name
    if not tool_name:
        error_result: Dict[str, Any] = {
            "error": "Command must contain a 'tool' key",
            "code": "MISSING_TOOL",
        }
        _log_execution(tool_name, action, params, error_result, start_time, None)
        return error_result

    # Security Check
    if not SecurityManager.validate_action(tool_name, action):
        error_result = {
            "error": f"Security Violation: '{tool_name}' is blocked in Safe Mode.",
            "code": "SECURITY_VIOLATION",
            "is_security_violation": True,
        }
        _log_execution(tool_name, action, params, error_result, start_time, None)
        return error_result

    # Check tool exists
    if tool_name not in HANDLER_REGISTRY:
        error_result = {"error": f"Unknown command: {tool_name}", "code": "UNKNOWN_TOOL"}
        _log_execution(tool_name, action, params, error_result, start_time, None)
        return error_result

    handler_func: HandlerProtocol = HANDLER_REGISTRY[tool_name]
    metadata = cast(HandlerMetadata, HANDLER_METADATA.get(tool_name, {}))
    actions = metadata.get("actions", [])
    schema = metadata.get("schema", {})

    # Validate action if specified
    if actions and action not in actions:
        error_result = {
            "error": f"Invalid action '{action}' for tool '{tool_name}'",
            "code": "INVALID_ACTION",
            "valid_actions": actions,
        }
        _log_execution(tool_name, action, params, error_result, start_time, None)
        return error_result

    # Validate schema if provided
    if schema:
        validation = validate_params_schema(params, schema)
        if not validation["valid"]:
            error_result = {
                "error": "Parameter validation failed",
                "code": "VALIDATION_ERROR",
                "details": validation["errors"],
            }
            _log_execution(tool_name, action, params, error_result, start_time, None)
            return error_result
        # Merge sanitized parameters
        params.update(validation["sanitized"])

    # Execute handler with thread safety and logging
    try:

        def execute_handler() -> Any:
            """Inner function to execute the handler."""
            call_params = params.copy()
            action_param = call_params.pop("action", None)

            # Check if handler expects context
            sig = inspect.signature(handler_func)
            if "ctx" in sig.parameters:
                return handler_func(action=action_param, ctx=ctx, **call_params)
            else:
                return handler_func(action=action_param, **call_params)

        # Route to main thread if needed
        if use_thread_safety and not is_main_thread():
            try:
                # Use caller-supplied timeout_seconds (e.g. for RENDER_FRAME: 300s).
                # Default 300s matches RenderTimeout.FRAME_DEFAULT so renders never time
                # out at the dispatcher level before the handler's own timeout fires.
                _dispatch_timeout = float(params.get("timeout_seconds", 300.0))
                result = execute_on_main_thread(execute_handler, timeout=_dispatch_timeout)
            except TimeoutError as e:
                error_result = {
                    "error": f"Execution timeout: {str(e)}",
                    "code": "TIMEOUT_ERROR",
                    "suggestion": "Try with simpler parameters or split into smaller operations",
                }
                _log_execution(tool_name, action, params, error_result, start_time, e)
                return error_result
            except Exception as e:
                error_result = {"error": f"Execution failed: {str(e)}", "code": "EXECUTION_ERROR"}
                _log_execution(tool_name, action, params, error_result, start_time, e)
                return error_result
        else:
            result = execute_handler()

        # Normalize result
        if result is None:
            result = {"success": True}
        elif isinstance(result, dict):
            if "success" not in result and "error" not in result:
                result["success"] = True
        else:
            result = {"result": result, "success": True}

        # Add metadata
        result["_meta"] = {
            "request_id": request_id,
            "tool": tool_name,
            "action": action,
        }

        _log_execution(tool_name, action, params, result, start_time, None)
        return cast(Dict[str, Any], result)

    except Exception as e:
        # Enhanced error reporting
        tb = traceback.format_exc()
        error_result = {
            "error": str(e),
            "code": "EXECUTION_ERROR",
            "type": type(e).__name__,
            "tool": tool_name,
            "action": action,
            "_meta": {
                "request_id": request_id,
            },
        }

        # Include traceback in debug mode
        if ctx and getattr(ctx, "debug", False):
            error_result["traceback"] = tb

        _log_execution(tool_name, action, params, error_result, start_time, e)
        return error_result

    finally:
        clear_request_context()


def _log_execution(
    tool: Optional[str],
    action: str,
    params: Dict[str, Any],
    result: Dict[str, Any],
    start_time: float,
    error: Optional[Exception],
) -> None:
    """Log execution with timing."""
    duration_ms = (time.time() - start_time) * 1000

    # Sanitize params (remove sensitive data)
    safe_params = {
        k: v for k, v in params.items() if k not in ["password", "api_key", "secret", "token"]
    }

    logger.log_tool_execution(
        tool=tool or "unknown_tool",
        action=action,
        params=safe_params,
        result=result.get("success", False),
        duration_ms=duration_ms,
        error=error,
    )


def load_handlers() -> None:
    """
    Dynamically load all handler modules in the 'handlers' sub-package.

    V1.0.0: External integration handlers (integration_*) are ALWAYS loaded last
    to ensure they occupy the final 4 positions (61-64 in current release).
    """
    package_path = handlers.__path__

    global LOAD_ERRORS
    loaded_count = 0

    def rollback_partial_registration(previous_keys: set[str], module_name: str) -> None:
        """Remove handlers partially registered by a module that failed to import."""
        new_keys = [key for key in HANDLER_REGISTRY.keys() if key not in previous_keys]
        for key in new_keys:
            HANDLER_REGISTRY.pop(key, None)
            HANDLER_METADATA.pop(key, None)
        partial_module_name = f"{handlers.__name__}.{module_name}"
        if partial_module_name in sys.modules:
            del sys.modules[partial_module_name]

    # External integration handlers that MUST be loaded last (positions 61-64)
    EXTERNAL_INTEGRATIONS = [
        "hunyuan_handler",
        "hyper3d_handler",
        "polyhaven_handler",
        "sketchfab_handler",
    ]

    # First pass: Load all handlers EXCEPT external integrations
    for _, module_name, _ in pkgutil.iter_modules(package_path):
        if module_name == "base_handler" or module_name.startswith("__"):
            continue
        # Skip external integrations - they will be loaded last
        if module_name in EXTERNAL_INTEGRATIONS:
            continue
        previous_keys = set(HANDLER_REGISTRY.keys())
        try:
            importlib.import_module(f".{module_name}", package=handlers.__name__)
            logger.debug(f"Loaded handler module: {module_name}")
            loaded_count += 1
        except ImportError as e:
            rollback_partial_registration(previous_keys, module_name)
            err_msg = f"ImportError in {module_name}: {str(e)}"
            logger.error(err_msg)
            LOAD_ERRORS.append(err_msg)
        except Exception as e:
            rollback_partial_registration(previous_keys, module_name)
            err_msg = f"Error loading {module_name}: {str(e)}"
            logger.error(err_msg, exc_info=True)
            LOAD_ERRORS.append(err_msg)

    # Second pass: Load external integrations LAST (always final 4 positions)
    for module_name in EXTERNAL_INTEGRATIONS:
        previous_keys = set(HANDLER_REGISTRY.keys())
        try:
            importlib.import_module(f".{module_name}", package=handlers.__name__)
            logger.debug(f"Loaded external integration module: {module_name}")
            loaded_count += 1
        except ImportError as e:
            rollback_partial_registration(previous_keys, module_name)
            err_msg = f"ImportError in {module_name}: {str(e)}"
            logger.error(err_msg)
            LOAD_ERRORS.append(err_msg)
        except Exception as e:
            rollback_partial_registration(previous_keys, module_name)
            err_msg = f"Error loading {module_name}: {str(e)}"
            logger.error(err_msg, exc_info=True)
            LOAD_ERRORS.append(err_msg)

    logger.info(f"Handler loading complete. Success: {loaded_count}, Failed: {len(LOAD_ERRORS)}")


def reload_handler(module_name: str) -> Dict[str, Any]:
    """
    Reload a specific handler module (for development).

    Args:
        module_name: Name of module to reload (e.g., "manage_physics")

    Returns:
        Success status
    """
    import sys

    try:
        full_name = f"{handlers.__name__}.{module_name}"
        if full_name in sys.modules:
            importlib.reload(sys.modules[full_name])
            return {"success": True, "module": module_name}
        else:
            return {"error": f"Module {module_name} not loaded"}
    except Exception as e:
        logger.error(f"Failed to reload {module_name}: {e}", exc_info=True)
        return {"error": str(e), "module": module_name}
