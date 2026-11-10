---
inclusion: always
---

# Backend Guidelines

Detailed docs: `docs/architecture/backend-architecture.md`, `docs/api-design.md`, `docs/api/*.md`, `docs/deployment/monitoring-and-logging.md`.

## API Structure

- Routers per module in `modules/<name>/router.py`, mounted under `/api/v1/`.
- Handlers are thin: parse input, call a service, return a response model.
- Consistent error envelope and `request_id` in every response (see `coding-standards.md`).
- Webhooks live under `/api/v1/webhooks/<provider>` and are separate from user-facing routes.

## Service and Repository Boundaries

- Services hold business rules, authorisation checks, and transaction boundaries.
- Repositories are the only layer touching SQLAlchemy; they return domain objects or schemas, not query builders.
- Services call other modules' services, never their repositories.
- Providers (SMS, AI) are injected through interfaces. Routers never call providers directly.

## Validation

- Pydantic models validate all requests, responses, settings, and webhook payloads.
- Validate phone numbers (E.164), message length, language codes, and pagination bounds.
- Treat all external input as untrusted. Reject unknown fields where practical.

## Dependency Injection

- Use FastAPI `Depends` for DB session, current user, settings, rate limiter, and providers.
- Provider selection (mock vs live) happens in one factory driven by configuration. If live fails to initialise, fail explicitly; never fall back to simulation silently.
- Tests override dependencies rather than patching globals.

## Background Processing

- Use background tasks or a queue for SMS dispatch, status reconciliation, retries, and AI calls.
- Jobs are idempotent, carry idempotency keys, use exponential backoff with jitter, and have configurable max attempts.
- Permanent failures are recorded, credits refunded, and the user notified.
- No blocking I/O in async handlers.

## Logging and Observability

- Structured JSON logs with request ID, user ID (where safe), module, and error type.
- Mask phone numbers. Never log message bodies, AI content, tokens, or secrets.
- Expose health/readiness endpoints. Track metrics: send latency, failure rate, delivery rate, webhook errors, AI token usage.
- Log provider errors server-side; return generic messages to clients.
