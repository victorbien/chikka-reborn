"""Request and response models for Modules D and E (SMS)."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.sanitize import clean_text
from app.modules.credits.schemas import BalanceHint

MAX_SMS_BODY_CHARS = 1600

SmsMessageStatus = Literal[
    "queued", "retrying", "accepted", "sent", "delivered", "undelivered", "failed", "received"
]
Availability = Literal["available", "simulation_only", "unavailable"]
Replies = Literal["supported", "unverified", "unsupported"]
DeliveryConfirmation = Literal["confirmed", "pending", "unconfirmed", "not_applicable"]


class RecipientFields(BaseModel):
    """Exactly one way to name the recipient. The server resolves it; the client never sends a
    user id, and a phone number is only used after validation."""

    model_config = ConfigDict(extra="forbid")

    to: str | None = Field(default=None, max_length=32)
    # ISO 3166-1 alpha-2 from the country selector; lets users type a local format.
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    contact_id: UUID | None = None
    conversation_id: UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "RecipientFields":
        named = [v for v in (self.to, self.contact_id, self.conversation_id) if v is not None]
        if len(named) != 1:
            raise ValueError(
                "Name the recipient with exactly one of to, contact_id, conversation_id"
            )
        return self


def _clean(value: str) -> str:
    # clean_text strips markup and control characters; keep inner newlines as typed.
    return clean_text(value)


class QuoteRequest(RecipientFields):
    body: str = Field(default="", max_length=MAX_SMS_BODY_CHARS * 2)

    @field_validator("body")
    @classmethod
    def _body(cls, value: str) -> str:
        return _clean(value)


class SendSmsRequest(RecipientFields):
    body: Annotated[str, Field(min_length=1, max_length=MAX_SMS_BODY_CHARS * 2)]
    # The user reviewed and confirmed the final text, recipient and cost (FR-SMS-008).
    confirmed: Literal[True]

    @field_validator("body")
    @classmethod
    def _body(cls, value: str) -> str:
        cleaned = _clean(value)
        if not cleaned:
            raise ValueError("Write a message")
        if len(cleaned) > MAX_SMS_BODY_CHARS:
            raise ValueError(f"Messages can be at most {MAX_SMS_BODY_CHARS} characters")
        return cleaned


class RetrySmsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: Literal[True]


class ConsentRequest(RecipientFields):
    decision: Literal["granted", "withdrawn"]


class MarkSmsReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    up_to_seq: Annotated[int, Field(ge=0)]


class SimulateInboundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_phone: str = Field(max_length=32)
    to_number: str = Field(max_length=32)
    body: str = Field(max_length=MAX_SMS_BODY_CHARS)
    # Reuse an earlier id to replay the same event and test duplicate handling.
    replay_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")


# -- responses ----------------------------------------------------------------------------


class SmsModeOut(BaseModel):
    mode: Literal["simulation", "live"]
    provider: str
    is_simulated: bool
    outbound_paused: bool
    sender_verified: bool
    notice: str


class RecipientOut(BaseModel):
    masked_phone: str
    country_code: str
    country_name: str | None
    number_type: str
    contact_id: UUID | None = None
    display_name: str | None = None
    conversation_id: UUID | None = None


class SegmentOut(BaseModel):
    encoding: Literal["gsm7", "ucs2"]
    characters: int
    units: int
    segments: int
    per_segment: int
    remaining_in_segment: int
    max_segments: int
    too_long: bool


class CostOut(BaseModel):
    units: int | None
    credits: float | None
    # configured | demo_default (simulation only) | unavailable
    source: Literal["configured", "demo_default", "unavailable"]
    estimated: Literal[True] = True


class ConsentOut(BaseModel):
    required: bool
    granted: bool
    notice_version: str


class BlockerOut(BaseModel):
    code: str
    message: str


class QuoteOut(BaseModel):
    # Simulated credits only: what you have and whether this send is covered.
    balance: BalanceHint
    recipient: RecipientOut
    mode: Literal["simulation", "live"]
    is_simulated: bool
    availability: Availability
    replies: Replies
    warnings: list[str]
    segment: SegmentOut
    cost: CostOut
    consent: ConsentOut
    recipient_opted_out: bool
    blockers: list[BlockerOut]
    can_send: bool


class CountryOut(BaseModel):
    country_code: str
    country_name: str
    dial_code: int
    availability: Availability
    unavailable_reason: str | None
    outbound: str
    replies: Replies
    alphanumeric_sender_allowed: bool
    registered_sender_required: bool
    registered_sender_status: str
    supported_number_types: list[str]
    content_restrictions: str | None
    consent_required: bool
    credits_per_segment: float | None
    max_segments: int
    verified: bool
    notes: str | None


class FailureOut(BaseModel):
    code: str | None
    reason: str
    # A permanent failure will not be retried automatically. The user may resend.
    is_permanent: bool
    # True when the outcome is unknown: the message may still have been delivered.
    may_have_been_delivered: bool


class DeliveryOut(BaseModel):
    attempt_number: int
    provider: str | None
    accepted_at: datetime | None
    sent_at: datetime | None
    delivered_at: datetime | None
    next_attempt_at: datetime | None
    confirmation: DeliveryConfirmation


class SmsMessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    seq: int
    direction: Literal["outbound", "inbound"]
    is_mine: bool
    body: str | None
    status: SmsMessageStatus
    status_version: int
    is_simulated: bool
    encoding: str | None
    char_count: int | None
    segment_count: int | None
    created_at: datetime
    client_message_id: UUID | None = None
    delivery: DeliveryOut | None = None
    failure: FailureOut | None = None
    can_retry: bool = False
    attempt_count: int = 1


class SmsConversationOut(BaseModel):
    id: UUID
    masked_phone: str
    country_code: str | None
    display_name: str | None
    contact_id: UUID | None
    last_message_preview: str | None
    last_message_direction: Literal["outbound", "inbound"] | None
    last_message_status: SmsMessageStatus | None
    last_message_at: datetime | None
    last_is_simulated: bool
    unread_count: int
    is_archived: bool
    is_muted: bool
    replies: Replies


class SmsMessagePage(BaseModel):
    messages: list[SmsMessageOut]
    has_more_before: bool
    last_read_seq: int


class SmsReadState(BaseModel):
    conversation_id: UUID
    last_read_seq: int
    unread_count: int


class SendOut(BaseModel):
    message: SmsMessageOut
    quote: QuoteOut | None = None


class DeliveryEventOut(BaseModel):
    status: str
    source: str
    applied: bool
    occurred_at: datetime | None
    received_at: datetime


class SmsMessageDetail(BaseModel):
    message: SmsMessageOut
    events: list[DeliveryEventOut]
