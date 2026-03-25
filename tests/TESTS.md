# Blender MCP — Test Suite Reference

> live-37 | Last Updated: 2026-03-09

## Overview

| Layer | Directory | Purpose | Tests |
|-------|-----------|---------|-------|
| **Unit** | `tests/unit/` | Pure-Python tests — no Blender required, run in CI | **499** |
| **Integration** | `tests/integration/` | End-to-end tests using mock MCP bridge responses | 24 |
| **Grand total** | | | **523** |

All tests are discovered and run by **pytest**. Unit tests mock `bpy` and run in ~1.4 seconds.

---

## Quick Start

```bash
# Run full test suite
uv run pytest tests -v --tb=short

# Run only unit tests (fastest — no Blender required)
uv run pytest tests/unit -v --tb=short

# Run with coverage report
uv run pytest tests -v --cov=blender_mcp --cov-report=term

# Makefile shortcuts
make test         # Full suite
make test-fast    # Unit tests only, stop on first failure
make test-cov     # Full suite with HTML + XML coverage
```

---

## Unit Test Files (`tests/unit/`)

### `test_essential_tools.py` (183 tests)
Comprehensive tests for all 8 ESSENTIAL tier tools (priority ≤ 9). All tests run through `dispatch_command` (real execution path) with mocked bpy.

Covers: `execute_blender_code`, `get_scene_graph` (11 actions: GET_OBJECTS_FLAT, GET_SCENE_MATRIX, ANALYZE_ASSEMBLY, CAST_RAY, VERIFY_ASSEMBLY, GET_SPATIAL_REPORT, DETECT_GEOMETRY_ERRORS, GEOMETRY_COMPLEXITY, CHECK_PRODUCTION_READINESS, GET_HIERARCHY_TREE), `get_viewport_screenshot_base64`, `get_object_info`, `manage_agent_context` (GET_PRIMER, GET_TACTICS, GET_TOOL_CATALOG, GET_ACTION_HELP), `list_all_tools`, `get_server_status`, `new_scene`.

```bash
uv run pytest tests/unit/test_essential_tools.py -v
```

---

### `test_parameter_validator.py` (60 tests) — NEW in live-37
Tests `ParameterValidator` — type coercion, schema validation, enum checks, bounds clamping, and decorators.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestValidationResult` | 5 | Subscript access, `.get()`, `__contains__`, `.to_dict()` |
| `TestCoerceInt` | 10 | int/float/string/bool/None → int, bounds clamping (min/max) |
| `TestCoerceFloat` | 6 | int/string/None → float, bounds clamping |
| `TestCoerceBool` | 5 | bool/string/int/None → bool, "true"/"yes"/"1"/"on"/"enabled" |
| `TestCoerceType` | 5 | string/array/object/unknown type coercion, None defaults |
| `TestSchemaValidation` | 11 | Valid params, missing required, invalid enum, bounds clamp, defaults, type coercion, unknown param warning, non-dict input |
| `TestValidateAction` | 4 | Valid/missing/invalid/non-string action |
| `TestIntegrationValidator` | 3 | Integration handler params validation |
| `TestLegacyValidateParamsSchema` | 2 | `validate_params_schema()` backward compatibility |
| `TestValidatedHandlerDecorator` | 4 | `@validated_handler` — pass valid, block invalid, schema enforcement |
| `TestCoerceParamsDecorator` | 3 | `@coerce_params` — coercion applied, failure keeps original, None skipped |

```bash
uv run pytest tests/unit/test_parameter_validator.py -v
```

---

### `test_intent_router.py` (35 tests) — NEW in live-37
Tests `IntentRouter` — multi-language intent classification, handler routing, workflow suggestions.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestClassifyIntent` | 15 | Empty → GENERAL, EN/TR/FR keywords for all 7 categories, multi-category, case insensitive, partial match scoring |
| `TestGetRelevantHandlers` | 9 | Handler list structure, external inclusion/exclusion, reduction %, token savings, category details, sorted output |
| `TestGetSuggestedWorkflow` | 5 | CHARACTER_CREATION, ENVIRONMENT_CREATION, PROP_CREATION workflows, None for generic, step structure |
| `TestGetCategoryDescription` | 2 | Known/unknown category lookup |
| `TestConvenienceFunctions` | 3 | `classify_intent()`, `get_relevant_handlers()`, `get_intent_summary()` |

```bash
uv run pytest tests/unit/test_intent_router.py -v
```

---

### `test_execution_engine.py` (31 tests) — NEW in live-37
Tests `ExecutionEngine` — policy enforcement, operator safety, batch execution, decorators, and SafeOps proxy.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestExecutionResult` | 5 | `.to_dict()` success/error paths, default code, no-alternatives, `.to_error_dict()` alias |
| `TestExecutionPolicy` | 5 | Default mode/diff, `set_mode()`, `set_diff_level()`, singleton pattern |
| `TestOperatorSafety` | 4 | Modal/UI/destructive operators blocked, `allow_dangerous` bypass |
| `TestOperatorSafetyCheck` | 4 | `is_safe()` — safe operator, modal, UI-dependent, scene-destructive |
| `TestReadOnlyPolicy` | 2 | MUTATION_OPERATORS blocked in READ_ONLY, non-mutation allowed |
| `TestGetOperator` | 2 | Invalid path formats |
| `TestExecuteBatch` | 2 | `stop_on_error=True/False` behavior |
| `TestSafeExecuteDecorator` | 3 | Exception catching, success passthrough, custom fallback |
| `TestSafeOps` | 2 | Proxy returns ExecutionResult, singleton |

```bash
uv run pytest tests/unit/test_execution_engine.py -v
```

---

### `test_dispatcher_deep.py` (28 tests) — NEW in live-37
Deep coverage for `dispatcher.py` — paths not covered by `test_dispatch_routing.py`.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestResultNormalization` | 4 | None → `{success: True}`, dict auto-`success`, non-dict wrapped, `_meta` injection |
| `TestDispatchErrors` | 4 | Handler exception → EXECUTION_ERROR, schema validation → VALIDATION_ERROR, security violation, debug traceback |
| `TestValidateTool` | 4 | Valid params, unknown tool, missing tool param, invalid action |
| `TestRegisterHandler` | 2 | Duplicate from different module → RuntimeError, action auto-discovery from schema enum |
| `TestManifestFormatting` | 3 | `_format_tool_full()` ESSENTIAL format, `_format_tool_row()` compact, `_build_system_manifest()` tiered output |
| `TestReloadHandler` | 2 | Reload loaded/unloaded module |
| `TestGetServerStatus` | 2 | Active status, tools list in response |
| `TestListAllTools` | 6 | Count/tools, agent onboarding, category filter, intent filter, system manifest, external integrations |

```bash
uv run pytest tests/unit/test_dispatcher_deep.py -v
```

---

### `test_job_manager.py` (25 tests) — NEW in live-37
Tests `AsyncJobManager` — job lifecycle, status polling, progress tracking, cancellation, and eviction.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestJobEnums` | 2 | `JobStatus` / `JobType` enum values |
| `TestInternalJobLifecycle` | 4 | Submit creates entry, mark success/failed, ignores non-internal |
| `TestCheckJobStatus` | 4 | Unknown ID, returns data, subprocess poll completed/failed |
| `TestUpdateJobProgress` | 3 | Update progress, clamped to 0-100, completed job ignored |
| `TestCancelJob` | 4 | Cancel queued/running internal, nonexistent, subprocess |
| `TestListJobs` | 4 | Empty, all jobs, status filter, safe copies |
| `TestEvictOldJobs` | 3 | No eviction under limit, removes oldest finished, preserves running |

```bash
uv run pytest tests/unit/test_job_manager.py -v
```

---

### `test_semantic_memory.py` (25 tests) — NEW in live-37
Tests `SemanticSceneMemory` — tag-based object resolution, manual tagging, access tracking, and singleton.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestSemanticTag` | 2 | Default values, custom values |
| `TestObjectMemory` | 4 | add_tag, replace existing, has_tag false, get_confidence missing |
| `TestSemanticSceneMemory` | 11 | Manual tag/untag, get_tags empty, tag_info known/user, list_all_tags, update_access, last_created/modified, index dedup |
| `TestResolve` | 4 | Empty tag, direct name lookup (dict-backed mock), tag index resolve, last_created resolve, resolve_multiple empty |
| `TestGetSemanticMemory` | 1 | Singleton pattern |

```bash
uv run pytest tests/unit/test_semantic_memory.py -v
```

---

### `test_dispatch_routing.py` (23 tests)
Tests dispatcher routing, action validation, system manifest generation, and essential-tier registration.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestHandlerRegistration` | 7 | Essential tools registered with correct priorities |
| `TestDispatchRouting` | 4 | Unknown tool, missing tool key, invalid action, list_all_tools manifest |
| `TestManifestFormat` | 2 | ESSENTIAL header, get_server_status in manifest |
| `TestSceneComprehensionActions` | 9 | get_scene_graph registered, old name absent, all actions listed, ≥10 actions, ESSENTIAL priority, get_local_transforms |

```bash
uv run pytest tests/unit/test_dispatch_routing.py -v
```

---

### `test_response_builder.py` (21 tests)
Tests `ResponseBuilder` and `ResponseTimer` — no bpy required.

| Test | What It Checks |
|------|---------------|
| `test_success_*` (8) | OK status, required keys, metadata fields, data passthrough, summary variants, empty errors |
| `test_error_*` (6) | ERROR status, errors list structure, auto-suggestion, next_steps, from_error dict/exception |
| `test_partial_*` (1) | PARTIAL status with completed/failed steps |
| `test_warning_*` (1) | WARNING status with warnings list |
| `test_add_*` (2) | Mutation helpers: add_affected_object, add_warning |
| `test_response_timer_*` (2) | Duration measurement, get_duration returns float |

```bash
uv run pytest tests/unit/test_response_builder.py -v
```

---

### `test_protocol.py` (17 tests) — NEW in live-37
Tests wire protocol (4-byte Big-Endian length-prefix + JSON over TCP).

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestRecvN` | 5 | Exact bytes, multi-chunk, connection close, zero bytes, partial then close |
| `TestSendMessage` | 5 | Simple dict, empty dict, Unicode, socket error propagation, large payload (>100KB) |
| `TestRecvMessage` | 5 | Simple parse, closed connection (header/body), timeout propagation, invalid JSON |
| `TestRoundTrip` | 1 | send → recv produces identical dict |

```bash
uv run pytest tests/unit/test_protocol.py -v
```

---

### `test_registry_completeness.py` (15 tests)
Loads all handlers via `load_handlers()` and verifies registry integrity.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestRegistryCount` | 1 | `≥ 60` handlers registered |
| `TestEssentialTier` | 4 | Priority 1/2, all essential present, ≥ 8 essential count |
| `TestMetadataQuality` | 4 | Every handler has description, category, actions (non-empty) |
| `TestSpecificHandlers` | 5 | manage_history, get_local_transforms, get_scene_graph, manage_agent_context, new_scene |

```bash
uv run pytest tests/unit/test_registry_completeness.py -v
```

---

### `test_error_protocol.py` (13 tests)
Tests `ErrorCode` enum and `create_error()` factory.

```bash
uv run pytest tests/unit/test_error_protocol.py -v
```

---

### `test_smoke.py` (10 tests)
Minimal sanity checks: core entrypoints exist, handler count ≥ 50, ESSENTIAL tier declared, version consistency.

```bash
uv run pytest tests/unit/test_smoke.py -v
```

---

### `test_engine.py` (9 tests)
MCP bridge JSON-schema validation layer + `execute_blender_code` blocking patterns.

```bash
uv run pytest tests/unit/test_engine.py -v
```

---

### `test_manage_history.py` (9 tests)
Session-level checkpoint stack logic from `manage_history.py` without bpy.

```bash
uv run pytest tests/unit/test_manage_history.py -v
```

---

### `test_security.py` (6 tests) — NEW in live-37
Tests `SecurityManager` High Mode — all actions permitted.

```bash
uv run pytest tests/unit/test_security.py -v
```

---

### `test_scene_graph_geo_center.py` (6 tests)
Bounding-box geometry center computation and origin-offset warnings.

```bash
uv run pytest tests/unit/test_scene_graph_geo_center.py -v
```

---

## Integration Tests (`tests/integration/`)

| Mode | Requires | Files |
|------|----------|-------|
| **Mock** | No Blender | `test_incident_replay_p11_mock.py` (24 tests) — always runs in CI |
| **Live** | Blender on port 9879 | `test_incident_replay.py`, `test_incident_replay_p11.py` |

```bash
# Mock integration (CI-safe)
uv run pytest tests/integration/test_incident_replay_p11_mock.py -v

# Live integration (requires Blender)
uv run pytest tests/integration/test_incident_replay_p11.py -v
```

---

## Test Count Summary

| File | Tests | Module Covered |
|------|-------|----------------|
| `test_essential_tools.py` | 183 | 8 ESSENTIAL tier handlers |
| `test_parameter_validator.py` | 60 | `core/parameter_validator.py` |
| `test_intent_router.py` | 35 | `core/intent_router.py` |
| `test_execution_engine.py` | 31 | `core/execution_engine.py` |
| `test_dispatcher_deep.py` | 28 | `dispatcher.py` (deep paths) |
| `test_semantic_memory.py` | 25 | `core/semantic_memory.py` |
| `test_job_manager.py` | 25 | `core/job_manager.py` |
| `test_dispatch_routing.py` | 23 | `dispatcher.py` (routing) |
| `test_response_builder.py` | 21 | `core/response_builder.py` |
| `test_protocol.py` | 17 | `core/protocol.py` |
| `test_registry_completeness.py` | 15 | Handler registry integrity |
| `test_error_protocol.py` | 13 | `core/error_protocol.py` |
| `test_smoke.py` | 10 | Project structure sanity |
| `test_engine.py` | 9 | MCP bridge validation |
| `test_manage_history.py` | 9 | `handlers/manage_history.py` |
| `test_security.py` | 6 | `core/security.py` |
| `test_scene_graph_geo_center.py` | 6 | Geometry center computation |
| **Unit total** | **499** | |
| `test_incident_replay_p11_mock.py` | 24 | Mock integration |
| **Grand total** | **523** | |

---

## Core Module Coverage Map

| Core Module | Test File | Status |
|-------------|-----------|--------|
| `dispatcher.py` | `test_dispatch_routing.py` + `test_dispatcher_deep.py` | Covered |
| `core/protocol.py` | `test_protocol.py` | Covered |
| `core/parameter_validator.py` | `test_parameter_validator.py` | Covered |
| `core/execution_engine.py` | `test_execution_engine.py` | Covered |
| `core/intent_router.py` | `test_intent_router.py` | Covered |
| `core/job_manager.py` | `test_job_manager.py` | Covered |
| `core/security.py` | `test_security.py` | Covered |
| `core/semantic_memory.py` | `test_semantic_memory.py` | Covered |
| `core/response_builder.py` | `test_response_builder.py` | Covered |
| `core/error_protocol.py` | `test_error_protocol.py` | Covered |
| `handlers/manage_history.py` | `test_manage_history.py` | Covered |
| 8 ESSENTIAL handlers | `test_essential_tools.py` | Covered |

---

## All Commands Summary

| Command | Description |
|---------|-------------|
| `uv run pytest tests -v` | Full suite, verbose |
| `uv run pytest tests/unit -v` | Unit tests only |
| `uv run pytest tests/unit -v -x` | Unit tests, stop on first failure |
| `uv run pytest tests -v --cov=blender_mcp --cov-report=term` | With terminal coverage |
| `uv run pytest tests -v --cov=blender_mcp --cov-report=html` | With HTML coverage report |
| `make test` | Full suite via Makefile |
| `make test-fast` | Unit tests only, fail-fast via Makefile |
| `make test-cov` | Full suite + HTML + XML coverage via Makefile |

---

## Writing New Tests

1. Unit tests go in `tests/unit/` — named `test_<module>.py`
2. Always add `sys.path.insert(0, ...)` to find project root
3. For handler tests: mock `bpy` via `sys.modules.setdefault("bpy", MagicMock())`
4. For dispatcher tests: import after patching bpy, then call `load_handlers()`
5. Follow the pattern in `test_manage_history.py` for pure stack logic tests
6. Follow the pattern in `test_parameter_validator.py` for core module tests

### Template

```python
"""Unit tests for manage_X handler."""

from __future__ import annotations
import sys, os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
sys.modules.setdefault("bpy", MagicMock())
sys.modules.setdefault("mathutils", MagicMock())

import blender_mcp.handlers.manage_X as _handler


def test_something() -> None:
    result = _handler._some_function(param="value")
    assert result.get("success") is True
```
