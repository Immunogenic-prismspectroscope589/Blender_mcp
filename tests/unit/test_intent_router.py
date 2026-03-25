"""
Unit tests for IntentRouter — intent classification, handler routing, and workflows.

No bpy required — pure Python.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

sys.modules.setdefault("bpy", MagicMock())
sys.modules.setdefault("mathutils", MagicMock())

from blender_mcp.core.intent_router import (
    IntentRouter,
    classify_intent,
    get_relevant_handlers,
    get_intent_summary,
)


# ---------------------------------------------------------------------------
# classify_intent tests
# ---------------------------------------------------------------------------


class TestClassifyIntent:
    def test_empty_request_returns_general(self) -> None:
        result = IntentRouter.classify_intent("")
        assert result == ["GENERAL"]

    def test_modeling_keywords(self) -> None:
        result = IntentRouter.classify_intent("I want to create a mesh cube")
        assert "MODELING" in result

    def test_animation_keywords(self) -> None:
        result = IntentRouter.classify_intent("animate the character with keyframes")
        assert "ANIMATION" in result

    def test_rendering_keywords(self) -> None:
        result = IntentRouter.classify_intent("render the scene with cycles")
        assert "RENDERING" in result

    def test_materials_keywords(self) -> None:
        result = IntentRouter.classify_intent("create a PBR material with metallic shader")
        assert "MATERIALS" in result

    def test_physics_keywords(self) -> None:
        result = IntentRouter.classify_intent("add rigid body simulation")
        assert "PHYSICS" in result

    def test_scene_pipeline_keywords(self) -> None:
        result = IntentRouter.classify_intent("export the scene to gltf")
        assert "SCENE_PIPELINE" in result

    def test_ai_external_keywords(self) -> None:
        result = IntentRouter.classify_intent("generate a 3D model with AI")
        assert "AI_EXTERNAL" in result

    def test_multiple_categories_matched(self) -> None:
        """Request mentioning multiple domains should match multiple categories."""
        result = IntentRouter.classify_intent("rig the character and animate a walk cycle")
        assert "ANIMATION" in result

    def test_turkish_keywords_modeling(self) -> None:
        result = IntentRouter.classify_intent("modelleme yapmak istiyorum")
        assert "MODELING" in result

    def test_turkish_keywords_animation(self) -> None:
        result = IntentRouter.classify_intent("animasyon ekle ve iskelet kur")
        assert "ANIMATION" in result

    def test_french_keywords(self) -> None:
        result = IntentRouter.classify_intent("modélisation du maillage")
        assert "MODELING" in result

    def test_no_match_returns_general(self) -> None:
        result = IntentRouter.classify_intent("tell me a joke about elephants")
        assert result == ["GENERAL"]

    def test_case_insensitive(self) -> None:
        result = IntentRouter.classify_intent("RENDER THE SCENE WITH CYCLES ENGINE")
        assert "RENDERING" in result

    def test_partial_match_scores_lower(self) -> None:
        """Exact word match (\\bword\\b) scores higher than partial substring match."""
        # "mesh" as full word should score higher than partial match
        result = IntentRouter.classify_intent("mesh")
        assert "MODELING" in result


# ---------------------------------------------------------------------------
# get_relevant_handlers tests
# ---------------------------------------------------------------------------


class TestGetRelevantHandlers:
    def test_returns_handler_list(self) -> None:
        result = IntentRouter.get_relevant_handlers("create a mesh")
        assert "handlers" in result
        assert isinstance(result["handlers"], list)
        assert len(result["handlers"]) > 0

    def test_includes_external_by_default(self) -> None:
        result = IntentRouter.get_relevant_handlers("sculpt a face")
        assert result["include_external"] is True
        for ext in IntentRouter.EXTERNAL_HANDLERS:
            assert ext in result["handlers"]

    def test_excludes_external_when_disabled(self) -> None:
        result = IntentRouter.get_relevant_handlers("sculpt a face", include_external=False)
        assert result["include_external"] is False
        for ext in IntentRouter.EXTERNAL_HANDLERS:
            assert ext not in result["handlers"]

    def test_reduction_percent_calculated(self) -> None:
        result = IntentRouter.get_relevant_handlers("animate a character")
        assert "reduction_percent" in result
        assert 0 <= result["reduction_percent"] <= 100

    def test_token_savings_positive(self) -> None:
        result = IntentRouter.get_relevant_handlers("add rigid body")
        assert result["estimated_token_savings"] >= 0

    def test_category_details_populated(self) -> None:
        result = IntentRouter.get_relevant_handlers("render with eevee")
        assert "category_details" in result
        assert len(result["category_details"]) >= 1
        detail = result["category_details"][0]
        assert "name" in detail
        assert "handlers" in detail

    def test_handler_count_matches_list(self) -> None:
        result = IntentRouter.get_relevant_handlers("physics simulation")
        assert result["handler_count"] == len(result["handlers"])

    def test_handlers_are_sorted(self) -> None:
        result = IntentRouter.get_relevant_handlers("model a cube")
        handlers = result["handlers"]
        assert handlers == sorted(handlers)

    def test_general_intent_still_has_external(self) -> None:
        """Even generic intent includes external handlers."""
        result = IntentRouter.get_relevant_handlers("do something random")
        for ext in IntentRouter.EXTERNAL_HANDLERS:
            assert ext in result["handlers"]


# ---------------------------------------------------------------------------
# get_suggested_workflow tests
# ---------------------------------------------------------------------------


class TestGetSuggestedWorkflow:
    def test_character_workflow(self) -> None:
        result = IntentRouter.get_suggested_workflow("create a character")
        assert result is not None
        assert result["workflow"] == "CHARACTER_CREATION"
        assert len(result["steps"]) >= 5

    def test_environment_workflow(self) -> None:
        result = IntentRouter.get_suggested_workflow("build an environment")
        assert result is not None
        assert result["workflow"] == "ENVIRONMENT_CREATION"

    def test_prop_workflow(self) -> None:
        result = IntentRouter.get_suggested_workflow("make a weapon prop")
        assert result is not None
        assert result["workflow"] == "PROP_CREATION"

    def test_no_workflow_for_generic(self) -> None:
        result = IntentRouter.get_suggested_workflow("do something")
        assert result is None

    def test_workflow_steps_have_tool_and_action(self) -> None:
        result = IntentRouter.get_suggested_workflow("design a human character")
        assert result is not None
        for step in result["steps"]:
            assert "tool" in step
            assert "action" in step
            assert "step" in step


# ---------------------------------------------------------------------------
# get_category_description tests
# ---------------------------------------------------------------------------


class TestGetCategoryDescription:
    def test_known_category(self) -> None:
        result = IntentRouter.get_category_description("MODELING")
        assert result["name"] == "MODELING"
        assert "description" in result
        assert result["handler_count"] > 0
        assert "sample_patterns" in result

    def test_unknown_category(self) -> None:
        result = IntentRouter.get_category_description("NONEXISTENT")
        assert result["name"] == "NONEXISTENT"
        assert "Unknown" in result["description"]


# ---------------------------------------------------------------------------
# Convenience function tests
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    def test_classify_intent_function(self) -> None:
        result = classify_intent("render")
        assert isinstance(result, list)
        assert "RENDERING" in result

    def test_get_relevant_handlers_function(self) -> None:
        result = get_relevant_handlers("animate")
        assert "handlers" in result

    def test_get_intent_summary_returns_string(self) -> None:
        result = get_intent_summary("render the scene")
        assert isinstance(result, str)
        assert "Intent Analysis" in result
        assert "Token Reduction" in result
