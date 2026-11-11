from typing import Any, Literal
from uuid import UUID

import jwt
from pydantic import BaseModel, ConfigDict

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ServiceUnavailableError

UserRole = Literal["user", "admin"]
AccountStatus = Literal["pending_verification", "active", "suspended", "deleted"]

# Supabase issues access tokens with this audience.
SUPABASE_AUDIENCE = "authenticated"


class TokenClaims(BaseModel):
    """What a verified access token proves: who, and which Supabase Auth session."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    session_id: UUID
    email: str | None = None


class AuthenticatedUser(BaseModel):
    """The caller, built from a verified token plus the database. Never from client input.

    Role and status come from public.profiles on every request (JWT metadata is not trusted).
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    session_id: UUID
    email: str | None
    role: UserRole
    status: AccountStatus
    onboarded: bool


def decode_access_token(token: str, settings: Settings) -> TokenClaims:
    """Verify signature, expiry and audience, then extract identity. Denies by default."""
    if settings.supabase_jwt_secret is None:
        raise ServiceUnavailableError(
            "Authentication is not configured.", details={"reason": "auth_not_configured"}
        )
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.supabase_jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience=SUPABASE_AUDIENCE,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(
            "Your session has expired. Please sign in again.", code="token_expired"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("The access token is not valid.") from exc

    try:
        user_id = UUID(str(claims["sub"]))
        session_id = UUID(str(claims["session_id"]))
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("The access token is not valid.") from exc

    email = claims.get("email")
    return TokenClaims(
        user_id=user_id,
        session_id=session_id,
        email=email if isinstance(email, str) and email else None,
    )
