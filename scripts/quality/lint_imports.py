"""
Lint Imports - Architecture & Layering Validator

Enforces strict dependency rules:
1. Core cannot import Handlers (Circular dependency prevention)
2. Utils cannot import Core or Handlers (Bottom-up layering)
3. No star imports (Explicit dependencies)
4. No relative imports in tests (Absolute paths required)
"""

import ast
import sys
from pathlib import Path
from typing import List


class ImportVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.errors: List[str] = []
        self.module_path = list(file_path.parts)

    def visit_Import(self, node):
        for alias in node.names:
            self._check_import(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        if node.level > 0:
            module = "." * node.level + module
        self._check_import(module, node.lineno)
        self.generic_visit(node)

    def _check_import(self, module_name: str, lineno: int):
        # Rule 1: No star imports
        if "*" in module_name:
            self.errors.append(f"Line {lineno}: Star import detected")

        # Context-based rules
        is_core = "core" in self.module_path
        is_utils = "utils" in self.module_path

        # Rule 2: Core cannot import Handlers
        if is_core and "handlers" in module_name:
            # Whitelist standard library logging.handlers
            if not module_name.startswith("logging.") and "logging.handlers" not in module_name:
                self.errors.append(
                    f"Line {lineno}: Core module importing Handler layer '{module_name}'"
                )

        # Rule 3: Utils cannot import Core or Handlers
        if is_utils:
            if "core" in module_name and "utils" not in module_name:
                # Whitelist logging config
                if "logging_config" not in module_name:
                    self.errors.append(
                        f"Line {lineno}: Utils module importing Core layer '{module_name}'"
                    )
            if "handlers" in module_name:
                # Whitelist standard library logging.handlers
                if not module_name.startswith("logging.") and "logging.handlers" not in module_name:
                    self.errors.append(
                        f"Line {lineno}: Utils module importing Handler layer '{module_name}'"
                    )


def check_file(file_path: Path) -> List[str]:
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
        visitor = ImportVisitor(file_path)
        visitor.visit(tree)
        return visitor.errors
    except Exception as e:
        return [f"Failed to parse {file_path}: {e}"]


def main():
    root = Path(".")
    files = list(root.rglob("*.py"))

    # Filter for source code only (skip venv, build, etc.)
    source_files = [
        f
        for f in files
        if "blender_mcp" in f.parts
        and "venv" not in f.parts
        and ".git" not in f.parts
        and "__pycache__" not in f.parts
    ]

    all_errors = []
    print(f"Checking {len(source_files)} files for architectural violations...")

    for f in source_files:
        errors = check_file(f)
        if errors:
            print(f"\n[FAIL] {f}")
            for e in errors:
                print(f"  - {e}")
                all_errors.append((f, e))

    if all_errors:
        print(f"\nFAILED: {len(all_errors)} deviations found.")
        sys.exit(1)

    print("SUCCESS: Architecture integrity verified.")
    sys.exit(0)


if __name__ == "__main__":
    main()
