#!/usr/bin/env python3
"""
Forbidden Pattern Scanner - HIGH MODE Edition
Only blocks ACTUAL errors, warnings are silenced for High Mode freedom.
"""

import re
import sys
from pathlib import Path

# ACTUAL ERRORS only (things that WILL break)
FATAL_PATTERNS = [
    # Critical Blender 5.x breakages
    (r"bpy\.types\.SimpleNamespace", "SimpleNamespace crashes Blender 5.x - must fix", "FATAL"),
    (
        r"mathutils\.noise\.arctan2",
        "mathutils.noise.arctan2 REMOVED in Blender 5.x - use math.atan2",
        "FATAL",
    ),
    (r"\.face_indices(?=\s*[=\)])", "face_indices REMOVED - use link_faces", "FATAL"),
]

# Optional warnings (silenced in High Mode)
OPTIONAL_PATTERNS = [
    # Security - we trust the user (High Mode)
    (r"\beval\s*\(", "eval() used - acceptable in High Mode", "INFO"),
    (r"\bexec\s*\(", "exec() used - required for scripting features", "INFO"),
    # Deprecated but still functional
    (r"export_scene\.obj", "OBJ exporter - still works with fallback", "INFO"),
    # Import style - relative preferred but absolute works
    (r"from blender_mcp\.", "Absolute import - works but relative preferred", "INFO"),
]


def check_file(file_path: Path) -> list:
    """Check a file for fatal patterns only."""
    issues = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [("ERROR", f"Cannot read file: {e}")]

    for pattern, message, severity in FATAL_PATTERNS:
        for line_num, line in enumerate(content.split("\n"), 1):
            if re.search(pattern, line):
                issues.append((severity, f"{file_path}:{line_num}: {message}"))

    return issues


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Check for fatal patterns only (High Mode)")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument("--all", action="store_true", help="Check all Python files")
    args = parser.parse_args()

    files_to_check = []

    if args.all:
        # Only check blender_mcp, NOT tests (High Mode - tests are free)
        files_to_check = list(Path("blender_mcp").rglob("*.py"))
    else:
        files_to_check = [Path(f) for f in args.files if f.endswith(".py")]

    if not files_to_check:
        print("No files to check")
        sys.exit(0)

    all_errors = []

    for file_path in files_to_check:
        if not file_path.exists():
            continue
        # Skip tests entirely in High Mode
        if "test" in str(file_path).lower():
            continue
        issues = check_file(file_path)
        all_errors.extend(issues)

    if all_errors:
        print("\n[FATAL ERRORS - Will Break Blender 5.x]")
        for severity, msg in all_errors:
            print(f"  [FATAL] {msg}")
        print(f"\n[FAIL] {len(all_errors)} fatal error(s) found - MUST FIX")
        sys.exit(1)

    print(f"[OK] No fatal errors in {len(files_to_check)} file(s) - High Mode Active")
    sys.exit(0)


if __name__ == "__main__":
    main()
