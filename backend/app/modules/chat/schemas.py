"""Request and response models for Module C (Chikka-to-Chikka messaging)."""

import re
import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_BODY_CHARS = 2000

# Server-side message states. "pending" (not yet stored) and "failed" (could not be stored)
# exist only on the sender's device. "delivered" means the recipient's app received the
# message; "read" is reported only when both people allow read receipts.
ChatMessageStatus = Literal["sent", "delivered", "read"]
ConversationPresence = Literal["online", "away", "busy", "offline", "unknown"]

# Control characters except tab and newline.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_body(value: str) -> str:
    """Message text is stored as typed (it is escaped when rendered), minus invisible
    control characters. Length is counted in Unicode code points, so one emoji is one."""
    return _CONTROL.sub("", unicodedata.normalize("NFC", value)).strip()


# -- people ----------------------------------------------------------------------------------


class Participant(BaseModel):
    user_id: UUID
    username: str | None
    display_name: str
    avatar_url: str | None
    presence: ConversationPresence
    is_contact: bool


# -- messages --------------------------------------------------------------------------------


class AttachmentOut(BaseModel):
    id: UUID
    file_name: str
    content_type: str
    size_bytes: int
    # Short-lived signed URL. Null when storage is unreachable; refetch to get a new one.
    url: str | None


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    seq: int
    sender_user_id: UUID
    is_mine: bool
    body: str | None
    attachments: list[AttachmentOut]
    created_at: datetime
    edited_at: datetime | None
    # Present on your own messages only.
    client_message_id: UUID | None = None
    status: ChatMessageStatus | None = None
    status_version: int | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None


class MessagePage(BaseModel):
    messages: list[MessageOut]
    # True when older messages exist before the first one returned.
    has_more_before: bool
    last_read_seq: int
    # The other person's read position, only when read receipts are on for both.
    peer_read_seq: int | None


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_message_id: UUID
    body: str | None = None
    attachment_ids: Annotated[list[UUID], Field(max_length=5)] = []

    @field_validator("body")
    @classmethod
    def _body(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = clean_body(value)
        if len(cleaned) > MAX_BODY_CHARS:
            raise ValueError(f"Messages can be at most {MAX_BODY_CHARS} characters")
        return cleaned or None

    @model_validator(mode="after")
    def _not_empty(self) -> "SendMessageRequest":
        if self.body is None and not self.attachment_ids:
            raise ValueError("Write a message or attach a file")
        if len(set(self.attachment_ids)) != len(self.attachment_ids):
            raise ValueError("Each attachment can be sent once")
        return self


class StatusChange(BaseModel):
    message_id: UUID
    conversation_id: UUID
    status: ChatMessageStatus
    status_version: int
    delivered_at: datetime | None
    read_at: datetime | None


# -- conversations ---------------------------------------------------------------------------


class LastMessage(BaseModel):
    id: UUID
    seq: int
    is_mine: bool
    preview: str
    has_attachments: bool
    created_at: datetime
    status: ChatMessageStatus | None = None


class ConversationSummary(BaseModel):
    id: UUID
    conversation_type: Literal["chikka"]
    participant: Participant
    last_message: LastMessage | None
    last_message_at: datetime | None
    unread_count: int
    is_archived: bool
    is_muted: bool
    can_send: bool
    # Why sending is off, in words the user can act on. Never reveals that you were blocked.
    cannot_send_reason: str | None


class OpenConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class ConversationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_archived: bool


class MarkReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    up_to_seq: Annotated[int, Field(ge=0)]


class ReadState(BaseModel):
    conversation_id: UUID
    last_read_seq: int
    unread_count: int


class UnreadTotals(BaseModel):
    unread_messages: int
    unread_conversations: int
