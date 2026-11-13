from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnvironment = Literal["development", "test", "staging", "production"]
SmsProviderMode = Literal["mock", "live"]


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables (and a local .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "chikka-reborn-api"
    app_version: str = "0.1.0"
    app_env: AppEnvironment = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # NoDecode lets us accept a plain comma-separated string instead of JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    database_url: str | None = None
    supabase_url: str | None = None
    # Legacy shared secret: verifies HS256 access tokens.
    supabase_jwt_secret: SecretStr | None = None
    # Public signing keys: verify ES256/RS256 access tokens. Defaults to the project's JWKS URL.
    supabase_jwks_url: str | None = None
    # Public anon key: identifies the project to GoTrue for user-level calls.
    supabase_anon_key: SecretStr | None = None
    # Backend-only. Used for admin calls (ban user) and Storage writes. Never sent to the browser.
    supabase_service_role_key: SecretStr | None = None
    avatar_bucket: str = "avatars"
    attachment_bucket: str = "message-attachments"

    # Keys the HMACs for rate-limit subjects and OTP hashes. Required outside dev/test.
    app_secret_key: SecretStr | None = None

    # Where email links point (the SPA) and what the refresh cookie may do.
    frontend_base_url: str = "http://localhost:5173"
    cookie_secure: bool | None = None
    terms_version: str = "2026-11-01"
    privacy_version: str = "2026-11-01"

    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=20, ge=0, le=100)

    sms_provider_mode: SmsProviderMode = "mock"
    sms_live_confirmed: bool = False

    # Live SMS (Twilio). Credentials are backend-only and never sent to the browser or logged.
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    # Public HTTPS origin of this backend. Twilio signs the exact URL it calls, so the webhook
    # signature URL is built from this value and never from request headers.
    sms_public_base_url: str | None = None
    # Keys the simulation signer. A random per-process value is used when unset.
    sms_mock_webhook_secret: SecretStr | None = None
    # Background worker: dispatch, retries, reconciliation, simulated callbacks.
    sms_worker_enabled: bool = True
    sms_worker_poll_seconds: float = Field(default=1.0, gt=0, le=60)
    sms_ambiguous_window_seconds: int = Field(default=900, ge=1)
    sms_queue_max_age_seconds: int = Field(default=86400, ge=60)
    sms_attestation_version: str = "2026-11-01"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_origin(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed")
        return value

    @field_validator(
        "database_url",
        "supabase_url",
        "supabase_jwt_secret",
        "supabase_jwks_url",
        "supabase_anon_key",
        "supabase_service_role_key",
        "app_secret_key",
        "cookie_secure",
        "twilio_account_sid",
        "twilio_auth_token",
        "sms_public_base_url",
        "sms_mock_webhook_secret",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        # A copied .env.example leaves blank values; treat them as not configured.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url")
    @classmethod
    def _use_async_driver(cls, value: str | None) -> str | None:
        if value is None:
            return None
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value.removeprefix(prefix)
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return value

    @model_validator(mode="after")
    def _live_sms_requires_confirmation(self) -> Self:
        # Never fall back silently: live mode needs an explicit operator opt-in.
        if self.sms_provider_mode == "live" and not self.sms_live_confirmed:
            raise ValueError("SMS_PROVIDER_MODE=live requires SMS_LIVE_CONFIRMED=true")
        return self

    @model_validator(mode="after")
    def _live_sms_requires_credentials(self) -> Self:
        # Fail at startup, loudly, rather than discovering missing credentials on first send.
        if self.sms_provider_mode == "live":
            missing = [
                name
                for name, value in (
                    ("TWILIO_ACCOUNT_SID", self.twilio_account_sid),
                    ("TWILIO_AUTH_TOKEN", self.twilio_auth_token),
                    ("SMS_PUBLIC_BASE_URL", self.sms_public_base_url),
                )
                if value is None
            ]
            if missing:
                raise ValueError("SMS_PROVIDER_MODE=live requires " + ", ".join(missing))
        return self

    @model_validator(mode="after")
    def _secret_key_required_outside_dev(self) -> Self:
        if self.app_env in ("staging", "production"):
            key = self.app_secret_key
            if key is None or len(key.get_secret_value()) < 32:
                raise ValueError("APP_SECRET_KEY (at least 32 characters) is required")
        return self

    @property
    def secure_cookies(self) -> bool:
        """Secure cookies everywhere except local http development, unless overridden."""
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env in ("staging", "production")

    @property
    def auth_issuer(self) -> str | None:
        """The `iss` claim Supabase Auth puts in this project's access tokens."""
        return f"{self.supabase_url.rstrip('/')}/auth/v1" if self.supabase_url else None

    @property
    def jwks_url(self) -> str | None:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        issuer = self.auth_issuer
        return f"{issuer}/.well-known/jwks.json" if issuer else None

    @property
    def sms_mode(self) -> Literal["simulation", "live"]:
        """Product-facing name: the mock provider is what the UI calls simulation."""
        return "live" if self.sms_provider_mode == "live" else "simulation"

    @property
    def docs_enabled(self) -> bool:
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
