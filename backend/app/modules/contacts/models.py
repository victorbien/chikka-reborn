"""ORM mappings for the contacts tables (schema owned by supabase/migrations/..._contacts.sql)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    owner_id: Mapped[UUID]
    contact_type: Mapped[str] = mapped_column(Text)
    contact_user_id: Mapped[UUID | None]
    phone_e164: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    is_favourite: Mapped[bool] = mapped_column(server_default=FetchedValue())
    muted_until: Mapped[datetime | None]
    muted_indefinitely: Mapped[bool] = mapped_column(server_default=FetchedValue())
    recent_cleared_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )


class ContactRequest(Base):
    __tablename__ = "contact_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    from_user_id: Mapped[UUID]
    to_user_id: Mapped[UUID]
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    expires_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    responded_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )


class ContactGroup(Base):
    __tablename__ = "contact_groups"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    owner_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )


class ContactGroupMember(Base):
    __tablename__ = "contact_group_members"

    group_id: Mapped[UUID] = mapped_column(primary_key=True)
    contact_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    position: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class UserBlock(Base):
    __tablename__ = "user_blocks"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    blocker_id: Mapped[UUID]
    blocked_user_id: Mapped[UUID | None]
    blocked_phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
