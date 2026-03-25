"""
Intent-Based Tool Router for Blender MCP 1.0.0

Reduces 64 handlers to relevant subset based on user intent.
Solves context window overflow: 64 tools × 800 tokens = 51k tokens!

With Intent Router: 10-15 tools × 800 tokens = 12k tokens (77% reduction)
"""

import re
from typing import List, Dict, Optional
from ..core.logging_config import get_logger

logger = get_logger()


class IntentRouter:
    """
    Route user requests to appropriate handler categories.

    Reduces tool discovery from 64 handlers to 10-15 relevant ones,
    saving ~39k tokens per request.
    """

    # Handler categories with their patterns and handlers
    CATEGORIES: Dict[str, Dict] = {
        "MODELING": {
            "patterns": [
                # English
                "model",
                "mesh",
                "vertex",
                "edge",
                "face",
                "polygon",
                "geometry",
                "sculpt",
                "sculpting",
                "dyntopo",
                "remesh",
                "uv",
                "unwrap",
                "texture coordinate",
                "bevel",
                "extrude",
                "inset",
                "loop cut",
                "knife",
                "boolean",
                "union",
                "difference",
                "intersect",
                "subdivide",
                "subdivision",
                "smooth",
                "subsurf",
                "mirror",
                "array",
                "solidify",
                "wireframe",
                # Turkish
                "modelleme",
                "mesh",
                "poligon",
                "geometri",
                "oyma",
                "skulpt",
                "dokulu",
                "kaplama",
                # French
                "modélisation",
                "maillage",
                "polygone",
                "sculpture",
                "dépliage uv",
            ],
            "handlers": [
                "manage_modeling",
                "manage_sculpting",
                "manage_uv",
                "manage_uvs",
                "manage_uv_advanced",
                "manage_bmesh_edit",
                "manage_geometry_nodes",
                "manage_geometry_nodes_advanced",
                "manage_procedural",
            ],
            "description": "Mesh creation, editing, and geometry operations",
            "priority": "high",
        },
        "ANIMATION": {
            "patterns": [
                # English
                "animate",
                "animation",
                "keyframe",
                "timeline",
                "rig",
                "rigging",
                "bone",
                "armature",
                "skin",
                "weight paint",
                "constraint",
                "ik",
                "fk",
                "inverse kinematics",
                "driver",
                "driver",
                "mocap",
                "motion capture",
                "retarget",
                "walk cycle",
                "run cycle",
                "pose",
                "pose library",
                "action",
                "nla",
                "non-linear",
                # Turkish
                "animasyon",
                "anahtar kare",
                "iskelet",
                "kemik",
                "kısıtlama",
                "hareket yakalama",
                # French
                "animation",
                "os",
                "squelette",
                "contrainte",
            ],
            "handlers": [
                "manage_animation",
                "manage_animation_advanced",
                "manage_animation_slots",
                "manage_rigging",
                "manage_constraints",
                "manage_drivers",
                "manage_mocap",
            ],
            "description": "Animation, rigging, and motion workflows",
            "priority": "high",
        },
        "RENDERING": {
            "patterns": [
                # English
                "render",
                "rendering",
                "cycles",
                "eevee",
                "viewport",
                "camera",
                "cameras",
                "lens",
                "dof",
                "depth of field",
                "focus",
                "light",
                "lighting",
                "lamp",
                "sun",
                "area",
                "spot",
                "point",
                "three point",
                "studio lighting",
                "hdri",
                "bake",
                "baking",
                "texture bake",
                "normal bake",
                "ao bake",
                "composit",
                "compositing",
                "node",
                "nodes",
                "sequencer",
                "video",
                "edit",
                "vse",
                "view layer",
                "cryptomatte",
                "pass",
                "render pass",
                # Turkish
                "render",
                "kamera",
                "ışık",
                "ışıklandırma",
                "pişirme",
                "kompozisyon",
                # French
                "rendu",
                "caméra",
                "lumière",
                "composition",
            ],
            "handlers": [
                "manage_rendering",
                "manage_render_optimization",
                "manage_camera",
                "manage_light",
                "manage_bake",
                "manage_compositing",
                "manage_compositor_modifier",
                "manage_eevee_next",
                "manage_sequencer",
            ],
            "description": "Rendering, lighting, and output",
            "priority": "high",
        },
        "MATERIALS": {
            "patterns": [
                # English
                "material",
                "shader",
                "texture",
                "image texture",
                "procedural texture",
                "pbr",
                "metallic",
                "roughness",
                "normal map",
                "bump",
                "node editor",
                "shader editor",
                "principled",
                "uv mapping",
                "texel",
                "texture paint",
                "subsurface",
                "sss",
                "transmission",
                "glass",
                "metal",
                # Turkish
                "materyal",
                "dokulu",
                "kaplama",
                "gölgelendirici",
                # French
                "matériau",
                "texture",
                "ombrage",
            ],
            "handlers": ["manage_materials", "manage_bake", "manage_compositing"],
            "description": "Materials, textures, and shading",
            "priority": "medium",
        },
        "PHYSICS": {
            "patterns": [
                # English
                "physics",
                "simulation",
                "sim",
                "cloth",
                "fluid",
                "smoke",
                "fire",
                "rigid body",
                "soft body",
                "collision",
                "particle",
                "particles",
                "force field",
                "wind",
                "vortex",
                "turbulence",
                "bake physics",
                "cache",
                "explosion",
                "destruction",
                "fracture",
                # Turkish
                "fizik",
                "simülasyon",
                "kumaş",
                "akışkan",
                "parçacık",
                # French
                "physique",
                "simulation",
                "tissu",
                "fluide",
            ],
            "handlers": ["manage_physics", "manage_simulation_presets"],
            "description": "Physics simulations and effects",
            "priority": "medium",
        },
        "SCENE_PIPELINE": {
            "patterns": [
                # English
                "scene",
                "collection",
                "view layer",
                "outliner",
                "export",
                "import",
                "fbx",
                "obj",
                "gltf",
                "glb",
                "usd",
                "alembic",
                "batch",
                "batch process",
                "rename",
                "organization",
                "script",
                "python",
                "code",
                "automation",
                "profile",
                "performance",
                "optimize",
                "memory",
                "statistics",
                "backup",
                "save",
                "load",
                "append",
                "link",
                "unity",
                "unreal",
                "game engine",
                "pipeline",
                "headless",
                "batch mode",
                "ci/cd",
                # Turkish
                "sahne",
                "koleksiyon",
                "dışa aktar",
                "içe aktar",
                "toplu",
                "script",
                "performans",
                # French
                "scène",
                "collection",
                "export",
                "import",
            ],
            "handlers": [
                "manage_scene",
                "manage_objects",
                "manage_scripting",
                "manage_export",
                "manage_export_pipeline",
                "manage_batch",
                "manage_advanced_batch",
                "manage_collections_advanced",
                "manage_inspection",
                "manage_profiling",
                "manage_headless_mode",
            ],
            "description": "Scene management, export, and pipeline",
            "priority": "medium",
        },
        "AI_EXTERNAL": {
            "patterns": [
                # English
                "ai",
                "artificial intelligence",
                "generate",
                "generation",
                "hunyuan",
                "hyper3d",
                "tripo",
                "meshy",
                "rodin",
                "polyhaven",
                "hdri",
                "texture download",
                "sketchfab",
                "download model",
                "import model",
                "auto",
                "automatic",
                "smart",
                "intelligent",
                "procedural",
                "procedural generation",
                "lod",
                "level of detail",
                "auto lod",
                # Turkish
                "yapay zeka",
                "üret",
                "otomatik",
                "akıllı",
                # French
                "ia",
                "intelligence artificielle",
                "générer",
            ],
            "handlers": [
                "manage_ai_tools",
                "manage_procedural",
                "integration_hunyuan",
                "integration_hyper3d",
                "integration_polyhaven",
                "integration_sketchfab",
            ],
            "description": "AI tools and external integrations",
            "priority": "high",
            "always_include": True,  # Always include these
        },
    }

    # External integration handlers (always at final 4 positions)
    EXTERNAL_HANDLERS = [
        "integration_hunyuan",
        "integration_hyper3d",
        "integration_polyhaven",
        "integration_sketchfab",
    ]

    @classmethod
    def classify_intent(cls, user_request: str) -> List[str]:
        """
        Classify user request into one or more categories.

        Args:
            user_request: Natural language request from user

        Returns:
            List of matched category names
        """
        if not user_request:
            return ["GENERAL"]

        request_lower = user_request.lower()
        matched_categories = []
        match_scores = {}

        for category, config in cls.CATEGORIES.items():
            score = 0
            matched_patterns = []

            for pattern in config["patterns"]:
                # Exact word match (higher score)
                if re.search(r"\b" + re.escape(pattern.lower()) + r"\b", request_lower):
                    score += 2
                    matched_patterns.append(pattern)
                # Partial match (lower score)
                elif pattern.lower() in request_lower:
                    score += 1
                    matched_patterns.append(pattern)

            if score > 0:
                matched_categories.append(category)
                match_scores[category] = {
                    "score": score,
                    "patterns": matched_patterns,
                    "priority": config.get("priority", "medium"),
                }

        # Sort by score (descending) then priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        matched_categories.sort(
            key=lambda c: (
                -match_scores[c]["score"],
                priority_order.get(cls.CATEGORIES[c].get("priority", "medium"), 1),
            )
        )

        logger.debug(f"Intent classification: {request_lower[:50]}... → {matched_categories}")

        return matched_categories if matched_categories else ["GENERAL"]

    @classmethod
    def get_relevant_handlers(cls, user_request: str, include_external: bool = True) -> Dict:
        """
        Get handler list for user request with metadata.

        Args:
            user_request: Natural language request
            include_external: Always include external integrations

        Returns:
            Dict with handlers, categories, and metadata
        """
        categories = cls.classify_intent(user_request)
        handlers = set()
        category_info = []

        for category in categories:
            if category in cls.CATEGORIES:
                cat_handlers = cls.CATEGORIES[category]["handlers"]
                handlers.update(cat_handlers)
                category_info.append(
                    {
                        "name": category,
                        "description": cls.CATEGORIES[category]["description"],
                        "handlers": cat_handlers,
                        "priority": cls.CATEGORIES[category].get("priority", "medium"),
                    }
                )

        # Always include external integrations if requested
        if include_external:
            handlers.update(cls.EXTERNAL_HANDLERS)
            if "AI_EXTERNAL" not in categories:
                category_info.append(
                    {
                        "name": "AI_EXTERNAL",
                        "description": "AI tools and external integrations",
                        "handlers": cls.EXTERNAL_HANDLERS,
                        "priority": "high",
                        "always_included": True,
                    }
                )

        # Calculate token savings
        total_handlers = 64  # Current total
        selected_count = len(handlers)
        reduction_percent = ((total_handlers - selected_count) / total_handlers) * 100

        return {
            "categories": categories,
            "category_details": category_info,
            "handlers": sorted(list(handlers)),
            "handler_count": selected_count,
            "total_handlers": total_handlers,
            "reduction_percent": round(reduction_percent, 1),
            "estimated_token_savings": int((total_handlers - selected_count) * 800),
            "include_external": include_external,
        }

    @classmethod
    def get_suggested_workflow(cls, user_request: str) -> Optional[Dict]:
        """
        Suggest a workflow based on intent.

        Args:
            user_request: Natural language request

        Returns:
            Workflow suggestion or None
        """
        request_lower = user_request.lower()

        # Character workflow
        if any(word in request_lower for word in ["character", "human", "creature", "biped"]):
            return {
                "workflow": "CHARACTER_CREATION",
                "steps": [
                    {
                        "step": 1,
                        "tool": "manage_modeling",
                        "action": "ADD_PRIMITIVE",
                        "description": "Base mesh",
                    },
                    {
                        "step": 2,
                        "tool": "manage_sculpting",
                        "action": "ENTER_MODE",
                        "description": "Sculpt details",
                    },
                    {
                        "step": 3,
                        "tool": "manage_ai_tools",
                        "action": "AUTO_RETOPOLOGY",
                        "description": "Retopologize",
                    },
                    {
                        "step": 4,
                        "tool": "manage_uv",
                        "action": "UNWRAP",
                        "description": "UV mapping",
                    },
                    {
                        "step": 5,
                        "tool": "manage_materials",
                        "action": "CREATE",
                        "description": "Materials",
                    },
                    {
                        "step": 6,
                        "tool": "manage_rigging",
                        "action": "GENERATE_RIG",
                        "description": "Rigging",
                    },
                    {
                        "step": 7,
                        "tool": "manage_animation",
                        "action": "POSE_LIBRARY_CREATE",
                        "description": "Poses",
                    },
                ],
            }

        # Environment workflow
        if any(
            word in request_lower
            for word in ["environment", "scene", "world", "level", "architect"]
        ):
            return {
                "workflow": "ENVIRONMENT_CREATION",
                "steps": [
                    {
                        "step": 1,
                        "tool": "manage_scene",
                        "action": "NEW_SCENE",
                        "description": "Setup",
                    },
                    {
                        "step": 2,
                        "tool": "manage_procedural",
                        "action": "TERRAIN_GENERATE",
                        "description": "Terrain",
                    },
                    {
                        "step": 3,
                        "tool": "manage_modeling",
                        "action": "ADD_PRIMITIVE",
                        "description": "Props",
                    },
                    {
                        "step": 4,
                        "tool": "manage_light",
                        "action": "CREATE_SUN",
                        "description": "Lighting",
                    },
                    {
                        "step": 5,
                        "tool": "manage_camera",
                        "action": "CREATE",
                        "description": "Camera",
                    },
                    {
                        "step": 6,
                        "tool": "manage_render_optimization",
                        "action": "OPTIMIZE_SCENE",
                        "description": "Optimize",
                    },
                ],
            }

        # Prop/Asset workflow
        if any(
            word in request_lower for word in ["prop", "asset", "object", "item", "weapon", "tool"]
        ):
            return {
                "workflow": "PROP_CREATION",
                "steps": [
                    {
                        "step": 1,
                        "tool": "manage_modeling",
                        "action": "ADD_PRIMITIVE",
                        "description": "Blockout",
                    },
                    {
                        "step": 2,
                        "tool": "manage_modeling",
                        "action": "BEVEL",
                        "description": "Refine",
                    },
                    {
                        "step": 3,
                        "tool": "manage_uv",
                        "action": "SMART_PROJECT",
                        "description": "UVs",
                    },
                    {
                        "step": 4,
                        "tool": "manage_materials",
                        "action": "CREATE_PBR",
                        "description": "Material",
                    },
                    {
                        "step": 5,
                        "tool": "manage_bake",
                        "action": "BAKE_NORMAL",
                        "description": "Bake maps",
                    },
                    {
                        "step": 6,
                        "tool": "manage_export",
                        "action": "EXPORT_GLTF",
                        "description": "Export",
                    },
                ],
            }

        return None

    @classmethod
    def get_category_description(cls, category: str) -> Dict:
        """Get description for a category."""
        if category in cls.CATEGORIES:
            return {
                "name": category,
                "description": cls.CATEGORIES[category]["description"],
                "handler_count": len(cls.CATEGORIES[category]["handlers"]),
                "priority": cls.CATEGORIES[category].get("priority", "medium"),
                "sample_patterns": cls.CATEGORIES[category]["patterns"][:5],
            }
        return {"name": category, "description": "Unknown category"}


# Convenience functions for dispatcher integration
def classify_intent(user_request: str) -> List[str]:
    """Convenience function for intent classification."""
    return IntentRouter.classify_intent(user_request)


def get_relevant_handlers(user_request: str, include_external: bool = True) -> Dict:
    """Convenience function for getting relevant handlers."""
    return IntentRouter.get_relevant_handlers(user_request, include_external)


def get_intent_summary(user_request: str) -> str:
    """Get human-readable summary of intent analysis."""
    result = IntentRouter.get_relevant_handlers(user_request)

    lines = [
        f"Intent Analysis: '{user_request[:50]}...'",
        f"  Matched Categories: {', '.join(result['categories'])}",
        f"  Relevant Handlers: {result['handler_count']} of {result['total_handlers']}",
        f"  Token Reduction: {result['reduction_percent']}% (~{result['estimated_token_savings']} tokens saved)",
    ]

    return "\n".join(lines)
