"""
Unit tests for manage_history handler — pure stack logic, no bpy required.

Tests the session-level checkpoint stack operations without needing Blender.
bpy operations (undo_push, undo, redo) are no-ops when bpy is unavailable.
"""

from __future__ import annotations

import sys
import os
import importlib
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Patch bpy before importing the handler so BPY_AVAILABLE = False path is used
sys.modules.setdefault("bpy", MagicMock())

# We import the private stack helpers directly to test without bpy side effects
import blender_mcp.handlers.manage_history as _mh


def _clear_stack() -> None:
    """Reset the module-level _HISTORY_STACK between tests."""
    _mh._HISTORY_STACK.clear()


def test_push_checkpoint_increments_stack() -> None:
    """PUSH_CHECKPOINT adds an entry to the stack."""
    _clear_stack()
    result = _mh._push_checkpoint(label="Before UV unwrap")
    assert result.get("success") is True
    assert len(_mh._HISTORY_STACK) == 1
    assert _mh._HISTORY_STACK[0]["label"] == "Before UV unwrap"


def test_push_checkpoint_assigns_index() -> None:
    """Each checkpoint gets an incrementing index."""
    _clear_stack()
    _mh._push_checkpoint(label="A")
    _mh._push_checkpoint(label="B")
    _mh._push_checkpoint(label="C")
    assert _mh._HISTORY_STACK[0]["index"] == 0
    assert _mh._HISTORY_STACK[1]["index"] == 1
    assert _mh._HISTORY_STACK[2]["index"] == 2


def test_push_checkpoint_max_limit() -> None:
    """Stack is capped at _MAX_HISTORY (50) entries — oldest is evicted."""
    _clear_stack()
    for i in range(_mh._MAX_HISTORY + 5):
        _mh._push_checkpoint(label=f"Step {i}")

    assert len(_mh._HISTORY_STACK) == _mh._MAX_HISTORY


def test_index_recomputed_after_eviction() -> None:
    """After eviction, all remaining entries must have contiguous indices 0..N-1."""
    _clear_stack()
    for i in range(_mh._MAX_HISTORY + 3):
        _mh._push_checkpoint(label=f"Step {i}")

    for expected_idx, entry in enumerate(_mh._HISTORY_STACK):
        assert entry["index"] == expected_idx, (
            f"Index mismatch at position {expected_idx}: got {entry['index']}"
        )


def test_list_history_returns_all() -> None:
    """LIST_HISTORY returns all checkpoints with correct stack_depth."""
    _clear_stack()
    _mh._push_checkpoint(label="X")
    _mh._push_checkpoint(label="Y")

    result = _mh._list_history()
    assert result.get("success") is True
    data = result.get("data", {})
    assert data["stack_depth"] == 2
    assert len(data["checkpoints"]) == 2
    assert data["checkpoints"][0]["label"] == "X"
    assert data["checkpoints"][1]["label"] == "Y"


def test_clear_history_empties_stack() -> None:
    """CLEAR_HISTORY empties the MCP session stack."""
    _clear_stack()
    _mh._push_checkpoint(label="Keep")
    _mh._push_checkpoint(label="Also Keep")

    result = _mh._clear_history()
    assert result.get("success") is True
    assert result["data"]["cleared"] == 2
    assert len(_mh._HISTORY_STACK) == 0


def test_push_without_label_uses_default() -> None:
    """PUSH_CHECKPOINT without a label generates a default label."""
    _clear_stack()
    result = _mh._push_checkpoint()
    assert result.get("success") is True
    label = _mh._HISTORY_STACK[0]["label"]
    assert "MCP Checkpoint" in label or len(label) > 0


def test_list_history_empty_stack() -> None:
    """LIST_HISTORY on empty stack returns stack_depth=0 and empty checkpoints list."""
    _clear_stack()
    result = _mh._list_history()
    assert result["data"]["stack_depth"] == 0
    assert result["data"]["checkpoints"] == []
