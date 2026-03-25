"""
Legacy context compatibility layer.

Provides a stable `safe_context` API for older handlers while delegating
context overrides to ContextManagerV3.
"""

from contextlib import contextmanager
from typing import Iterator

from .context_manager_v3 import ContextManagerV3

try:
    import bpy

    _ = bpy  # Silence F401

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False


@contextmanager
def safe_context(area_type: str = "VIEW_3D") -> Iterator[None]:
    """
    Backward-compatible safe context wrapper.

    Falls back to a no-op context when bpy is unavailable.
    """
    if not BPY_AVAILABLE:
        yield
        return

    with ContextManagerV3.temp_override(area_type=area_type):
        yield


__all__ = ["safe_context"]
