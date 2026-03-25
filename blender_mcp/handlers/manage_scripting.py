from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import bpy
    import mathutils
else:
    try:
        import bpy
        import mathutils

        BPY_AVAILABLE = True
    except ImportError:
        BPY_AVAILABLE = False
        bpy = None
        mathutils = None
from ..core.context import safe_context
from ..dispatcher import register_handler


from ..core.parameter_validator import validated_handler
from ..core.enums import ScriptingAction
from ..core.thread_safety import ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_scripting",
    actions=[a.value for a in ScriptingAction],
    category="general",
    schema={
        "type": "object",
        "title": "Scripting Manager",
        "description": "Execute Python scripts and manage Text blocks. Context-safe execution for safe_ops.",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(ScriptingAction, "Operation."),
            "code": {"type": "string", "description": "Raw Python code to execute."},
            "name": {"type": "string", "description": "Text block name."},
            "use_safe_context": {
                "type": "boolean",
                "default": True,
                "description": "Use safe context wrapper for bpy.ops calls",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in ScriptingAction])
def manage_scripting(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Scripting Tools with Context Safety.
    """
    if not action:
        return ResponseBuilder.error(
            handler="manage_scripting",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == ScriptingAction.EXECUTE_CODE.value:
        code = params.get("code")
        if not code:
            return ResponseBuilder.error(
                handler="manage_scripting",
                action="EXECUTE_CODE",
                error_code="MISSING_PARAMETER",
                message="No code provided",
            )

        try:
            # Enhanced globals with utility functions
            exec_globals = {
                "bpy": bpy,
                "__name__": "__main__",
            }

            # Add mathutils if available
            try:
                import mathutils

                exec_globals["mathutils"] = mathutils
                exec_globals["Vector"] = mathutils.Vector
                exec_globals["Matrix"] = mathutils.Matrix
            except:
                pass

            # Execute with context safety
            use_safe = params.get("use_safe_context", True)
            if use_safe:
                # Wrap execution in safe context for ops that need it
                with safe_context("VIEW_3D"):
                    exec(code, exec_globals)
            else:
                exec(code, exec_globals)

            return {"success": True, "message": "Code executed successfully"}
        except Exception as e:
            import traceback

            return ResponseBuilder.error(
                handler="manage_scripting",
                action="EXECUTE_CODE",
                error_code="EXECUTION_ERROR",
                message=f"Code execution failed: {str(e)}",
                details={"traceback": traceback.format_exc()},
            )

    elif action == ScriptingAction.CREATE_TEXT_BLOCK.value:
        name = params.get("name", "Script.py")
        code = params.get("code", "")

        txt = bpy.data.texts.new(name)
        txt.write(code)
        return {"success": True, "text_block": txt.name}

    elif action == ScriptingAction.EXECUTE_TEXT_BLOCK.value:
        name = params.get("name")
        if name not in bpy.data.texts:
            return ResponseBuilder.error(
                handler="manage_scripting",
                action="EXECUTE_TEXT_BLOCK",
                error_code="OBJECT_NOT_FOUND",
                message=f"Text block '{name}' not found",
            )

        try:
            with ContextManagerV3.temp_override(
                area_type="TEXT_EDITOR",
                edit_text=bpy.data.texts[name],
            ):
                safe_ops.text.run_script()
            return {"success": True, "message": f"Ran {name}"}
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_scripting",
                action="EXECUTE_TEXT_BLOCK",
                error_code="EXECUTION_ERROR",
                message=f"Text block execution failed: {str(e)}",
            )

    return ResponseBuilder.error(
        handler="manage_scripting",
        action=action,
        error_code="UNKNOWN_ACTION",
        message=f"Unknown action: {action}",
    )


# =============================================================================
# STANDALONE HANDLERS (Power Tools)
# =============================================================================

_BLOCKING_RENDER_PATTERNS = [
    (
        r"bpy\.ops\.render\.render\s*\(",
        (
            "BLOCKED: bpy.ops.render.render() freezes Blender's main thread and the MCP server cannot "
            "respond until rendering completes (which may take minutes). "
            "Use manage_rendering with action=RENDER_FRAME instead — it runs as an async subprocess. "
            "Example: manage_rendering(action='RENDER_FRAME', filepath='/tmp/render.png'). "
            "For RENDER_STILL (single frame), also use manage_rendering action=RENDER_FRAME."
        ),
    ),
]


@register_handler(
    "execute_blender_code",
    priority=1,
    schema={
        "type": "object",
        "title": "Execute Python Code",
        "description": (
            "TIER 1 PRIMARY TOOL — Full bpy Python API access. Use for all creation, modification, "
            "animation, and anything not covered by other tools.\n\n"
            "RETURNS: stdout (print() output), stderr, success/error. "
            "Always print() created object names so subsequent tools can reference them.\n\n"
            "CRITICAL — Use bpy.data API (context-independent, always works):\n"
            "  me = bpy.data.meshes.new('PropMesh')\n"
            "  obj = bpy.data.objects.new('Propeller_L', me)\n"
            "  obj.location = (1.2, 0.5, 2.0)\n"
            "  bpy.context.scene.collection.objects.link(obj)\n"
            "  print(f'Created: {obj.name} at {list(obj.location)}')\n\n"
            "AVOID bpy.ops.* — operators require correct context and often fail headlessly.\n\n"
            "BLOCKS (auto-rejected): bpy.ops.render.render() — freezes Blender main thread, MCP server stops responding.\n"
            "  Use manage_rendering action=RENDER_FRAME (async subprocess) instead.\n\n"
            "ANIMATION OVERRIDE WARNING: If an object has animation_data, setting transforms in Python "
            "will be overridden on the next frame. Call obj.animation_data_clear() first if needed.\n\n"
            "ORIGIN vs GEOMETRY: obj.location = object origin, NOT geometry center. "
            "If origin ≠ geometry center, rotations will orbit the wrong point. "
            "Check get_object_info geometry_center_world vs world_location to detect this."
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": ["execute_blender_code"],
                "default": "execute_blender_code",
                "description": "Action to perform",
            },
            "code": {
                "type": "string",
                "description": "The Python code snippet to execute.",
            },
        },
        "required": ["action", "code"],
    },
)
def execute_blender_code(**params):  # type: ignore[no-untyped-def]
    """
    Execute arbitrary Python code in Blender.
    """
    import contextlib
    import io
    import re
    import traceback

    code = params.get("code")
    if not code:
        return ResponseBuilder.error(
            handler="execute_blender_code",
            action="EXECUTE_CODE",
            error_code="MISSING_PARAMETER",
            message="No code provided",
        )

    # Pre-execution blocking pattern scan
    for pattern, message in _BLOCKING_RENDER_PATTERNS:
        if re.search(pattern, code):
            return ResponseBuilder.error(
                handler="execute_blender_code",
                action="EXECUTE_CODE",
                error_code="BLOCKED_PATTERN",
                message=message,
            )

    # Simple output capture redirection
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    try:
        with (
            contextlib.redirect_stdout(stdout_buffer),
            contextlib.redirect_stderr(stderr_buffer),
        ):
            # Pass valuable context
            exec_globals = {
                "bpy": bpy,
                "__builtins__": __builtins__,
            }
            try:
                import types

                import mathutils

                exec_globals["mathutils"] = mathutils
                exec_globals["Vector"] = mathutils.Vector  # type: ignore[assignment]
                exec_globals["Matrix"] = mathutils.Matrix  # type: ignore[assignment]
                exec_globals["Quaternion"] = mathutils.Quaternion  # type: ignore[assignment]
                exec_globals["Color"] = mathutils.Color  # type: ignore[assignment]
                exec_globals["types"] = types
            except Exception as e:
                logger.warning(f"[MCP] Warning: Could not import mathutils/types: {e}")

            exec(code, exec_globals)

        return {
            "success": True,
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
        }
    except Exception as e:
        return ResponseBuilder.error(
            handler="execute_blender_code",
            action="EXECUTE_CODE",
            error_code="EXECUTION_ERROR",
            message=f"Code execution failed: {str(e)}",
            details={
                "traceback": traceback.format_exc(),
                "stdout": stdout_buffer.getvalue(),
            },
        )


@register_handler(
    "execute_code",
    priority=200,
    schema={
        "type": "object",
        "title": "Execute Code (Legacy Alias)",
        "description": "[DEPRECATED — use execute_blender_code instead] Legacy alias with identical functionality. Prefer execute_blender_code for all new code.",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["execute_code"],
                "default": "execute_code",
                "description": "Legacy alias action",
            },
            "code": {"type": "string"},
        },
        "required": ["action", "code"],
    },
)
def execute_code(**params):  # type: ignore[no-untyped-def]
    """
    Alias wrapper for Python code execution within Blender context.
    """
    return execute_blender_code(**params)
