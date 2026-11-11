---
inclusion: always
---

# Architecture

Detailed docs: `docs/architecture.md`, `docs/architecture/system-architecture.md`, `application-architecture.md`, `backend-architecture.md`, `frontend-architecture.md`, `sms-gateway-architecture.md`, `ai-architecture.md`, `security-architecture.md`, `architecture-decisions.md`.

## Modular Monolith

One deployable frontend (React SPA) and one deployable backend (FastAPI). No microservices without a documented scaling or isolation requirement recorded as an ADR.

## Module Boundaries

Modules follow project-overview IDs: auth (A), contacts (B), chat (C), sms_outbound (D), sms_inbound (E), ai (F), notifications (G), credits (H), privacy (I), admin (J), display_mode (K).

- Each backend module lives in `backend/app/modules/<name>/` with `router`, `schemas`, `service`, `repository`, `models`.
- Each frontend module lives in `frontend/src/features/<name>/`.
- A module exposes a public interface (service functions or `index.ts`). Others must not import its internals or query its tables directly.

## Responsibilities

- Frontend: presentation, input validation (Zod), server state caching, WebSocket subscription. No business rules, no provider credentials, no direct SMS or AI calls.
- Backend: authorisation, business rules, SMS and AI provider calls, webhooks, credits, audit.
- Supabase: Postgres, Auth, Realtime, RLS, Storage. RLS is the last line of defence, not a substitute for backend checks.

## Integration Patterns

- External systems (SMS, AI) sit behind provider interfaces in `backend/app/integrations/`. Services depend on the interface, never the vendor SDK.
- Cross-module calls go through service interfaces. Cross-module side effects use internal domain events.
- Inbound webhooks: verify signature, persist raw event, enqueue processing, return 2xx quickly.

## Asynchronous Messaging

- Sending SMS and calling AI never block request handlers. Persist the message as `queued`, enqueue a background job, return the message ID.
- Status moves forward through provider callbacks and is pushed to clients via WebSocket/Realtime.
- Jobs are idempotent, retried with exponential backoff and jitter, and end in an explicit permanent-failure state.
- Real-time chat uses WebSockets/Supabase Realtime; clients reconcile via REST on reconnect.

## Dependency Rules

- Direction: router -> service -> repository -> database. Never upward.
- Routers contain no business logic. Services contain no HTTP concerns. Repositories contain no business rules.
- Integrations depend on nothing in modules; modules depend on integration interfaces.
- No circular module dependencies. If two modules need each other, extract an interface or event.
- Frontend features do not import from other features; shared code goes in `shared/` or `components/ui/`.
- Changes that alter these rules require an ADR first (see `documentation.md`).
