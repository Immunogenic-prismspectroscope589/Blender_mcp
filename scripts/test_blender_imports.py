#!/usr/bin/env python3
"""
Blender Runtime Import Test
Validates that all handlers can be imported in actual Blender environment.

Usage:
    blender --background --python scripts/test_blender_imports.py

Or inside Blender:
    import sys
    sys.path.insert(0, 'C:/Tools/my_mcp/blender-mcp')
    exec(open('scripts/test_blender_imports.py').read())
"""

import sys
import traceback
from pathlib import Path


def test_imports():
    """Test all critical imports in Blender environment."""
    from typing import Dict, List, Any

    results: Dict[str, List[Any]] = {"passed": [], "failed": []}

    # 1. Core modules
    print("\n[1/3] Testing Core Modules...")
    core_modules = [
        "blender_mcp.core.error_handling",
        "blender_mcp.core.compatibility",
        "blender_mcp.core.resolver",
        "blender_mcp.core.context",
        "blender_mcp.core.reliability",
    ]

    for mod in core_modules:
        try:
            __import__(mod)
            results["passed"].append(mod)
            print(f"  [OK] {mod}")
        except Exception as e:
            results["failed"].append((mod, str(e)))
            print(f"  [FAIL] {mod}: {e}")

    # 2. Dispatcher
    print("\n[2/3] Testing Dispatcher...")
    try:
        from blender_mcp.dispatcher import HANDLER_REGISTRY, load_handlers

        initial_count = len(HANDLER_REGISTRY)
        load_handlers()
        final_count = len(HANDLER_REGISTRY)
        loaded = final_count - initial_count
        results["passed"].append(f"dispatcher (loaded {loaded} handlers)")
        print(f"  [OK] Dispatcher loaded {loaded} handlers")
    except Exception as e:
        results["failed"].append(("dispatcher", str(e)))
        print(f"  [FAIL] Dispatcher: {e}")
        traceback.print_exc()

    # 3. Critical handlers
    print("\n[3/3] Testing Critical Handlers...")
    critical_handlers = [
        "blender_mcp.handlers.manage_scene",
        "blender_mcp.handlers.manage_modeling",
        "blender_mcp.handlers.manage_sculpting",
        "blender_mcp.handlers.manage_materials",
        "blender_mcp.handlers.manage_physics",
        "blender_mcp.handlers.manage_camera",
    ]

    for handler in critical_handlers:
        try:
            __import__(handler)
            results["passed"].append(handler)
            print(f"  [OK] {handler}")
        except Exception as e:
            results["failed"].append((handler, str(e)))
            print(f"  [FAIL] {handler}: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Passed: {len(results['passed'])}")
    print(f"Failed: {len(results['failed'])}")

    if results["failed"]:
        print("\nFailed items:")
        for name, error in results["failed"]:
            print(f"  - {name}: {error}")
        return False
    else:
        print("\n[OK] All imports successful! Blender MCP ready.")
        return True


if __name__ == "__main__":
    # Check if running in Blender
    try:
        import bpy

        print("[INFO] Running inside Blender")
        IN_BLENDER = True
    except ImportError:
        print("[WARN] Not running in Blender - tests may fail")
        IN_BLENDER = False

    # Add project to path if needed
    script_dir = Path(__file__).parent.parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
        print(f"[INFO] Added {script_dir} to Python path")

    success = test_imports()

    # Exit with appropriate code for CI
    if not success:
        sys.exit(1)
