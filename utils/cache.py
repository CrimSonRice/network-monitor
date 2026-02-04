"""
In-memory cache example. Production: use Redis or Memcached for multi-instance.
Async-friendly: get/set are async to match Redis API when you switch.
"""

import asyncio
import time
from typing import Any

from core.config import get_settings

_cache: dict[str, tuple[Any, float]] = {}
_lock = asyncio.Lock()


async def cache_get(key: str) -> Any | None:
    """Return value if key exists and not expired."""
    async with _lock:
        if key not in _cache:
            return None
        value, expires = _cache[key]
        if time.monotonic() > expires:
            del _cache[key]
            return None
        return value


async def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    """Set key with optional TTL. Use config default if ttl_seconds not provided."""
    ttl = ttl_seconds if ttl_seconds is not None else get_settings().CACHE_TTL_SECONDS
    async with _lock:
        _cache[key] = (value, time.monotonic() + ttl)


async def cache_delete(key: str) -> bool:
    """Remove key; return True if it existed."""
    async with _lock:
        if key in _cache:
            del _cache[key]
            return True
        return False
