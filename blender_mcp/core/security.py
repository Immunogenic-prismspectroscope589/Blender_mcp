import bpy
from typing import cast, Any


class SecurityManager:
    """
    Enforces Security Policies (Safe Mode).
    """

    @staticmethod
    def is_safe_mode() -> bool:
        """
        Check if Safe Mode is enabled in Addon Preferences.
        """
        try:
            main_package = __package__.split(".")[0]
            if bpy.context.preferences and bpy.context.preferences.addons:
                if main_package in bpy.context.preferences.addons:
                    addon = bpy.context.preferences.addons[main_package]
                    return bool(cast(Any, addon).preferences.safe_mode)
            return True
        except (AttributeError, KeyError, IndexError):
            # Default to SAFE (True) if we can't determining
            return True

    @staticmethod
    def validate_action(tool_name: str, action_name: str) -> bool:
        """
        HIGH MODE ENABLED: All actions are permitted.
        """
        return True
