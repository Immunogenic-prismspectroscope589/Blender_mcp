"""
Manage Physics - V1.0.0 Refactored

Safe, thread-aware physics and simulation operations with:
- Thread safety (main thread execution for operators)
- Context validation via ContextManagerV3
- Crash prevention for physics operators
- Structured error handling with ErrorProtocol
- Blender 5.0+ compatibility

High Mode Philosophy: Maximum power, maximum safety.
"""

from typing import Any, Dict, Optional, Tuple, cast

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.resolver import resolve_name
from ..core.thread_safety import execute_on_main_thread, ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.versioning import BlenderCompatibility
from ..core.validation_utils import ValidationUtils
from ..dispatcher import register_handler

from ..core.parameter_validator import validated_handler
from ..core.enums import PhysicsAction

logger = get_logger()


@register_handler(
    "manage_physics",
    priority=30,
    schema={
        "type": "object",
        "title": "Physics & Simulation (STANDARD)",
        "description": (
            "STANDARD — Add and configure physics/simulation modifiers: cloth, rigid body, "
            "soft body, fluid domain, particle systems.\n\n"
            "Blender 5.0+ compatible. Use BAKE_ALL to pre-compute simulation cache.\n"
            "ACTIONS: ADD_CLOTH, ADD_RIGID_BODY, ADD_SOFT_BODY, ADD_FLUID_DOMAIN, "
            "ADD_PARTICLE_SYSTEM, BAKE_ALL, CLEAR_CACHE, SET_PRESET"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                PhysicsAction, "Physics action to perform"
            ),
            "object_name": {"type": "string", "description": "Target object"},
            "preset": {"type": "string", "enum": ["SILK", "DENIM", "LEATHER", "COTTON", "RUBBER"]},
            "cache_path": {"type": "string", "description": "Cache directory path"},
            "steps_per_second": {
                "type": "integer",
                "description": "Simulation steps per second (auto-converted for Blender 5.0+)",
            },
            "substeps_per_frame": {
                "type": "integer",
                "description": "Substeps per frame (Blender 5.0+ native)",
            },
        },
        "required": ["action"],
    },
    actions=[a.value for a in PhysicsAction],
    category="physics",
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in PhysicsAction])
def manage_physics(action: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    """
    Complete physics simulation automation with Blender 5.0+ compatibility.

    Categories:
    - Rigid Body: World setup, add/remove bodies, baking
    - Cloth: Presets (silk, denim, leather), pinning, baking
    - Fluid: Domain, flow, effector setup, baking
    - Particles: Hair, fur, explosion, emission systems
    - Force Fields: Wind, vortex, turbulence, magnetic
    - Soft Body: Jelly, bouncing objects
    - Collision: Collision shape configuration

    CRITICAL: All bpy.ops calls execute on main thread for thread safety.
    """
    if not action:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="UNKNOWN",
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    try:
        # Rigid Body Actions
        if action == PhysicsAction.RIGID_BODY_WORLD_SETUP.value:
            return _handle_rigid_body_world_setup(**params)
        elif action == PhysicsAction.RIGID_BODY_ADD.value:
            return _handle_rigid_body_add(**params)
        elif action == PhysicsAction.RIGID_BODY_REMOVE.value:
            return _handle_rigid_body_remove(**params)
        elif action == PhysicsAction.RIGID_BODY_BAKE.value:
            return _handle_rigid_body_bake(**params)
        elif action == PhysicsAction.RIGID_BODY_CACHE_CLEAR.value:
            return _handle_cache_clear("RIGID_BODY")

        # Cloth Actions
        elif action == PhysicsAction.CLOTH_SIM_SETUP.value:
            return _handle_cloth_setup(**params)
        elif action == PhysicsAction.CLOTH_PRESET.value:
            return _handle_cloth_preset(**params)
        elif action == PhysicsAction.CLOTH_PIN.value:
            return _handle_cloth_pin(**params)
        elif action == PhysicsAction.CLOTH_UNPIN.value:
            return _handle_cloth_unpin(**params)
        elif action == PhysicsAction.CLOTH_BAKE.value:
            return _handle_cloth_bake(**params)
        elif action == PhysicsAction.CLOTH_CACHE_CLEAR.value:
            return _handle_cache_clear("CLOTH", params.get("object_name"))

        # Fluid Actions
        elif action == PhysicsAction.FLUID_DOMAIN_SETUP.value:
            return _handle_fluid_domain_setup(**params)
        elif action == PhysicsAction.FLUID_ADD_FLOW.value:
            return _handle_fluid_add_flow(**params)
        elif action == PhysicsAction.FLUID_ADD_EFFECTOR.value:
            return _handle_fluid_add_effector(**params)
        elif action == PhysicsAction.FLUID_BAKE.value:
            return _handle_fluid_bake(**params)
        elif action == PhysicsAction.FLUID_CACHE_CLEAR.value:
            return _handle_cache_clear("FLUID")

        # Particle Actions
        elif action == PhysicsAction.PARTICLE_HAIR.value:
            return _handle_particle_hair(**params)
        elif action == PhysicsAction.PARTICLE_FUR.value:
            return _handle_particle_fur(**params)
        elif action == PhysicsAction.PARTICLE_EXPLOSION.value:
            return _handle_particle_explosion(**params)
        elif action == PhysicsAction.PARTICLE_EMISSION.value:
            return _handle_particle_emission(**params)
        elif action == PhysicsAction.PARTICLE_BAKE.value:
            return _handle_particle_bake(**params)

        # Force Field Actions
        elif action == PhysicsAction.FORCE_FIELD_ADD.value:
            return _handle_force_field_add(**params)
        elif action == PhysicsAction.FORCE_FIELD_CONFIGURE.value:
            return _handle_force_field_configure(**params)
        elif action == PhysicsAction.FORCE_FIELD_REMOVE.value:
            return _handle_force_field_remove(**params)

        # Soft Body Actions
        elif action == PhysicsAction.SOFT_BODY_SETUP.value:
            return _handle_soft_body_setup(**params)
        elif action == PhysicsAction.SOFT_BODY_BAKE.value:
            return _handle_soft_body_bake(**params)

        # Collision Actions
        elif action == PhysicsAction.COLLISION_SETUP.value:
            return _handle_collision_setup(**params)

        # General Actions
        elif action == PhysicsAction.SIMULATION_PLAY.value:
            return _handle_simulation_play()
        elif action == PhysicsAction.SIMULATION_STOP.value:
            return _handle_simulation_stop()
        elif action == PhysicsAction.ALL_BAKE.value:
            return _handle_all_bake(**params)
        elif action == PhysicsAction.ALL_CACHE_CLEAR.value:
            return _handle_all_cache_clear()
        else:
            return ResponseBuilder.error(
                handler="manage_physics",
                action=action,
                error_code="INVALID_PARAMETER_VALUE",
                message=f"Unknown action: {action}",
            )
    except Exception as e:
        logger.error(f"manage_physics.{action} failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics", action=action, error_code="EXECUTION_ERROR", message=str(e)
        )


# =============================================================================
# PARAMETER VALIDATION HELPERS
# =============================================================================


def _coerce_int(
    value: Any, default: int = 0, min_val: Optional[int] = None, max_val: Optional[int] = None
) -> int:
    """Coerce value to integer with bounds."""
    try:
        result = int(float(value))
        if min_val is not None:
            result = max(result, min_val)
        if max_val is not None:
            result = min(result, max_val)
        return result
    except (TypeError, ValueError):
        return default


def _coerce_float(
    value: Any,
    default: float = 0.0,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> float:
    """Coerce value to float with bounds."""
    try:
        result = float(value)
        if min_val is not None:
            result = max(result, min_val)
        if max_val is not None:
            result = min(result, max_val)
        return result
    except (TypeError, ValueError):
        return default


def _get_object(
    obj_name: Optional[str], required_type: Optional[str] = None
) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """Get object by name with optional type checking."""
    obj = None
    if obj_name:
        obj = resolve_name(obj_name)
    if not obj:
        obj = ContextManagerV3.get_active_object()

    if not obj:
        return None, ResponseBuilder.error(
            handler="manage_physics",
            action="UNKNOWN",
            error_code="NO_ACTIVE_OBJECT",
            message="No active object found",
        )

    if required_type and obj.type != required_type:
        return None, ResponseBuilder.error(
            handler="manage_physics",
            action="UNKNOWN",
            error_code="WRONG_OBJECT_TYPE",
            message=f"Expected {required_type}, got {obj.type}",
        )

    return obj, None


# =============================================================================
# RIGID BODY SYSTEM - Thread Safe
# =============================================================================


def _handle_rigid_body_world_setup(**params: Any) -> Dict[str, Any]:
    """
    Configure rigid body world settings with Blender 5.0+ compatibility.

    CRITICAL: Uses main thread execution for rigidbody.world_add.
    """
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_WORLD_SETUP",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_WORLD_SETUP",
            error_code="NO_SCENE",
            message="No scene available",
        )

    def configure_world() -> Dict[str, Any]:
        # Enable rigid body world
        if not scene.rigidbody_world:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.rigidbody.world_add()

        rbw = scene.rigidbody_world
        rbw.enabled = True
        rbw.use_split_impulse = True

        # Handle steps_per_second vs substeps_per_frame (Blender 5.0+)
        steps = params.get("steps_per_second")
        substeps = params.get("substeps_per_frame")

        if substeps is not None:
            substeps_val = _coerce_int(substeps, default=10, min_val=1, max_val=1000)
            rbw.substeps_per_frame = substeps_val
        elif steps is not None:
            # Legacy steps_per_second - convert to substeps_per_frame
            BlenderCompatibility.set_rigid_body_world_attr(rbw, "steps_per_second", steps)
        else:
            # Default
            if BlenderCompatibility.is_blender5():
                rbw.substeps_per_frame = 10
            else:
                rbw.steps_per_second = 60

        # Solver iterations
        rbw.solver_iterations = _coerce_int(
            params.get("solver_iterations", 10), min_val=1, max_val=100
        )

        # Gravity - Blender 5.0+: Use scene.gravity
        gravity = params.get("gravity", [0, 0, -9.81])
        if isinstance(gravity, (list, tuple)) and len(gravity) == 3:
            scene.gravity = gravity
            scene.use_gravity = True

        # Cache settings
        cache_path = params.get("cache_path")
        if cache_path:
            rbw.point_cache.use_disk_cache = True
            rbw.point_cache.filepath = cache_path

        # Return actual values set
        actual_steps = BlenderCompatibility.get_rigid_body_world_attr(rbw, "steps_per_second") or (
            getattr(rbw, "substeps_per_frame", 1) * 60
        )
        gravity_value = list(scene.gravity) if hasattr(scene, "gravity") else [0, 0, -9.81]

        return ResponseBuilder.success(
            handler="manage_physics",
            action="RIGID_BODY_WORLD_SETUP",
            data={
                "steps_per_second": actual_steps,
                "substeps_per_frame": getattr(rbw, "substeps_per_frame", None),
                "solver_iterations": rbw.solver_iterations,
                "gravity": gravity_value,
                "blender_50_plus": BlenderCompatibility.is_blender5(),
            },
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(configure_world, timeout=30.0))
    except Exception as e:
        logger.error(f"RIGID_BODY_WORLD_SETUP failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_WORLD_SETUP",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_rigid_body_add(**params: Any) -> Dict[str, Any]:
    """Add rigid body to object with validation and thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_ADD",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    if obj.name not in bpy.data.objects:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_ADD",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{obj.name}' not found",
        )

    def add_rigid_body() -> Dict[str, Any]:
        ContextManagerV3.set_active_object(obj)

        body_type = params.get("body_type", "ACTIVE")
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
        ):
            safe_ops.rigidbody.object_add(type=body_type)

        # Configure
        if obj.rigid_body:
            rb = obj.rigid_body
            rb.mass = _coerce_float(params.get("mass", 1.0), min_val=0.001)
            rb.friction = _coerce_float(params.get("friction", 0.5), min_val=0.0, max_val=1.0)
            rb.restitution = _coerce_float(params.get("restitution", 0.0), min_val=0.0, max_val=1.0)
            rb.use_margin = True
            rb.collision_margin = _coerce_float(params.get("margin", 0.04), min_val=0.0)

            # Collision shape
            shape = params.get("collision_shape", "CONVEX_HULL")
            valid_shapes = [
                "BOX",
                "SPHERE",
                "CAPSULE",
                "CYLINDER",
                "CONE",
                "CONVEX_HULL",
                "MESH",
                "COMPOUND",
            ]
            if shape in valid_shapes:
                rb.collision_shape = shape

        return ResponseBuilder.success(
            handler="manage_physics",
            action="RIGID_BODY_ADD",
            data={
                "object": obj.name,
                "body_type": obj.rigid_body.type,
                "mass": obj.rigid_body.mass,
                "collision_shape": obj.rigid_body.collision_shape,
            },
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(add_rigid_body, timeout=30.0))
    except Exception as e:
        logger.error(f"RIGID_BODY_ADD failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_ADD",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_rigid_body_remove(**params: Any) -> Dict[str, Any]:
    """Remove rigid body from object with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_REMOVE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    if obj.name not in bpy.data.objects:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_REMOVE",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{obj.name}' not found",
        )

    def remove_rigid_body() -> Dict[str, Any]:
        ContextManagerV3.set_active_object(obj)
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
        ):
            safe_ops.rigidbody.object_remove()
        return ResponseBuilder.success(
            handler="manage_physics",
            action="RIGID_BODY_REMOVE",
            data={"object": obj.name, "removed": True},
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(remove_rigid_body, timeout=30.0))
    except Exception as e:
        logger.error(f"RIGID_BODY_REMOVE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_REMOVE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_rigid_body_bake(**params: Any) -> Dict[str, Any]:
    """Bake rigid body simulation with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_BAKE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_BAKE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    if not scene.rigidbody_world:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_BAKE",
            error_code="EXECUTION_ERROR",
            message="Rigid body world not set up",
        )

    def bake_rigid_body() -> Dict[str, Any]:
        frame_start = _coerce_int(params.get("frame_start", scene.frame_start))
        frame_end = _coerce_int(params.get("frame_end", scene.frame_end))

        # Set cache range
        scene.rigidbody_world.point_cache.frame_start = frame_start
        scene.rigidbody_world.point_cache.frame_end = frame_end

        # Bake
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.ptcache.bake_all(bake=True)

        return ResponseBuilder.success(
            handler="manage_physics",
            action="RIGID_BODY_BAKE",
            data={"frame_start": frame_start, "frame_end": frame_end, "baked": True},
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(bake_rigid_body, timeout=300.0))
    except Exception as e:
        logger.error(f"RIGID_BODY_BAKE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="RIGID_BODY_BAKE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


# =============================================================================
# CLOTH SIMULATION - Thread Safe
# =============================================================================

CLOTH_PRESETS: dict[str, dict[str, float]] = {
    "SILK": {
        "tension_stiffness": 5,
        "compression_stiffness": 5,
        "shear_stiffness": 5,
        "bending_stiffness": 0.05,
        "air_damping": 5,
    },
    "DENIM": {
        "tension_stiffness": 80,
        "compression_stiffness": 80,
        "shear_stiffness": 60,
        "bending_stiffness": 20,
        "air_damping": 5,
    },
    "LEATHER": {
        "tension_stiffness": 100,
        "compression_stiffness": 100,
        "shear_stiffness": 80,
        "bending_stiffness": 50,
        "air_damping": 3,
    },
    "COTTON": {
        "tension_stiffness": 15,
        "compression_stiffness": 15,
        "shear_stiffness": 10,
        "bending_stiffness": 0.5,
        "air_damping": 3,
    },
    "RUBBER": {
        "tension_stiffness": 200,
        "compression_stiffness": 200,
        "shear_stiffness": 150,
        "bending_stiffness": 100,
        "air_damping": 10,
    },
}


def _handle_cloth_setup(**params: Any) -> Dict[str, Any]:
    """Setup cloth simulation on object with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_SIM_SETUP",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name, "MESH")
    if error:
        return error

    if obj.name not in bpy.data.objects:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_SIM_SETUP",
            error_code="OBJECT_NOT_FOUND",
            message=f"Object '{obj.name}' not found",
        )

    def setup_cloth_modifier() -> Dict[str, Any]:
        ContextManagerV3.set_active_object(obj)

        # Add cloth modifier
        cloth = obj.modifiers.new(name="Cloth", type="CLOTH")

        # Apply preset if specified
        preset = params.get("preset")
        if preset and preset in CLOTH_PRESETS:
            settings = CLOTH_PRESETS[preset]
            cl = cloth.settings

            cl.tension_stiffness = settings["tension_stiffness"]
            cl.compression_stiffness = settings["compression_stiffness"]
            cl.shear_stiffness = settings["shear_stiffness"]
            cl.bending_stiffness = settings["bending_stiffness"]
            cl.air_damping = settings["air_damping"]

        # Quality
        quality = _coerce_int(params.get("quality", 12), default=12, min_val=1, max_val=30)
        cloth.settings.quality = quality

        # Mass
        mass = _coerce_float(params.get("mass", 0.3), default=0.3, min_val=0.001)
        cloth.settings.mass = mass

        # Cache
        cache_path = params.get("cache_path")
        if cache_path:
            cloth.point_cache.use_disk_cache = True
            cloth.point_cache.filepath = cache_path

        return ResponseBuilder.success(
            handler="manage_physics",
            action="CLOTH_SIM_SETUP",
            data={
                "object": obj.name,
                "preset": preset,
                "quality": cloth.settings.quality,
                "mass": cloth.settings.mass,
            },
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(setup_cloth_modifier, timeout=30.0))
    except Exception as e:
        logger.error(f"CLOTH_SIM_SETUP failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_SIM_SETUP",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_cloth_preset(**params: Any) -> Dict[str, Any]:
    """Apply cloth preset to existing cloth simulation."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_PRESET",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    # Find cloth modifier
    cloth = None
    for mod in obj.modifiers:
        if mod.type == "CLOTH":
            cloth = mod
            break

    if not cloth:
        # Add cloth first
        return _handle_cloth_setup(**params)

    preset = params.get("preset", "COTTON")
    if preset not in CLOTH_PRESETS:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_PRESET",
            error_code="INVALID_PARAMETER_VALUE",
            message=f"Unknown preset: {preset}",
        )

    def apply_cloth_preset() -> Dict[str, Any]:
        settings = CLOTH_PRESETS[preset]
        cl = cloth.settings

        cl.tension_stiffness = settings["tension_stiffness"]
        cl.compression_stiffness = settings["compression_stiffness"]
        cl.shear_stiffness = settings["shear_stiffness"]
        cl.bending_stiffness = settings["bending_stiffness"]
        cl.air_damping = settings["air_damping"]

        return ResponseBuilder.success(
            handler="manage_physics",
            action="CLOTH_PRESET",
            data={"object": obj.name, "preset_applied": preset},
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(apply_cloth_preset, timeout=30.0))
    except Exception as e:
        logger.error(f"CLOTH_PRESET failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_PRESET",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_cloth_pin(**params: Any) -> Dict[str, Any]:
    """Pin cloth vertices to target."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_PIN",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name, "MESH")
    if error:
        return error

    vertex_group = params.get("vertex_group")

    def pin_cloth_vertices() -> Dict[str, Any]:
        # Create vertex group if not exists
        if vertex_group and vertex_group not in obj.vertex_groups:
            obj.vertex_groups.new(name=vertex_group)

        # Find cloth modifier and configure
        for mod in obj.modifiers:
            if mod.type == "CLOTH":
                if vertex_group:
                    mod.settings.vertex_group_mass = vertex_group
                break

        return ResponseBuilder.success(
            handler="manage_physics",
            action="CLOTH_PIN",
            data={"object": obj.name, "pinned": True, "vertex_group": vertex_group},
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(pin_cloth_vertices, timeout=30.0))
    except Exception as e:
        logger.error(f"CLOTH_PIN failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_PIN",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_cloth_unpin(**params: Any) -> Dict[str, Any]:
    """Remove cloth pinning."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_UNPIN",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    def unpin_cloth_vertices() -> Dict[str, Any]:
        for mod in obj.modifiers:
            if mod.type == "CLOTH":
                mod.settings.vertex_group_mass = ""
                break

        return ResponseBuilder.success(
            handler="manage_physics",
            action="CLOTH_UNPIN",
            data={"object": obj.name, "unpinned": True},
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(unpin_cloth_vertices, timeout=30.0))
    except Exception as e:
        logger.error(f"CLOTH_UNPIN failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_UNPIN",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_cloth_bake(**params: Any) -> Dict[str, Any]:
    """Bake cloth simulation with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_BAKE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_BAKE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    frame_start = _coerce_int(params.get("frame_start", scene.frame_start))
    frame_end = _coerce_int(params.get("frame_end", scene.frame_end))

    def bake_cloth() -> Dict[str, Any]:
        # Find cloth modifier
        for mod in obj.modifiers:
            if mod.type == "CLOTH":
                mod.point_cache.frame_start = frame_start
                mod.point_cache.frame_end = frame_end
                mod.point_cache.use_disk_cache = params.get("disk_cache", True)

                # Bake
                ContextManagerV3.set_active_object(obj)
                with ContextManagerV3.temp_override(
                    area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                ):
                    safe_ops.ptcache.bake(bake=True)

                return ResponseBuilder.success(
                    handler="manage_physics",
                    action="CLOTH_BAKE",
                    data={
                        "object": obj.name,
                        "frame_start": frame_start,
                        "frame_end": frame_end,
                        "baked": True,
                    },
                )

        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_BAKE",
            error_code="EXECUTION_ERROR",
            message="No cloth modifier found on object",
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(bake_cloth, timeout=300.0))
    except Exception as e:
        logger.error(f"CLOTH_BAKE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CLOTH_BAKE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


# =============================================================================
# FLUID SIMULATION - Thread Safe
# =============================================================================


def _handle_fluid_domain_setup(**params: Any) -> Dict[str, Any]:
    """Setup fluid simulation domain."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_DOMAIN_SETUP",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        # Add fluid modifier
        fluid = obj.modifiers.new(name="Fluid", type="FLUID")
        fluid.fluid_type = "DOMAIN"

        settings = fluid.domain_settings

        # Domain type
        domain_type = params.get("domain_type", "LIQUID")
        if domain_type in ["LIQUID", "GAS", "FLUID"]:
            settings.domain_type = domain_type

        # Resolution
        settings.resolution_max = _coerce_int(params.get("resolution", 64), min_val=1, max_val=1000)
        settings.time_scale = _coerce_float(params.get("time_scale", 1.0), min_val=0.001)

        # Cache
        cache_path = params.get("cache_path")
        if cache_path:
            settings.cache_directory = cache_path
            settings.cache_type = "MODULAR"

        # Adaptive domain
        settings.use_adaptive_domain = params.get("adaptive", False)

        return ResponseBuilder.success(
            handler="manage_physics",
            action="FLUID_DOMAIN_SETUP",
            data={
                "object": obj.name,
                "domain_type": settings.domain_type,
                "resolution": settings.resolution_max,
            },
        )
    except Exception as e:
        logger.error(f"FLUID_DOMAIN_SETUP failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_DOMAIN_SETUP",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_fluid_add_flow(**params: Any) -> Dict[str, Any]:
    """Add fluid flow source."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_ADD_FLOW",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        fluid = obj.modifiers.new(name="Fluid_Flow", type="FLUID")
        fluid.fluid_type = "FLOW"

        settings = fluid.flow_settings

        flow_type = params.get("flow_type", "LIQUID")
        if flow_type in ["LIQUID", "GAS", "SMOKE", "FIRE", "FLUID"]:
            settings.flow_type = flow_type

        behavior = params.get("behavior", "INFLOW")
        if behavior in ["INFLOW", "OUTFLOW", "GEOMETRY"]:
            settings.flow_behavior = behavior

        return ResponseBuilder.success(
            handler="manage_physics",
            action="FLUID_ADD_FLOW",
            data={
                "object": obj.name,
                "flow_type": settings.flow_type,
                "behavior": settings.flow_behavior,
            },
        )
    except Exception as e:
        logger.error(f"FLUID_ADD_FLOW failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_ADD_FLOW",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_fluid_add_effector(**params: Any) -> Dict[str, Any]:
    """Add fluid effector (obstacle)."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_ADD_EFFECTOR",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        fluid = obj.modifiers.new(name="Fluid_Effector", type="FLUID")
        fluid.fluid_type = "EFFECTOR"

        settings = fluid.effector_settings
        effector_type = params.get("effector_type", "OBSTACLE")
        if effector_type in ["OBSTACLE", "GUIDE", "WIND", "FORCE"]:
            settings.effector_type = effector_type

        return ResponseBuilder.success(
            handler="manage_physics",
            action="FLUID_ADD_EFFECTOR",
            data={"object": obj.name, "effector_type": settings.effector_type},
        )
    except Exception as e:
        logger.error(f"FLUID_ADD_EFFECTOR failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_ADD_EFFECTOR",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_fluid_bake(**params: Any) -> Dict[str, Any]:
    """Bake fluid simulation with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_BAKE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_BAKE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    # Find fluid domain
    domain = None
    for obj in scene.objects:
        for mod in obj.modifiers:
            if mod.type == "FLUID" and mod.fluid_type == "DOMAIN":
                domain = obj
                break
        if domain:
            break

    if not domain:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_BAKE",
            error_code="EXECUTION_ERROR",
            message="No fluid domain found",
        )

    def bake_fluid() -> Dict[str, Any]:
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.fluid.bake_all()
        return ResponseBuilder.success(
            handler="manage_physics",
            action="FLUID_BAKE",
            data={"domain": domain.name, "baked": True},
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(bake_fluid, timeout=600.0))
    except Exception as e:
        logger.error(f"FLUID_BAKE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FLUID_BAKE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


# =============================================================================
# PARTICLE SYSTEMS - Thread Safe
# =============================================================================


def _handle_particle_hair(**params: Any) -> Dict[str, Any]:
    """Setup hair particle system."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_HAIR",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name, "MESH")
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        # Create particle system
        obj.modifiers.new(name="Hair", type="PARTICLE_SYSTEM")
        psys = obj.particle_systems[-1]
        settings = psys.settings

        settings.type = "HAIR"
        settings.count = _coerce_int(params.get("count", 1000), min_val=1, max_val=1000000)
        settings.hair_length = _coerce_float(params.get("length", 0.3), min_val=0.001)
        settings.hair_step = _coerce_int(params.get("segments", 5), min_val=1, max_val=50)

        # Material - coerce to int
        material_param = params.get("material", 1)
        settings.material = _coerce_int(material_param, default=1, min_val=0)

        # Render settings
        settings.render_type = "PATH"
        settings.use_hair_bspline = True

        return ResponseBuilder.success(
            handler="manage_physics",
            action="PARTICLE_HAIR",
            data={
                "object": obj.name,
                "type": "HAIR",
                "count": settings.count,
                "length": settings.hair_length,
                "material": settings.material,
            },
        )
    except Exception as e:
        logger.error(f"PARTICLE_HAIR failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_HAIR",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_particle_fur(**params: Any) -> Dict[str, Any]:
    """Setup fur particle system."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_FUR",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name, "MESH")
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        obj.modifiers.new(name="Fur", type="PARTICLE_SYSTEM")
        psys = obj.particle_systems[-1]
        settings = psys.settings

        settings.type = "HAIR"
        settings.count = _coerce_int(params.get("count", 50000), min_val=1)
        settings.hair_length = _coerce_float(params.get("length", 0.05), min_val=0.001)
        settings.hair_step = 3

        # Dense fur settings
        settings.child_type = "INTERPOLATED"
        settings.child_nbr = 10
        settings.rendered_child_count = 100
        settings.clump_factor = 0.5

        return ResponseBuilder.success(
            handler="manage_physics",
            action="PARTICLE_FUR",
            data={
                "object": obj.name,
                "type": "FUR",
                "count": settings.count,
                "children": settings.child_nbr,
            },
        )
    except Exception as e:
        logger.error(f"PARTICLE_FUR failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_FUR",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_particle_explosion(**params: Any) -> Dict[str, Any]:
    """Setup explosion particle system."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_EXPLOSION",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        obj.modifiers.new(name="Explosion", type="PARTICLE_SYSTEM")
        psys = obj.particle_systems[-1]
        settings = psys.settings

        settings.type = "EMITTER"
        settings.count = _coerce_int(params.get("count", 1000), min_val=1)
        settings.frame_start = _coerce_float(params.get("frame_start", 1))
        settings.frame_end = _coerce_float(params.get("frame_end", 10))
        settings.lifetime = _coerce_float(params.get("lifetime", 50), min_val=1)

        settings.physics_type = "NEWTON"
        settings.normal_factor = _coerce_float(params.get("velocity", 10.0))
        settings.factor_random = _coerce_float(params.get("randomness", 0.5))
        settings.mass = 0.1

        settings.particleSize = 0.1
        settings.size_random = 0.5

        return ResponseBuilder.success(
            handler="manage_physics",
            action="PARTICLE_EXPLOSION",
            data={
                "object": obj.name,
                "type": "EXPLOSION",
                "count": settings.count,
                "velocity": settings.normal_factor,
            },
        )
    except Exception as e:
        logger.error(f"PARTICLE_EXPLOSION failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_EXPLOSION",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_particle_emission(**params: Any) -> Dict[str, Any]:
    """Setup standard emission particle system."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_EMISSION",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        obj.modifiers.new(name="Emission", type="PARTICLE_SYSTEM")
        psys = obj.particle_systems[-1]
        settings = psys.settings

        settings.type = "EMITTER"
        settings.count = _coerce_int(params.get("count", 1000), min_val=1)
        settings.frame_start = _coerce_float(params.get("frame_start", 1))
        settings.frame_end = _coerce_float(params.get("frame_end", 250))
        settings.lifetime = _coerce_float(params.get("lifetime", 50), min_val=1)

        settings.normal_factor = _coerce_float(params.get("normal_velocity", 1.0))
        settings.factor_random = _coerce_float(params.get("randomness", 0.0))

        return ResponseBuilder.success(
            handler="manage_physics",
            action="PARTICLE_EMISSION",
            data={"object": obj.name, "type": "EMITTER", "count": settings.count},
        )
    except Exception as e:
        logger.error(f"PARTICLE_EMISSION failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_EMISSION",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_particle_bake(**params: Any) -> Dict[str, Any]:
    """Bake particle system with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_BAKE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    if not obj.particle_systems:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_BAKE",
            error_code="EXECUTION_ERROR",
            message="No particle systems on object",
        )

    psys_name = params.get("system_name")

    def bake_particles() -> Dict[str, Any]:
        for psys in obj.particle_systems:
            if psys_name and psys.name != psys_name:
                continue

            ContextManagerV3.set_active_object(obj)
            with ContextManagerV3.temp_override(
                area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
            ):
                safe_ops.object.particle_system_bake()

            return ResponseBuilder.success(
                handler="manage_physics",
                action="PARTICLE_BAKE",
                data={"object": obj.name, "system": psys.name, "baked": True},
            )

        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_BAKE",
            error_code="EXECUTION_ERROR",
            message="Particle system not found",
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(bake_particles, timeout=300.0))
    except Exception as e:
        logger.error(f"PARTICLE_BAKE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="PARTICLE_BAKE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


# =============================================================================
# FORCE FIELDS - Thread Safe
# =============================================================================


def _handle_force_field_add(**params: Any) -> Dict[str, Any]:
    """Add force field to scene with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FORCE_FIELD_ADD",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    field_type = params.get("field_type", "WIND")
    location = params.get("location", [0, 0, 0])

    def add_force_field() -> Dict[str, Any]:
        # Create empty with force field
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.object.effector_add(
                type=field_type,
                radius=_coerce_float(params.get("radius", 1.0)),
                enter_editmode=False,
                align="WORLD",
                location=location,
            )

        field_obj = ContextManagerV3.get_active_object()
        if not field_obj:
            return ResponseBuilder.error(
                handler="manage_physics",
                action="FORCE_FIELD_ADD",
                error_code="CREATION_FAILED",
                message="Failed to create force field object",
            )
        field_obj.name = f"Force_{field_type}"

        # Configure strength
        if field_obj.field:
            field_obj.field.strength = _coerce_float(params.get("strength", 1.0))
            field_obj.field.flow = _coerce_float(params.get("flow", 0.0))
            field_obj.field.noise = _coerce_float(params.get("noise", 0.0))

        return ResponseBuilder.success(
            handler="manage_physics",
            action="FORCE_FIELD_ADD",
            data={
                "field": field_obj.name,
                "type": field_type,
                "strength": field_obj.field.strength if field_obj.field else 0,
            },
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(add_force_field, timeout=30.0))
    except Exception as e:
        logger.error(f"FORCE_FIELD_ADD failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FORCE_FIELD_ADD",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_force_field_configure(**params: Any) -> Dict[str, Any]:
    """Configure existing force field."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FORCE_FIELD_CONFIGURE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    if not obj or not obj.field:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FORCE_FIELD_CONFIGURE",
            error_code="WRONG_OBJECT_TYPE",
            message="Object is not a force field",
        )

    try:
        if "strength" in params:
            obj.field.strength = _coerce_float(params["strength"])
        if "flow" in params:
            obj.field.flow = _coerce_float(params["flow"])
        if "noise" in params:
            obj.field.noise = _coerce_float(params["noise"])
        if "radius" in params:
            obj.field.falloff_power = _coerce_float(params["radius"])

        return ResponseBuilder.success(
            handler="manage_physics",
            action="FORCE_FIELD_CONFIGURE",
            data={"field": obj.name, "strength": obj.field.strength, "flow": obj.field.flow},
        )
    except Exception as e:
        logger.error(f"FORCE_FIELD_CONFIGURE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FORCE_FIELD_CONFIGURE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_force_field_remove(**params: Any) -> Dict[str, Any]:
    """Remove force field."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FORCE_FIELD_REMOVE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    try:
        obj.field.type = "NONE"
        return ResponseBuilder.success(
            handler="manage_physics", action="FORCE_FIELD_REMOVE", data={"field_removed": obj.name}
        )
    except Exception as e:
        logger.error(f"FORCE_FIELD_REMOVE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="FORCE_FIELD_REMOVE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


# =============================================================================
# SOFT BODY - Thread Safe
# =============================================================================


def _handle_soft_body_setup(**params: Any) -> Dict[str, Any]:
    """Setup soft body simulation."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SOFT_BODY_SETUP",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name, "MESH")
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        # Add soft body
        soft = obj.modifiers.new(name="Soft_Body", type="SOFT_BODY")

        settings = soft.settings
        settings.mass = _coerce_float(params.get("mass", 1.0), min_val=0.001)
        settings.friction = _coerce_float(params.get("friction", 0.5))
        settings.speed = _coerce_float(params.get("speed", 1.0))

        # Goal (pinning)
        settings.use_goal = params.get("use_goal", True)
        settings.goal_default = _coerce_float(params.get("goal_strength", 0.7))

        return ResponseBuilder.success(
            handler="manage_physics",
            action="SOFT_BODY_SETUP",
            data={"object": obj.name, "mass": settings.mass, "friction": settings.friction},
        )
    except Exception as e:
        logger.error(f"SOFT_BODY_SETUP failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SOFT_BODY_SETUP",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_soft_body_bake(**params: Any) -> Dict[str, Any]:
    """Bake soft body simulation with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SOFT_BODY_BAKE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name)
    if error:
        return error

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SOFT_BODY_BAKE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    frame_start = _coerce_int(params.get("frame_start", scene.frame_start))
    frame_end = _coerce_int(params.get("frame_end", scene.frame_end))

    def bake_soft_body() -> Dict[str, Any]:
        for mod in obj.modifiers:
            if mod.type == "SOFT_BODY":
                mod.point_cache.frame_start = frame_start
                mod.point_cache.frame_end = frame_end

                ContextManagerV3.set_active_object(obj)
                with ContextManagerV3.temp_override(
                    area_type="VIEW_3D", active_object=obj, selected_objects=[obj]
                ):
                    safe_ops.ptcache.bake(bake=True)

                return ResponseBuilder.success(
                    handler="manage_physics",
                    action="SOFT_BODY_BAKE",
                    data={
                        "object": obj.name,
                        "baked": True,
                        "frames": f"{frame_start}-{frame_end}",
                    },
                )

        return ResponseBuilder.error(
            handler="manage_physics",
            action="SOFT_BODY_BAKE",
            error_code="EXECUTION_ERROR",
            message="No soft body modifier found",
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(bake_soft_body, timeout=300.0))
    except Exception as e:
        logger.error(f"SOFT_BODY_BAKE failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SOFT_BODY_BAKE",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


# =============================================================================
# COLLISION - Thread Safe
# =============================================================================


def _handle_collision_setup(**params: Any) -> Dict[str, Any]:
    """Setup collision for object."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="COLLISION_SETUP",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    obj_name = params.get("object_name")
    obj, error = _get_object(obj_name, "MESH")
    if error:
        return error

    try:
        ContextManagerV3.set_active_object(obj)

        # Add collision modifier
        if not obj.modifiers.get("Collision"):
            obj.modifiers.new(name="Collision", type="COLLISION")
        settings = obj.modifiers["Collision"].settings

        # Blender 5.0 API check
        thickness_val = _coerce_float(params.get("thickness", 0.02))
        if hasattr(settings, "thickness_outer"):
            settings.thickness_outer = thickness_val
            settings.thickness_inner = _coerce_float(params.get("thickness_inner", 0.01))
            thickness_actual = settings.thickness_outer
        elif hasattr(settings, "thickness"):
            settings.thickness = thickness_val
            thickness_actual = settings.thickness
        else:
            thickness_actual = thickness_val

        settings.damping = _coerce_float(params.get("damping", 0.1))
        settings.friction_factor = _coerce_float(params.get("friction", 0.5))

        return ResponseBuilder.success(
            handler="manage_physics",
            action="COLLISION_SETUP",
            data={"object": obj.name, "thickness": thickness_actual, "damping": settings.damping},
        )
    except Exception as e:
        logger.error(f"COLLISION_SETUP failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="COLLISION_SETUP",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


# =============================================================================
# GENERAL SIMULATION CONTROLS - Thread Safe
# =============================================================================


def _handle_simulation_play() -> Dict[str, Any]:
    """Start simulation playback with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SIMULATION_PLAY",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    def play() -> Dict[str, Any]:
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.screen.animation_play()
        return ResponseBuilder.success(
            handler="manage_physics", action="SIMULATION_PLAY", data={"status": "playing"}
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(play, timeout=10.0))
    except Exception as e:
        logger.error(f"SIMULATION_PLAY failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SIMULATION_PLAY",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_simulation_stop() -> Dict[str, Any]:
    """Stop simulation playback with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SIMULATION_STOP",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    def stop() -> Dict[str, Any]:
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.screen.animation_cancel()
        return ResponseBuilder.success(
            handler="manage_physics", action="SIMULATION_STOP", data={"status": "stopped"}
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(stop, timeout=10.0))
    except Exception as e:
        logger.error(f"SIMULATION_STOP failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="SIMULATION_STOP",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_all_bake(**params: Any) -> Dict[str, Any]:
    """Bake all simulations in scene."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="ALL_BAKE",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="ALL_BAKE",
            error_code="NO_SCENE",
            message="No scene available",
        )

    frame_start = _coerce_int(params.get("frame_start", scene.frame_start))
    frame_end = _coerce_int(params.get("frame_end", scene.frame_end))

    baked = []

    # Rigid body
    if scene.rigidbody_world:
        _handle_rigid_body_bake(**params)
        baked.append("rigid_body")

    # Cloth and soft body per object
    for obj in scene.objects:
        for mod in obj.modifiers:
            if mod.type == "CLOTH":
                _handle_cloth_bake(object_name=obj.name, **params)
                baked.append(f"cloth:{obj.name}")
            elif mod.type == "SOFT_BODY":
                _handle_soft_body_bake(object_name=obj.name, **params)
                baked.append(f"soft_body:{obj.name}")

    return ResponseBuilder.success(
        handler="manage_physics",
        action="ALL_BAKE",
        data={"baked_systems": baked, "frame_range": f"{frame_start}-{frame_end}"},
    )


def _handle_all_cache_clear() -> Dict[str, Any]:
    """Clear all simulation caches with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="ALL_CACHE_CLEAR",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    scene = ContextManagerV3.get_scene()
    if not scene:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="ALL_CACHE_CLEAR",
            error_code="NO_SCENE",
            message="No scene available",
        )

    def clear_all() -> Dict[str, Any]:
        cleared = []

        # Rigid body
        if scene.rigidbody_world:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.ptcache.free_bake_all()
            cleared.append("rigid_body")

        # Per-object caches
        for obj in scene.objects:
            for mod in obj.modifiers:
                if mod.type in {"CLOTH", "SOFT_BODY"}:
                    mod.point_cache.free_bake()
                    cleared.append(f"{mod.type.lower()}:{obj.name}")

        return ResponseBuilder.success(
            handler="manage_physics", action="ALL_CACHE_CLEAR", data={"cleared_caches": cleared}
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(clear_all, timeout=60.0))
    except Exception as e:
        logger.error(f"ALL_CACHE_CLEAR failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="ALL_CACHE_CLEAR",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )


def _handle_cache_clear(sim_type: str, obj_name: Optional[str] = None) -> Dict[str, Any]:
    """Clear specific cache type with thread safety."""
    if not BPY_AVAILABLE:
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CACHE_CLEAR",
            error_code="NO_CONTEXT",
            message="bpy not available",
        )

    def clear_cache() -> Dict[str, Any]:
        if sim_type == "RIGID_BODY":
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.ptcache.free_bake_all()
            return ResponseBuilder.success(
                handler="manage_physics", action="CACHE_CLEAR", data={"cleared": "rigid_body"}
            )

        elif sim_type in ["CLOTH", "SOFT_BODY"] and obj_name:
            obj = bpy.data.objects.get(obj_name)
            if obj:
                for mod in obj.modifiers:
                    if mod.type == sim_type:
                        # mypy: point_cache exists on specific modifiers
                        mod.point_cache.free_bake()  # type: ignore
                        return ResponseBuilder.success(
                            handler="manage_physics",
                            action="CACHE_CLEAR",
                            data={"cleared": f"{sim_type.lower()}:{obj.name}"},
                        )

        return ResponseBuilder.error(
            handler="manage_physics",
            action="CACHE_CLEAR",
            error_code="EXECUTION_ERROR",
            message=f"Unknown cache type: {sim_type}",
        )

    try:
        return cast(Dict[str, Any], execute_on_main_thread(clear_cache, timeout=30.0))
    except Exception as e:
        logger.error(f"CACHE_CLEAR failed: {e}", exc_info=True)
        return ResponseBuilder.error(
            handler="manage_physics",
            action="CACHE_CLEAR",
            error_code="EXECUTION_ERROR",
            message=str(e),
        )
