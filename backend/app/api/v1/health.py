from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, get_optional_db_session
from app.repositories.health_repository import HealthRepository
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService

# Versioned routes for clients: /api/v1/health and /api/v1/health/ready.
router = APIRouter(prefix="/health", tags=["health"])
# Unversioned aliases for hosting platforms (ADR): /healthz and /readyz.
platform_router = APIRouter(tags=["health"])

OptionalSessionDep = Annotated[AsyncSession | None, Depends(get_optional_db_session)]


def _build_service(settings: SettingsDep, session: OptionalSessionDep) -> HealthService:
    repository = HealthRepository(session) if session is not None else None
    return HealthService(settings, repository)


HealthServiceDep = Annotated[HealthService, Depends(_build_service)]


async def get_health(service: HealthServiceDep) -> HealthResponse:
    """Always answers 200 while the process is up; `status` reports degradation."""
    return await service.check()


async def get_readiness(service: HealthServiceDep, response: Response) -> HealthResponse:
    """503 when a configured dependency (the database) is unavailable."""
    result = await service.check()
    if result.status != "ok":
        response.status_code = 503
    return result


for _router, _live, _ready in ((router, "", "/ready"), (platform_router, "/healthz", "/readyz")):
    _router.add_api_route(
        _live,
        get_health,
        methods=["GET"],
        response_model=HealthResponse,
        summary="Liveness and configuration summary",
    )
    _router.add_api_route(
        _ready,
        get_readiness,
        methods=["GET"],
        response_model=HealthResponse,
        summary="Readiness: 503 when a configured dependency is down",
        responses={503: {"model": HealthResponse}},
    )
