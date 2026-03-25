"""
Operator Safety Module for Blender MCP 1.0.0

Maps dangerous modal/UI-dependent operators to safe alternatives.
Automatically intercepts and redirects blocked operations.

High Mode Philosophy: No restrictions, just safer paths.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

try:
    import bpy
    import bmesh

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from .context_manager_v3 import ContextManagerV3, SafeModeContext

from .execution_engine import ExecutionEngine, ExecutionResult


@dataclass
class OperatorMapping:
    """
    Maps a dangerous operator to safe alternatives.

    Attributes:
        dangerous_op: The blocked operator path
        safe_alternative: Function to call instead
        description: Human-readable explanation
        parameters: Parameter mapping from dangerous to safe
    """

    dangerous_op: str
    safe_alternative: Callable
    description: str
    parameter_map: Optional[Dict[str, str]] = None


class OperatorSafety:
    """
        Central registry for operator safety mappings.

        This class provides automatic redirection of dangerous modal/UI operators
    to safe programmatic alternatives.
    """

    # Registry of operator mappings
    _mappings: Dict[str, OperatorMapping] = {}

    @classmethod
    def register(cls, dangerous_op: str, mapping: OperatorMapping) -> None:
        """Register an operator safety mapping."""
        cls._mappings[dangerous_op] = mapping

    @classmethod
    def get_mapping(cls, operator_path: str) -> Optional[OperatorMapping]:
        """Get safety mapping for an operator."""
        return cls._mappings.get(operator_path)

    @classmethod
    def has_safe_alternative(cls, operator_path: str) -> bool:
        """Check if operator has a safe alternative."""
        return operator_path in cls._mappings

    @classmethod
    def execute_safe_alternative(
        cls, operator_path: str, original_params: Dict[str, Any]
    ) -> ExecutionResult:
        """
        Execute safe alternative for a dangerous operator.

        Args:
            operator_path: The dangerous operator path
            original_params: Original parameters

        Returns:
            ExecutionResult from safe alternative
        """
        mapping = cls.get_mapping(operator_path)
        if not mapping:
            return ExecutionResult(
                success=False,
                error=f"No safe alternative for {operator_path}",
                error_code="NO_ALTERNATIVE",
            )

        # Map parameters if needed
        params = original_params.copy()
        if mapping.parameter_map:
            params = {mapping.parameter_map.get(k, k): v for k, v in params.items()}

        try:
            result = mapping.safe_alternative(**params)
            if isinstance(result, dict):
                return ExecutionResult(success=True, result=result)
            elif isinstance(result, ExecutionResult):
                return result
            else:
                return ExecutionResult(success=True, result=str(result))
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Safe alternative failed: {str(e)}",
                error_code="ALTERNATIVE_FAILED",
            )


# =============================================================================
# SAFE ALTERNATIVE IMPLEMENTATIONS
# =============================================================================


class SafeAlternatives:
    """
    Collection of safe alternatives to dangerous modal operators.
    All methods are static and return ExecutionResult or dict.
    """

    @staticmethod
    def loopcut_slide(cuts: int = 1, smoothness: float = 0.0, **kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to mesh.loopcut_slide (modal).
        Uses subdivide + edge slide for similar effect.

        Args:
            cuts: Number of cuts to make
            smoothness: Smoothness factor

        Returns:
            Result dict
        """
        if not BPY_AVAILABLE:
            return {"error": "bpy not available"}

        obj = ContextManagerV3.get_active_object()
        if not obj or obj.type != "MESH":
            return {"error": "No mesh object active"}

        with SafeModeContext("EDIT", obj) as success:
            if not success:
                return {"error": "Failed to enter edit mode"}

            try:
                # Get BMesh for safe editing
                me = obj.data
                bm = bmesh.from_edit_mesh(me)

                # Store selection
                selected_edges = [e for e in bm.edges if e.select]

                if not selected_edges:
                    return {
                        "success": False,
                        "error": "No edges selected for loop cut",
                        "suggestion": "Select edge ring first",
                    }

                # Use subdivide for simple edge cutting
                geom = selected_edges[:]
                bmesh.ops.subdivide_edges(bm, edges=geom, cuts=cuts, smooth=smoothness)

                # Update mesh
                bmesh.update_edit_mesh(me)

                return {
                    "success": True,
                    "operation": "SUBDIVIDE (loopcut alternative)",
                    "edges_cut": len(selected_edges),
                    "cuts": cuts,
                    "note": "Used safe subdivide instead of modal loopcut",
                }

            except Exception as e:
                return {"success": False, "error": f"Loopcut alternative failed: {str(e)}"}

        return {"error": "Failed to enter edit mode"}

    @staticmethod
    def knife_tool(cut_co: Optional[List] = None, **kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to mesh.knife_tool (modal).
        Uses bisect for planar cuts.

        Args:
            cut_co: Cut coordinates (not used, for API compatibility)

        Returns:
            Result dict
        """
        if not BPY_AVAILABLE:
            return {"error": "bpy not available"}

        return {
            "success": False,
            "error": "Knife tool requires interactive UI",
            "alternatives": [
                "Use 'mesh.bisect' for planar cuts",
                "Use boolean operations for complex cuts",
                "Use 'manage_modeling' with action='BOOLEAN_DIFFERENCE'",
            ],
        }

    @staticmethod
    def transform_translate(value: tuple = (0, 0, 0), **kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to transform.translate (modal).
        Directly manipulates object location.

        Args:
            value: Translation vector (x, y, z)

        Returns:
            Result dict
        """
        if not BPY_AVAILABLE:
            return {"error": "bpy not available"}

        obj = ContextManagerV3.get_active_object()
        if not obj:
            return {"error": "No active object"}

        try:
            obj.location.x += value[0]
            obj.location.y += value[1]
            obj.location.z += value[2]

            return {
                "success": True,
                "operation": "DIRECT_LOCATION_SET",
                "translation": value,
                "new_location": tuple(obj.location),
            }
        except Exception as e:
            return {"error": f"Translation failed: {str(e)}"}

    @staticmethod
    def transform_rotate(value: tuple = (0, 0, 0), **kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to transform.rotate (modal).
        Directly manipulates object rotation.

        Args:
            value: Rotation vector in radians (x, y, z)

        Returns:
            Result dict
        """
        if not BPY_AVAILABLE:
            return {"error": "bpy not available"}

        obj = ContextManagerV3.get_active_object()
        if not obj:
            return {"error": "No active object"}

        try:
            from mathutils import Euler

            # Add rotation to current
            current = obj.rotation_euler
            obj.rotation_euler = Euler(
                (current.x + value[0], current.y + value[1], current.z + value[2])
            )

            return {
                "success": True,
                "operation": "DIRECT_ROTATION_SET",
                "rotation": value,
                "new_rotation": tuple(obj.rotation_euler),
            }
        except Exception as e:
            return {"error": f"Rotation failed: {str(e)}"}

    @staticmethod
    def transform_resize(value: tuple = (1, 1, 1), **kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to transform.resize (modal).
        Directly manipulates object scale.

        Args:
            value: Scale vector (x, y, z)

        Returns:
            Result dict
        """
        if not BPY_AVAILABLE:
            return {"error": "bpy not available"}

        obj = ContextManagerV3.get_active_object()
        if not obj:
            return {"error": "No active object"}

        try:
            obj.scale.x *= value[0]
            obj.scale.y *= value[1]
            obj.scale.z *= value[2]

            return {
                "success": True,
                "operation": "DIRECT_SCALE_SET",
                "scale": value,
                "new_scale": tuple(obj.scale),
            }
        except Exception as e:
            return {"error": f"Scale failed: {str(e)}"}

    @staticmethod
    def view3d_render_border(**kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to view3d.render_border (modal).
        Sets render border via scene properties.

        Returns:
            Result dict
        """
        if not BPY_AVAILABLE:
            return {"error": "bpy not available"}

        scene = ContextManagerV3.get_scene()
        if not scene:
            return {"error": "No scene"}

        try:
            # Enable border render
            scene.render.use_border = True

            # Set border if provided
            if "xmin" in kwargs and "xmax" in kwargs and "ymin" in kwargs and "ymax" in kwargs:
                scene.render.border_min_x = kwargs["xmin"]
                scene.render.border_max_x = kwargs["xmax"]
                scene.render.border_min_y = kwargs["ymin"]
                scene.render.border_max_y = kwargs["ymax"]

            return {
                "success": True,
                "operation": "RENDER_BORDER_PROPERTY_SET",
                "border_enabled": True,
            }
        except Exception as e:
            return {"error": f"Render border failed: {str(e)}"}

    @staticmethod
    def paint_brush_stroke(stroke: Optional[List] = None, **kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to paint.brush_stroke (modal).
        Returns error with alternatives.

        Returns:
            Result dict with suggestions
        """
        return {
            "success": False,
            "error": "Brush stroke requires interactive UI input",
            "alternatives": [
                "Use direct vertex color assignment via mesh data",
                "Use image processing libraries for texture painting",
                "Use sculpting modifiers for displacement",
                "Paint in manual Blender UI session",
            ],
        }

    @staticmethod
    def wm_read_homefile(**kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to wm.read_homefile (crashes UI).
        Creates new scene data instead.

        Returns:
            Result dict
        """
        if not BPY_AVAILABLE:
            return {"error": "bpy not available"}

        try:
            # Create new scene instead of reloading
            new_scene = bpy.data.scenes.new(name="Scene")

            # Remove default objects
            for obj in list(new_scene.objects):
                bpy.data.objects.remove(obj, do_unlink=True)

            # Set as active
            if bpy.context.window:
                bpy.context.window.scene = new_scene

            return {
                "success": True,
                "operation": "NEW_SCENE_DATA",
                "note": "Created new scene data (wm.read_homefile is dangerous in socket mode)",
                "scene_name": new_scene.name,
            }
        except Exception as e:
            return {"error": f"New scene failed: {str(e)}"}

    @staticmethod
    def outliner_collection_new(name: str = "Collection", **kwargs: Any) -> Dict[str, Any]:
        """
        Safe alternative to outliner.collection_new (UI dependent).
        Uses bpy.data.collections directly.

        Args:
            name: Collection name

        Returns:
            Result dict
        """
        if not BPY_AVAILABLE:
            return {"error": "bpy not available"}

        try:
            coll = bpy.data.collections.new(name)
            scene = ContextManagerV3.get_scene()
            if scene:
                scene.collection.children.link(coll)

            return {
                "success": True,
                "operation": "COLLECTION_NEW_DIRECT",
                "collection_name": coll.name,
            }
        except Exception as e:
            return {"error": f"Collection creation failed: {str(e)}"}


# =============================================================================
# REGISTER DEFAULT MAPPINGS
# =============================================================================


def _register_default_mappings() -> None:
    """Register all default operator safety mappings."""

    OperatorSafety.register(
        "mesh.loopcut_slide",
        OperatorMapping(
            dangerous_op="mesh.loopcut_slide",
            safe_alternative=SafeAlternatives.loopcut_slide,
            description="Subdivide instead of modal loopcut",
        ),
    )

    OperatorSafety.register(
        "mesh.knife_tool",
        OperatorMapping(
            dangerous_op="mesh.knife_tool",
            safe_alternative=SafeAlternatives.knife_tool,
            description="Bisect or boolean for cuts",
        ),
    )

    OperatorSafety.register(
        "transform.translate",
        OperatorMapping(
            dangerous_op="transform.translate",
            safe_alternative=SafeAlternatives.transform_translate,
            description="Direct location manipulation",
        ),
    )

    OperatorSafety.register(
        "transform.rotate",
        OperatorMapping(
            dangerous_op="transform.rotate",
            safe_alternative=SafeAlternatives.transform_rotate,
            description="Direct rotation manipulation",
        ),
    )

    OperatorSafety.register(
        "transform.resize",
        OperatorMapping(
            dangerous_op="transform.resize",
            safe_alternative=SafeAlternatives.transform_resize,
            description="Direct scale manipulation",
        ),
    )

    OperatorSafety.register(
        "view3d.render_border",
        OperatorMapping(
            dangerous_op="view3d.render_border",
            safe_alternative=SafeAlternatives.view3d_render_border,
            description="Scene render properties",
        ),
    )

    OperatorSafety.register(
        "paint.brush_stroke",
        OperatorMapping(
            dangerous_op="paint.brush_stroke",
            safe_alternative=SafeAlternatives.paint_brush_stroke,
            description="Direct mesh data manipulation",
        ),
    )

    OperatorSafety.register(
        "wm.read_homefile",
        OperatorMapping(
            dangerous_op="wm.read_homefile",
            safe_alternative=SafeAlternatives.wm_read_homefile,
            description="Create new scene data",
        ),
    )

    OperatorSafety.register(
        "outliner.collection_new",
        OperatorMapping(
            dangerous_op="outliner.collection_new",
            safe_alternative=SafeAlternatives.outliner_collection_new,
            description="Direct collection creation",
        ),
    )


# Register on import
_register_default_mappings()


# =============================================================================
# SAFE OPERATOR EXECUTION
# =============================================================================


def safe_operator_execute(
    operator_path: str, params: Optional[Dict[str, Any]] = None, try_alternatives: bool = True
) -> ExecutionResult:
    """
    Execute operator with automatic safety redirection.

    This is the RECOMMENDED way to execute operators in handlers.

    Args:
        operator_path: e.g., "object.mode_set"
        params: Operator parameters
        try_alternatives: Use safe alternatives for dangerous ops

    Returns:
        ExecutionResult

    Examples:
        # Safe - will use alternative if needed
        result = safe_operator_execute("mesh.loopcut_slide", {"cuts": 2})

        # Force dangerous (not recommended)
        result = safe_operator_execute("mesh.loopcut_slide", try_alternatives=False)
    """
    params = params or {}

    # Check if dangerous and has alternative
    if try_alternatives and OperatorSafety.has_safe_alternative(operator_path):
        return OperatorSafety.execute_safe_alternative(operator_path, params)

    # Normal execution
    return ExecutionEngine.execute(operator_path, params)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "OperatorMapping",
    "OperatorSafety",
    "SafeAlternatives",
    "safe_operator_execute",
]
