#!/usr/bin/env python3
"""
Validate manage_tool_groups workflow integrity.

Checks:
- Every referenced handler exists in dispatcher metadata.
- Every typical action is valid for its target handler.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def _is_optional_handler(handler_name: str) -> bool:
    """External provider integrations are optional in local quality runs."""
    return handler_name.startswith("integration_")


def main() -> int:
    _bootstrap_path()

    from blender_mcp.dispatcher import HANDLER_METADATA, load_handlers
    from blender_mcp.handlers.manage_tool_groups import TOOL_GROUPS

    load_handlers()

    errors: list[str] = []
    warnings: list[str] = []

    for group_name, group_data in TOOL_GROUPS.items():
        required_group_keys = {"name", "description", "handlers", "typical_actions"}
        missing_keys = sorted(required_group_keys - set(group_data.keys()))
        if missing_keys:
            errors.append(f"{group_name}: missing required keys: {', '.join(missing_keys)}")
            continue

        handlers = group_data.get("handlers", [])
        if not isinstance(handlers, list):
            errors.append(f"{group_name}: 'handlers' must be a list")
            continue

        for handler_name in handlers:
            if handler_name not in HANDLER_METADATA:
                msg = f"{group_name}: handler '{handler_name}' is not registered"
                if _is_optional_handler(handler_name):
                    warnings.append(msg)
                else:
                    errors.append(msg)

        typical_actions = group_data.get("typical_actions", [])
        if not isinstance(typical_actions, list):
            errors.append(f"{group_name}: 'typical_actions' must be a list")
            continue

        for idx, item in enumerate(typical_actions):
            if not isinstance(item, dict):
                errors.append(f"{group_name}: typical_actions[{idx}] must be an object")
                continue

            handler_name = item.get("handler")
            action_name = item.get("action")
            if not handler_name or not action_name:
                errors.append(
                    f"{group_name}: typical_actions[{idx}] requires 'handler' and 'action'"
                )
                continue

            metadata = HANDLER_METADATA.get(handler_name)
            if metadata is None:
                msg = f"{group_name}: typical action references unknown handler '{handler_name}'"
                if _is_optional_handler(handler_name):
                    warnings.append(msg)
                else:
                    errors.append(msg)
                continue

            valid_actions = metadata.get("actions", [])
            if valid_actions and action_name not in valid_actions:
                errors.append(f"{group_name}: invalid action '{action_name}' for '{handler_name}'")

            if handler_name not in handlers:
                warnings.append(
                    f"{group_name}: typical action handler '{handler_name}' is not listed in 'handlers'"
                )

    if warnings:
        print("[WARN] Tool group warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("[FAIL] Tool group integrity check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"[OK] Tool groups validated successfully ({len(TOOL_GROUPS)} groups, {len(HANDLER_METADATA)} handlers)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
