"""
Blender MCP Tool & Action Inspector
------------------------------------
Runs outside Blender by mocking bpy/bmesh/mathutils.
Prints a full inventory of all registered tools: tier, priority, description,
actions, and parameters — sorted by priority order (ESSENTIAL first).

Usage:
    python scripts/inspect_tools.py              # Full report
    python scripts/inspect_tools.py --tier core  # Filter by tier
    python scripts/inspect_tools.py --cat anim   # Filter by category substring
    python scripts/inspect_tools.py --tool manage_objects  # Single tool detail
    python scripts/inspect_tools.py --no-params  # Hide parameter tree
    python scripts/inspect_tools.py --summary    # Summary table only
"""

import sys
import os
import pkgutil
import importlib
import textwrap
import argparse
from unittest.mock import MagicMock

# Force UTF-8 output on Windows terminals
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ─── Tier helpers ────────────────────────────────────────────────────────────

TIERS = [
    (1, 9, "ESSENTIAL", "⭐"),
    (10, 49, "CORE", "●"),
    (50, 149, "STANDARD", "○"),
    (150, 9999, "OPTIONAL", "·"),
]


def tier_info(priority: int) -> tuple[str, str]:
    """Return (tier_name, icon) for a given priority value."""
    for lo, hi, name, icon in TIERS:
        if lo <= priority <= hi:
            return name, icon
    return "OPTIONAL", "·"


def format_description(desc: str, indent: str = "|   ", width: int = 72) -> list[str]:
    """Wrap and indent a multi-line description, returning list of lines."""
    lines = []
    for paragraph in desc.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        wrapped = textwrap.fill(paragraph, width=width)
        for line in wrapped.splitlines():
            lines.append(f"{indent}    {line}")
    return lines


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Blender MCP Tool Inspector")
    parser.add_argument("--tier", help="Filter by tier name (essential/core/standard/optional)")
    parser.add_argument("--cat", help="Filter by category substring (e.g. 'anim', 'geo')")
    parser.add_argument("--tool", help="Show single tool detail by name")
    parser.add_argument("--no-params", action="store_true", help="Hide parameter tree")
    parser.add_argument("--summary", action="store_true", help="Print summary table only")
    args = parser.parse_args()

    # ── 1. Mock Blender modules ──────────────────────────────────────────────
    for mod in ["bpy", "mathutils", "bmesh", "bpy.types", "bpy.props"]:
        sys.modules[mod] = MagicMock()

    # ── 2. Add project root to path ─────────────────────────────────────────
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    sys.path.insert(0, project_root)

    # ── 3. Import dispatcher ────────────────────────────────────────────────
    try:
        import blender_mcp.handlers  # noqa: F401 — triggers package init
        from blender_mcp.dispatcher import HANDLER_METADATA
    except ImportError as e:
        print(f"ERROR: Could not import blender_mcp: {e}")
        sys.exit(1)

    # ── 4. Load all handler modules (registers @register_handler decorators) ─
    import blender_mcp.handlers as _handlers_pkg

    failed = []
    for _, name, _ in pkgutil.iter_modules(_handlers_pkg.__path__):
        try:
            importlib.import_module(f"blender_mcp.handlers.{name}")
        except Exception as exc:
            failed.append((name, str(exc)))

    # ── 5. Build sorted tool list ────────────────────────────────────────────
    all_tools = sorted(
        HANDLER_METADATA.values(),
        key=lambda t: (int(t.get("priority", 100)), t.get("category", "general"), t["name"]),
    )

    # ── 6. Apply filters ─────────────────────────────────────────────────────
    if args.tool:
        all_tools = [t for t in all_tools if t["name"] == args.tool]
        if not all_tools:
            print(f"Tool '{args.tool}' not found.")
            sys.exit(1)

    if args.tier:
        tier_upper = args.tier.upper()
        all_tools = [
            t for t in all_tools if tier_info(int(t.get("priority", 100)))[0] == tier_upper
        ]

    if args.cat:
        cat_lower = args.cat.lower()
        all_tools = [
            t
            for t in all_tools
            if cat_lower in t.get("category", "").lower() or cat_lower in t["name"].lower()
        ]

    # ── 7. Counts ────────────────────────────────────────────────────────────
    total_tools = len(all_tools)
    total_actions = sum(len(t.get("actions", [])) for t in all_tools)

    # ── 8. Header ────────────────────────────────────────────────────────────
    print("=" * 90)
    print(" BLENDER MCP — TOOL & ACTION INVENTORY ".center(90, "="))
    print("=" * 90)
    print(f"  Registered tools : {total_tools}")
    print(f"  Total actions    : {total_actions}")
    tier_counts = {}
    for t in HANDLER_METADATA.values():
        tname, _ = tier_info(int(t.get("priority", 100)))
        tier_counts[tname] = tier_counts.get(tname, 0) + 1
    for _, _, tname, icon in TIERS:
        print(f"  {icon} {tname:<12}: {tier_counts.get(tname, 0)}")
    if failed:
        print(f"  ⚠  Skipped (mock failures): {len(failed)}")
    print("=" * 90)

    # ── 9. Summary table mode ────────────────────────────────────────────────
    if args.summary:
        print(f"\n{'#':<4} {'TIER':<12} {'PRI':<5} {'TOOL NAME':<38} {'CATEGORY':<14} {'ACTIONS'}")
        print("-" * 90)
        for i, t in enumerate(all_tools, 1):
            pri = int(t.get("priority", 100))
            tname, icon = tier_info(pri)
            actions = t.get("actions", [])
            action_str = ", ".join(actions[:4])
            if len(actions) > 4:
                action_str += f" +{len(actions) - 4}"
            print(
                f"{i:<4} {icon + ' ' + tname:<12} {pri:<5} {t['name']:<38} {t.get('category', 'general'):<14} {action_str}"
            )
        print("-" * 90)
        print(f"\nTotal: {total_tools} tools, {total_actions} actions")
        return

    # ── 10. Full tree output ─────────────────────────────────────────────────
    current_tier = None
    for t in all_tools:
        pri = int(t.get("priority", 100))
        tname, icon = tier_info(pri)
        actions = t.get("actions", [])
        schema = t.get("schema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        title = schema.get("title", t["name"])
        raw_desc = t.get("description") or schema.get("description", "")

        # Tier section header
        if tname != current_tier:
            current_tier = tname
            print(f"\n{'━' * 90}")
            print(
                f"  {icon}  {tname} TIER  (priority {
                    {
                        'ESSENTIAL': '1-9',
                        'CORE': '10-49',
                        'STANDARD': '50-149',
                        'OPTIONAL': '150+',
                    }.get(tname, '?')
                })"
            )
            print(f"{'━' * 90}")

        # Tool header
        print(f"\n  [{pri:>3}] {icon} {t['name']}")
        print(f"        Title    : {title}")
        print(f"        Category : {t.get('category', 'general')}")

        # Description (full, wrapped)
        if raw_desc:
            desc_lines = format_description(raw_desc, indent="       ", width=80)
            print("        Description:")
            for line in desc_lines:
                print(line)

        # Actions
        if actions:
            if len(actions) <= 8:
                print(f"        Actions  : {', '.join(actions)}")
            else:
                chunks = [actions[i : i + 6] for i in range(0, len(actions), 6)]
                print(f"        Actions  : {', '.join(chunks[0])}")
                for chunk in chunks[1:]:
                    print(f"                   {', '.join(chunk)}")

        # Parameters
        if not args.no_params and properties:
            print(f"        Parameters ({len(properties)}):")
            prop_items = list(properties.items())
            for i, (prop_name, prop_details) in enumerate(prop_items):
                is_last = i == len(prop_items) - 1
                branch = "└──" if is_last else "├──"
                req = "[REQ] " if prop_name in required else "      "
                ptype = prop_details.get("type", "any")
                pdesc = prop_details.get("description", "")
                enum_vals = prop_details.get("enum", [])
                default = prop_details.get("default")

                line = f"          {branch} {req}{prop_name} ({ptype})"
                if default is not None:
                    line += f"  [default={default!r}]"
                if enum_vals:
                    shown = enum_vals[:6]
                    line += f"  → {shown}{'...' if len(enum_vals) > 6 else ''}"
                if pdesc:
                    line += f"  — {pdesc[:80]}"
                print(line)

    print("\n" + "=" * 90)
    if failed:
        print(f"\n⚠  {len(failed)} handler(s) skipped (could not load without full Blender env):")
        for name, err in failed:
            print(f"   • {name}: {err[:100]}")
    print()


if __name__ == "__main__":
    main()
