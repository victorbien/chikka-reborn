"""Presence (FR-AUTH-013).

Presence is ephemeral: heartbeats live in memory and only last_seen_at is persisted
(AC3). The client sends a heartbeat every 30 seconds with idle=true after 5 minutes without
activity. No heartbeat for 60 seconds means offline.

Limitation: the registry is per process. With several backend instances, presence must move
to the realtime layer (ADL-013, Postgres NOTIFY fan-out) planned for chat in Module C.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.modules.profiles.schemas import PresencePreference, PresenceStatus

OFFLINE_AFTER_SECONDS = 60
PERSIST_LAST_SEEN_EVERY_SECONDS = 60


@dataclass
class _Beat:
    at: float
    idle: bool
    persisted_at: float


class PresenceRegistry:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._beats: dict[str, _Beat] = {}

    def heartbeat(self, user_id: str, *, idle: bool) -> bool:
        """Record activity. Returns True when last_seen_at should be written to the database."""
        now = self._clock()
        previous = self._beats.get(user_id)
        if previous is None or now - previous.persisted_at >= PERSIST_LAST_SEEN_EVERY_SECONDS:
            self._beats[user_id] = _Beat(at=now, idle=idle, persisted_at=now)
            return True
        self._beats[user_id] = _Beat(at=now, idle=idle, persisted_at=previous.persisted_at)
        return False

    def clear(self, user_id: str) -> None:
        self._beats.pop(user_id, None)

    def status(self, user_id: str, preference: PresencePreference) -> PresenceStatus:
        """Presence as the user themselves sees it. Others will see invisible as offline."""
        beat = self._beats.get(user_id)
        if beat is None or self._clock() - beat.at > OFFLINE_AFTER_SECONDS:
            return "offline"
        if preference == "online" and beat.idle:
            return "away"
        return preference

    @staticmethod
    def as_seen_by_others(status: PresenceStatus) -> PresenceStatus:
        return "offline" if status == "invisible" else status
