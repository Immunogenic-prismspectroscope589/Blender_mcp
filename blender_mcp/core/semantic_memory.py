"""
V1.0.0: Semantic Scene Memory
==============================
Map natural language tags to scene objects.

Instead of requiring exact object names:
    "Cube.001" → rigid, error-prone

Use semantic tags:
    "hero_character" → last active character
    "main_camera" → scene camera
    "ground_plane" → floor object
    "selected_objects" → current selection

This enables LLMs to work with intent rather than implementation details.
"""

import bpy
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


def _is_active_camera(obj: Any) -> bool:
    """Safe active camera detection for headless/partial context."""
    scene = getattr(bpy.context, "scene", None)
    return scene is not None and obj == getattr(scene, "camera", None)


@dataclass
class SemanticTag:
    """A semantic tag attached to an object."""

    tag: str
    confidence: float = 1.0  # 0-1, how sure are we?
    source: str = "inferred"  # "user", "inferred", "ai", "pattern"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectMemory:
    """Memory entry for a scene object."""

    name: str
    object_type: str
    tags: List[SemanticTag] = field(default_factory=list)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0

    def add_tag(
        self, tag: str, confidence: float = 1.0, source: str = "inferred", **metadata: Any
    ) -> None:
        """Add a semantic tag to this object."""
        # Remove existing tag of same name
        self.tags = [t for t in self.tags if t.tag != tag]
        self.tags.append(SemanticTag(tag, confidence, source, metadata=metadata))

    def has_tag(self, tag: str) -> bool:
        """Check if object has a specific tag."""
        return any(t.tag == tag for t in self.tags)

    def get_confidence(self, tag: str) -> float:
        """Get confidence for a specific tag."""
        for t in self.tags:
            if t.tag == tag:
                return t.confidence
        return 0.0


class SemanticSceneMemory:
    """
    Central registry for semantic object tags in a Blender scene.

    Provides:
    - Tag-based object resolution ("hero_character" → Object)
    - Pattern-based auto-tagging (detect cameras, lights, etc.)
    - Access tracking (most-used objects bubble up)
    - Context persistence across operations
    """

    # Well-known semantic tags with detection rules
    KNOWN_TAGS: Dict[str, Dict[str, Any]] = {
        "main_camera": {
            "description": "Primary scene camera for rendering",
            "detection": lambda obj: (
                obj.type == "CAMERA" and obj.name.lower() in ["camera", "main_camera", "cam"]
            ),
        },
        "active_camera": {
            "description": "Currently active camera",
            "detection": lambda obj: _is_active_camera(obj),
        },
        "ground_plane": {
            "description": "Floor/ground surface",
            "detection": lambda obj: (
                obj.type == "MESH"
                and any(x in obj.name.lower() for x in ["ground", "floor", "plane", "zemin", "yer"])
            ),
        },
        "hero_character": {
            "description": "Main character/rig in the scene",
            "detection": lambda obj: (
                obj.type == "ARMATURE"
                or any(x in obj.name.lower() for x in ["char", "hero", "player", "rig", "karakter"])
            ),
        },
        "sun_light": {
            "description": "Primary directional light",
            "detection": lambda obj: obj.type == "LIGHT" and obj.data.type == "SUN",
        },
        "key_light": {
            "description": "Main illuminating light",
            "detection": lambda obj: (
                obj.type == "LIGHT"
                and any(x in obj.name.lower() for x in ["key", "main", "primary", "sun"])
            ),
        },
        "fill_light": {
            "description": "Secondary fill illumination",
            "detection": lambda obj: obj.type == "LIGHT" and "fill" in obj.name.lower(),
        },
        "rim_light": {
            "description": "Back/rim lighting",
            "detection": lambda obj: (
                obj.type == "LIGHT" and any(x in obj.name.lower() for x in ["rim", "back", "hair"])
            ),
        },
        "selected_objects": {
            "description": "Currently selected objects",
            "detection": lambda obj: obj.select_get(),
        },
        "active_object": {
            "description": "Object currently in context",
            "detection": lambda obj: obj == bpy.context.active_object,
        },
        "last_created": {
            "description": "Most recently created object",
            "detection": None,  # Set dynamically
        },
        "last_modified": {
            "description": "Most recently modified object",
            "detection": None,  # Set dynamically
        },
        "mesh_objects": {
            "description": "All mesh geometry objects",
            "detection": lambda obj: obj.type == "MESH",
        },
        "light_objects": {
            "description": "All light sources",
            "detection": lambda obj: obj.type == "LIGHT",
        },
        "camera_objects": {
            "description": "All cameras",
            "detection": lambda obj: obj.type == "CAMERA",
        },
        "armature_objects": {
            "description": "All rigs/armatures",
            "detection": lambda obj: obj.type == "ARMATURE",
        },
        "curve_objects": {
            "description": "All curve objects",
            "detection": lambda obj: obj.type == "CURVE",
        },
        "empty_objects": {
            "description": "All empties/nulls",
            "detection": lambda obj: obj.type == "EMPTY",
        },
    }

    def __init__(self) -> None:
        self._memory: Dict[str, ObjectMemory] = {}
        self._tag_index: Dict[str, List[str]] = {}  # tag -> list of object names
        self._last_created: Optional[str] = None
        self._last_modified: Optional[str] = None
        self._initialized = False

    def initialize(self, force: bool = False) -> None:
        """Scan scene and build semantic memory."""
        if self._initialized and not force:
            return

        self._memory.clear()
        self._tag_index.clear()

        # Scan all objects
        for obj in bpy.data.objects:
            self._scan_object(obj)

        self._initialized = True

    def _scan_object(self, obj: Any) -> None:
        """Scan a single object and assign tags."""
        memory = ObjectMemory(name=obj.name, object_type=obj.type)

        # Auto-detect tags based on rules
        for tag_name, tag_info in self.KNOWN_TAGS.items():
            detection = tag_info.get("detection")
            if detection and detection(obj):
                memory.add_tag(tag_name, confidence=0.8, source="pattern")
                self._index_tag(tag_name, obj.name)

        self._memory[obj.name] = memory

    def _index_tag(self, tag: str, obj_name: str) -> None:
        """Add object to tag index."""
        if tag not in self._tag_index:
            self._tag_index[tag] = []
        if obj_name not in self._tag_index[tag]:
            self._tag_index[tag].append(obj_name)

    def resolve(
        self, semantic_tag: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[bpy.types.Object]:
        """
        Resolve a semantic tag to a Blender object.

        Args:
            semantic_tag: Tag like "hero_character", "main_camera"
            context: Optional context to disambiguate

        Returns:
            Blender object or None
        """
        if not semantic_tag:
            return None

        self.initialize()

        # Direct object name lookup first (backward compatibility)
        if semantic_tag in bpy.data.objects:
            return bpy.data.objects[semantic_tag]

        # Check tag index
        if semantic_tag in self._tag_index:
            candidates = self._tag_index[semantic_tag]
            if len(candidates) == 1:
                return bpy.data.objects.get(candidates[0])
            elif len(candidates) > 1:
                # Multiple candidates - use context to disambiguate
                return self._disambiguate(candidates, context)

        # Try fuzzy matching on tag names
        for known_tag in self.KNOWN_TAGS:
            if (
                semantic_tag.lower() in known_tag.lower()
                or known_tag.lower() in semantic_tag.lower()
            ):
                candidates = self._tag_index.get(known_tag, [])
                if candidates:
                    return bpy.data.objects.get(candidates[0])

        # Dynamic tags
        if semantic_tag == "last_created" and self._last_created:
            return bpy.data.objects.get(self._last_created)
        if semantic_tag == "last_modified" and self._last_modified:
            return bpy.data.objects.get(self._last_modified)

        return None

    def resolve_multiple(self, semantic_tag: str) -> List[bpy.types.Object]:
        """Resolve a tag to multiple objects (e.g., 'lights')."""
        if not semantic_tag:
            return []

        self.initialize()

        candidates = self._tag_index.get(semantic_tag, [])
        return [bpy.data.objects[name] for name in candidates if name in bpy.data.objects]

    def _disambiguate(
        self, candidates: List[str], context: Optional[Dict[str, Any]] = None
    ) -> Optional[bpy.types.Object]:
        """Choose best candidate based on context."""
        context = context or {}

        # Prefer active object if in candidates
        active = bpy.context.active_object
        if active and active.name in candidates:
            return active

        # Prefer selected objects
        selected = [obj.name for obj in bpy.context.selected_objects]
        for name in candidates:
            if name in selected:
                return bpy.data.objects[name]

        # Most recently accessed
        best = None
        best_time = None
        for name in candidates:
            mem = self._memory.get(name)
            if mem and (best_time is None or mem.last_accessed > best_time):
                best = name
                best_time = mem.last_accessed

        return bpy.data.objects.get(best) if best else bpy.data.objects.get(candidates[0])

    def tag_object(
        self, obj_name: str, tag: str, confidence: float = 1.0, source: str = "user"
    ) -> None:
        """Manually tag an object."""
        if obj_name not in self._memory:
            self._memory[obj_name] = ObjectMemory(name=obj_name, object_type="UNKNOWN")

        self._memory[obj_name].add_tag(tag, confidence, source)
        self._index_tag(tag, obj_name)

    def untag_object(self, obj_name: str, tag: str) -> None:
        """Remove a tag from an object."""
        if obj_name in self._memory:
            self._memory[obj_name].tags = [t for t in self._memory[obj_name].tags if t.tag != tag]

        if tag in self._tag_index:
            self._tag_index[tag] = [n for n in self._tag_index[tag] if n != obj_name]

    def get_tags(self, obj_name: str) -> List[str]:
        """Get all tags for an object."""
        if obj_name not in self._memory:
            return []
        return [t.tag for t in self._memory[obj_name].tags]

    def get_tag_info(self, tag: str) -> Dict[str, Any]:
        """Get information about a tag."""
        if tag in self.KNOWN_TAGS:
            return {
                "tag": tag,
                "description": self.KNOWN_TAGS[tag]["description"],
                "objects": self._tag_index.get(tag, []),
                "auto_detected": True,
            }
        return {
            "tag": tag,
            "description": "User-defined tag",
            "objects": self._tag_index.get(tag, []),
            "auto_detected": False,
        }

    def list_all_tags(self) -> List[str]:
        """List all known and used tags."""
        return list(set(list(self.KNOWN_TAGS.keys()) + list(self._tag_index.keys())))

    def update_access(self, obj_name: str) -> None:
        """Update access tracking for an object."""
        if obj_name in self._memory:
            self._memory[obj_name].last_accessed = datetime.now()
            self._memory[obj_name].access_count += 1

    def set_last_created(self, obj_name: str) -> None:
        """Mark object as most recently created."""
        self._last_created = obj_name
        if obj_name in self._memory:
            self._memory[obj_name].add_tag("last_created", confidence=1.0, source="system")

    def set_last_modified(self, obj_name: str) -> None:
        """Mark object as most recently modified."""
        self._last_modified = obj_name
        if obj_name in self._memory:
            self._memory[obj_name].add_tag("last_modified", confidence=1.0, source="system")

    def query(self, **criteria: Any) -> List[bpy.types.Object]:
        """
        Complex query: find objects matching criteria.

        Examples:
            query(type="MESH", has_tag="selected_objects")
            query(tags=["light_objects", "key_light"])
        """
        results = []

        for obj in bpy.data.objects:
            matches = True

            # Check type
            if "type" in criteria and obj.type != criteria["type"]:
                matches = False

            # Check tags
            if "has_tag" in criteria:
                mem = self._memory.get(obj.name)
                if not mem or not mem.has_tag(criteria["has_tag"]):
                    matches = False

            if "tags" in criteria:
                mem = self._memory.get(obj.name)
                required_tags = criteria["tags"]
                if isinstance(required_tags, str):
                    required_tags = [required_tags]
                if not mem or not all(mem.has_tag(t) for t in required_tags):
                    matches = False

            if matches:
                results.append(obj)

        return results

    def get_scene_summary(self) -> Dict[str, Any]:
        """Get semantic summary of the scene."""
        self.initialize()

        main_camera = self.resolve("main_camera")
        active_camera = self.resolve("active_camera")
        hero_character = self.resolve("hero_character")
        ground_plane = self.resolve("ground_plane")

        return {
            "total_objects": len(bpy.data.objects),
            "tagged_objects": len(self._memory),
            "known_tags": {tag: len(objects) for tag, objects in self._tag_index.items()},
            "main_camera": main_camera.name if main_camera else None,
            "active_camera": active_camera.name if active_camera else None,
            "hero_character": hero_character.name if hero_character else None,
            "ground_plane": ground_plane.name if ground_plane else None,
            "lights": [obj.name for obj in self.resolve_multiple("light_objects")],
            "selected": [obj.name for obj in self.resolve_multiple("selected_objects")],
        }


# Global instance
_semantic_memory = None


def get_semantic_memory() -> SemanticSceneMemory:
    """Get the global semantic memory instance."""
    global _semantic_memory
    if _semantic_memory is None:
        _semantic_memory = SemanticSceneMemory()
    return _semantic_memory


def resolve_semantic(
    tag: str, context: Optional[Dict[str, Any]] = None
) -> Optional[bpy.types.Object]:
    """Convenience function: resolve a semantic tag."""
    return get_semantic_memory().resolve(tag, context)


def resolve_semantic_multiple(tag: str) -> List[bpy.types.Object]:
    """Convenience function: resolve to multiple objects."""
    return get_semantic_memory().resolve_multiple(tag)
