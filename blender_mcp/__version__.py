"""
Version Information - Single Source of Truth
Blender MCP for Unity Integration
"""

# Standard Python version attributes
__version__ = "1.0.0"
__version_info__ = (1, 0, 0)

# Aliases for compatibility with sync_version.py
VERSION = __version__
VERSION_TUPLE = __version_info__

# Extended version info
VERSION_NAME = "High Mode Vision - Deterministic Outputs & Semantic Memory"
VERSION_DATE = "2026-02-10"
VERSION_FEATURES = [
    "ResponseBuilder - Deterministic output standardization",
    "Validation-First Workflow - VALIDATE/PREVIEW/COMMIT pattern",
    "Semantic Scene Memory - Tag-based object resolution",
    "Intent-Based Animation - Style/emotion-driven F-curve generation",
    "Complete Error Protocol Standardization - 280+ errors standardized",
    "SmartModeManager - Safe mode transitions with validation",
    "Thread Safety Infrastructure - Main thread execution",
    "42+ Handlers with 920+ Actions",
    "95%+ Tool Success Rate Target",
]


def get_version_string():
    """Return full version string with name."""
    return f"Blender MCP v{__version__} - {VERSION_NAME} ({VERSION_DATE})"


def get_feature_summary():
    """Return feature summary."""
    return {
        "version": __version__,
        "name": VERSION_NAME,
        "date": VERSION_DATE,
        "features": VERSION_FEATURES,
        "handlers": 58,
        "actions": "280+",
    }
