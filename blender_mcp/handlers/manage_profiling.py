"""Performance Profiling & Diagnostics Handler for Blender MCP - V1.0.0 Refactored

Safe, thread-aware operations with:
- Thread safety (main thread execution)
- Context validation
- Crash prevention for modal operators
- Structured error handling
- Performance tracking

High Mode Philosophy: Maximum power, maximum safety.
"""

from collections import defaultdict
from typing import Dict, Any, List, cast

import bmesh

try:
    import bpy

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
from ..dispatcher import register_handler


from ..core.parameter_validator import validated_handler
from ..core.enums import ProfilingAction
from ..core.thread_safety import ensure_main_thread
from ..core.response_builder import ResponseBuilder
from ..core.logging_config import get_logger
from ..core.validation_utils import ValidationUtils

logger = get_logger()


@register_handler(
    "manage_profiling",
    actions=[a.value for a in ProfilingAction],
    category="general",
    schema={
        "type": "object",
        "title": "Performance Profiler",
        "description": "Scene analysis, optimization recommendations, and bottleneck detection.",
        "properties": {
            "action": ValidationUtils.generate_enum_schema(ProfilingAction, "Profiling operation"),
            "object_name": {
                "type": "string",
                "description": "Target object for single-object analysis",
            },
            "threshold": {
                "type": "integer",
                "default": 10000,
                "description": "Vertex count threshold for 'heavy' classification",
            },
            "check_duplicates": {
                "type": "boolean",
                "default": True,
                "description": "Check for duplicate mesh data",
            },
            "detailed": {
                "type": "boolean",
                "default": False,
                "description": "Include detailed vertex/edge/face analysis",
            },
        },
        "required": ["action"],
    },
)
@ensure_main_thread
@validated_handler(actions=[a.value for a in ProfilingAction])
def manage_profiling(action: str | None = None, **params: Any) -> dict[str, Any]:
    """
    Comprehensive scene profiling and optimization analysis.
    """

    def get_mesh_tri_count(mesh):  # type: ignore[no-untyped-def]
        """Calculate triangle count from mesh polygons."""
        return sum(len(p.vertices) - 2 for p in mesh.polygons)

    def format_bytes(bytes_val):  # type: ignore[no-untyped-def]
        """Format bytes to human readable."""
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_val < 1024:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.2f} TB"

    # 1. SCENE_STATS
    if not action:
        return ResponseBuilder.error(
            handler="manage_profiling",
            action=action,
            error_code="MISSING_PARAMETER",
            message="Missing required parameter: 'action'",
        )

    if action == ProfilingAction.SCENE_STATS.value:
        stats: Dict[str, Any] = {
            "objects": {
                "total": 0,
                "mesh": 0,
                "armature": 0,
                "light": 0,
                "camera": 0,
                "empty": 0,
                "other": 0,
            },
            "geometry": {"total_vertices": 0, "total_edges": 0, "total_faces": 0, "total_tris": 0},
            "materials": {"total": len(bpy.data.materials), "unused": 0},
            "textures": {"total": len(bpy.data.images), "unused": 0},
            "collections": len(bpy.data.collections),
            "scenes": len(bpy.data.scenes),
        }

        # Count objects
        for obj in bpy.data.objects:
            stats["objects"]["total"] += 1
            if obj.type == "MESH":
                stats["objects"]["mesh"] += 1
                if obj.data:
                    mesh_data = cast(bpy.types.Mesh, obj.data)
                    stats["geometry"]["total_vertices"] += len(mesh_data.vertices)
                    stats["geometry"]["total_edges"] += len(mesh_data.edges)
                    stats["geometry"]["total_faces"] += len(mesh_data.polygons)
                    stats["geometry"]["total_tris"] += get_mesh_tri_count(mesh_data)
            elif obj.type == "ARMATURE":
                stats["objects"]["armature"] += 1
            elif obj.type == "LIGHT":
                stats["objects"]["light"] += 1
            elif obj.type == "CAMERA":
                stats["objects"]["camera"] += 1
            elif obj.type == "EMPTY":
                stats["objects"]["empty"] += 1
            else:
                stats["objects"]["other"] += 1

        # Count unused materials
        for mat in bpy.data.materials:
            if mat.users == 0:
                stats["materials"]["unused"] += 1

        # Count unused textures
        for img in bpy.data.images:
            if img.users == 0:
                stats["textures"]["unused"] += 1

        return {"success": True, "scene": bpy.context.scene.name, "statistics": stats}

    # 2. MESH_ANALYSIS
    elif action == ProfilingAction.MESH_ANALYSIS.value:
        obj_name = params.get("object_name")
        if not obj_name:
            # Analyze all meshes
            heavy_threshold = params.get("threshold", 10000)
            meshes = []

            for obj in bpy.data.objects:
                if obj.type != "MESH" or not obj.data:
                    continue

                mesh = cast(bpy.types.Mesh, obj.data)
                tri_count = get_mesh_tri_count(mesh)

                mesh_info = {
                    "name": obj.name,
                    "vertices": len(mesh.vertices),
                    "edges": len(mesh.edges),
                    "polygons": len(mesh.polygons),
                    "triangles": tri_count,
                    "material_slots": len(obj.material_slots),
                    "modifiers": len(obj.modifiers),
                    "is_heavy": tri_count > heavy_threshold,
                    "has_custom_normals": mesh.has_custom_normals,
                    "uv_layers": len(mesh.uv_layers),
                    "vertex_colors": (
                        len(mesh.vertex_colors) if hasattr(mesh, "vertex_colors") else 0
                    ),
                    "shape_keys": len(mesh.shape_keys.key_blocks) if mesh.shape_keys else 0,
                }

                # Check for ngons (faces with > 4 vertices)
                ngons = sum(1 for p in mesh.polygons if len(p.vertices) > 4)
                mesh_info["ngons"] = ngons

                # Check for non-manifold geometry
                if params.get("detailed"):
                    bm = bmesh.new()
                    bm.from_mesh(mesh)
                    bm.verts.ensure_lookup_table()

                    non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
                    mesh_info["non_manifold_edges"] = non_manifold_edges

                    loose_verts = sum(1 for v in bm.verts if not v.link_edges)
                    mesh_info["loose_vertices"] = loose_verts

                    bm.free()

                meshes.append(mesh_info)

            # Sort by triangle count
            meshes.sort(key=lambda x: x["triangles"], reverse=True)

            return {
                "success": True,
                "mesh_count": len(meshes),
                "heavy_threshold": heavy_threshold,
                "heavy_objects": [m for m in meshes if m["is_heavy"]],
                "all_meshes": meshes if params.get("detailed") else None,
                "top_5_heaviest": meshes[:5],
            }
        else:
            # Single object analysis
            obj = bpy.data.objects.get(obj_name)
            if not obj or obj.type != "MESH":
                return ResponseBuilder.error(
                    handler="manage_profiling",
                    action="MESH_ANALYSIS",
                    error_code="OBJECT_NOT_FOUND",
                    message=f"Mesh object not found: {obj_name}",
                )

            mesh = cast(bpy.types.Mesh, obj.data)
            bm = bmesh.new()
            bm.from_mesh(mesh)

            analysis = {
                "name": obj.name,
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "triangles": get_mesh_tri_count(mesh),
                "ngons": sum(1 for p in mesh.polygons if len(p.vertices) > 4),
                "quads": sum(1 for p in mesh.polygons if len(p.vertices) == 4),
                "tris_count": sum(1 for p in mesh.polygons if len(p.vertices) == 3),
                "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold),
                "loose_vertices": sum(1 for v in bm.verts if not v.link_edges),
                "boundary_edges": sum(1 for e in bm.edges if e.is_boundary),
                "uv_layers": [
                    {"name": uv_layer.name, "active": uv_layer == mesh.uv_layers.active}
                    for uv_layer in mesh.uv_layers
                ],
                "materials": [
                    slot.material.name if slot.material else None for slot in obj.material_slots
                ],
                "modifiers": [{"name": m.name, "type": m.type} for m in obj.modifiers],
            }

            bm.free()

            return {"success": True, "analysis": analysis}

    # 3. MATERIAL_ANALYSIS
    elif action == ProfilingAction.MATERIAL_ANALYSIS.value:
        materials = []

        for mat in bpy.data.materials:
            if not params.get("detailed") and mat.users == 0:
                continue

            mat_info = {
                "name": mat.name,
                "users": mat.users,
                "use_nodes": mat.use_nodes,
                "node_count": len(mat.node_tree.nodes) if mat.use_nodes and mat.node_tree else 0,
            }

            if mat.use_nodes and mat.node_tree and params.get("detailed"):
                # Count texture nodes
                tex_nodes = [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"]
                mat_info["texture_nodes"] = len(tex_nodes)

                # Check for complex shaders
                has_principled = any(n.type == "BSDF_PRINCIPLED" for n in mat.node_tree.nodes)
                mat_info["has_principled_bsdf"] = has_principled

            materials.append(mat_info)

        return {
            "success": True,
            "total_materials": len(bpy.data.materials),
            "unused_materials": sum(1 for m in bpy.data.materials if m.users == 0),
            "materials": materials,
        }

    # 4. TEXTURE_ANALYSIS
    elif action == ProfilingAction.TEXTURE_ANALYSIS.value:
        textures: List[Dict[str, Any]] = []
        for img in bpy.data.images:
            tex_info = {
                "name": img.name,
                "filepath": img.filepath,
                "size": [img.size[0], img.size[1]],
                "channels": img.channels,
                "depth": img.depth,
                "users": img.users,
                "packed": img.packed_file is not None,
                "file_format": img.file_format,
                "colorspace": img.colorspace_settings.name,
            }

            # Calculate memory usage
            memory = img.size[0] * img.size[1] * img.channels * (img.depth // 8)
            tex_info["estimated_memory"] = format_bytes(memory)

            textures.append(tex_info)

        total_memory = sum(
            t["size"][0] * t["size"][1] * 4 / (1024 * 1024) if t["size"] else 0  # type: ignore
            for t in textures
            if t["size"][0] > 0
        )

        return {
            "success": True,
            "total_textures": len(textures),
            "total_estimated_memory": format_bytes(total_memory),
            "unused_textures": sum(1 for img in bpy.data.images if img.users == 0),
            "textures": textures,
        }

    # 5. RENDER_STATS
    elif action == ProfilingAction.RENDER_STATS.value:
        scene = bpy.context.scene
        render = scene.render
        cycles = scene.cycles if hasattr(scene, "cycles") else None

        stats = {
            "engine": render.engine,
            "resolution": [render.resolution_x, render.resolution_y],
            "resolution_percentage": render.resolution_percentage,
            "actual_resolution": [
                int(render.resolution_x * render.resolution_percentage / 100),
                int(render.resolution_y * render.resolution_percentage / 100),
            ],
            "pixel_count": 0,
            "frame_range": [scene.frame_start, scene.frame_end],
            "frame_count": scene.frame_end - scene.frame_start + 1,
        }

        stats["pixel_count"] = stats["actual_resolution"][0] * stats["actual_resolution"][1]

        if cycles:
            stats["cycles"] = {
                "device": cycles.device,
                "samples": cycles.samples,
                "preview_samples": cycles.preview_samples,
                "use_denoising": cycles.use_denoising,
                "max_bounces": cycles.max_bounces,
                "diffuse_bounces": cycles.diffuse_bounces,
                "glossy_bounces": cycles.glossy_bounces,
            }

        # Estimate render time (rough)
        if cycles:
            samples = cycles.samples
            pixels = stats["pixel_count"]
            # Very rough estimate: 1 sample per 100k pixels per second on GPU
            est_time_per_frame = (samples * pixels) / 100000000
            stats["estimated_time_per_frame"] = f"{est_time_per_frame:.1f}s"
            stats["estimated_total_time"] = f"{est_time_per_frame * stats['frame_count'] / 60:.1f}m"

        return {"success": True, "render_stats": stats}

    # 6. MEMORY_USAGE
    elif action == ProfilingAction.MEMORY_USAGE.value:
        import psutil
        import subprocess
        import os

        system_memory: Dict[str, Any] = {}
        vram_tracking: Dict[str, Any] = {}

        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            system_memory = {
                "process_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                "process_vms_mb": round(mem_info.vms / (1024 * 1024), 2),
                "cpu_percent": process.cpu_percent(interval=0.1),
                "ram_percent": round(process.memory_percent(), 2),
            }
        except Exception as e:
            system_memory = {"error": f"psutil failure: {str(e)}"}

        try:
            # Query nvidia-smi for VRAM independent of Blender's debug_value
            smi_out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                encoding="utf-8",
                timeout=2,
            )
            vram_lines = smi_out.strip().split("\n")
            if vram_lines:
                used, total = vram_lines[0].split(",")
                vram_tracking = {
                    "used_vram_mb": float(used.strip()),
                    "total_vram_mb": float(total.strip()),
                    "gpu_vram_percent": round(
                        (float(used.strip()) / max(float(total.strip()), 1.0)) * 100, 2
                    ),
                }
        except Exception:
            vram_tracking = {"status": "nvidia-smi not available or unsupported GPU"}

        memory = {  # type: ignore
            "system_psutil": system_memory,
            "gpu_vram": vram_tracking,
            "meshes": {"count": 0, "estimated_mb": 0},
            "images": {"count": 0, "estimated_mb": 0},
            "materials": {"count": len(bpy.data.materials), "estimated_mb": 0},
            "objects": {"count": len(bpy.data.objects), "estimated_mb": 0},
        }

        # Calculate mesh memory
        for mesh in bpy.data.meshes:
            memory["meshes"]["count"] += 1  # type: ignore
            # Rough estimate: 12 bytes per vertex (position), 8 bytes per edge, 12 bytes per face
            mesh_mem = len(mesh.vertices) * 12 + len(mesh.edges) * 8 + len(mesh.polygons) * 12
            memory["meshes"]["estimated_mb"] += mesh_mem / (1024 * 1024)  # type: ignore

        # Calculate image memory
        for img in bpy.data.images:
            memory["images"]["count"] += 1  # type: ignore
            if img.size[0] > 0 and img.size[1] > 0:
                img_mem = img.size[0] * img.size[1] * img.channels * (img.depth // 8)
                memory["images"]["estimated_mb"] += img_mem / (1024 * 1024)  # type: ignore

        total_mb = sum(m["estimated_mb"] for m in memory.values())  # type: ignore
        memory["total_estimated_mb"] = round(total_mb, 2)  # type: ignore

        return {"success": True, "memory_analysis": memory}

    # 7. FIND_HEAVY_OBJECTS
    elif action == ProfilingAction.FIND_HEAVY_OBJECTS.value:
        threshold = params.get("threshold", 10000)
        heavy = []

        for obj in bpy.data.objects:
            if obj.type != "MESH" or not obj.data:
                continue

            tri_count = get_mesh_tri_count(cast(bpy.types.Mesh, obj.data))
            if tri_count > threshold:
                heavy.append(
                    {
                        "name": obj.name,
                        "triangles": tri_count,
                        "vertices": len(cast(bpy.types.Mesh, obj.data).vertices),
                        "modifiers": len(obj.modifiers),
                        "suggestion": "Consider LOD or decimation",
                    }
                )

        heavy.sort(key=lambda x: x["triangles"], reverse=True)

        return {
            "success": True,
            "threshold": threshold,
            "heavy_object_count": len(heavy),
            "heavy_objects": heavy,
        }

    # 8. FIND_DUPLICATE_MESHES
    elif action == ProfilingAction.FIND_DUPLICATE_MESHES.value:
        """Find objects sharing the same mesh data (instancing candidates)."""
        mesh_users = defaultdict(list)

        for obj in bpy.data.objects:
            if obj.type == "MESH" and obj.data:
                mesh_users[obj.data.name].append(obj.name)

        duplicates = {k: v for k, v in mesh_users.items() if len(v) > 1}

        return {
            "success": True,
            "duplicate_groups": len(duplicates),
            "duplicates": [{"mesh": k, "objects": v} for k, v in duplicates.items()],
            "memory_savings_potential": f"{len(duplicates) * 10:.1f} MB (estimated)",
        }

    # 9. FIND_UNUSED_DATA
    elif action == ProfilingAction.FIND_UNUSED_DATA.value:
        unused = {
            "materials": [m.name for m in bpy.data.materials if m.users == 0],
            "images": [i.name for i in bpy.data.images if i.users == 0],
            "meshes": [m.name for m in bpy.data.meshes if m.users == 0],
            "textures": [],  # Legacy texture type
            "node_groups": [n.name for n in bpy.data.node_groups if n.users == 0],
            "actions": [a.name for a in bpy.data.actions if a.users == 0],
        }

        return {
            "success": True,
            "unused_data_blocks": {k: len(v) for k, v in unused.items()},
            "details": unused if params.get("detailed") else None,
        }

    # 10. OPTIMIZATION_REPORT
    elif action == ProfilingAction.OPTIMIZATION_REPORT.value:
        """Generate comprehensive optimization report."""
        report: Dict[str, Any] = {"summary": {}, "recommendations": [], "issues": []}

        # Scene size
        mesh_count = sum(1 for o in bpy.data.objects if o.type == "MESH")
        total_tris = sum(
            get_mesh_tri_count(cast(bpy.types.Mesh, o.data))
            for o in bpy.data.objects
            if o.type == "MESH" and o.data
        )

        report["summary"]["mesh_objects"] = mesh_count
        report["summary"]["total_triangles"] = total_tris
        report["summary"]["avg_tris_per_mesh"] = total_tris // mesh_count if mesh_count > 0 else 0

        # Check for performance issues
        if total_tris > 1000000:
            report["issues"].append(
                {
                    "severity": "HIGH",
                    "issue": "Scene has over 1 million triangles",
                    "recommendation": "Consider using LODs or reducing mesh complexity",
                }
            )

        # Check for heavy objects
        heavy_objects: List[Any] = [
            o
            for o in bpy.data.objects
            if o.type == "MESH"
            and o.data
            and get_mesh_tri_count(cast(bpy.types.Mesh, o.data)) > 50000
        ]
        if heavy_objects:
            report["issues"].append(
                {
                    "severity": "MEDIUM",
                    "issue": f"{len(heavy_objects)} objects have >50k triangles",
                    "objects": [o.name for o in heavy_objects],
                    "recommendation": "Split meshes or use Level of Detail (LOD)",
                }
            )

        # Check for ngons
        ngon_objects = []
        for obj in bpy.data.objects:
            if obj.type == "MESH" and obj.data:
                mesh_data = cast(bpy.types.Mesh, obj.data)
                ngons = sum(1 for p in mesh_data.polygons if len(p.vertices) > 4)
                if ngons > 0:
                    ngon_objects.append({"name": obj.name, "ngons": ngons})

        if ngon_objects:
            report["recommendations"].append(
                {
                    "type": "MESH_CLEANUP",
                    "message": f"{len(ngon_objects)} objects have ngons",
                    "objects": ngon_objects[:5],
                    "recommendation": "Triangulate or quad-convert before export",
                }
            )

        # Check unused data
        unused_mats = sum(1 for m in bpy.data.materials if m.users == 0)
        if unused_mats > 0:
            report["recommendations"].append(
                {
                    "type": "CLEANUP",
                    "message": f"{unused_mats} unused materials",
                    "recommendation": "Purge unused data blocks",
                }
            )

        # Texture size check
        oversized_textures = [i for i in bpy.data.images if i.size[0] > 4096 or i.size[1] > 4096]
        if oversized_textures:
            report["issues"].append(
                {
                    "severity": "LOW",
                    "issue": f"{len(oversized_textures)} textures > 4K resolution",
                    "recommendation": "Resize textures to 2K or 4K unless necessary",
                }
            )

        return {"success": True, "report": report}

    # 11. COMPARE_OBJECTS
    elif action == ProfilingAction.COMPARE_OBJECTS.value:
        """Compare two objects for similarity."""
        obj1_name = params.get("object_1")
        obj2_name = params.get("object_2")

        if not obj1_name or not obj2_name:
            return ResponseBuilder.error(
                handler="manage_profiling",
                action="COMPARE_OBJECTS",
                error_code="MISSING_PARAMETER",
                message="object_1 and object_2 are required",
            )

        obj1 = bpy.data.objects.get(obj1_name)
        obj2 = bpy.data.objects.get(obj2_name)

        if not obj1 or not obj2:
            return ResponseBuilder.error(
                handler="manage_profiling",
                action="COMPARE_OBJECTS",
                error_code="OBJECT_NOT_FOUND",
                message="One or both objects not found",
            )

        comparison = {
            "object_1": obj1_name,
            "object_2": obj2_name,
            "same_type": obj1.type == obj2.type,
            "same_vertex_count": False,
            "same_triangle_count": False,
            "same_material_count": False,
            "similarity_score": 0,
        }

        if obj1.type == "MESH" and obj2.type == "MESH" and obj1.data and obj2.data:
            mesh1 = cast(bpy.types.Mesh, obj1.data)
            mesh2 = cast(bpy.types.Mesh, obj2.data)
            v1, v2 = len(mesh1.vertices), len(mesh2.vertices)
            t1 = get_mesh_tri_count(mesh1)
            t2 = get_mesh_tri_count(mesh2)

            comparison["vertex_count"] = {"obj1": v1, "obj2": v2, "diff": abs(v1 - v2)}
            comparison["triangle_count"] = {"obj1": t1, "obj2": t2, "diff": abs(t1 - t2)}
            comparison["same_vertex_count"] = v1 == v2
            comparison["same_triangle_count"] = t1 == t2
            comparison["same_material_count"] = len(obj1.material_slots) == len(obj2.material_slots)

            # Simple similarity score
            if v1 == v2 and t1 == t2:
                comparison["similarity_score"] = 100
            elif v1 > 0 and v2 > 0:
                v_sim = 1 - (abs(v1 - v2) / max(v1, v2))
                t_sim = 1 - (abs(t1 - t2) / max(t1, t2))
                comparison["similarity_score"] = round((v_sim + t_sim) / 2 * 100, 1)

        return {"success": True, "comparison": comparison}

    # 12. ANALYZE_VIEWPORT
    elif action == ProfilingAction.ANALYZE_VIEWPORT.value:
        """Analyze current viewport settings for performance."""
        area = None
        for a in bpy.context.screen.areas:
            if a.type == "VIEW_3D":
                area = a
                break

        if not area:
            return ResponseBuilder.error(
                handler="manage_profiling",
                action="ANALYZE_VIEWPORT",
                error_code="NO_CONTEXT",
                message="No 3D viewport found",
            )

        space = area.spaces.active

        viewport_info = {
            "shading_type": space.shading.type,  # type: ignore
            "shading_light": space.shading.light if hasattr(space.shading, "light") else None,  # type: ignore
            "show_overlays": space.overlay.show_overlays,  # type: ignore
            "show_wireframes": space.overlay.show_wireframes,  # type: ignore
            "show_relationship_lines": space.overlay.show_relationship_lines,  # type: ignore
            "show_face_orientation": space.overlay.show_face_orientation,  # type: ignore
            "use_scene_lights": (
                space.shading.use_scene_lights  # type: ignore
                if hasattr(space.shading, "use_scene_lights")  # type: ignore
                else None
            ),
            "use_scene_world": (
                space.shading.use_scene_world if hasattr(space.shading, "use_scene_world") else None  # type: ignore
            ),
            "performance_recommendations": [],
        }

        # Performance recommendations
        if space.shading.type == "RENDERED":  # type: ignore
            viewport_info["performance_recommendations"].append("Rendered viewport is heavy on GPU")

        if space.overlay.show_overlays and len(bpy.data.objects) > 100:  # type: ignore
            viewport_info["performance_recommendations"].append(
                "Consider disabling overlays for many objects"
            )

        return {"success": True, "viewport": viewport_info}

    return ResponseBuilder.error(
        handler="manage_profiling",
        action=action,
        error_code="INVALID_PARAMETER_VALUE",
        message=f"Unknown action: {action}",
    )
