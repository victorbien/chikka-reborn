"""Mobile OTP delivery abstraction (FR-AUTH-008).

Mobile verification is not delegated to Supabase phone auth, which needs an SMS provider
configured in Supabase. The backend owns the flow and sends the code through OtpDelivery:

* simulation (SMS_PROVIDER_MODE=mock): nothing is sent; the code goes to an in-memory
  inbox that the UI shows with a SIMULATED label outside production.
* live: delivery needs the Phase 2 SmsProvider. Until it exists, live delivery raises
  OtpDeliveryUnavailableError. It never falls back to simulation.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal, Protocol

VerificationMode = Literal["live", "simulated"]


class OtpDeliveryUnavailableError(Exception):
    """The configured delivery channel cannot send codes right now."""


class OtpDelivery(Protocol):
    mode: VerificationMode

    async def deliver(self, *, user_id: str, e164: str, code: str, ttl_seconds: int) -> None: ...


@dataclass(frozen=True)
class SimulatedMessage:
    code: str
    created_at: float
    expires_at: float
    masked_to: str


class SimulatedInbox:
    """Per-process, memory-only store of simulated OTP messages. Never persisted or logged."""

    MAX_PER_USER = 5

    def __init__(self) -> None:
        self._messages: dict[str, deque[SimulatedMessage]] = {}

    def put(self, user_id: str, message: SimulatedMessage) -> None:
        queue = self._messages.setdefault(user_id, deque(maxlen=self.MAX_PER_USER))
        queue.append(message)

    def list_for(self, user_id: str) -> list[SimulatedMessage]:
        now = time.time()
        live = [m for m in self._messages.get(user_id, ()) if m.expires_at > now]
        self._messages[user_id] = deque(live, maxlen=self.MAX_PER_USER)
        return list(reversed(live))

    def clear(self, user_id: str) -> None:
        self._messages.pop(user_id, None)


class SimulatedOtpDelivery:
    mode: VerificationMode = "simulated"

    def __init__(self, inbox: SimulatedInbox) -> None:
        self._inbox = inbox

    async def deliver(self, *, user_id: str, e164: str, code: str, ttl_seconds: int) -> None:
        from app.core.privacy import mask_phone

        now = time.time()
        self._inbox.put(
            user_id,
            SimulatedMessage(
                code=code,
                created_at=now,
                expires_at=now + ttl_seconds,
                masked_to=mask_phone(e164),
            ),
        )


class UnavailableLiveOtpDelivery:
    mode: VerificationMode = "live"

    async def deliver(self, *, user_id: str, e164: str, code: str, ttl_seconds: int) -> None:
        raise OtpDeliveryUnavailableError("Live SMS delivery is not available yet")
