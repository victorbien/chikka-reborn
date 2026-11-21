import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Typed domain error. Services raise these; one handler maps them to HTTP."""

    status_code = 500
    code = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}
        self.headers = headers or {}


class AuthenticationError(AppError):
    status_code = 401
    code = "not_authenticated"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnprocessableError(AppError):
    status_code = 422
    code = "validation_error"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after: int, message: str | None = None) -> None:
        seconds = max(1, int(retry_after))
        super().__init__(
            message or "Too many attempts. Please try again later.",
            details={"retry_after_seconds": seconds},
            headers={"Retry-After": str(seconds)},
        )


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class BadGatewayError(AppError):
    """An upstream provider (for example the AI model) failed. The message is generic."""

    status_code = 502
    code = "provider_error"


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id() or ""
    response_headers = {"X-Request-ID": request_id, **(headers or {})}
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, "details": details or {}},
            "request_id": request_id,
        },
        headers=response_headers,
    )


async def _handle_app_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    headers = dict(exc.headers)
    if exc.status_code == 401:
        headers.setdefault("WWW-Authenticate", "Bearer")
    if exc.status_code >= 500:
        logger.error("application error", extra={"error_code": exc.code})
    return error_response(exc.status_code, exc.code, exc.message, exc.details, headers or None)


async def _handle_http_exception(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    message = "Resource not found." if exc.status_code == 404 else "Request could not be handled."
    return error_response(exc.status_code, code, message)


async def _handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    # Report where and why, never the submitted values (they may be private).
    problems = [
        {"field": ".".join(str(part) for part in err["loc"]), "reason": err["msg"]}
        for err in exc.errors()
    ]
    return error_response(
        422, "validation_error", "The request was invalid.", {"problems": problems}
    )


async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled exception", extra={"error_type": type(exc).__name__}, exc_info=exc)
    return error_response(500, "internal_error", "Something went wrong on our side.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
