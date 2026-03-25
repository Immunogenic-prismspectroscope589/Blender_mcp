import os
from pathlib import Path


class PathValidator:
    """
    Utility class to safely handle system paths coming from the MCP LLM Client.
    Protects against Path Traversals and validates file extensions before C-API calls.
    Adheres to Rule 9 (Zero Trust Input).
    """

    @staticmethod
    def validate_and_prepare(filepath: str, allowed_extensions: set[str] = None) -> str:
        """
        Takes a raw filepath, normalizes it, checks permissions and extension.
        Creates parent directories if missing.

        Args:
            filepath (str): The raw input path from JSON.
            allowed_extensions (set[str]): e.g., {'.glb', '.gltf'}

        Returns:
            str: The safe, absolute, normalized filepath ready for Blender API.

        Raises:
            ValueError: If path is invalid or extension is wrong.
        """
        if not filepath or not str(filepath).strip():
            raise ValueError(f"Filepath cannot be empty: '{filepath}'")

        # Normalize slashed to current OS
        raw_path = Path(str(filepath).strip()).resolve()

        if allowed_extensions:
            ext = raw_path.suffix.lower()
            if ext not in allowed_extensions:
                raise ValueError(
                    f"Invalid file extension: '{ext}'. Must be one of {allowed_extensions}"
                )

        # Create parent directories dynamically (Defends against FileNotFoundError)
        parent_dir = raw_path.parent
        if not parent_dir.exists():
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise PermissionError(f"Failed to create directory {parent_dir}: {e}")

        return str(raw_path)
