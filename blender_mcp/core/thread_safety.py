"""
Thread Safety V2 for Blender MCP 1.0.0

High-performance, event-driven thread safety for Blender MCP.
Uses optimized queue + threading.Event for sub-second latency.

High Mode Philosophy: Thread-safe execution without limiting functionality.
Performance Target: <100ms latency for all operations.
"""

import queue
import threading
import functools
import time
import uuid
from typing import Callable, Any, Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .logging_config import get_logger

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

logger = get_logger()


class ExecutionStatus(Enum):
    """Execution status for tracked operations."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class MCPCommand:
    """
    Structured command payload for XAI-compliant execution.
    Adheres to 'CommandQueue' pattern.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    func: Callable[..., Any] = field(default=print)
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)

    # XAI & Traceability
    tool_id: Optional[str] = None
    intent: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None

    # Execution State
    event: threading.Event = field(default_factory=threading.Event)
    result: Optional[Any] = None
    error: Optional[Exception] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def execute(self) -> None:
        """Execute the command and signal completion."""
        self.status = ExecutionStatus.RUNNING
        try:
            self.result = self.func(*self.args, **self.kwargs)
            self.status = ExecutionStatus.COMPLETED
        except Exception as e:
            self.error = e
            self.status = ExecutionStatus.FAILED
        finally:
            self.end_time = time.time()
            self.event.set()

    @property
    def duration_ms(self) -> float:
        """Get execution duration in milliseconds."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000


class ThreadSafety:
    """
    High-performance thread-safe execution for Blender MCP.

    Features:
    - Event-driven (no polling)
    - Automatic main thread detection
    - Performance metrics
    - Task cancellation
    - Batch execution
    """

    _instance: Optional["ThreadSafety"] = None
    _lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> "ThreadSafety":
        """Singleton pattern for global access."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the thread safety system."""
        if self._initialized:
            return

        self._initialized = True
        self._initialized = True
        self._task_queue: queue.Queue[MCPCommand] = queue.Queue()
        self._active_tasks: Dict[str, MCPCommand] = {}
        self._timer_registered = False
        self._stats = {
            "total_executed": 0,
            "total_failed": 0,
            "avg_latency_ms": 0.0,
        }

        # Health Monitoring (Logical Stall Detector)
        self._last_depsgraph_update: float = time.time()
        self._last_main_thread_tick: float = time.time()
        self._stop_monitor = threading.Event()

        self._register_health_monitors()

    def _register_health_monitors(self) -> None:
        """Register Blender handlers for health monitoring."""
        if not BPY_AVAILABLE:
            return

        # Track Depsgraph Updates (Scene changes)
        # We use a persistent wrapper to avoid double registration
        if not hasattr(bpy.app.handlers, "depsgraph_update_post"):
            return

        handlers = bpy.app.handlers.depsgraph_update_post
        # Remove existing if present (to allow reloading)
        handlers[:] = [h for h in handlers if getattr(h, "__name__", "") != "_mcp_depsgraph_hook"]

        _depsgraph_throttle: Dict[str, float] = {"last": 0.0}

        @bpy.app.handlers.persistent
        def _mcp_depsgraph_hook(scene: Any, depsgraph: Any) -> None:
            # Throttle to at most once per 0.1s — depsgraph fires on every
            # viewport move/property change/animation frame, so an unthrottled
            # hook causes Python overhead on every GPU frame.
            now = time.time()
            if now - _depsgraph_throttle["last"] < 0.1:
                return
            _depsgraph_throttle["last"] = now
            if self._instance:
                self._instance._last_depsgraph_update = now

        handlers.append(_mcp_depsgraph_hook)

        # Start Daemon Monitor Thread (guard against double-start on reload)
        monitor: threading.Thread | None = getattr(self, "_monitor_thread", None)
        if not (monitor is not None and monitor.is_alive()):
            self._stop_monitor.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop, name="MCP-Stall-Detector", daemon=True
            )
            self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        """
        Background thread checking for logical stalls.
        Runs every 5 seconds.
        """
        while not self._stop_monitor.is_set():
            time.sleep(5.0)
            try:
                self._check_logical_stall()
            except Exception as e:
                print(f"[MCP-Monitor] Error: {e}")

    def _check_logical_stall(self) -> None:
        """
        Composite Watchdog Logic.
        Triangulates: Time + Depsgraph + Job Status.
        """
        if not BPY_AVAILABLE:
            return

        # Explicitly check for job state to avoid thread race conditions
        is_job_running = False
        try:
            # Split to avoid multi-line ignore issues with formatter
            check_render = bpy.app.is_job_running("RENDER")

            check_bake = bpy.app.is_job_running("OBJECT_BAKE")

            is_job_running = check_render or check_bake
        except:
            pass

        now = time.time()
        # If job is running, we consider the main thread "alive" even if not ticking
        if is_job_running:
            self._last_main_thread_tick = now  # Fake tick to Prevent alarm
            return

        tick_delta = now - self._last_main_thread_tick
        deps_delta = now - self._last_depsgraph_update

        # Threshold: 30 seconds of silence
        THRESHOLD = 30.0

        if tick_delta > THRESHOLD and deps_delta > THRESHOLD:
            logger.warning("⚠️ [MCP-Health] LOGICAL STALL DETECTED!")
            logger.warning(f"   - Main Thread Silence: {tick_delta:.2f}s")
            logger.warning(f"   - Depsgraph Silence: {deps_delta:.2f}s")
            logger.debug("   - No Active Render/Bake Job Detected")

    def _ensure_timer(self) -> bool:
        """
        Ensure the Blender timer is registered.

        Returns:
            True if timer is active
        """
        if not BPY_AVAILABLE:
            return False

        if self._timer_registered:
            try:
                if bpy.app.timers.is_registered(self._process_queue):
                    return True
            except:
                pass

        try:
            bpy.app.timers.register(
                self._process_queue,
                first_interval=0.001,  # 1ms initial delay
                persistent=True,
            )
            self._timer_registered = True
            return True
        except Exception as e:
            logger.error(f"[MCP ThreadSafety] Timer registration failed: {e}")
            return False

    def _process_queue(self) -> Optional[float]:
        """
        Process pending tasks on main thread.
        Called by bpy.app.timers.

        Returns:
            Next interval or None to stop
        """
        # Update Heartbeat
        self._last_main_thread_tick = time.time()

        processed = 0
        max_per_tick = 20  # Process up to 20 tasks per frame

        while processed < max_per_tick:
            try:
                task = self._task_queue.get_nowait()
            except queue.Empty:
                break

            # Execute task
            task.execute()

            # Update stats
            self._stats["total_executed"] += 1
            if task.status == ExecutionStatus.FAILED:
                self._stats["total_failed"] += 1

            # Update average latency
            n = self._stats["total_executed"]
            current_avg = self._stats["avg_latency_ms"]
            self._stats["avg_latency_ms"] = ((n - 1) * current_avg + task.duration_ms) / n

            processed += 1

        # Return interval based on queue state
        if not self._task_queue.empty():
            return 0.001  # Keep processing
        return 1.0  # 1fps when idle — reduces continuous GPU/CPU polling

    @classmethod
    def execute_on_main(
        cls,
        func: Callable[..., Any],
        *args: Any,
        tool_id: Optional[str] = None,
        intent: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a function on the main thread and wait for result.

        Args:
            func: Function to execute
            *args: Positional arguments
            tool_id: ID of the calling tool (for XAI)
            intent: User intent description (for XAI)
            timeout: Maximum wait time in seconds
            **kwargs: Keyword arguments for func

        Returns:
            Function result

        Raises:
            TimeoutError: If execution exceeds timeout
            Exception: If function raises an exception
        """
        # Fast path: not in Blender
        if not BPY_AVAILABLE:
            return func(*args, **kwargs)

        # Fast path: already on main thread
        if is_main_thread():
            return func(*args, **kwargs)

        instance = cls()
        instance._ensure_timer()

        # Create MCP Command
        cmd = MCPCommand(func=func, args=args, kwargs=kwargs, tool_id=tool_id, intent=intent)

        instance._task_queue.put(cmd)
        instance._active_tasks[cmd.id] = cmd

        # Wait for completion
        if not cmd.event.wait(timeout):
            cmd.status = ExecutionStatus.TIMEOUT
            del instance._active_tasks[cmd.id]

            # Log XAI Failure
            if tool_id or intent:
                logger.warning(f"[XAI_TRACE] TIMEOUT: {tool_id} | Intent: {intent}")

            raise TimeoutError(f"Execution timed out after {timeout}s")

        if cmd.status == ExecutionStatus.FAILED:
            if cmd.error:
                # Log XAI Error
                if tool_id or intent:
                    logger.error(f"[XAI_TRACE] ERROR: {tool_id} | Intent: {intent} | {cmd.error}")
                raise cmd.error
            raise RuntimeError("Execution failed without error details")

        # Log XAI Success
        if tool_id or intent:
            # In production, this would go to a structured log
            # print(f"[XAI_TRACE] SUCCESS: {tool_id} | Intent: {intent} | {cmd.duration_ms:.2f}ms")
            pass

        return cmd.result

    def execute_batch(
        self, operations: List[Tuple[Any, ...]], timeout: float = 60.0, stop_on_error: bool = True
    ) -> List[Any]:
        """
        Execute multiple operations efficiently using MCPCommands.

        Args:
            operations: List of (func, args, kwargs) tuples
            timeout: Total timeout for all operations
            stop_on_error: Stop on first error

        Returns:
            List of results
        """
        results: List[Any] = []
        errors: List[Optional[Exception]] = []

        # Create all tasks
        cmds: List[MCPCommand] = []
        for op in operations:
            func: Callable[..., Any]
            args: Tuple[Any, ...]
            kwargs: Dict[str, Any]

            if len(op) == 2:
                func, args = op
                kwargs = {}
            elif len(op) == 3:
                func, args, kwargs = op
            else:
                raise ValueError(f"Invalid operation format: {op}")

            cmd = MCPCommand(
                id=str(uuid.uuid4()), func=func, args=args, kwargs=kwargs, intent="batch_execution"
            )
            cmds.append(cmd)
            self._active_tasks[cmd.id] = cmd
            self._task_queue.put(cmd)

        # Ensure timer
        self._ensure_timer()

        # Wait for all with timeout
        start = time.time()
        remaining_timeout = timeout

        for cmd in cmds:
            if remaining_timeout <= 0:
                errors.append(TimeoutError("Batch timeout"))
                results.append(None)
                continue

            if not cmd.event.wait(timeout=remaining_timeout):
                errors.append(TimeoutError(f"Command {cmd.id} timeout"))
                results.append(None)
                if stop_on_error:
                    break
            else:
                if cmd.status == ExecutionStatus.FAILED:
                    errors.append(cmd.error)
                    results.append(None)
                    if stop_on_error:
                        break
                else:
                    results.append(cmd.result)
                    errors.append(None)

            remaining_timeout = timeout - (time.time() - start)

        # Cleanup
        for cmd in cmds:
            self._active_tasks.pop(cmd.id, None)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            **self._stats,
            "queue_size": self._task_queue.qsize(),
            "active_tasks": len(self._active_tasks),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def is_main_thread() -> bool:
    """
    Check if current thread is Blender's main thread.

    Returns:
        True if on main thread
    """
    try:
        return threading.current_thread() is threading.main_thread()
    except Exception:
        return False


def execute_on_main_thread(
    func: Callable[..., Any], *args: Any, timeout: float = 30.0, **kwargs: Any
) -> Any:
    """
    Convenience function for main thread execution.

    Example:
        result = execute_on_main_thread(bpy.ops.object.mode_set, mode='EDIT')
    """
    return ThreadSafety().execute_on_main(func, *args, timeout=timeout, **kwargs)


def thread_safe(timeout: float = 30.0) -> Callable[..., Any]:
    """
    Decorator to automatically route function to main thread.

    Usage:
        @thread_safe(timeout=10.0)
        def my_bpy_operation():
            bpy.ops.mesh.primitive_cube_add()
            return bpy.context.active_object
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return ThreadSafety().execute_on_main(func, *args, timeout=timeout, **kwargs)

        return wrapper

    return decorator


def ensure_main_thread(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator that ensures function runs on main thread.
    Only redirects if NOT on main thread.

    Usage:
        @ensure_main_thread
        def my_handler():
            # Always runs on main thread
            pass
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if is_main_thread():
            return func(*args, **kwargs)
        return ThreadSafety().execute_on_main(func, *args, **kwargs)

    return wrapper


# =============================================================================
# SAFE OPERATORS - Pre-bound safe operations
# =============================================================================


class SafeOperators:
    """
    Pre-bound safe operations for common bpy.ops calls.
    All operations automatically execute on main thread.

    Usage:
        from ..core.thread_safety import SafeOperators

        # These automatically execute on main thread
        SafeOperators.mode_set(mode='EDIT')
        SafeOperators.cube_add(size=2.0)
    """

    @staticmethod
    def mode_set(mode: str, **kwargs: Any) -> Any:
        """Safe mode_set."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.object.mode_set, mode=mode, **kwargs)

    @staticmethod
    def cube_add(size: float = 2.0, **kwargs: Any) -> Any:
        """Safe cube add."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.mesh.primitive_cube_add, size=size, **kwargs)

    @staticmethod
    def sphere_add(radius: float = 1.0, **kwargs: Any) -> Any:
        """Safe sphere add."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.mesh.primitive_uv_sphere_add, radius=radius, **kwargs)

    @staticmethod
    def select_all(action: str = "SELECT") -> Any:
        """Safe select all."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.object.select_all, action=action)

    @staticmethod
    def delete(**kwargs: Any) -> Any:
        """Safe delete."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.object.delete, **kwargs)

    @staticmethod
    def modifier_apply(modifier: str, **kwargs: Any) -> Any:
        """Safe modifier apply."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.object.modifier_apply, modifier=modifier, **kwargs)

    @staticmethod
    def join() -> Any:
        """Safe join."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.object.join)

    @staticmethod
    def duplicate(linked: bool = False, mode: str = "TRANSLATION", **kwargs: Any) -> Any:
        """Safe duplicate."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.object.duplicate, linked=linked, mode=mode, **kwargs)

    @staticmethod
    def modifier_add(type: str, **kwargs: Any) -> Any:
        """Safe modifier add."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.object.modifier_add, type=type, **kwargs)

    @staticmethod
    def subdivide(number_cuts: int = 1, **kwargs: Any) -> Any:
        """Safe mesh subdivide."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.mesh.subdivide, number_cuts=number_cuts, **kwargs)

    @staticmethod
    def nla_bake(frame_start: int, frame_end: int, **kwargs: Any) -> Any:
        """Safe NLA bake."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(
            bpy.ops.nla.bake, frame_start=frame_start, frame_end=frame_end, **kwargs
        )

    @staticmethod
    def export_gltf(filepath: str, **kwargs: Any) -> Any:
        """Safe glTF export."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.export_scene.gltf, filepath=filepath, **kwargs)

    @staticmethod
    def export_usd(filepath: str, **kwargs: Any) -> Any:
        """Safe USD export."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.wm.usd_export, filepath=filepath, **kwargs)

    @staticmethod
    def export_alembic(filepath: str, **kwargs: Any) -> Any:
        """Safe Alembic export."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.wm.alembic_export, filepath=filepath, **kwargs)

    @staticmethod
    def export_fbx(filepath: str, **kwargs: Any) -> Any:
        """Safe FBX export."""
        if not BPY_AVAILABLE:
            return None
        return execute_on_main_thread(bpy.ops.export_scene.fbx, filepath=filepath, **kwargs)

    @staticmethod
    def export_obj(filepath: str, **kwargs: Any) -> Any:
        """Safe OBJ export."""
        if not BPY_AVAILABLE:
            return None
        export_scene = getattr(bpy.ops, "export_scene", None)
        if export_scene is not None and hasattr(export_scene, "obj"):
            return execute_on_main_thread(export_scene.obj, filepath=filepath, **kwargs)
        wm_ops = getattr(bpy.ops, "wm", None)
        if wm_ops is not None and hasattr(wm_ops, "obj_export"):
            return execute_on_main_thread(wm_ops.obj_export, filepath=filepath, **kwargs)
        raise RuntimeError("No OBJ export operator available in this Blender build")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ThreadSafety",
    "MCPCommand",
    "ExecutionStatus",
    "execute_on_main_thread",
    "is_main_thread",
    "thread_safe",
    "ensure_main_thread",
    "SafeOperators",
]
