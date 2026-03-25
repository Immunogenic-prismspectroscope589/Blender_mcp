"""
blender_mcp CLI — run as: python -m blender_mcp [--help|--version|--list-tools|--status]

Provides a quick overview of tools, scripts, and project status
without needing Blender running.
"""

from __future__ import annotations

import argparse
import sys
import os


def _get_version() -> str:
    try:
        from blender_mcp.__version__ import VERSION

        return VERSION
    except ImportError:
        return "unknown"


def _print_help() -> None:
    version = _get_version()
    print(f"""
Blender MCP v{version}
Control Blender with AI via the Model Context Protocol.
GitHub: https://github.com/glonorce/Blender_mcp
Inspired by: https://github.com/ahujasid/blender-mcp

USAGE
  python -m blender_mcp [OPTIONS]

OPTIONS
  --help          Show this help message
  --version       Print version number
  --list-tools    List all registered tools (summary table)
  --status        Show project health (version sync, handler count)

QUICK START
  1. Build the addon ZIP:
       python create_release_zip.py

  2. Install in Blender:
       Edit → Preferences → Add-ons → Install → blender_mcp_v{version}.zip → Enable

  3. Configure your MCP client (Claude Desktop, Cursor, Codex…):
       See README.md for config snippets

  4. Verify in your AI client:
       Tool: get_server_status

MCP BRIDGE
  python -u stdio_bridge.py               Start the MCP bridge manually
  BLENDER_HOST=localhost                  Default Blender host
  BLENDER_PORT=9879                       Default Blender TCP port
  PYTHONPATH=<project-root>              Must be set so blender_mcp is importable

SCRIPTS
  uv run python scripts/inspect_tools.py --summary      All 69 tools, compact table
  uv run python scripts/inspect_tools.py --tier essential  ESSENTIAL tier, full detail
  uv run python scripts/inspect_tools.py --tool <name>  Single tool deep dive
  python scripts/count_tools.py                          Count registered handlers
  python scripts/sync_version.py --verify                Verify version consistency
  python scripts/sync_version.py --bump patch            Bump version (1.0.0 → 1.0.1)

QUALITY GATES
  uv run python scripts/quality/run_checks.py --fast     8 checks (~10s)
  uv run python scripts/quality/run_checks.py            12 checks (~60s)
  uv run ruff format blender_mcp scripts tests           Auto-format code
  uv run mypy blender_mcp                                Type analysis

TESTS
  uv run pytest tests/unit -q                            499 unit tests, ~1.4s
  uv run pytest tests -v --cov=blender_mcp               Full suite with coverage

MAKEFILE SHORTCUTS
  make help              List all targets
  make sync              Install dependencies (uv sync --all-extras)
  make check             Full quality gate (12 checks)
  make check-fast        Fast quality gate (8 checks)
  make test              Run all tests
  make test-fast         Unit tests only, stop on first failure
  make inspect-summary   All tools compact table
  make inspect-essential ESSENTIAL tools full detail
  make release           Quality gate + build ZIP
  make clean             Remove cache artifacts

TOOL TIERS
  ⭐ ESSENTIAL (1–9):   9 tools — always shown first in list_all_tools
  ● CORE      (10–49):  ~35 tools — important standard tools
  ○ STANDARD  (50–149): ~20 tools — all other tools
  · OPTIONAL  (150+):   4 tools — external integrations (Polyhaven, Sketchfab…)

ESSENTIAL TOOLS (priority 1–9)
  1  execute_blender_code          Full bpy Python API — the primary creation tool
  2  get_scene_graph               Scene intelligence: 11 actions (GET_OBJECTS_FLAT, CAST_RAY…)
  3  get_viewport_screenshot_base64 Visual verification — single/multi-view capture
  4  get_object_info               Object detail inspector
  5  get_local_transforms          Parent-relative coordinates
  6  manage_agent_context          Workflow guides (GET_PRIMER, GET_TACTICS…)
  7  list_all_tools                Tool discovery with intent filtering
  8  get_server_status             Health check
  9  new_scene                     Create empty scene

ARCHITECTURE
  Claude/AI → stdio (JSON-RPC 2.0) → stdio_bridge.py → TCP:9879 → Blender Addon → bpy API

  stdio_bridge.py runs outside Blender (standard Python).
  The Blender addon runs inside Blender's Python (has bpy).
  TCP localhost:9879 with 4-byte length-prefix + JSON body.

DOCS
  docs/ARCHITECTURE.md             System design, wire protocol, thread model
  scripts/SCRIPTS.md               All scripts documented with examples
  tests/TESTS.md                   Test suite documentation

For more information: https://github.com/glonorce/Blender_mcp
""")


def _list_tools() -> None:
    """List all tools using inspect_tools.py summary mode."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inspect_script = os.path.join(project_root, "scripts", "inspect_tools.py")

    if not os.path.exists(inspect_script):
        print("ERROR: scripts/inspect_tools.py not found. Run from the project root.")
        sys.exit(1)

    import subprocess

    result = subprocess.run(
        [sys.executable, inspect_script, "--summary"],
        cwd=project_root,
    )
    sys.exit(result.returncode)


def _show_status() -> None:
    """Show project health status."""
    version = _get_version()
    print(f"Blender MCP v{version}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")

    # Count handlers
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        handlers_dir = os.path.join(project_root, "blender_mcp", "handlers")
        import glob

        handler_files = [
            f
            for f in glob.glob(os.path.join(handlers_dir, "*.py"))
            if not os.path.basename(f).startswith("_")
        ]
        print(f"Handler files: {len(handler_files)}")
    except Exception:
        print("Handler files: (could not count)")

    # Check version sync
    try:
        import re
        from pathlib import Path

        root = Path(project_root)
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            pv = match.group(1) if match else "?"
            sync = "[OK]" if pv == version else "[MISMATCH]"
            print(f"Version sync: {sync} (__version__.py={version}, pyproject.toml={pv})")
    except Exception:
        pass

    print(f"\nFor full status: uv run python scripts/quality/run_checks.py --fast")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m blender_mcp",
        description="Blender MCP — project CLI and help",
        add_help=False,
    )
    parser.add_argument("--help", "-h", action="store_true", help="Show help")
    parser.add_argument("--version", "-v", action="store_true", help="Print version")
    parser.add_argument("--list-tools", action="store_true", help="List all registered tools")
    parser.add_argument("--status", action="store_true", help="Show project health status")

    args = parser.parse_args()

    if args.version:
        print(_get_version())
    elif args.list_tools:
        _list_tools()
    elif args.status:
        _show_status()
    else:
        _print_help()


if __name__ == "__main__":
    main()
