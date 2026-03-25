"""
Object Lifecycle Manager for Blender MCP 1.0.0

Provides safe object reference management to prevent:
- "StructRNA of type Object has been removed" errors
- Accessing deleted objects
- Stale references

Uses WeakKeyDictionary for automatic garbage collection of dead references.
"""

import weakref
from typing import Dict, Optional, Any, Callable, Union, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

try:
    import bpy

    HAS_BPY = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]


@dataclass
class ObjectMetadata:
    """Metadata for tracked objects."""

    name: str
    type: str
    created_at: datetime = field(default_factory=datetime.now)
    ttl: Optional[int] = None  # Time to live in seconds
    tags: Set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """Check if the metadata has expired."""
        if self.ttl is None:
            return False
        expiry = self.created_at + timedelta(seconds=self.ttl)
        return datetime.now() > expiry


class ObjectLifecycleManager:
    """
    Central registry for object lifecycle tracking.

    Uses WeakKeyDictionary to automatically remove entries when objects
    are garbage collected (deleted from Blender).

    Usage:
        manager = ObjectLifecycleManager()
        session_id = manager.track_object(obj, ttl=3600)

        if manager.is_valid(obj):
            # Safe to use obj
            pass
    """

    _instance = None
    _initialized = False

    def __new__(cls) -> "ObjectLifecycleManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if ObjectLifecycleManager._initialized:
            return

        self._cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self._name_map: Dict[str, Any] = {}  # name -> weakref
        self._session_counter = 0
        ObjectLifecycleManager._initialized = True

    def track_object(
        self, obj: Any, ttl: Optional[int] = None, tags: Optional[Set[str]] = None
    ) -> str:
        """
        Register object for lifecycle tracking.

        Args:
            obj: Blender object to track
            ttl: Time to live in seconds (None = no expiry)
            tags: Optional set of tags for categorization

        Returns:
            Session ID for tracking
        """
        if not HAS_BPY or not obj:
            return ""

        self._session_counter += 1
        session_id = f"obj_{self._session_counter}_{id(obj)}"

        # Store metadata
        metadata = ObjectMetadata(
            name=getattr(obj, "name", str(obj)),
            type=getattr(obj, "type", "UNKNOWN"),
            ttl=ttl,
            tags=tags or set(),
        )

        self._cache[obj] = metadata
        self._name_map[metadata.name] = weakref.ref(obj)

        return session_id

    def is_valid(self, obj_or_id: Union[Any, str]) -> bool:
        """
        Check if object reference is still valid.

        Args:
            obj_or_id: Object or session ID to check

        Returns:
            True if object exists and is valid
        """
        if not HAS_BPY:
            return False

        # Check if it's a string (session ID or name)
        if isinstance(obj_or_id, str):
            # Try to find by name
            if obj_or_id in bpy.data.objects:
                obj = bpy.data.objects[obj_or_id]
                return obj in self._cache or self._validate_object(obj)
            return False

        # Check if object is in cache
        if obj_or_id in self._cache:
            metadata = self._cache[obj_or_id]
            if metadata.is_expired():
                return False
            return self._validate_object(obj_or_id)

        # Object not tracked, validate directly
        return self._validate_object(obj_or_id)

    def _validate_object(self, obj: Any) -> bool:
        """Validate that object still exists in Blender."""
        if not HAS_BPY or not obj:
            return False

        try:
            # Try to access name - will raise exception if deleted
            name = obj.name
            # Check if still in bpy.data.objects
            return name in bpy.data.objects
        except (ReferenceError, AttributeError):
            return False

    def get_safe(self, obj_id: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Get object only if valid, otherwise return default.

        Args:
            obj_id: Object name or session ID
            default: Default value if object not found or invalid

        Returns:
            Object if valid, otherwise default
        """
        if not HAS_BPY:
            return default

        # Try to get by name
        if obj_id in bpy.data.objects:
            obj = bpy.data.objects[obj_id]
            if self.is_valid(obj):
                return obj

        # Try to get from name map
        if obj_id in self._name_map:
            obj_ref = self._name_map[obj_id]
            obj = obj_ref()
            if obj is not None and self.is_valid(obj):
                return obj

        return default

    def batch_validate(self, obj_ids: List[str]) -> Dict[str, bool]:
        """
        Validate multiple objects efficiently.

        Args:
            obj_ids: List of object names or session IDs

        Returns:
            Dictionary mapping IDs to validity
        """
        return {obj_id: self.is_valid(obj_id) for obj_id in obj_ids}

    def cleanup_stale_refs(self) -> int:
        """
        Clean up expired metadata entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        expired_names = []

        # Find expired entries
        for obj, metadata in list(self._cache.items()):
            if metadata.is_expired() or not self._validate_object(obj):
                expired_names.append(metadata.name)
                removed += 1

        # Clean up name map
        for name in expired_names:
            if name in self._name_map:
                del self._name_map[name]

        return removed

    def get_tracked_count(self) -> int:
        """Get number of tracked objects."""
        return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tracked objects."""
        types: Dict[str, int] = {}
        expired = 0

        for obj, metadata in self._cache.items():
            types[metadata.type] = types.get(metadata.type, 0) + 1
            if metadata.is_expired():
                expired += 1

        return {"total_tracked": len(self._cache), "expired": expired, "by_type": types}


# Global instance
_lifecycle_manager = None


def get_lifecycle_manager() -> ObjectLifecycleManager:
    """Get the global lifecycle manager instance."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = ObjectLifecycleManager()
    return _lifecycle_manager


def track_object(obj: Any, ttl: Optional[int] = None) -> str:
    """Convenience function to track an object."""
    return get_lifecycle_manager().track_object(obj, ttl)


def is_valid(obj_or_id: Union[Any, str]) -> bool:
    """Convenience function to check if object is valid."""
    return get_lifecycle_manager().is_valid(obj_or_id)


def get_safe(obj_id: str, default: Any = None) -> Optional[Any]:
    """Convenience function to get object safely."""
    return get_lifecycle_manager().get_safe(obj_id, default)


def with_object_exists(func: Callable) -> Callable:
    """
    Decorator that checks if first argument (object) exists before calling function.

    Usage:
        @with_object_exists
        def process_object(obj, **params):
            # obj is guaranteed to exist
            pass
    """

    def wrapper(obj: Any, *args: Any, **kwargs: Any) -> Any:
        if not is_valid(obj):
            return {"error": "Object no longer exists", "code": "OBJECT_DELETED"}
        return func(obj, *args, **kwargs)

    return wrapper


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ObjectLifecycleManager",
    "ObjectMetadata",
    "get_lifecycle_manager",
    "track_object",
    "is_valid",
    "get_safe",
    "with_object_exists",
]
