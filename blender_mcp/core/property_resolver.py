"""
Property Path Resolver for Blender MCP 1.0.0

Provides intelligent property path resolution with:
- Multi-language alias support (EN, TR, FR, ES, CN, DE, JP, RU)
- Standard 3D software conventions (Maya, 3ds Max, Cinema 4D style)
- Array index handling
- Dot notation support
- Fuzzy matching fallback

High Mode Philosophy: User-friendly input, machine-perfect output.
"""

from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union
from difflib import SequenceMatcher

ResolvedProperty = Tuple[str, int]
ResolvedBatch = List[ResolvedProperty]
ResolveResult = Union[ResolvedProperty, ResolvedBatch, None]


class SpecialProperty(TypedDict):
    description: str
    paths: ResolvedBatch


# =============================================================================
# PROPERTY ALIASES - Multi-Language & Multi-Software Support
# =============================================================================

PROPERTY_ALIASES = {
    # =========================================================================
    # ROTATION - Euler
    # =========================================================================
    # English
    "rotation_x": ("rotation_euler", 0),
    "rotation_y": ("rotation_euler", 1),
    "rotation_z": ("rotation_euler", 2),
    "rot_x": ("rotation_euler", 0),
    "rot_y": ("rotation_euler", 1),
    "rot_z": ("rotation_euler", 2),
    "rx": ("rotation_euler", 0),
    "ry": ("rotation_euler", 1),
    "rz": ("rotation_euler", 2),
    # Turkish
    "dönüş_x": ("rotation_euler", 0),
    "dönüş_y": ("rotation_euler", 1),
    "dönüş_z": ("rotation_euler", 2),
    "donus_x": ("rotation_euler", 0),
    "donus_y": ("rotation_euler", 1),
    "donus_z": ("rotation_euler", 2),
    # French
    # "rotation": ("rotation_euler", -1), # REMOVED DUPLICATE
    "rot": ("rotation_euler", -1),
    # Spanish
    "rotación_x": ("rotation_euler", 0),
    "rotación_y": ("rotation_euler", 1),
    "rotación_z": ("rotation_euler", 2),
    "rotacion_x": ("rotation_euler", 0),
    "rotacion_y": ("rotation_euler", 1),
    "rotacion_z": ("rotation_euler", 2),
    # Chinese
    "旋转_x": ("rotation_euler", 0),
    "旋转_y": ("rotation_euler", 1),
    "旋转_z": ("rotation_euler", 2),
    "旋转x": ("rotation_euler", 0),
    "旋转y": ("rotation_euler", 1),
    "旋转z": ("rotation_euler", 2),
    # German
    "drehung_x": ("rotation_euler", 0),
    "drehung_y": ("rotation_euler", 1),
    "drehung_z": ("rotation_euler", 2),
    # "rotation": ("rotation_euler", -1), # REMOVED DUPLICATE
    # Japanese
    "回転_x": ("rotation_euler", 0),
    "回転_y": ("rotation_euler", 1),
    "回転_z": ("rotation_euler", 2),
    # Russian
    "вращение_x": ("rotation_euler", 0),
    "вращение_y": ("rotation_euler", 1),
    "вращение_z": ("rotation_euler", 2),
    # =========================================================================
    # LOCATION / POSITION
    # =========================================================================
    # English
    "location_x": ("location", 0),
    "location_y": ("location", 1),
    "location_z": ("location", 2),
    "loc_x": ("location", 0),
    "loc_y": ("location", 1),
    "loc_z": ("location", 2),
    "pos_x": ("location", 0),
    "pos_y": ("location", 1),
    "pos_z": ("location", 2),
    "translate_x": ("location", 0),
    "translate_y": ("location", 1),
    "translate_z": ("location", 2),
    # Maya-style
    "tx": ("location", 0),
    "ty": ("location", 1),
    "tz": ("location", 2),
    # 3ds Max style
    "x_position": ("location", 0),
    "y_position": ("location", 1),
    "z_position": ("location", 2),
    # Turkish
    "konum_x": ("location", 0),
    "konum_y": ("location", 1),
    "konum_z": ("location", 2),
    "pozisyon_x": ("location", 0),
    "pozisyon_y": ("location", 1),
    "pozisyon_z": ("location", 2),
    # French
    "position_x": ("location", 0),
    "position_y": ("location", 1),
    "position_z": ("location", 2),
    "emplacement_x": ("location", 0),
    "emplacement_y": ("location", 1),
    "emplacement_z": ("location", 2),
    # Spanish
    "ubicación_x": ("location", 0),
    "ubicación_y": ("location", 1),
    "ubicación_z": ("location", 2),
    "ubicacion_x": ("location", 0),
    "ubicacion_y": ("location", 1),
    "ubicacion_z": ("location", 2),
    "posición_x": ("location", 0),
    "posición_y": ("location", 1),
    "posición_z": ("location", 2),
    # Chinese
    "位置_x": ("location", 0),
    "位置_y": ("location", 1),
    "位置_z": ("location", 2),
    "位置x": ("location", 0),
    "位置y": ("location", 1),
    "位置z": ("location", 2),
    # German
    # position_x/y/z already defined in French section
    "standort_x": ("location", 0),
    "standort_y": ("location", 1),
    "standort_z": ("location", 2),
    # Japanese
    # "位置_x": ("location", 0), # Already defined in Chinese section
    # "位置_y": ("location", 1),
    # "位置_z": ("location", 2),
    # Russian
    "положение_x": ("location", 0),
    "положение_y": ("location", 1),
    "положение_z": ("location", 2),
    "позиция_x": ("location", 0),
    "позиция_y": ("location", 1),
    "позиция_z": ("location", 2),
    # =========================================================================
    # SCALE
    # =========================================================================
    # English
    "scale_x": ("scale", 0),
    "scale_y": ("scale", 1),
    "scale_z": ("scale", 2),
    "scl_x": ("scale", 0),
    "scl_y": ("scale", 1),
    "scl_z": ("scale", 2),
    # Maya-style
    "sx": ("scale", 0),
    "sy": ("scale", 1),
    "sz": ("scale", 2),
    # Turkish
    "ölçek_x": ("scale", 0),
    "ölçek_y": ("scale", 1),
    "ölçek_z": ("scale", 2),
    "olcek_x": ("scale", 0),
    "olcek_y": ("scale", 1),
    "olcek_z": ("scale", 2),
    "boyut_x": ("scale", 0),
    "boyut_y": ("scale", 1),
    "boyut_z": ("scale", 2),
    # French
    "échelle_x": ("scale", 0),
    "échelle_y": ("scale", 1),
    "échelle_z": ("scale", 2),
    "echelle_x": ("scale", 0),
    "echelle_y": ("scale", 1),
    "echelle_z": ("scale", 2),
    # Spanish
    "escala_x": ("scale", 0),
    "escala_y": ("scale", 1),
    "escala_z": ("scale", 2),
    # Chinese
    "缩放_x": ("scale", 0),
    "缩放_y": ("scale", 1),
    "缩放_z": ("scale", 2),
    "缩放x": ("scale", 0),
    "缩放y": ("scale", 1),
    "缩放z": ("scale", 2),
    # German
    "skalierung_x": ("scale", 0),
    "skalierung_y": ("scale", 1),
    "skalierung_z": ("scale", 2),
    # Japanese
    "スケール_x": ("scale", 0),
    "スケール_y": ("scale", 1),
    "スケール_z": ("scale", 2),
    # Russian
    "масштаб_x": ("scale", 0),
    "масштаб_y": ("scale", 1),
    "масштаб_z": ("scale", 2),
    # =========================================================================
    # DIMENSIONS (for objects)
    # =========================================================================
    "dimension_x": ("dimensions", 0),
    "dimension_y": ("dimensions", 1),
    "dimension_z": ("dimensions", 2),
    "dim_x": ("dimensions", 0),
    "dim_y": ("dimensions", 1),
    "dim_z": ("dimensions", 2),
    "width": ("dimensions", 0),
    "length": ("dimensions", 1),
    "height": ("dimensions", 2),
    "derinlik": ("dimensions", 0),  # Turkish
    "genişlik": ("dimensions", 1),  # Turkish
    "yükseklik": ("dimensions", 2),  # Turkish
    "genislik": ("dimensions", 1),
    "yukseklik": ("dimensions", 2),
    # =========================================================================
    # COMPLETE TRANSFORMS (for batch operations)
    # =========================================================================
    "all_transforms": (None, -1),  # Special: all location, rotation, scale
    "all_loc": (None, -2),  # Special: all location axes
    "all_rot": (None, -3),  # Special: all rotation axes
    "all_scl": (None, -4),  # Special: all scale axes
    "transforms": (None, -1),
    "location": ("location", -1),
    # "rotation": ("rotation_euler", -1), # REMOVED DUPLICATE
    "rotation_euler": ("rotation_euler", -1),
    "scale": ("scale", -1),
    "konum": ("location", -1),  # Turkish
    "dönüş": ("rotation_euler", -1),
    "donus": ("rotation_euler", -1),
    "ölçek": ("scale", -1),
    "olcek": ("scale", -1),
    "boyut": ("scale", -1),
    "位置": ("location", -1),  # Chinese
    "旋转": ("rotation_euler", -1),
    "缩放": ("scale", -1),
}


# =============================================================================
# SPECIAL PROPERTY HANDLERS
# =============================================================================

SPECIAL_PROPERTIES: Dict[str, SpecialProperty] = {
    "all_transforms": {
        "description": "All transform properties (location, rotation, scale)",
        "paths": [("location", -1), ("rotation_euler", -1), ("scale", -1)],
    },
    "all_loc": {
        "description": "All location axes",
        "paths": [("location", 0), ("location", 1), ("location", 2)],
    },
    "all_rot": {
        "description": "All rotation axes",
        "paths": [("rotation_euler", 0), ("rotation_euler", 1), ("rotation_euler", 2)],
    },
    "all_scl": {
        "description": "All scale axes",
        "paths": [("scale", 0), ("scale", 1), ("scale", 2)],
    },
}


# =============================================================================
# PROPERTY RESOLVER CLASS
# =============================================================================


class PropertyResolver:
    """
    Resolves user-friendly property paths to Blender-compatible data paths.

    Supports:
    - Multi-language aliases
    - Array index notation (rotation_euler[2])
    - Dot notation (location.x)
    - Fuzzy matching fallback
    - Special batch properties
    """

    def __init__(self, fuzzy_threshold: float = 0.7):
        self.fuzzy_threshold = fuzzy_threshold
        self._alias_cache: Dict[str, Tuple[Optional[str], int]] = {}
        self._build_cache()

    def _build_cache(self) -> None:
        """Build lowercase cache for faster lookup."""
        for key, value in PROPERTY_ALIASES.items():
            self._alias_cache[key.lower()] = value

    def resolve(
        self, path: str, obj: Optional[Any] = None, allow_fuzzy: bool = True
    ) -> ResolveResult:
        """
        Resolve property path to Blender-compatible format.

        Args:
            path: Property path (e.g., "rotation_z", "location.x")
            obj: Optional object for validation
            allow_fuzzy: Whether to try fuzzy matching

        Returns:
            - Tuple (data_path, array_index) for single property
            - List of tuples for batch properties (all_transforms)
            - None if cannot resolve

        Examples:
            >>> resolver.resolve("rotation_z")
            ("rotation_euler", 2)

            >>> resolver.resolve("location.x")
            ("location", 0)

            >>> resolver.resolve("all_transforms")
            [("location", -1), ("rotation_euler", -1), ("scale", -1)]
        """
        if not path:
            return None

        path = path.strip()
        path_lower = path.lower()

        # 1. Direct alias match
        if path_lower in self._alias_cache:
            result = self._alias_cache[path_lower]
            base, index = result
            # Check if it's a special batch property
            if base is None and index < 0:
                special_key = {
                    -1: "all_transforms",
                    -2: "all_loc",
                    -3: "all_rot",
                    -4: "all_scl",
                }.get(index)
                if special_key and special_key in SPECIAL_PROPERTIES:
                    return SPECIAL_PROPERTIES[special_key]["paths"]
                return None
            if base is None:
                return None
            return (base, index)

        # 2. Parse array notation: rotation_euler[2]
        if "[" in path and "]" in path:
            try:
                base_path = path.split("[")[0].strip()
                index_str = path.split("[")[1].split("]")[0].strip()

                # Handle string indices
                if index_str.lower() in ["x", "r", "u"]:
                    index = 0
                elif index_str.lower() in ["y", "g", "v"]:
                    index = 1
                elif index_str.lower() in ["z", "b", "w"]:
                    index = 2
                else:
                    index = int(index_str)

                # Check if base path has alias
                if base_path.lower() in self._alias_cache:
                    aliased_base, _ = self._alias_cache[base_path.lower()]
                    if aliased_base:
                        base_path = aliased_base

                return (base_path, index)
            except (ValueError, IndexError):
                pass

        # 3. Parse dot notation: location.x
        if "." in path:
            parts = path.split(".")
            if len(parts) == 2:
                base_path, axis = parts
                base_lower = base_path.lower()
                axis_lower = axis.lower()

                # Map axis to index
                axis_map = {"x": 0, "r": 0, "u": 0, "y": 1, "g": 1, "v": 1, "z": 2, "b": 2, "w": 2}

                if axis_lower in axis_map:
                    index = axis_map[axis_lower]

                    # Check base path alias
                    full_path = f"{base_lower}_{axis_lower}"
                    if full_path in self._alias_cache:
                        cached_base, cached_index = self._alias_cache[full_path]
                        if cached_base is None:
                            return None
                        return (cached_base, cached_index)

                    # Try just the base path
                    if base_lower in self._alias_cache:
                        aliased_base, _ = self._alias_cache[base_lower]
                        if aliased_base:
                            return (aliased_base, index)

                    # Return as-is with index
                    return (base_path, index)

        # 4. Try to match with array index in alias
        # e.g., "rotation_euler_2" -> rotation_euler, 2
        for suffix in ["_0", "_1", "_2", "_x", "_y", "_z"]:
            if path_lower.endswith(suffix):
                base_part = path_lower[:-2]
                index_map = {"_0": 0, "_1": 1, "_2": 2, "_x": 0, "_y": 1, "_z": 2}

                if base_part in self._alias_cache:
                    aliased_base, _ = self._alias_cache[base_part]
                    if aliased_base:
                        return (aliased_base, index_map[suffix])

        # 5. Fuzzy matching fallback
        if allow_fuzzy:
            best_match = self._fuzzy_match(path_lower)
            if best_match:
                result = self._alias_cache[best_match]
                base, index = result
                if base is None and index < 0:
                    special_key = {
                        -1: "all_transforms",
                        -2: "all_loc",
                        -3: "all_rot",
                        -4: "all_scl",
                    }.get(index)
                    if special_key and special_key in SPECIAL_PROPERTIES:
                        return SPECIAL_PROPERTIES[special_key]["paths"]
                    return None
                if base is None:
                    return None
                return (base, index)

        # 6. Return as-is with index -1 (no array)
        return (path, -1)

    def _fuzzy_match(self, query: str) -> Optional[str]:
        """Find best fuzzy match for query."""
        best_match = None
        best_score = self.fuzzy_threshold

        for alias in self._alias_cache.keys():
            score = SequenceMatcher(None, query, alias).ratio()
            if score > best_score:
                best_score = score
                best_match = alias

        return best_match

    def resolve_for_keyframe(self, path: str, obj: Optional[Any] = None) -> ResolveResult:
        """
        Resolve path specifically for keyframe insertion.

        Returns paths suitable for obj.keyframe_insert(data_path=..., index=...)
        """
        result = self.resolve(path, obj)
        if result is None:
            return None
        return result

    def get_available_aliases(self, language: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get available aliases organized by property type.

        Args:
            language: Filter by language code (en, tr, fr, es, cn, de, jp, ru)
        """
        aliases: Dict[str, List[str]] = {
            "rotation": [],
            "location": [],
            "scale": [],
            "dimensions": [],
            "batch": [],
        }

        language_map = {
            "en": ["rotation_x", "rx", "location_x", "loc_x", "tx", "scale_x", "sx"],
            "tr": ["dönüş_x", "donus_x", "konum_x", "pozisyon_x", "ölçek_x", "olcek_x"],
            "fr": ["rotation", "position_x", "échelle_x", "echelle_x"],
            "es": ["rotación_x", "rotacion_x", "ubicación_x", "ubicacion_x", "escala_x"],
            "cn": ["旋转_x", "旋转x", "位置_x", "位置x", "缩放_x", "缩放x"],
            "de": ["drehung_x", "rotation", "position_x", "skalierung_x"],
            "jp": ["回転_x", "位置_x", "スケール_x"],
            "ru": ["вращение_x", "положение_x", "позиция_x", "масштаб_x"],
        }

        filter_list = language_map.get(language.lower(), []) if language else []

        for alias, (base, index) in PROPERTY_ALIASES.items():
            if language and alias not in filter_list:
                continue

            if base == "rotation_euler":
                aliases["rotation"].append(alias)
            elif base == "location":
                aliases["location"].append(alias)
            elif base == "scale":
                aliases["scale"].append(alias)
            elif base == "dimensions":
                aliases["dimensions"].append(alias)
            elif base is None:
                aliases["batch"].append(alias)

        return aliases

    def validate_path(self, path: str, obj: Optional[Any] = None) -> bool:
        """Validate if a property path is resolvable."""
        return self.resolve(path, obj, allow_fuzzy=False) is not None

    def suggest_corrections(self, path: str, top_n: int = 3) -> List[str]:
        """Suggest possible corrections for invalid path."""
        if not path:
            return []

        path_lower = path.lower()
        matches = []

        for alias in self._alias_cache.keys():
            score = SequenceMatcher(None, path_lower, alias).ratio()
            if score > 0.5:  # Lower threshold for suggestions
                matches.append((alias, score))

        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:top_n]]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def resolve_property_path(
    path: str, obj: Optional[Any] = None, allow_fuzzy: bool = True
) -> ResolveResult:
    """
    Convenience function to resolve property path.

    Examples:
        >>> resolve_property_path("rotation_z")
        ("rotation_euler", 2)

        >>> resolve_property_path("tx")
        ("location", 0)

        >>> resolve_property_path("位置_y")  # Chinese
        ("location", 1)
    """
    resolver = PropertyResolver()
    return resolver.resolve(path, obj, allow_fuzzy)


def get_property_friendly_name(data_path: str, index: int = -1) -> str:
    """
    Get user-friendly name for a property.

    Examples:
        >>> get_property_friendly_name("rotation_euler", 2)
        "rotation_z"

        >>> get_property_friendly_name("location", 0)
        "location_x / tx"
    """
    # Build reverse mapping
    reverse_map: Dict[Tuple[Optional[str], int], List[str]] = {}
    for alias, (base, idx) in PROPERTY_ALIASES.items():
        key = (base, idx)
        if key not in reverse_map:
            reverse_map[key] = []
        reverse_map[key].append(alias)

    # Look up
    key = (data_path, index)
    if key in reverse_map:
        return " / ".join(reverse_map[key][:3])  # Max 3 aliases

    # Build from components
    axis = ["x", "y", "z"][index] if 0 <= index <= 2 else ""
    return f"{data_path}.{axis}" if axis else data_path


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PropertyResolver",
    "resolve_property_path",
    "get_property_friendly_name",
    "PROPERTY_ALIASES",
    "SPECIAL_PROPERTIES",
]
