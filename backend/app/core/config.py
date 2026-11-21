from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnvironment = Literal["development", "test", "staging", "production"]
SmsProviderMode = Literal["mock", "live"]
AiProviderMode = Literal["mock", "bedrock"]
EmailProviderMode = Literal["mock", "smtp"]


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

    # AI assistant. "mock" returns canned drafts and calls nothing external. "bedrock" calls
    # Amazon Bedrock and refuses to start when it is not fully configured.
    ai_provider_mode: AiProviderMode = "mock"
    bedrock_region: str | None = None
    bedrock_model_id: str | None = None
    # Backend-only Bedrock API key (sent as a bearer token). Never logged or sent to the browser.
    bedrock_api_key: SecretStr | None = None
    ai_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    ai_max_output_tokens: int = Field(default=600, ge=50, le=4000)
    # Optional list prices (USD per 1,000 tokens) so the admin dashboard can show an approximate
    # cost. Unset means no cost figure is shown; nothing is guessed.
    ai_cost_per_1k_input_usd: float | None = Field(default=None, ge=0)
    ai_cost_per_1k_output_usd: float | None = Field(default=None, ge=0)

    # Notifications: the worker announces new notifications to open sessions and sends emails.
    notifications_worker_enabled: bool = True
    notifications_worker_poll_seconds: float = Field(default=1.0, gt=0, le=60)
    # "mock" sends nothing. "smtp" needs SMTP_HOST and EMAIL_FROM_ADDRESS and fails at startup
    # without them; it never falls back to the mock.
    email_provider_mode: EmailProviderMode = "mock"
    email_from_address: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True

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
        "bedrock_region",
        "bedrock_model_id",
        "bedrock_api_key",
        "email_from_address",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "ai_cost_per_1k_input_usd",
        "ai_cost_per_1k_output_usd",
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
    def _smtp_requires_configuration(self) -> Self:
        if self.email_provider_mode == "smtp":
            missing = [
                name
                for name, value in (
                    ("SMTP_HOST", self.smtp_host),
                    ("EMAIL_FROM_ADDRESS", self.email_from_address),
                )
                if value is None
            ]
            if missing:
                raise ValueError("EMAIL_PROVIDER_MODE=smtp requires " + ", ".join(missing))
        return self

    @model_validator(mode="after")
    def _bedrock_requires_configuration(self) -> Self:
        # Same rule as live SMS: fail at startup, never fall back to the mock silently.
        if self.ai_provider_mode == "bedrock":
            missing = [
                name
                for name, value in (
                    ("BEDROCK_REGION", self.bedrock_region),
                    ("BEDROCK_MODEL_ID", self.bedrock_model_id),
                    ("BEDROCK_API_KEY", self.bedrock_api_key),
                )
                if value is None
            ]
            if missing:
                raise ValueError("AI_PROVIDER_MODE=bedrock requires " + ", ".join(missing))
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
