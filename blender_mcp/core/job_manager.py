"""
Async Job Manager for Blender 5.0+
Handles background subprocesses AND internal asynchronous tasks via bpy.app.timers.
Features:
- CLI Job Queue & Persistence
- Internal Job Queue via app.timers
- Zombie Process Cleanup (atexit)
- Status Polling
"""

import os
import subprocess
import threading
import uuid
import time
import atexit
import traceback
import inspect
from typing import Dict, List, Any, Optional, Callable, Generator
from enum import Enum

from ..core.logging_config import get_logger

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy = None

logger = get_logger()


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobType(str, Enum):
    SUBPROCESS = "SUBPROCESS"
    INTERNAL = "INTERNAL"


class AsyncJobManager:
    _instance = None
    _lock = threading.Lock()

    # In-memory job store
    _jobs: Dict[str, Dict[str, Any]] = {}

    # Subprocess tracking
    _processes: Dict[str, subprocess.Popen] = {}

    # Internal queue tracking
    _internal_queue: List[str] = []
    _internal_callbacks: Dict[str, Callable] = {}
    _internal_is_running: bool = False

    def __new__(cls) -> "AsyncJobManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(AsyncJobManager, cls).__new__(cls)
                    atexit.register(cls._cleanup_all_processes)
        return cls._instance

    @classmethod
    def check_job_status(cls, job_id: str) -> Dict[str, Any]:
        """Get current status of a job."""
        job = cls._jobs.get(job_id)
        if not job:
            return {"status": "UNKNOWN", "job_id": job_id}

        # Subprocess check logic
        if job["type"] == JobType.SUBPROCESS.value and job["status"] == JobStatus.RUNNING.value:
            proc = cls._processes.get(job_id)
            if proc:
                ret = proc.poll()
                if ret is not None:
                    if ret == 0:
                        job["status"] = JobStatus.COMPLETED.value
                        job["end_time"] = time.time()
                        job["duration"] = job["end_time"] - job["start_time"]
                    else:
                        job["status"] = JobStatus.FAILED.value
                        job["error_message"] = f"Process exited with code {ret}"
                        job["end_time"] = time.time()

                    del cls._processes[job_id]

        return job

    @classmethod
    def update_job_progress(cls, job_id: str, progress: float, message: str = "") -> None:
        """Update progress for an internal running job."""
        job = cls._jobs.get(job_id)
        if job and job["status"] in (JobStatus.RUNNING.value, JobStatus.QUEUED.value):
            job["progress"] = max(0.0, min(100.0, progress))
            if message:
                job["metadata"]["last_message"] = message

    @classmethod
    def submit_job(
        cls,
        command: List[str],
        cwd: str,
        name: str = "SubprocessJob",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Submit an external OS subprocess job."""
        job_id = str(uuid.uuid4())

        log_dir = os.path.join(cwd, "logs")
        os.makedirs(log_dir, exist_ok=True)
        stdout_path = os.path.join(log_dir, f"{job_id}.out")
        stderr_path = os.path.join(log_dir, f"{job_id}.err")

        try:
            stdout_f = open(stdout_path, "w")
            stderr_f = open(stderr_path, "w")

            proc = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=stdout_f,
                stderr=stderr_f,
            )
            # Close Python-side handles immediately — the subprocess inherited
            # the FDs at Popen() time, so these Python objects are now redundant.
            # Leaving them open leaks file descriptors on repeated renders.
            stdout_f.close()
            stderr_f.close()

            cls._processes[job_id] = proc

            cls._jobs[job_id] = {
                "job_id": job_id,
                "type": JobType.SUBPROCESS.value,
                "name": name,
                "command": " ".join(command),
                "status": JobStatus.RUNNING.value,
                "progress": 0.0,
                "start_time": time.time(),
                "pid": proc.pid,
                "log_files": {"stdout": stdout_path, "stderr": stderr_path},
                "metadata": metadata or {},
            }

            logger.info(f"Started subprocess job {job_id} (PID: {proc.pid}): {name}")
            cls._evict_old_jobs()
            return job_id

        except Exception as e:
            logger.error(f"Failed to submit subprocess job {name}: {e}")
            raise e

    @classmethod
    def submit_internal_job(
        cls,
        callback: Callable[[str], Generator[None, None, None] | None],
        name: str = "InternalJob",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Submit an internal Blender task to run via app.timers.
        The callback must accept `job_id` as its only argument, and should yield or return quickly
        if implemented as a generator. However, simple synchronous-chunks inside handlers
        are preferred, using timer intervals.
        """
        job_id = str(uuid.uuid4())

        cls._jobs[job_id] = {
            "job_id": job_id,
            "type": JobType.INTERNAL.value,
            "name": name,
            "status": JobStatus.QUEUED.value,
            "progress": 0.0,
            "start_time": time.time(),
            "metadata": metadata or {},
        }

        cls._internal_callbacks[job_id] = callback
        cls._internal_queue.append(job_id)

        logger.info(f"Queued internal job {job_id}: {name}")

        if not cls._internal_is_running and BPY_AVAILABLE and bpy:
            cls._start_internal_ticker()

        # Evict old completed/failed/cancelled jobs if store exceeds limit
        cls._evict_old_jobs()

        return job_id

    @classmethod
    def _evict_old_jobs(cls, max_jobs: int = 100) -> None:
        """Remove oldest finished jobs when store exceeds max_jobs entries."""
        if len(cls._jobs) <= max_jobs:
            return
        finished_statuses = {
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        }
        finished = sorted(
            [(jid, j) for jid, j in cls._jobs.items() if j.get("status") in finished_statuses],
            key=lambda x: x[1].get("end_time", 0),
        )
        to_remove = len(cls._jobs) - max_jobs
        for jid, _ in finished[:to_remove]:
            del cls._jobs[jid]

    @classmethod
    def mark_internal_job_success(cls, job_id: str, result_payload: Any = None) -> None:
        """Mark an internal job as finished successfully."""
        job = cls._jobs.get(job_id)
        if job and job["type"] == JobType.INTERNAL.value:
            job["status"] = JobStatus.COMPLETED.value
            job["progress"] = 100.0
            job["end_time"] = time.time()
            if "duration" not in job:
                job["duration"] = job["end_time"] - job["start_time"]
            if result_payload:
                job["metadata"]["result"] = result_payload
            logger.info(f"Internal Job {job_id} COMPLETED.")

    @classmethod
    def mark_internal_job_failed(cls, job_id: str, error_msg: str) -> None:
        """Mark an internal job as failed."""
        job = cls._jobs.get(job_id)
        if job and job["type"] == JobType.INTERNAL.value:
            job["status"] = JobStatus.FAILED.value
            job["error_message"] = error_msg
            job["end_time"] = time.time()
            if "duration" not in job:
                job["duration"] = job["end_time"] - job["start_time"]
            logger.error(f"Internal Job {job_id} FAILED: {error_msg}")

    @classmethod
    def _start_internal_ticker(cls) -> None:
        """Register the Blender app timer to process the internal queue."""
        if cls._internal_is_running:
            return

        cls._internal_is_running = True
        bpy.app.timers.register(cls._internal_tick)
        logger.debug("AsyncJobManager internal ticker registered.")

    @classmethod
    def _internal_tick(cls) -> Optional[float]:
        """
        Called periodically by Blender.
        Pulls jobs from the queue and executes them in an Exception-Shielded wrapper.
        """
        if not cls._internal_queue:
            cls._internal_is_running = False
            logger.debug("AsyncJobManager internal queue empty. Ticker unregistered.")
            return None  # Unregister timer

        job_id = cls._internal_queue[0]
        job = cls._jobs.get(job_id)
        callback = cls._internal_callbacks.get(job_id)

        if not job or not callback:
            cls._internal_queue.pop(0)
            return 0.1  # Run again soon

        if job["status"] == JobStatus.QUEUED.value:
            job["status"] = JobStatus.RUNNING.value
            job["start_time"] = time.time()
            # If the callback is a generator function, instantiate it.
            if inspect.isgeneratorfunction(callback):
                # We replace the callback in the dict with the generator instance
                gen = callback(job_id)
                cls._internal_callbacks[job_id] = gen
                callback = gen

        try:
            # Execute the callback footprint.
            if inspect.isgenerator(callback):
                # It's a generator, so we resume it.
                next(callback)
            elif callable(callback):
                # It's a normal function, runs synchronously.
                callback(job_id)
                # If a normal function doesn't manually mark completion, auto-complete it.
                if job["status"] == JobStatus.RUNNING.value:
                    cls.mark_internal_job_success(job_id)

        except StopIteration:
            # The generator has finished.
            if job["status"] == JobStatus.RUNNING.value:
                cls.mark_internal_job_success(job_id)

        except Exception as e:
            err_msg = traceback.format_exc()
            logger.error(f"Error executing internal job {job_id}:\n{err_msg}")
            cls.mark_internal_job_failed(job_id, str(e))
        finally:
            # We ONLY pop the job if it explicitly declared COMPLETED/FAILED/CANCELLED
            if job["status"] in (
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value,
            ):
                cls._internal_queue.pop(0)
                if job_id in cls._internal_callbacks:
                    del cls._internal_callbacks[job_id]

        return 0.1  # Run the queue frequently enough to process fast yielding processes

    @classmethod
    def cancel_job(cls, job_id: str) -> bool:
        """Kill a running job (subprocess) or remove from queue (internal)."""
        job = cls._jobs.get(job_id)
        if not job:
            return False

        if job["type"] == JobType.SUBPROCESS.value:
            proc = cls._processes.get(job_id)
            if proc:
                try:
                    proc.terminate()
                    time.sleep(0.5)
                    if proc.poll() is None:
                        proc.kill()
                    job["status"] = JobStatus.CANCELLED.value
                    job["end_time"] = time.time()
                    del cls._processes[job_id]
                    return True
                except Exception as e:
                    logger.error(f"Failed to cancel subprocess job {job_id}: {e}")
                    return False

        elif job["type"] == JobType.INTERNAL.value:
            if job["status"] == JobStatus.QUEUED.value:
                if job_id in cls._internal_queue:
                    cls._internal_queue.remove(job_id)
                job["status"] = JobStatus.CANCELLED.value
                return True
            else:
                logger.warning(f"Cannot cancel running internal job {job_id} safely.")
                return False

        return False

    @classmethod
    def list_jobs(cls, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return a snapshot of all tracked jobs, optionally filtered by status."""
        jobs = list(cls._jobs.values())
        if status_filter:
            jobs = [j for j in jobs if j.get("status") == status_filter]
        # Return safe copies (strip internal references)
        return [
            {
                "job_id": j.get("job_id"),
                "name": j.get("name"),
                "type": j.get("type"),
                "status": j.get("status"),
                "progress": j.get("progress", 0),
                "start_time": j.get("start_time"),
                "end_time": j.get("end_time"),
                "metadata": j.get("metadata", {}),
            }
            for j in jobs
        ]

    @classmethod
    def _cleanup_all_processes(cls) -> None:
        """Atexit handler to kill zombies."""
        if not cls._processes:
            return
        logger.info(f"Cleaning up {len(cls._processes)} background jobs...")
        for job_id, proc in list(cls._processes.items()):
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
        cls._processes.clear()
