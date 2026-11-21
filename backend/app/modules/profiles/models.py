from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Profile(Base):
    """public.profiles (schema owned by supabase/migrations). Rows are created by the
    on_auth_user_created trigger, never by the application, and never hard-deleted."""

    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    username: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_path: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2))
    language: Mapped[str] = mapped_column(Text)
    time_zone: Mapped[str] = mapped_column(Text)
    ui_mode: Mapped[str] = mapped_column(Text)
    theme: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    onboarding_completed_at: Mapped[datetime | None]
    status_message: Mapped[str | None] = mapped_column(Text)
    presence_preference: Mapped[str] = mapped_column(Text)
    profile_visibility: Mapped[str] = mapped_column(Text)
    share_presence: Mapped[str] = mapped_column(Text)
    show_last_seen: Mapped[bool]
    discoverable_by_phone: Mapped[bool]
    discoverable_by_email: Mapped[bool]
    send_typing_indicators: Mapped[bool]
    send_read_receipts: Mapped[bool]
    last_seen_at: Mapped[datetime | None]
    suspended_at: Mapped[datetime | None]
    deletion_requested_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]
    # Database defaults and the set_updated_at trigger own these.
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
