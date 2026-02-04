"""
Pydantic schemas for request/response validation.
Reusable across routes; keeps API contracts explicit.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from core.config import get_settings


class ErrorDetail(BaseModel):
    """Standard error payload for API responses."""

    detail: str
    code: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"extra": "forbid"}


class PaginatedResponse(BaseModel):
    """Generic paginated list. Use with concrete item type."""

    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(default=20, alias="page_size")
    has_more: bool = False

    model_config = {"populate_by_name": True, "extra": "forbid"}


def example_env_schema() -> dict[str, Any]:
    """Return schema of expected env vars for docs/deployment."""
    s = get_settings()
    return {
        "APP_NAME": s.APP_NAME,
        "ENVIRONMENT": s.ENVIRONMENT,
        "LOG_LEVEL": s.LOG_LEVEL,
        "RATE_LIMIT_REQUESTS": s.RATE_LIMIT_REQUESTS,
    }
