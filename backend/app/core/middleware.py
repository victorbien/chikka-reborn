import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.core.request_context import new_request_id, set_request_id

logger = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request ID, logs one access line and adds baseline security headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = new_request_id(request.headers.get(REQUEST_ID_HEADER))
        set_request_id(request_id)
        started = time.perf_counter()

        response = await call_next(request)

        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                # Path only: query strings can carry personal data.
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response


def register_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(RequestContextMiddleware)
    # Added last so it is outermost and answers preflight requests first.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # refresh cookie; origins are explicit, never "*"
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Chikka-CSRF",
            REQUEST_ID_HEADER,
        ],
        expose_headers=[REQUEST_ID_HEADER, "Retry-After"],
    )
