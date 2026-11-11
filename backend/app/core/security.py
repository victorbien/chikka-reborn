from typing import Any, Literal

import jwt
from pydantic import BaseModel, ConfigDict

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ServiceUnavailableError

UserRole = Literal["user", "admin"]

# Supabase issues access tokens with this audience.
SUPABASE_AUDIENCE = "authenticated"


class AuthenticatedUser(BaseModel):
    """Identity derived from a verified Supabase access token. Never from client input."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str | None = None
    role: UserRole = "user"


def decode_access_token(token: str, settings: Settings) -> AuthenticatedUser:
    """Verify signature, expiry and audience, then build the user. Denies by default."""
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
        raise AuthenticationError("Your session has expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("The access token is not valid.") from exc

    # Roles come only from app_metadata, which users cannot edit. user_metadata is untrusted.
    app_metadata = claims.get("app_metadata")
    is_admin = isinstance(app_metadata, dict) and app_metadata.get("role") == "admin"
    email = claims.get("email")
    return AuthenticatedUser(
        id=str(claims["sub"]),
        email=email if isinstance(email, str) else None,
        role="admin" if is_admin else "user",
    )
