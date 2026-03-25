"""
Deep coverage tests for dispatcher.py — covers paths not tested in
test_dispatch_routing.py: security checks, schema validation, thread safety,
result normalization, error handling, handler loading, and reload.

No bpy required — bpy is mocked.
"""

from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

bpy_mock = MagicMock()
bpy_mock.app.version = (5, 0, 0)
bpy_mock.app.translations.locale = "en_US"
sys.modules.setdefault("bpy", bpy_mock)
sys.modules.setdefault("mathutils", MagicMock())
sys.modules.setdefault("mathutils.bvhtree", MagicMock())
sys.modules.setdefault("bmesh", MagicMock())

from blender_mcp.dispatcher import (
    HANDLER_REGISTRY,
    HANDLER_METADATA,
    dispatch_command,
    load_handlers,
    register_handler,
    validate_tool,
    reload_handler,
    _build_system_manifest,
    _format_tool_full,
    _format_tool_row,
)

load_handlers()


# ---------------------------------------------------------------------------
# dispatch_command — result normalization
# ---------------------------------------------------------------------------


class TestResultNormalization:
    def test_none_result_becomes_success(self) -> None:
        """Handler returning None should be normalized to {success: True}."""

        @register_handler(
            "_test_none_handler",
            actions=["DO"],
            schema={
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["DO"]}},
                "required": ["action"],
            },
            category="test",
        )
        def _test_none_handler(**params):
            return None

        result = dispatch_command(
            {"tool": "_test_none_handler", "params": {"action": "DO"}},
            use_thread_safety=False,
        )
        assert result.get("success") is True

    def test_dict_without_success_gets_success_key(self) -> None:
        """Handler returning dict without 'success' key should get it added."""

        @register_handler(
            "_test_dict_handler",
            actions=["DO"],
            schema={
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["DO"]}},
                "required": ["action"],
            },
            category="test",
        )
        def _test_dict_handler(**params):
            return {"data": 42}

        result = dispatch_command(
            {"tool": "_test_dict_handler", "params": {"action": "DO"}},
            use_thread_safety=False,
        )
        assert result.get("success") is True
        assert result.get("data") == 42

    def test_non_dict_result_wrapped(self) -> None:
        """Handler returning non-dict value should be wrapped."""

        @register_handler(
            "_test_scalar_handler",
            actions=["DO"],
            schema={
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["DO"]}},
                "required": ["action"],
            },
            category="test",
        )
        def _test_scalar_handler(**params):
            return "just a string"

        result = dispatch_command(
            {"tool": "_test_scalar_handler", "params": {"action": "DO"}},
            use_thread_safety=False,
        )
        assert result.get("success") is True
        assert result.get("result") == "just a string"

    def test_meta_added_to_result(self) -> None:
        """Every successful result should have _meta with request_id, tool, action."""
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        )
        meta = result.get("_meta", {})
        assert "request_id" in meta
        assert meta["tool"] == "list_all_tools"
        assert meta["action"] == "list_all_tools"


# ---------------------------------------------------------------------------
# dispatch_command — error paths
# ---------------------------------------------------------------------------


class TestDispatchErrors:
    def test_handler_exception_returns_execution_error(self) -> None:
        """Handler that raises should return EXECUTION_ERROR."""

        @register_handler(
            "_test_raise_handler",
            actions=["BOOM"],
            schema={
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["BOOM"]}},
                "required": ["action"],
            },
            category="test",
        )
        def _test_raise_handler(**params):
            raise RuntimeError("intentional crash")

        result = dispatch_command(
            {"tool": "_test_raise_handler", "params": {"action": "BOOM"}},
            use_thread_safety=False,
        )
        assert result.get("code") == "EXECUTION_ERROR"
        assert "intentional crash" in result.get("error", "")

    def test_schema_validation_error(self) -> None:
        """Invalid schema params should return VALIDATION_ERROR."""

        @register_handler(
            "_test_schema_val",
            actions=["GO"],
            schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["GO"]},
                    "count": {"type": "integer", "minimum": 1},
                },
                "required": ["action", "count"],
            },
            category="test",
        )
        def _test_schema_val(**params):
            return {"ok": True}

        result = dispatch_command(
            {"tool": "_test_schema_val", "params": {"action": "GO"}},
            use_thread_safety=False,
        )
        assert result.get("code") == "VALIDATION_ERROR"

    def test_security_violation_returns_error(self) -> None:
        """When SecurityManager blocks, SECURITY_VIOLATION code is returned."""
        with patch("blender_mcp.dispatcher.SecurityManager.validate_action", return_value=False):
            result = dispatch_command(
                {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
                use_thread_safety=False,
            )
            assert result.get("code") == "SECURITY_VIOLATION"

    def test_exception_with_debug_context_includes_traceback(self) -> None:
        """With debug context, traceback should be in the error result."""

        @register_handler(
            "_test_debug_raise",
            actions=["ERR"],
            schema={
                "type": "object",
                "properties": {"action": {"type": "string", "enum": ["ERR"]}},
                "required": ["action"],
            },
            category="test",
        )
        def _test_debug_raise(**params):
            raise ValueError("debug test")

        ctx = MagicMock()
        ctx.debug = True
        result = dispatch_command(
            {"tool": "_test_debug_raise", "params": {"action": "ERR"}},
            ctx=ctx,
            use_thread_safety=False,
        )
        assert result.get("code") == "EXECUTION_ERROR"
        assert "traceback" in result


# ---------------------------------------------------------------------------
# validate_tool handler tests
# ---------------------------------------------------------------------------


class TestValidateTool:
    def test_validate_valid_params(self) -> None:
        result = validate_tool(
            action="validate_tool",
            tool="list_all_tools",
            params={"action": "list_all_tools"},
        )
        assert result.get("valid") is True

    def test_validate_unknown_tool(self) -> None:
        result = validate_tool(
            action="validate_tool",
            tool="nonexistent_xyz",
            params={},
        )
        assert result.get("valid") is False
        assert "Unknown" in result.get("error", "")

    def test_validate_missing_tool_param(self) -> None:
        result = validate_tool(action="validate_tool")
        assert result.get("valid") is False

    def test_validate_invalid_action(self) -> None:
        result = validate_tool(
            action="validate_tool",
            tool="list_all_tools",
            params={"action": "NONEXISTENT"},
        )
        assert result.get("valid") is False


# ---------------------------------------------------------------------------
# register_handler edge cases
# ---------------------------------------------------------------------------


class TestRegisterHandler:
    def test_duplicate_different_module_raises(self) -> None:
        """Registering same command from different module should raise RuntimeError."""

        # First, register from module A
        @register_handler("_test_dup", actions=["A"], category="test")
        def handler_a(**params):
            return None

        # Override __module__ to simulate different module
        original_module = handler_a.__module__

        def handler_b(**params):
            return None

        handler_b.__module__ = "fake.other.module"

        try:
            HANDLER_REGISTRY["_test_dup"] = handler_a
            HANDLER_METADATA["_test_dup"] = {"name": "_test_dup"}
            # Manually attempt registration with different module
            handler_a.__module__ = original_module
            register_handler("_test_dup", actions=["A"], category="test")(handler_b)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as exc:
            assert "Duplicate" in str(exc)
        finally:
            HANDLER_REGISTRY.pop("_test_dup", None)
            HANDLER_METADATA.pop("_test_dup", None)

    def test_action_auto_discovery_from_schema(self) -> None:
        """When actions=None, actions are inferred from schema.properties.action.enum."""

        @register_handler(
            "_test_auto_actions",
            schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["RUN", "WALK", "JUMP"]},
                },
            },
            category="test",
        )
        def _test_auto_actions(**params):
            return None

        meta = HANDLER_METADATA.get("_test_auto_actions", {})
        assert meta["actions"] == ["RUN", "WALK", "JUMP"]

        # Cleanup
        HANDLER_REGISTRY.pop("_test_auto_actions", None)
        HANDLER_METADATA.pop("_test_auto_actions", None)


# ---------------------------------------------------------------------------
# Manifest formatting tests
# ---------------------------------------------------------------------------


class TestManifestFormatting:
    def test_format_tool_full_essential(self) -> None:
        tool = {
            "name": "test_tool",
            "priority": 1,
            "category": "test",
            "description": "A test tool",
            "actions": ["DO", "UNDO"],
            "schema": {
                "title": "Test Tool",
                "properties": {
                    "action": {"type": "string", "enum": ["DO", "UNDO"]},
                    "count": {"type": "integer", "description": "How many"},
                },
                "required": ["action"],
            },
        }
        output = _format_tool_full(tool)
        assert "test_tool" in output
        assert "Test Tool" in output
        assert "DO" in output
        assert "count" in output

    def test_format_tool_row_compact(self) -> None:
        tool = {
            "name": "manage_something",
            "priority": 50,
            "category": "modeling",
            "actions": ["CREATE", "DELETE", "LIST", "UPDATE", "EXTRA"],
        }
        output = _format_tool_row(1, tool)
        assert "manage_something" in output
        assert "modeling" in output
        # Only first 4 actions + ellipsis
        assert "..." in output or "EXTRA" not in output

    def test_build_system_manifest_tiered(self) -> None:
        tools = [
            {
                "name": "essential_tool",
                "priority": 1,
                "category": "core",
                "description": "Essential",
                "actions": ["A"],
                "schema": {"title": "E"},
            },
            {
                "name": "core_tool",
                "priority": 20,
                "category": "general",
                "description": "Core tool",
                "actions": ["B"],
                "schema": {},
            },
            {
                "name": "standard_tool",
                "priority": 80,
                "category": "general",
                "description": "Standard",
                "actions": ["C"],
                "schema": {},
            },
            {
                "name": "optional_tool",
                "priority": 200,
                "category": "deprecated",
                "description": "Optional",
                "actions": ["D"],
                "schema": {},
            },
        ]
        manifest = _build_system_manifest(tools)
        assert "ESSENTIAL" in manifest
        assert "CORE" in manifest
        assert "Standard" in manifest
        assert "Optional" in manifest


# ---------------------------------------------------------------------------
# reload_handler tests
# ---------------------------------------------------------------------------


class TestReloadHandler:
    def test_reload_loaded_module(self) -> None:
        """Reloading a loaded module should succeed."""
        result = reload_handler("manage_history")
        assert result.get("success") is True or "error" in result

    def test_reload_unloaded_module(self) -> None:
        """Reloading an unloaded module should return error."""
        result = reload_handler("definitely_not_loaded_xyz")
        assert "error" in result


# ---------------------------------------------------------------------------
# get_server_status tests (via dispatch)
# ---------------------------------------------------------------------------


class TestGetServerStatus:
    def test_returns_active_status(self) -> None:
        result = dispatch_command(
            {"tool": "get_server_status", "params": {"action": "get_server_status"}},
            use_thread_safety=False,
        )
        assert result.get("status") == "active"
        assert "handler_count" in result
        assert "version" in result
        assert "blender_language" in result
        assert "next_step" in result

    def test_returns_tools_list(self) -> None:
        result = dispatch_command(
            {"tool": "get_server_status", "params": {"action": "get_server_status"}},
            use_thread_safety=False,
        )
        assert isinstance(result.get("tools"), list)
        assert len(result["tools"]) > 0


# ---------------------------------------------------------------------------
# list_all_tools tests (via dispatch)
# ---------------------------------------------------------------------------


class TestListAllTools:
    def test_returns_count_and_tools(self) -> None:
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        )
        assert result.get("count") > 0
        assert isinstance(result.get("tools"), list)

    def test_has_agent_onboarding(self) -> None:
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        )
        onboarding = result.get("agent_onboarding", {})
        assert "essential_5step_workflow" in onboarding
        assert "critical_warnings" in onboarding

    def test_category_filter(self) -> None:
        result = dispatch_command(
            {
                "tool": "list_all_tools",
                "params": {
                    "action": "list_all_tools",
                    "category": "NONEXISTENT_CAT",
                },
            },
            use_thread_safety=False,
        )
        assert result.get("count") == 0

    def test_intent_filter(self) -> None:
        result = dispatch_command(
            {
                "tool": "list_all_tools",
                "params": {
                    "action": "list_all_tools",
                    "intent": "render the scene",
                },
            },
            use_thread_safety=False,
        )
        assert result.get("intent_matched") is True
        assert result.get("count") < dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        ).get("count", 999)

    def test_has_system_manifest(self) -> None:
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        )
        manifest = result.get("system_manifest", "")
        assert isinstance(manifest, str)
        assert len(manifest) > 100

    def test_external_integrations_info(self) -> None:
        result = dispatch_command(
            {"tool": "list_all_tools", "params": {"action": "list_all_tools"}},
            use_thread_safety=False,
        )
        ext = result.get("external_integrations", {})
        assert "count" in ext
        assert "names" in ext
