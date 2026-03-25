#!/usr/bin/env python3
"""
Version Consistency Checker
Ensures version is consistent across all files.
"""

import re
import sys
from pathlib import Path
from typing import Optional

# Files to check for version consistency
# Note: uv.lock tracks dependencies, not our version
# Note: create_release_zip.py imports from __version__.py
VERSION_FILES = [
    ("blender_mcp/__version__.py", r'__version__\s*=\s*["\']([^"\']+)["\']'),
    ("pyproject.toml", r'version\s*=\s*["\']([^"\']+)["\']'),
    ("blender_mcp/dispatcher.py", r'["\']version["\']\s*:\s*["\']([^"\']+)["\']'),
    ("blender_mcp/__init__.py", r"v(\d+\.\d+\.\d+)"),
]

# Optional version anchors that may be absent during doc refactors.
OPTIONAL_VERSION_FILES = [
    ("README.md", r"blender_mcp_v(\d+\.\d+\.\d+)\.zip"),
]


def extract_version(file_path: Path, pattern: str) -> Optional[str]:
    """Extract version from file using regex."""
    if not file_path.exists():
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    except Exception:
        pass

    return None


def main():
    """Main entry point."""
    print("[CHECK] Checking version consistency...")

    versions = {}
    errors = []

    for file_path, pattern in VERSION_FILES:
        path = Path(file_path)
        version = extract_version(path, pattern)

        if version is None:
            errors.append(f"Could not extract version from {file_path}")
        else:
            versions[file_path] = version
            print(f"  {file_path}: {version}")

    for file_path, pattern in OPTIONAL_VERSION_FILES:
        path = Path(file_path)
        version = extract_version(path, pattern)
        if version is not None:
            versions[file_path] = version
            print(f"  {file_path}: {version}")

    # Check consistency
    if len(set(versions.values())) > 1:
        errors.append("Version mismatch detected!")
        print("\n[ERRORS]")
        for file, version in versions.items():
            print(f"  {file}: {version}")

    if errors:
        print("\n[FAIL] Version consistency check failed:")
        for error in errors:
            print(f"  [ERROR] {error}")
        sys.exit(1)

    print(f"\n[OK] All files have consistent version: {list(versions.values())[0]}")
    sys.exit(0)


if __name__ == "__main__":
    main()
