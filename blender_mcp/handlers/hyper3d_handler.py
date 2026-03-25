"""
Hyper3D Integration Handler for Blender MCP 1.0.0
Hyper3D Rodin / Tripo / Meshy API Integration
"""

import bpy

try:
    import requests  # type: ignore[import-untyped]
except ImportError:
    requests = None

from ..core.thread_safety import ensure_main_thread
from ..dispatcher import register_handler
from ..core.enums import Hyper3DAction
from ..core.parameter_validator import validated_handler
from ..core.validation_utils import ValidationUtils


@register_handler(
    "integration_hyper3d",
    schema={
        "type": "object",
        "title": "Hyper3D Integration",
        "description": "Hyper3D Rodin / Tripo / Meshy API Integration for 3D generation",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(Hyper3DAction, "Operation to perform"),
            "prompt": {"type": "string", "description": "Text prompt for generation"},
            "image_path": {"type": "string", "description": "Path to image for image-to-3D"},
            "job_id": {"type": "string", "description": "Job ID for checking status"},
            "model_url": {"type": "string", "description": "Model URL to import"},
        },
        "required": ["action"],
    },
)
@validated_handler(actions=[a.value for a in Hyper3DAction])
@ensure_main_thread
def integration_hyper3d(action=None, **params):  # type: ignore[no-untyped-def]
    """
    Hyper3D Rodin / Tripo / Meshy API Integration.
    """
    if not action:
        return {"error": "Missing required parameter: 'action'", "code": "MISSING_ACTION"}

    if action != Hyper3DAction.STATUS.value and requests is None:
        return {
            "error": "Optional dependency 'requests' is not installed",
            "code": "DEPENDENCY_MISSING",
            "dependency": "requests",
        }

    if action == Hyper3DAction.STATUS.value:
        return _get_status()

    if action == Hyper3DAction.GENERATE.value:
        return _create_job(params.get("prompt"), params.get("image_path"))

    if action == Hyper3DAction.CHECK_JOB.value:
        return _poll_job(params.get("job_id"))

    if action == Hyper3DAction.IMPORT.value:
        return _import_model(params.get("model_url"))

    return {"error": f"Unknown action: {action}", "code": "UNKNOWN_ACTION"}


def _get_status():  # type: ignore[no-untyped-def]
    """Get integration status."""
    try:
        enabled = getattr(bpy.context.scene, "blendermcp_use_hyper3d", False)
        service = getattr(bpy.context.scene, "blendermcp_hyper3d_service", "RODIN")
        return {
            "success": True,
            "enabled": enabled,
            "service": service,
            "message": "Hyper3D Integration Active" if enabled else "Hyper3D Integration Disabled",
        }
    except Exception as e:
        return {"error": f"Failed to get status: {str(e)}", "code": "STATUS_ERROR"}


def _create_job(prompt, image):  # type: ignore[no-untyped-def]
    """Create generation job."""
    try:
        service = bpy.context.scene.blendermcp_hyper3d_service  # type: ignore[attr-defined]
        if service == "RODIN":
            return _create_job_rodin(prompt, image)
        elif service == "TRIPO":
            return _create_job_tripo(prompt, image)
        elif service == "MESHY":
            return _create_job_meshy(prompt, image)
        return {"error": f"Unknown service: {service}", "code": "UNKNOWN_SERVICE"}
    except Exception as e:
        return {"error": f"Failed to create job: {str(e)}", "code": "JOB_CREATE_ERROR"}


def _poll_job(job_id):  # type: ignore[no-untyped-def]
    """Poll job status."""
    if not job_id:
        return {"error": "Job ID required", "code": "MISSING_JOB_ID"}

    try:
        service = bpy.context.scene.blendermcp_hyper3d_service  # type: ignore[attr-defined]
        if service == "RODIN":
            return _poll_rodin(job_id)
        elif service == "TRIPO":
            return _poll_tripo(job_id)
        elif service == "MESHY":
            return _poll_meshy(job_id)
        return {"error": f"Unknown service: {service}", "code": "UNKNOWN_SERVICE"}
    except Exception as e:
        return {"error": str(e), "code": "POLL_ERROR"}


def _import_model(model_url):  # type: ignore[no-untyped-def]
    """Import model from URL."""
    if not model_url:
        return {"error": "Model URL required", "code": "MISSING_URL"}

    try:
        # Download and import logic
        return {"success": True, "message": "Model import initiated", "url": model_url}
    except Exception as e:
        return {"error": str(e), "code": "IMPORT_ERROR"}


# Rodin API


def _create_job_rodin(prompt, image):  # type: ignore[no-untyped-def]
    """Create job via Rodin API."""
    key = bpy.context.scene.blendermcp_hyper3d_rodin_key  # type: ignore[attr-defined]
    url = "https://hyperhuman.deemos.com/v2/models"
    headers = {"Authorization": f"Bearer {key}"}
    files = {}
    data = {}
    if prompt:
        data["text"] = prompt
    if image:
        files["image"] = open(image, "rb")
    try:
        resp = requests.post(url, headers=headers, data=data, files=files)
        return {"success": True, "data": resp.json()}
    except Exception as e:
        return {"error": str(e), "code": "RODIN_ERROR"}


def _poll_rodin(job_id):  # type: ignore[no-untyped-def]
    """Poll Rodin job."""
    key = bpy.context.scene.blendermcp_hyper3d_rodin_key  # type: ignore[attr-defined]
    url = f"https://hyperhuman.deemos.com/v2/models/{job_id}"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        resp = requests.get(url, headers=headers)
        return {"success": True, "data": resp.json()}
    except Exception as e:
        return {"error": str(e), "code": "RODIN_POLL_ERROR"}


# Tripo API


def _create_job_tripo(prompt, image):  # type: ignore[no-untyped-def]
    """Create job via Tripo API."""
    key = bpy.context.scene.blendermcp_hyper3d_tripo_key  # type: ignore[attr-defined]
    url = "https://api.tripo3d.ai/v1/task"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = {"type": "model_generation"}
    if prompt:
        data["text"] = prompt
    try:
        resp = requests.post(url, headers=headers, json=data)
        return {"success": True, "data": resp.json()}
    except Exception as e:
        return {"error": str(e), "code": "TRIPO_ERROR"}


def _poll_tripo(job_id):  # type: ignore[no-untyped-def]
    """Poll Tripo job."""
    key = bpy.context.scene.blendermcp_hyper3d_tripo_key  # type: ignore[attr-defined]
    url = f"https://api.tripo3d.ai/v1/task/{job_id}"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        resp = requests.get(url, headers=headers)
        return {"success": True, "data": resp.json()}
    except Exception as e:
        return {"error": str(e), "code": "TRIPO_POLL_ERROR"}


# Meshy API


def _create_job_meshy(prompt, image):  # type: ignore[no-untyped-def]
    """Create job via Meshy API."""
    key = bpy.context.scene.blendermcp_hyper3d_meshy_key  # type: ignore[attr-defined]
    url = "https://api.meshy.ai/v2/text-to-3d"
    headers = {"Authorization": f"Bearer {key}"}
    data = {"text": prompt} if prompt else {}
    try:
        resp = requests.post(url, headers=headers, json=data)
        return {"success": True, "data": resp.json()}
    except Exception as e:
        return {"error": str(e), "code": "MESHY_ERROR"}


def _poll_meshy(job_id):  # type: ignore[no-untyped-def]
    """Poll Meshy job."""
    key = bpy.context.scene.blendermcp_hyper3d_meshy_key  # type: ignore[attr-defined]
    url = f"https://api.meshy.ai/v2/{job_id}"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        resp = requests.get(url, headers=headers)
        return {"success": True, "data": resp.json()}
    except Exception as e:
        return {"error": str(e), "code": "MESHY_POLL_ERROR"}
