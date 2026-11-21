"""MockSmsProvider: the simulation. Sends nothing, costs nothing, and is always labelled.

Everything it produces goes back through the real webhook intake with a signature from the mock
signer, so signature handling, de-duplication, ordering and persistence are exercised exactly
as in live mode. Scenarios are chosen by reserved fictional numbers (NANP +1 202 555 0100-0199).
Time comes from the injected clock, so tests are deterministic.
"""

import hashlib
import hmac
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.integrations.sms.base import (
    DeliveryStatus,
    InboundSmsEvent,
    ProviderCountryInfo,
    ProviderError,
    ProviderStatusEvent,
    ProviderStatusSnapshot,
    SendRequest,
    SendResult,
    SimulatedCallback,
    SmsMode,
    SmsProvider,
    WebhookError,
)

SIGNATURE_HEADER = "x-mock-signature"
TIMESTAMP_HEADER = "x-mock-timestamp"
SIGNATURE_TOLERANCE_SECONDS = 300
SIM_ID_PREFIX = "SIM-"

# Reserved fictional numbers -> scenario (FR-SMS-013). Any other number is "delivered".
SCENARIOS: dict[str, str] = {
    "+12025550100": "delivered",
    "+12025550101": "failed",
    "+12025550102": "undelivered",
    "+12025550103": "transient_error_then_success",
    "+12025550104": "transient_error_always",
    "+12025550105": "permanent_error",
    "+12025550106": "delayed_delivery",
    "+12025550107": "no_receipt",
    "+12025550108": "duplicate_callback",
    "+12025550109": "out_of_order",
    "+12025550110": "ambiguous_timeout",
}
TEST_NUMBERS = tuple(SCENARIOS)


@dataclass(frozen=True)
class Timeline:
    """Seconds after acceptance (accepted is the send response itself)."""

    sent: float = 3.0
    delivered: float = 6.0
    delayed_delivered: float = 600.0


@dataclass
class _Scheduled:
    due_at: datetime
    message_id: str
    status: str
    error_code: str | None
    correlation_id: UUID
    event_id: str


@dataclass
class _Record:
    request: SendRequest
    events: list[_Scheduled] = field(default_factory=list)


def sign(secret: str, timestamp: str, raw_body: bytes) -> str:
    return hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw_body, hashlib.sha256
    ).hexdigest()


class MockSmsProvider(SmsProvider):
    name = "mock"
    mode: SmsMode = "simulation"

    def __init__(
        self,
        *,
        secret: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeline: Timeline | None = None,
        id_factory: Callable[[], str] = lambda: uuid.uuid4().hex[:20],
    ) -> None:
        if not secret:
            raise ValueError("the mock webhook secret must not be empty")
        self._secret = secret
        self._clock = clock
        self._timeline = timeline or Timeline()
        self._new_id = id_factory
        self._records: dict[str, _Record] = {}
        self._pending: list[_Scheduled] = []
        self._attempts: dict[str, int] = {}
        # Every request the provider accepted, so tests can assert "exactly one send".
        self.sent: list[SendRequest] = []

    @staticmethod
    def scenario_for(number: str) -> str:
        return SCENARIOS.get(number, "delivered")

    # -- outbound --------------------------------------------------------------------------

    async def send_message(self, request: SendRequest) -> SendResult:
        scenario = self.scenario_for(request.to)
        attempt = self._attempts.get(request.idempotency_key, 0) + 1
        self._attempts[request.idempotency_key] = attempt

        if scenario == "permanent_error":
            raise ProviderError("permanent", "SIM-INVALID", "Simulated invalid number")
        if scenario == "transient_error_always" or (
            scenario == "transient_error_then_success" and attempt == 1
        ):
            raise ProviderError(
                "transient", "SIM-TRANSIENT", "Simulated provider outage", http_status=503
            )
        if scenario == "ambiguous_timeout":
            raise ProviderError("ambiguous", "SIM-TIMEOUT", "Simulated read timeout")

        message_id = SIM_ID_PREFIX + self._new_id()
        record = _Record(request)
        self._records[message_id] = record
        self.sent.append(request)
        self._schedule(record, message_id, scenario)
        return SendResult(
            provider_message_id=message_id,
            provider_status="accepted",
            mapped_status="accepted",
            segments_reported=None,
            response={"simulated": 1, "scenario": scenario, "status": "accepted"},
        )

    def _schedule(self, record: _Record, message_id: str, scenario: str) -> None:
        now = self._clock()
        t = self._timeline

        def add(
            status: str, after: float, error: str | None = None, event: str | None = None
        ) -> None:
            item = _Scheduled(
                due_at=now + timedelta(seconds=after),
                message_id=message_id,
                status=status,
                error_code=error,
                correlation_id=record.request.correlation_id,
                event_id=event or f"{message_id}:{status}",
            )
            record.events.append(item)
            self._pending.append(item)

        if scenario in ("delivered", "duplicate_callback"):
            add("sent", t.sent)
            add("delivered", t.delivered)
            if scenario == "duplicate_callback":
                add("delivered", t.delivered + 1, event=f"{message_id}:delivered")
        elif scenario == "failed":
            add("failed", t.sent, "SIM-FAILED")
        elif scenario == "undelivered":
            add("sent", t.sent)
            add("undelivered", t.delivered, "SIM-UNDELIVERED")
        elif scenario == "delayed_delivery":
            add("sent", t.sent)
            add("delivered", t.delayed_delivered)
        elif scenario == "no_receipt":
            add("sent", t.sent)
        elif scenario == "out_of_order":
            add("delivered", t.sent)
            add("sent", t.delivered)

    async def pending_callbacks(self) -> list[SimulatedCallback]:
        now = self._clock()
        due = sorted((e for e in self._pending if e.due_at <= now), key=lambda e: e.due_at)
        self._pending = [e for e in self._pending if e.due_at > now]
        return [self._status_callback(e) for e in due]

    def _status_callback(self, event: _Scheduled) -> SimulatedCallback:
        payload: dict[str, Any] = {
            "kind": "status",
            "event_id": event.event_id,
            "message_id": event.message_id,
            "status": event.status,
            "error_code": event.error_code,
            "sms_id": str(event.correlation_id),
            "occurred_at": event.due_at.isoformat(),
        }
        return self._signed("status", payload)

    def build_inbound_callback(
        self, *, from_phone: str, to_number: str, body: str, message_id: str | None = None
    ) -> SimulatedCallback:
        """A simulated reply. Reusing message_id replays the same event (duplicate testing)."""
        payload: dict[str, Any] = {
            "kind": "inbound",
            "event_id": message_id or f"{SIM_ID_PREFIX}IN-{self._new_id()}",
            "from": from_phone,
            "to": to_number,
            "body": body,
            "received_at": self._clock().isoformat(),
        }
        return self._signed("inbound", payload)

    def _signed(self, kind: str, payload: dict[str, Any]) -> SimulatedCallback:
        raw = json.dumps(payload, sort_keys=True).encode()
        timestamp = str(int(self._clock().timestamp()))
        return SimulatedCallback(
            kind="status" if kind == "status" else "inbound",
            raw_body=raw,
            headers={
                TIMESTAMP_HEADER: timestamp,
                SIGNATURE_HEADER: sign(self._secret, timestamp, raw),
                "content-type": "application/json",
            },
        )

    async def get_message_status(self, provider_message_id: str) -> ProviderStatusSnapshot:
        record = self._records.get(provider_message_id)
        if record is None:
            raise ProviderError("permanent", "SIM-UNKNOWN", "Unknown simulated message")
        now = self._clock()
        status, error = "accepted", None
        rank = {"accepted": 1, "sent": 2, "delivered": 3, "undelivered": 3, "failed": 3}
        for event in record.events:
            if event.due_at <= now and rank[event.status] > rank[status]:
                status, error = event.status, event.error_code
        return ProviderStatusSnapshot(
            provider_message_id=provider_message_id,
            provider_status=status,
            mapped_status=_mapped(status),
            error_code=error,
        )

    # -- webhooks --------------------------------------------------------------------------

    async def validate_webhook(self, raw_body: bytes, headers: Mapping[str, str], url: str) -> bool:
        lowered = {k.lower(): v for k, v in headers.items()}
        signature = lowered.get(SIGNATURE_HEADER)
        timestamp = lowered.get(TIMESTAMP_HEADER)
        if not signature or not timestamp:
            return False
        try:
            age = abs(self._clock().timestamp() - int(timestamp))
        except ValueError:
            return False
        if age > SIGNATURE_TOLERANCE_SECONDS:
            return False
        return hmac.compare_digest(signature, sign(self._secret, timestamp, raw_body))

    @staticmethod
    def _load(raw_body: bytes) -> dict[str, Any]:
        try:
            data = json.loads(raw_body)
        except ValueError as exc:
            raise WebhookError("malformed simulated payload") from exc
        if not isinstance(data, dict):
            raise WebhookError("malformed simulated payload")
        return data

    async def parse_inbound_message(
        self, raw_body: bytes, headers: Mapping[str, str]
    ) -> InboundSmsEvent:
        data = self._load(raw_body)
        try:
            return InboundSmsEvent(
                provider_message_id=str(data["event_id"]),
                from_phone=str(data["from"]),
                to_number=str(data["to"]),
                body=str(data.get("body", "")),
                received_at=datetime.fromisoformat(str(data["received_at"])),
                dedupe_key=str(data["event_id"]),
            )
        except (KeyError, ValueError) as exc:
            raise WebhookError("malformed simulated inbound payload") from exc

    async def parse_status_callback(
        self, raw_body: bytes, headers: Mapping[str, str], query: Mapping[str, str]
    ) -> ProviderStatusEvent:
        data = self._load(raw_body)
        try:
            status = str(data["status"])
            correlation = data.get("sms_id")
            return ProviderStatusEvent(
                provider_message_id=str(data["message_id"]),
                provider_status=status,
                mapped_status=_mapped(status),
                error_code=data.get("error_code"),
                occurred_at=datetime.fromisoformat(str(data["occurred_at"])),
                dedupe_key=str(data["event_id"]),
                correlation_id=UUID(str(correlation)) if correlation else None,
            )
        except (KeyError, ValueError) as exc:
            raise WebhookError("malformed simulated status payload") from exc

    async def get_country_capabilities(self, country_code: str) -> ProviderCountryInfo:
        return ProviderCountryInfo(
            country_code=country_code.upper(),
            source="simulation",
            inbound_supported=True,
            notes="Simulation accepts every destination. This is not evidence of real coverage.",
        )


_KNOWN: dict[str, DeliveryStatus] = {
    "accepted": "accepted",
    "sent": "sent",
    "delivered": "delivered",
    "undelivered": "undelivered",
    "failed": "failed",
}


def _mapped(status: str) -> DeliveryStatus | None:
    return _KNOWN.get(status)
