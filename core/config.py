"""Application configuration via environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-based configuration. Validated at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = Field(default="network-monitor", description="Service name for logs and headers")
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development", description="Deployment environment"
    )
    DEBUG: bool = Field(default=False, description="Enable debug mode")

    HOST: str = Field(default="0.0.0.0", description="Bind address; 0.0.0.0 for containers")
    PORT: int = Field(default=8000, ge=1, le=65535)
    WORKERS: int = Field(default=1, ge=1, description="Workers; use 1 for async, scale via replicas")

    SECRET_KEY: str = Field(default="change-me-in-production", min_length=32)
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_EXPIRE_MINUTES: int = Field(default=30, ge=1)
    CORS_ORIGINS: str = Field(default="*", description="Comma-separated origins or *")

    RATE_LIMIT_REQUESTS: int = Field(default=100, ge=1)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1)

    TRUST_PROXY: bool = Field(default=True, description="Trust X-Forwarded-* headers")
    PROXY_HEADER_COUNT: int = Field(default=1, ge=0, description="Number of proxies in front")

    LOG_LEVEL: str = Field(default="INFO")
    LOG_JSON: bool = Field(default=False, description="JSON logs for cloud aggregators")

    CACHE_TTL_SECONDS: int = Field(default=60, ge=0)
    CACHE_ENABLED: bool = Field(default=True)

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret(cls, v: str) -> str:
        if isinstance(v, str) and len(v) < 32 and v != "change-me-in-production":
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Use for DI; avoids re-reading env on every request."""
    return Settings()
