# Blender MCP — Scripts Reference

All scripts run outside Blender. They mock `bpy` / `mathutils` internally where needed.
Run from the **project root** directory using `uv run` (recommended) or `python` directly.

> **uv run vs python:** `uv run <cmd>` automatically uses the `.venv/` virtual environment.
> Without uv, activate `.venv` first: `source .venv/bin/activate` (macOS/Linux) or `.venv\Scripts\activate` (Windows).

---

## Table of Contents

- [Makefile Targets](#makefile-targets)
- [inspect_tools.py](#inspect_toolspy)
- [count_tools.py](#count_toolspy)
- [sync_version.py](#sync_versionpy)
- [test_blender_imports.py](#test_blender_importspy)
- [remove_unused_ignores.py](#remove_unused_ignorespy)
- [quality/run_checks.py](#qualityrun_checkspy)
- [quality/check_version.py](#qualitycheck_versionpy)
- [quality/check_forbidden.py](#qualitycheck_forbiddenpy)
- [quality/check_handler_completeness.py](#qualitycheck_handler_completenesspy)
- [quality/check_handler_imports.py](#qualitycheck_handler_importspy)
- [quality/check_schemas.py](#qualitycheck_schemaspy)
- [quality/check_tool_groups.py](#qualitycheck_tool_groupspy)
- [quality/lint_imports.py](#qualitylint_importspy)
- [python -m blender_mcp](#python--m-blender_mcp)
- [Full Command Reference](#full-command-reference)

---

## Makefile Targets

The `Makefile` in the project root wraps the most common commands. Run `make help` to see all targets.

```bash
make help              # Print all targets with descriptions
make sync              # uv sync --all-extras  (create/update .venv)
make check             # Full quality gate: lint + format + type-check + tests (12 checks)
make check-fast        # Fast quality gate: lint + custom checks only (8 checks)
make format            # Auto-format all code with ruff format
make format-check      # Check formatting without writing files (CI-safe)
make lint              # Syntax + undefined-name lint with ruff
make type-check        # MyPy + Pyright static type analysis
make import-check      # Import architecture rules (import-linter)
make test              # pytest tests/ -v --tb=short
make test-fast         # pytest tests/unit only, stop on first failure (-x)
make test-cov          # Full coverage: HTML + XML + terminal report
make release           # Run all checks, then build blender_mcp_v*.zip
make inspect           # All 69 tools, full detail format
make inspect-essential # ESSENTIAL tier (priority 1–9), full detail
make inspect-summary   # All tools, compact table
make clean             # Remove: .pytest_cache, .mypy_cache, .ruff_cache, __pycache__, *.pyc
make clean-all         # clean + remove .venv and all release ZIPs
```

---

## inspect_tools.py

**Location:** `scripts/inspect_tools.py`

**Purpose:** Browse the full tool registry without starting Blender. Loads all handler modules with mocked `bpy`/`bmesh`/`mathutils` and prints a complete inventory of tools — tier, priority, description, actions, and parameter schemas.

**When to use:**
- Verify that a new handler was registered correctly
- Inspect a tool's full parameter schema
- Get a quick overview of what's in each tier
- Debug why a tool is missing or has wrong metadata

```bash
# Full report — every tool with all parameters (~400 lines)
uv run python scripts/inspect_tools.py

# Compact summary table — one row per tool (most useful for overview)
uv run python scripts/inspect_tools.py --summary

# Filter to a specific tier
uv run python scripts/inspect_tools.py --tier essential   # priority 1–9
uv run python scripts/inspect_tools.py --tier core        # priority 10–49
uv run python scripts/inspect_tools.py --tier standard    # priority 50–149
uv run python scripts/inspect_tools.py --tier optional    # priority 150+

# Filter by category or name substring
uv run python scripts/inspect_tools.py --cat anim         # animation tools
uv run python scripts/inspect_tools.py --cat render       # rendering tools
uv run python scripts/inspect_tools.py --cat scene        # scene management tools
uv run python scripts/inspect_tools.py --cat geo          # geometry/mesh tools
uv run python scripts/inspect_tools.py --cat mat          # material tools

# Single tool deep dive — full schema + all parameters
uv run python scripts/inspect_tools.py --tool get_scene_graph
uv run python scripts/inspect_tools.py --tool execute_blender_code
uv run python scripts/inspect_tools.py --tool manage_rendering
uv run python scripts/inspect_tools.py --tool manage_animation

# Hide parameter tree (show tool info but not the parameter table)
uv run python scripts/inspect_tools.py --no-params
uv run python scripts/inspect_tools.py --tier essential --no-params

# Combinations
uv run python scripts/inspect_tools.py --tier core --no-params
uv run python scripts/inspect_tools.py --cat anim --summary
```

**Full output example:**
```
  [  1] ⭐ execute_blender_code
        Title    : Execute Blender Code
        Category : general
        Description:
        |       ESSENTIAL (priority=1) — Execute arbitrary Python code in Blender...
        Actions  : execute_blender_code
        Parameters (2):
          ├── [REQ] code (string)        — Python code to execute
          └──       timeout (integer)    [default=30] — Execution timeout in seconds
```

**Summary table example:**
```
#    TIER         PRI   TOOL NAME                              CATEGORY       ACTIONS
------------------------------------------------------------------------------------------
1    ⭐ ESSENTIAL  1     execute_blender_code                   general        execute_blender_code
2    ⭐ ESSENTIAL  2     get_scene_graph                        scene          GET_OBJECTS_FLAT +10
```

---

## count_tools.py

**Location:** `scripts/count_tools.py`

**Purpose:** Count `@register_handler` decorators across all handler files using regex — no Python imports needed, so it works even if dependencies are broken. Groups results by name prefix.

**When to use:** Quick sanity-check of how many tools are registered, or to list all tool names grouped by prefix category.

```bash
python scripts/count_tools.py

# Or with uv
uv run python scripts/count_tools.py
```

**Output example:**
```
Scanning .../blender_mcp/handlers/...
Results:
  Total Handler Files:    52
  Total Registered Tools: 69
[EXECUTE]
  - execute_blender_code
[GET]
  - get_local_transforms
  - get_object_info
  - get_scene_graph
  - get_server_status
  - get_viewport_screenshot_base64
[MANAGE]
  - manage_agent_context
  - manage_animation
  ...
```

---

## sync_version.py

**Location:** `scripts/sync_version.py`

**Purpose:** Keep the version string consistent across all project files. Single source of truth: `blender_mcp/__version__.py`. This script propagates the version to `pyproject.toml`, `__init__.py`, `dispatcher.py`, and `uv.lock`.

**When to use:** After bumping the version in `__version__.py`, or to verify all files are in sync before a release.

```bash
# Sync current version from __version__.py to all files (no bump)
python scripts/sync_version.py
uv run python scripts/sync_version.py

# Bump patch version:  1.0.0 → 1.0.1
python scripts/sync_version.py --bump patch

# Bump minor version:  1.0.0 → 1.1.0
python scripts/sync_version.py --bump minor

# Bump major version:  1.0.0 → 2.0.0
python scripts/sync_version.py --bump major

# Set an exact version
python scripts/sync_version.py --set 1.2.3

# Verify only — don't write anything
python scripts/sync_version.py --verify
```

**Files updated:**
| File | Field |
|------|-------|
| `blender_mcp/__version__.py` | `VERSION_TUPLE` (only when bumping/setting) |
| `pyproject.toml` | `version = "..."` |
| `blender_mcp/__init__.py` | `"version": (X, Y, Z)` in `bl_info` |
| `blender_mcp/dispatcher.py` | `"version": "..."` in server status |
| `uv.lock` | `blender-mcp` package version entry |

**Recommended release workflow:**
```bash
python scripts/sync_version.py --bump patch    # bump version
python scripts/sync_version.py --verify        # confirm sync
make check                                     # run quality gates
python create_release_zip.py                  # build ZIP
```

---

## test_blender_imports.py

**Location:** `scripts/test_blender_imports.py`

**Purpose:** Validate that all handlers and core modules can be imported inside a **real Blender Python environment**. This is the only script that requires Blender — it's designed to run with Blender's `--background` flag.

**When to use:** After writing a new handler, run this in Blender to catch import errors before users install the addon.

```bash
# Run headless (no Blender UI needed)
blender --background --python scripts/test_blender_imports.py

# Run from inside Blender's Scripting workspace (paste into Python console):
import sys
sys.path.insert(0, 'C:/path/to/Blender_mcp')
exec(open('scripts/test_blender_imports.py').read())
```

**What it tests:**
1. Core modules: `error_handling`, `compatibility`, `resolver`, `context`, `reliability`
2. Dispatcher: loads `HANDLER_REGISTRY`, counts handlers
3. Critical handlers: `manage_scene`, `manage_modeling`, `manage_sculpting`, `manage_materials`, `manage_physics`, `manage_camera`

> **Note:** Running outside Blender prints `[WARN] Not running in Blender` — tests will fail because `bpy` isn't available without mocking. This script is specifically for real Blender.

---

## remove_unused_ignores.py

**Location:** `scripts/remove_unused_ignores.py`

**Purpose:** Reads mypy's text output and removes `# type: ignore` comments that mypy reports as unused. Keeps the codebase clean after fixing type errors.

**When to use:** After a round of type fixes, mypy will report `[unused-ignore]` for suppressions that are no longer needed. Use this script to remove them automatically.

```bash
# 1. Run mypy and save output to a file
uv run mypy blender_mcp > /tmp/mypy_output.txt 2>&1

# 2. Remove unused type:ignore comments
python scripts/remove_unused_ignores.py /tmp/mypy_output.txt

# 3. Verify the fixes
uv run mypy blender_mcp
```

**How it works:** Parses mypy output with regex to find `"Unused type: ignore"` / `[unused-ignore]` messages, extracts the file path and line number, then removes the `# type: ignore[...]` suffix from that line in the source file.

> **Warning:** Review the changes before committing — verify the removed suppressions don't introduce new mypy errors.

---

## quality/run_checks.py

**Location:** `scripts/quality/run_checks.py`

**Purpose:** The main quality gate. Orchestrates 8–12 checks and prints a pass/fail summary. This is what `make check` and `make check-fast` call internally.

**When to use:** Before every commit. All checks must pass. The `--fast` mode is suitable for rapid iteration during development; full mode is required before creating a release.

```bash
# Fast mode — 8 checks (~10s)
uv run python scripts/quality/run_checks.py --fast

# Full mode — 12 checks including type analysis (~60s)
uv run python scripts/quality/run_checks.py

# Auto-fix ruff lint issues where possible
uv run python scripts/quality/run_checks.py --fix

# Strict — warnings count as errors
uv run python scripts/quality/run_checks.py --strict
uv run python scripts/quality/run_checks.py --fast --strict
```

**Check sequence:**
| # | Name | Tool | What it catches | Fast? |
|---|------|------|-----------------|-------|
| 1 | venv | pip check | Missing dependencies | ✓ |
| 2 | ruff-lint | ruff | Syntax errors, undefined names | ✓ |
| 3 | ruff-format | ruff format | Formatting violations | — |
| 4 | import-arch | lint_imports.py | Circular imports, layering violations | ✓ |
| 5 | imports | check_handler_imports.py | Absolute imports in handlers | ✓ |
| 6 | completeness | check_handler_completeness.py | Missing handlers, duplicates | ✓ |
| 7 | tool-groups | check_tool_groups.py | Tool group integrity | ✓ |
| 8 | forbidden | check_forbidden.py | Fatal Blender 5.x breakages | ✓ |
| 9 | version | check_version.py | Version string consistency | ✓ |
| 10 | mypy | mypy | Static type errors | — |
| 11 | pyright | pyright | Additional type analysis | — |
| 12 | schemas | check_schemas.py | Invalid JSON schemas | — |

**Exit codes:** 0 = all pass, 1 = at least one check failed.

---

## quality/check_version.py

**Location:** `scripts/quality/check_version.py`

**Purpose:** Verify the version string is identical in all tracked files.

```bash
uv run python scripts/quality/check_version.py
```

**Files checked:** `blender_mcp/__version__.py`, `pyproject.toml`, `blender_mcp/dispatcher.py`, `blender_mcp/__init__.py`

**Fix:** Run `python scripts/sync_version.py` if versions diverge.

---

## quality/check_forbidden.py

**Location:** `scripts/quality/check_forbidden.py`

**Purpose:** Scan `blender_mcp/` source files for patterns that **will crash Blender 5.x**. Fatal patterns fail the check; informational patterns are logged but don't block (High Mode philosophy).

```bash
# Check all blender_mcp/ Python files
uv run python scripts/quality/check_forbidden.py --all

# Check specific files
uv run python scripts/quality/check_forbidden.py blender_mcp/handlers/manage_scene.py
```

**Fatal patterns — hard fail:**
| Pattern | Why |
|---------|-----|
| `bpy.types.SimpleNamespace` | Removed in Blender 5.x — use `dict` or `dataclass` |
| `mathutils.noise.arctan2` | Removed — use `math.atan2` |
| `.face_indices` | Removed — use `.link_faces` |

**Informational only (not blocked in High Mode):**
- `eval()` / `exec()` — required for scripting handler
- Absolute imports — works but relative preferred

---

## quality/check_handler_completeness.py

**Location:** `scripts/quality/check_handler_completeness.py`

**Purpose:** Verify all required handlers exist, have `@register_handler` decorators, and load successfully. Also detects duplicate registrations.

```bash
uv run python scripts/quality/check_handler_completeness.py
uv run python scripts/quality/check_handler_completeness.py --strict  # warnings = errors
```

**Checks:**
1. 18 required handlers are present (manage_scene, manage_modeling, manage_materials, etc.)
2. Each handler file has `@register_handler` decorator
3. No duplicate handler names across files
4. `load_handlers()` completes without errors

> External integrations (`hunyuan`, `hyper3d`, etc.) are optional — their failures are reported but don't fail the check.

---

## quality/check_handler_imports.py

**Location:** `scripts/quality/check_handler_imports.py`

**Purpose:** Enforce relative imports in handler files. Absolute imports break the addon ZIP installation path.

```bash
uv run python scripts/quality/check_handler_imports.py --all
```

**Rule:** Use `from ..module import X`, not `from blender_mcp.module import X`.

---

## quality/check_schemas.py

**Location:** `scripts/quality/check_schemas.py`

**Purpose:** Validate every handler's JSON Schema. Imports all handlers with mocked `bpy` and checks `HANDLER_METADATA`.

```bash
uv run python scripts/quality/check_schemas.py --all
uv run python scripts/quality/check_schemas.py --all --verbose
```

**Validates:** `"type": "object"` present, `"properties"` present, each property has `"type"`, required fields exist in properties, enum lists are non-empty.

---

## quality/check_tool_groups.py

**Location:** `scripts/quality/check_tool_groups.py`

**Purpose:** Validate the `manage_tool_groups` handler's `TOOL_GROUPS` definition — all referenced handlers exist, all required keys are present.

```bash
uv run python scripts/quality/check_tool_groups.py
```

---

## quality/lint_imports.py

**Location:** `scripts/quality/lint_imports.py`

**Purpose:** Enforce import layering rules using Python AST analysis. Prevents circular dependencies.

```bash
uv run python scripts/quality/lint_imports.py
```

**Rules:**
| Rule | Description |
|------|-------------|
| No star imports | `from module import *` forbidden everywhere |
| Core → no Handlers | `core/` cannot import `handlers/` |
| Utils → no Core/Handlers | `utils/` cannot import `core/` or `handlers/` |

**Layer hierarchy (bottom to top):**
```
utils  →  core  →  handlers  →  dispatcher
```

---

## python -m blender_mcp

Run the package as a module for quick CLI help and status without starting Blender.

```bash
# Show help overview — all tools, scripts, and commands
python -m blender_mcp --help
uv run python -m blender_mcp --help

# Show version
python -m blender_mcp --version

# List all registered tools (summary table, same as inspect_tools.py --summary)
python -m blender_mcp --list-tools

# Check project status — version sync, handler count, environment
python -m blender_mcp --status
```

---

## Full Command Reference

All commands in logical workflow order. Run from the **project root**.

```bash
# ── SETUP ──────────────────────────────────────────────────────────────────
uv sync --all-extras                                          # Install all deps into .venv

# ── INSPECT TOOLS ──────────────────────────────────────────────────────────
uv run python scripts/inspect_tools.py --summary              # Compact table, all 69 tools
uv run python scripts/inspect_tools.py --tier essential       # ESSENTIAL tier, full detail
uv run python scripts/inspect_tools.py --tier core            # CORE tier, full detail
uv run python scripts/inspect_tools.py --tool get_scene_graph # Single tool deep dive
uv run python scripts/inspect_tools.py --cat anim             # Filter by category substring
uv run python scripts/inspect_tools.py --no-params            # Hide parameter trees
python scripts/count_tools.py                                 # Count handlers (no imports)

# ── QUALITY CHECKS ─────────────────────────────────────────────────────────
uv run python scripts/quality/run_checks.py --fast            # 8 checks (~10s)
uv run python scripts/quality/run_checks.py                   # 12 checks (~60s)
uv run python scripts/quality/check_version.py                # Version consistency only
uv run python scripts/quality/check_forbidden.py --all        # Fatal pattern scan only
uv run python scripts/quality/check_handler_completeness.py   # Handler registry audit

# ── FORMATTING & LINTING ───────────────────────────────────────────────────
uv run ruff format blender_mcp scripts tests                  # Auto-format all files
uv run ruff format --check blender_mcp scripts tests          # Check only (no writes)
uv run ruff check blender_mcp scripts tests --select E9,F63,F7,F82  # Lint

# ── TYPE CHECKING ──────────────────────────────────────────────────────────
uv run mypy blender_mcp --ignore-missing-imports              # MyPy type analysis
uv run pyright blender_mcp                                    # Pyright type analysis

# ── TESTING ────────────────────────────────────────────────────────────────
uv run pytest tests/unit -q                                   # 499 unit tests, ~1.4s
uv run pytest tests/unit -q -x                                # Stop on first failure
uv run pytest tests -v --tb=short                             # Full suite, verbose
uv run pytest tests -v --cov=blender_mcp --cov-report=term    # With coverage report
uv run pytest tests -k "test_protocol"                        # Run matching tests only

# ── VERSION MANAGEMENT ─────────────────────────────────────────────────────
python scripts/sync_version.py --verify                       # Verify all files in sync
python scripts/sync_version.py                                # Sync current version
python scripts/sync_version.py --bump patch                   # 1.0.0 → 1.0.1
python scripts/sync_version.py --bump minor                   # 1.0.0 → 1.1.0
python scripts/sync_version.py --bump major                   # 1.0.0 → 2.0.0
python scripts/sync_version.py --set 1.2.3                    # Set exact version

# ── RELEASE ────────────────────────────────────────────────────────────────
python create_release_zip.py                                  # Build blender_mcp_v*.zip only
make release                                                  # Full quality gate + ZIP

# ── BLENDER RUNTIME (requires Blender installed) ───────────────────────────
blender --background --python scripts/test_blender_imports.py # Validate in real Blender

# ── MAINTENANCE ────────────────────────────────────────────────────────────
uv run mypy blender_mcp > /tmp/mypy.txt 2>&1 && python scripts/remove_unused_ignores.py /tmp/mypy.txt
make clean                                                    # Remove cache dirs + *.pyc
make clean-all                                                # clean + remove .venv and ZIPs

# ── MAKEFILE SHORTCUTS ─────────────────────────────────────────────────────
make help              # List all targets
make sync              # uv sync --all-extras
make check             # Full quality gate (12 checks)
make check-fast        # Fast quality gate (8 checks)
make format            # Auto-format code
make lint              # Lint only
make type-check        # mypy + pyright
make test              # pytest tests/
make test-fast         # pytest tests/unit -x (stop on first fail)
make test-cov          # pytest with HTML/XML/terminal coverage
make inspect           # All tools full format
make inspect-essential # ESSENTIAL tier full format
make inspect-summary   # All tools compact table
make release           # All checks + create ZIP
make clean             # Remove cache artifacts
make clean-all         # Remove everything including .venv
```
