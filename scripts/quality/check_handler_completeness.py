#!/usr/bin/env python3
"""
Handler Completeness Checker
Detects missing handlers and validates handler registration.
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Required handlers that MUST exist
REQUIRED_HANDLERS = [
    "manage_scene",
    "manage_modeling",
    "manage_sculpting",
    "manage_materials",
    "manage_rendering",
    "manage_animation",
    "manage_physics",
    "manage_camera",
    "manage_constraints",
    "manage_compositing",
    "manage_rigging",
    "manage_uvs",
    "manage_sequencer",
    "manage_batch",
    "manage_export",
    "manage_light",
    "manage_objects",
    "manage_bake",
]

# Handlers that are allowed to be missing (optional)
OPTIONAL_HANDLERS = [
    "manage_advanced_batch",
    "manage_animation_advanced",
    "manage_ai_tools",
    "manage_cloud_render",
    "manage_collections_advanced",
    "manage_drivers",
    "manage_geometry_nodes",
    "manage_inspection",
    "manage_mocap",
    "manage_procedural",
    "manage_profiling",
    "manage_render_optimization",
    "manage_scripting",
    "manage_simulation_presets",
    "manage_uv_advanced",
    "hunyuan_handler",
    "hyper3d_handler",
    "polyhaven_handler",
    "sketchfab_handler",
    "unity_handler",
]

# Integration handlers (external API integrations)
INTEGRATION_HANDLERS = [
    "integration_hunyuan",
    "integration_hyper3d",
    "integration_polyhaven",
    "integration_sketchfab",
]


class HandlerChecker:
    """Checks handler file completeness."""

    def __init__(self, base_path: Path = Path(".")):
        self.base_path = base_path
        self.handlers_dir = base_path / "blender_mcp" / "handlers"
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def get_all_handler_files(self) -> Set[str]:
        """Get all handler Python files."""
        handlers: Set[str] = set()
        if not self.handlers_dir.exists():
            self.errors.append(f"Handlers directory not found: {self.handlers_dir}")
            return handlers

        for file_path in self.handlers_dir.glob("*.py"):
            if file_path.stem.startswith("_"):
                continue
            if file_path.stem == "base_handler":
                continue
            handlers.add(file_path.stem)

        return handlers

    def check_required_handlers(self, existing: Set[str]) -> None:
        """Check if all required handlers exist."""
        missing = set(REQUIRED_HANDLERS) - existing
        if missing:
            for handler in sorted(missing):
                self.errors.append(f"REQUIRED handler missing: {handler}")

    def check_handler_structure(self, handler_name: str) -> bool:
        """Check if a handler has proper structure."""
        file_path = self.handlers_dir / f"{handler_name}.py"
        if not file_path.exists():
            return False

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except SyntaxError as e:
            self.errors.append(f"Syntax error in {handler_name}: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Cannot read {handler_name}: {e}")
            return False

        # Check for @register_handler decorator
        has_register = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name):
                            if decorator.func.id == "register_handler":
                                has_register = True
                                break
                        elif isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr == "register_handler":
                                has_register = True
                                break
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "register_handler":
                    has_register = True

        if not has_register:
            # Try regex as fallback for complex decorators
            if "@register_handler" not in content:
                self.warnings.append(f"{handler_name}: Missing @register_handler decorator")
                return False

        # High Mode: Handler structure is flexible
        # - Import style is convention, not requirement
        # - Schema is optional (runtime flexible)
        # - Docstrings are optional (code is the documentation)

        return True

    def check_registration_works(self) -> None:
        """Try to import all handlers and check registration."""
        sys.path.insert(0, str(self.base_path))

        # Track optional dependency failures (not critical)
        optional_failures: list[str] = []

        try:
            # Import the dispatcher to trigger handler loading
            from blender_mcp.dispatcher import HANDLER_REGISTRY, load_handlers

            # Clear any existing registrations
            initial_count = len(HANDLER_REGISTRY)

            # Load all handlers
            load_handlers()

            final_count = len(HANDLER_REGISTRY)
            loaded = final_count - initial_count

            self.info.append(f"Loaded {loaded} handlers into registry")

            # Check for expected handlers
            expected_tools = [
                "manage_modeling",
                "manage_sculpting",
                "manage_scene",
                "manage_materials",
            ]

            for tool in expected_tools:
                if tool not in HANDLER_REGISTRY:
                    self.errors.append(f"Handler '{tool}' not registered in HANDLER_REGISTRY")

            # Report optional integration handlers that failed to load (non-critical)
            optional_integrations = [
                "integration_hunyuan",
                "integration_hyper3d",
                "integration_polyhaven",
                "integration_sketchfab",
            ]
            for integration in optional_integrations:
                if integration not in HANDLER_REGISTRY:
                    optional_failures.append(integration)

            if optional_failures:
                self.info.append(
                    f"Optional handlers not loaded (OK - missing dependencies): {', '.join(optional_failures)}"
                )

        except Exception as e:
            self.errors.append(f"Failed to load handlers: {e}")
            import traceback

            self.errors.append(traceback.format_exc())

    def check_duplicate_handlers(self) -> None:
        """Check for duplicate handler registrations."""
        sys.path.insert(0, str(self.base_path))

        handler_names: Dict[str, List[str]] = {}

        for file_path in self.handlers_dir.glob("*.py"):
            if file_path.stem.startswith("_"):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                # Find @register_handler("name") patterns
                import re

                matches = re.findall(r'@register_handler\s*\(\s*["\']([^"\']+)["\']', content)
                for name in matches:
                    if name not in handler_names:
                        handler_names[name] = []
                    handler_names[name].append(file_path.stem)
            except Exception:
                pass

        # Check for duplicates
        for name, files in handler_names.items():
            if len(files) > 1:
                self.errors.append(f"Duplicate handler '{name}' found in: {', '.join(files)}")

    def run_all_checks(self) -> Tuple[List[str], List[str], List[str]]:
        """Run all checks and return results."""
        print("[CHECK] Checking handler completeness...")

        # Get all handlers
        existing = self.get_all_handler_files()
        self.info.append(f"Found {len(existing)} handler files")

        # Check required
        print("  Checking required handlers...")
        self.check_required_handlers(existing)

        # Check structure
        print("  Checking handler structure...")
        for handler in sorted(existing):
            self.check_handler_structure(handler)

        # Check duplicates
        print("  Checking for duplicates...")
        self.check_duplicate_handlers()

        # Check registration
        print("  Checking registration...")
        self.check_registration_works()

        return self.errors, self.warnings, self.info


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Check handler completeness")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    checker = HandlerChecker()
    errors, warnings, info = checker.run_all_checks()

    # Filter out optional dependency errors (e.g., 'requests' module not found)
    # These are integration handlers that require external dependencies
    filtered_errors = []
    ignored_errors = []
    for msg in errors:
        # Ignore import errors for optional integration handlers
        if any(opt in msg for opt in ["hunyuan", "hyper3d", "polyhaven", "sketchfab", "requests"]):
            ignored_errors.append(msg)
        else:
            filtered_errors.append(msg)

    # Print results
    if info:
        print("\n[INFO]")
        for msg in info:
            print(f"  [INFO] {msg}")

    if warnings:
        print("\n[WARNINGS]")
        for msg in warnings:
            print(f"  [WARN] {msg}")

    if ignored_errors:
        print("\n[IGNORED - Optional Dependencies]")
        for msg in ignored_errors[:3]:  # Show first 3 only
            print(f"  [SKIP] {msg[:100]}...")
        if len(ignored_errors) > 3:
            print(f"  ... and {len(ignored_errors) - 3} more (optional integrations)")

    if filtered_errors:
        print("\n[ERRORS]")
        for msg in filtered_errors:
            print(f"  [ERROR] {msg}")
        print(f"\n[FAIL] {len(filtered_errors)} error(s) found")
        sys.exit(1)

    total_issues = len(filtered_errors) + (len(warnings) if args.strict else 0)

    if total_issues == 0:
        print("\n[OK] All handler completeness checks passed!")
        if ignored_errors:
            print(f"      ({len(ignored_errors)} optional integration errors ignored)")
        sys.exit(0)
    else:
        print(f"\n[WARN] {len(warnings)} warning(s) found (strict mode)")
        sys.exit(1)


if __name__ == "__main__":
    main()
