"""
Unit tests for AsyncJobManager — job lifecycle, eviction, and status tracking.

No bpy required — bpy is mocked.
"""

from __future__ import annotations

import sys
import os
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

sys.modules.setdefault("bpy", MagicMock())
sys.modules.setdefault("mathutils", MagicMock())

from blender_mcp.core.job_manager import (
    AsyncJobManager,
    JobStatus,
    JobType,
)


def _reset_manager() -> None:
    """Reset singleton state between tests."""
    AsyncJobManager._jobs.clear()
    AsyncJobManager._processes.clear()
    AsyncJobManager._internal_queue.clear()
    AsyncJobManager._internal_callbacks.clear()
    AsyncJobManager._internal_is_running = False


# ---------------------------------------------------------------------------
# JobStatus / JobType enum tests
# ---------------------------------------------------------------------------


class TestJobEnums:
    def test_job_status_values(self) -> None:
        assert JobStatus.QUEUED.value == "QUEUED"
        assert JobStatus.RUNNING.value == "RUNNING"
        assert JobStatus.COMPLETED.value == "COMPLETED"
        assert JobStatus.FAILED.value == "FAILED"
        assert JobStatus.CANCELLED.value == "CANCELLED"

    def test_job_type_values(self) -> None:
        assert JobType.SUBPROCESS.value == "SUBPROCESS"
        assert JobType.INTERNAL.value == "INTERNAL"


# ---------------------------------------------------------------------------
# Internal job lifecycle tests
# ---------------------------------------------------------------------------


class TestInternalJobLifecycle:
    def setup_method(self) -> None:
        _reset_manager()

    def test_submit_internal_job_creates_entry(self) -> None:
        job_id = AsyncJobManager.submit_internal_job(
            callback=lambda jid: None,
            name="TestJob",
            metadata={"key": "val"},
        )
        assert job_id in AsyncJobManager._jobs
        job = AsyncJobManager._jobs[job_id]
        assert job["type"] == JobType.INTERNAL.value
        assert job["name"] == "TestJob"
        assert job["status"] == JobStatus.QUEUED.value
        assert job["metadata"]["key"] == "val"

    def test_mark_internal_job_success(self) -> None:
        job_id = AsyncJobManager.submit_internal_job(lambda jid: None, name="S")
        # Manually set to RUNNING (normally done by ticker)
        AsyncJobManager._jobs[job_id]["type"] = JobType.INTERNAL.value
        AsyncJobManager.mark_internal_job_success(job_id, result_payload={"output": 42})
        job = AsyncJobManager._jobs[job_id]
        assert job["status"] == JobStatus.COMPLETED.value
        assert job["progress"] == 100.0
        assert job["metadata"]["result"]["output"] == 42
        assert "end_time" in job

    def test_mark_internal_job_failed(self) -> None:
        job_id = AsyncJobManager.submit_internal_job(lambda jid: None, name="F")
        AsyncJobManager._jobs[job_id]["type"] = JobType.INTERNAL.value
        AsyncJobManager.mark_internal_job_failed(job_id, "boom")
        job = AsyncJobManager._jobs[job_id]
        assert job["status"] == JobStatus.FAILED.value
        assert job["error_message"] == "boom"
        assert "end_time" in job

    def test_mark_success_ignores_non_internal(self) -> None:
        """mark_internal_job_success should not modify subprocess jobs."""
        _reset_manager()
        AsyncJobManager._jobs["sub1"] = {
            "job_id": "sub1",
            "type": JobType.SUBPROCESS.value,
            "status": JobStatus.RUNNING.value,
            "start_time": time.time(),
            "metadata": {},
        }
        AsyncJobManager.mark_internal_job_success("sub1")
        assert AsyncJobManager._jobs["sub1"]["status"] == JobStatus.RUNNING.value


# ---------------------------------------------------------------------------
# check_job_status tests
# ---------------------------------------------------------------------------


class TestCheckJobStatus:
    def setup_method(self) -> None:
        _reset_manager()

    def test_unknown_job_id(self) -> None:
        result = AsyncJobManager.check_job_status("nonexistent")
        assert result["status"] == "UNKNOWN"
        assert result["job_id"] == "nonexistent"

    def test_returns_job_data(self) -> None:
        job_id = AsyncJobManager.submit_internal_job(lambda jid: None, name="Check")
        result = AsyncJobManager.check_job_status(job_id)
        assert result["name"] == "Check"
        assert result["status"] == JobStatus.QUEUED.value

    def test_subprocess_poll_completed(self) -> None:
        """Subprocess job whose process exited with 0 is marked COMPLETED."""
        proc = MagicMock()
        proc.poll.return_value = 0
        job_id = "proc-1"
        AsyncJobManager._jobs[job_id] = {
            "job_id": job_id,
            "type": JobType.SUBPROCESS.value,
            "status": JobStatus.RUNNING.value,
            "start_time": time.time(),
            "metadata": {},
        }
        AsyncJobManager._processes[job_id] = proc

        result = AsyncJobManager.check_job_status(job_id)
        assert result["status"] == JobStatus.COMPLETED.value
        assert job_id not in AsyncJobManager._processes

    def test_subprocess_poll_failed(self) -> None:
        """Subprocess job whose process exited with non-zero is marked FAILED."""
        proc = MagicMock()
        proc.poll.return_value = 1
        job_id = "proc-2"
        AsyncJobManager._jobs[job_id] = {
            "job_id": job_id,
            "type": JobType.SUBPROCESS.value,
            "status": JobStatus.RUNNING.value,
            "start_time": time.time(),
            "metadata": {},
        }
        AsyncJobManager._processes[job_id] = proc

        result = AsyncJobManager.check_job_status(job_id)
        assert result["status"] == JobStatus.FAILED.value
        assert "exit" in result.get("error_message", "").lower()


# ---------------------------------------------------------------------------
# update_job_progress tests
# ---------------------------------------------------------------------------


class TestUpdateJobProgress:
    def setup_method(self) -> None:
        _reset_manager()

    def test_update_progress(self) -> None:
        job_id = AsyncJobManager.submit_internal_job(lambda jid: None)
        AsyncJobManager.update_job_progress(job_id, 50.0, "halfway")
        job = AsyncJobManager._jobs[job_id]
        assert job["progress"] == 50.0
        assert job["metadata"]["last_message"] == "halfway"

    def test_progress_clamped_to_bounds(self) -> None:
        job_id = AsyncJobManager.submit_internal_job(lambda jid: None)
        AsyncJobManager.update_job_progress(job_id, 150.0)
        assert AsyncJobManager._jobs[job_id]["progress"] == 100.0

        AsyncJobManager.update_job_progress(job_id, -10.0)
        assert AsyncJobManager._jobs[job_id]["progress"] == 0.0

    def test_update_completed_job_noop(self) -> None:
        job_id = AsyncJobManager.submit_internal_job(lambda jid: None)
        AsyncJobManager._jobs[job_id]["status"] = JobStatus.COMPLETED.value
        AsyncJobManager.update_job_progress(job_id, 50.0)
        # Progress should NOT have changed since job is COMPLETED
        assert AsyncJobManager._jobs[job_id]["progress"] != 50.0


# ---------------------------------------------------------------------------
# cancel_job tests
# ---------------------------------------------------------------------------


class TestCancelJob:
    def setup_method(self) -> None:
        _reset_manager()

    def test_cancel_queued_internal_job(self) -> None:
        job_id = AsyncJobManager.submit_internal_job(lambda jid: None, name="Cancel")
        result = AsyncJobManager.cancel_job(job_id)
        assert result is True
        assert AsyncJobManager._jobs[job_id]["status"] == JobStatus.CANCELLED.value
        assert job_id not in AsyncJobManager._internal_queue

    def test_cancel_running_internal_job_fails(self) -> None:
        """Running internal jobs cannot be safely cancelled."""
        job_id = AsyncJobManager.submit_internal_job(lambda jid: None)
        AsyncJobManager._jobs[job_id]["status"] = JobStatus.RUNNING.value
        result = AsyncJobManager.cancel_job(job_id)
        assert result is False

    def test_cancel_nonexistent_returns_false(self) -> None:
        assert AsyncJobManager.cancel_job("fake-id") is False

    def test_cancel_subprocess_job(self) -> None:
        proc = MagicMock()
        proc.poll.return_value = None  # Still running after terminate
        # After kill, poll returns exit code
        proc.poll.side_effect = [None, 137]
        job_id = "proc-cancel"
        AsyncJobManager._jobs[job_id] = {
            "job_id": job_id,
            "type": JobType.SUBPROCESS.value,
            "status": JobStatus.RUNNING.value,
            "start_time": time.time(),
            "metadata": {},
        }
        AsyncJobManager._processes[job_id] = proc

        result = AsyncJobManager.cancel_job(job_id)
        assert result is True
        assert AsyncJobManager._jobs[job_id]["status"] == JobStatus.CANCELLED.value
        proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# list_jobs tests
# ---------------------------------------------------------------------------


class TestListJobs:
    def setup_method(self) -> None:
        _reset_manager()

    def test_list_empty(self) -> None:
        result = AsyncJobManager.list_jobs()
        assert result == []

    def test_list_all_jobs(self) -> None:
        AsyncJobManager.submit_internal_job(lambda jid: None, name="A")
        AsyncJobManager.submit_internal_job(lambda jid: None, name="B")
        result = AsyncJobManager.list_jobs()
        assert len(result) == 2
        names = {j["name"] for j in result}
        assert names == {"A", "B"}

    def test_list_with_status_filter(self) -> None:
        j1 = AsyncJobManager.submit_internal_job(lambda jid: None, name="Queued")
        j2 = AsyncJobManager.submit_internal_job(lambda jid: None, name="Done")
        AsyncJobManager._jobs[j2]["status"] = JobStatus.COMPLETED.value

        queued = AsyncJobManager.list_jobs(status_filter=JobStatus.QUEUED.value)
        assert len(queued) == 1
        assert queued[0]["name"] == "Queued"

    def test_list_returns_safe_copies(self) -> None:
        """Returned dicts should not expose internal mutable state."""
        AsyncJobManager.submit_internal_job(lambda jid: None, name="Safe")
        result = AsyncJobManager.list_jobs()
        expected_keys = {
            "job_id",
            "name",
            "type",
            "status",
            "progress",
            "start_time",
            "end_time",
            "metadata",
        }
        assert set(result[0].keys()) == expected_keys


# ---------------------------------------------------------------------------
# evict_old_jobs tests
# ---------------------------------------------------------------------------


class TestEvictOldJobs:
    def setup_method(self) -> None:
        _reset_manager()

    def test_no_eviction_under_limit(self) -> None:
        for i in range(5):
            AsyncJobManager.submit_internal_job(lambda jid: None, name=f"J{i}")
        AsyncJobManager._evict_old_jobs(max_jobs=10)
        assert len(AsyncJobManager._jobs) == 5

    def test_eviction_removes_oldest_finished(self) -> None:
        # Create 5 jobs, mark 3 as completed with different end_times
        for i in range(5):
            jid = AsyncJobManager.submit_internal_job(lambda jid: None, name=f"J{i}")
            if i < 3:
                AsyncJobManager._jobs[jid]["status"] = JobStatus.COMPLETED.value
                AsyncJobManager._jobs[jid]["end_time"] = float(i)

        assert len(AsyncJobManager._jobs) == 5
        AsyncJobManager._evict_old_jobs(max_jobs=3)
        assert len(AsyncJobManager._jobs) == 3

    def test_eviction_preserves_running_jobs(self) -> None:
        """Running jobs should never be evicted."""
        jids = []
        for i in range(5):
            jid = AsyncJobManager.submit_internal_job(lambda jid: None, name=f"J{i}")
            jids.append(jid)
            if i < 3:
                AsyncJobManager._jobs[jid]["status"] = JobStatus.RUNNING.value
            else:
                AsyncJobManager._jobs[jid]["status"] = JobStatus.COMPLETED.value
                AsyncJobManager._jobs[jid]["end_time"] = float(i)

        AsyncJobManager._evict_old_jobs(max_jobs=3)
        # All 3 RUNNING jobs must survive
        running_count = sum(
            1 for j in AsyncJobManager._jobs.values() if j["status"] == JobStatus.RUNNING.value
        )
        assert running_count == 3
