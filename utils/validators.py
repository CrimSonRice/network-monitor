"""
Input validators and sanitization helpers.
Use with Pydantic validators and in services for defense in depth.
"""

import re
from typing import Any

from core.security import sanitize_string

HOSTNAME_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)
IPV4_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)


def validate_host(value: str) -> str:
    """Validate host (hostname or IPv4). Raises ValueError if invalid."""
    if not value or len(value) > 253:
        raise ValueError("Invalid host length")
    cleaned = sanitize_string(value, max_length=253)
    if not cleaned:
        raise ValueError("Invalid host characters")
    if IPV4_PATTERN.match(cleaned) or HOSTNAME_PATTERN.match(cleaned):
        return cleaned
    raise ValueError("Invalid host format")


def safe_int(value: Any, default: int = 0, min_val: int | None = None, max_val: int | None = None) -> int:
    """Parse int safely for query params; clamp to range."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if min_val is not None and n < min_val:
        return min_val
    if max_val is not None and n > max_val:
        return max_val
    return n
