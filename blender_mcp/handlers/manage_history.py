"""
Manage History — Undo/Redo and Checkpoint Handler for Blender MCP

Session-level history tracking with Blender undo stack integration.
The _HISTORY_STACK lives for the duration of the Blender session (module-level).
"""

from __future__ import annotations

import time
from typing import Any

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None

from ..dispatcher import register_handler
from ..core.response_builder import ResponseBuilder
from ..core.thread_safety import ensure_main_thread
from ..core.logging_config import get_logger

logger = get_logger()

# Session-level history stack (survives within a Blender session, reset on module reload)
_HISTORY_STACK: list[dict[str, Any]] = []
_MAX_HISTORY = 50  # cap to avoid memory bloat


@register_handler(
    "manage_history",
    priority=55,
    schema={
        "type": "object",
        "title": "History Manager (Checkpoint)",
        "description": (
            "STANDARD — Session-level checkpoint management.\n"
            "Tracks MCP operation checkpoints within a Blender session (module-level stack).\n\n"
            "ACTIONS:\n"
            "  PUSH_CHECKPOINT — Save a named checkpoint (bpy.ops.ed.undo_push + stack entry).\n"
            "  LIST_HISTORY — List all MCP session checkpoints.\n"
            "  CLEAR_HISTORY — Clear MCP session stack (does NOT affect Blender undo stack).\n\n"
            "NOTE: Blender undo stack has no introspection API. MCP tracks its own checkpoint labels.\n"
            "NOTE: Use Blender UI Ctrl+Z / Ctrl+Shift+Z for undo/redo (not available via MCP)."
        ),
        "properties": {
            "action": {
                "type": "string",
                "enum": ["PUSH_CHECKPOINT", "LIST_HISTORY", "CLEAR_HISTORY"],
                "description": (
                    "Operation to perform.\n"
                    "  PUSH_CHECKPOINT — Save a named checkpoint.\n"
                    "  LIST_HISTORY — List MCP session checkpoints.\n"
                    "  CLEAR_HISTORY — Clear MCP session stack."
                ),
            },
            "label": {
                "type": "string",
                "description": "Checkpoint label for PUSH_CHECKPOINT (e.g. 'Before UV unwrap').",
            },
        },
        "required": ["action"],
    },
    actions=["PUSH_CHECKPOINT", "LIST_HISTORY", "CLEAR_HISTORY"],
    category="scene",
)
@ensure_main_thread
def manage_history(action: str | None = None, **params: Any) -> dict[str, Any]:
    """Session-level checkpoint manager (PUSH_CHECKPOINT, LIST_HISTORY, CLEAR_HISTORY)."""
    if not action:
        return ResponseBuilder.error(
            handler="manage_history",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == "PUSH_CHECKPOINT":
        return _push_checkpoint(**params)
    elif action == "LIST_HISTORY":
        return _list_history()
    elif action == "CLEAR_HISTORY":
        return _clear_history()
    else:
        return ResponseBuilder.error(
            handler="manage_history",
            action=action,
            error_code="UNKNOWN_ACTION",
            message=f"Unknown action: '{action}'. Valid: PUSH_CHECKPOINT, LIST_HISTORY, CLEAR_HISTORY",
        )


def _push_checkpoint(**params: Any) -> dict[str, Any]:
    """Push a named checkpoint to MCP history and Blender undo stack."""
    label = str(params.get("label", f"MCP Checkpoint {len(_HISTORY_STACK) + 1}"))

    # Push to Blender undo stack
    blender_push_ok = False
    try:
        if bpy is not None:
            bpy.ops.ed.undo_push(message=label)
            blender_push_ok = True
    except Exception as e:
        logger.warning(f"manage_history PUSH_CHECKPOINT: bpy.ops.ed.undo_push failed: {e}")

    # Evict oldest entry if at capacity before computing new index
    if len(_HISTORY_STACK) >= _MAX_HISTORY:
        _HISTORY_STACK.pop(0)
        # Re-index after eviction (rename loop var to avoid mypy except-var collision)
        for idx, entry_ref in enumerate(_HISTORY_STACK):
            entry_ref["index"] = idx

    # Push to MCP session stack — index computed after potential eviction
    entry = {
        "index": len(_HISTORY_STACK),
        "label": label,
        "timestamp": time.time(),
        "blender_undo_registered": blender_push_ok,
    }
    _HISTORY_STACK.append(entry)

    return ResponseBuilder.success(
        handler="manage_history",
        action="PUSH_CHECKPOINT",
        data={
            "checkpoint": entry,
            "stack_depth": len(_HISTORY_STACK),
            "blender_undo_registered": blender_push_ok,
        },
    )


def _list_history() -> dict[str, Any]:
    """List all MCP session checkpoints."""
    return ResponseBuilder.success(
        handler="manage_history",
        action="LIST_HISTORY",
        data={
            "stack_depth": len(_HISTORY_STACK),
            "max_history": _MAX_HISTORY,
            "checkpoints": list(_HISTORY_STACK),
            "note": (
                "This is the MCP session checkpoint list. "
                "Blender's full undo stack cannot be introspected via bpy API."
            ),
        },
    )


def _clear_history() -> dict[str, Any]:
    """Clear MCP session checkpoint stack (does NOT touch Blender's undo stack)."""
    count = len(_HISTORY_STACK)
    _HISTORY_STACK.clear()

    return ResponseBuilder.success(
        handler="manage_history",
        action="CLEAR_HISTORY",
        data={
            "cleared": count,
            "note": "MCP session stack cleared. Blender's own undo stack is NOT affected.",
        },
    )
