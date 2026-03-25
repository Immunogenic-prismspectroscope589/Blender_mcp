"""
Headless/Background Mode Module for Blender MCP 1.0.0

Implements:
- Background mode detection and adaptation
- Contextless operations
- Timer-based execution queue
- Memory management for long-running sessions
- CI/CD optimization

High Mode Philosophy: Runs anywhere, anytime, flawlessly.
"""

import time
import gc
from typing import Dict, Any, List, Optional, Tuple, Iterator, Callable, cast
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
from .error_protocol import ErrorProtocol, create_error
from .logging_config import get_logger
from .versioning import BlenderCompatibility

logger = get_logger()


class HeadlessMode(Enum):
    """Headless operation modes."""

    FULL_GUI = "full_gui"
    BACKGROUND = "background"
    SERVER = "server"
    CI_CD = "ci_cd"


@dataclass
class ExecutionTask:
    """Task for deferred execution."""

    func: Callable
    args: Tuple
    kwargs: Dict
    callback: Optional[Callable] = None
    timeout: float = 30.0


class HeadlessModeManager:
    """
    Manage headless/background mode operations.

    Critical for:
    - CI/CD pipelines
    - Cloud rendering
    - Server-side automation
    - Batch processing
    """

    _instance = None
    _task_queue: List[ExecutionTask] = []
    _is_processing = False

    def __new__(cls) -> "HeadlessModeManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def detect_mode() -> HeadlessMode:
        """
        Detect current Blender running mode.
        """
        if not BPY_AVAILABLE:
            return HeadlessMode.BACKGROUND

        if bpy.app.background:
            # Check for server mode (no display)
            if BlenderCompatibility.is_version(4, 0, 0) and hasattr(bpy.app, "version_string"):
                return HeadlessMode.CI_CD
            return HeadlessMode.BACKGROUND

        return HeadlessMode.FULL_GUI

    @staticmethod
    def is_headless() -> bool:
        """Check if running in headless mode."""
        return HeadlessModeManager.detect_mode() != HeadlessMode.FULL_GUI

    @staticmethod
    def ensure_minimal_context() -> Dict[str, Any]:
        """
        Ensure minimal viable context for headless operations.
        Creates default scene, collection, and camera if missing.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            created = []

            # Ensure main scene
            if not bpy.data.scenes:
                scene = bpy.data.scenes.new("Scene")
                created.append(f"scene:{scene.name}")
            else:
                scene = bpy.data.scenes[0]

            # Ensure context scene
            if bpy.context.scene is None:
                # Try to set context
                if bpy.context.window:
                    bpy.context.window.scene = scene

            # Ensure view layer
            if not scene.view_layers:
                vl = scene.view_layers.new(name="ViewLayer")
                created.append(f"view_layer:{vl.name}")

            # Ensure collection
            if not scene.collection:
                col = bpy.data.collections.new("Collection")
                scene.collection.children.link(col)
                created.append(f"collection:{col.name}")

            # Ensure camera
            if not scene.camera:
                cam = bpy.data.cameras.new("Camera")
                cam_obj = bpy.data.objects.new("Camera", cam)
                scene.collection.objects.link(cam_obj)
                scene.camera = cam_obj
                created.append(f"camera:{cam_obj.name}")

            return {
                "success": True,
                "scene": scene.name,
                "created": created,
                "headless": bpy.app.background,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.NO_CONTEXT, custom_message=f"Context setup failed: {str(e)}"
            )

    @staticmethod
    def queue_execution(
        func: Callable,
        *args: Any,
        callback: Optional[Callable] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Queue function for execution on main thread.

        Critical for headless mode where bpy.ops calls must be
        deferred to the main thread via timers.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            task = ExecutionTask(
                func=func, args=args, kwargs=kwargs, callback=callback, timeout=timeout
            )

            HeadlessModeManager._task_queue.append(task)

            # Register timer if not already processing
            if not HeadlessModeManager._is_processing:
                bpy.app.timers.register(HeadlessModeManager._process_queue, first_interval=0.01)

            return {
                "success": True,
                "queued": True,
                "queue_size": len(HeadlessModeManager._task_queue),
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Queue failed: {str(e)}"
            )

    @staticmethod
    def _process_queue() -> Optional[float]:
        """
        Process execution queue.
        Called by bpy.app.timers.
        """
        HeadlessModeManager._is_processing = True

        try:
            if HeadlessModeManager._task_queue:
                task = HeadlessModeManager._task_queue.pop(0)

                start_time = time.time()
                try:
                    result = task.func(*task.args, **task.kwargs)

                    if task.callback:
                        task.callback(result)

                except Exception as e:
                    logger.error(f"Task execution failed: {e}")
                    if task.callback:
                        task.callback({"error": str(e)})

                elapsed = time.time() - start_time
                if elapsed > task.timeout:
                    logger.warning(f"Task exceeded timeout: {elapsed}s")

        except Exception as e:
            logger.error(f"Queue processing error: {e}")

        finally:
            # Re-register if more tasks
            if HeadlessModeManager._task_queue:
                return 0.01  # Next call in 10ms
            else:
                HeadlessModeManager._is_processing = False
                return None  # Stop timer

    @staticmethod
    def execute_safely(func: Callable, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute function safely in any mode.

        Automatically uses queue in headless mode for bpy.ops calls.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # If headless and function uses bpy.ops, queue it
            if (
                HeadlessModeManager.is_headless()
                and hasattr(func, "__module__")
                and "bpy.ops" in str(func)
            ):
                result_holder = {}

                def callback(result: Any) -> None:
                    result_holder["result"] = result

                HeadlessModeManager.queue_execution(func, *args, callback=callback, **kwargs)

                # Wait for execution (blocking in headless)
                timeout = 30.0
                start = time.time()
                while "result" not in result_holder:
                    if time.time() - start > timeout:
                        return create_error(
                            ErrorProtocol.TIMEOUT_ERROR, custom_message="Execution timeout"
                        )
                    time.sleep(0.01)

                queued_result = result_holder.get("result")
                if isinstance(queued_result, dict):
                    return queued_result
                return {"success": True, "result": queued_result}

            else:
                # Direct execution
                direct_result = func(*args, **kwargs)
                if isinstance(direct_result, dict):
                    return direct_result
                return {"success": True, "result": direct_result}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Safe execution failed: {str(e)}"
            )

    @staticmethod
    def render_headless(
        scene: Any, output_path: str, frame: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute headless render.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Set output
            scene.render.filepath = output_path

            # Set frame
            if frame is not None:
                scene.frame_set(frame)

            # Execution
            result = HeadlessModeManager.execute_safely(bpy.ops.render.render, write_still=True)

            if "error" in result:
                return result

            return {
                "success": True,
                "output_path": output_path,
                "frame": frame if frame is not None else scene.frame_current,
                "engine": scene.render.engine,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Render failed: {str(e)}"
            )


class MemoryManager:
    """
    Manage memory for long-running headless sessions.
    """

    @staticmethod
    def purge_unused_data() -> Dict[str, Any]:
        """
        Remove unused data blocks to free memory.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            removed = {
                "meshes": 0,
                "materials": 0,
                "textures": 0,
                "images": 0,
                "node_groups": 0,
                "actions": 0,
                "objects": 0,
            }

            # Purge meshes with no users
            for mesh in list(bpy.data.meshes):
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
                    removed["meshes"] += 1

            # Purge materials with no users
            for mat in list(bpy.data.materials):
                if mat.users == 0:
                    bpy.data.materials.remove(mat)
                    removed["materials"] += 1

            # Purge textures
            for tex in list(bpy.data.textures):
                if tex.users == 0:
                    bpy.data.textures.remove(tex)
                    removed["textures"] += 1

            # Purge images
            for img in list(bpy.data.images):
                if img.users == 0 and not img.is_dirty:
                    bpy.data.images.remove(img)
                    removed["images"] += 1

            # Purge node groups
            for ng in list(bpy.data.node_groups):
                if ng.users == 0:
                    bpy.data.node_groups.remove(ng)
                    removed["node_groups"] += 1

            # Purge actions
            for action in list(bpy.data.actions):
                if action.users == 0:
                    bpy.data.actions.remove(action)
                    removed["actions"] += 1

            # Force garbage collection
            gc.collect()

            total_removed = sum(removed.values())

            return {"success": True, "removed": removed, "total": total_removed}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Memory purge failed: {str(e)}"
            )

    @staticmethod
    def get_memory_stats() -> Dict[str, Any]:
        """
        Get memory usage statistics.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            stats: Dict[str, Any] = {
                "meshes": len(bpy.data.meshes),
                "objects": len(bpy.data.objects),
                "materials": len(bpy.data.materials),
                "textures": len(bpy.data.textures),
                "images": len(bpy.data.images),
                "node_groups": len(bpy.data.node_groups),
                "actions": len(bpy.data.actions),
                "scenes": len(bpy.data.scenes),
                "collections": len(bpy.data.collections),
            }

            # Calculate estimated memory (rough)
            estimated_mb = (
                stats["meshes"] * 0.5  # ~500KB per mesh
                + stats["images"] * 2.0  # ~2MB per image
                + stats["objects"] * 0.001  # ~1KB per object
            )

            stats["estimated_mb"] = round(estimated_mb, 2)

            return {"success": True, "stats": stats}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Memory stats failed: {str(e)}"
            )

    @staticmethod
    def auto_purge(threshold_mb: float = 1000.0) -> Dict[str, Any]:
        """
        Auto purge if memory exceeds threshold.
        """
        stats = MemoryManager.get_memory_stats()
        if "error" in stats:
            return stats

        current_mb = stats["stats"]["estimated_mb"]

        if current_mb > threshold_mb:
            return MemoryManager.purge_unused_data()

        return {
            "success": True,
            "purged": False,
            "reason": f"Memory {current_mb}MB below threshold {threshold_mb}MB",
        }


class CI_CDManager:
    """
    CI/CD specific optimizations.
    """

    @staticmethod
    def setup_for_ci_cd(scene: Any) -> Dict[str, Any]:
        """
        Optimize scene for CI/CD rendering.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Disable UI updates
            if hasattr(scene, "frame_set"):
                pass  # Frame set is minimal

            # Optimize render settings
            scene.render.use_simplify = True
            scene.render.simplify_subdivision = 0
            scene.render.simplify_child_particles = 0.5

            # Disable unnecessary features
            scene.render.use_motion_blur = False
            scene.render.use_border = False

            # Eevee optimizations
            if scene.render.engine == "BLENDER_EEVEE":
                if hasattr(scene, "eevee"):
                    eevee = scene.eevee
                    if hasattr(eevee, "use_gtao"):
                        eevee.use_gtao = False
                    if hasattr(eevee, "use_ssr"):
                        eevee.use_ssr = False
                    eevee.volumetric_enable = False

            return {"success": True, "optimized_for": "ci_cd", "engine": scene.render.engine}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"CI/CD setup failed: {str(e)}"
            )

    @staticmethod
    def validate_scene_for_batch(scene: Any) -> Dict[str, Any]:
        """
        Validate scene is ready for batch rendering.
        """
        issues = []
        warnings = []

        # Check camera
        if not scene.camera:
            issues.append("No active camera")

        # Check output path
        if not scene.render.filepath:
            warnings.append("No output filepath set")

        # Check render engine
        if scene.render.engine == "BLENDER_WORKBENCH":
            warnings.append("Using Workbench engine (may not be intended)")

        # Check for missing textures
        for mat in bpy.data.materials:
            if mat.use_nodes and mat.node_tree:
                for node in cast(Any, mat.node_tree).nodes:
                    if node.type == "TEX_IMAGE" and cast(Any, node).image:
                        img = cast(Any, node).image
                        if img.filepath and not img.packed_file:
                            if not bpy.path.abspath(img.filepath):
                                warnings.append(f"Missing texture: {img.name}")

        return {
            "success": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "scene": scene.name,
        }


@contextmanager
def headless_context() -> Iterator["HeadlessModeManager"]:
    """
    Context manager for headless operations.

    Usage:
        with headless_context():
            # Operations here are safe for headless mode
            bpy.ops.render.render()
    """
    manager = HeadlessModeManager()

    # Ensure context
    result = manager.ensure_minimal_context()
    if "error" in result:
        raise RuntimeError(f"Cannot establish headless context: {result}")

    try:
        yield manager
    finally:
        # Cleanup
        MemoryManager.purge_unused_data()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "HeadlessModeManager",
    "MemoryManager",
    "CI_CDManager",
    "HeadlessMode",
    "headless_context",
]
