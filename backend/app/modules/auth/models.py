from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PhoneNumber(Base):
    """public.phone_numbers. otp_hash holds a keyed hash, never the code."""

    __tablename__ = "phone_numbers"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    user_id: Mapped[UUID]
    e164: Mapped[str] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(String(2))
    verification_mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    otp_hash: Mapped[str | None] = mapped_column(Text)
    otp_expires_at: Mapped[datetime | None]
    otp_attempts: Mapped[int] = mapped_column(SmallInteger)
    otp_sent_count: Mapped[int] = mapped_column(SmallInteger)
    otp_window_started_at: Mapped[datetime | None]
    last_otp_sent_at: Mapped[datetime | None]
    verified_at: Mapped[datetime | None]
    released_at: Mapped[datetime | None]
    # Database defaults and the set_updated_at trigger own these.
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
