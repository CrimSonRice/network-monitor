"""
Core package: configuration, security, and middleware.
Clean separation from API and business logic for testability and deployment flexibility.
"""

from core.config import get_settings

__all__ = ["get_settings"]
