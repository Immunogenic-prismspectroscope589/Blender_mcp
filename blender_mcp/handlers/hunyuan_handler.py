"""
Hunyuan3D Integration Handler for Blender MCP 1.0.0
Tencent Hunyuan 3D Generation (Text/Image to 3D)
"""

import base64
import datetime
import hashlib
import hmac
import json
import os
import os.path as osp
import tempfile
import time
import zipfile

from typing import Dict, Any
import bpy
from ..core.thread_safety import ensure_main_thread
from ..core.execution_engine import safe_ops

try:
    import requests  # type: ignore[import-untyped]
except ImportError:
    requests = None

from ..dispatcher import register_handler
from ..core.enums import HunyuanAction
from ..core.parameter_validator import validated_handler
from ..core.context_manager_v3 import ContextManagerV3
from ..core.validation_utils import ValidationUtils


@register_handler(
    "integration_hunyuan",
    schema={
        "type": "object",
        "title": "Hunyuan3D Integration",
        "description": "Tencent Hunyuan 3D Generation (Text/Image to 3D).",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(HunyuanAction, "Operation to perform."),
            "prompt": {"type": "string", "description": "Text prompt for generation."},
            "image_path": {
                "type": "string",
                "description": "Local path or URL to image.",
            },
            "job_id": {"type": "string", "description": "Job ID for checking status."},
            "zip_url": {
                "type": "string",
                "description": "URL of ZIP file to import (for IMPORT action).",
            },
        },
        "required": ["action"],
    },
)
@validated_handler(actions=[a.value for a in HunyuanAction])
@ensure_main_thread
def integration_hunyuan(action=None, **params):  # type: ignore[no-untyped-def]
    """
    Unified Hunyuan3D Integration.
    Supported by both Official API and Local deployments.
    """
    if not action:
        return {"error": "Missing required parameter: 'action'", "code": "MISSING_ACTION"}

    if action != HunyuanAction.STATUS.value and requests is None:
        return {
            "error": "Optional dependency 'requests' is not installed",
            "code": "DEPENDENCY_MISSING",
            "dependency": "requests",
        }

    if action == HunyuanAction.STATUS.value:
        return _get_status()

    if action == HunyuanAction.GENERATE.value:
        return _create_job(params.get("prompt"), params.get("image_path"))

    if action == HunyuanAction.CHECK_JOB.value:
        return _poll_job(params.get("job_id"))

    if action == HunyuanAction.IMPORT.value:
        return _import_asset(params.get("zip_url"))

    return {"error": f"Unknown action: {action}", "code": "UNKNOWN_ACTION"}


def _get_status():  # type: ignore[no-untyped-def]
    """Get integration status."""
    try:
        enabled = getattr(bpy.context.scene, "blendermcp_use_hunyuan3d", False)
        mode = getattr(bpy.context.scene, "blendermcp_hunyuan3d_mode", "OFFICIAL_API")
        return {
            "success": True,
            "enabled": enabled,
            "mode": mode,
            "message": "Hunyuan Integration Active" if enabled else "Hunyuan Integration Disabled",
        }
    except Exception as e:
        return {"error": f"Failed to get status: {str(e)}", "code": "STATUS_ERROR"}


def _create_job(text_prompt, image):  # type: ignore[no-untyped-def]
    """Create generation job."""
    try:
        mode = bpy.context.scene.blendermcp_hunyuan3d_mode  # type: ignore[attr-defined]
        if mode == "OFFICIAL_API":
            return _create_job_official(text_prompt, image)
        elif mode == "LOCAL_API":
            return _create_job_local(text_prompt, image)
        return {"error": "Unknown mode", "code": "UNKNOWN_MODE"}
    except Exception as e:
        return {"error": f"Failed to create job: {str(e)}", "code": "JOB_CREATE_ERROR"}


def _poll_job(job_id):  # type: ignore[no-untyped-def]
    """Poll job status."""
    if not job_id:
        return {"error": "Job ID required", "code": "MISSING_JOB_ID"}

    try:
        secret_id = bpy.context.scene.blendermcp_hunyuan3d_secret_id  # type: ignore[attr-defined]
        secret_key = bpy.context.scene.blendermcp_hunyuan3d_secret_key  # type: ignore[attr-defined]

        headParams = {
            "Action": "QueryHunyuanTo3DJob",
            "Version": "2023-09-01",
            "Region": "ap-guangzhou",
        }
        data = {
            "JobId": (
                job_id.removeprefix("job_")
                if hasattr(job_id, "removeprefix")
                else job_id.replace("job_", "")
            )
        }

        headers, endpoint = get_tencent_cloud_sign_headers(
            "POST",
            "/",
            headParams,
            data,
            "hunyuan",
            "ap-guangzhou",
            secret_id,
            secret_key,
        )
        resp = requests.post(endpoint, headers=headers, data=json.dumps(data))
        return {"success": True, "data": resp.json()}
    except Exception as e:
        return {"error": str(e), "code": "POLL_ERROR"}


def _import_asset(zip_url):  # type: ignore[no-untyped-def]
    """Import asset from ZIP."""
    if not zip_url:
        return {"error": "Zip URL required", "code": "MISSING_ZIP_URL"}
    try:
        temp_dir = tempfile.mkdtemp(prefix="tencent_obj_")
        zip_path = osp.join(temp_dir, "model.zip")

        # Download
        r = requests.get(zip_url, stream=True)
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

        # Extract
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_dir)

        # Find OBJ
        obj_file = next((f for f in os.listdir(temp_dir) if f.endswith(".obj")), None)
        if not obj_file:
            return {"error": "No OBJ found in ZIP", "code": "NO_OBJ_FOUND"}

        # Import
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.import_scene.obj(filepath=osp.join(temp_dir, obj_file))

        return {"success": True, "message": "Imported successfully"}
    except Exception as e:
        return {"error": str(e), "code": "IMPORT_ERROR"}


def _create_job_official(text_prompt, image):  # type: ignore[no-untyped-def]
    """Create job via official API."""
    secret_id = bpy.context.scene.blendermcp_hunyuan3d_secret_id  # type: ignore[attr-defined]
    secret_key = bpy.context.scene.blendermcp_hunyuan3d_secret_key  # type: ignore[attr-defined]

    headParams = {
        "Action": "SubmitHunyuanTo3DJob",
        "Version": "2023-09-01",
        "Region": "ap-guangzhou",
    }
    data: Dict[str, Any] = {"Num": 1}
    if text_prompt:
        data["Prompt"] = text_prompt
    if image:
        if image.startswith("http"):
            data["ImageUrl"] = image
        else:
            with open(image, "rb") as f:
                data["ImageBase64"] = base64.b64encode(f.read()).decode("ascii")

    headers, endpoint = get_tencent_cloud_sign_headers(
        "POST", "/", headParams, data, "hunyuan", "ap-guangzhou", secret_id, secret_key
    )
    try:
        resp = requests.post(endpoint, headers=headers, data=json.dumps(data))
        return {"success": True, "data": resp.json()}
    except Exception as e:
        return {"error": str(e), "code": "API_ERROR"}


def _create_job_local(text_prompt, image):  # type: ignore[no-untyped-def]
    """Create job via local API."""
    base_url = bpy.context.scene.blendermcp_hunyuan3d_api_url.rstrip("/")  # type: ignore[attr-defined]
    data = {
        "octree_resolution": bpy.context.scene.blendermcp_hunyuan3d_octree_resolution,  # type: ignore[attr-defined]
        "num_inference_steps": bpy.context.scene.blendermcp_hunyuan3d_num_inference_steps,  # type: ignore[attr-defined]
        "guidance_scale": bpy.context.scene.blendermcp_hunyuan3d_guidance_scale,  # type: ignore[attr-defined]
        "texture": bpy.context.scene.blendermcp_hunyuan3d_texture,  # type: ignore[attr-defined]
    }
    if text_prompt:
        data["text"] = text_prompt
    if image:
        # Simplified image handling for local
        pass

    try:
        resp = requests.post(f"{base_url}/generate", json=data)
        if resp.status_code != 200:
            return {"error": resp.text, "code": "LOCAL_API_ERROR"}

        # Handle GLB return
        with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as tmp:
            tmp.write(resp.content)
            tmp_name = tmp.name

        def import_cb():  # type: ignore[no-untyped-def]
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.import_scene.gltf(filepath=tmp_name)
            os.unlink(tmp_name)

        bpy.app.timers.register(import_cb)
        return {"success": True, "message": "Job submitted to local API"}
    except Exception as e:
        return {"error": str(e), "code": "LOCAL_API_ERROR"}


def get_tencent_cloud_sign_headers(  # type: ignore[no-untyped-def]
    method, path, headParams, data, service, region, secret_id, secret_key, host=None
):
    """Helper: Sign Headers for Tencent Cloud API."""
    timestamp = int(time.time())
    date = datetime.datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
    if not host:
        host = f"{service}.tencentcloudapi.com"
    endpoint = f"https://{host}"

    payload = json.dumps(data)
    canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{host}\nx-tc-action:{headParams.get('Action', '').lower()}\n"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        f"{method}\n{path}\n\n{canonical_headers}\ncontent-type;host;x-tc-action\n{hashed_payload}"
    )

    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

    def sign(key, msg):  # type: ignore[no-untyped-def]
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = sign(secret_date, service)
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth = f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, SignedHeaders=content-type;host;x-tc-action, Signature={signature}"
    return {
        "Authorization": auth,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": headParams.get("Action"),
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": headParams.get("Version"),
        "X-TC-Region": region,
    }, endpoint
