import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.sanitize import clean_text

# FR-AUTH-001 AC2. Matches supabase/config.toml (lower_upper_letters_digits, min 8).
# 72 bytes is the bcrypt input limit used by Supabase Auth.
_PASSWORD_RULES = (
    (re.compile(r"[a-z]"), "a lowercase letter"),
    (re.compile(r"[A-Z]"), "an uppercase letter"),
    (re.compile(r"[0-9]"), "a digit"),
)


def validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value.encode()) > 72:
        raise ValueError("Password must be at most 72 bytes")
    missing = [label for pattern, label in _PASSWORD_RULES if not pattern.search(value)]
    if missing:
        raise ValueError("Password needs " + ", ".join(missing))
    return value


def _normalise_email(value: str) -> str:
    return value.strip().lower()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=320)


class RegisterRequest(_Strict):
    email: EmailStr
    password: str = Field(max_length=200)
    display_name: str
    accept_terms: bool

    @field_validator("email")
    @classmethod
    def _v_email(cls, value: str) -> str:
        return _normalise_email(value)

    @field_validator("password")
    @classmethod
    def _v_password(cls, value: str) -> str:
        return validate_password(value)

    @field_validator("display_name")
    @classmethod
    def _v_display_name(cls, value: str) -> str:
        cleaned = clean_text(value)
        if not 2 <= len(cleaned) <= 50:
            raise ValueError("Display name must be 2 to 50 characters")
        return cleaned

    @field_validator("accept_terms")
    @classmethod
    def _v_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must accept the Terms and Privacy Notice")
        return value


class LoginRequest(_Strict):
    # Plain str: a malformed email must fail exactly like a wrong password (no enumeration
    # of the validation rules is possible, but the response shape stays identical anyway).
    email: str = Field(min_length=1)
    password: str = Field(min_length=1, max_length=200)


class EmailOnlyRequest(_Strict):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _v_email(cls, value: str) -> str:
        return _normalise_email(value)


class TokenHashRequest(_Strict):
    token_hash: str = Field(min_length=8, max_length=256, pattern=r"^[A-Za-z0-9_\-.]+$")


class ResetPasswordConfirmRequest(TokenHashRequest):
    new_password: str = Field(max_length=200)
    confirm_password: str = Field(max_length=200)

    @field_validator("new_password")
    @classmethod
    def _v_password(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def _passwords_match(self) -> "ResetPasswordConfirmRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LogoutRequest(_Strict):
    scope: Literal["local", "global"] = "local"


class PasswordConfirmation(_Strict):
    password: str = Field(min_length=1, max_length=200)


class DeleteAccountRequest(PasswordConfirmation):
    confirmation: Literal["DELETE"]


class SessionTokens(BaseModel):
    """Access token for memory only. The refresh token is set as an httpOnly cookie."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_in: int


class SessionInfo(BaseModel):
    id: UUID
    created_at: datetime
    last_active_at: datetime | None
    device: str
    ip_prefix: str | None
    current: bool


class AccountDeletedResponse(BaseModel):
    message: str
    deleted_at: datetime


# -- mobile verification ---------------------------------------------------------------


class PhoneStartRequest(_Strict):
    phone_number: str = Field(min_length=4, max_length=32)
    # Required only when replacing an already verified number (FR-AUTH-012 AC1).
    password: str | None = Field(default=None, max_length=200)


class PhoneConfirmRequest(_Strict):
    phone_number: str = Field(min_length=4, max_length=32)
    code: str = Field(pattern=r"^[0-9]{6}$")


class PhoneStartResponse(BaseModel):
    masked: str
    verification_mode: Literal["live", "simulated"]
    expires_in: int
    resend_available_in: int


class PhoneStatusResponse(BaseModel):
    verified: bool
    masked: str | None
    verification_mode: Literal["live", "simulated"] | None
    verified_at: datetime | None
    delivery_mode: Literal["live", "simulated"]


class SimulatedSmsMessage(BaseModel):
    label: Literal["SIMULATED"] = "SIMULATED"
    to: str
    body: str
    created_at: datetime
    expires_at: datetime
