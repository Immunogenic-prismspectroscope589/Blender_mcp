# Blender MCP — Architecture

> Last Updated: 2026-03-10 | Version: 1.0.0

---

## Overview

Blender MCP connects AI agents to a live Blender session via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). The system is split across two separate OS processes — because `bpy` (Blender's Python API) only exists inside Blender's own bundled Python interpreter and cannot be imported anywhere else.

```
┌─────────────────────────────────────────────────────────────────────┐
│  AI Agent Process  (Claude / GPT / any MCP client)                  │
│                                                                     │
│    "Create a red metallic cube at position 2, 0, 0"                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  stdio  (JSON-RPC 2.0 / MCP protocol)
                               │  {"jsonrpc":"2.0","method":"tools/call",...}
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  MCP Bridge Process  (stdio_bridge.py)                              │
│  Standard Python — runs outside Blender, started by AI client      │
│                                                                     │
│  • Parses JSON-RPC 2.0 from AI client                               │
│  • Caches tool schemas from Blender on first connect                │
│  • Validates JSON schemas (jsonschema) before forwarding            │
│  • Handles tools/list and tools/call MCP methods                    │
│  • Translates MCP ↔ Blender wire protocol                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  TCP localhost:9879
                               │  4-byte Big-Endian uint32 length + UTF-8 JSON
                               │  {"tool": "...", "params": {...}}
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Blender Process  (blender_mcp addon)                               │
│  Blender's Python — the only place bpy exists                       │
│                                                                     │
│  BlenderMCPServer (background thread)                               │
│    └── TCP listener on port 9879                                    │
│         └── on message: execute_on_main_thread(dispatch_command)    │
│                                        ↓                            │
│  dispatcher.dispatch_command()  [main thread via bpy.app.timers]   │
│    1. SecurityManager.validate_action()     ← Safe/High Mode check  │
│    2. HANDLER_REGISTRY lookup              ← unknown tool → error   │
│    3. Action string validation             ← not in actions → error │
│    4. validate_params_schema()             ← coerce + validate      │
│    5. execute_on_main_thread(handler_fn)   ← already on main thread │
│    6. Result normalization + _meta inject  ← standardize output     │
│                                        ↓                            │
│  Handler function (e.g. manage_scene_comprehension)                 │
│    └── bpy.data / bpy.ops / mathutils / bmesh calls                 │
│         └── 3D scene modified / queried                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Wire Protocol

**Transport:** TCP, `localhost:9879` only — no external binding.

**Framing:** 4-byte Big-Endian unsigned integer length header, followed by that many bytes of UTF-8 JSON.

```
Byte layout:
┌──────────────────────┬────────────────────────────────────────────┐
│  4 bytes             │  N bytes                                   │
│  uint32 Big-Endian   │  UTF-8 JSON payload                        │
│  value = N           │  {"tool": "...", "params": {...}}           │
└──────────────────────┴────────────────────────────────────────────┘
```

**Why length-prefix instead of newlines?** JSON values can span multiple lines; length-prefix framing is unambiguous and doesn't require escaping.

**Implementation:** `blender_mcp/core/protocol.py`
- `send_message(sock, data)` — serializes dict to JSON, prepends 4-byte length, calls `sendall`
- `recv_message(sock)` — reads 4-byte header, reads exactly N bytes, deserializes JSON
- `_recv_n(sock, n)` — reads exactly n bytes, handles partial TCP segments, returns None on connection close

**Request format:**
```json
{
  "tool": "get_scene_graph",
  "params": {
    "action": "GET_OBJECTS_FLAT"
  }
}
```

**Success response format:**
```json
{
  "status": "success",
  "result": {
    "success": true,
    "objects": [...],
    "_meta": {
      "request_id": "abc123",
      "tool": "get_scene_graph",
      "action": "GET_OBJECTS_FLAT",
      "elapsed_ms": 12.4
    }
  }
}
```

**Error response format:**
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_ACTION",
    "message": "Unknown action 'FOO'. Valid: GET_OBJECTS_FLAT, GET_SCENE_MATRIX, ..."
  }
}
```

---

## Thread Model

Blender's Python API (`bpy`) is strictly single-threaded — all `bpy.*` calls must happen on Blender's **main thread** (the event loop thread). The TCP listener runs on a **background thread**. The thread safety layer bridges this:

```
Background Thread (TCP socket listener)
         │
         │  receives JSON command bytes
         │  deserializes to dict
         │
         ▼
execute_on_main_thread(handler_fn, timeout=300)
         │  appends (callable, threading.Event, result_holder) to timer queue
         │  calls bpy.app.timers.register(tick_fn, first_interval=0.001)
         │  blocks on threading.Event.wait(timeout)
         │
         ▼  [Blender event loop fires timer]
Main Thread
         │  timer callback executes handler_fn()
         │  handler calls bpy.data, bpy.ops, mathutils, etc.
         │  result stored in result_holder
         │  threading.Event.set() — unblocks background thread
         │
         ▼
Background Thread unblocked
         │  retrieves result from result_holder
         │  serializes to JSON, sends back over TCP
```

**Key file:** `blender_mcp/core/thread_safety.py`

- `execute_on_main_thread(fn, timeout=300)` — the core marshalling function
- `@ensure_main_thread` — decorator that asserts a function is called from the main thread
- Default timeout: 300 seconds (covers long bpy operations; render uses a subprocess instead)

**Why `bpy.app.timers`?** It's the only Blender-provided mechanism for scheduling callbacks on the main thread from external threads. The timer fires on the next frame of Blender's event loop — typically within 1–10ms when Blender is idle.

---

## Handler System

### Registration

Every tool is a Python function decorated with `@register_handler`:

```python
@register_handler(
    "manage_scene",                      # unique command name (string)
    priority=14,                         # tier: 1-9=ESSENTIAL, 10-49=CORE, 50-149=STANDARD, 150+=OPTIONAL
    actions=["NEW_SCENE", "RENAME"],     # valid values for the "action" param
    category="scene",                    # for intent routing and filtering
    schema={                             # JSON Schema for parameter validation
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["NEW_SCENE", "RENAME"]},
            "name": {"type": "string"},
        },
        "required": ["action"],
    },
    description="CORE — ...",
)
def manage_scene(action=None, **params):
    ...
```

All `.py` files in `blender_mcp/handlers/` are **auto-discovered** by `dispatcher.load_handlers()` at addon startup. No registration list to maintain.

### Priority Tiers

| Range | Tier | Typical count | Format in `list_all_tools` |
|-------|------|---------------|---------------------------|
| 1–9 | ESSENTIAL | 9 | Full detail — title, description, parameter table |
| 10–49 | CORE | ~35 | Compact one-line table row |
| 50–149 | STANDARD | ~20 | Compact one-line table row |
| 150+ | OPTIONAL | 4 | Listed last |

The hybrid format in `list_all_tools` ensures ESSENTIAL tools always get full context while keeping total token usage manageable (~77% reduction vs listing everything in full detail).

### Dispatch Flow

```
dispatch_command({"tool": "get_scene_graph", "params": {"action": "GET_OBJECTS_FLAT"}})
         │
         ├─ 1. SecurityManager.validate_action()   → blocked in Safe Mode? → error
         ├─ 2. HANDLER_REGISTRY.get(tool_name)     → not found? → UNKNOWN_TOOL error
         ├─ 3. validate_action_string(action)       → not in actions list? → INVALID_ACTION error
         ├─ 4. validate_params_schema(params, schema)  → coerce types, then validate
         │      • type coercion: "5" → 5 (string→int), "true" → True (string→bool), etc.
         │      • bounds clamping: count=0 with minimum=1 → clamped to 1 before range check
         │      • unknown params → warning (not error)
         │      • missing required → error
         ├─ 5. execute_on_main_thread(handler_fn, **sanitized_params)
         └─ 6. normalize_result(raw_result) → inject _meta → return
```

---

## Security Model

Controlled by `blender_mcp/core/security.py`. Toggle from the addon's N-panel or programmatically.

| Mode | `execute_blender_code` | Destructive ops |
|------|------------------------|-----------------|
| **High Mode** (default) | ✅ Available — full bpy Python | ✅ Available |
| **Safe Mode** | ❌ Blocked | ❌ Blocked |

### BLOCKED_PATTERN — Always blocked regardless of mode

```python
# blender_mcp/handlers/manage_scripting.py
_BLOCKING_RENDER_PATTERNS = [
    (r"bpy\.ops\.render\.render\s*\(", "BLOCKED: freezes main thread..."),
]
```

`bpy.ops.render.render()` runs synchronously on the main thread — Blender cannot process any MCP timer callbacks during rendering (which can take minutes). Auto-rejected with `error_code: "BLOCKED_PATTERN"`. Use `manage_rendering action=RENDER_FRAME` instead (subprocess).

### Input Validation Layers

1. **Bridge** (`stdio_bridge.py`) — `jsonschema` validation before TCP forward
2. **Dispatcher** — action string check + `ParameterValidator.validate()` with type coercion
3. **Handler** — domain-specific validation (object exists, path valid, etc.)

---

## Parameter Validation

`blender_mcp/core/parameter_validator.py` implements a two-phase approach:

**Phase 1 — Type coercion** (before schema validation):
- `"5"` → `5` for integer params
- `"3.14"` → `3.14` for number params
- `"true"` / `"yes"` / `"1"` / `"on"` → `True` for boolean params
- Values outside `minimum`/`maximum` bounds are **clamped** (not rejected)

**Phase 2 — Schema validation** (after coercion):
- Checks required fields are present and non-None
- Checks enum values
- Warns on unknown params (doesn't reject — allows forward compatibility)
- Applies default values for missing optional params

This means `count=0` with `minimum=1` becomes `count=1` (clamped) and passes validation, rather than failing.

---

## Intent Routing

`blender_mcp/core/intent_router.py` maps free-text intent strings to handler categories:

```
Input: "I want to rig a character"
       ↓
Score each category by keyword matches:
  MODELING:      0 matches
  ANIMATION:     3 matches (rig, character → animation)
  RENDERING:     0 matches
  ...
       ↓
Return: handlers in top-scoring categories
        ~15 tools instead of 69 → ~77% token savings
```

**Languages:** English, Turkish, French keyword sets per category.
**Categories:** MODELING, ANIMATION, RENDERING, MATERIALS, PHYSICS, SCENE_PIPELINE, AI_EXTERNAL.

---

## Semantic Memory

`blender_mcp/core/semantic_memory.py` maintains a tag-based index of Blender objects:

```
resolve("main_camera")
  → check if "main_camera" is a direct object name (bpy.data.objects)
  → check _tag_index["main_camera"] → ["Camera"]
  → return bpy.data.objects.get("Camera")

resolve("last_created")
  → return bpy.data.objects.get(_last_created)
```

`KNOWN_TAGS` contains detection lambdas for semantic roles like `main_camera`, `hero_character`, `ground_plane`, `key_light`. Auto-populated by scanning the scene on first use.

---

## Async Job Manager

`blender_mcp/core/job_manager.py` handles long-running operations (renders) as background subprocesses:

```
manage_rendering(action="RENDER_FRAME", filepath="/tmp/out.png")
  → AsyncJobManager.start_render_job(...)
  → spawns subprocess: blender --background --python render_worker.py
  → returns {"job_id": "render_001", "status": "RUNNING"} immediately

manage_rendering(action="GET_JOB_STATUS", job_id="render_001")
  → AsyncJobManager.get_job_status("render_001")
  → returns {"status": "COMPLETE", "filepath": "/tmp/out.png"} when done
```

Job store: `_jobs` dict capped at `MAX_JOBS` (oldest finished jobs evicted).

---

## External Integrations

Four external service integrations, always loaded last (priority 150+):

| Handler | Service | What it does |
|---------|---------|-------------|
| `polyhaven_handler` | [Polyhaven](https://polyhaven.com/) | Download free CC0 HDRIs, textures, 3D models directly into Blender |
| `sketchfab_handler` | [Sketchfab](https://sketchfab.com/) | Search and download 3D models by keyword |
| `hunyuan_handler` | [Tencent Hunyuan3D](https://3d.hunyuan.tencent.com/) | AI image-to-3D generation |
| `hyper3d_handler` | [Hyper3D Rodin](https://hyper3d.ai/) | AI text/image-to-3D generation |

The core MCP functionality works entirely offline. External integrations require API keys or service availability.

---

## Key Files Quick Reference

| File | Role |
|------|------|
| `stdio_bridge.py` | MCP bridge — started by AI client, runs outside Blender |
| `blender_mcp/__init__.py` | Addon entry, `BlenderMCPServer`, N-panel UI |
| `blender_mcp/__main__.py` | `python -m blender_mcp` CLI |
| `blender_mcp/dispatcher.py` | `HANDLER_REGISTRY`, `dispatch_command`, `list_all_tools` |
| `blender_mcp/core/protocol.py` | `send_message`, `recv_message`, `_recv_n` |
| `blender_mcp/core/thread_safety.py` | `execute_on_main_thread`, `@ensure_main_thread` |
| `blender_mcp/core/execution_engine.py` | `ExecutionEngine`, `SafeOps`, `ExecutionPolicy` |
| `blender_mcp/core/parameter_validator.py` | Type coercion + schema validation |
| `blender_mcp/core/security.py` | `SecurityManager` — Safe/High Mode |
| `blender_mcp/core/semantic_memory.py` | Tag index, `resolve()`, `KNOWN_TAGS` |
| `blender_mcp/core/intent_router.py` | `classify_intent()`, multilingual keyword sets |
| `blender_mcp/core/job_manager.py` | `AsyncJobManager` — render subprocess queue |
| `blender_mcp/core/response_builder.py` | `ResponseBuilder.success()` / `.error()` |
| `blender_mcp/core/error_protocol.py` | `ErrorCode` enum — 280+ error codes |
| `blender_mcp/__version__.py` | Single source of version truth |
