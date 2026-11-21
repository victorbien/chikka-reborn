"""In-process fan-out of real-time events to connected WebSocket clients (ADL-013).

The hub knows connections, not business rules: services decide who receives an event (after
their membership and block checks) and call publish() after the database commit. Pushing is
best-effort. Clients repair anything they missed through REST, so a dropped frame never loses
a message.

Limitation: the hub is per process. Running more than one backend instance needs cross-instance
fan-out (Postgres NOTIFY, see docs/architecture/realtime-design.md) before scaling out.
"""

import asyncio
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_USER = 5
SEND_QUEUE_LIMIT = 256

# Close codes (documented in docs/api/realtime-api.md).
CLOSE_NORMAL = 1000
CLOSE_GOING_AWAY = 1001
CLOSE_TOO_BIG = 1009
CLOSE_UNAUTHORISED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_AUTH_TIMEOUT = 4408
CLOSE_REPLACED = 4409
CLOSE_BACKPRESSURE = 4413
CLOSE_RATE_LIMITED = 4429


@dataclass(frozen=True)
class CloseRequest:
    code: int
    reason: str


Outbound = dict[str, Any] | CloseRequest


@dataclass(eq=False)
class Connection:
    user_id: UUID
    session_id: UUID
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    queue: asyncio.Queue[Outbound] = field(
        default_factory=lambda: asyncio.Queue(maxsize=SEND_QUEUE_LIMIT)
    )
    closing: bool = False

    def offer(self, frame: Outbound) -> None:
        """Queue a frame without blocking. A full queue means the client cannot keep up:
        close it, and it will resync through REST when it reconnects."""
        if self.closing:
            return
        try:
            self.queue.put_nowait(frame)
        except asyncio.QueueFull:
            self.close(CLOSE_BACKPRESSURE, "Too many pending events")

    def close(self, code: int, reason: str) -> None:
        if self.closing:
            return
        self.closing = True
        # Make room so the close request is always delivered.
        while self.queue.full():
            self.queue.get_nowait()
        self.queue.put_nowait(CloseRequest(code, reason))


def event(
    event_type: str, data: dict[str, Any], conversation_id: UUID | None = None
) -> dict[str, Any]:
    """The server-to-client envelope. event_id lets clients ignore duplicates."""
    envelope: dict[str, Any] = {
        "type": event_type,
        "event_id": uuid.uuid4().hex,
        "data": data,
        "sent_at": datetime.now(UTC).isoformat(),
    }
    if conversation_id is not None:
        envelope["conversation_id"] = str(conversation_id)
    return envelope


class RealtimeHub:
    def __init__(self) -> None:
        self._by_user: dict[UUID, dict[str, Connection]] = {}

    def register(self, connection: Connection) -> None:
        connections = self._by_user.setdefault(connection.user_id, {})
        connections[connection.id] = connection
        # Oldest first (dicts keep insertion order). Over the cap, the oldest is replaced.
        while len(connections) > MAX_CONNECTIONS_PER_USER:
            oldest = next(iter(connections.values()))
            oldest.close(CLOSE_REPLACED, "Too many connections")
            connections.pop(oldest.id, None)

    def unregister(self, connection: Connection) -> None:
        connections = self._by_user.get(connection.user_id)
        if connections is None:
            return
        connections.pop(connection.id, None)
        if not connections:
            self._by_user.pop(connection.user_id, None)

    def is_online(self, user_id: UUID) -> bool:
        return bool(self._by_user.get(user_id))

    def connection_count(self, user_id: UUID) -> int:
        return len(self._by_user.get(user_id, {}))

    def publish(self, user_ids: Iterable[UUID], frame: dict[str, Any]) -> None:
        for user_id in set(user_ids):
            for connection in list(self._by_user.get(user_id, {}).values()):
                connection.offer(frame)

    def publish_each(self, frames: dict[UUID, dict[str, Any]]) -> None:
        """Different payload per user (each sees the message as the REST API would show it)."""
        for user_id, frame in frames.items():
            self.publish([user_id], frame)

    def disconnect_session(self, session_id: UUID, code: int = CLOSE_UNAUTHORISED) -> None:
        for connections in list(self._by_user.values()):
            for connection in list(connections.values()):
                if connection.session_id == session_id:
                    connection.close(code, "Session ended")

    def disconnect_user(self, user_id: UUID, code: int = CLOSE_UNAUTHORISED) -> None:
        for connection in list(self._by_user.get(user_id, {}).values()):
            connection.close(code, "Session ended")

    def close_all(self, code: int = CLOSE_GOING_AWAY) -> None:
        """Shutdown: ask every client to reconnect (they resync through REST)."""
        for connections in list(self._by_user.values()):
            for connection in list(connections.values()):
                connection.close(code, "Server restarting")
