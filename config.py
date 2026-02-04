"""
Root config module: re-exports from core for backward compatibility and simple imports.
Use: from config import get_settings or from core.config import get_settings
"""

from core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
