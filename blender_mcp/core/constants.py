"""
Constants for Blender MCP Core - V1.0.0
Single Source of Truth for all fixed numeric/configuration values.

High Mode Philosophy: No magic numbers.
"""


class BakingDefaults:
    """Default values for baking operations."""

    DEFAULT_RESOLUTION = 1024
    MIN_RESOLUTION = 64
    MAX_RESOLUTION = 8192

    DEFAULT_SAMPLES = 128
    MIN_SAMPLES = 1
    MAX_SAMPLES = 10000

    DEFAULT_MARGIN = 16
    MIN_MARGIN = 0
    MAX_MARGIN = 128

    DEFAULT_CAGE_EXTRUSION = 0.1
    DEFAULT_AO_DISTANCE = 1.0


class BMeshDefaults:
    """Default values for BMesh operations."""

    DEFAULT_CUTS = 1
    DEFAULT_SMOOTHNESS = 0.0
    DEFAULT_FRACTAL = 0.0

    DEFAULT_EXTRUDE_OFFSET = 0.0

    DEFAULT_INSET_THICKNESS = 0.1
    DEFAULT_INSET_DEPTH = 0.0

    DEFAULT_BEVEL_OFFSET = 0.1
    DEFAULT_BEVEL_SEGMENTS = 2
    DEFAULT_BEVEL_PROFILE = 0.5

    DEFAULT_SMOOTH_FACTOR = 0.5
    DEFAULT_SMOOTH_ITERATIONS = 1

    DEFAULT_MERGE_DISTANCE = 0.0001


class ObjectDefaults:
    """Default values for Object operations."""

    DEFAULT_TIMEOUT = 10.0
    EXTENDED_TIMEOUT = 30.0


class CollectionDefaults:
    """Default values for Collection operations."""

    DEFAULT_HIERARCHY_DEPTH = 10


class RiggingDefaults:
    """Default values for Rigging operations."""

    DEFAULT_EXTRUSION_LENGTH = 1.0
    DEFAULT_POLE_ANGLE = 0.0


class SculptDefaults:
    """Default values for Sculpting operations."""

    DEFAULT_Detail_SIZE = 12
    MIN_DETAIL_SIZE = 1
    MAX_DETAIL_SIZE = 1000

    DEFAULT_STRENGTH = 0.5
    DEFAULT_RADIUS = 50
