"""FastAPI application factory and ASGI entrypoint.

Run locally with::

    uv run uvicorn app:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.config import get_settings
from core.exceptions import register_exception_handlers
from core.logging import configure_logging, get_logger
from core.metrics import MetricsMiddleware, metrics_endpoint
from core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from core.version import __version__
from db.session import dispose_engine
from internal.router import router as internal_router
from items.router import router as items_router

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    configure_logging(log_level=settings.log_level, json_logs=settings.log_json)
    logger.info(
        "app_startup",
        app=settings.app_name,
        version=__version__,
        environment=settings.environment,
    )
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("app_shutdown", app=settings.app_name)


def _register_middleware(app: FastAPI) -> None:
    """Install middleware.

    Execution order is outer -> inner: request context/access log, metrics, CORS,
    security headers, trusted host, rate limiting. Middleware added later runs
    first because Starlette inserts each at the front of the stack.
    """
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
            exempt_paths=["/health/live", "/health/ready", settings.metrics_path],
        )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    if settings.security_headers_enabled:
        app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    if settings.metrics_enabled:
        app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestContextMiddleware)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Production-ready FastAPI microservice template.",
        debug=settings.debug,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    _register_middleware(app)
    register_exception_handlers(app)

    # internal routes (metadata, probes) live at the root, outside versioning
    app.include_router(internal_router)
    app.include_router(items_router, prefix=settings.api_v1_prefix)

    if settings.metrics_enabled:
        app.add_api_route(
            settings.metrics_path,
            metrics_endpoint,
            methods=["GET"],
            include_in_schema=False,
            summary="Prometheus metrics",
        )

    return app


app = create_app()
