from datetime import UTC, datetime
from functools import lru_cache
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
    # When the token stops being valid. Long-lived connections (the WebSocket) enforce it.
    expires_at: datetime | None = None


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


# Supabase signs with ES256 (default for new signing keys) or RS256; legacy projects use HS256.
ASYMMETRIC_ALGORITHMS = frozenset({"ES256", "RS256"})
JWKS_CACHE_SECONDS = 600


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    """One cached client per JWKS URL. Keys are cached; an unknown `kid` triggers a refetch."""
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=JWKS_CACHE_SECONDS, timeout=5)


def _not_configured() -> ServiceUnavailableError:
    return ServiceUnavailableError(
        "Authentication is not configured.", details={"reason": "auth_not_configured"}
    )


def _verification_key(token: str, settings: Settings) -> tuple[Any, str, str | None]:
    """Pick the key for the token's algorithm. Returns (key, algorithm, expected issuer).

    Each algorithm is paired with exactly one key type, so a token cannot pick its own key:
    HS256 only ever uses the shared secret, ES256/RS256 only ever use a published public key.
    """
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("The access token is not valid.") from exc

    if algorithm == "HS256":
        if settings.supabase_jwt_secret is None:
            raise AuthenticationError("The access token is not valid.")
        return settings.supabase_jwt_secret.get_secret_value(), "HS256", None

    if algorithm in ASYMMETRIC_ALGORITHMS:
        url = settings.jwks_url
        if url is None:
            raise AuthenticationError("The access token is not valid.")
        try:
            signing_key = _jwks_client(url).get_signing_key_from_jwt(token)
        except jwt.PyJWKClientConnectionError as exc:
            # The keys could not be fetched: our problem, not a bad token.
            raise ServiceUnavailableError(
                "Sign-in is temporarily unavailable. Please try again shortly.",
                code="auth_unavailable",
                details={"reason": "auth_keys_unavailable"},
            ) from exc
        except (jwt.PyJWKClientError, jwt.InvalidTokenError) as exc:
            raise AuthenticationError("The access token is not valid.") from exc
        return signing_key.key, algorithm, settings.auth_issuer

    raise AuthenticationError("The access token is not valid.")


def decode_access_token(token: str, settings: Settings) -> TokenClaims:
    """Verify signature, expiry, audience (and issuer for asymmetric keys), then extract
    identity. Denies by default.

    May fetch the project's public keys over the network the first time; call it from a
    worker thread in async code.
    """
    if settings.supabase_jwt_secret is None and settings.jwks_url is None:
        raise _not_configured()
    key, algorithm, issuer = _verification_key(token, settings)
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            audience=SUPABASE_AUDIENCE,
            issuer=issuer,
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
    expires = claims.get("exp")
    return TokenClaims(
        user_id=user_id,
        session_id=session_id,
        expires_at=datetime.fromtimestamp(expires, UTC)
        if isinstance(expires, int | float)
        else None,
        email=email if isinstance(email, str) and email else None,
    )
