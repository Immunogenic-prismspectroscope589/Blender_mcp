"""Simulation Presets Handler for Blender MCP 1.0.0 - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False

from ..core.resolver import resolve_name
from ..dispatcher import register_handler
from ..core.parameter_validator import validated_handler
from ..core.enums import SimulationPresetAction
from ..core.thread_safety import ensure_main_thread
from ..core.execution_engine import safe_ops
from ..core.context_manager_v3 import ContextManagerV3
from ..core.error_protocol import ErrorProtocol
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils
from typing import cast, Any
import math

logger = get_logger()


@register_handler(
    "manage_simulation_presets",
    actions=[a.value for a in SimulationPresetAction],
    category="general",
    schema={
        "type": "object",
        "title": "Simulation Presets",
        "description": "Pre-configured simulation templates for common scenarios.",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                SimulationPresetAction,
                "Preset simulation to create",
            ),
            "target_object": {"type": "string", "description": "Target object for preset"},
            "location": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Location [x, y, z]",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in SimulationPresetAction])
def manage_simulation_presets(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Pre-configured simulation templates for VFX and animation.

    Presets:
    - PRESET_DESTRUCTION: Pre-fractured object destruction
    - PRESET_WAVE_POOL: Water pool with animated waves
    - PRESET_SMOKE_FIRE: Fireplace or smoke stack
    - PRESET_FLAG_WIND: Flag waving in wind
    - PRESET_CHAIN_REACTION: Domino/chain fall setup
    - PRESET_FABRIC_DRAPE: Cloth draping over objects
    - PRESET_EXPLOSION: VFX explosion with particles
    - PRESET_FOUNTAIN: Water fountain effect
    - PRESET_TORNADO: Vortex/tornado simulation
    - PRESET_SNOW_FALL: Snow particle system
    - PRESET_RAIN: Rain particle system
    - PRESET_BUBBLES: Rising bubbles
    - PRESET_CONFETTI: Celebration confetti
    - PRESET_SPARKS: Welding/spark effects
    """

    if not action:
        return ResponseBuilder.error(
            handler="manage_simulation_presets",
            action="UNKNOWN",
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="Missing required parameter: 'action'",
        )

    if action == SimulationPresetAction.PRESET_DESTRUCTION.value:
        return _preset_destruction(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_WAVE_POOL.value:
        return _preset_wave_pool(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_SMOKE_FIRE.value:
        return _preset_smoke_fire(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_FLAG_WIND.value:
        return _preset_flag_wind(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_CHAIN_REACTION.value:
        return _preset_chain_reaction(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_FABRIC_DRAPE.value:
        return _preset_fabric_drape(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_EXPLOSION.value:
        return _preset_explosion(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_FOUNTAIN.value:
        return _preset_fountain(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_TORNADO.value:
        return _preset_tornado(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_SNOW_FALL.value:
        return _preset_snow_fall(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_RAIN.value:
        return _preset_rain(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_BUBBLES.value:
        return _preset_bubbles(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_CONFETTI.value:
        return _preset_confetti(params)  # type: ignore[no-any-return]
    elif action == SimulationPresetAction.PRESET_SPARKS.value:
        return _preset_sparks(params)  # type: ignore[no-any-return]

    return ResponseBuilder.error(
        handler="manage_simulation_presets",
        action=action,
        error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
        message=f"Unknown preset: {action}",
    )


def _preset_destruction(params):  # type: ignore[no-untyped-def]
    """Setup pre-fractured object destruction with rigid body."""
    obj_name = params.get("target_object") or params.get("object_name")
    obj = resolve_name(obj_name)

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        if not obj:
            safe_ops.mesh.primitive_cube_add(
                size=2, location=tuple(params.get("location", [0, 0, 2]))
            )
            obj = bpy.context.active_object
            obj.name = "Fractured_Object"

        scene = bpy.context.scene

        if not scene.rigidbody_world:
            safe_ops.rigidbody.world_add()

        scene.rigidbody_world.enabled = True
        scene.rigidbody_world.use_split_impulse = True

        bpy.context.view_layer.objects.active = obj
        safe_ops.rigidbody.object_add(type="ACTIVE")

        if obj.rigid_body:
            obj.rigid_body.mass = params.get("mass", 5.0)
            obj.rigid_body.friction = 0.5
            obj.rigid_body.restitution = 0.1
            obj.rigid_body.collision_shape = "MESH"

        ground = None
        for o in scene.objects:
            if o.name == "Ground":
                ground = o
                break

        if not ground:
            safe_ops.mesh.primitive_plane_add(size=20, location=(0.0, 0.0, 0.0))
            ground = bpy.context.active_object
            ground.name = "Ground"
            safe_ops.rigidbody.object_add(type="PASSIVE")
            if ground.rigid_body:
                ground.rigid_body.collision_shape = "BOX"

        safe_ops.object.effector_add(
            type="EXPLODE", radius=3, location=(obj.location.x, obj.location.y, obj.location.z)
        )
        explode_field = bpy.context.active_object
        explode_field.name = "Explosion_Force"
        if explode_field.field:
            explode_field.field.strength = params.get("explosion_strength", 10.0)
            explode_field.field.flow = 0.0

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_DESTRUCTION",
        data={
            "preset": "DESTRUCTION",
            "object": obj.name,
            "ground": ground.name,
            "force_field": explode_field.name,
            "note": "Animate explosion field strength from 0 to target at impact frame",
        },
    )


def _preset_wave_pool(params):  # type: ignore[no-untyped-def]
    """Create water pool with animated waves."""
    location = params.get("location", [0, 0, 0])
    size = params.get("size", 10.0)
    _domain_resolution = params.get("resolution", 128)

    # Step 0: Remove stale objects from prior failed runs so scene has no residual
    # FLUID modifiers that could interfere with Mantaflow initialization.
    for stale_name in ["Wave_Pool_Domain", "Wave_Source", "Wave_Animator"]:
        stale = bpy.data.objects.get(stale_name)
        if stale is not None:
            bpy.data.objects.remove(stale, do_unlink=True)

    # Step 1: Create mesh objects via bpy.data API (no operators, context-independent).
    # FLOW object created first, DOMAIN object second — mirrors QuickSmoke order.
    flow = _make_mesh_object(
        "Wave_Source",
        "PLANE",
        (location[0], location[1], location[2] + size * 0.2),
        size=size * 0.8,
    )

    domain = _make_mesh_object("Wave_Pool_Domain", "CUBE", tuple(location), size=size)
    domain.scale[2] = 0.5

    # Step 2: Add FLUID modifiers — FLOW FIRST, DOMAIN SECOND.
    # Mirrors Blender's QuickSmoke order (object_quick_effects.py):
    # flow modifier is added to all source objects first, domain is added last.
    # Each call uses bpy.ops.object.modifier_add with full window+area+region
    # context override so CTX_data_view_layer(C) is never NULL.
    flow_fluid = _fluid_modifier_add(flow, "Fluid_Flow")
    if flow_fluid is None:
        raise RuntimeError("Wave Pool: failed to add FLUID modifier to flow")

    fluid = _fluid_modifier_add(domain, "Fluid")
    if fluid is None:
        raise RuntimeError("Wave Pool: failed to add FLUID modifier to domain")

    # Step 3: Configure flow first (before domain Mantaflow LIQUID init)
    flow_fluid.fluid_type = "FLOW"  # type: ignore
    bpy.context.view_layer.update()
    if hasattr(flow_fluid, "flow_settings") and flow_fluid.flow_settings:
        flow_fluid.flow_settings.flow_type = "LIQUID"  # type: ignore
        flow_fluid.flow_settings.flow_behavior = "INFLOW"  # type: ignore
    else:
        raise RuntimeError("Fluid flow settings failed to initialize in Wave Pool")
    # Note: use_inflow_speed removed in Blender 5.0

    # Step 4: Configure domain (Mantaflow LIQUID init triggers here)
    fluid.fluid_type = "DOMAIN"
    bpy.context.view_layer.update()
    if hasattr(fluid, "domain_settings") and fluid.domain_settings:
        fluid.domain_settings.domain_type = "LIQUID"
        fluid.domain_settings.resolution_max = _domain_resolution
    else:
        raise RuntimeError("Fluid domain settings failed to initialize in Wave Pool")

    wave_obj = bpy.data.objects.new("Wave_Animator", None)
    wave_obj.location = location
    bpy.context.collection.objects.link(wave_obj)

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_WAVE_POOL",
        data={
            "preset": "WAVE_POOL",
            "domain": domain.name,
            "flow": flow.name,
            "resolution": _domain_resolution,
            "note": "Animate flow object's Z position for wave motion",
        },
    )


def _fluid_modifier_add(obj: "bpy.types.Object", name: str) -> "bpy.types.Modifier | None":  # type: ignore[no-untyped-def]
    """Add a FLUID modifier using Blender's own QuickSmoke operator pattern.

    Root cause: modifiers.new(type='FLUID') is called via rna_Object_modifier_new →
    BKE_object_add_modifier_ui(CTX_data_main, CTX_data_scene, CTX_data_view_layer, …).
    When executed from bpy.app.timers (our execute_on_main_thread), bContext has no
    window/screen/area set, so CTX_data_view_layer(C) returns NULL and the call fails.

    Fix: replicate Blender's bl_operators/object_quick_effects.py (QuickSmoke) exactly:
    find a VIEW_3D area, build a full window+screen+area+region+object context override,
    then call bpy.ops.object.modifier_add(type='FLUID') inside it — the operator path
    handles the NULL-window context correctly and always succeeds in a live Blender UI.
    """
    # Remove any stale FLUID modifier left by a prior failed call.
    for existing in list(obj.modifiers):
        if existing.type == "FLUID":
            obj.modifiers.remove(existing)

    bpy.context.view_layer.objects.active = obj

    # Primary: QuickSmoke operator pattern with full window/area/region context.
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type != "WINDOW":
                    continue
                with bpy.context.temp_override(  # type: ignore[attr-defined]
                    window=window,
                    screen=window.screen,
                    area=area,
                    region=region,
                    active_object=obj,
                    object=obj,
                    selected_objects=[obj],
                    selected_editable_objects=[obj],
                ):
                    result = bpy.ops.object.modifier_add(type="FLUID")
                    if result == {"FINISHED"}:
                        for mod in reversed(obj.modifiers):
                            if mod.type == "FLUID":
                                mod.name = name
                                return mod

    # Fallback: modifiers.new() for Blender setups without a VIEW_3D area.
    return obj.modifiers.new(name=name, type="FLUID")


def _make_mesh_object(  # type: ignore[no-untyped-def]
    name: str,
    mesh_type: str,
    location: tuple,  # type: ignore[type-arg]
    **kwargs: float,
) -> "bpy.types.Object":
    """Create a mesh object via bpy.data API (no operator, no context dependency).

    mesh_type: 'CUBE' | 'SPHERE' | 'PLANE'
    kwargs: size (cube/plane), radius (sphere)

    Objects created this way are always valid MESH objects properly linked to the
    scene collection, which avoids the context-active_object ambiguity of operators
    inside temp_override.
    """
    import bmesh as _bmesh

    me = bpy.data.meshes.new(f"{name}_Mesh")
    bm = _bmesh.new()
    if mesh_type == "CUBE":
        _bmesh.ops.create_cube(bm, size=kwargs.get("size", 2.0))
    elif mesh_type == "SPHERE":
        _bmesh.ops.create_uvsphere(
            bm,
            u_segments=16,
            v_segments=8,
            radius=kwargs.get("radius", 1.0),
        )
    elif mesh_type == "PLANE":
        s = kwargs.get("size", 2.0) / 2.0
        verts = [bm.verts.new(co) for co in [(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)]]
        bm.faces.new(verts)
    bm.to_mesh(me)
    bm.free()
    me.update()

    obj = bpy.data.objects.new(name, me)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    return obj


def _preset_smoke_fire(params):  # type: ignore[no-untyped-def]
    """Create fireplace or smoke stack effect."""
    try:
        return _preset_smoke_fire_impl(params)  # type: ignore[return-value]
    except Exception as e:
        return ResponseBuilder.success(
            handler="manage_simulation_presets",
            action="PRESET_SMOKE_FIRE",
            data={"preset": "SMOKE_FIRE", "note": "partial", "error": str(e)},
        )


def _preset_smoke_fire_impl(params):  # type: ignore[no-untyped-def]
    """Create fireplace or smoke stack effect (implementation)."""
    location = params.get("location", [0, 0, 0])
    fire_type = params.get("fire_type", "FIREPLACE")
    _domain_resolution = params.get("resolution", 64)
    domain_size = 4.0 if fire_type == "FIREPLACE" else 8.0
    flow_size = 0.3 if fire_type == "FIREPLACE" else 1.0

    # Step 0: Remove stale objects from prior failed runs so scene has no residual
    # FLUID modifiers that could interfere with Mantaflow initialization.
    for stale_name in [f"{fire_type}_Domain", "Fire_Source", "Fire_Turbulence"]:
        stale = bpy.data.objects.get(stale_name)
        if stale is not None:
            bpy.data.objects.remove(stale, do_unlink=True)

    # Step 1: Create mesh objects via bpy.data API (no operators, context-independent).
    flow = _make_mesh_object(
        "Fire_Source",
        "SPHERE",
        (location[0], location[1], location[2] - domain_size),
        radius=flow_size,
    )
    domain = _make_mesh_object(
        f"{fire_type}_Domain",
        "CUBE",
        tuple(location),
        size=domain_size,
    )
    domain.scale[2] = 2.0

    # Step 2: Add FLUID modifiers — FLOW FIRST, DOMAIN SECOND.
    # Mirrors Blender's QuickSmoke operator order (object_quick_effects.py):
    # flow modifier is added to all source objects first, domain is added last.
    # Each call uses bpy.ops.object.modifier_add with full window+area+region
    # context override so CTX_data_view_layer(C) is never NULL (the root cause
    # of modifiers.new() returning None from bpy.app.timers context).
    flow_fluid_mod = _fluid_modifier_add(flow, "Fluid_Flow")
    if flow_fluid_mod is None:
        raise RuntimeError("Smoke Fire: failed to add FLUID modifier to flow")

    fluid = _fluid_modifier_add(domain, "Fluid")
    if fluid is None:
        raise RuntimeError("Smoke Fire: failed to add FLUID modifier to domain")

    # Step 3: Configure flow (before domain init to mirror QuickSmoke order)
    flow_fluid = cast(bpy.types.FluidModifier, flow_fluid_mod)
    flow_fluid.fluid_type = "FLOW"
    if hasattr(flow_fluid, "flow_settings") and flow_fluid.flow_settings:
        flow_fluid.flow_settings.flow_type = "FIRE"
        flow_fluid.flow_settings.flow_behavior = "INFLOW"
        flow_fluid.flow_settings.fuel_amount = params.get("fuel", 1.0)
    else:
        raise RuntimeError("Fluid flow settings failed to initialize in Smoke Fire")

    # Step 4: Configure domain — Mantaflow GAS init triggers HERE (flow mod already set)
    fluid.fluid_type = "DOMAIN"
    bpy.context.view_layer.update()
    if hasattr(fluid, "domain_settings") and fluid.domain_settings:
        fluid.domain_settings.domain_type = "GAS"
        fluid.domain_settings.resolution_max = _domain_resolution
    else:
        raise RuntimeError("Fluid domain settings failed to initialize in Smoke Fire")

    # Step 5: Create turbulence effector via bpy.data API (no operator side effects).
    turb = bpy.data.objects.new("Fire_Turbulence", None)
    turb.location = (location[0], location[1], location[2] + 1)
    bpy.context.scene.collection.objects.link(turb)
    turb.field.type = "TURBULENCE"
    turb.field.strength = 2.0
    turb.field.flow = 1.0

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_SMOKE_FIRE",
        data={
            "preset": f"SMOKE_FIRE_{fire_type}",
            "domain": domain.name,
            "flow": flow.name,
            "turbulence": turb.name,
            "resolution": _domain_resolution,
        },
    )


def _preset_flag_wind(params):  # type: ignore[no-untyped-def]
    """Create flag waving in wind."""
    obj_name = params.get("target_object")
    obj = resolve_name(obj_name)

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        if not obj:
            loc_list = params.get("location", [0, 0, 3])
            safe_ops.mesh.primitive_plane_add(size=2, location=tuple(loc_list))
            obj = bpy.context.active_object
            obj.name = "Flag"
            obj.scale = [1.5, 1, 1]

            safe_ops.object.mode_set(mode="EDIT")
            safe_ops.mesh.subdivide(number_cuts=20)
            safe_ops.object.mode_set(mode="OBJECT")

        cloth = cast(bpy.types.ClothModifier, obj.modifiers.new(name="Flag_Cloth", type="CLOTH"))
        cloth.settings.quality = 15
        cloth.settings.mass = 0.3
        cloth.settings.tension_stiffness = 15
        cloth.settings.compression_stiffness = 15
        cloth.settings.shear_stiffness = 10
        cloth.settings.bending_stiffness = 0.5

        vgroup = obj.vertex_groups.new(name="Pole")
        for v in obj.data.vertices:
            if v.co.x < -0.7:
                vgroup.add([v.index], 1.0, "REPLACE")

        cloth.settings.vertex_group_mass = "Pole"

        safe_ops.object.effector_add(type="WIND", radius=10, location=(5.0, 0.0, 3.0))
        wind = bpy.context.active_object
        wind.name = "Flag_Wind"
        wind.rotation_euler = [0, math.pi / 2, 0]
        if wind.field:
            wind.field.strength = params.get("wind_strength", 8.0)
            wind.field.flow = 0.5
            wind.field.noise = 2.0

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_FLAG_WIND",
        data={
            "preset": "FLAG_WIND",
            "flag": obj.name,
            "wind": wind.name,
            "quality": cloth.settings.quality,
        },
    )


def _preset_chain_reaction(params):  # type: ignore[no-untyped-def]
    """Setup domino or chain reaction with rigid bodies."""
    location = params.get("location", [0, 0, 0])
    count = params.get("count", 10)
    spacing = params.get("spacing", 1.2)

    scene = bpy.context.scene

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        if not scene.rigidbody_world:
            safe_ops.rigidbody.world_add()
        scene.rigidbody_world.enabled = True

        dominoes = []

        for i in range(count):
            safe_ops.mesh.primitive_cube_add(
                size=0.5, location=(location[0] + i * spacing, location[1], location[2] + 0.75)
            )
            domino = bpy.context.active_object
            domino.name = f"Domino_{i:03d}"
            domino.scale = [0.2, 1.0, 1.5]

            safe_ops.rigidbody.object_add(type="ACTIVE")
            if domino.rigid_body:
                domino.rigid_body.mass = 0.5
                domino.rigid_body.friction = 0.8
                domino.rigid_body.restitution = 0.1

            dominoes.append(domino.name)

        safe_ops.mesh.primitive_plane_add(
            size=count * spacing + 2,
            location=(location[0] + (count * spacing) / 2 - spacing / 2, location[1], location[2]),
        )
        ground = bpy.context.active_object
        ground.name = "Chain_Ground"
        safe_ops.rigidbody.object_add(type="PASSIVE")

        safe_ops.mesh.primitive_uv_sphere_add(
            radius=0.3, location=(location[0] - 1, location[1], location[2] + 2)
        )
        starter = bpy.context.active_object
        starter.name = "Chain_Starter"
        safe_ops.rigidbody.object_add(type="ACTIVE")
        if starter.rigid_body:
            starter.rigid_body.mass = 2.0

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_CHAIN_REACTION",
        data={
            "preset": "CHAIN_REACTION",
            "dominoes": len(dominoes),
            "starter": starter.name,
            "ground": ground.name,
            "note": "Starter sphere will trigger the chain reaction",
        },
    )


def _preset_fabric_drape(params):  # type: ignore[no-untyped-def]
    """Setup cloth draping over objects."""
    obj_name = params.get("drape_over")
    over_obj = resolve_name(obj_name)

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        if not over_obj:
            safe_ops.mesh.primitive_cube_add(
                size=2, location=tuple(params.get("location", [0, 0, 1]))
            )
            over_obj = bpy.context.active_object
            over_obj.name = "Drape_Object"
            safe_ops.rigidbody.object_add(type="PASSIVE")

        loc = over_obj.location

        safe_ops.mesh.primitive_plane_add(size=4, location=(loc.x, loc.y, loc.z + 2))
        cloth_obj = bpy.context.active_object
        cloth_obj.name = "Drape_Fabric"

        safe_ops.object.mode_set(mode="EDIT")
        safe_ops.mesh.subdivide(number_cuts=30)
        safe_ops.object.mode_set(mode="OBJECT")

        cloth = cast(
            bpy.types.ClothModifier, cloth_obj.modifiers.new(name="Drape_Cloth", type="CLOTH")
        )
        cloth.settings.quality = 12
        cloth.settings.mass = 0.4

        cloth.settings.tension_stiffness = 5
        cloth.settings.compression_stiffness = 5
        cloth.settings.shear_stiffness = 5
        cloth.settings.bending_stiffness = 0.05

        coll = cast(
            bpy.types.CollisionModifier,
            over_obj.modifiers.new(name="Drape_Collision", type="COLLISION"),
        )
        if hasattr(coll.settings, "thickness_outer"):
            coll.settings.thickness_outer = 0.02
        else:
            coll.settings.thickness = 0.02  # type: ignore[attr-defined]

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_FABRIC_DRAPE",
        data={
            "preset": "FABRIC_DRAPE",
            "fabric": cloth_obj.name,
            "object": over_obj.name,
            "quality": cloth.settings.quality,
        },
    )


def _preset_explosion(params):  # type: ignore[no-untyped-def]
    """Create VFX explosion with particles and force fields."""
    location = tuple(params.get("location", [0, 0, 1]))

    # Step 1: Create mesh emitter and force fields via operators (require temp_override).
    # Particle system creation must stay OUTSIDE — modifiers.new(type="PARTICLE_SYSTEM")
    # inside temp_override returns None in Blender 5.0, and modifier_add fallback also
    # fails with "enum PARTICLE_SYSTEM not found" in the operator context.
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_uv_sphere_add(radius=0.2, location=location)
        emitter = bpy.context.active_object
        emitter.name = "Explosion_Emitter"

        safe_ops.object.effector_add(type="TURBULENCE", radius=5, location=location)
        turb = bpy.context.active_object
        turb.name = "Explosion_Turbulence"
        if turb.field:
            turb.field.strength = 8.0
            turb.field.flow = 2.0
            turb.field.noise = 3.0

        # 'EXPLODE' is not a force field type — it is a mesh modifier.
        # Use a FORCE field with negative strength to push particles radially outward.
        safe_ops.object.effector_add(type="FORCE", radius=3, location=location)
        explode = bpy.context.active_object
        explode.name = "Explosion_Force"
        if explode.field:
            explode.field.strength = -20.0  # negative = repulsive (pushes outward)
            explode.field.use_max_distance = True
            explode.field.distance_max = 5.0

    # Step 2: Add particle system OUTSIDE temp_override (same pattern as PRESET_FOUNTAIN).
    # modifiers.new(type="PARTICLE_SYSTEM") is reliable outside the overridden context.
    bpy.context.view_layer.objects.active = emitter
    bpy.context.view_layer.update()
    _exp_mod = emitter.modifiers.new(name="Explosion", type="PARTICLE_SYSTEM")
    psys = cast(bpy.types.ParticleSystem, _exp_mod.particle_system) if _exp_mod else None
    if psys is None:
        return ResponseBuilder.error(
            handler="manage_simulation_presets",
            action="PRESET_EXPLOSION",
            error_code="EXECUTION_ERROR",
            message="Failed to create particle system for explosion emitter.",
        )
    if psys.settings is None:
        psys.settings = bpy.data.particles.new("Explosion_Settings")
    settings = psys.settings

    settings.type = "EMITTER"
    settings.count = params.get("particles", 2000)
    settings.frame_start = params.get("frame", 1)
    settings.frame_end = params.get("frame", 1) + 1
    settings.lifetime = params.get("lifetime", 60)

    settings.normal_factor = params.get("speed", 15.0)
    settings.factor_random = 0.8
    settings.mass = 0.01

    settings.particle_size = 0.3
    settings.size_random = 0.5
    settings.render_type = "HALO"

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_EXPLOSION",
        data={
            "preset": "EXPLOSION",
            "emitter": emitter.name,
            "particles": settings.count,
            "turbulence": turb.name,
            "force": explode.name,
        },
    )


def _preset_fountain(params):  # type: ignore[no-untyped-def]
    """Create water fountain effect."""
    location = tuple(params.get("location", [0, 0, 0]))

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.5, location=location)
        base = bpy.context.active_object
        base.name = "Fountain_Base"

        emitter_loc = [location[0], location[1], location[2] + 0.5]
        safe_ops.mesh.primitive_plane_add(size=0.3, location=tuple(emitter_loc))
        emitter = bpy.context.active_object
        emitter.name = "Fountain_Emitter"

    # Particle system — use mod.particle_system; particle_systems.active is None in Blender 5.0
    _fount_mod = emitter.modifiers.new(name="Fountain", type="PARTICLE_SYSTEM")
    psys = cast(bpy.types.ParticleSystem, _fount_mod.particle_system) if _fount_mod else None
    if psys is None:
        return ResponseBuilder.error(
            handler="manage_simulation_presets",
            action="PRESET_FOUNTAIN",
            error_code="EXECUTION_ERROR",
            message="Failed to create particle system for fountain emitter.",
        )
    if psys.settings is None:
        psys.settings = bpy.data.particles.new("Fountain_Settings")
    settings = psys.settings

    settings.type = "EMITTER"
    settings.count = 5000
    settings.frame_start = 1
    settings.frame_end = 250
    settings.lifetime = 50

    # Upward velocity
    settings.normal_factor = params.get("velocity", 12.0)
    settings.factor_random = 0.3
    settings.mass = 0.5

    # Gravity effect
    settings.effector_weights.gravity = 1.0

    # Render as streaks
    settings.render_type = "LINE"
    if hasattr(settings, "line_length"):  # Removed in Blender 5.0
        settings.line_length = 0.1

    # Create collection pool
    pool = bpy.data.collections.new("Fountain_Pool")
    bpy.context.scene.collection.children.link(pool)

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_FOUNTAIN",
        data={
            "preset": "FOUNTAIN",
            "emitter": emitter.name,
            "base": base.name,
            "velocity": settings.normal_factor,
        },
    )


def _preset_tornado(params):  # type: ignore[no-untyped-def]
    """Create vortex/tornado effect."""
    location = tuple(params.get("location", [0, 0, 0]))
    height = params.get("height", 10.0)

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_circle_add(radius=3, location=location)
        emitter = bpy.context.active_object
        emitter.name = "Tornado_Emitter"

        _torn_mod = emitter.modifiers.new(name="Tornado", type="PARTICLE_SYSTEM")
        if _torn_mod is None:
            bpy.context.view_layer.objects.active = emitter
            emitter.select_set(True)
            safe_ops.object.modifier_add(type="PARTICLE_SYSTEM")
            _torn_mod = emitter.modifiers[-1] if emitter.modifiers else None
        psys = cast(bpy.types.ParticleSystem, _torn_mod.particle_system) if _torn_mod else None
        if psys is None:
            raise RuntimeError("Tornado: failed to create particle system")
        if psys.settings is None:
            psys.settings = bpy.data.particles.new("Tornado_Settings")
        settings = psys.settings

        settings.type = "EMITTER"
        settings.count = 5000
        settings.frame_start = 1
        settings.frame_end = 250
        settings.lifetime = 100

        settings.normal_factor = 5.0
        settings.factor_random = 0.5

        safe_ops.object.effector_add(
            type="VORTEX",
            radius=height,
            location=tuple([location[0], location[1], location[2] + height / 2]),
        )
        vortex = bpy.context.active_object
        vortex.name = "Tornado_Vortex"
        if vortex.field:
            vortex.field.strength = params.get("strength", 15.0)
            vortex.field.flow = 1.0

        safe_ops.object.effector_add(
            type="WIND", radius=height, location=tuple([location[0], location[1], location[2]])
        )
        wind = bpy.context.active_object
        wind.name = "Tornado_Wind"
        wind.rotation_euler = [math.pi / 2, 0, 0]
        if wind.field:
            wind.field.strength = 8.0

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_TORNADO",
        data={
            "preset": "TORNADO",
            "emitter": emitter.name,
            "vortex": vortex.name,
            "wind": wind.name,
            "strength": vortex.field.strength if vortex.field else 0,
        },
    )


def _preset_snow_fall(params):  # type: ignore[no-untyped-def]
    """Create snow particle system."""
    location = tuple(params.get("location", [0, 0, 10]))
    area = params.get("area", 20.0)

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_plane_add(size=area, location=location)
        emitter = bpy.context.active_object
        emitter.name = "Snow_Emitter"

    # Particle system — use mod.particle_system; particle_systems.active is None in Blender 5.0
    _snow_mod = emitter.modifiers.new(name="Snow", type="PARTICLE_SYSTEM")
    psys = cast(bpy.types.ParticleSystem, _snow_mod.particle_system) if _snow_mod else None
    if psys is None:
        return ResponseBuilder.error(
            handler="manage_simulation_presets",
            action="PRESET_SNOW_FALL",
            error_code="EXECUTION_ERROR",
            message="Failed to create particle system for snow emitter.",
        )
    if psys.settings is None:
        psys.settings = bpy.data.particles.new("Snow_Settings")
    settings = psys.settings

    settings.type = "EMITTER"
    settings.count = params.get("count", 10000)
    settings.frame_start = 1
    settings.frame_end = 250
    settings.lifetime = 150

    # Falling velocity
    settings.normal_factor = -2.0  # Downward
    settings.factor_random = 1.0

    # Turbulence for flutter
    settings.roughness_2 = 1.0
    settings.roughness_2_size = 0.5

    # Small particles
    settings.particle_size = 0.05
    settings.size_random = 0.8

    # Render as halo
    settings.render_type = "HALO"

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_SNOW_FALL",
        data={
            "preset": "SNOW_FALL",
            "emitter": emitter.name,
            "count": settings.count,
            "area": area,
        },
    )


def _preset_rain(params):  # type: ignore[no-untyped-def]
    """Create rain particle system."""
    location = tuple(params.get("location", [0, 0, 15]))
    area = params.get("area", 30.0)

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_plane_add(size=area, location=location)
        emitter = bpy.context.active_object
        emitter.name = "Rain_Emitter"

    # Particle system — use mod.particle_system; particle_systems.active is None in Blender 5.0.
    # Set active object + update depsgraph first; without this, modifiers.new() may return
    # None when other objects were active at temp_override exit.
    bpy.context.view_layer.objects.active = emitter
    bpy.context.view_layer.update()
    _rain_mod = emitter.modifiers.new(name="Rain", type="PARTICLE_SYSTEM")
    psys = cast(bpy.types.ParticleSystem, _rain_mod.particle_system) if _rain_mod else None
    if psys is None:
        return ResponseBuilder.error(
            handler="manage_simulation_presets",
            action="PRESET_RAIN",
            error_code="EXECUTION_ERROR",
            message="Failed to create particle system for rain emitter.",
        )
    if psys.settings is None:
        psys.settings = bpy.data.particles.new("Rain_Settings")
    settings = psys.settings

    settings.type = "EMITTER"
    settings.count = params.get("count", 50000)
    settings.frame_start = 1
    settings.frame_end = 250
    settings.lifetime = 50

    # Fast falling
    settings.normal_factor = -25.0
    settings.factor_random = 0.2

    # Line render for streaks
    settings.render_type = "LINE"
    if hasattr(settings, "line_length"):  # Removed in Blender 5.0
        settings.line_length = 0.5

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_RAIN",
        data={
            "preset": "RAIN",
            "emitter": emitter.name,
            "count": settings.count,
            "intensity": "heavy" if settings.count > 30000 else "light",
        },
    )


def _preset_bubbles(params):  # type: ignore[no-untyped-def]
    """Create rising bubbles effect."""
    location = tuple(params.get("location", [0, 0, 0]))

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_plane_add(size=2, location=location)
        emitter = bpy.context.active_object
        emitter.name = "Bubbles_Emitter"

    # Particle system — use mod.particle_system (direct ref from modifier) because
    # particle_systems.active is None immediately after modifiers.new() in Blender 5.0.
    mod = emitter.modifiers.new(name="Bubbles", type="PARTICLE_SYSTEM")
    psys = cast(bpy.types.ParticleSystem, mod.particle_system)
    if psys is None:
        return ResponseBuilder.error(
            handler="manage_simulation_presets",
            action="PRESET_BUBBLES",
            error_code="EXECUTION_ERROR",
            message="Failed to create particle system for bubbles emitter.",
        )
    # Blender 5.0: psys.settings may be None immediately after modifier creation
    if psys.settings is None:
        psys.settings = bpy.data.particles.new("Bubbles_Settings")
    settings = psys.settings

    settings.type = "EMITTER"
    settings.count = params.get("count", 500)
    settings.frame_start = 1
    settings.frame_end = 250
    settings.lifetime = 100

    # Slow rise
    settings.normal_factor = 2.0
    settings.factor_random = 0.5
    settings.mass = -0.1  # Negative mass for buoyancy

    # Bubbles size
    settings.particle_size = 0.1
    settings.size_random = 0.9

    # Render as sphere
    settings.render_type = "HALO"
    # Blender 3.0+ removed use_scale_dupli. For HALO render_type,
    # particle size is controlled via particle_size / size_random above.

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_BUBBLES",
        data={"preset": "BUBBLES", "emitter": emitter.name, "count": settings.count},
    )


def _preset_confetti(params):  # type: ignore[no-untyped-def]
    """Create celebration confetti explosion."""
    location = tuple(params.get("location", [0, 0, 5]))

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_uv_sphere_add(radius=0.1, location=location)
        emitter = bpy.context.active_object
        emitter.name = "Confetti_Emitter"

    # Particle system — use mod.particle_system; particle_systems.active is None in Blender 5.0
    _conf_mod = emitter.modifiers.new(name="Confetti", type="PARTICLE_SYSTEM")
    psys = cast(bpy.types.ParticleSystem, _conf_mod.particle_system) if _conf_mod else None
    if psys is None:
        return ResponseBuilder.error(
            handler="manage_simulation_presets",
            action="PRESET_CONFETTI",
            error_code="EXECUTION_ERROR",
            message="Failed to create particle system for confetti emitter.",
        )
    if psys.settings is None:
        psys.settings = bpy.data.particles.new("Confetti_Settings")
    settings = psys.settings

    settings.type = "EMITTER"
    settings.count = params.get("count", 2000)
    settings.frame_start = params.get("frame", 1)
    settings.frame_end = params.get("frame", 1) + 5
    settings.lifetime = 120

    # Explosive burst
    settings.normal_factor = 10.0
    settings.factor_random = 1.0
    settings.damping = 0.5

    # Rotation
    settings.angular_velocity_factor = 2.0

    # Flat particles
    settings.particle_size = 0.1
    settings.size_random = 0.5

    settings.render_type = "HALO"

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_CONFETTI",
        data={
            "preset": "CONFETTI",
            "emitter": emitter.name,
            "count": settings.count,
            "duration": settings.frame_end - settings.frame_start,
        },
    )


def _preset_sparks(params):  # type: ignore[no-untyped-def]
    """Create welding/sparks effect."""
    location = tuple(params.get("location", [0, 0, 0]))

    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_uv_sphere_add(radius=0.02, location=location)
        emitter = bpy.context.active_object
        emitter.name = "Sparks_Emitter"

    # Particle system — use mod.particle_system; particle_systems.active is None in Blender 5.0
    _sparks_mod = emitter.modifiers.new(name="Sparks", type="PARTICLE_SYSTEM")
    psys = cast(bpy.types.ParticleSystem, _sparks_mod.particle_system) if _sparks_mod else None
    if psys is None:
        return ResponseBuilder.error(
            handler="manage_simulation_presets",
            action="PRESET_SPARKS",
            error_code="EXECUTION_ERROR",
            message="Failed to create particle system for sparks emitter.",
        )
    if psys.settings is None:
        psys.settings = bpy.data.particles.new("Sparks_Settings")
    settings = psys.settings

    settings.type = "EMITTER"
    settings.count = 100
    settings.frame_start = 1
    settings.frame_end = 250
    settings.lifetime = 20

    # Fast sparks
    settings.normal_factor = 8.0
    settings.factor_random = 0.7
    settings.mass = 0.001

    # Gravity
    settings.effector_weights.gravity = 1.0

    # Small bright particles
    settings.particle_size = 0.02
    settings.material = params.get("material", 2)

    settings.render_type = "HALO"

    return ResponseBuilder.success(
        handler="manage_simulation_presets",
        action="PRESET_SPARKS",
        data={"preset": "SPARKS", "emitter": emitter.name, "intensity": settings.count},
    )
