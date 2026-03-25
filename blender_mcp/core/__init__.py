"""
Blender MCP Core Module - V1.0.0 "High Mode Ultra"

Central exports for all core functionality.

Usage:
    from blender_mcp.core import ErrorProtocol, create_error
    from blender_mcp.core import SmartModeManager
    from blender_mcp.core import BlenderCompatibility
    from blender_mcp.core import PropertyResolver, FuzzyMatcher, ContextManagerV3
"""

# Error Handling
from .error_protocol import (
    ErrorProtocol,
    ErrorCode,
    MCPError,
    create_error,
)

# Validation Utilities
from .validation_utils import ValidationUtils

# Mode Management
from .smart_mode_manager import (
    SmartModeManager,
    ModeValidator,
    SculptModeManager,
    requires_mode,
)

# API Compatibility
from .versioning import BlenderCompatibility

# Thread Safety
from .thread_safety import (
    execute_on_main_thread,
    SafeOperators,
)

# Context Management


# Context Management V3 (NEW in 1.0.0)
from .context_manager_v3 import (
    ContextManagerV3,
    with_context,
    with_mode,
    ensure_context,
    get_safe_context,
)

# Property Resolution (NEW in 1.0.0)
from .property_resolver import (
    PropertyResolver,
    resolve_property_path,
    get_property_friendly_name,
    PROPERTY_ALIASES,
    SPECIAL_PROPERTIES,
)

# Fuzzy Matching (NEW in 1.0.0)
from .fuzzy_matcher import (
    FuzzyMatcher,
    MultiFieldMatcher,
    SmartNameResolver,
    fuzzy_match,
    find_best_match,
    resolve_name,
)

# Tool Discovery (NEW in 1.0.0)
from .tool_discovery import (
    ToolCatalog,
    ToolInfo,
    ActionInfo,
    ActionDiscovery,
    SchemaGenerator,
    ExampleGenerator,
    MultiLanguageResolver,
    get_tool_catalog,
    search_tools,
    get_action_help,
    resolve_tool_alias,
    resolve_action_alias,
)

# Blender 5.0 Advanced Features (NEW in 1.0.0)
from .blender50_features import (
    ActionSlotManager,
    GeometryNodesAdvanced,
    ViewLayerOverrideManager,
)

# BMesh Operations (NEW in 1.0.0)
from .bmesh_operations import (
    BMeshOperations,
    BMeshTopologyAnalysis,
    BMeshUVOperations,
    bmesh_from_object,
)

# Advanced Animation (NEW in 1.0.0)
from .animation_advanced import (
    NLAManager,
    FCurveModifierManager,
    KeyframeManager,
    DriverManager,
    AnimationBaker,
    InterpolationType,
    EasingType,
)

# Advanced Geometry Nodes (NEW in 1.0.0)
from .geometry_nodes_advanced import (
    SimulationZoneBuilder,
    BundleManager,
    ClosureManager,
    ProceduralAssetBuilder,
    ZoneNodeBuilder,
    GeometryNodeType,
)

# Eevee Next Render (NEW in 1.0.0)
from .render_eevee_next import (
    EeveeNextManager,
    ViewLayerManager,
    RenderPassManager,
    EeveeNextQualityPreset,
    RaytracingQualityPreset,
    EeveeNextSettings,
)

# Compositor Modifier (NEW in 1.0.0)
from .compositor_modifier import (
    CompositorModifierManager,
    VSECompositorManager,
    RealTimeEffectManager,
    CompositorEffectType,
    GlareType,
)

# Headless Mode (NEW in 1.0.0)
from .headless_mode import (
    HeadlessModeManager,
    MemoryManager,
    CI_CDManager,
    HeadlessMode,
    headless_context,
)

# Export Pipeline (NEW in 1.0.0)
from .export_pipeline import (
    GLTFExporter,
    USDExporter,
    AlembicExporter,
    FBXExporter,
    BatchExporter,
    ExportValidator,
    ExportFormat,
    ExportSettings,
)

# Parameter Validation
from .parameter_validator import (
    ParameterValidator,
    validated_handler,
)

# Universal Coercion
from .universal_coercion import TypeCoercer

# Logging
from .logging_config import get_logger

# Resolver
from .resolver import resolve_name as resolve_object_name

__all__ = [
    # Error Handling
    "ErrorProtocol",
    "ErrorCode",
    "MCPError",
    "create_error",
    # Validation Utilities
    "ValidationUtils",
    # Mode Management
    "SmartModeManager",
    "ModeValidator",
    "SculptModeManager",
    "requires_mode",
    # API Compatibility
    "BlenderCompatibility",
    # Thread Safety
    "execute_on_main_thread",
    "SafeOperators",
    # Context Management
    "ContextManagerV3",
    "with_context",
    "with_mode",
    "ensure_context",
    "get_safe_context",
    # Property Resolution (NEW 1.0.0)
    "PropertyResolver",
    "resolve_property_path",
    "get_property_friendly_name",
    "PROPERTY_ALIASES",
    "SPECIAL_PROPERTIES",
    # Fuzzy Matching (NEW 1.0.0)
    "FuzzyMatcher",
    "MultiFieldMatcher",
    "SmartNameResolver",
    "fuzzy_match",
    "find_best_match",
    "resolve_name",
    # Validation
    "ParameterValidator",
    "validated_handler",
    # Coercion
    "TypeCoercer",
    # Logging
    "get_logger",
    # Resolver
    "resolve_object_name",
    # Tool Discovery (NEW 1.0.0)
    "ToolCatalog",
    "ToolInfo",
    "ActionInfo",
    "ActionDiscovery",
    "SchemaGenerator",
    "ExampleGenerator",
    "MultiLanguageResolver",
    "get_tool_catalog",
    "search_tools",
    "get_action_help",
    "resolve_tool_alias",
    "resolve_action_alias",
    # Blender 5.0 Features (NEW 1.0.0)
    "ActionSlotManager",
    "GeometryNodesAdvanced",
    "CompositorModifierManager",
    "EeveeNextManager",
    "ViewLayerOverrideManager",
    "HeadlessModeManager",
    # BMesh (NEW 1.0.0)
    "BMeshOperations",
    "BMeshTopologyAnalysis",
    "BMeshUVOperations",
    "bmesh_from_object",
    # Animation Advanced (NEW 1.0.0)
    "NLAManager",
    "FCurveModifierManager",
    "KeyframeManager",
    "DriverManager",
    "AnimationBaker",
    "InterpolationType",
    "EasingType",
    # Geometry Nodes Advanced (NEW 1.0.0)
    "SimulationZoneBuilder",
    "BundleManager",
    "ClosureManager",
    "ProceduralAssetBuilder",
    "ZoneNodeBuilder",
    "GeometryNodeType",
    # Eevee Next (NEW 1.0.0)
    "ViewLayerManager",
    "RenderPassManager",
    "EeveeNextQualityPreset",
    "RaytracingQualityPreset",
    "EeveeNextSettings",
    # Compositor Modifier (NEW 1.0.0)
    "CompositorModifierManager",
    "VSECompositorManager",
    "RealTimeEffectManager",
    "CompositorEffectType",
    "GlareType",
    # Headless Mode (NEW 1.0.0)
    "MemoryManager",
    "CI_CDManager",
    "HeadlessMode",
    "headless_context",
    # Export Pipeline (NEW 1.0.0)
    "GLTFExporter",
    "USDExporter",
    "AlembicExporter",
    "FBXExporter",
    "BatchExporter",
    "ExportValidator",
    "ExportFormat",
    "ExportSettings",
]
