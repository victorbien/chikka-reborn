"""Turns database rows into API models. Shared by the service, the engine and realtime."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from app.core.privacy import mask_phone
from app.integrations.sms.errors import reason_for_any
from app.modules.sms.schemas import (
    DeliveryConfirmation,
    DeliveryOut,
    FailureOut,
    SmsMessageOut,
    SmsMessageStatus,
)

# After this long in "sent" without a receipt the UI says delivery is not confirmed.
UNCONFIRMED_AFTER = timedelta(hours=24)
PREVIEW_CHARS = 120


def preview(body: str | None) -> str | None:
    if not body:
        return None
    flat = " ".join(body.split())
    return flat if len(flat) <= PREVIEW_CHARS else flat[: PREVIEW_CHARS - 1] + "…"


def confirmation_for(status: str, sent_at: datetime | None, now: datetime) -> DeliveryConfirmation:
    if status == "delivered":
        return "confirmed"
    if status in ("failed", "undelivered", "received"):
        return "not_applicable"
    if status == "sent" and sent_at is not None and now - sent_at >= UNCONFIRMED_AFTER:
        return "unconfirmed"
    return "pending"


def render_message(row: Mapping[str, Any], viewer: UUID, now: datetime) -> SmsMessageOut:
    status = cast(SmsMessageStatus, row["status"])
    outbound = row["direction"] == "outbound"
    delivery: DeliveryOut | None = None
    failure: FailureOut | None = None
    if row["attempt_number"] is not None:
        delivery = DeliveryOut(
            attempt_number=row["attempt_number"],
            provider=row["provider"],
            accepted_at=row["accepted_at"],
            sent_at=row["sent_at"],
            delivered_at=row["delivered_at"],
            next_attempt_at=row["next_attempt_at"] if status in ("queued", "retrying") else None,
            confirmation=confirmation_for(status, row["sent_at"], now),
        )
    if outbound and status in ("failed", "undelivered"):
        failure = FailureOut(
            code=row["failure_code"],
            reason=reason_for_any(row["failure_code"]),
            is_permanent=bool(row["is_permanent"]),
            may_have_been_delivered=row["failure_class"] == "ambiguous",
        )
    return SmsMessageOut(
        id=row["id"],
        conversation_id=row["conversation_id"],
        seq=row["seq"],
        direction=row["direction"],
        is_mine=outbound and row["sender_user_id"] == viewer,
        body=row["body"],
        status=status,
        status_version=row["status_version"],
        is_simulated=row["is_simulated"],
        encoding=row["encoding"],
        char_count=row["char_count"],
        segment_count=row["segment_count"],
        created_at=row["created_at"],
        client_message_id=row["idempotency_key"] if outbound else None,
        delivery=delivery,
        failure=failure,
        can_retry=outbound and status in ("failed", "undelivered"),
        attempt_count=row["attempt_number"] or 1,
    )


def masked(phone: str) -> str:
    return mask_phone(phone)
