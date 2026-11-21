"""ORM mappings for conversations and messages (schema owned by supabase/migrations)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    conversation_type: Mapped[str] = mapped_column(Text)
    direct_key: Mapped[str] = mapped_column(Text)
    remote_phone: Mapped[str | None] = mapped_column(Text)
    last_seq: Mapped[int] = mapped_column(server_default=FetchedValue())
    last_message_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    conversation_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    left_at: Mapped[datetime | None]
    last_read_seq: Mapped[int] = mapped_column(server_default=FetchedValue())
    last_read_at: Mapped[datetime | None]
    is_pinned: Mapped[bool] = mapped_column(server_default=FetchedValue())
    is_archived: Mapped[bool] = mapped_column(server_default=FetchedValue())
    muted_until: Mapped[datetime | None]
    muted_indefinitely: Mapped[bool] = mapped_column(server_default=FetchedValue())
    cleared_before_seq: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    conversation_id: Mapped[UUID]
    # Assigned by the trg_messages_assign_seq trigger.
    seq: Mapped[int] = mapped_column(server_default=FetchedValue())
    channel: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(Text)
    sender_user_id: Mapped[UUID | None]
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    status_version: Mapped[int] = mapped_column(server_default=FetchedValue())
    idempotency_key: Mapped[UUID | None]
    request_hash: Mapped[str | None] = mapped_column(Text)
    attachment_count: Mapped[int] = mapped_column(server_default=FetchedValue())
    suppressed_at: Mapped[datetime | None]
    suppressed_reason: Mapped[str | None] = mapped_column(Text)
    edited_at: Mapped[datetime | None]
    deleted_for_everyone_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )


class MessageDelivery(Base):
    """One row per recipient for a chikka message: sent -> delivered -> read (forward only,
    enforced by a trigger that also projects the status onto messages.status)."""

    __tablename__ = "message_deliveries"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    message_id: Mapped[UUID]
    attempt_number: Mapped[int] = mapped_column(server_default=FetchedValue())
    channel: Mapped[str] = mapped_column(Text)
    recipient_user_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None]
    delivered_at: Mapped[datetime | None]
    read_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    conversation_id: Mapped[UUID]
    uploader_id: Mapped[UUID]
    message_id: Mapped[UUID | None]
    storage_path: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
