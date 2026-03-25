"""
Custom Quality Checks for Blender MCP

Each check addresses specific issues from our Transformation Journey.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Set
from abc import ABC, abstractmethod

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class QualityCheck(ABC):
    """Base class for all quality checks."""

    @abstractmethod
    def run(self, fix: bool = False, ci: bool = False) -> Tuple[bool, List[str]]:
        """
        Run the check.

        Returns:
            (passed, messages)
        """
        pass


class VersionConsistencyCheck(QualityCheck):
    """
    Check #1: Version Consistency Across All Files

    Addresses: Issue #1 - Version synchronization problems
    """

    def run(self, fix: bool = False, ci: bool = False) -> Tuple[bool, List[str]]:
        messages = []

        # Import version from source of truth
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from blender_mcp.__version__ import VERSION

            source_version = VERSION
        except Exception as e:
            return False, [f"Cannot read source version: {e}"]

        # Files to check with their patterns
        checks = [
            ("pyproject.toml", r'^version = "([\d.]+)"', "toml"),
            ("uv.lock", r'name = "blender-mcp"\nversion = "([\d.]+)"', "lock"),
            ("blender_mcp/__init__.py", r'"version": \((\d+, \d+, \d+)\)', "tuple"),
            ("blender_mcp/dispatcher.py", r'"version": "([\d.]+)"', "string"),
            ("stdio_bridge.py", r"MCP BRIDGE STARTED \(V([\d.]+)", "log"),
        ]

        all_match = True

        for filename, pattern, pattern_type in checks:
            filepath = PROJECT_ROOT / filename
            if not filepath.exists():
                messages.append(f"[WARN] {filename}: File not found")
                all_match = False
                continue

            content = filepath.read_text(encoding="utf-8")
            match = re.search(pattern, content, re.MULTILINE)

            if not match:
                messages.append(f"❌ {filename}: Version pattern not found")
                all_match = False
                continue

            found = match.group(1)
            if pattern_type == "tuple":
                found = found.replace(", ", ".")

            if found == source_version:
                messages.append(f"[OK] {filename}: {found}")
            else:
                messages.append(f"[FAIL] {filename}: {found} (expected {source_version})")
                all_match = False

        return all_match, messages


class HandlerRegistrationCheck(QualityCheck):
    """
    Check #2, #3, #4: Handler Registration Integrity

    Addresses:
    - Issue #3: Module registration conflicts
    - Issue #4: Tool name collisions
    - Issue #8: Handler completeness
    """

    def run(self, fix: bool = False, ci: bool = False) -> Tuple[bool, List[str]]:
        messages = []
        handlers_dir = PROJECT_ROOT / "blender_mcp" / "handlers"

        if not handlers_dir.exists():
            return False, ["Handlers directory not found"]

        # Find all handler files
        handler_files = list(handlers_dir.glob("*.py"))

        registrations: Dict[str, List[str]] = {}  # name -> [files]
        issues = []

        for filepath in handler_files:
            if filepath.name.startswith("_"):
                continue

            content = filepath.read_text(encoding="utf-8")

            # Find @register_handler decorators
            # Pattern: @register_handler("name", ...)
            pattern = r'@register_handler\(\s*["\']([^"\']+)["\']'
            matches = re.finditer(pattern, content)

            for match in matches:
                handler_name = match.group(1)

                if handler_name not in registrations:
                    registrations[handler_name] = []
                registrations[handler_name].append(filepath.name)

        # Check for duplicates
        duplicates = {k: v for k, v in registrations.items() if len(v) > 1}

        if duplicates:
            issues.append(f"Found {len(duplicates)} duplicate registrations:")
            for name, files in duplicates.items():
                issues.append(f"  - '{name}' in: {', '.join(files)}")

        # Check naming conventions
        naming_issues = []
        reserved_names = {"list_all_tools", "get_server_status", "execute_blender_code"}

        for name in registrations.keys():
            # Check for reserved names being overridden
            if name in reserved_names:
                continue  # These are allowed to be in __init__.py

            # Check prefix for manage_* handlers
            if name.startswith("manage_"):
                continue  # Good
            elif name.startswith("integration_"):
                continue  # Good
            elif name.startswith("unity_"):
                continue  # Good
            elif name in reserved_names:
                continue  # Core handlers
            else:
                naming_issues.append(f"  - '{name}' doesn't follow naming convention")

        if naming_issues and ci:
            issues.extend(naming_issues)

        # Report results
        messages.append(f"Found {len(registrations)} handler registrations")

        if duplicates:
            messages.append(f"[FAIL] {len(duplicates)} duplicates detected!")
            return False, messages + issues

        if naming_issues:
            messages.append(f"[WARN] {len(naming_issues)} naming convention warnings")

        messages.append("[OK] All handler registrations are unique")
        return True, messages


class SchemaValidationCheck(QualityCheck):
    """
    Check #2: Schema-Implementation Alignment

    Addresses: Issue #2 - Action-schema mismatches
    """

    def run(self, fix: bool = False, ci: bool = False) -> Tuple[bool, List[str]]:
        messages = []
        handlers_dir = PROJECT_ROOT / "blender_mcp" / "handlers"

        mismatches = []

        for filepath in handlers_dir.glob("*.py"):
            if filepath.name.startswith("_"):
                continue

            content = filepath.read_text(encoding="utf-8")

            # Extract schema actions
            schema_pattern = r'"enum":\s*\[(.*?)\]'
            schema_matches = re.findall(schema_pattern, content, re.DOTALL)

            schema_actions: Set[str] = set()
            for match in schema_matches:
                # Extract quoted strings from enum
                actions = re.findall(r'"([^"]+)"', match)
                schema_actions.update(actions)

            # Extract implementation actions (if action == "...")
            impl_pattern = r'if\s+action\s*==\s*["\']([^"\']+)["\']'
            impl_actions = set(re.findall(impl_pattern, content))

            # Check for mismatches
            if schema_actions and impl_actions:
                in_schema_not_impl = schema_actions - impl_actions
                in_impl_not_schema = impl_actions - schema_actions

                if in_schema_not_impl or in_impl_not_schema:
                    mismatches.append(
                        {
                            "file": filepath.name,
                            "schema_only": in_schema_not_impl,
                            "impl_only": in_impl_not_schema,
                        }
                    )

        if mismatches:
            messages.append(f"[FAIL] Found {len(mismatches)} files with schema mismatches:")
            for m in mismatches:
                messages.append(f"  - {m['file']}")
                if m["schema_only"]:
                    messages.append(f"    In schema only: {m['schema_only']}")
                if m["impl_only"]:
                    messages.append(f"    In implementation only: {m['impl_only']}")
            return False, messages

        messages.append("[OK] All schema-implementation alignments verified")
        return True, messages


class ForbiddenPatternCheck(QualityCheck):
    """
    Check #11, #6, #16: Forbidden Code Patterns

    Addresses:
    - Issue #11: SimpleNamespace bug
    - Issue #6: Blender 5.x API compatibility
    - Issue #16: Registry protection
    """

    FORBIDDEN_PATTERNS = [
        (r"bpy\.types\.SimpleNamespace", "Use types.SimpleNamespace instead (Issue #11 fix)"),
        (
            r"bpy\.ops\.export_scene\.obj",
            "Use bpy.ops.wm.obj_export for Blender 5.x (Issue #6 fix)",
        ),
        (
            r"sequence_editor\.sequences\b(?!_all|_new)",
            "Use sequences_all for Blender 5.x (Issue #20 fix)",
        ),
        (
            r"print\s*\([^)]*\)(?!\s*#\s*OK)",
            "Use logging instead of print (add # OK comment if intentional)",
        ),
        (r"^\s*print\s*\(", "Use logging instead of print"),
    ]

    def run(self, fix: bool = False, ci: bool = False) -> Tuple[bool, List[str]]:
        messages = []
        violations = []

        # Check Python files
        for pyfile in PROJECT_ROOT.rglob("*.py"):
            # Skip certain directories
            if any(skip in str(pyfile) for skip in [".venv", "venv", "__pycache__", ".git"]):
                continue

            content = pyfile.read_text(encoding="utf-8")
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                for pattern, reason in self.FORBIDDEN_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Skip comments and strings
                        stripped = line.strip()
                        if (
                            stripped.startswith("#")
                            or stripped.startswith('"""')
                            or stripped.startswith("'''")
                        ):
                            continue

                        relative_path = pyfile.relative_to(PROJECT_ROOT)
                        violations.append(
                            {
                                "file": str(relative_path),
                                "line": line_num,
                                "pattern": pattern,
                                "reason": reason,
                            }
                        )

        if violations:
            messages.append(f"[FAIL] Found {len(violations)} forbidden patterns:")

            # Group by file
            by_file: Dict[str, List[dict]] = {}
            for v in violations:
                if v["file"]:
                    by_file.setdefault(str(v["file"]), []).append(v)

            for filename, file_violations in by_file.items():
                messages.append(f"  - {filename}:")
                for v in file_violations:
                    messages.append(f"      Line {v['line']}: {v['reason']}")

            return False, messages

        messages.append("[OK] No forbidden patterns found")
        return True, messages


class DocumentationCheck(QualityCheck):
    """
    Check #10, #12: Documentation Completeness

    Addresses:
    - Issue #10: Documentation gaps
    - Issue #12: MD file currency
    """

    REQUIRED_DOCS = [
        "README.md",
        "blender_docs/ARCHITECTURE.md",
        "blender_docs/DEVELOPER.md",
        "blender_docs/TOOLS_ACTIONS.md",
        "blender_docs/HISTORY.md",
        "blender_docs/VERSION_SYSTEM.md",
        "blender_docs/BLENDER_INTEGRATION.md",
        "blender_docs/TESTING.md",
        "blender_docs/TRANSFORMATION_JOURNEY.md",
    ]

    def run(self, fix: bool = False, ci: bool = False) -> Tuple[bool, List[str]]:
        messages = []
        missing = []
        outdated = []

        for doc_path in self.REQUIRED_DOCS:
            full_path = PROJECT_ROOT / doc_path
            if not full_path.exists():
                missing.append(doc_path)
            else:
                # Check if file mentions current version
                content = full_path.read_text(encoding="utf-8")

                # Get current version
                try:
                    sys.path.insert(0, str(PROJECT_ROOT))
                    from blender_mcp.__version__ import VERSION

                    if VERSION not in content and doc_path not in ["README.md"]:
                        # README might not need version in content
                        outdated.append(f"{doc_path} (doesn't mention v{VERSION})")
                except:
                    pass

        if missing:
            messages.append(f"[FAIL] Missing {len(missing)} required documentation files:")
            for m in missing:
                messages.append(f"  - {m}")

        if outdated:
            messages.append(f"[WARN] {len(outdated)} docs may be outdated:")
            for o in outdated:
                messages.append(f"  - {o}")

        if not missing and not outdated:
            messages.append("[OK] All required documentation present and current")
            return True, messages

        return len(missing) == 0, messages


class ImportOrganizationCheck(QualityCheck):
    """
    Check import organization and circular dependencies.
    """

    def run(self, fix: bool = False, ci: bool = False) -> Tuple[bool, List[str]]:
        messages = []
        issues = []

        # Check for circular imports would require AST analysis
        # For now, just check import ordering in files

        handlers_dir = PROJECT_ROOT / "blender_mcp" / "handlers"

        for pyfile in handlers_dir.glob("*.py"):
            if pyfile.name.startswith("_"):
                continue

            content = pyfile.read_text(encoding="utf-8")
            lines = content.split("\n")

            imports = []
            for line_num, line in enumerate(lines, 1):
                if line.startswith("import ") or line.startswith("from "):
                    imports.append((line_num, line.strip()))

            # Check for relative import pattern (should use absolute)
            for line_num, line in imports:
                if line.startswith("from .") and ".." in line:
                    issues.append(
                        f"{pyfile.name}:{line_num} - Avoid parent relative imports: {line}"
                    )

        if issues:
            messages.append(f"[WARN] Found {len(issues)} import organization issues:")
            for issue in issues[:10]:  # Limit output
                messages.append(f"  - {issue}")
            if len(issues) > 10:
                messages.append(f"  ... and {len(issues) - 10} more")

            return not ci, messages  # Warning only in standard mode

        messages.append("[OK] Import organization looks good")
        return True, messages


class BlenderCompatibilityCheck(QualityCheck):
    """
    Check #6, #7: Blender 5.x Compatibility

    Addresses:
    - Issue #6: API compatibility
    - Issue #7: Primitive operator parameters
    """

    BLENDER_5X_CHANGES = [
        (r"bpy\.ops\.export_scene\.obj\(", "Use wm.obj_export for Blender 5.x"),
        (r"bpy\.ops\.import_scene\.obj\(", "Use wm.obj_import for Blender 5.x"),
        (
            r"primitive_torus_add.*scale\s*=",
            "Torus doesn't accept scale in 5.x, set after creation",
        ),
    ]

    def run(self, fix: bool = False, ci: bool = False) -> Tuple[bool, List[str]]:
        messages = []
        issues = []

        handlers_dir = PROJECT_ROOT / "blender_mcp" / "handlers"

        for pyfile in handlers_dir.glob("*.py"):
            if pyfile.name.startswith("_"):
                continue

            content = pyfile.read_text(encoding="utf-8")

            for pattern, reason in self.BLENDER_5X_CHANGES:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Check if there's a fallback comment
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line_end = content.find("\n", match.end())
                    line = content[line_start:line_end]

                    if "# Fallback" not in line and "# Blender 4.x" not in line:
                        issues.append(
                            {
                                "file": pyfile.name,
                                "line": content[: match.start()].count("\n") + 1,
                                "reason": reason,
                            }
                        )

        if issues:
            messages.append(
                f"[WARN] Found {len(issues)} potential Blender 5.x compatibility issues:"
            )
            for issue in issues:
                messages.append(f"  - {issue['file']}:{issue['line']} - {issue['reason']}")

            return not ci, messages  # Warning in standard mode

        messages.append("[OK] Blender 5.x compatibility verified")
        return True, messages
