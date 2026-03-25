"""
Jobs Handler for Blender MCP 1.0.0

Exposes the AsyncJobManager status query directly to MCP Clients.
Allows querying, listing, and canceling background tasks.
"""

from typing import Any
from ..core.job_manager import AsyncJobManager, JobStatus
from ..core.enums import JobsAction
from ..core.parameter_validator import validated_handler
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..dispatcher import register_handler
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_jobs",
    actions=[a.value for a in JobsAction],
    category="system",
    schema={
        "type": "object",
        "title": "Background Job Manager",
        "description": (
            "Monitor and control background render/simulation jobs. "
            "RENDER_ANIMATION and RENDER_FRAME both run as background subprocesses and "
            "return a job_id — use this tool to track and cancel them. "
            "LIST_JOBS: show all jobs (optionally filtered by status). "
            "CHECK_STATUS: get progress of a specific job by job_id. "
            "CANCEL_JOB: immediately terminate a running render subprocess (stops frame output)."
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(JobsAction, "Job action to perform"),
            "job_id": {
                "type": "string",
                "description": "The UUID of the background job (required for CHECK_STATUS and CANCEL_JOB)",
            },
            "status_filter": {
                "type": "string",
                "enum": ["RUNNING", "QUEUED", "COMPLETED", "FAILED", "CANCELLED"],
                "description": "Optional filter for LIST_JOBS",
            },
        },
        "required": ["action"],
    },
)
@validated_handler(actions=[a.value for a in JobsAction])
def manage_jobs(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Diagnostic and lifecycle manager for Async background jobs.
    Check execution status, list all jobs, or trigger cancellations.
    """
    job_id = params.get("job_id", "")

    if action == JobsAction.LIST_JOBS.value:
        status_filter = params.get("status_filter")
        jobs = AsyncJobManager.list_jobs(status_filter=status_filter)
        return ResponseBuilder.success(
            handler="manage_jobs",
            action=action,
            data={
                "jobs": jobs,
                "total": len(jobs),
                "filter": status_filter or "ALL",
            },
        )

    # CHECK_STATUS and CANCEL_JOB require a job_id
    if not job_id:
        return ResponseBuilder.error(
            handler="manage_jobs",
            action=str(action),
            error_code="MISSING_PARAMETER",
            message=f"'job_id' is required for action '{action}'. Use LIST_JOBS to see available jobs.",
        )

    if action == JobsAction.CHECK_STATUS.value:
        status_info = AsyncJobManager.check_job_status(job_id)
        status = status_info.get("status")
        # Reject expired, timeout, failed or cancelled jobs
        if status in ("UNKNOWN", "FAILED", "CANCELLED", "TIMEOUT"):
            return ResponseBuilder.error(
                handler="manage_jobs",
                action=action,
                error_code="JOB_EXPIRED_OR_FAILED",
                message=(
                    f"Job '{job_id}' not found or no longer active (status: {status}). "
                    "Use LIST_JOBS to see current jobs."
                ),
            )
        return ResponseBuilder.success(
            handler="manage_jobs",
            action=action,
            data={"job": status_info},
        )

    elif action == JobsAction.CANCEL_JOB.value:
        success = AsyncJobManager.cancel_job(job_id)
        if success:
            return ResponseBuilder.success(
                handler="manage_jobs",
                action=action,
                data={"job_id": job_id, "status": JobStatus.CANCELLED.value},
            )
        else:
            return ResponseBuilder.error(
                handler="manage_jobs",
                action=action,
                error_code="CANCEL_FAILED",
                message=f"Job '{job_id}' could not be cancelled or was not running.",
            )

    return ResponseBuilder.error(
        handler="manage_jobs",
        action=str(action),
        error_code="INVALID_ACTION",
        message=f"Unknown job action: {action}",
    )
