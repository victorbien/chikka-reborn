"""Provider-independent SMS contract (docs/architecture/sms-gateway-design.md section 2).

Services depend on SmsProvider and these models only. Nothing vendor-specific leaks out:
provider statuses are mapped to the platform vocabulary here, failures are classified, and
phone numbers are always E.164.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

SmsMode = Literal["simulation", "live"]
ProviderName = Literal["mock", "twilio"]

# Platform vocabulary for outbound SMS (sms-provider-guidelines.md). "accepted" is never delivery.
DeliveryStatus = Literal["queued", "accepted", "sent", "delivered", "undelivered", "failed"]
FailureClass = Literal["policy", "transient", "ambiguous", "permanent", "configuration"]

# Forward-only ranking. Terminal states share a rank: the first terminal state wins.
STATUS_RANK: dict[str, int] = {
    "queued": 0,
    "accepted": 1,
    "sent": 2,
    "delivered": 3,
    "undelivered": 3,
    "failed": 3,
}
TERMINAL_STATUSES = frozenset({"delivered", "undelivered", "failed"})


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SendRequest(_Frozen):
    to: str
    body: str
    sender: str
    # Our message_deliveries.id for this attempt. Echoed back on callbacks to correlate them.
    correlation_id: UUID
    # Stable across retries of one message. Providers do not necessarily honour it.
    idempotency_key: str
    status_callback_url: str | None = None


class SendResult(_Frozen):
    provider_message_id: str
    provider_status: str
    mapped_status: DeliveryStatus
    segments_reported: int | None = None
    # Redacted: no credentials, no message body.
    response: dict[str, str | int | None] = {}


class ProviderStatusSnapshot(_Frozen):
    provider_message_id: str
    provider_status: str
    mapped_status: DeliveryStatus
    error_code: str | None = None


class ProviderStatusEvent(_Frozen):
    provider_message_id: str
    provider_status: str
    mapped_status: DeliveryStatus | None
    error_code: str | None = None
    occurred_at: datetime | None = None
    dedupe_key: str
    correlation_id: UUID | None = None


class InboundSmsEvent(_Frozen):
    provider_message_id: str
    from_phone: str
    to_number: str
    body: str
    received_at: datetime
    dedupe_key: str
    media_count: int = 0


class ProviderCountryInfo(_Frozen):
    """What the provider itself reports about a destination. Informational: the platform's own
    verified capability configuration decides whether a send is allowed."""

    country_code: str
    source: str
    outbound_price_per_segment: Decimal | None = None
    currency: str | None = None
    inbound_supported: bool | None = None
    notes: str | None = None


class SimulatedCallback(_Frozen):
    """A signed webhook request the simulation produced. It is delivered through the same
    intake code as a real provider callback."""

    kind: Literal["status", "inbound"]
    raw_body: bytes
    headers: dict[str, str]
    query: str = ""


class ProviderError(Exception):
    """Raised by providers. `message` is safe to log; it never carries credentials or bodies."""

    def __init__(
        self,
        failure_class: FailureClass,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_class: FailureClass = failure_class
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retry_after = retry_after


class WebhookError(Exception):
    """A signed webhook whose payload could not be understood."""


class SmsProvider(ABC):
    name: ProviderName
    mode: SmsMode

    @property
    def is_simulated(self) -> bool:
        return self.mode == "simulation"

    @abstractmethod
    async def send_message(self, request: SendRequest) -> SendResult:
        """Submit one message. Raises ProviderError; never succeeds without a provider ID."""

    @abstractmethod
    async def get_message_status(self, provider_message_id: str) -> ProviderStatusSnapshot: ...

    @abstractmethod
    async def validate_webhook(self, raw_body: bytes, headers: Mapping[str, str], url: str) -> bool:
        """Verify the signature over the exact raw request. False means reject.

        Raises ProviderError(configuration) when the signing secret is missing, so the
        endpoint fails closed instead of accepting unsigned traffic."""

    @abstractmethod
    async def parse_inbound_message(
        self, raw_body: bytes, headers: Mapping[str, str]
    ) -> InboundSmsEvent: ...

    @abstractmethod
    async def parse_status_callback(
        self, raw_body: bytes, headers: Mapping[str, str], query: Mapping[str, str]
    ) -> ProviderStatusEvent:
        """Added beyond the four core operations: a delivery callback is not an inbound SMS."""

    @abstractmethod
    async def get_country_capabilities(self, country_code: str) -> ProviderCountryInfo: ...

    async def pending_callbacks(self) -> list[SimulatedCallback]:
        """Callbacks due now. Only the simulation produces them; live providers call us."""
        return []

    async def aclose(self) -> None:  # noqa: B027 - optional hook
        """Release network resources."""
