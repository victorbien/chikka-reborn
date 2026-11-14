"""Request and response models for /api/v1/notifications."""

from datetime import datetime, time
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.notifications.preferences import NotificationType


class NotificationOut(BaseModel):
    id: UUID
    type: NotificationType
    title: str
    body: str | None
    reference_type: str | None
    reference_id: UUID | None
    # How many events a grouped notification stands for (for example 3 new messages).
    occurrence_count: int
    is_read: bool
    created_at: datetime


class UnreadCountOut(BaseModel):
    unread_count: int


class MarkAllReadOut(BaseModel):
    updated: int
    unread_count: int


class PreferenceTypeOut(BaseModel):
    type: NotificationType
    in_app: bool
    push: bool
    email: bool
    # True for notices that cannot be switched off in the app.
    in_app_locked: bool


class PreferencesOut(BaseModel):
    types: list[PreferenceTypeOut]
    quiet_hours_start: str | None
    quiet_hours_end: str | None
    show_previews: bool
    low_balance_threshold_units: int
    low_balance_threshold_credits: float
    # True when email is switched off for this account after repeated delivery failures.
    email_disabled: bool
    # True when emails are not really sent (mock provider).
    email_simulated: bool


class ChannelPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_app: bool | None = None
    push: bool | None = None
    email: bool | None = None


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    types: dict[NotificationType, ChannelPatch] | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    show_previews: bool | None = None
    # 1 to 100 credits.
    low_balance_threshold_units: int | None = Field(default=None, ge=100, le=10000)

    @model_validator(mode="after")
    def _quiet_hours_pair(self) -> Self:
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValueError("Set both quiet hours times, or neither to turn quiet hours off")
        return self


class AnnouncementRequest(BaseModel):
    """An administrator's notice. No user_id means every active user."""

    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    user_id: UUID | None = None


class AnnouncementOut(BaseModel):
    recipients: int
    created: int
