"""The real-time gateway: GET /ws/v1 (ADL-013, docs/api/realtime-api.md).

* Authentication is the first frame ({"type": "auth", "token": ...}) within 5 seconds, never a
  URL parameter (URLs end up in access logs). The same checks as REST apply: valid token,
  live Supabase session, active and onboarded account.
* The socket is mostly downlink. Writes go through REST; uplink frames are only ping, ack
  (recipient received messages), typing and auth.refresh.
* The connection ends when the access token expires (plus a short grace) unless the client
  sends auth.refresh, when the session is signed out, and when the client goes quiet.
* Nothing about a conversation is sent before a membership check in the chat service.
"""

import asyncio
import contextlib
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, WebSocket
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.api.container import Providers
from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
)
from app.core.security import AuthenticatedUser, TokenClaims, decode_access_token
from app.database.session import Database
from app.modules.auth.account_service import AccountResolver
from app.modules.chat.service import ChatService
from app.modules.rate_limits.service import RateLimiter
from app.realtime.hub import (
    CLOSE_AUTH_TIMEOUT,
    CLOSE_FORBIDDEN,
    CLOSE_GOING_AWAY,
    CLOSE_RATE_LIMITED,
    CLOSE_TOO_BIG,
    CLOSE_UNAUTHORISED,
    CloseRequest,
    Connection,
)
from app.realtime.protocol import (
    MAX_FRAME_BYTES,
    AckFrame,
    AuthFrame,
    PingFrame,
    RefreshFrame,
    TypingFrame,
    uplink_adapter,
)

logger = logging.getLogger(__name__)

router = APIRouter()

AUTH_TIMEOUT_SECONDS = 5.0
HEARTBEAT_SECONDS = 25
# Two missed heartbeats and the connection is considered gone.
IDLE_TIMEOUT_SECONDS = HEARTBEAT_SECONDS * 2 + 10
EXPIRY_GRACE = timedelta(seconds=30)
TYPING_INTERVAL_SECONDS = 2.0
MAX_FORBIDDEN_FRAMES = 5
CLOSE_SERVER_ERROR = 1011
CLOSE_TRY_AGAIN = 1013


class _TokenBucket:
    """Uplink flood protection: 10 frames per second, bursts of 20."""

    def __init__(self, rate: float = 10.0, burst: float = 20.0) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = burst
        self._at = time.monotonic()

    def take(self) -> bool:
        now = time.monotonic()
        self._tokens = min(self._burst, self._tokens + (now - self._at) * self._rate)
        self._at = now
        if self._tokens < 1:
            return False
        self._tokens -= 1
        return True


class _RejectedError(Exception):
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


async def _authenticate(
    token: str, settings: Settings, database: Database
) -> tuple[AuthenticatedUser, TokenClaims]:
    try:
        claims = await run_in_threadpool(decode_access_token, token, settings)
        user = await AccountResolver(database).resolve(claims)
    except AuthenticationError as exc:
        raise _RejectedError(CLOSE_UNAUTHORISED, "Not authenticated") from exc
    except PermissionDeniedError as exc:
        raise _RejectedError(CLOSE_FORBIDDEN, "Account unavailable") from exc
    except ServiceUnavailableError as exc:
        raise _RejectedError(CLOSE_TRY_AGAIN, "Try again later") from exc
    if user.status != "active" or not user.onboarded:
        raise _RejectedError(CLOSE_FORBIDDEN, "Finish setting up your account first")
    return user, claims


def _error(code: str, message: str) -> dict[str, Any]:
    return {"type": "error", "code": code, "message": message}


@router.websocket("/ws/v1")
async def realtime_gateway(websocket: WebSocket) -> None:
    settings: Settings = websocket.app.state.settings
    providers: Providers = websocket.app.state.providers
    database: Database | None = websocket.app.state.database

    # Browsers always send Origin; a foreign page must not ride on a user's token.
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in settings.cors_origins:
        await websocket.close(code=CLOSE_FORBIDDEN)
        return
    await websocket.accept()
    if database is None:
        await websocket.close(code=CLOSE_TRY_AGAIN, reason="Service unavailable")
        return

    try:
        first = await asyncio.wait_for(websocket.receive(), AUTH_TIMEOUT_SECONDS)
    except TimeoutError:
        await websocket.close(code=CLOSE_AUTH_TIMEOUT, reason="Authentication timed out")
        return
    if first["type"] == "websocket.disconnect":
        return
    try:
        raw = first.get("text")
        if raw is None or len(raw.encode()) > MAX_FRAME_BYTES:
            raise _RejectedError(CLOSE_UNAUTHORISED, "Not authenticated")
        try:
            auth_frame = AuthFrame.model_validate_json(raw)
        except ValidationError as exc:
            raise _RejectedError(CLOSE_UNAUTHORISED, "Not authenticated") from exc
        user, claims = await _authenticate(auth_frame.token, settings, database)
    except _RejectedError as rejected:
        await websocket.close(code=rejected.code, reason=rejected.reason)
        return

    hub = providers.realtime
    chat = ChatService(
        database=database,
        attachments=providers.attachment_storage,
        avatars=providers.storage,
        limiter=RateLimiter(database, settings),
        presence=providers.presence,
        hub=hub,
    )
    connection = Connection(user_id=user.id, session_id=user.session_id)
    hub.register(connection)
    connection.offer(
        {
            "type": "ready",
            "connection_id": connection.id,
            "heartbeat_s": HEARTBEAT_SECONDS,
            "server_time": datetime.now(UTC).isoformat(),
            "expires_at": claims.expires_at.isoformat() if claims.expires_at else None,
        }
    )
    logger.info("realtime connected", extra={"connection_id": connection.id})

    async def pump() -> None:
        while True:
            outbound = await connection.queue.get()
            if isinstance(outbound, CloseRequest):
                with contextlib.suppress(Exception):
                    await websocket.close(code=outbound.code, reason=outbound.reason)
                return
            await websocket.send_json(outbound)

    pump_task = asyncio.create_task(pump())
    expires_at = claims.expires_at
    bucket = _TokenBucket()
    typing_sent: dict[str, float] = {}
    forbidden = 0
    close_code = CLOSE_GOING_AWAY

    try:
        while not pump_task.done():
            timeout = float(IDLE_TIMEOUT_SECONDS)
            expired = False
            if expires_at is not None:
                remaining = (expires_at + EXPIRY_GRACE - datetime.now(UTC)).total_seconds()
                if remaining <= 0:
                    expired = True
                timeout = max(0.0, min(timeout, remaining))
            if expired:
                connection.close(CLOSE_UNAUTHORISED, "Token expired")
                break

            receive_task = asyncio.ensure_future(websocket.receive())
            done, _ = await asyncio.wait(
                {receive_task, pump_task}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if receive_task not in done:
                receive_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await receive_task
                if pump_task.done():
                    break
                if expires_at is None or datetime.now(UTC) < expires_at + EXPIRY_GRACE:
                    connection.close(CLOSE_GOING_AWAY, "Idle")
                    break
                continue  # expiry is handled at the top of the loop

            message = receive_task.result()
            if message["type"] == "websocket.disconnect":
                close_code = int(message.get("code") or CLOSE_GOING_AWAY)
                break
            text = message.get("text")
            if text is None or len(text.encode()) > MAX_FRAME_BYTES:
                connection.close(CLOSE_TOO_BIG, "Frames must be text and at most 8 KB")
                break
            if not bucket.take():
                connection.close(CLOSE_RATE_LIMITED, "Too many frames")
                break

            try:
                frame = uplink_adapter.validate_json(text)
            except ValidationError:
                connection.offer(_error("invalid_frame", "Unknown or malformed frame."))
                continue

            try:
                if isinstance(frame, PingFrame):
                    connection.offer({"type": "pong", "server_time": datetime.now(UTC).isoformat()})
                elif isinstance(frame, AckFrame):
                    await chat.acknowledge(user, frame.message_ids)
                elif isinstance(frame, TypingFrame):
                    key = str(frame.conversation_id)
                    now = time.monotonic()
                    if now - typing_sent.get(key, 0.0) >= TYPING_INTERVAL_SECONDS:
                        typing_sent[key] = now
                        await chat.typing(user, frame.conversation_id)
                elif isinstance(frame, RefreshFrame):
                    refreshed, new_claims = await _authenticate(frame.token, settings, database)
                    if refreshed.id != user.id:
                        connection.close(CLOSE_UNAUTHORISED, "Token belongs to another user")
                        break
                    expires_at = new_claims.expires_at
                    connection.offer(
                        {
                            "type": "auth.ok",
                            "expires_at": expires_at.isoformat() if expires_at else None,
                        }
                    )
            except _RejectedError as rejected:
                connection.close(rejected.code, rejected.reason)
                break
            except NotFoundError:
                forbidden += 1
                connection.offer(_error("forbidden", "You are not part of that conversation."))
                if forbidden >= MAX_FORBIDDEN_FRAMES:
                    connection.close(CLOSE_FORBIDDEN, "Too many forbidden requests")
                    break
            except AppError as exc:
                connection.offer(_error(exc.code, exc.message))
            except Exception as exc:
                logger.error("realtime frame failed", extra={"error_type": type(exc).__name__})
                connection.offer(_error("internal_error", "Something went wrong."))
    finally:
        hub.unregister(connection)
        if not pump_task.done():
            # Let the pump deliver a pending close frame, then stop it.
            connection.close(close_code, "Closing")
            with contextlib.suppress(Exception):
                await asyncio.wait_for(pump_task, 2)
        if not pump_task.done():
            pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await pump_task
        logger.info("realtime disconnected", extra={"connection_id": connection.id})
