"""Light Management Handler for Blender MCP - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

import math
from typing import Any

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
import mathutils

from ..dispatcher import register_handler


from ..core.thread_safety import ensure_main_thread
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.enums import LightAction, LightType
from ..core.validation_utils import ValidationUtils
from typing import cast

logger = get_logger()


@register_handler(
    "manage_light",
    actions=[a.value for a in LightAction],
    category="general",
    priority=15,
    schema={
        "type": "object",
        "title": "Light Manager (CORE)",
        "description": (
            "CORE — Create and configure lights (SUN, POINT, SPOT, AREA). Lighting presets included.\n\n"
            "Use to illuminate scenes for rendering or viewport preview.\n"
            "ACTIONS: CREATE, MODIFY, DELETE, SET_PRESET, LIST"
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                LightAction, "Light operation to perform"
            ),
            "light_name": {"type": "string", "description": "Name of the light"},
            "light_type": ValidationUtils.generate_enum_schema(
                LightType, "Type of light to create"
            ),
            "location": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x, y, z] position",
            },
            "rotation": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[x, y, z] Euler rotation",
            },
            "energy": {"type": "number", "default": 10.0, "description": "Light power/energy"},
            "color": {
                "type": "array",
                "items": {"type": "number"},
                "description": "[r, g, b] color (0-1 range)",
            },
            "temperature": {
                "type": "number",
                "description": "Color temperature in Kelvin (e.g., 2700, 5500, 6500)",
            },
            "target": {"type": "string", "description": "Object to point at"},
            "size": {
                "type": "number",
                "default": 0.1,
                "description": "Light size for soft shadows (Sun/Area)",
            },
            "angle": {
                "type": "number",
                "default": 45.0,
                "description": "Spot light angle in degrees",
            },
            "filepath": {
                "type": "string",
                "description": "Path to the HDRI image (Required for SETUP_HDRI)",
            },
            "use_shadow": {"type": "boolean", "default": True, "description": "Enable shadows"},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
def manage_light(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Comprehensive light management with presets for AAA rendering.
    """
    validation_error = ValidationUtils.validate_enum(action, LightAction, "action")
    if validation_error:
        return ResponseBuilder.from_error(validation_error, handler="manage_light", action=action)

    # Color temperature to RGB conversion (simplified)
    def kelvin_to_rgb(kelvin):  # type: ignore[no-untyped-def]
        """Approximate color temperature to RGB conversion."""
        temperature = kelvin / 100.0

        # Red
        if temperature <= 66:
            red = 255.0
        else:
            red = 329.698727446 * ((temperature - 60) ** -0.1332047592)
            red = max(0, min(255, red))

        # Green
        if temperature <= 66:
            green = 99.4708025861 * math.log(temperature) - 161.1195681661
        else:
            green = 288.1221695283 * ((temperature - 60) ** -0.0755148492)
        green = max(0, min(255, green))

        # Blue
        if temperature >= 66:
            blue = 255.0
        elif temperature <= 19:
            blue = 0.0
        else:
            blue = 138.5177312231 * math.log(temperature - 10) - 305.0447927307
            blue = max(0, min(255, blue))

        return (red / 255.0, green / 255.0, blue / 255.0)

    # 1. CREATE LIGHT
    if action == LightAction.CREATE.value:
        light_name = params.get("light_name", "Light")

        # Validate light type if provided
        light_type = params.get("light_type", LightType.POINT.value)
        type_validation = ValidationUtils.validate_enum(light_type, LightType, "light_type")
        if type_validation:
            return ResponseBuilder.from_error(
                type_validation, handler="manage_light", action=action
            )

        # Create light data
        light_data = bpy.data.lights.new(name=light_name, type=light_type)
        light_obj = bpy.data.objects.new(name=light_name, object_data=light_data)
        bpy.context.collection.objects.link(light_obj)

        # Set location
        loc = params.get("location", (0, 0, 5))
        light_obj.location = mathutils.Vector(loc)

        # Set rotation for directional lights
        if "rotation" in params and light_type in [
            LightType.SUN.value,
            LightType.SPOT.value,
            LightType.AREA.value,
        ]:
            light_obj.rotation_euler = mathutils.Euler(params["rotation"])

        # Look at target if specified
        elif "target" in params and light_type in [
            LightType.SUN.value,
            LightType.SPOT.value,
            LightType.AREA.value,
        ]:
            target_obj = bpy.data.objects.get(params["target"])
            if target_obj:
                direction = target_obj.location - light_obj.location
                rot_quat = direction.to_track_quat("-Z", "Y")
                light_obj.rotation_euler = rot_quat.to_euler()

        # Set energy
        light_data.energy = params.get("energy", 10.0)  # type: ignore

        # Set color (either RGB or temperature)
        if "temperature" in params:
            light_data.color = kelvin_to_rgb(params["temperature"])
        elif "color" in params:
            light_data.color = params["color"]

        # Set shadows
        light_data.use_shadow = params.get("use_shadow", True)

        # Type-specific settings
        if light_type == LightType.SUN.value:
            # Use setattr to bypass Mypy check for dynamic attribute
            setattr(light_data, "angle", params.get("size", 0.526))
        elif light_type == LightType.SPOT.value:
            light_data.spot_size = math.radians(params.get("angle", 45.0))  # type: ignore
            light_data.spot_blend = 0.1  # type: ignore
        elif light_type == LightType.AREA.value:
            light_data.size = params.get("size", 0.1)  # type: ignore
        elif light_type == LightType.POINT.value:
            light_data.shadow_soft_size = params.get("size", 0.1)  # type: ignore

        return ResponseBuilder.success(
            handler="manage_light",
            action=LightAction.CREATE.value,
            data={
                "light": light_obj.name,
                "type": light_type,
                "energy": light_data.energy,  # type: ignore
                "color": list(light_data.color),  # type: ignore
                "location": list(light_obj.location),  # type: ignore
            },
        )

    # 2. SET_ENERGY
    elif action == LightAction.SET_ENERGY.value:
        light_name = params.get("light_name")
        light_obj = bpy.data.objects.get(light_name)

        if not light_obj or light_obj.type != "LIGHT":
            return ResponseBuilder.error(
                handler="manage_light",
                action=LightAction.SET_ENERGY.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Light not found: {light_name}",
                details={"light_name": light_name},
            )

        light_data = cast(bpy.types.Light, light_obj.data)
        light_data.energy = params.get("energy", 10.0)  # type: ignore[attr-defined]  # type: ignore[attr-defined]

        return ResponseBuilder.success(
            handler="manage_light",
            action=LightAction.SET_ENERGY.value,
            data={"light": light_name, "energy": light_obj.data.energy},  # type: ignore
        )

    # 3. SET_COLOR
    elif action == LightAction.SET_COLOR.value:
        light_name = params.get("light_name")
        light_obj = bpy.data.objects.get(light_name)

        if not light_obj or light_obj.type != "LIGHT":
            return ResponseBuilder.error(
                handler="manage_light",
                action=LightAction.SET_COLOR.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Light not found: {light_name}",
                details={"light_name": light_name},
            )

        light_data = cast(bpy.types.Light, light_obj.data)
        if "temperature" in params:
            light_data.color = kelvin_to_rgb(params["temperature"])
        elif "color" in params:
            light_data.color = params["color"]

        return ResponseBuilder.success(
            handler="manage_light",
            action=LightAction.SET_COLOR.value,
            data={"light": light_name, "color": list(light_data.color)},  # type: ignore[call-overload]
        )

    # 4. SET_TRANSFORM
    elif action == LightAction.SET_TRANSFORM.value:
        light_name = params.get("light_name")
        light_obj = bpy.data.objects.get(light_name)

        if not light_obj or light_obj.type != "LIGHT":
            return ResponseBuilder.error(
                handler="manage_light",
                action=LightAction.SET_TRANSFORM.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Light not found: {light_name}",
                details={"light_name": light_name},
            )

        if "location" in params:
            light_obj.location = mathutils.Vector(params["location"])
        if "rotation" in params:
            light_obj.rotation_euler = mathutils.Euler(params["rotation"])

        return ResponseBuilder.success(
            handler="manage_light",
            action=LightAction.SET_TRANSFORM.value,
            data={"location": list(light_obj.location), "rotation": list(light_obj.rotation_euler)},  # type: ignore
        )

    # 5. SETUP_THREE_POINT
    elif action == LightAction.SETUP_THREE_POINT.value:
        """Create classic three-point lighting setup."""
        target_name = params.get("target")
        target_obj = bpy.data.objects.get(target_name) if target_name else None

        # Get target position (or use origin)
        target_loc = target_obj.location if target_obj else mathutils.Vector((0, 0, 0))

        lights = []

        # Key light (main light, warm)
        key_data = bpy.data.lights.new(name="Key_Light", type="AREA")
        key_data.energy = params.get("key_energy", 100.0)  # type: ignore
        key_data.color = (1.0, 0.95, 0.9)  # Slightly warm
        key_data.size = 2.0  # type: ignore

        key_obj = bpy.data.objects.new(name="Key_Light", object_data=key_data)
        bpy.context.collection.objects.link(key_obj)
        key_obj.location = target_loc + mathutils.Vector((5, -5, 5))

        # Point at target
        direction = target_loc - key_obj.location
        key_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        lights.append("Key_Light")

        # Fill light (softer, cool)
        fill_data = bpy.data.lights.new(name="Fill_Light", type="AREA")
        fill_data.energy = params.get("fill_energy", 30.0)  # type: ignore
        fill_data.color = (0.9, 0.95, 1.0)  # Slightly cool
        fill_data.size = 3.0  # type: ignore

        fill_obj = bpy.data.objects.new(name="Fill_Light", object_data=fill_data)
        bpy.context.collection.objects.link(fill_obj)
        fill_obj.location = target_loc + mathutils.Vector((-5, -3, 3))

        direction = target_loc - fill_obj.location
        fill_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        lights.append("Fill_Light")

        # Rim light (back light, highlights edges)
        rim_data = bpy.data.lights.new(name="Rim_Light", type="SPOT")
        rim_data.energy = params.get("rim_energy", 50.0)  # type: ignore
        rim_data.color = (1.0, 1.0, 1.0)
        rim_data.spot_size = math.radians(60)  # type: ignore

        rim_obj = bpy.data.objects.new(name="Rim_Light", object_data=rim_data)
        bpy.context.collection.objects.link(rim_obj)
        rim_obj.location = target_loc + mathutils.Vector((0, 5, 4))

        direction = target_loc - rim_obj.location
        rim_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        lights.append("Rim_Light")

        return ResponseBuilder.success(
            handler="manage_light",
            action=LightAction.SETUP_THREE_POINT.value,
            data={"setup": "three_point", "lights": lights, "target": target_name or "origin"},
        )

    # 6. SETUP_STUDIO
    elif action == LightAction.SETUP_STUDIO.value:
        """Create studio lighting setup with softboxes."""
        lights = []

        # Main softbox (large area light)
        main_data = bpy.data.lights.new(name="Studio_Main", type="AREA")
        main_data.energy = 50.0  # type: ignore
        main_data.size = 4.0  # type: ignore
        main_data.color = (1.0, 0.98, 0.95)

        main_obj = bpy.data.objects.new(name="Studio_Main", object_data=main_data)
        bpy.context.collection.objects.link(main_obj)
        main_obj.location = (4, -4, 6)
        main_obj.rotation_euler = (math.radians(60), 0, math.radians(45))
        lights.append("Studio_Main")

        # Fill softbox
        fill_data = bpy.data.lights.new(name="Studio_Fill", type="AREA")
        fill_data.energy = 20.0  # type: ignore
        fill_data.size = 6.0  # type: ignore
        fill_data.color = (0.9, 0.95, 1.0)

        fill_obj = bpy.data.objects.new(name="Studio_Fill", object_data=fill_data)
        bpy.context.collection.objects.link(fill_obj)
        fill_obj.location = (-5, -2, 4)
        fill_obj.rotation_euler = (math.radians(45), 0, math.radians(-30))
        lights.append("Studio_Fill")

        # Background/ambient
        bg_data = bpy.data.lights.new(name="Studio_BG", type="SUN")
        bg_data.energy = 2.0  # type: ignore
        setattr(bg_data, "angle", 0.1)  # Soft shadows
        bg_data.color = (1.0, 1.0, 1.0)

        bg_obj = bpy.data.objects.new(name="Studio_BG", object_data=bg_data)
        bpy.context.collection.objects.link(bg_obj)
        bg_obj.rotation_euler = (math.radians(45), 0, 0)
        lights.append("Studio_BG")

        return ResponseBuilder.success(
            handler="manage_light",
            action=LightAction.SETUP_STUDIO.value,
            data={"setup": "studio", "lights": lights},
        )

    # 7. LIST_LIGHTS
    elif action == LightAction.LIST_LIGHTS.value:
        light_data_list = [
            {
                "name": obj.name,
                "type": cast(bpy.types.Light, obj.data).type,
                "energy": cast(bpy.types.Light, obj.data).energy,  # type: ignore[attr-defined]
                "color": list(cast(bpy.types.Light, obj.data).color),  # type: ignore[call-overload]
                "location": list(obj.location),  # type: ignore
            }
            for obj in bpy.data.objects
            if obj.type == "LIGHT"
        ]

        return ResponseBuilder.success(
            handler="manage_light",
            action=LightAction.LIST_LIGHTS.value,
            data={"count": len(light_data_list), "lights": light_data_list},
        )

    # 8. DELETE
    elif action == LightAction.DELETE.value:
        light_name = params.get("light_name")
        light_obj = bpy.data.objects.get(light_name)

        if not light_obj or light_obj.type != "LIGHT":
            return ResponseBuilder.error(
                handler="manage_light",
                action=LightAction.DELETE.value,
                error_code="OBJECT_NOT_FOUND",
                message=f"Light not found: {light_name}",
                details={"light_name": light_name},
            )

        light_data = cast(bpy.types.Light, light_obj.data)
        bpy.data.objects.remove(light_obj, do_unlink=True)

        if light_data.users == 0:
            bpy.data.lights.remove(light_data)

        return ResponseBuilder.success(
            handler="manage_light", action=LightAction.DELETE.value, data={"deleted": light_name}
        )

    # 9. SETUP_HDRI
    elif action == LightAction.SETUP_HDRI.value:
        filepath = params.get("filepath", "")
        if not filepath:
            return ResponseBuilder.error(
                handler="manage_light",
                action=LightAction.SETUP_HDRI.value,
                error_code="MISSING_PARAMETER",
                message="filepath is required for SETUP_HDRI",
            )

        world = bpy.context.scene.world
        if not world:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world

        world.use_nodes = True
        tree = world.node_tree
        tree.nodes.clear()

        bg_node = tree.nodes.new(type="ShaderNodeBackground")
        out_node = tree.nodes.new(type="ShaderNodeOutputWorld")
        env_node = tree.nodes.new(type="ShaderNodeTexEnvironment")

        try:
            img = bpy.data.images.load(filepath, check_existing=True)
            env_node.image = img
        except Exception as e:
            return ResponseBuilder.error(
                handler="manage_light",
                action=LightAction.SETUP_HDRI.value,
                error_code="EXECUTION_ERROR",
                message=f"Failed to load HDRI: {str(e)}",
            )

        tree.links.new(env_node.outputs["Color"], bg_node.inputs["Color"])
        tree.links.new(bg_node.outputs["Background"], out_node.inputs["Surface"])

        # We need to coerce the energy value, or type-ignore it since we're writing dynamically via indexing.
        bg_node.inputs["Strength"].default_value = params.get("energy", 1.0)  # type: ignore[index]

        if "rotation" in params:
            mapping_node = tree.nodes.new(type="ShaderNodeMapping")
            coord_node = tree.nodes.new(type="ShaderNodeTexCoord")

            mapping_node.inputs["Rotation"].default_value = mathutils.Euler(params["rotation"])  # type: ignore[index]

            tree.links.new(coord_node.outputs["Generated"], mapping_node.inputs["Vector"])
            tree.links.new(mapping_node.outputs["Vector"], env_node.inputs["Vector"])

        return ResponseBuilder.success(
            handler="manage_light",
            action=LightAction.SETUP_HDRI.value,
            data={"world": world.name, "hdri_path": filepath},
        )

    return ResponseBuilder.error(
        handler="manage_light",
        action=action,
        error_code="INVALID_ACTION",
        message=f"Unknown action: {action}",
    )
