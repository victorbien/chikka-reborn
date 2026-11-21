import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.sanitize import clean_text
from app.modules.profiles.reference import (
    RESERVED_USERNAMES,
    SUPPORTED_LANGUAGES,
    supported_regions,
    supported_time_zones,
)

Theme = Literal["system", "light", "dark"]
UiMode = Literal["modern", "classic"]
PresencePreference = Literal["online", "away", "busy", "invisible"]
PresenceStatus = Literal["online", "away", "busy", "invisible", "offline"]

_USERNAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def _display_name(value: str) -> str:
    cleaned = clean_text(value)
    if not 2 <= len(cleaned) <= 50:
        raise ValueError("Display name must be 2 to 50 characters")
    return cleaned


def _bio(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_text(value)
    if len(cleaned) > 160:
        raise ValueError("Bio must be at most 160 characters")
    return cleaned or None


def _status_message(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_text(value)
    if len(cleaned) > 80:
        raise ValueError("Status message must be at most 80 characters")
    return cleaned or None


def _country(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip().upper()
    if code not in supported_regions():
        raise ValueError("Unknown country code")
    return code


def _language(value: str) -> str:
    if value not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language")
    return value


def _time_zone(value: str) -> str:
    if value not in supported_time_zones():
        raise ValueError("Unknown time zone")
    return value


def validate_username(value: str) -> str:
    username = value.strip()
    if not _USERNAME.fullmatch(username):
        raise ValueError("Username must be 3 to 20 letters, digits or underscores")
    if username.lower() in RESERVED_USERNAMES:
        raise ValueError("This username is reserved")
    return username


class ProfileUpdateRequest(BaseModel):
    """PATCH /users/me. Every field optional; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    bio: str | None = None
    status_message: str | None = None
    country_code: str | None = None
    language: str | None = None
    time_zone: str | None = None
    theme: Theme | None = None
    ui_mode: UiMode | None = None

    @field_validator("display_name")
    @classmethod
    def _v_display_name(cls, value: str | None) -> str | None:
        return None if value is None else _display_name(value)

    @field_validator("bio")
    @classmethod
    def _v_bio(cls, value: str | None) -> str | None:
        return _bio(value)

    @field_validator("status_message")
    @classmethod
    def _v_status_message(cls, value: str | None) -> str | None:
        return _status_message(value)

    @field_validator("country_code")
    @classmethod
    def _v_country(cls, value: str | None) -> str | None:
        return _country(value)

    @field_validator("language")
    @classmethod
    def _v_language(cls, value: str | None) -> str | None:
        return None if value is None else _language(value)

    @field_validator("time_zone")
    @classmethod
    def _v_time_zone(cls, value: str | None) -> str | None:
        return None if value is None else _time_zone(value)


class OnboardingRequest(BaseModel):
    """POST /users/me/onboarding (FR-AUTH-015)."""

    model_config = ConfigDict(extra="forbid")

    username: str
    display_name: str
    country_code: str | None = None
    language: str = "en"
    time_zone: str = "UTC"
    ui_mode: UiMode = "modern"

    @field_validator("username")
    @classmethod
    def _v_username(cls, value: str) -> str:
        return validate_username(value)

    @field_validator("display_name")
    @classmethod
    def _v_display_name(cls, value: str) -> str:
        return _display_name(value)

    @field_validator("country_code")
    @classmethod
    def _v_country(cls, value: str | None) -> str | None:
        return _country(value)

    @field_validator("language")
    @classmethod
    def _v_language(cls, value: str) -> str:
        return _language(value)

    @field_validator("time_zone")
    @classmethod
    def _v_time_zone(cls, value: str) -> str:
        return _time_zone(value)


class PhoneSummary(BaseModel):
    masked: str
    verification_mode: Literal["live", "simulated"]
    verified_at: datetime


class ProfileResponse(BaseModel):
    id: UUID
    username: str | None
    display_name: str
    email: str | None
    email_verified: bool
    avatar_url: str | None
    bio: str | None
    status_message: str | None
    country_code: str | None
    language: str
    time_zone: str
    theme: Theme
    ui_mode: UiMode
    presence_preference: PresencePreference
    role: Literal["user", "admin"]
    status: Literal["pending_verification", "active", "suspended", "deleted"]
    onboarding_completed: bool
    phone: PhoneSummary | None
    created_at: datetime
    updated_at: datetime


ProfileVisibility = Literal["everyone", "contacts", "private"]
SharePresence = Literal["everyone", "contacts", "nobody"]


class PrivacySettings(BaseModel):
    """Who can find and see you (FR-PRIVACY-001, 005). Safe defaults live in the database."""

    profile_visibility: ProfileVisibility
    share_presence: SharePresence
    show_last_seen: bool
    discoverable_by_email: bool
    discoverable_by_phone: bool


class PrivacySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_visibility: ProfileVisibility | None = None
    share_presence: SharePresence | None = None
    show_last_seen: bool | None = None
    discoverable_by_email: bool | None = None
    discoverable_by_phone: bool | None = None

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> "PrivacySettingsUpdate":
        # Omit a field to leave it unchanged; an explicit null is never meaningful.
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class AvatarResponse(BaseModel):
    avatar_url: str | None


class PresenceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preference: PresencePreference


class HeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idle: bool = False


class PresenceResponse(BaseModel):
    status: PresenceStatus
    preference: PresencePreference
    last_seen_at: datetime | None
