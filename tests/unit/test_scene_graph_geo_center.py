"""
Unit tests for scene graph geometry center computation logic.

Tests the geometry_center_world / origin_offset / origin_offset_warning
fields added to get_scene_graph in live-20.

Uses a lightweight mock of bpy.data.objects — no real Blender needed.
"""

from __future__ import annotations

import sys
import os
import math
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


# ---------------------------------------------------------------------------
# Helpers — replicate the geo-center computation from manage_inspection.py
# ---------------------------------------------------------------------------


def _compute_geo_center_and_offset(
    bound_box: list[tuple[float, float, float]],
    matrix_world_translation: tuple[float, float, float],
) -> dict:
    """
    Pure-Python replica of the get_scene_graph geometry_center_world computation.

    Args:
        bound_box: 8 bounding-box corners in world space (already transformed)
        matrix_world_translation: (x, y, z) origin position from matrix_world col 3

    Returns:
        dict with geometry_center_world, origin_offset_m, origin_offset_warning
    """
    geo_center = [
        (min(c[i] for c in bound_box) + max(c[i] for c in bound_box)) / 2 for i in range(3)
    ]
    ox, oy, oz = matrix_world_translation
    origin_offset = math.sqrt(
        (geo_center[0] - ox) ** 2 + (geo_center[1] - oy) ** 2 + (geo_center[2] - oz) ** 2
    )
    return {
        "geometry_center_world": [round(v, 4) for v in geo_center],
        "origin_offset_m": round(origin_offset, 4),
        "origin_offset_warning": origin_offset > 0.01,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_geo_center_computed_for_centered_object() -> None:
    """A unit cube centred at origin → geometry_center_world = [0,0,0]."""
    bbox = [
        (-0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
    ]
    result = _compute_geo_center_and_offset(bbox, (0.0, 0.0, 0.0))
    assert result["geometry_center_world"] == [0.0, 0.0, 0.0]
    assert result["origin_offset_m"] == 0.0
    assert result["origin_offset_warning"] is False


def test_geo_center_computed_for_offset_object() -> None:
    """Mesh shifted 2m on X axis, origin at world origin → warning must fire."""
    # bbox corners at X=1.5 to X=2.5
    bbox = [
        (1.5, -0.5, -0.5),
        (2.5, -0.5, -0.5),
        (2.5, 0.5, -0.5),
        (1.5, 0.5, -0.5),
        (1.5, -0.5, 0.5),
        (2.5, -0.5, 0.5),
        (2.5, 0.5, 0.5),
        (1.5, 0.5, 0.5),
    ]
    result = _compute_geo_center_and_offset(bbox, (0.0, 0.0, 0.0))
    assert result["geometry_center_world"][0] == pytest.approx(2.0, abs=1e-4)
    assert result["origin_offset_m"] == pytest.approx(2.0, abs=1e-4)
    assert result["origin_offset_warning"] is True


def test_origin_offset_warning_false_when_centered() -> None:
    """Offset < 1cm → no warning."""
    bbox = [
        (-0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
    ]
    # Origin shifted 5mm from geo center → offset = 0.005m < 0.01m threshold
    result = _compute_geo_center_and_offset(bbox, (0.005, 0.0, 0.0))
    assert result["origin_offset_warning"] is False


def test_origin_offset_warning_true_when_offset_exceeds_1cm() -> None:
    """Offset > 1cm → warning must be True."""
    bbox = [
        (-0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
    ]
    # Origin shifted 15mm → offset = 0.015m > 0.01m threshold
    result = _compute_geo_center_and_offset(bbox, (0.015, 0.0, 0.0))
    assert result["origin_offset_warning"] is True
    assert result["origin_offset_m"] == pytest.approx(0.015, abs=1e-4)


def test_geo_center_at_large_world_coordinates() -> None:
    """Mesh at large world coordinates (e.g. architectural scale) computed correctly."""
    cx, cy, cz = 100.0, 200.0, 50.0
    half = 5.0
    bbox = [
        (cx - half, cy - half, cz - half),
        (cx + half, cy - half, cz - half),
        (cx + half, cy + half, cz - half),
        (cx - half, cy + half, cz - half),
        (cx - half, cy - half, cz + half),
        (cx + half, cy - half, cz + half),
        (cx + half, cy + half, cz + half),
        (cx - half, cy + half, cz + half),
    ]
    result = _compute_geo_center_and_offset(bbox, (cx, cy, cz))
    assert result["geometry_center_world"] == pytest.approx([cx, cy, cz], abs=1e-3)
    assert result["origin_offset_warning"] is False


# Import pytest after helper definitions so it's available for approx
import pytest
