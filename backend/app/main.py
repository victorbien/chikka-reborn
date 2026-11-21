import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import websocket
from app.api.container import Providers, build_providers
from app.api.v1 import health
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.database.session import build_database
from app.integrations.ai.factory import build_ai_provider
from app.integrations.email.factory import build_email_provider
from app.integrations.sms.factory import build_sms_provider
from app.modules.notifications.dispatcher import NotificationDispatcher
from app.modules.sms.gateway import announce_mode, build_gateway
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

API_V1_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None, providers: Providers | None = None) -> FastAPI:
    """Application factory. Tests pass their own Settings and fake providers."""
    settings = settings or get_settings()
    owns_providers = providers is None
    app_providers = providers or build_providers(settings)
    configure_logging(settings.log_level)
    # A live provider that cannot be built raises here, at startup. It is never replaced by
    # the simulation.
    owns_sms = app_providers.sms is None
    if app_providers.sms is None:
        app_providers.sms = build_sms_provider(settings, clock=app_providers.clock)
    owns_email = app_providers.email is None
    if app_providers.email is None:
        app_providers.email = build_email_provider(settings)
    owns_ai = app_providers.ai is None
    if app_providers.ai is None:
        app_providers.ai = build_ai_provider(settings)

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
                "ai_provider": settings.ai_provider_mode,
                "email_provider": settings.email_provider_mode,
                "database_configured": app.state.database is not None,
            },
        )
        gateway = None
        if app.state.database is not None and app_providers.sms is not None:
            gateway = build_gateway(
                settings=settings,
                database=app.state.database,
                provider=app_providers.sms,
                hub=app_providers.realtime,
                clock=app_providers.clock,
                rng=app_providers.rng,
            )
            app.state.sms_gateway = gateway
            await announce_mode(app.state.database, app_providers.sms)
            if settings.sms_worker_enabled:
                gateway.worker.start()
        dispatcher = None
        if app.state.database is not None and app_providers.email is not None:
            dispatcher = NotificationDispatcher(
                settings=settings,
                database=app.state.database,
                hub=app_providers.realtime,
                email=app_providers.email,
                clock=app_providers.clock,
            )
            app.state.notification_dispatcher = dispatcher
            if settings.notifications_worker_enabled:
                dispatcher.start()
        try:
            yield
        finally:
            if dispatcher is not None:
                await dispatcher.stop()
            if gateway is not None:
                await gateway.worker.stop()
            app_providers.realtime.close_all()
            if app.state.database is not None:
                await app.state.database.dispose()
            if owns_providers or owns_sms or owns_ai or owns_email:
                await app_providers.aclose()
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
    app.state.sms_gateway = None
    app.state.notification_dispatcher = None
    app.state.providers = app_providers
    app.state.settings = settings

    register_middleware(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)
    app.include_router(health.platform_router)
    app.include_router(websocket.router)
    return app


app = create_app()
