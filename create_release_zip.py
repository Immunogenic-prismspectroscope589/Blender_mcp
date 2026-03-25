"""
Release ZIP Creator for Blender MCP
Uses centralized version management from blender_mcp.__version__
"""

import os
import sys
import zipfile

# Add project root to path for version import
# Current File: create_release_zip.py (in root)
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import version safely
try:
    from blender_mcp.__version__ import VERSION
except ImportError:
    # Fallback if run in a way where relative imports fail
    VERSION = "0.0.0"


def create_release():
    # Configuration - Dynamic version from single source of truth
    SOURCE_DIR = project_root
    OUTPUT_ZIP = os.path.join(SOURCE_DIR, f"blender_mcp_v{VERSION}.zip")

    # What to Ignore (Folders) - Sync with .gitignore
    IGNORE_DIRS = {
        # Version Control
        ".git",
        ".github",
        # Virtual Environments
        ".venv",
        "venv",
        "env",
        "ENV",
        # Python Cache
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".importlinter_cache",
        ".import_linter_cache",
        # IDEs
        ".vscode",
        ".idea",
        # AI/Agent artifacts
        ".gemini",
        ".claude",
        ".cursor",
        "artifacts",
        ".agent",
        # Temp files
        "tmp",
        "temp",
        # Test outputs
        "htmlcov",
        ".coverage",
        "test_outputs",
        "test-results",
        "coverage.xml",
        # Documentation (separate)
        "blender_docs",
        "docs",
        "blender_python_reference_5_0",
        # Security/Quality reports
        "bandit-report.json",
        # The script itself (don't include the zipper in the zip)
        "scripts",  # We usually don't verify scripts folder in the release? Use caution.
        # Actually user likely wants the addon code (blender_mcp) and maybe README.
        # The previous script excluded 'scripts' and 'blender_docs'.
        "tests",
    }

    # Explicitly add specific folders to ignore if they are in root
    IGNORE_DIRS.add("scripts")
    # Note: 'blender_docs' is already in the set above.

    # What to Ignore (File Extensions or specific files)
    IGNORE_FILES = {
        ".DS_Store",
        "Thumbs.db",
        ".gitignore",
        ".gitattributes",
        ".env",
        ".env.local",
        "*.log",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".python-version",
        ".pre-commit-config.yaml",
        "create_release_zip.py",  # Exclude self
        "Makefile",
        "pyproject.toml",
        "pytest.ini",
        "README.md",  # Maybe include? usually good practice. Let's exclude for now if strictly addon.
        # Actually standard add-ons often include README. But let's stick to the previous list logic implicitly.
        # The previous list didn't exclude README explicitly but 'files' were filtered by extension mostly.
        # Let's add explicit strict exclusions to keep it clean.
        "LICENSE",  # Usually include?
        "stdio_bridge.py",  # This is needed for the client! Wait.
        # The ZIP is for "Install in Blender".
        # The "stdio_bridge.py" is run by the CLIENT.
        # So the zip should contain the "blender_mcp" folder (the addon).
        # Users install the zip in Blender.
        # They DO NOT install stdio_bridge.py in Blender.
    }

    # Files to explicitly exclude if found in root
    EXCLUDE_FILENAMES = {
        "create_release_zip.py",
        "stdio_bridge.py",  # Client side script, not addon side.
        "Makefile",
        "pytest.ini",
        "uv.lock",
        "package-lock.json",
        "yarn.lock",
        "requirements.txt",
        ".importlinter",  # import-linter config, not needed in release
        ".coverage",  # coverage data file (also in IGNORE_DIRS as dir, but handle as file too)
    }

    print(f"Blender MCP Release Creator v{VERSION}")
    print("=" * 60)
    print(f"Source: {SOURCE_DIR}")
    print(f"Output: {OUTPUT_ZIP}")
    print("=" * 60)

    file_count = 0
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(SOURCE_DIR):
            # 1. Prune ignored directories in-place so os.walk doesn't visit them
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                if file in IGNORE_FILES or file in EXCLUDE_FILENAMES:
                    continue
                if file.endswith(".pyc"):
                    continue
                # Skip zip files (including the one we are making)
                if file.endswith(".zip"):
                    continue

                # Check absolute path to ignore hidden/dot files if needed

                abs_path = os.path.join(root, file)
                # Create relative path for inside the zip
                rel_path = os.path.relpath(abs_path, SOURCE_DIR)

                # We primarily want 'blender_mcp' folder.
                # If the user installs the zip, Blender expects the top level to be the module OR the __init__.py.
                # Usually:
                # zip/
                #   blender_mcp/
                #     __init__.py
                # This works if we zip from root.

                zipf.write(abs_path, rel_path)
                file_count += 1
                try:
                    print(f"Packed: {rel_path}")
                except:
                    pass

    print(f"\n[SUCCESS] Created: {OUTPUT_ZIP}")
    print(f"Files packaged: {file_count}")
    print("Excluded folders:", ", ".join(sorted(IGNORE_DIRS)))
    print("=" * 60)


if __name__ == "__main__":
    create_release()
