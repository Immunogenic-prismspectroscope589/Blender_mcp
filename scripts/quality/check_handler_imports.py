#!/usr/bin/env python3
"""
Handler Import Validator - Pre-commit hook
Detects wrong import patterns before they break the system.
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Forbidden import patterns (will fail the check)
FORBIDDEN_PATTERNS = [
    # (regex_pattern, error_message)
    (
        r"^from blender_mcp\.",
        "Use relative imports (from ..module) instead of absolute (from blender_mcp.module)",
    ),
    (r"^import blender_mcp", "Use relative imports instead of importing the whole package"),
]


def extract_imports(file_path: Path) -> Tuple[List[str], List[str]]:
    """Extract all imports from a Python file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [], [f"ERROR reading {file_path}: {e}"]

    imports = []
    errors = []

    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(a.name for a in node.names)
                level = "." * node.level
                imports.append(f"from {level}{module} import {names}")
    except SyntaxError as e:
        errors.append(f"SYNTAX ERROR in {file_path}: {e}")

    return imports, errors


def check_file(file_path: Path) -> Tuple[List[str], List[str], List[str]]:
    """
    Check a single file for import issues.
    Returns: (errors, warnings, info)
    """
    errors = []
    warnings: List[str] = []
    info: List[str] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"Cannot read {file_path}: {e}"], [], []

    # Check forbidden patterns (only at start of line - actual imports)
    for pattern, message in FORBIDDEN_PATTERNS:
        for line in content.split("\n"):
            if re.match(pattern, line.strip()):
                errors.append(f"{file_path}: {message}")
                break

    # High Mode: Only check critical import errors
    # Schema and decorator presence are runtime concerns, not static check concerns

    return errors, warnings, info


def main():
    """Main entry point for pre-commit hook."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate handler imports")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument("--all", action="store_true", help="Check all handler files")
    args = parser.parse_args()

    files_to_check = []

    if args.all:
        handlers_dir = Path("blender_mcp/handlers")
        if handlers_dir.exists():
            files_to_check = [
                f
                for f in handlers_dir.glob("*.py")
                if not f.name.startswith("_") and f.name != "base_handler.py"
            ]
        # Also check core modules
        core_dir = Path("blender_mcp/core")
        if core_dir.exists():
            files_to_check.extend([f for f in core_dir.glob("*.py") if not f.name.startswith("_")])
    else:
        files_to_check = [Path(f) for f in args.files if f.endswith(".py")]

    if not files_to_check:
        print("No Python files to check")
        sys.exit(0)

    all_errors = []
    all_warnings = []
    all_info = []

    for file_path in files_to_check:
        if not file_path.exists():
            continue

        errors, warnings, info = check_file(file_path)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        all_info.extend(info)

    # Report results
    if all_info:
        print("\n[INFO]")
        for msg in all_info[:10]:
            print(f"  [INFO] {msg}")
        if len(all_info) > 10:
            print(f"  ... and {len(all_info) - 10} more")

    if all_warnings:
        print("\n[WARNINGS]")
        for msg in all_warnings[:10]:
            print(f"  [WARN] {msg}")
        if len(all_warnings) > 10:
            print(f"  ... and {len(all_warnings) - 10} more")

    if all_errors:
        print("\n[ERRORS]")
        for msg in all_errors[:20]:
            print(f"  [ERROR] {msg}")
        if len(all_errors) > 20:
            print(f"  ... and {len(all_errors) - 20} more")
        print(f"\n[FAIL] {len(all_errors)} import error(s) found")
        sys.exit(1)

    print(f"[OK] All {len(files_to_check)} file(s) passed import validation")
    sys.exit(0)


if __name__ == "__main__":
    main()
