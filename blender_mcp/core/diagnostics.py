import bpy
from typing import Dict, List, Any


class SystemDoctor:
    """
    Staff+ Diagnostics: Audit System Health and Data Integrity.
    """

    @staticmethod
    def check_orphan_data() -> Dict[str, List[str]]:
        """
        Report unused data blocks (Meshes, Materials, etc.) with 0 users.
        """
        report = {}
        for attr in ["meshes", "materials", "textures", "images", "actions", "armatures"]:
            collection = getattr(bpy.data, attr)
            orphans = [item.name for item in collection if item.users == 0]
            if orphans:
                report[attr] = orphans
        return report

    @staticmethod
    def clean_orphan_data() -> int:
        """
        Aggressively remove unused data blocks.
        """
        count = 0
        for block in bpy.data.meshes:
            if block.users == 0:
                bpy.data.meshes.remove(block)
                count += 1
        for mat in bpy.data.materials:
            if mat.users == 0:
                bpy.data.materials.remove(mat)
                count += 1
        # Add more types as needed
        return count

    @staticmethod
    def audit_scene() -> Dict[str, Any]:
        """
        Comprehensive Scene Audit.
        """
        if not bpy.context.scene:
            return {"error": "No active scene"}
        s = bpy.context.scene

        return {
            "name": s.name,
            "objects": len(s.objects),
            "render_engine": s.render.engine,
            "resolution": f"{s.render.resolution_x}x{s.render.resolution_y}",
            "unit_system": s.unit_settings.system,
            "has_sequencer": bool(s.sequence_editor),
            "has_compositor": s.use_nodes,
            "orphans": SystemDoctor.check_orphan_data(),
        }
