"""
Health and readiness endpoints for load balancers and Kubernetes.
No auth required; keep payload minimal for fast checks.
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel

from core.config import SettingsDep

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Minimal health payload for probes."""

    status: str = "ok"
    service: str = "network-monitor"


class ReadinessResponse(BaseModel):
    """Readiness: include dependency checks when applicable."""

    ready: bool = True
    checks: dict[str, str] = {}

    model_config = {"extra": "forbid"}


@router.get("", response_model=HealthResponse)
async def health(settings: SettingsDep) -> HealthResponse:
    """
    Liveness: is the process alive.
    Used by Kubernetes livenessProbe, Docker HEALTHCHECK.
    """
    return HealthResponse(service=settings.APP_NAME)


@router.get("/ready", response_model=ReadinessResponse)
async def ready(settings: SettingsDep) -> ReadinessResponse:
    """
    Readiness: can the instance accept traffic (DB, cache, etc.).
    Add checks here (e.g. Redis ping, DB connection) for full readiness.
    """
    checks: dict[str, str] = {"config": "loaded"}
    # Example: checks["database"] = "ok" after pool check
    return ReadinessResponse(ready=True, checks=checks)


@router.get("/live")
async def live(response: Response) -> None:
    """
    Minimal live check: 200 with no body. For Nginx/Cloudflare health checks.
    """
    response.status_code = 200
