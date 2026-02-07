"""
Network monitoring API: example async endpoints with validation and caching.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from core.config import SettingsDep
from core.dependencies import CurrentUserOptional
from core.security import sanitize_string
from services.monitor_service import MonitorService
from utils.cache import cache_get, cache_set
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/monitor", tags=["monitor"])


class HostCheckRequest(BaseModel):
    """Validated input for host check. Sanitization applied in service layer."""

    host: str = Field(..., min_length=1, max_length=253)
    timeout_seconds: float = Field(default=5.0, ge=0.5, le=30.0)

    model_config = {"extra": "forbid"}


class HostCheckResponse(BaseModel):
    """Response schema for host availability check."""

    host: str
    reachable: bool
    latency_ms: float | None = None
    message: str = ""

    model_config = {"extra": "forbid"}


@router.get("/status", response_model=dict[str, Any])
async def get_system_status(
    settings: SettingsDep,
    user: CurrentUserOptional = None,
) -> dict[str, Any]:
    """
    Example async endpoint: system status summary.
    Uses optional auth; response can vary by user if needed.
    """
    cache_key = "monitor:status"
    if settings.CACHE_ENABLED:
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached
    result = await MonitorService.get_system_status()
    if settings.CACHE_ENABLED:
        await cache_set(cache_key, result, ttl_seconds=settings.CACHE_TTL_SECONDS)
    return result


@router.post("/check", response_model=HostCheckResponse)
async def check_host(
    body: HostCheckRequest,
    settings: SettingsDep,
) -> HostCheckResponse:
    """
    Check host reachability. Input validated by Pydantic; host sanitized for logging/display.
    SQL injection safe: no raw SQL; if you add DB, use parameterized queries only.
    """
    host = sanitize_string(body.host, max_length=253)
    if not host:
        host = body.host[:253]
    result = await MonitorService.check_host_async(host, body.timeout_seconds)
    return HostCheckResponse(
        host=result["host"],
        reachable=result["reachable"],
        latency_ms=result.get("latency_ms"),
        message=result.get("message", ""),
    )


@router.get("/stats")
async def get_stats(
    settings: SettingsDep,
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    """
    Example of validated query params. Use limit for pagination; never trust raw input in queries.
    """
    return {"limit": limit, "items": [], "total": 0}
