# Backend Architecture

**Document:** CHKR-ARCH-004  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines the internal architecture of the Chikka Reborn FastAPI backend — its layer structure, module organisation, dependency injection, service contracts, and integration patterns with Supabase, Twilio, and Amazon Bedrock.

## Scope

`backend/` directory. All phases.

---

## 1. Technology Stack

| Technology | Version | Role |
|---|---|---|
| Python | 3.12+ | Language |
| FastAPI | 0.115+ | ASGI web framework |
| Pydantic | v2 | Request/response validation and serialisation |
| SQLAlchemy | 2.x (async) | ORM and database access |
| pydantic-settings | v2 | Environment-variable configuration |
| Uvicorn | Latest | ASGI server |
| Supabase Python | v2 | Auth JWT validation |
| httpx | Latest | Async HTTP client (for provider calls) |
| Ruff | Latest | Linting and formatting |
| mypy | Latest | Type checking in CI |

---

## 2. Directory Structure

```
backend/
├── main.py                        # App factory; lifespan; mount routers
├── config.py                      # pydantic-settings Settings class
├── database.py                    # Async SQLAlchemy engine + session factory
├── dependencies.py                # Shared FastAPI dependencies
│
├── api/
│   └── v1/
│       ├── router.py              # Aggregate all v1 routers
│       ├── auth.py                # /api/v1/auth/*
│       ├── users.py               # /api/v1/users/*
│       ├── contacts.py            # /api/v1/contacts/*
│       ├── conversations.py       # /api/v1/conversations/*
│       ├── messages.py            # /api/v1/messages/*
│       ├── sms.py                 # /api/v1/sms/*
│       ├── webhooks.py            # /api/v1/webhooks/*
│       ├── ai.py                  # /api/v1/ai/*
│       ├── credits.py             # /api/v1/credits/*
│       ├── notifications.py       # /api/v1/notifications/*
│       └── admin.py               # /api/v1/admin/*
│
├── services/
│   ├── auth_service.py
│   ├── user_service.py
│   ├── contact_service.py
│   ├── conversation_service.py
│   ├── message_service.py
│   ├── sms_service.py
│   ├── ai_service.py
│   ├── credit_service.py
│   ├── notification_service.py
│   └── admin_service.py
│
├── repositories/
│   ├── base_repository.py         # Generic async CRUD base
│   ├── user_repository.py
│   ├── contact_repository.py
│   ├── conversation_repository.py
│   ├── message_repository.py
│   ├── sms_repository.py
│   └── credit_repository.py
│
├── providers/
│   ├── sms/
│   │   ├── base.py                # SmsProvider ABC
│   │   ├── mock_provider.py       # MockSmsProvider
│   │   └── twilio_provider.py     # TwilioSmsProvider
│   └── ai/
│       ├── base.py                # AiProvider ABC
│       └── bedrock_provider.py    # BedrockAiProvider
│
├── models/
│   ├── db/                        # SQLAlchemy ORM models
│   │   ├── base.py                # Declarative base
│   │   ├── profile.py
│   │   ├── contact.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── outbound_sms.py
│   │   ├── inbound_sms.py
│   │   ├── credit.py
│   │   └── notification.py
│   └── schemas/                   # Pydantic request/response models
│       ├── auth.py
│       ├── user.py
│       ├── contact.py
│       ├── conversation.py
│       ├── message.py
│       ├── sms.py
│       ├── ai.py
│       ├── credit.py
│       └── admin.py
│
├── middleware/
│   ├── request_id.py              # Assigns X-Request-ID UUID
│   ├── logging.py                 # Structured JSON request logging
│   └── rate_limit.py              # Sliding window rate limiter
│
├── tasks/
│   ├── sms_retry.py               # Exponential backoff SMS retry
│   └── data_export.py             # Async user data export
│
├── exceptions.py                  # Typed domain exceptions
├── exception_handlers.py          # Maps exceptions to HTTP error responses
│
└── utils/
    ├── phone.py                   # E.164 validation, masking, parsing
    ├── sms_segments.py            # Segment count calculation (GSM-7 + Unicode)
    └── idempotency.py             # Idempotency key validation
```

---

## 3. Layered Architecture

```
┌────────────────────────────────────────────┐
│  HTTP Layer (api/v1/*.py)                  │
│  – Thin route handlers                     │
│  – Input validation via Pydantic           │
│  – Auth dependency injection               │
│  – No business logic                       │
└────────────────┬───────────────────────────┘
                 │ calls
┌────────────────▼───────────────────────────┐
│  Service Layer (services/*.py)             │
│  – Business logic and orchestration        │
│  – Raises typed domain exceptions          │
│  – Calls repositories and providers        │
│  – No direct HTTP concepts                 │
└────────────────┬──────────────┬────────────┘
                 │              │
    ┌────────────▼──┐    ┌──────▼─────────────┐
    │  Repository   │    │  Provider Layer     │
    │  Layer        │    │  (providers/*)      │
    │  (repos/*.py) │    │  – SmsProvider      │
    │  – DB queries │    │  – AiProvider       │
    │  – SQLAlchemy │    │  – Implement ABC    │
    └────────────┬──┘    └──────┬─────────────┘
                 │              │
    ┌────────────▼──┐    ┌──────▼─────────────┐
    │  Supabase DB  │    │  External Services  │
    │  PostgreSQL   │    │  Twilio / Bedrock   │
    └───────────────┘    └─────────────────────┘
```

**Rule:** No layer may bypass an intermediate layer. Route handlers do not call repositories. Services do not make direct HTTP calls to Twilio or Bedrock — they call provider abstractions.

---

## 4. Dependency Injection

FastAPI's dependency injection system (`Depends()`) provides:

```python
# dependencies.py

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an async SQLAlchemy session per request."""
    async with async_session_factory() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> Profile:
    """Validates Supabase JWT, returns authenticated user profile."""
    payload = verify_supabase_jwt(token)
    user = await user_repository.get_by_id(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=401)
    return user

async def get_admin_user(
    current_user: Profile = Depends(get_current_user),
) -> Profile:
    """Ensures the current user has admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403)
    return current_user

def get_sms_provider() -> SmsProvider:
    """Returns MockSmsProvider or TwilioSmsProvider based on SMS_PROVIDER_MODE."""
    mode = settings.SMS_PROVIDER_MODE
    if mode == "live":
        return TwilioSmsProvider(settings)
    return MockSmsProvider()
```

---

## 5. Provider Abstraction Contracts

### SmsProvider ABC

```python
# providers/sms/base.py
from abc import ABC, abstractmethod

class SmsProvider(ABC):
    @abstractmethod
    async def send_message(
        self, to: str, body: str, from_: str, idempotency_key: str
    ) -> SmsResult: ...

    @abstractmethod
    async def get_message_status(
        self, provider_message_id: str
    ) -> SmsStatus: ...

    @abstractmethod
    async def validate_webhook_signature(
        self, payload: bytes, signature: str, url: str
    ) -> bool: ...

    @abstractmethod
    async def parse_inbound_webhook(
        self, payload: dict
    ) -> InboundSmsEvent: ...

    @abstractmethod
    async def parse_delivery_webhook(
        self, payload: dict
    ) -> DeliveryStatusEvent: ...
```

### AiProvider ABC

```python
# providers/ai/base.py
from abc import ABC, abstractmethod

class AiProvider(ABC):
    @abstractmethod
    async def suggest_replies(
        self, context: list[str], count: int = 3
    ) -> list[str]: ...

    @abstractmethod
    async def translate(
        self, text: str, target_language: str, source_language: str | None = None
    ) -> str: ...

    @abstractmethod
    async def rewrite(
        self, text: str, instruction: RewriteInstruction
    ) -> str: ...

    @abstractmethod
    async def optimise_sms(
        self, text: str, max_segments: int, encoding: SmsEncoding
    ) -> SmsOptimisationResult: ...

    @abstractmethod
    async def summarise(
        self, messages: list[str]
    ) -> str: ...

    @abstractmethod
    async def compose(
        self, prompt: str, context: list[str] | None = None
    ) -> str: ...
```

---

## 6. Configuration Management

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # SMS
    sms_provider_mode: Literal["mock", "live"] = "mock"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_webhook_secret: str = ""

    # AI
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    bedrock_model_id: str = ""

    # App
    log_level: str = "INFO"
    rate_limit_login: int = 5

    class Config:
        env_file = ".env"

    def __init__(self, **data):
        super().__init__(**data)
        # Fail fast: validate required fields
        if self.sms_provider_mode == "live":
            assert self.twilio_account_sid, "TWILIO_ACCOUNT_SID required in live mode"
            assert self.twilio_auth_token, "TWILIO_AUTH_TOKEN required in live mode"

settings = Settings()
```

---

## 7. Middleware Stack

Middleware is applied in this order (outermost first):

1. **CORS** — allows configured frontend origins only.
2. **Request ID** — assigns `X-Request-ID` UUID.
3. **Structured Logging** — logs request start/end with timing.
4. **Rate Limiting** — checks and enforces per-route limits.
5. **Route Handler** — processes the request.

---

## 8. Exception Architecture

```python
# exceptions.py — typed domain exceptions

class ChikkaError(Exception):
    """Base exception for all domain errors."""
    code: str
    http_status: int

class InsufficientCreditsError(ChikkaError):
    code = "INSUFFICIENT_CREDITS"
    http_status = 422

class PhoneNotVerifiedError(ChikkaError):
    code = "PHONE_NOT_VERIFIED"
    http_status = 422

class SmsCountryUnsupportedError(ChikkaError):
    code = "SMS_COUNTRY_UNSUPPORTED"
    http_status = 422

class PhoneOptedOutError(ChikkaError):
    code = "PHONE_OPTED_OUT"
    http_status = 422

class WebhookSignatureInvalidError(ChikkaError):
    code = "WEBHOOK_SIGNATURE_INVALID"
    http_status = 403

class SmsProviderError(ChikkaError):
    code = "PROVIDER_ERROR"
    http_status = 502
```

The global exception handler in `exception_handlers.py` maps all `ChikkaError` subclasses to the standard error response JSON structure.

---

## 9. Async Patterns

- All route handlers are `async def`.
- All repository methods use `async with session.begin()` for transactions.
- All provider calls use `httpx.AsyncClient`.
- No blocking I/O in any async function.
- CPU-bound tasks (segment count calculation) are synchronous but lightweight; no thread pool needed.
- Long-running tasks (retry scheduling, export generation) use FastAPI `BackgroundTasks`.

---

## 10. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
