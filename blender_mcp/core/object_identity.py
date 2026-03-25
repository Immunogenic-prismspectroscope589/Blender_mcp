"""
Object Identity Manager for Blender MCP 1.0.0
"Ship of Theseus Paradox Resolver"

Maintains persistent object identity across:
- Renames (Name changes, Identity stays)
- Pointer invalidation (Undo/Redo, File Load)
- Python garbage collection

High Mode Philosophy:
"I know who you are, even if you change your name or face."
"""

import uuid
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any, List, Tuple
from difflib import SequenceMatcher

try:
    import bpy
    import mathutils

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
    bmesh: Any = None

from .logging_config import get_logger

logger = get_logger()


@dataclass
class IdentityData:
    """Persistent identity signature."""

    uid: str
    name: str  # Last known name
    type: str
    parent_name: Optional[str] = None
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    last_seen: float = 0.0

    # Matching confidence for debugging
    match_score: float = 1.0


class IdentityManager:
    """
    Singleton managing the mapping between:
    Blender Object (Transient Pointer) <-> MCP UID (Persistent)
    """

    _instance: Optional["IdentityManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "IdentityManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._uid_map: Dict[str, IdentityData] = {}  # UID -> Data
        self._ptr_map: Dict[int, str] = {}  # id(obj) -> UID
        self._initialized = True

        # Registration
        self._register_handlers()

    def _register_handlers(self) -> None:
        if not BPY_AVAILABLE:
            return

        # Register for Undo/Load/Depsgraph
        # Note: In a real addon, use proper append/remove checks
        if self.on_undo_post not in bpy.app.handlers.undo_post:
            bpy.app.handlers.undo_post.append(self.on_undo_post)
        if self.on_load_post not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(self.on_load_post)

    def resolve_uid(self, obj: Any) -> str:
        """Get or create UID for a blender object."""
        if not obj:
            return ""

        ptr_id = id(obj)

        # 1. Check Pointer Map (Fast Path)
        if ptr_id in self._ptr_map:
            uid = self._ptr_map[ptr_id]
            # Update data while we are here to keep it fresh
            self._update_data(uid, obj)
            return uid

        # 2. Check Name Map (heuristic if pointer missing but name exists?)
        # Dangerous due to Rename. Better to treat as new if pointer missing
        # unless we are in a "Rebuild" step.

        # 3. Create New
        new_uid = str(uuid.uuid4())
        self._ptr_map[ptr_id] = new_uid
        self._update_data(new_uid, obj)
        return new_uid

    def get_object(self, uid: str) -> Optional[Any]:
        """Resolve UID to Blender Object."""
        # This is expensive, O(N) scan if we don't have reverse map valid.
        # But usually we go Obj -> UID.
        # For UID -> Obj, we might need a cache refresh.

        # Try to find by pointer? pointers change.
        # We need to scan scene objects and match UIDs?
        # Or keep a reverse cache valid?

        # For now, simplistic scan if needed, or rely on _ptr_map validity.
        target_data = self._uid_map.get(uid)
        if not target_data:
            return None

        # Try to find object by name first (Fastest)
        obj = bpy.data.objects.get(target_data.name)
        if obj and self.resolve_uid(obj) == uid:
            return obj

        return None

    def _update_data(self, uid: str, obj: Any) -> None:
        """Update last known state."""
        loc = (0.0, 0.0, 0.0)
        rot = (0.0, 0.0, 0.0)
        scl = (1.0, 1.0, 1.0)
        p_name = None

        if hasattr(obj, "matrix_world"):
            # Use local or world? Identity usually implicit on Local or interactions
            # But matrix_world is absolute.
            # Let's simple use loc/rot/scale properties for now
            loc = tuple(obj.location)
            rot = tuple(obj.rotation_euler)
            scl = tuple(obj.scale)

        if obj.parent:
            p_name = obj.parent.name

        self._uid_map[uid] = IdentityData(
            uid=uid,
            name=obj.name,
            type=obj.type,
            parent_name=p_name,
            location=loc,
            rotation=rot,
            scale=scl,
            last_seen=time.time(),
        )

    @bpy.app.handlers.persistent
    def on_undo_post(self, *args: Any) -> None:
        """Handle Undo Event - Invalidates Pointers!"""
        if self._instance:
            logger.warning("[Identity] Undo detected. Rebuilding Identity Map...")
            self._instance.rebuild_map()

    @bpy.app.handlers.persistent
    def on_load_post(self, *args: Any) -> None:
        """Handle File Load - Fresh State."""
        if self._instance:
            logger.warning("[Identity] Load detected. Clearing Identity Map...")
            self._instance._uid_map.clear()
            self._instance._ptr_map.clear()
            # Optionally populate fresh
            self._instance.rebuild_map()

    def rebuild_map(self) -> None:
        """
        Fuzzy Match Rebuild.
        Re-links new object pointers to existing UIDs based on heuristics.
        """
        if not BPY_AVAILABLE:
            return

        # 1. Clear pointer map (all invalid)
        self._ptr_map.clear()

        current_objects = []
        if bpy.context.scene:
            current_objects = list(bpy.context.scene.objects)

        unmatched_uids = set(self._uid_map.keys())

        # Thresholds
        SCORE_THRESHOLD = 0.75

        # First pass: Exact Name + Type matches (Fast)
        for obj in current_objects[:]:
            ptr_id = id(obj)

            # Find candidate UIDs that match this name
            candidates = [uid for uid in unmatched_uids if self._uid_map[uid].name == obj.name]

            for uid in candidates:
                data = self._uid_map[uid]
                if data.type == obj.type:
                    # High confidence match
                    self._ptr_map[ptr_id] = uid
                    unmatched_uids.remove(uid)
                    current_objects.remove(obj)
                    break

        # Group unmatched UIDs by Type for faster lookup
        # O(N) prep
        uids_by_type: Dict[str, List[str]] = {}
        for uid in unmatched_uids:
            # IdentityData must expose 'type'
            dtype = self._uid_map[uid].type
            if dtype not in uids_by_type:
                uids_by_type[dtype] = []
            uids_by_type[dtype].append(uid)

        # Second pass: Fuzzy Match (Slow but Optimized)
        # O(M * (N/Types)) complexity
        for obj in current_objects:
            best_score = 0.0
            best_uid = None

            # Pre-calc object probs
            p_name = obj.parent.name if obj.parent else None
            o_loc = tuple(obj.location)

            # Only compare against objects of the SAME TYPE
            # (Type change is unlikely enough to ignore for fuzzy match)
            candidates = uids_by_type.get(obj.type, [])

            for uid in candidates:
                data = self._uid_map[uid]

                # 1. Name Similarity (40%)
                name_score = SequenceMatcher(None, data.name, obj.name).ratio()

                # 2. Parent Match (20%)
                parent_score = 1.0 if data.parent_name == p_name else 0.0

                # 3. Location Match (30%)
                # Vector distance
                data_loc = mathutils.Vector(data.location)
                obj_loc_vec = mathutils.Vector(o_loc)
                dist = (data_loc - obj_loc_vec).length

                # Inverse distance decay (safer than linear cut-off)
                # dist=0 -> 1.0
                # dist=1 -> 0.5
                # dist=10 -> ~0.1
                loc_score = 1.0 / (1.0 + dist)

                # 4. Type Match (10%)
                type_score = 1.0 if data.type == obj.type else 0.0

                # Total
                total_score = (
                    (name_score * 0.4)
                    + (parent_score * 0.2)
                    + (loc_score * 0.3)
                    + (type_score * 0.1)
                )

                if total_score > best_score:
                    best_score = total_score
                    best_uid = uid

            if best_score >= SCORE_THRESHOLD and best_uid:
                self._ptr_map[id(obj)] = best_uid
                unmatched_uids.remove(best_uid)
                logger.info(
                    f"[Identity] Fuzzy Match: {obj.name} -> {data.name} (Score: {best_score:.2f})"
                )
            else:
                # Treat as new object (will be assigned new UID on access)
                pass

        # Cleanup: UIDs still unmatched are effectively 'Deleted' (or hidden in another scene)
        # We keep them in _uid_map for historical lookup or 'resurrection' via Undo Redo?
        # Yes, keep them.
