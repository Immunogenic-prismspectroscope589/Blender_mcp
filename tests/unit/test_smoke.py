"""Minimal smoke tests for CI and local tooling sanity checks."""

import re
from pathlib import Path


def test_project_has_core_entrypoints() -> None:
    assert Path("blender_mcp/__init__.py").exists()
    assert Path("blender_mcp/dispatcher.py").exists()


def test_project_has_handlers_package() -> None:
    assert Path("blender_mcp/handlers").is_dir()


def test_handler_count_minimum() -> None:
    """At least 50 handler files must exist in the handlers package."""
    handlers_dir = Path("blender_mcp/handlers")
    handler_files = [
        f
        for f in handlers_dir.glob("*.py")
        if not f.name.startswith("__") and f.name != "base_handler.py"
    ]
    assert len(handler_files) >= 50, (
        f"Expected at least 50 handler files, found {len(handler_files)}: "
        + ", ".join(f.name for f in handler_files)
    )


def test_essential_tools_declared() -> None:
    """dispatcher.py must declare at least 9 tools with priority <= 9 (ESSENTIAL tier)."""
    dispatcher_text = Path("blender_mcp/dispatcher.py").read_text(encoding="utf-8")
    # Count occurrences of priority=<1-9> in register_handler calls
    matches = re.findall(r"priority\s*=\s*([1-9])\b", dispatcher_text)
    # Also check handler files
    handlers_dir = Path("blender_mcp/handlers")
    for f in handlers_dir.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        matches += re.findall(r"priority\s*=\s*([1-9])\b", text)
    assert len(matches) >= 9, (
        f"Expected at least 9 ESSENTIAL-tier handlers (priority 1-9), found {len(matches)}"
    )


def test_live20_handler_files_exist() -> None:
    """Handler files added in live-20 must exist."""
    assert Path("blender_mcp/handlers/manage_history.py").exists(), (
        "manage_history.py (live-20) not found"
    )


def test_live24_handler_files_exist() -> None:
    """get_local_transforms.py (live-24) must exist."""
    assert Path("blender_mcp/handlers/get_local_transforms.py").exists(), (
        "get_local_transforms.py (live-24) not found"
    )


def test_tests_md_exists() -> None:
    """tests/TESTS.md must exist."""
    assert Path("tests/TESTS.md").exists()


def test_integration_conftest_exists() -> None:
    """tests/integration/conftest.py must exist (live-25)."""
    assert Path("tests/integration/conftest.py").exists()


def test_version_consistency() -> None:
    """__version__.py and pyproject.toml must declare the same version string."""
    # Read pyproject.toml version
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    toml_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert toml_match, "Could not find version in pyproject.toml"
    toml_version = toml_match.group(1)

    # Read __version__.py version
    ver_text = Path("blender_mcp/__version__.py").read_text(encoding="utf-8")
    ver_match = re.search(r'^__version__\s*=\s*"([^"]+)"', ver_text, re.MULTILINE)
    assert ver_match, "Could not find __version__ in blender_mcp/__version__.py"
    pkg_version = ver_match.group(1)

    assert toml_version == pkg_version, (
        f"Version mismatch: pyproject.toml={toml_version!r}, __version__.py={pkg_version!r}"
    )
