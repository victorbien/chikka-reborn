import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import health
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.database.session import build_database
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

API_V1_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Tests pass their own Settings; production uses the environment."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = build_database(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )
        logger.info(
            "application starting",
            extra={
                "environment": settings.app_env,
                "sms_mode": settings.sms_mode,
                "database_configured": app.state.database is not None,
            },
        )
        try:
            yield
        finally:
            if app.state.database is not None:
                await app.state.database.dispose()
            logger.info("application stopped")

    app = FastAPI(
        title="Chikka Reborn API",
        version=settings.app_version,
        description=(
            "Independent, Chikka-inspired messaging platform. "
            "Not affiliated with the original service."
        ),
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url=f"{API_V1_PREFIX}/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
        responses={"default": {"model": ErrorResponse, "description": "Error envelope"}},
    )
    # Dependencies read settings from here so tests can override a single object.
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.database = None

    register_middleware(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)
    app.include_router(health.platform_router)
    return app


app = create_app()
