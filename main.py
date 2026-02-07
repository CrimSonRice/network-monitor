"""
Application entry point. FastAPI app with middleware and routers.
Run: uvicorn main:app --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routes import health_router, monitor_router
from core.config import get_settings
from core.middleware import (
    RateLimitMiddleware,
    RequestTimingMiddleware,
    SecureHeadersMiddleware,
)
from utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: init logging, connections, background tasks.
    Shutdown: close pools, cancel tasks.
    """
    settings = get_settings()
    logger.info(
        "startup",
        extra={
            "app": settings.APP_NAME,
            "env": settings.ENVIRONMENT,
            "log_level": settings.LOG_LEVEL,
        },
    )
    yield
    logger.info("shutdown", extra={"app": settings.APP_NAME})


def create_app() -> FastAPI:
    """Factory for FastAPI app. Enables testing with overrides."""
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        description="Network monitoring API — production-ready async backend",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(SecureHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware    )

    app.include_router(health_router)
    app.include_router(monitor_router)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "body": exc.body},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "main:app",
        host=s.HOST,
        port=s.PORT,
        reload=s.ENVIRONMENT == "development",
        log_level=s.LOG_LEVEL.lower(),
    )
