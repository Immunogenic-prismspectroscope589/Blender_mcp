#!/usr/bin/env python3
"""
Blender MCP Quality Gate - Main Entry Point
Runs all quality checks in sequence.
"""

import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Tuple, Any


# Color codes for terminal output (Windows compatible)
class Colors:
    OK = "\033[92m" if sys.platform != "win32" else ""
    WARNING = "\033[93m" if sys.platform != "win32" else ""
    ERROR = "\033[91m" if sys.platform != "win32" else ""
    INFO = "\033[94m" if sys.platform != "win32" else ""
    BOLD = "\033[1m" if sys.platform != "win32" else ""
    END = "\033[0m" if sys.platform != "win32" else ""


RUNNER_PYTHON = "python"


def _ruff_base_cmd() -> List[str]:
    """Prefer ruff binary, fallback to module invocation."""
    if shutil.which("ruff"):
        return ["ruff"]
    return [sys.executable, "-m", "ruff"]


def _mypy_base_cmd() -> List[str]:
    """Prefer mypy binary, fallback to module invocation."""
    if shutil.which("mypy"):
        return ["mypy"]
    return [sys.executable, "-m", "mypy"]


def _pyright_base_cmd() -> List[str]:
    """Prefer pyright binary, fallback to module invocation."""
    if shutil.which("pyright"):
        return ["pyright"]
    return [sys.executable, "-m", "pyright"]


def _safe_console_text(text: str) -> str:
    """Normalize text to current console encoding to avoid Windows charmap crashes."""
    if not text:
        return text
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def run_command(cmd: List[str], description: str, **kwargs: Any) -> Tuple[int, str]:
    """Run a command and return exit code and output."""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.INFO}[RUN] {description}{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kwargs
        )

        if result.stdout:
            print(_safe_console_text(result.stdout))
        if result.stderr:
            print(_safe_console_text(result.stderr))

        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        print(f"{Colors.ERROR}Failed to run command: {_safe_console_text(str(e))}{Colors.END}")
        return 1, str(e)


def check_venv_health() -> bool:
    """Check virtual environment health."""
    print(f"\n{Colors.BOLD}Virtual Environment Check{Colors.END}")

    result = subprocess.run([RUNNER_PYTHON, "-m", "pip", "check"], capture_output=True, text=True)

    if result.returncode != 0:
        print(
            f"{Colors.WARNING}[WARN] pip check reported dependency warnings (non-blocking):{Colors.END}"
        )
        print(result.stdout)
        print(result.stderr)
        return True
    print(f"{Colors.OK}[OK] Virtual environment healthy{Colors.END}")
    return True


def main():
    """Run all quality checks."""
    import argparse

    parser = argparse.ArgumentParser(description="Blender MCP Quality Gate")
    parser.add_argument("--fast", action="store_true", help="Run only fast checks")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues where possible")
    args = parser.parse_args()

    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}  Blender MCP Quality Gate{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")

    results = []

    # 1. Virtual Environment Health
    if not check_venv_health():
        results.append(("venv", 1))
    else:
        results.append(("venv", 0))

    lint_targets = [p for p in ["blender_mcp", "tests", "scripts"] if Path(p).exists()]

    # 2. Ruff (Linting + Import sorting)
    if args.fix:
        code, _ = run_command(
            [*_ruff_base_cmd(), "check", "--fix", "--select", "E9,F63,F7,F82", *lint_targets],
            "Ruff Linting (with auto-fix)",
        )
    else:
        code, _ = run_command(
            [*_ruff_base_cmd(), "check", "--select", "E9,F63,F7,F82", *lint_targets], "Ruff Linting"
        )
    results.append(("ruff-lint", code))

    if not args.fast:
        # Ruff Format check
        code, _ = run_command(
            [*_ruff_base_cmd(), "format", "--check", *lint_targets], "Ruff Format Check"
        )
        results.append(("ruff-format", code))

    # 2.5 Import Architecture Check (Restored)
    code, _ = run_command(
        [RUNNER_PYTHON, "scripts/quality/lint_imports.py"], "Import Architecture Check"
    )
    results.append(("import-arch", code))

    # 3. Import Validation
    code, _ = run_command(
        [RUNNER_PYTHON, "scripts/quality/check_handler_imports.py", "--all"],
        "Handler Import Validation",
    )
    results.append(("imports", code))

    # 4. Handler Completeness
    code, _ = run_command(
        [RUNNER_PYTHON, "scripts/quality/check_handler_completeness.py"]
        + (["--strict"] if args.strict else []),
        "Handler Completeness Check",
    )
    results.append(("completeness", code))

    # 4.5 Tool Group Integrity
    code, _ = run_command(
        [RUNNER_PYTHON, "scripts/quality/check_tool_groups.py"], "Tool Group Integrity Check"
    )
    results.append(("tool-groups", code))

    # 5. Forbidden Patterns
    code, _ = run_command(
        [RUNNER_PYTHON, "scripts/quality/check_forbidden.py", "--all"], "Forbidden Pattern Scan"
    )
    results.append(("forbidden", code))

    # 6. Version Consistency
    code, _ = run_command(
        [RUNNER_PYTHON, "scripts/quality/check_version.py"], "Version Consistency"
    )
    results.append(("version", code))

    # Skip slow checks if --fast
    if not args.fast:
        # 7. MyPy Type Checking
        code, _ = run_command(
            [*_mypy_base_cmd(), "."],
            "MyPy Type Checking",
        )
        results.append(("mypy", code))

        # 8. Pyright Type Checking
        # Note: shell=True handles Windows wrappers (.cmd/.bat) well when called as array
        code, _ = run_command([*_pyright_base_cmd()], "Pyright Type Checking", shell=True)
        results.append(("pyright", code))

    if not args.fast:
        # 10. Schema Validation
        code, _ = run_command(
            [RUNNER_PYTHON, "scripts/quality/check_schemas.py", "--all"], "Schema Validation"
        )
        results.append(("schemas", code))

    # Summary
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}  Summary{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")

    failed = []
    passed = []

    for name, code in results:
        if code != 0:
            failed.append(name)
            print(f"  {Colors.ERROR}[FAIL] {name}{Colors.END}")
        else:
            passed.append(name)
            print(f"  {Colors.OK}[OK] {name}{Colors.END}")

    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")

    if failed:
        print(f"{Colors.ERROR}FAILED: {len(failed)}/{len(results)} checks{Colors.END}")
        print(f"Failed checks: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"{Colors.OK}PASSED: All {len(results)} checks passed!{Colors.END}")
        sys.exit(0)


if __name__ == "__main__":
    main()
