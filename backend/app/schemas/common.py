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


class Pagination(BaseModel):
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class PagedResponse[T](BaseModel):
    """List envelope: {"data": [...], "pagination": {...}, "request_id": ...}."""

    data: list[T]
    pagination: Pagination
    request_id: str


def paged[T](items: list[T], *, total: int, page: int, page_size: int) -> PagedResponse[T]:
    return PagedResponse[T](
        data=items,
        pagination=Pagination(
            total=total,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total,
            has_prev=page > 1,
        ),
        request_id=get_request_id() or "",
    )


class MessageData(BaseModel):
    message: str


def ok[T](data: T) -> DataResponse[T]:
    return DataResponse[T](data=data, request_id=get_request_id() or "")
