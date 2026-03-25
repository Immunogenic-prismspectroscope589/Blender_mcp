"""
Advanced Name Resolution System with Multi-language Support and Fuzzy Matching
Provides intelligent name resolution for Blender entities with aliases and fallbacks
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, Optional, cast

import bpy


def _default_sun_name() -> str:
    """Return a safe sun/light default without assuming Blender runtime context."""
    data = getattr(bpy, "data", None)
    lights = getattr(data, "lights", None)
    if lights is not None and "Sun" in dir(lights):
        return "Sun"
    return "Light"


def _default_capsule_name() -> str:
    """Return capsule primitive name only when operator exists."""
    ops = getattr(bpy, "ops", None)
    mesh_ops = getattr(ops, "mesh", None)
    if mesh_ops is not None and hasattr(mesh_ops, "primitive_capsule_add"):
        return "Capsule"
    return "Cylinder"


DEFAULT_SUN_NAME = _default_sun_name()
DEFAULT_CAPSULE_NAME = _default_capsule_name()


class MultiLanguageAliases:
    """
    Multi-language aliases for common Blender entities
    Supports English, Spanish, French, German, Italian, Portuguese, Russian, Turkish, Japanese, Chinese
    """

    # Object name aliases
    OBJECT_ALIASES = {
        # English variants
        "box": "Cube",
        "cube": "Cube",
        "ball": "Sphere",
        "sphere": "Sphere",
        "monkey": "Suzanne",
        "suzanne": "Suzanne",
        "cam": "Camera",
        "camera": "Camera",
        "lamp": "Light",
        "light": "Light",
        "sun": DEFAULT_SUN_NAME,
        "point_light": "Point",
        "spot_light": "Spot",
        "area_light": "Area",
        "cone": "Cone",
        "cylinder": "Cylinder",
        "plane": "Plane",
        "torus": "Torus",
        "ico_sphere": "Icosphere",
        "icosphere": "Icosphere",
        "uv_sphere": "Sphere",
        "capsule": DEFAULT_CAPSULE_NAME,
        "circle": "Circle",
        "grid": "Grid",
        "monkey_head": "Suzanne",
        # Spanish (Español)
        "cubo": "Cube",
        "esfera": "Sphere",
        "caja": "Cube",
        "bola": "Sphere",
        "mono": "Suzanne",
        "camara": "Camera",
        "luz": "Light",
        "sol": DEFAULT_SUN_NAME,
        "cono": "Cone",
        "cilindro": "Cylinder",
        "plano": "Plane",
        # French (Français)
        "cube_fr": "Cube",
        "sphere_fr": "Sphere",
        "boite": "Cube",
        "boule": "Sphere",
        "singe": "Suzanne",
        "camera_fr": "Camera",
        "lumiere": "Light",
        "soleil": DEFAULT_SUN_NAME,
        "cone_fr": "Cone",
        "cylindre": "Cylinder",
        "plan": "Plane",
        # German (Deutsch)
        "wurfel": "Cube",
        "kugel": "Sphere",
        "kiste": "Cube",
        "ball_de": "Sphere",
        "affe": "Suzanne",
        "kamera": "Camera",
        "licht": "Light",
        "sonne": DEFAULT_SUN_NAME,
        "kegel": "Cone",
        "zylinder": "Cylinder",
        "ebene": "Plane",
        # Italian (Italiano)
        "cubo_it": "Cube",
        "sfera": "Sphere",
        "scatola": "Cube",
        "palla": "Sphere",
        "scimmia": "Suzanne",
        "telecamera": "Camera",
        "luce": "Light",
        "sole_it": DEFAULT_SUN_NAME,
        "cono_it": "Cone",
        "cilindro_it": "Cylinder",
        "piano": "Plane",
        # Portuguese (Português)
        "cubo_pt": "Cube",
        "esfera_pt": "Sphere",
        "caixa": "Cube",
        "bola_pt": "Sphere",
        "macaco": "Suzanne",
        "camera_pt": "Camera",
        "luz_pt": "Light",
        "sol_pt": DEFAULT_SUN_NAME,
        "cone_pt": "Cone",
        "cilindro_pt": "Cylinder",
        "plano_pt": "Plane",
        # Turkish (Türkçe)
        "kup": "Cube",
        "küp": "Cube",
        "kure": "Sphere",
        "küre": "Sphere",
        "top": "Sphere",
        "kutu": "Cube",
        "maymun": "Suzanne",
        "kamera_tr": "Camera",
        "isik": "Light",
        "ışık": "Light",
        "gunes": DEFAULT_SUN_NAME,
        "güneş": DEFAULT_SUN_NAME,
        "kon": "Cone",
        "konik": "Cone",
        "silindir": "Cylinder",
        "duzlem": "Plane",
        "düzlem": "Plane",
        "daire": "Circle",
        # Russian (Русский)
        "kub": "Cube",
        "куб": "Cube",
        "sfera_ru": "Sphere",
        "сфера": "Sphere",
        "shar": "Sphere",
        "шар": "Sphere",
        "obeziana": "Suzanne",
        "обезьяна": "Suzanne",
        "kamera_ru": "Camera",
        "камера": "Camera",
        "svet": "Light",
        "свет": "Light",
        "solnce": DEFAULT_SUN_NAME,
        "солнце": DEFAULT_SUN_NAME,
        "konys": "Cone",
        "конус": "Cone",
        "cilindr": "Cylinder",
        "цилиндр": "Cylinder",
        "ploskost": "Plane",
        "плоскость": "Plane",
        # Japanese (日本語)
        "キューブ": "Cube",
        "球": "Sphere",
        "箱": "Cube",
        "猿": "Suzanne",
        "カメラ": "Camera",
        "ライト": "Light",
        "太陽": DEFAULT_SUN_NAME,
        "円錐": "Cone",
        "円柱": "Cylinder",
        "平面": "Plane",
        # Chinese (中文)
        "立方体": "Cube",
        "球体": "Sphere",
        "盒子": "Cube",
        "猴子": "Suzanne",
        " Suzanne头": "Suzanne",
        "相机": "Camera",
        "灯光": "Light",
        "太阳": DEFAULT_SUN_NAME,
        "圆锥": "Cone",
        "圆柱": "Cylinder",
        # "平面": "Plane", # DUPLICATE REMOVED
    }

    # Material name aliases
    MATERIAL_ALIASES = {
        "basic": "Material",
        "default": "Material",
        "principled": "Principled BSDF",
        "glass": "Glass BSDF",
        "metal": "Metallic",
        "emission": "Emission",
        "diffuse": "Diffuse BSDF",
        "glossy": "Glossy BSDF",
    }

    # Collection name aliases
    COLLECTION_ALIASES = {
        "main": "Collection",
        "scene": "Scene Collection",
        "master": "Master Collection",
        "default": "Collection",
    }

    # Brush name aliases for sculpting
    BRUSH_ALIASES = {
        "draw": "Draw",
        "clay": "Clay",
        "clay_strips": "Clay Strips",
        "crease": "Crease",
        "blob": "Blob",
        "smooth": "Smooth",
        "grab": "Grab",
        "snake_hook": "Snake Hook",
        "inflate": "Inflate",
        "pinch": "Pinch",
        "scrape": "Scrape",
        "flatten": "Flatten",
        "fill": "Fill",
        "mask": "Mask",
    }


class NameResolver:
    """
    Advanced name resolution with fuzzy matching and multi-language support
    """

    def __init__(self) -> None:
        self.aliases = MultiLanguageAliases()
        self._cache: Dict[str, Optional[bpy.types.Object]] = {}

    def resolve_object(
        self, name: str, use_aliases: bool = True, use_fuzzy: bool = True, threshold: float = 0.6
    ) -> Optional[bpy.types.Object]:
        """
        Resolve object name with aliases and fuzzy matching

        Args:
            name: Object name to resolve
            use_aliases: Whether to check multi-language aliases
            use_fuzzy: Whether to use fuzzy matching as fallback
            threshold: Minimum similarity score for fuzzy match (0-1)

        Returns:
            Resolved Object or None
        """
        if not name:
            return None

        # Normalize name
        search_name = name.strip()

        # Cache key
        cache_key = f"obj:{search_name}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            try:
                # Validate the cached reference is still alive (not StructRNA-freed)
                if cached is not None:
                    _ = cached.name
                return cached
            except (ReferenceError, RuntimeError):
                # Stale reference — evict and fall through to fresh lookup
                del self._cache[cache_key]

        # 1. Exact match
        if search_name in bpy.data.objects:
            result = bpy.data.objects[search_name]
            self._cache[cache_key] = result
            return result

        # 2. Check aliases
        if use_aliases:
            alias_name = MultiLanguageAliases.OBJECT_ALIASES.get(search_name.lower())
            if alias_name and alias_name in bpy.data.objects:
                result = bpy.data.objects[alias_name]
                self._cache[cache_key] = result
                return result

        # 3. Case-insensitive match
        search_lower = search_name.lower()
        for obj in bpy.data.objects:
            if obj.name.lower() == search_lower:
                self._cache[cache_key] = obj
                return obj

        # 4. Fuzzy matching
        if use_fuzzy:
            best_match = None
            best_score = 0.0

            for obj in bpy.data.objects:
                # Check name similarity
                score = SequenceMatcher(None, search_lower, obj.name.lower()).ratio()
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = obj

            if best_match:
                self._cache[cache_key] = best_match
                return best_match

        return None

    def resolve_material(self, name: str) -> Optional[bpy.types.Material]:
        """Resolve material name with aliases"""
        if not name:
            return None

        # Exact match
        if name in bpy.data.materials:
            return bpy.data.materials[name]

        # Check aliases
        alias = MultiLanguageAliases.MATERIAL_ALIASES.get(name.lower())
        if alias and alias in bpy.data.materials:
            return bpy.data.materials[alias]

        # Case-insensitive
        name_lower = name.lower()
        for mat in bpy.data.materials:
            if mat.name.lower() == name_lower:
                return mat

        return None

    def resolve_collection(self, name: str) -> Optional[bpy.types.Collection]:
        """Resolve collection name with aliases"""
        if not name:
            return None

        # Exact match
        if name in bpy.data.collections:
            return bpy.data.collections[name]

        # Check aliases
        alias = MultiLanguageAliases.COLLECTION_ALIASES.get(name.lower())
        if alias and alias in bpy.data.collections:
            return bpy.data.collections[alias]

        # Case-insensitive
        name_lower = name.lower()
        for coll in bpy.data.collections:
            if coll.name.lower() == name_lower:
                return coll

        # Scene collection special case
        if name_lower in ("scene", "master", "main"):
            scene = getattr(bpy.context, "scene", None)
            if scene is not None:
                return cast(bpy.types.Collection, scene.collection)
            return None

        return None

    def resolve_bone(
        self, armature: bpy.types.Object, name: str, use_fuzzy: bool = True
    ) -> Optional[bpy.types.Bone]:
        """
        Resolve bone name with encoding safety and fuzzy matching

        Args:
            armature: Armature object
            name: Bone name to resolve
            use_fuzzy: Whether to use fuzzy matching

        Returns:
            Resolved Bone or None
        """
        if (
            not armature
            or not hasattr(armature, "data")
            or getattr(armature, "type", "") != "ARMATURE"
        ):
            return None

        armature_data = getattr(armature, "data", None)
        if armature_data is None or not hasattr(armature_data, "bones"):
            return None
        bones = armature_data.bones

        # 1. Exact match
        if name in bones:
            return cast(bpy.types.Bone, bones[name])

        # 2. Case-insensitive
        name_lower = name.lower()
        for bone in bones:
            try:
                if bone.name.lower() == name_lower:
                    return cast(bpy.types.Bone, bone)
            except:
                # Encoding error, skip
                continue

        # 3. Fuzzy matching
        if use_fuzzy:
            best_match: Optional[bpy.types.Bone] = None
            best_score = 0.0

            for bone in bones:
                try:
                    score = SequenceMatcher(None, name_lower, bone.name.lower()).ratio()
                    if score > best_score and score >= 0.6:
                        best_score = score
                        best_match = bone
                except:
                    continue

            return best_match

        return None

    def resolve_brush(self, name: str, tool: str = "sculpt") -> Optional[bpy.types.Brush]:
        """
        Resolve brush name with aliases and version compatibility

        Args:
            name: Brush name or alias
            tool: Tool type (sculpt, vertex_paint, weight_paint, etc.)

        Returns:
            Resolved Brush or None
        """
        if not name:
            return None

        # Check aliases
        alias = MultiLanguageAliases.BRUSH_ALIASES.get(name.lower())
        brush_name = alias or name

        # Search in brushes
        for brush in bpy.data.brushes:
            # Check if brush is for the right tool
            brush_for_tool = False
            if tool == "sculpt" and hasattr(brush, "use_paint_sculpt"):
                brush_for_tool = brush.use_paint_sculpt
            elif tool == "vertex_paint" and hasattr(brush, "use_paint_vertex"):
                brush_for_tool = brush.use_paint_vertex
            elif tool == "weight_paint" and hasattr(brush, "use_paint_weight"):
                brush_for_tool = brush.use_paint_weight

            if brush_for_tool or tool == "any":
                if brush.name == brush_name:
                    return brush

        # Case-insensitive fallback
        brush_lower = brush_name.lower()
        for brush in bpy.data.brushes:
            if brush.name.lower() == brush_lower:
                return brush

        # Partial match
        for brush in bpy.data.brushes:
            if brush_lower in brush.name.lower():
                return brush

        return None

    def clear_cache(self) -> None:
        """Clear resolution cache"""
        self._cache.clear()


# Global resolver instance
_resolver = None


def get_resolver() -> NameResolver:
    """Get global name resolver instance"""
    global _resolver
    if _resolver is None:
        _resolver = NameResolver()
    return _resolver


def resolve_name(
    name: str, collection_type: str = "objects", use_semantic: bool = True, **kwargs: Any
) -> Optional[Any]:
    """
    Convenience function to resolve any name

    V1.0.0: Added semantic tag support. If name is not found as exact match,
    tries to resolve it as a semantic tag (e.g., "hero_character", "main_camera").

    Args:
        name: Name to resolve (or semantic tag)
        collection_type: Type of entity (objects, materials, collections, brushes)
        use_semantic: Whether to try semantic resolution for objects
        **kwargs: Additional arguments for specific resolvers

    Returns:
        Resolved entity or None
    """
    resolver = get_resolver()

    if collection_type == "objects":
        # Try standard resolution first
        result = resolver.resolve_object(name, **kwargs)
        if result:
            return result

        # V1.0.0: Try semantic resolution
        if use_semantic and result is None:
            try:
                from .semantic_memory import resolve_semantic

                semantic_result = resolve_semantic(name, context=kwargs)
                if semantic_result:
                    return semantic_result
            except ImportError:
                pass  # Semantic memory not available
        return None

    elif collection_type == "materials":
        return resolver.resolve_material(name)
    elif collection_type == "collections":
        return resolver.resolve_collection(name)
    elif collection_type == "brushes":
        return resolver.resolve_brush(name, kwargs.get("tool", "sculpt"))
    elif collection_type == "bones":
        armature = kwargs.get("armature")
        if armature is None:
            return None
        return resolver.resolve_bone(armature, name, kwargs.get("use_fuzzy", True))
    else:
        # Generic lookup
        collection = getattr(bpy.data, collection_type, None)
        if collection and name in collection:
            return collection[name]
        return None
