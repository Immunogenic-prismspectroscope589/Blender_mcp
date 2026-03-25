"""
Poly Haven Integration Handler for Blender MCP 1.0.0 Refactored (SSOT)

Attributes:
    - Implements PolyHavenAction Enum (SSOT)
    - Robust validation with ValidationUtils
    - Replaces legacy @validated_handler decorator
"""

import os
import tempfile

try:
    import requests  # type: ignore[import-untyped]
except ImportError:
    requests = None

from typing import Optional, Dict, Any

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..dispatcher import register_handler
from ..core.context_manager_v3 import ContextManagerV3
from ..core.thread_safety import ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.response_builder import ResponseBuilder

# SSOT Imports
from ..core.enums import PolyHavenAction
from ..core.validation_utils import ValidationUtils


@register_handler(
    "integration_polyhaven",
    actions=[a.value for a in PolyHavenAction],
    schema={
        "type": "object",
        "title": "Poly Haven (HDRI/Assets) Integration",
        "description": "Access HDRI environments, 3D models, and materials from Poly Haven",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(PolyHavenAction, "Operation to perform"),
            "query": {"type": "string", "description": "Search query"},
            "asset_type": {
                "type": "string",
                "enum": ["hdris", "models", "textures"],
                "description": "Asset type for search",
            },
            "asset_id": {"type": "string", "description": "Asset ID to import"},
            "resolution": {
                "type": "string",
                "enum": ["1k", "2k", "4k", "8k"],
                "default": "4k",
                "description": "Texture resolution",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def integration_polyhaven(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Poly Haven asset library integration.
    """
    if not action:
        # Fallback
        action = params.get("action")

    if not action:
        return ResponseBuilder.error(
            handler="integration_polyhaven",
            action=None,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action != PolyHavenAction.STATUS.value and requests is None:
        return ResponseBuilder.error(
            handler="integration_polyhaven",
            action=action,
            error_code="DEPENDENCY_MISSING",
            message="Optional dependency 'requests' is not installed",
        )

    # Validate Action Enum
    validation_error = ValidationUtils.validate_enum(action, PolyHavenAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(
            validation_error, handler="integration_polyhaven", action=action
        )

    try:
        if action == PolyHavenAction.STATUS.value:
            return _get_status()

        elif action == PolyHavenAction.SEARCH.value:
            return _search(params.get("query"), params.get("asset_type", "hdris"))

        elif action == PolyHavenAction.IMPORT_HDRI.value:
            return _import_hdri(
                str(params.get("asset_id", "")), str(params.get("resolution", "4k"))
            )

        elif action == PolyHavenAction.IMPORT_MODEL.value:
            return _import_model(str(params.get("asset_id", "")))

        elif action == PolyHavenAction.IMPORT_MATERIAL.value:
            return _import_material(
                str(params.get("asset_id", "")), str(params.get("resolution", "4k"))
            )

        else:
            return ResponseBuilder.error(
                handler="integration_polyhaven",
                action=action,
                error_code="INVALID_ACTION",
                message=f"Unknown action: {action}",
            )

    except Exception as e:
        return ResponseBuilder.error(
            handler="integration_polyhaven",
            action=action,
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _get_status() -> Dict[str, Any]:
    """Get integration status."""
    try:
        enabled = getattr(bpy.context.scene, "blendermcp_use_polyhaven", True)
        return {"success": True, "enabled": enabled, "message": "Poly Haven Integration Active"}
    except Exception as e:
        return {"error": f"Failed to get status: {str(e)}", "code": "STATUS_ERROR"}


def _search(query: Optional[str], asset_type: str = "hdris") -> Dict[str, Any]:
    """Search for assets on Poly Haven."""
    url = "https://api.polyhaven.com/assets"
    try:
        params = {"t": asset_type}
        if query:
            params["q"] = query
        resp = requests.get(url, params=params)
        data = resp.json()

        # Filter by query if provided
        if query:
            results = [a for a in data.values() if query.lower() in a.get("name", "").lower()]
        else:
            results = list(data.values())

        # Limit results? Not specified, but let's limit to 20 to avoid huge payload
        return {"success": True, "count": len(results), "results": results[:20]}
    except Exception as e:
        return {"error": str(e), "code": "SEARCH_ERROR"}


def _import_hdri(asset_id: str, resolution: str = "4k") -> Dict[str, Any]:
    """
    Download and setup HDRI from Poly Haven
    """
    if not asset_id:
        return {"error": "Asset ID required", "code": "MISSING_ASSET_ID"}

    try:
        asset_info_url = f"https://api.polyhaven.com/files/{asset_id}"
        resp = requests.get(asset_info_url)
        data = resp.json()

        files = data.get("hdri", {}).get(f"hdri_{resolution}", {})
        if not files:
            return {
                "error": f"HDRI {asset_id} not found at resolution {resolution}",
                "code": "ASSET_NOT_FOUND",
            }

        url = files.get("hdr", {}).get("url")
        if not url:
            return {"error": "No HDR file available", "code": "NO_HDR_AVAILABLE"}

        world = bpy.data.worlds.new(name=asset_id)
        world.use_nodes = True
        nodes = world.node_tree.nodes
        nodes.clear()

        env = nodes.new("ShaderNodeTexEnvironment")
        output = nodes.new("ShaderNodeOutputWorld")
        world.node_tree.links.new(env.outputs[0], output.inputs[0])

        # Download
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, f"{asset_id}.hdr")
        r = requests.get(url)
        with open(path, "wb") as f:
            f.write(r.content)

        # Load
        image = bpy.data.images.load(path)
        env.image = image  # type: ignore[attr-defined, unused-ignore]

        bpy.context.scene.world = world

        return {"success": True, "asset_id": asset_id, "world_name": world.name}

    except Exception as e:
        return {"error": str(e), "code": "IMPORT_ERROR"}


def _import_model(asset_id: str) -> Dict[str, Any]:
    """
    Download and import 3D model from Poly Haven
    """
    if not asset_id:
        return {"error": "Asset ID required", "code": "MISSING_ASSET_ID"}

    try:
        asset_info_url = f"https://api.polyhaven.com/files/{asset_id}"
        resp = requests.get(asset_info_url)
        data = resp.json()

        files = data.get("3d", {})
        gltf = files.get("gltf", {}).get("glb", {}).get("url")
        if not gltf:
            return {"error": "No GLTF file available", "code": "NO_GLTF_AVAILABLE"}

        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, f"{asset_id}.glb")
        r = requests.get(gltf)
        with open(path, "wb") as f:
            f.write(r.content)

        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.import_scene.gltf(filepath=path)

        return {"success": True, "asset_id": asset_id}

    except Exception as e:
        return {"error": str(e), "code": "IMPORT_ERROR"}


def _import_material(asset_id: str, resolution: str = "4k") -> Dict[str, Any]:
    """
    Download and create material from Poly Haven
    """
    if not asset_id:
        return {"error": "Asset ID required", "code": "MISSING_ASSET_ID"}

    try:
        asset_info_url = f"https://api.polyhaven.com/files/{asset_id}"
        resp = requests.get(asset_info_url)
        data = resp.json()

        maps = data.get("blend", {}).get(resolution, {})
        if not maps:
            maps = data.get("texture", {}).get(resolution, {})

        temp_dir = tempfile.mkdtemp()

        # Download textures
        textures = {}
        for map_type, info in maps.items():
            url = info.get("url")
            ext = info.get("ext", "jpg")
            path = os.path.join(temp_dir, f"{asset_id}_{map_type}.{ext}")
            r = requests.get(url)
            with open(path, "wb") as f:
                f.write(r.content)
            textures[map_type] = path

        # Create material
        mat = bpy.data.materials.new(name=asset_id)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if not bsdf:
            # Fix possible case where Principled BSDF is missing or renamed
            bsdf = nodes.new("ShaderNodeBsdfPrincipled")

        # Setup texture nodes
        for map_type, path in textures.items():
            img = bpy.data.images.load(path)
            tex = nodes.new("ShaderNodeTexImage")
            tex.image = img  # type: ignore[attr-defined, unused-ignore]

            # Simple connection logic - could be improved but sufficient for now
            if map_type in ["diff", "albedo", "diffuse"]:
                mat.node_tree.links.new(tex.outputs[0], bsdf.inputs["Base Color"])
            elif map_type in ["nor", "normal", "nor_gl", "nor_dx"]:
                tex.image.colorspace_settings.name = "Non-Color"  # type: ignore[attr-defined, unused-ignore]
                normal = nodes.new("ShaderNodeNormalMap")
                mat.node_tree.links.new(tex.outputs[0], normal.inputs[1])
                mat.node_tree.links.new(normal.outputs[0], bsdf.inputs["Normal"])
            elif map_type in ["rough", "roughness"]:
                tex.image.colorspace_settings.name = "Non-Color"  # type: ignore[attr-defined, unused-ignore]
                mat.node_tree.links.new(tex.outputs[0], bsdf.inputs["Roughness"])
            elif map_type in ["metal", "metallic"]:
                tex.image.colorspace_settings.name = "Non-Color"  # type: ignore[attr-defined, unused-ignore]
                mat.node_tree.links.new(tex.outputs[0], bsdf.inputs["Metallic"])
            elif map_type in ["disp", "displacement"]:
                tex.image.colorspace_settings.name = "Non-Color"  # type: ignore[attr-defined, unused-ignore]
                # Connect displacement...
                disp = nodes.new("ShaderNodeDisplacement")
                mat.node_tree.links.new(tex.outputs[0], disp.inputs["Height"])
                output = nodes.get("Material Output")
                if output:
                    mat.node_tree.links.new(
                        disp.outputs["Displacement"], output.inputs["Displacement"]
                    )

        return {"success": True, "asset_id": asset_id, "material_name": mat.name}

    except Exception as e:
        return {"error": str(e), "code": "IMPORT_ERROR"}
