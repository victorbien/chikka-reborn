"""Request body size limits (audit finding SEC-003).

A pure ASGI middleware: it rejects on the declared Content-Length and also counts the bytes of
chunked bodies as they arrive, so an oversized request is refused before it is buffered.
"""

import re
from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions import error_response

DEFAULT_LIMIT = 1024 * 1024
WEBHOOK_LIMIT = 64 * 1024
# 10 MB file plus multipart framing.
UPLOAD_LIMIT = 11 * 1024 * 1024
AVATAR_LIMIT = 3 * 1024 * 1024

_UPLOAD_ROUTES = (
    (re.compile(r"^/api/v1/conversations/[^/]+/attachments$"), UPLOAD_LIMIT),
    (re.compile(r"^/api/v1/users/me/avatar$"), AVATAR_LIMIT),
    (re.compile(r"^/api/v1/webhooks/"), WEBHOOK_LIMIT),
)


def limit_for(path: str) -> int:
    for pattern, limit in _UPLOAD_ROUTES:
        if pattern.match(path):
            return limit
    return DEFAULT_LIMIT


class _TooLargeError(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        limit = limit_for(scope["path"])
        headers: MutableMapping[bytes, bytes] = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await self._reject(scope, receive, send)
            return

        received = 0
        started = False

        async def counted_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLargeError
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self._app(scope, counted_receive, tracking_send)
        except _TooLargeError:
            if started:
                raise
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response: Any = error_response(
            413, "payload_too_large", "The request is too large.", None, {"Connection": "close"}
        )
        await response(scope, receive, send)
