#!/usr/bin/env python3
"""
JSON Schema Validator for Handlers (Runtime Import Version)
Validates that handler schemas are valid and complete by actually importing the code.

Implementation:
- Mocks 'bpy' and 'mathutils' to allow import outside Blender.
- Uses `blender_mcp.dispatcher` to load all handlers.
- Validates the ACTUAL evaluated schemas in `HANDLER_METADATA`.
- Catches runtime errors during schema definition (e.g. broken Enum references).
"""

import sys
import unittest.mock
from pathlib import Path
from typing import Dict, Any, List

# --- 1. Environment Setup & Mocking ---

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mock Blender modules BEFORE importing project code
# This allows us to import handlers causing 'import bpy' without crashing
sys.modules["bpy"] = unittest.mock.MagicMock()
sys.modules["bpy.types"] = unittest.mock.MagicMock()
sys.modules["bpy.props"] = unittest.mock.MagicMock()
sys.modules["mathutils"] = unittest.mock.MagicMock()
sys.modules["gpu"] = unittest.mock.MagicMock()
sys.modules["bmesh"] = unittest.mock.MagicMock()

# --- 2. Import Project Modules ---

try:
    from blender_mcp.dispatcher import load_handlers, HANDLER_METADATA
except ImportError as e:
    print(f"CRITICAL: Could not import blender_mcp.dispatcher: {e}")
    sys.exit(1)

# --- 3. Validation Logic ---

REQUIRED_SCHEMA_FIELDS = ["type", "properties"]


def validate_single_schema(name: str, schema: Dict[str, Any]) -> List[str]:
    """Validate a single JSON schema definition."""
    errors = []
    context = f"Handler '{name}'"

    # Check required fields
    for field in REQUIRED_SCHEMA_FIELDS:
        if field not in schema:
            errors.append(f"{context}: Missing required field '{field}'")
            return errors  # Stop if basic structure is wrong

    # Check type
    if schema.get("type") != "object":
        errors.append(f"{context}: Schema type should be 'object'")

    # Check properties
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        errors.append(f"{context}: 'properties' should be an object")
    else:
        # Validate 'action' property presence and structure
        if "action" not in properties:
            errors.append(f"{context}: Schema missing 'action' property")
        else:
            action_prop = properties["action"]
            if not isinstance(action_prop, dict):
                errors.append(f"{context}: 'action' property must be a dict")
            else:
                # Critical: Check if 'enum' is a LIST (not dynamic code)
                # Since we imported the code, list comprehensions should be evaluated now.
                enum_val = action_prop.get("enum")
                if enum_val is not None:
                    if not isinstance(enum_val, list):
                        errors.append(
                            f"{context}: action.enum is not a list (Got {type(enum_val)})"
                        )
                    elif not enum_val:
                        errors.append(f"{context}: action.enum is empty")
                    else:
                        # Check contents are strings
                        if not all(isinstance(x, str) for x in enum_val):
                            errors.append(f"{context}: action.enum contains non-string values")

    # Check for recursion or overflow causing issues (basic sanity)
    try:
        import json

        json.dumps(schema)
    except (TypeError, ValueError) as e:
        errors.append(f"{context}: Schema is not serializable to JSON: {e}")

    return errors


def main():
    print("--- Blender MCP Schema Validator (Runtime) ---")
    print(f"Project Root: {PROJECT_ROOT}")

    # Load handlers (this triggers @register_handler decorators)
    print("Loading handlers...")
    try:
        load_handlers()
    except Exception as e:
        print(f"ERROR: Failed to load handlers: {e}")
        # We continue to check whatever WAS loaded

    print(f"Loaded {len(HANDLER_METADATA)} handlers.")

    all_errors = []

    for name, metadata in HANDLER_METADATA.items():
        schema = metadata.get("schema")
        if not schema:
            all_errors.append(f"Handler '{name}' has no schema.")
            continue

        errors = validate_single_schema(name, schema)
        all_errors.extend(errors)

    if all_errors:
        print("\n[ERRORS]")
        for err in all_errors:
            print(f"  - {err}")
        print(f"\n[FAIL] Found {len(all_errors)} schema errors.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All schemas validated successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
