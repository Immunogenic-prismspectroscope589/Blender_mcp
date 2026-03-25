"""
Asset Management Utility for Blender 5.0+ Compatbility.
Centralizes logic for loading assets from the 'Essentials' library and other sources.

Strict adherence to Blender 5.0 API changes:
- Using `bpy.ops.brush.asset_activate` with correct relative paths.
- Handling the shift from `bpy.data.brushes` pre-loading to on-demand asset loading.
"""

from typing import Optional, Any

try:
    import bpy
    from bpy.types import Brush

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    Brush = Any  # type: ignore[assignment, misc]

# Logger
from ..core.logging_config import get_logger

logger = get_logger()


class AssetLoader:
    """
    Single Source of Truth (SSOT) for Blender Asset interaction.
    Handles version-specific differences and path normalization.
    """

    # Constants for Blender 5.0 Essentials Library
    ASSET_LIB_TYPE = "ESSENTIALS"
    SCULPT_FILE = "essentials_brushes-mesh_sculpt.blend"

    # Mapping of common brush names to their canonical asset names if different
    # Most match, but this allows fixing specific discrepancies
    BRUSH_NAME_MAP = {
        "User Scrape": "Scrape",  # Example mapping if needed
    }

    @classmethod
    def get_sculpt_brush(cls, brush_name: str) -> Optional[Brush]:
        """
        Retrieves a sculpt brush, activating it from assets if necessary.

        Args:
            brush_name: The name of the brush (e.g., "Clay Strips")

        Returns:
            bpy.types.Brush object or None if not found/activatable.
        """
        if not BPY_AVAILABLE:
            logger.warning("BPY not available, cannot load assets.")
            return None

        # 1. Check Local Data (Fast Path)
        # ----------------------------------------------------------------
        # First, try exact match
        if brush_name in bpy.data.brushes:
            return bpy.data.brushes[brush_name]  # type: ignore[no-any-return]

        # Try case-insensitive match
        brush_lower = brush_name.lower()
        for b in bpy.data.brushes:
            if b.name.lower() == brush_lower:
                return b  # type: ignore[no-any-return]
            # The following line was requested to be restored, but it is syntactically incorrect
            # and refers to undefined variables (`pattern`, `request_lower`) in this context.
            # It has been commented out to maintain a syntactically correct file.
            # elif pattern.lower() in request_lower:  # type: ignore[unreachable]
            #     return b

        # 2. Activate from Essentials (Blender 5.0+ Path)
        # ----------------------------------------------------------------
        # Only relevant if we are in a version that supports asset activation
        if hasattr(bpy.ops, "brush") and hasattr(bpy.ops.brush, "asset_activate"):
            return cls._activate_from_essentials(brush_name)

        logger.warning(f"Brush '{brush_name}' not found locally and asset system unavailable.")
        return None

    @classmethod
    def _activate_from_essentials(cls, brush_name: str) -> Optional[Brush]:
        """
        Attempts to activate a brush from the built-in Essentials library.
        """
        # Resolve canonical name
        canonical_name = cls.BRUSH_NAME_MAP.get(brush_name, brush_name)

        # Construct relative path for Blender 5.0 structure
        # specific to 'essentials_brushes-mesh_sculpt.blend'
        # Format: brushes/essentials_brushes-mesh_sculpt.blend/Brush/<Name>
        relative_path = f"brushes/{cls.SCULPT_FILE}/Brush/{canonical_name}"

        logger.info(f"Attempting to activate asset: {relative_path}")

        try:
            # Execute activation operator
            # Note: asset_library_identifier is empty for ESSENTIALS/ALL
            # Note: The ignore below is for the attr-defined (likely)
            bpy.ops.brush.asset_activate(  # type: ignore[attr-defined]
                asset_library_type=cls.ASSET_LIB_TYPE,
                asset_library_identifier="",
                relative_asset_identifier=relative_path,
            )

            # 3. Validation: Verify it was loaded
            # ----------------------------------------------------------------
            # After activation, it should appear in bpy.data.brushes
            # The name might be "Clay Strips" or "Clay Strips.001" if conflict
            # We look for exact match first, then checks

            if canonical_name in bpy.data.brushes:
                logger.info(f"Successfully activated '{canonical_name}' from Essentials.")
                return bpy.data.brushes[canonical_name]  # type: ignore[no-any-return]

            # Fallback: Search for name in keys again
            for b in bpy.data.brushes:
                if b.name.startswith(canonical_name):  # Loose check for .001
                    return b  # type: ignore[no-any-return]

            logger.error(f"Asset '{canonical_name}' activated but not found in bpy.data.brushes.")
            return None

        except RuntimeError as e:
            # Operator fails if asset is not found
            logger.warning(f"Failed to activate brush '{canonical_name}' from assets: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error activating asset '{canonical_name}': {e}")
            return None
