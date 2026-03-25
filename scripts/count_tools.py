"""
Tool Counter & Registry Auditor
-------------------------------
Scans the handlers directory for @register_handler decorators to verify
the exact number of available tools and aliases in the system.

Usage:
    python scripts/count_tools.py
"""

import os
import re

# Adjust path to find the source
SOURCE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDLERS_DIR = os.path.join(SOURCE_DIR, "blender_mcp", "handlers")


def count_tools():
    total_files = 0
    total_handlers = 0
    handler_names = []

    print(f"Scanning {HANDLERS_DIR}...")
    print("-" * 60)

    for root, dirs, files in os.walk(HANDLERS_DIR):
        for file in files:
            if file.endswith(".py") and file != "__init__.py" and file != "base_handler.py":
                total_files += 1
                filepath = os.path.join(root, file)

                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Find @register_handler("tool_name", ...)
                    matches = re.findall(r'@register_handler\s*\(\s*["\']([^"\']+)["\']', content)

                    if matches:
                        total_handlers += len(matches)
                        handler_names.extend(matches)
                    else:
                        # Some helper files might not have handlers, which is fine
                        pass

    # Also scan dispatcher.py for core tools (list_all_tools, get_server_status, validate_tool)
    dispatcher_path = os.path.join(SOURCE_DIR, "blender_mcp", "dispatcher.py")
    if os.path.exists(dispatcher_path):
        print(f"Scanning {dispatcher_path}...")
        with open(dispatcher_path, "r", encoding="utf-8") as f:
            content = f.read()
            matches = re.findall(r'@register_handler\s*\(\s*["\']([^"\']+)["\']', content)
            if matches:
                total_handlers += len(matches)
                handler_names.extend(matches)

    print("Results:")
    print(f"  Total Handler Files:   {total_files}")
    print(f"  Total Registered Tools: {total_handlers}")
    print("-" * 60)

    # Group by prefix for better readability
    grouped: dict[str, list[str]] = {}
    for name in handler_names:
        prefix = name.split("_")[0]
        if prefix not in grouped:
            grouped[prefix] = []
        grouped[prefix].append(name)

    for prefix in sorted(grouped.keys()):
        print(f"[{prefix.upper()}]")
        for name in sorted(grouped[prefix]):
            print(f"  - {name}")
        print()


if __name__ == "__main__":
    if os.path.exists(HANDLERS_DIR):
        count_tools()
    else:
        print(f"Error: Handlers directory not found at {HANDLERS_DIR}")
