"""
BMesh High-Performance Operations Module for Blender MCP 1.0.0

Implements efficient mesh editing using bmesh module.
BMesh is 1000x faster than bpy.ops for batch operations.

High Mode Philosophy: Performance is not optional.
"""

from typing import Dict, Any, List, Optional, Tuple, Iterator
from contextlib import contextmanager

try:
    import bpy
    import bmesh

    import mathutils
    from mathutils import Vector, Matrix, Euler

    BPY_AVAILABLE = True
except ImportError:
    BPY_AVAILABLE = False
    bpy: Any = None  # type: ignore[no-redef]
    bmesh: Any = None  # type: ignore[no-redef]
    mathutils = None

from .thread_safety import ensure_main_thread
from .error_protocol import ErrorProtocol, create_error
from .logging_config import get_logger

logger = get_logger()


@contextmanager
def bmesh_from_object(
    obj: Any, use_edit_mesh: bool = True
) -> Iterator[Optional["bmesh.types.BMesh"]]:
    """
    Context manager for safe bmesh operations.
    Automatically handles from_mesh/to_mesh and cleanup.

    Usage:
        with bmesh_from_object(obj) as bm:
            bm.verts[0].co.x += 1.0
            bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=2)
    """
    if not BPY_AVAILABLE or obj.type != "MESH":
        yield None
        return

    bm = None
    try:
        # Check if in edit mode
        if obj.mode == "EDIT" and use_edit_mesh:
            bm = bmesh.from_edit_mesh(obj.data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj.data)

        # Ensure lookup tables
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        yield bm

        # Write back
        if obj.mode == "EDIT" and use_edit_mesh:
            bmesh.update_edit_mesh(obj.data)
        else:
            bm.to_mesh(obj.data)
            obj.data.update()
            if BPY_AVAILABLE and bpy.context.view_layer:
                bpy.context.view_layer.update()

    finally:
        if bm and (obj.mode != "EDIT" or not use_edit_mesh):
            bm.free()


class BMeshOperations:
    """
    High-performance mesh operations using BMesh.
    """

    @staticmethod
    @ensure_main_thread
    def subdivide_mesh(
        obj: Any,
        cuts: int = 1,
        use_smooth: bool = False,
        fractal: float = 0.0,
        along_normal: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Subdivide mesh edges efficiently.

        1000x faster than bpy.ops.mesh.subdivide for complex meshes.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                # Get all edges or selected
                edges = bm.edges[:]

                result = bmesh.ops.subdivide_edges(
                    bm,
                    edges=edges,
                    cuts=cuts,
                    smooth=1.0 if use_smooth else 0.0,
                    fractal=fractal,
                    along_normal=along_normal,
                )

                new_faces = len(result.get("geom", []))

            return {
                "success": True,
                "object": obj.name,
                "operation": "subdivide_edges",
                "cuts": cuts,
                "new_faces": new_faces,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Subdivide failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def extrude_faces(
        obj: Any,
        faces_indices: Optional[List[int]] = None,
        normal_offset: float = 0.0,
        individual: bool = False,
    ) -> Dict[str, Any]:
        """
        Extrude faces with high performance.

        Args:
            obj: Mesh object
            faces_indices: Specific faces to extrude (None = all)
            normal_offset: Offset along face normal
            individual: Extrude faces individually
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                # Get faces
                if faces_indices:
                    faces = [bm.faces[i] for i in faces_indices if i < len(bm.faces)]
                else:
                    faces = bm.faces[:]

                if not faces:
                    return create_error(
                        ErrorProtocol.NO_MESH_DATA, custom_message="No faces to extrude"
                    )

                # Extrude
                if individual:
                    result = bmesh.ops.inset_individual(
                        bm, faces=faces, thickness=0.0, depth=normal_offset
                    )
                else:
                    result = bmesh.ops.extrude_discrete_faces(bm, faces=faces)

                    # Move extruded faces
                    extruded_faces = result.get("faces", [])
                    for face in extruded_faces:
                        vec = face.normal * normal_offset
                        bmesh.ops.translate(bm, vec=vec, verts=face.verts)

                new_faces = len(result.get("faces", []))

            return {
                "success": True,
                "object": obj.name,
                "operation": "extrude_faces",
                "faces_extruded": len(faces),
                "new_faces": new_faces,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Extrude failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def inset_faces(
        obj: Any,
        faces_indices: Optional[List[int]] = None,
        thickness: float = 0.1,
        depth: float = 0.0,
        use_even_offset: bool = True,
        use_boundary: bool = True,
        use_relative_offset: bool = False,
    ) -> Dict[str, Any]:
        """
        Inset faces with precise control.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                faces = [bm.faces[i] for i in faces_indices] if faces_indices else bm.faces[:]

                result = bmesh.ops.inset_individual(
                    bm,
                    faces=faces,
                    thickness=thickness,
                    depth=depth,
                    use_even_offset=use_even_offset,
                    use_boundary=use_boundary,
                    use_relative_offset=use_relative_offset,
                )

                inset_faces = len(result.get("faces", []))

            return {
                "success": True,
                "object": obj.name,
                "operation": "inset_faces",
                "faces_inset": inset_faces,
                "thickness": thickness,
                "depth": depth,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Inset failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def bevel_edges(
        obj: Any,
        edges_indices: Optional[List[int]] = None,
        offset: float = 0.1,
        segments: int = 2,
        profile: float = 0.5,
        offset_type: str = "OFFSET",
        clamp_overlap: bool = True,
    ) -> Dict[str, Any]:
        """
        Bevel edges with high performance.

        Args:
            offset: Bevel width/offset
            segments: Number of segments
            profile: Bevel profile (0.5 = round)
            offset_type: 'OFFSET', 'WIDTH', 'DEPTH', 'PERCENT'
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                edges = [bm.edges[i] for i in edges_indices] if edges_indices else bm.edges[:]

                kwargs = {
                    "geom": edges,
                    "segments": segments,
                    "profile": profile,
                    "affect": "EDGES",
                    "clamp_overlap": clamp_overlap,
                }

                # Blender 5.0 Fix: "offset_pct" was deprecated in favor of offset_type="PERCENT".
                if hasattr(bmesh.ops, "bevel") and bpy.app.version >= (5, 0, 0):
                    kwargs["offset_type"] = offset_type
                    # In percentage mode, offset is 0-100
                    kwargs["offset"] = offset * 100.0 if offset_type == "PERCENT" else offset
                else:
                    # Legacy fallback
                    kwargs["offset"] = offset
                    kwargs["offset_pct"] = offset * 100.0 if offset_type == "PERCENT" else 0.0

                result = bmesh.ops.bevel(bm, **kwargs)

                new_verts = len(result.get("verts", []))
                new_edges = len(result.get("edges", []))
                new_faces = len(result.get("faces", []))

            return {
                "success": True,
                "object": obj.name,
                "operation": "bevel_edges",
                "edges_beveled": len(edges),
                "new_verts": new_verts,
                "new_edges": new_edges,
                "new_faces": new_faces,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Bevel failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def dissolve_faces(
        obj: Any, faces_indices: Optional[List[int]] = None, use_verts: bool = False
    ) -> Dict[str, Any]:
        """
        Dissolve faces (merge adjacent faces).
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                faces = [bm.faces[i] for i in faces_indices] if faces_indices else bm.faces[:]

                bmesh.ops.dissolve_faces(bm, faces=faces, use_verts=use_verts)

                remaining_faces = len(bm.faces)

            return {
                "success": True,
                "object": obj.name,
                "operation": "dissolve_faces",
                "dissolved_count": len(faces),
                "remaining_faces": remaining_faces,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Dissolve failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def bridge_edge_loops(
        obj: Any,
        edges_indices_1: List[int],
        edges_indices_2: List[int],
        use_pairs: bool = False,
        use_cyclic: bool = False,
        use_merge: bool = False,
        merge_factor: float = 0.5,
        twist_offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Bridge edge loops efficiently.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                edges1 = [bm.edges[i] for i in edges_indices_1 if i < len(bm.edges)]
                edges2 = [bm.edges[i] for i in edges_indices_2 if i < len(bm.edges)]

                all_edges = edges1 + edges2

                result = bmesh.ops.bridge_loops(
                    bm,
                    edges=all_edges,
                    use_pairs=use_pairs,
                    use_cyclic=use_cyclic,
                    use_merge=use_merge,
                    merge_factor=merge_factor,
                    twist_offset=twist_offset,
                )

                new_faces = len(result.get("faces", []))

            return {
                "success": True,
                "object": obj.name,
                "operation": "bridge_edge_loops",
                "loops_bridged": 2,
                "new_faces": new_faces,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Bridge failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def bisect_mesh(
        obj: Any,
        plane_co: Tuple[float, float, float],
        plane_no: Tuple[float, float, float],
        clear_inner: bool = False,
        clear_outer: bool = False,
        use_fill: bool = True,
        threshold: float = 0.0001,
    ) -> Dict[str, Any]:
        """
        Bisect mesh with a plane.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                geom = bm.verts[:] + bm.edges[:] + bm.faces[:]

                result = bmesh.ops.bisect_plane(
                    bm,
                    geom=geom,
                    dist=threshold,
                    plane_co=plane_co,
                    plane_no=plane_no,
                    clear_inner=clear_inner,
                    clear_outer=clear_outer,
                    use_fill=use_fill,
                )

                new_faces = len(result.get("geom_cut", []))

            return {
                "success": True,
                "object": obj.name,
                "operation": "bisect_plane",
                "plane_co": plane_co,
                "plane_no": plane_no,
                "faces_cut": new_faces,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Bisect failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def smooth_vertices(
        obj: Any,
        verts_indices: Optional[List[int]] = None,
        factor: float = 0.5,
        iterations: int = 1,
    ) -> Dict[str, Any]:
        """
        Smooth vertices using Laplacian smoothing.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                verts = [bm.verts[i] for i in verts_indices] if verts_indices else bm.verts[:]

                for _ in range(iterations):
                    bmesh.ops.smooth_vert(
                        bm,
                        verts=verts,
                        factor=factor,
                        use_axis_x=True,
                        use_axis_y=True,
                        use_axis_z=True,
                    )

            return {
                "success": True,
                "object": obj.name,
                "operation": "smooth_vertices",
                "vertices_smoothed": len(verts),
                "iterations": iterations,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Smooth failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def recalc_normals(
        obj: Any, faces_indices: Optional[List[int]] = None, inside: bool = False
    ) -> Dict[str, Any]:
        """
        Recalculate face normals.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                faces = [bm.faces[i] for i in faces_indices] if faces_indices else bm.faces[:]

                bmesh.ops.recalc_face_normals(bm, faces=faces)

            return {
                "success": True,
                "object": obj.name,
                "operation": "recalc_normals",
                "faces_processed": len(faces),
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Normal recalc failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def merge_by_distance(
        obj: Any, dist: float = 0.0001, verts_indices: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Merge vertices by distance (weld).
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                verts = [bm.verts[i] for i in verts_indices] if verts_indices else bm.verts[:]

                result = bmesh.ops.remove_doubles(bm, verts=verts, dist=dist)

                merged = len(result.get("targetmap", {}))

            return {
                "success": True,
                "object": obj.name,
                "operation": "merge_by_distance",
                "merged_verts": merged,
                "threshold": dist,
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Merge failed: {str(e)}"
            )

    @staticmethod
    @ensure_main_thread
    def transform_mesh(
        obj: Any,
        translate: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        rotate: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        verts_indices: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Safely transform BMesh geometry (Bug 1B fix).
        Converts array/float to safe Vectors/Matrices.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            with bmesh_from_object(obj) as bm:
                if not bm:
                    return create_error(ErrorProtocol.NO_MESH_DATA, object_name=obj.name)

                verts = [bm.verts[i] for i in verts_indices] if verts_indices else bm.verts[:]

                # Validation array checks
                tv = Vector(translate)
                rv = Euler(rotate, "XYZ")
                sv = Vector(scale)

                if sv.length_squared != 3.0:  # Avoid scale(1,1,1) if unchanged
                    matrix_scale = Matrix.Diagonal((sv.x, sv.y, sv.z, 1.0))
                    bmesh.ops.scale(bm, vec=sv, space=matrix_scale, verts=verts)

                if rv.x != 0.0 or rv.y != 0.0 or rv.z != 0.0:
                    matrix_rot = rv.to_matrix().to_4x4()
                    bmesh.ops.rotate(bm, matrix=matrix_rot, verts=verts)

                if tv.length_squared > 0:
                    bmesh.ops.translate(bm, vec=tv, verts=verts)

            return {
                "success": True,
                "object": obj.name,
                "operation": "transform_mesh",
                "transformed_verts": len(verts),
                "translate": str(tv),
                "rotate": str(rv),
                "scale": str(sv),
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Transform failed: {str(e)}"
            )


class BMeshTopologyAnalysis:
    """
    Analyze mesh topology using BMesh.
    """

    @staticmethod
    @ensure_main_thread
    def analyze_mesh(obj: Any) -> Dict[str, Any]:
        """
        Comprehensive mesh topology analysis.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            bm = bmesh.new()
            bm.from_mesh(obj.data)

            # Basic stats
            # Blender 5.0: BMLoopSeq (bm.loops) lost __len__ support.
            # Sum face-vertex counts instead — equivalent for well-formed meshes.
            stats: Dict[str, Any] = {
                "vertices": len(bm.verts),
                "edges": len(bm.edges),
                "faces": len(bm.faces),
                "loops": sum(len(f.verts) for f in bm.faces),
            }

            # Triangles and quads
            tris = sum(1 for f in bm.faces if len(f.verts) == 3)
            quads = sum(1 for f in bm.faces if len(f.verts) == 4)
            ngons = sum(1 for f in bm.faces if len(f.verts) > 4)

            stats.update({"triangles": tris, "quads": quads, "ngons": ngons})

            # Edge analysis
            boundary_edges = sum(1 for e in bm.edges if e.is_boundary)
            manifold_edges = sum(1 for e in bm.edges if e.is_manifold)
            seam_edges = sum(1 for e in bm.edges if e.seam)
            sharp_edges = sum(1 for e in bm.edges if e.smooth is False)

            stats.update(
                {
                    "boundary_edges": boundary_edges,
                    "manifold_edges": manifold_edges,
                    "seam_edges": seam_edges,
                    "sharp_edges": sharp_edges,
                }
            )

            # Check for common issues
            issues = []
            if ngons > 0:
                issues.append(f"{ngons} ngons detected")
            if boundary_edges > 0:
                issues.append(f"{boundary_edges} boundary edges (non-manifold)")

            stats["issues"] = issues
            stats["is_manifold"] = boundary_edges == 0 and ngons == 0

            bm.free()

            return {"success": True, "object": obj.name, "topology": stats}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"Topology analysis failed: {str(e)}"
            )

    @staticmethod
    def select_non_manifold(obj: Any) -> Dict[str, Any]:
        """
        Select non-manifold geometry.
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            bm = bmesh.new()
            bm.from_mesh(obj.data)

            non_manifold = []
            for e in bm.edges:
                if e.is_boundary or not e.is_manifold:
                    non_manifold.append(e.index)

            bm.free()

            return {
                "success": True,
                "object": obj.name,
                "non_manifold_edges": non_manifold,
                "count": len(non_manifold),
            }

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR,
                custom_message=f"Non-manifold detection failed: {str(e)}",
            )


class BMeshUVOperations:
    """
    UV operations using BMesh.
    """

    @staticmethod
    def unwrap_basic(obj: Any, method: str = "ANGLE_BASED") -> Dict[str, Any]:
        """
        Basic UV unwrapping (requires bpy.ops fallback).
        """
        if not BPY_AVAILABLE:
            return create_error(ErrorProtocol.NO_CONTEXT)

        try:
            # Ensure UV layer exists
            if not obj.data.uv_layers:
                obj.data.uv_layers.new(name="UVMap")

            # Select all faces in bmesh
            bm = bmesh.new()
            bm.from_mesh(obj.data)

            for face in bm.faces:
                face.select = True

            bm.to_mesh(obj.data)
            bm.free()

            # Use operator for unwrap (requires proper context)
            if bpy.context.view_layer:
                bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")

            if method == "ANGLE_BASED":
                bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=0.001)
            elif method == "CONFORMAL":
                bpy.ops.uv.unwrap(method="CONFORMAL", margin=0.001)

            bpy.ops.object.mode_set(mode="OBJECT")

            return {"success": True, "object": obj.name, "method": method}

        except Exception as e:
            return create_error(
                ErrorProtocol.EXECUTION_ERROR, custom_message=f"UV unwrap failed: {str(e)}"
            )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "bmesh_from_object",
    "BMeshOperations",
    "BMeshTopologyAnalysis",
    "BMeshUVOperations",
]
