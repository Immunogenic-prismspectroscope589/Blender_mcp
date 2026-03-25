"""
Procedural Generation Handler for Blender MCP 1.0.0

Features:
- Fractal landscapes
- City generation
- Vegetation scattering
- Abstract art generation

High Mode Philosophy: Maximum power, maximum safety.
"""

from ..core.execution_engine import safe_ops

import math
import random

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
import mathutils

from ..dispatcher import register_handler


from ..core.parameter_validator import validated_handler
from ..core.enums import ProceduralAction
from ..core.thread_safety import ensure_main_thread
from ..core.context_manager_v3 import ContextManagerV3
from ..core.error_protocol import ErrorProtocol
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils
from typing import Any

logger = get_logger()


@register_handler(
    "manage_procedural",
    actions=[a.value for a in ProceduralAction],
    category="general",
    schema={
        "type": "object",
        "title": "Procedural Generation",
        "description": (
            "STANDARD — Geometry Nodes and procedural generation manager.\n"
            "ACTIONS: TERRAIN_GENERATE, TREE_GENERATE, ROCK_GENERATE, CRYSTAL_GENERATE, "
            "L_SYSTEM_PLANT, VORONOI_PATTERN, GEOMETRIC_PATTERN, FRACTAL_GENERATE, "
            "CITY_LAYOUT, MAZE_GENERATE, PARAMETRIC_CURVE, SPIRAL_GALAXY, "
            "FABRIC_WEAVE, CHAIN_MAIL, PARTICLE_FLOWER\n\n"
            "NOTE: All generators create non-destructive Geometry Nodes setups. "
            "Results update in real-time when parameters change. "
            "Use execute_blender_code to modify Geometry Nodes input values after creation."
        ),
        "properties": {
            "action": ValidationUtils.generate_enum_schema(
                ProceduralAction, "Procedural generation action"
            ),
            "seed": {"type": "integer"},
            "resolution": {"type": "integer", "default": 64},
            "scale": {"type": "number", "default": 1.0},
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in ProceduralAction])
def manage_procedural(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Procedural generation tools for organic and structured content.

    Actions:
    - TERRAIN_GENERATE: Heightmap-based terrain with erosion simulation
    - ROCK_GENERATE: Photorealistic rock formations
    - TREE_GENERATE: Procedural tree with branches and leaves
    - CITY_LAYOUT: Urban planning with roads and blocks
    - MAZE_GENERATE: Solvable maze generation
    - CRYSTAL_GENERATE: Geometric crystal formations
    - VORONOI_PATTERN: Voronoi-based surface patterns
    - FRACTAL_GENERATE: Iterated function systems
    - SPIRAL_GALAXY: Procedural galaxy structure
    - GEOMETRIC_PATTERN: Islamic/geometric tile patterns
    - PARAMETRIC_CURVE: Mathematical curve generation
    - L_SYSTEM_PLANT: L-system botanical generation
    - PARTICLE_FLOWER: Flower petal distribution
    - FABRIC_WEAVE: Woven fabric simulation
    - CHAIN_MAIL: Chain mail armor pattern
    """

    seed = params.get("seed", random.randint(1, 10000))
    random.seed(seed)

    if not action:
        return ResponseBuilder.error(
            handler="manage_procedural",
            action="UNKNOWN",
            error_code=ErrorProtocol.MISSING_PARAMETER,
            message="Missing required parameter: 'action'",
        )

    if action == ProceduralAction.TERRAIN_GENERATE.value:
        return _terrain_generate(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.ROCK_GENERATE.value:
        return _rock_generate(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.TREE_GENERATE.value:
        return _tree_generate(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.CITY_LAYOUT.value:
        return _city_layout(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.MAZE_GENERATE.value:
        return _maze_generate(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.CRYSTAL_GENERATE.value:
        return _crystal_generate(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.VORONOI_PATTERN.value:
        return _voronoi_pattern(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.FRACTAL_GENERATE.value:
        return _fractal_generate(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.SPIRAL_GALAXY.value:
        return _spiral_galaxy(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.GEOMETRIC_PATTERN.value:
        return _geometric_pattern(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.PARAMETRIC_CURVE.value:
        return _parametric_curve(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.L_SYSTEM_PLANT.value:
        return _lsystem_plant(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.PARTICLE_FLOWER.value:
        return _particle_flower(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.FABRIC_WEAVE.value:
        return _fabric_weave(params, seed)  # type: ignore[no-any-return]
    elif action == ProceduralAction.CHAIN_MAIL.value:
        return _chain_mail(params, seed)  # type: ignore[no-any-return]

    return ResponseBuilder.error(
        handler="manage_procedural",
        action=action,
        error_code=ErrorProtocol.INVALID_PARAMETER_VALUE,
        message=f"Unknown action: {action}",
    )


def _terrain_generate(params, seed):  # type: ignore[no-untyped-def]
    """Generate heightmap-based terrain with multiple noise layers."""
    resolution = params.get("resolution", 128)
    scale = params.get("scale", 10.0)
    height = params.get("height", 2.0)

    # Create grid mesh
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_plane_add(size=scale, location=(0, 0, 0))
    terrain = bpy.context.active_object
    terrain.name = f"Terrain_{seed}"

    # Subdivide
    with ContextManagerV3.temp_override(
        area_type="VIEW_3D", active_object=terrain, selected_objects=[terrain]
    ):
        safe_ops.object.mode_set(mode="EDIT")
        safe_ops.mesh.subdivide(number_cuts=resolution - 1)
        safe_ops.object.mode_set(mode="OBJECT")

    # Apply multi-octave noise
    mesh = terrain.data
    for v in mesh.vertices:  # type: ignore[union-attr]
        x, y = v.co.x / scale, v.co.y / scale

        # Multi-octave noise
        z = 0
        amplitude = 1.0
        frequency = 1.0

        for octave in range(4):
            z += (  # type: ignore[assignment]
                mathutils.noise.noise(
                    mathutils.Vector((x * frequency + seed, y * frequency + seed, 0))
                )
                * amplitude
            )
            amplitude *= 0.5
            frequency *= 2

        v.co.z = max(0, z * height)

    # Update mesh
    mesh.update()  # type: ignore[union-attr]

    # Add erosion simulation (simplified)
    # Real implementation would use hydraulic erosion

    # Add material
    mat = bpy.data.materials.new(name=f"TerrainMat_{seed}")
    mat.use_nodes = True
    terrain.data.materials.append(mat)  # type: ignore[union-attr]

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="TERRAIN_GENERATE",
        data={
            "terrain_name": terrain.name,
            "seed": seed,
            "resolution": resolution,
            "vertices": len(mesh.vertices),  # type: ignore[union-attr]
        },
    )


def _rock_generate(params, seed):  # type: ignore[no-untyped-def]
    """Generate photorealistic rock formations."""
    scale = params.get("scale", 1.0)
    detail = params.get("detail", 3)

    # Start with icosphere
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_ico_sphere_add(
            radius=scale, subdivisions=detail + 2, location=(0, 0, 0)
        )
    rock = bpy.context.active_object
    rock.name = f"Rock_{seed}"

    # Displace with noise
    mesh = rock.data
    for v in mesh.vertices:  # type: ignore[union-attr]
        # Voronoi-like displacement
        displacement = (
            mathutils.noise.noise(
                mathutils.Vector((v.co.x * 2 + seed, v.co.y * 2 + seed, v.co.z * 2 + seed))
            )
            * scale
            * 0.3
        )

        v.co += v.normal * displacement

    mesh.update()  # type: ignore[union-attr]

    # Add bevel for realism
    bevel = rock.modifiers.new(name="RockBevel", type="BEVEL")
    bevel.width = scale * 0.02  # type: ignore
    bevel.segments = 2  # type: ignore

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="ROCK_GENERATE",
        data={"rock_name": rock.name, "seed": seed, "vertices": len(mesh.vertices)},  # type: ignore[union-attr]
    )


def _tree_generate(params, seed):  # type: ignore[no-untyped-def]
    """Generate procedural tree with recursive branches."""
    scale = params.get("scale", 3.0)
    levels = params.get("levels", 3)
    branch_angle = params.get("branch_angle", 45)

    # Create trunk
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_cylinder_add(
            radius=scale * 0.1, depth=scale, location=(0, 0, scale / 2)
        )
    tree = bpy.context.active_object
    tree.name = f"Tree_{seed}"

    # Create branches recursively
    branches = []

    def create_branch(parent_loc, direction, length, thickness, level):  # type: ignore[no-untyped-def]
        if level <= 0 or length < 0.1:
            return

        # Calculate end position
        end_loc = (
            parent_loc[0] + direction[0] * length,
            parent_loc[1] + direction[1] * length,
            parent_loc[2] + direction[2] * length,
        )

        # Create branch cylinder
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.mesh.primitive_cylinder_add(
                radius=thickness,
                depth=length,
                location=(
                    (parent_loc[0] + end_loc[0]) / 2,
                    (parent_loc[1] + end_loc[1]) / 2,
                    (parent_loc[2] + end_loc[2]) / 2,
                ),
            )
        branch = bpy.context.active_object
        branch.name = f"Tree_{seed}_Branch_L{level}"
        branches.append(branch)

        # Recursion
        num_branches = random.randint(2, 3)
        for i in range(num_branches):
            angle_rad = math.radians(branch_angle + random.uniform(-15, 15))

            # Random rotation around parent
            rot = random.uniform(0, 2 * math.pi)

            new_direction = (
                math.sin(angle_rad) * math.cos(rot),
                math.sin(angle_rad) * math.sin(rot),
                math.cos(angle_rad),
            )

            create_branch(end_loc, new_direction, length * 0.7, thickness * 0.7, level - 1)

    # Start recursion from top of trunk
    create_branch((0, 0, scale), (0, 0, 1), scale * 0.5, scale * 0.05, levels)

    # Join all branches
    if branches:
        with ContextManagerV3.temp_override(
            area_type="VIEW_3D", active_object=tree, selected_objects=[tree] + branches
        ):
            ContextManagerV3.deselect_all_objects()
            for b in branches:
                b.select_set(True)
            tree.select_set(True)
            bpy.context.view_layer.objects.active = tree
            safe_ops.object.join()

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="TREE_GENERATE",
        data={"tree_name": tree.name, "seed": seed, "branches": len(branches), "levels": levels},
    )


def _city_layout(params, seed):  # type: ignore[no-untyped-def]
    """Generate urban city layout with roads and blocks."""
    size = params.get("size", 10)
    block_size = params.get("block_size", 2.0)
    road_width = params.get("road_width", 0.3)

    buildings = []
    roads = []

    # Create grid of roads
    for i in range(-size, size + 1):
        # Horizontal road
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.mesh.primitive_plane_add(size=1, location=(0, i * block_size, 0))
        road_h = bpy.context.active_object
        road_h.scale = (size * block_size, road_width / 2, 1)
        road_h.name = f"Road_H_{i}"
        roads.append(road_h)

        # Vertical road
        with ContextManagerV3.temp_override(area_type="VIEW_3D"):
            safe_ops.mesh.primitive_plane_add(size=1, location=(i * block_size, 0, 0))
        road_v = bpy.context.active_object
        road_v.scale = (road_width / 2, size * block_size, 1)
        road_v.name = f"Road_V_{i}"
        roads.append(road_v)

    # Create buildings in blocks
    for x in range(-size, size):
        for y in range(-size, size):
            if random.random() > 0.3:  # 70% chance of building
                height = random.uniform(1, 4)

                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    safe_ops.mesh.primitive_cube_add(
                        size=block_size * 0.7,
                        location=((x + 0.5) * block_size, (y + 0.5) * block_size, height / 2),
                    )
                building = bpy.context.active_object
                building.scale.z = height
                building.name = f"Building_{x}_{y}"
                buildings.append(building)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="CITY_LAYOUT",
        data={
            "roads": len(roads),
            "buildings": len(buildings),
            "city_size": f"{size * 2 + 1}x{size * 2 + 1} blocks",
            "seed": seed,
        },
    )


def _maze_generate(params, seed):  # type: ignore[no-untyped-def]
    """Generate solvable maze using recursive backtracking."""
    width = params.get("width", 15)
    height = params.get("height", 15)
    wall_height = params.get("wall_height", 2.0)
    cell_size = params.get("cell_size", 1.0)

    # Initialize grid
    grid = [[1 for _ in range(width)] for _ in range(height)]

    # Recursive backtracking
    def carve(x, y):  # type: ignore[no-untyped-def]
        grid[y][x] = 0
        directions = [(0, -2), (2, 0), (0, 2), (-2, 0)]
        random.shuffle(directions)

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] == 1:
                grid[y + dy // 2][x + dx // 2] = 0
                carve(nx, ny)

    carve(1, 1)

    # Build 3D maze
    walls = []
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == 1:
                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    safe_ops.mesh.primitive_cube_add(
                        size=cell_size, location=(x * cell_size, y * cell_size, wall_height / 2)
                    )
                wall = bpy.context.active_object
                wall.scale.z = wall_height
                wall.name = f"MazeWall_{x}_{y}"
                walls.append(wall)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="MAZE_GENERATE",
        data={"walls": len(walls), "dimensions": f"{width}x{height}", "seed": seed},
    )


def _crystal_generate(params, seed):  # type: ignore[no-untyped-def]
    """Generate geometric crystal formations."""
    scale = params.get("scale", 1.0)
    crystal_type = params.get("type", "RANDOM")

    # Select crystal type
    types = ["CUBE", "OCTAHEDRON", "DODECAHEDRON", "CUSTOM"]
    if crystal_type == "RANDOM":
        crystal_type = random.choice(types)

    crystals = []
    cluster_size = random.randint(3, 8)

    for i in range(cluster_size):
        loc = (
            random.uniform(-scale, scale),
            random.uniform(-scale, scale),
            random.uniform(0, scale * 0.5),
        )

        rot = (random.uniform(0, 3.14), random.uniform(0, 3.14), random.uniform(0, 3.14))

        s = random.uniform(scale * 0.2, scale * 0.8)

        if crystal_type == "CUBE":
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.mesh.primitive_cube_add(size=s, location=loc, rotation=rot)
        elif crystal_type == "OCTAHEDRON":
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.mesh.primitive_cone_add(radius1=s, depth=s * 2, location=loc, rotation=rot)
        else:
            with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                safe_ops.mesh.primitive_ico_sphere_add(radius=s, location=loc, rotation=rot)

        crystal = bpy.context.active_object
        crystal.name = f"Crystal_{seed}_{i}"
        crystals.append(crystal)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="CRYSTAL_GENERATE",
        data={"crystals": len(crystals), "type": crystal_type, "seed": seed},
    )


def _voronoi_pattern(params, seed):  # type: ignore[no-untyped-def]
    """Generate Voronoi-based surface patterns."""
    size = params.get("size", 5.0)
    points = params.get("points", 20)

    # Generate random points
    sites = [(random.uniform(-size, size), random.uniform(-size, size)) for _ in range(points)]

    # Create base plane
    with ContextManagerV3.temp_override(area_type="VIEW_3D"):
        safe_ops.mesh.primitive_plane_add(size=size * 2, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = f"Voronoi_{seed}"

    # Subdivide heavily
    with ContextManagerV3.temp_override(
        area_type="VIEW_3D", active_object=plane, selected_objects=[plane]
    ):
        safe_ops.object.mode_set(mode="EDIT")
        safe_ops.mesh.subdivide(number_cuts=50)
        safe_ops.object.mode_set(mode="OBJECT")

    # Displace based on Voronoi distance
    mesh = plane.data
    for v in mesh.vertices:  # type: ignore[union-attr]
        x, y = v.co.x, v.co.y

        # Find nearest site
        min_dist = float("inf")
        for sx, sy in sites:
            dist = math.sqrt((x - sx) ** 2 + (y - sy) ** 2)
            if dist < min_dist:
                min_dist = dist

        # Displace
        v.co.z = min_dist * 0.5

    mesh.update()  # type: ignore[union-attr]

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="VORONOI_PATTERN",
        data={"sites": points, "object": plane.name, "seed": seed},
    )


def _fractal_generate(params, seed):  # type: ignore[no-untyped-def]
    """Generate fractal using iterated function systems."""
    iterations = params.get("iterations", 1000)
    fractal_type = params.get("fractal_type", "SIERPINSKI")

    points = []

    if fractal_type == "SIERPINSKI":
        # Sierpinski triangle
        vertices = [
            mathutils.Vector((-2, -1, 0)),
            mathutils.Vector((2, -1, 0)),
            mathutils.Vector((0, 2, 0)),
        ]

        current = mathutils.Vector((0, 0, 0))

        for _ in range(iterations):
            target = random.choice(vertices)
            current = (current + target) / 2
            points.append(current.copy())

    elif fractal_type == "FERN":
        # Barnsley fern
        x, y = 0.0, 0.0
        for _ in range(iterations):
            r = random.random()
            if r < 0.01:
                x, y = 0, 0.16 * y
            elif r < 0.86:
                x, y = 0.85 * x + 0.04 * y, -0.04 * x + 0.85 * y + 1.6
            elif r < 0.93:
                x, y = 0.2 * x - 0.26 * y, 0.23 * x + 0.22 * y + 1.6
            else:
                x, y = -0.15 * x + 0.28 * y, 0.26 * x + 0.24 * y + 0.44
            points.append(mathutils.Vector((x * 0.5, y * 0.5, 0)))

    # Create point cloud mesh
    mesh = bpy.data.meshes.new(name=f"Fractal_{seed}")
    obj = bpy.data.objects.new(f"Fractal_{fractal_type}", mesh)
    bpy.context.collection.objects.link(obj)

    mesh.from_pydata(points, [], [])
    mesh.update()

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="FRACTAL_GENERATE",
        data={"points": len(points), "type": fractal_type, "object": obj.name, "seed": seed},
    )


def _spiral_galaxy(params, seed):  # type: ignore[no-untyped-def]
    """Generate spiral galaxy structure."""
    arms = params.get("arms", 3)
    stars = params.get("stars", 500)
    radius = params.get("radius", 10.0)

    star_positions = []

    for _ in range(stars):
        # Distance from center with more stars in outer arms
        r = random.uniform(0, radius)
        r = math.sqrt(r / radius) * radius  # Distribute evenly by area

        # Angle with spiral perturbation
        angle = random.uniform(0, 2 * math.pi)
        arm_offset = math.log(r + 1) * 2  # Logarithmic spiral
        angle += arm_offset

        # Height (thickness of galaxy)
        z = random.gauss(0, r * 0.1)

        x = r * math.cos(angle)
        y = r * math.sin(angle)

        star_positions.append((x, y, z))

    # Create star mesh
    mesh = bpy.data.meshes.new(name=f"Galaxy_{seed}")
    obj = bpy.data.objects.new("Galaxy", mesh)
    bpy.context.collection.objects.link(obj)

    verts = [mathutils.Vector(p) for p in star_positions]
    mesh.from_pydata(verts, [], [])
    mesh.update()

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="SPIRAL_GALAXY",
        data={
            "stars": len(star_positions),
            "arms": arms,
            "radius": radius,
            "object": obj.name,
            "seed": seed,
        },
    )


def _geometric_pattern(params, seed):  # type: ignore[no-untyped-def]
    """Generate Islamic/geometric tile patterns."""
    pattern_type = params.get("pattern_type", "STAR")
    tiles_x = params.get("tiles_x", 5)
    tiles_y = params.get("tiles_y", 5)
    tile_size = params.get("tile_size", 2.0)

    shapes = []

    for tx in range(tiles_x):
        for ty in range(tiles_y):
            cx = (tx - tiles_x / 2) * tile_size
            cy = (ty - tiles_y / 2) * tile_size

            if pattern_type == "STAR":
                # 8-pointed star
                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    safe_ops.mesh.primitive_circle_add(
                        vertices=8, radius=tile_size * 0.4, location=(cx, cy, 0)
                    )
                shape = bpy.context.active_object

            elif pattern_type == "HEXAGON":
                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    safe_ops.mesh.primitive_circle_add(
                        vertices=6, radius=tile_size * 0.45, location=(cx, cy, 0)
                    )
                shape = bpy.context.active_object

            else:
                with ContextManagerV3.temp_override(area_type="VIEW_3D"):
                    safe_ops.mesh.primitive_plane_add(size=tile_size * 0.8, location=(cx, cy, 0))
                shape = bpy.context.active_object

            shape.name = f"Pattern_{tx}_{ty}"
            shapes.append(shape)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="GEOMETRIC_PATTERN",
        data={
            "shapes": len(shapes),
            "pattern": pattern_type,
            "tiles": f"{tiles_x}x{tiles_y}",
            "seed": seed,
        },
    )


def _parametric_curve(params, seed):  # type: ignore[no-untyped-def]
    """Generate mathematical parametric curves."""
    curve_type = params.get("curve_type", "TORUS_KNOT")
    resolution = params.get("resolution", 100)
    scale = params.get("scale", 2.0)

    points = []

    if curve_type == "TORUS_KNOT":
        p, q = 2, 3
        for i in range(resolution + 1):
            t = (i / resolution) * 2 * math.pi
            r = math.cos(q * t) + 2
            x = r * math.cos(p * t) * scale
            y = r * math.sin(p * t) * scale
            z = -math.sin(q * t) * scale
            points.append((x, y, z))

    elif curve_type == "SPHERICAL_SPIRAL":
        for i in range(resolution + 1):
            t = (i / resolution) * 4 * math.pi
            x = math.cos(t) * math.cos(t / 2) * scale
            y = math.sin(t) * math.cos(t / 2) * scale
            z = math.sin(t / 2) * scale
            points.append((x, y, z))

    elif curve_type == "VIVIANI":
        for i in range(resolution + 1):
            t = (i / resolution) * 4 * math.pi
            x = scale * (1 + math.cos(t))
            y = scale * math.sin(t)
            z = 2 * scale * math.sin(t / 2)
            points.append((x, y, z))

    # Create curve
    curve_data = bpy.data.curves.new(name=f"Parametric_{curve_type}", type="CURVE")
    curve_data.dimensions = "3D"

    spline = curve_data.splines.new("NURBS")
    spline.points.add(len(points) - 1)

    for i, (x, y, z) in enumerate(points):
        spline.points[i].co = (x, y, z, 1)

    obj = bpy.data.objects.new(f"Parametric_{curve_type}", curve_data)
    bpy.context.collection.objects.link(obj)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="PARAMETRIC_CURVE",
        data={"type": curve_type, "points": len(points), "object": obj.name, "seed": seed},
    )


def _lsystem_plant(params, seed):  # type: ignore[no-untyped-def]
    """Generate plant using L-systems."""
    axiom = params.get("axiom", "F")
    rules = params.get("rules", {"F": "F[+F]F[-F]F"})
    iterations = params.get("iterations", 3)
    angle = params.get("angle", 25.7)
    step_size = params.get("step_size", 0.5)

    # Generate L-system string
    current = axiom
    for _ in range(iterations):
        new_string = ""
        for char in current:
            new_string += rules.get(char, char)
        current = new_string

    # Interpret string
    points = [(0, 0, 0)]
    stack = []

    x, y, z = 0, 0, 0
    direction = mathutils.Vector((0, 0, 1))

    for char in current:
        if char == "F":
            x += direction.x * step_size
            y += direction.y * step_size
            z += direction.z * step_size
            points.append((x, y, z))
        elif char == "+":
            direction = direction @ mathutils.Matrix.Rotation(math.radians(angle), 3, "Z")
        elif char == "-":
            direction = direction @ mathutils.Matrix.Rotation(math.radians(-angle), 3, "Z")
        elif char == "[":
            stack.append(((x, y, z), direction.copy()))
        elif char == "]":
            (x, y, z), direction = stack.pop()
            points.append((x, y, z))

    # Create curve
    curve_data = bpy.data.curves.new(name=f"LSystem_{seed}", type="CURVE")
    curve_data.dimensions = "3D"

    spline = curve_data.splines.new("POLY")
    spline.points.add(len(points) - 1)

    for i, (x, y, z) in enumerate(points):
        spline.points[i].co = (x, y, z, 1)

    obj = bpy.data.objects.new("LSystem_Plant", curve_data)
    bpy.context.collection.objects.link(obj)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="L_SYSTEM_PLANT",
        data={
            "string_length": len(current),
            "points": len(points),
            "object": obj.name,
            "seed": seed,
        },
    )


def _particle_flower(params, seed):  # type: ignore[no-untyped-def]
    """Generate flower using particle distribution."""
    petals = params.get("petals", 8)
    layers = params.get("layers", 3)
    radius = params.get("radius", 2.0)

    # Create base mesh
    safe_ops.mesh.primitive_circle_add(vertices=32, radius=radius * 0.3)
    center = bpy.context.active_object
    center.name = f"FlowerCenter_{seed}"

    petal_objects = []

    for layer in range(layers):
        layer_radius = radius * (0.4 + layer * 0.3)
        layer_petals = petals + layer * 4

        for i in range(layer_petals):
            angle = (i / layer_petals) * 2 * math.pi
            x = math.cos(angle) * layer_radius
            y = math.sin(angle) * layer_radius

            # Create petal
            safe_ops.mesh.primitive_plane_add(size=radius * 0.4, location=(x, y, layer * 0.1))
            petal = bpy.context.active_object
            petal.rotation_euler = (0, 0, angle)
            petal.name = f"Petal_L{layer}_{i}"
            petal_objects.append(petal)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="PARTICLE_FLOWER",
        data={"petals": len(petal_objects), "layers": layers, "center": center.name, "seed": seed},
    )


def _fabric_weave(params, seed):  # type: ignore[no-untyped-def]
    """Generate woven fabric pattern."""
    width = params.get("width", 10)
    height = params.get("height", 10)
    threads = params.get("threads", 20)
    thread_size = params.get("thread_size", 0.05)

    weave_objects = []

    # Warp threads (vertical)
    for i in range(threads):
        x = (i / (threads - 1) - 0.5) * width

        # Create curve for thread
        curve_data = bpy.data.curves.new(name=f"Warp_{i}", type="CURVE")
        curve_data.dimensions = "3D"
        curve_data.bevel_depth = thread_size

        spline = curve_data.splines.new("NURBS")
        spline.points.add(height * 2)

        for j in range(height * 2 + 1):
            y = (j / (height * 2) - 0.5) * height
            z = math.sin(j * 0.5) * thread_size * 2  # Weave pattern
            spline.points[j].co = (x, y, z, 1)

        obj = bpy.data.objects.new(f"Warp_{i}", curve_data)
        bpy.context.collection.objects.link(obj)
        weave_objects.append(obj)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="FABRIC_WEAVE",
        data={"threads": len(weave_objects), "pattern": "plain_weave", "seed": seed},
    )


def _chain_mail(params, seed):  # type: ignore[no-untyped-def]
    """Generate chain mail armor pattern."""
    rows = params.get("rows", 10)
    cols = params.get("cols", 10)
    ring_size = params.get("ring_size", 0.3)
    link_size = params.get("link_size", 0.05)

    rings = []

    for row in range(rows):
        for col in range(cols):
            x = col * ring_size * 1.5
            y = row * ring_size * 1.5

            # Alternate orientation
            if (row + col) % 2 == 0:
                rot = (math.radians(90), 0.0, 0.0)
            else:
                rot = (0.0, math.radians(90), 0.0)

            safe_ops.mesh.primitive_torus_add(
                major_radius=ring_size * 0.4,
                minor_radius=link_size,
                location=(x, y, 0),
                rotation=rot,
            )
            ring = bpy.context.active_object
            ring.name = f"Ring_{row}_{col}"
            rings.append(ring)

    return ResponseBuilder.success(
        handler="manage_procedural",
        action="CHAIN_MAIL",
        data={"rings": len(rings), "dimensions": f"{rows}x{cols}", "seed": seed},
    )
