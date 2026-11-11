from typing import Literal

from pydantic import BaseModel

DatabaseState = Literal["ok", "unavailable", "not_configured"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str
    sms_mode: Literal["simulation", "live"]
    database: DatabaseState
    request_id: str
