#!/usr/bin/env python3
"""
Version Synchronization Script for Blender MCP

Synchronizes version information across all project files from a single source of truth.

Usage:
    python scripts/sync_version.py              # Sync current version
    python scripts/sync_version.py --bump patch # Bump patch version (1.0.0 -> 1.0.1)
    python scripts/sync_version.py --bump minor # Bump minor version (1.0.0 -> 1.1.0)
    python scripts/sync_version.py --bump major # Bump major version (1.0.0 -> 2.0.0)
    python scripts/sync_version.py --set 1.0.0 # Set specific version
"""

import argparse
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from blender_mcp.__version__ import VERSION, VERSION_TUPLE


def bump_version(current_tuple: tuple, bump_type: str) -> tuple:
    """Bump version according to semver rules."""
    major, minor, patch = current_tuple

    if bump_type == "major":
        return (major + 1, 0, 0)
    elif bump_type == "minor":
        return (major, minor + 1, 0)
    elif bump_type == "patch":
        return (major, minor, patch + 1)
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")


def parse_version(version_str: str) -> tuple:
    """Parse version string to tuple."""
    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError(f"Version must be in format X.Y.Z, got: {version_str}")
    return tuple(int(p) for p in parts)


def update_version_file(new_version_tuple: tuple):
    """Update the __version__.py file with new version."""
    version_file = Path(__file__).parent.parent / "blender_mcp" / "__version__.py"

    content = version_file.read_text(encoding="utf-8")

    # Replace VERSION_TUPLE line
    new_line = f"VERSION_TUPLE = {new_version_tuple}"
    content = re.sub(r"VERSION_TUPLE = \(\d+, \d+, \d+\)", new_line, content)

    version_file.write_text(content, encoding="utf-8")
    print(f"[OK] Updated {version_file}")


def sync_pyproject_toml(version: str):
    """Update pyproject.toml version."""
    file_path = Path(__file__).parent.parent / "pyproject.toml"
    content = file_path.read_text(encoding="utf-8")

    # Update version line
    new_content = re.sub(
        r'^version = "[\d.]+"', f'version = "{version}"', content, flags=re.MULTILINE
    )

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"[OK] Updated {file_path}")
    else:
        print(f"[SKIP] {file_path} already up to date")


def sync_init_py(version_tuple: tuple):
    """Update __init__.py bl_info version."""
    file_path = Path(__file__).parent.parent / "blender_mcp" / "__init__.py"
    content = file_path.read_text(encoding="utf-8")

    # Derive version string from tuple (avoids stale cached VERSION import)
    new_version_str = ".".join(str(p) for p in version_tuple)

    # Update bl_info version tuple
    new_tuple_str = f"({version_tuple[0]}, {version_tuple[1]}, {version_tuple[2]})"
    new_content = re.sub(r'"version": \(\d+, \d+, \d+\)', f'"version": {new_tuple_str}', content)

    # Update comment if exists
    new_content = re.sub(r"# High Mode v[\d.]+", f"# v{new_version_str}", new_content)

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"[OK] Updated {file_path}")
    else:
        print(f"[SKIP] {file_path} already up to date")


def sync_dispatcher_py(version: str):
    """Update dispatcher.py version."""
    file_path = Path(__file__).parent.parent / "blender_mcp" / "dispatcher.py"
    content = file_path.read_text(encoding="utf-8")

    # Update version string in get_server_status
    new_content = re.sub(r'"version": "[\d.]+"', f'"version": "{version}"', content)

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"[OK] Updated {file_path}")
    else:
        print(f"[SKIP] {file_path} already up to date")


def sync_uv_lock(version: str):
    """Update uv.lock version."""
    file_path = Path(__file__).parent.parent / "uv.lock"

    if not file_path.exists():
        print(f"[SKIP] {file_path} not found")
        return

    content = file_path.read_text(encoding="utf-8")

    # Update blender-mcp package version in uv.lock
    # Pattern: name = "blender-mcp" followed by version = "x.x.x"
    new_content = re.sub(
        r'(name = "blender-mcp"\nversion = ")([\d.]+)(")', f"\\g<1>{version}\\g<3>", content
    )

    if new_content != content:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"[OK] Updated {file_path}")
    else:
        print(f"[SKIP] {file_path} already up to date")


def sync_create_release_zip(version: str):
    """Update create_release_zip.py - now uses dynamic version from __version__."""
    file_path = Path(__file__).parent.parent / "create_release_zip.py"

    if not file_path.exists():
        print(f"[SKIP] {file_path} not found")
        return

    # File now imports version dynamically, no need to update
    # Just verify it imports correctly
    try:
        import importlib
        import create_release_zip

        importlib.reload(create_release_zip)
        print(f"[OK] {file_path} uses dynamic version: {create_release_zip.VERSION}")
    except Exception as e:
        print(f"[WARN] Could not verify {file_path}: {e}")


def verify_sync():
    """Verify all files are in sync."""
    print("\n" + "=" * 60)
    print("VERSION VERIFICATION")
    print("=" * 60)

    # Reload version after updates
    import importlib
    import blender_mcp.__version__

    importlib.reload(blender_mcp.__version__)
    current_version = blender_mcp.__version__.VERSION

    print(f"Source of Truth (blender_mcp/__version__.py): {current_version}")

    files_to_check = [
        ("pyproject.toml", r'version = "([\d.]+)"'),
        ("blender_mcp/__init__.py", r'"version": \((\d+, \d+, \d+)\)'),
        ("blender_mcp/dispatcher.py", r'"version": "([\d.]+)"'),
        ("blender_mcp/__init__.py", r"BLENDER SERVER LOADED \(V([\d.]+)"),
        ("stdio_bridge.py", r"MCP BRIDGE STARTED \(V([\d.]+)"),
        ("uv.lock", r'name = "blender-mcp"\nversion = "([\d.]+)"'),
    ]

    all_ok = True
    for filename, pattern in files_to_check:
        file_path = Path(__file__).parent.parent / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            match = re.search(pattern, content)
            if match:
                found_version = match.group(1).replace(", ", ".")
                status = "[OK]" if found_version == current_version else ["FAIL"]
                print(f"{status} {filename}: {found_version}")
                if found_version != current_version:
                    all_ok = False
            else:
                print(f"? {filename}: Version pattern not found")
                all_ok = False

    print("=" * 60)
    if all_ok:
        print("[OK] All files are synchronized!")
    else:
        print("[FAIL] Some files are out of sync. Run sync again.")
    print("=" * 60)

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Synchronize version across all project files")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], help="Bump version type")
    parser.add_argument("--set", metavar="VERSION", help="Set specific version (format: X.Y.Z)")
    parser.add_argument("--verify", action="store_true", help="Only verify current sync status")

    args = parser.parse_args()

    if args.verify:
        verify_sync()
        return

    # Determine target version
    if args.set:
        new_version_tuple = parse_version(args.set)
    elif args.bump:
        new_version_tuple = bump_version(VERSION_TUPLE, args.bump)
    else:
        new_version_tuple = VERSION_TUPLE

    new_version = ".".join(map(str, new_version_tuple))

    print("=" * 60)
    print("BLENDER MCP VERSION SYNC")
    print("=" * 60)
    print(f"Current: {VERSION}")
    print(f"Target:  {new_version}")
    print("=" * 60)

    if new_version_tuple == VERSION_TUPLE:
        print("No version change needed. Syncing current version...")
    else:
        print("Bumping version...")
        update_version_file(new_version_tuple)
        print()

    # Sync all files
    print("Synchronizing files...")
    print("-" * 60)
    sync_pyproject_toml(new_version)
    sync_uv_lock(new_version)
    sync_init_py(new_version_tuple)
    sync_dispatcher_py(new_version)
    sync_create_release_zip(new_version)

    # Verify
    print()
    verify_sync()

    print(f"\n[OK] Version sync complete: {new_version}")


if __name__ == "__main__":
    main()
