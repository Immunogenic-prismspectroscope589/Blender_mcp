"""
AI State Mirror for Blender MCP 1.0.0
"The All-Seeing Eye"

Computes granular semantic diffs between state snapshots to provide
meaningful feedback to the AI.

Features:
- Granular Semantic Diffing (Transform, Hierarchy, Data, Topology)
- DiffLevel Awareness (Optimization)
- Structural Hashing
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

try:
    import bpy
    # import mathutils  # noqa: F401

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
    bmesh: Any = None

from .object_identity import IdentityManager
from .execution_engine import DiffLevel  # type: ignore
from .logging_config import get_logger

logger = get_logger()


@dataclass
class ObjectState:
    """Captured state of a single object."""

    uid: str
    name: str
    type: str
    parent_uid: Optional[str]
    # Transform
    location: Tuple[float, float, float]
    rotation: Tuple[float, float, float]
    scale: Tuple[float, float, float]
    # Data (DiffLevel.FULL)
    data_hash: str = ""
    # Topology (DiffLevel.FULL)
    topo_hash: str = ""


@dataclass
class StateSnapshot:
    """Collection of object states."""

    timestamp: float
    objects: Dict[str, ObjectState] = field(default_factory=dict)


@dataclass
class StateDiff:
    """Semantic difference between two snapshots."""

    added: List[Dict[str, Any]] = field(default_factory=list)
    removed: List[Dict[str, Any]] = field(default_factory=list)
    modified: List[Dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.modified)

    def to_dict(self) -> Dict[str, Any]:
        return {"added": self.added, "removed": self.removed, "modified": self.modified}


class AIStateMirror:
    """
    Captures and compares Blender state.
    """

    def __init__(self) -> None:
        self.identity_mgr = IdentityManager()

    def capture(self, diff_level: DiffLevel = DiffLevel.TRANSFORM) -> StateSnapshot:
        """Capture current scene state."""
        if not BPY_AVAILABLE:
            return StateSnapshot(0.0)

        snapshot = StateSnapshot(timestamp=0.0)  # Time could be added

        # We iteration over all objects in scene (or view layer?)
        # Scene objects is safest.
        scene_objects: List[Any] = []
        if bpy.context.scene:
            scene_objects = list(bpy.context.scene.objects)

        for obj in scene_objects:
            uid = self.identity_mgr.resolve_uid(obj)

            # Parent UID
            p_uid = None
            if obj.parent:
                p_uid = self.identity_mgr.resolve_uid(obj.parent)

            # Hashes
            d_hash = ""
            t_hash = ""

            if diff_level == DiffLevel.FULL:
                d_hash = self._hash_data(obj)
                if obj.type == "MESH":
                    t_hash = self._hash_topology(obj)

            state = ObjectState(
                uid=uid,
                name=obj.name,
                type=obj.type,
                parent_uid=p_uid,
                location=tuple(obj.location),
                rotation=tuple(obj.rotation_euler),
                scale=tuple(obj.scale),
                data_hash=d_hash,
                topo_hash=t_hash,
            )
            snapshot.objects[uid] = state

        return snapshot

    def compute_diff(
        self, old: StateSnapshot, new: StateSnapshot, diff_level: DiffLevel = DiffLevel.TRANSFORM
    ) -> StateDiff:
        """Compute semantic diff between two snapshots."""
        diff = StateDiff()

        old_keys = set(old.objects.keys())
        new_keys = set(new.objects.keys())

        # Added
        for uid in new_keys - old_keys:
            obj = new.objects[uid]
            diff.added.append({"uid": uid, "name": obj.name, "type": obj.type})

        # Removed
        for uid in old_keys - new_keys:
            obj = old.objects[uid]
            diff.removed.append({"uid": uid, "name": obj.name, "type": obj.type})

        # Modified
        for uid in old_keys & new_keys:
            o = old.objects[uid]
            n = new.objects[uid]

            changes = []

            # 1. Transform Change (High Priority)
            EPSILON = 0.0001
            if self._dist(o.location, n.location) > EPSILON:
                changes.append(f"Location: {o.location} -> {n.location}")
            if self._dist(o.rotation, n.rotation) > EPSILON:
                changes.append("Rotation changed")  # Simplified for readability
            if self._dist(o.scale, n.scale) > EPSILON:
                changes.append(f"Scale: {o.scale} -> {n.scale}")

            # 2. Hierarchy Change
            if o.parent_uid != n.parent_uid:
                p_name_old = (
                    old.objects[o.parent_uid].name
                    if o.parent_uid and o.parent_uid in old.objects
                    else "None"
                )
                p_name_new = (
                    new.objects[n.parent_uid].name
                    if n.parent_uid and n.parent_uid in new.objects
                    else "None"
                )
                changes.append(f"Parent: {p_name_old} -> {p_name_new}")

            # 3. Rename
            if o.name != n.name:
                changes.append(f"Renamed: {o.name} -> {n.name}")

            # 4. Data/Topo (Only if FULL)
            if diff_level == DiffLevel.FULL:
                if o.data_hash != n.data_hash:
                    changes.append("Data changed (Properties)")
                if o.topo_hash != n.topo_hash:
                    changes.append("Topology changed (Mesh Structure)")

            if changes:
                diff.modified.append({"uid": uid, "name": n.name, "changes": changes})

        return diff

    def _dist(self, v1: Tuple[float, ...], v2: Tuple[float, ...]) -> float:
        return float(sum((a - b) ** 2 for a, b in zip(v1, v2)) ** 0.5)

    def _hash_data(self, obj: Any) -> str:
        """Hash data properties (Material, etc)."""
        # Simplistic hash of data name or ref
        if not obj.data:
            return ""
        return str(hash(obj.data.name))  # Using name as proxy for now

    def _hash_topology(self, obj: Any) -> str:
        """Hash mesh topology (Verts/Edges/Faces)."""
        if not obj.data or not hasattr(obj.data, "vertices"):
            return ""

        # Fast topo hash: Count
        mesh = obj.data
        return f"v{len(mesh.vertices)}e{len(mesh.edges)}f{len(mesh.polygons)}"
