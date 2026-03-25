"""
Sketchfab Integration Handler for Blender MCP 1.0.0
Sketchfab asset library integration for model search and download
"""

import os
import tempfile

import bpy

try:
    import requests  # type: ignore[import-untyped]
except ImportError:
    requests = None

from ..dispatcher import register_handler
from ..core.enums import SketchfabAction
from ..core.parameter_validator import validated_handler
from ..core.context_manager_v3 import ContextManagerV3
from ..core.execution_engine import safe_ops
from ..core.thread_safety import ensure_main_thread
from ..core.validation_utils import ValidationUtils
from ..core.types import SketchfabSearchResponse, SketchfabDownloadData
from typing import Dict, Any, Optional, cast


@register_handler(
    "integration_sketchfab",
    schema={
        "type": "object",
        "title": "Sketchfab Integration",
        "description": "Sketchfab 3D model library integration - search and import",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(SketchfabAction, "Operation to perform"),
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "default": 10, "description": "Number of results"},
            "uid": {"type": "string", "description": "Model UID for download/import"},
        },
        "required": ["action"],
    },
)
@validated_handler(actions=[a.value for a in SketchfabAction])
@ensure_main_thread
def integration_sketchfab(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Sketchfab asset library integration.

    Actions:
    - STATUS: Check integration status
    - SEARCH: Search for models
    - GET_DOWNLOAD_URL: Get download URL for a model
    - IMPORT: Download and import model
    """
    if not action:
        return {"error": "Missing required parameter: 'action'", "code": "MISSING_ACTION"}

    if action != SketchfabAction.STATUS.value and requests is None:
        return {
            "error": "Optional dependency 'requests' is not installed",
            "code": "DEPENDENCY_MISSING",
            "dependency": "requests",
        }

    if action == SketchfabAction.STATUS.value:
        return _get_status()

    if action == SketchfabAction.SEARCH.value:
        query = cast(str, params.get("query", ""))
        count = cast(int, params.get("count", 10))
        return _search(query, count)

    if action == SketchfabAction.GET_DOWNLOAD_URL.value:
        uid = cast(str, params.get("uid", ""))
        return _get_download_url(uid)

    if action == SketchfabAction.IMPORT.value:
        uid = cast(str, params.get("uid", ""))
        return _import_model(uid)

    return {"error": f"Unknown action: {action}", "code": "UNKNOWN_ACTION"}


def _get_status() -> Dict[str, Any]:
    """Get integration status."""
    api_key = cast(str, getattr(bpy.context.scene, "blendermcp_sketchfab_api_key", ""))
    return {
        "success": True,
        "enabled": bool(api_key),
        "authenticated": bool(api_key),
        "message": "Active" if api_key else "No API key configured",
    }


def _search(query: str, count: int = 10) -> Dict[str, Any]:
    """Search for models on Sketchfab."""
    if not query:
        return {"error": "Query required", "code": "MISSING_QUERY"}

    try:
        url = "https://api.sketchfab.com/v3/search"
        params = {"type": "models", "q": query, "count": count}
        api_key = getattr(bpy.context.scene, "blendermcp_sketchfab_api_key", "")
        headers = {"Authorization": f"Token {api_key}"} if api_key else {}

        if requests:
            resp = requests.get(url, params=params, headers=headers)  # type: ignore[arg-type]
            resp.raise_for_status()
            data = resp.json()
            if "results" not in data:
                return {
                    "success": True,
                    "data": {"results": []},
                }  # Graceful format mismatch handling
            return {"success": True, "data": cast(SketchfabSearchResponse, data)}
        return {"error": "Requests library not initialized", "code": "DEPENDENCY_ERROR"}
    except Exception as e:
        return {"error": str(e), "code": "SEARCH_ERROR"}


def _get_download_url(uid: str) -> Dict[str, Any]:
    """Get download URL for a model."""
    if not uid:
        return {"error": "UID required", "code": "MISSING_UID"}

    try:
        api_key = getattr(bpy.context.scene, "blendermcp_sketchfab_api_key", "")
        headers = {"Authorization": f"Token {api_key}"}
        url = f"https://api.sketchfab.com/v3/models/{uid}/download"
        if requests:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            # Basic structural validation
            if "gltf" not in data:
                return {
                    "error": "Invalid API response: missing 'gltf' key",
                    "code": "INVALID_API_RESPONSE",
                }
            return {"success": True, "data": cast(SketchfabDownloadData, data)}
        return {"error": "Requests library not initialized", "code": "DEPENDENCY_ERROR"}
    except Exception as e:
        return {"error": str(e), "code": "DOWNLOAD_ERROR"}


def _import_model(uid: str) -> Dict[str, Any]:
    """Download and import model from Sketchfab."""
    if not uid:
        return {"error": "UID required", "code": "MISSING_UID"}

    try:
        download_result = _get_download_url(uid)
        if "error" in download_result:
            return download_result

        # Type safe access
        data = cast(Dict[str, Any], download_result.get("data", {}))
        gltf_data = cast(Dict[str, Any], data.get("gltf", {}))
        gltf_url = gltf_data.get("url")

        if not gltf_url:
            return {"error": "No GLTF URL available", "code": "NO_GLTF_URL"}

        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, f"{uid}.glb")

        if requests:
            r = requests.get(gltf_url)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)

            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.import_scene.gltf(filepath=path)

            return {"success": True, "uid": uid, "message": "Model imported successfully"}
        return {"error": "Requests library not initialized", "code": "DEPENDENCY_ERROR"}
    except Exception as e:
        return {"error": str(e), "code": "IMPORT_ERROR"}
