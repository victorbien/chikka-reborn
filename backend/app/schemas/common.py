from typing import Any

from pydantic import BaseModel

from app.core.request_context import get_request_id


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    """Documented shape of every failing response."""

    error: ErrorBody
    request_id: str


class DataResponse[T](BaseModel):
    """Success envelope: {"data": ..., "request_id": ...}."""

    data: T
    request_id: str


class MessageData(BaseModel):
    message: str


def ok[T](data: T) -> DataResponse[T]:
    return DataResponse[T](data=data, request_id=get_request_id() or "")
