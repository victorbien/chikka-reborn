from typing import Protocol

from app.core.config import Settings
from app.core.request_context import get_request_id
from app.schemas.health import DatabaseState, HealthResponse


class DatabasePinger(Protocol):
    async def ping(self) -> bool: ...


class HealthService:
    def __init__(self, settings: Settings, database_check: DatabasePinger | None) -> None:
        self._settings = settings
        self._database_check = database_check

    async def check(self) -> HealthResponse:
        database: DatabaseState = "not_configured"
        if self._database_check is not None:
            database = "ok" if await self._database_check.ping() else "unavailable"
        return HealthResponse(
            status="degraded" if database == "unavailable" else "ok",
            service=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.app_env,
            sms_mode=self._settings.sms_mode,
            database=database,
            request_id=get_request_id() or "",
        )
