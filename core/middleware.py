"""
Middleware: rate limiting, secure headers, request timing, error handling.
Order matters: timing wraps innermost; then security; then rate limit; then exception handler.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

# In-memory rate limit store. Production: use Redis or similar for multi-instance.
_rate_limit_store: dict[str, list[float]] = {}


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Records request duration and logs slow requests.
    Async-compatible: uses monotonic time, no blocking.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        if duration_ms > 500:
            logger.warning(
                "slow_request",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "duration_ms": round(duration_ms, 2),
                    "status": response.status_code,
                },
            )
        return response


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers. Compatible with Nginx/Cloudflare (they may override).
    Reduces clickjacking, XSS, and MIME sniffing risks.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-client rate limiting. Uses X-Forwarded-For when TRUST_PROXY (Nginx/Cloudflare).
    In-memory implementation; use Redis for multi-worker/replica consistency.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        client_ip = _get_client_ip(request)
        now = time.time()
        window = settings.RATE_LIMIT_WINDOW_SECONDS
        max_requests = settings.RATE_LIMIT_REQUESTS

        # Prune old entries for this client
        if client_ip not in _rate_limit_store:
            _rate_limit_store[client_ip] = []
        timestamps = _rate_limit_store[client_ip]
        timestamps[:] = [t for t in timestamps if now - t < window]

        if len(timestamps) >= max_requests:
            logger.warning("rate_limit_exceeded", extra={"client_ip": client_ip})
            return Response(
                content='{"detail":"Too Many Requests"}',
                status_code=429,
                media_type="application/json",
            )
        timestamps.append(now)

        return await call_next(request)


def _get_client_ip(request: Request) -> str:
    """Resolve client IP; respect X-Forwarded-For when behind proxy (Nginx/Cloudflare)."""
    settings = get_settings()
    if settings.TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First address is client; optional PROXY_HEADER_COUNT for multiple hops
            parts = [p.strip() for p in forwarded.split(",")]
            idx = max(0, len(parts) - settings.PROXY_HEADER_COUNT)
            return parts[idx] if idx < len(parts) else parts[0]
    return request.client.host if request.client else "unknown"
