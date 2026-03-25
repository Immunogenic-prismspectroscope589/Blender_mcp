def get_aabb(obj):
    """
    Get World-Space Axis Aligned Bounding Box.
    Returns: min_vec, max_vec ([x,y,z], [x,y,z])
    """
    import mathutils

    if not obj:
        return [0, 0, 0], [0, 0, 0]

    bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    min_x = min(v.x for v in bbox_corners)
    max_x = max(v.x for v in bbox_corners)
    min_y = min(v.y for v in bbox_corners)
    max_y = max(v.y for v in bbox_corners)
    min_z = min(v.z for v in bbox_corners)
    max_z = max(v.z for v in bbox_corners)

    return [min_x, min_y, min_z], [max_x, max_y, max_z]
