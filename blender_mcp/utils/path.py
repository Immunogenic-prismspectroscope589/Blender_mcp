import ctypes
import os
import platform
from typing import List


def get_safe_path(filepath):
    """
    Sanitize file path for Windows/Unicode issues.
    Uses Kernel32 GetShortPathNameW to bypass encoding issues in C-modules.
    Stops recursion at System Roots to avoid PermissionError.
    """
    filepath = os.path.normpath(filepath)
    directory = os.path.dirname(filepath)

    if platform.system() != "Windows":
        try:
            os.makedirs(directory, exist_ok=True)
            return filepath
        except Exception as e:
            print(f"[MCP] Error creating dir: {e}")
            return filepath

    # Windows Logic: Anchor-Based Approach
    try:
        # 1. Try standard creation first (Least Invasive)
        try:
            os.makedirs(directory, exist_ok=True)
            # If standard creation works and path exists, we can return.
            # However, if we strongly desire ShortPath for C-compat, check config.
            # For now, let's assume if it exists, it's fine, unless it contains non-ascii.
            if os.path.exists(directory):
                try:
                    directory.encode("ascii")
                    return filepath  # Pure ASCII path is always safe
                except:
                    pass  # Fallthrough to ShortPath logic for Unicode safety in C-libs
        except:
            pass

        # 2. Logic: Find the "Deepest Anchor" that actually exists.
        abs_dir = os.path.abspath(directory)

        if os.path.exists(abs_dir):
            return _get_short_path_windows(abs_dir, os.path.basename(filepath))

        # Walk up
        parts: List[str] = []
        curr = abs_dir
        valid_root = None

        while True:
            parent, part = os.path.split(curr)
            if not part:  # Drive root reached (e.g. C:\)
                if os.path.exists(parent):  # Verify drive exists/accessible
                    valid_root = parent
                    break  # Success: We anchor at Drive Root
                else:
                    break  # Failure: Drive doesn't exist

            parts.insert(0, part)
            if os.path.exists(parent):
                valid_root = parent
                break
            curr = parent

        if valid_root:
            short_root = _get_short_path_string(valid_root)
            if short_root:
                safe_dir = os.path.join(short_root, *parts)
                try:
                    os.makedirs(safe_dir, exist_ok=True)
                    return os.path.join(safe_dir, os.path.basename(filepath))
                except Exception as e:
                    print(f"[MCP] Failed to create safe dir {safe_dir}: {e}")
                    raise PermissionError(
                        f"Could not create directory '{safe_dir}'. System security prevents writing here. Please choose a User-writable path."
                    )

    except Exception as e:
        print(f"[MCP] SafePath logic failed: {e}")
        # Re-raise to prevent silent failures
        raise e

    return filepath


def _get_short_path_string(path):
    buf_size = 260
    buffer = ctypes.create_unicode_buffer(buf_size)
    get_short = ctypes.windll.kernel32.GetShortPathNameW
    res = get_short(path, buffer, buf_size)
    if res > 0:
        return buffer.value
    return path


def _get_short_path_windows(directory, filename):
    short_dir = _get_short_path_string(directory)
    return os.path.join(short_dir, filename)
