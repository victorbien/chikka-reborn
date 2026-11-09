# Architecture Decisions

**Document:** CHKR-ARCH-009  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document records all significant architectural decisions made for Chikka Reborn using the Architecture Decision Record (ADR) format. Each decision records the context, the options considered, the chosen option, the rationale, and the consequences.

## Scope

All architectural decisions from Phase 0 onwards. New decisions are appended; existing decisions are never deleted (only superseded by a new ADR).

---

## ADL-001 — Modular Monolith Over Microservices

**Date:** November 2026  
**Status:** Accepted  
**Deciders:** Principal Architect  

### Context
Chikka Reborn has multiple distinct domains: auth, messaging, SMS, AI, credits, notifications, admin. A question arose about whether to structure the backend as microservices (one per domain) or as a single deployable unit.

### Options Considered
1. Microservices — one service per domain.
2. Modular monolith — single deployable with internal module boundaries.
3. Serverless functions — one function per endpoint.

### Decision
**Modular monolith.**

### Rationale
- Microservices introduce distributed systems complexity (inter-service auth, distributed tracing, network latency, deployment choreography) that is unjustified for a platform at this scale and team size.
- Serverless cold starts are incompatible with WebSocket connections and long-lived processes.
- A modular monolith with enforced boundary rules gives the same separation of concerns as microservices with none of the operational overhead.
- The architecture is designed so that individual modules can be extracted into separate services if specific scaling requirements emerge in the future.

### Consequences
- Single FastAPI process per environment.
- Module boundaries enforced by directory structure and import rules, not network calls.
- Simpler CI/CD, debugging, and local development.
- Must monitor for module boundary violations during code review.

---

## ADL-002 — Supabase Realtime for Phase 1 WebSocket

**Date:** November 2026  
**Status:** Accepted  
**Deciders:** Principal Architect  

### Context
Real-time message delivery requires WebSocket connections. Options include building a custom WebSocket server or using a managed service.

### Options Considered
1. Custom FastAPI WebSocket endpoint with Redis pub/sub.
2. Supabase Realtime (managed WebSocket via PostgreSQL NOTIFY).
3. Pusher / Ably (third-party managed WebSocket).

### Decision
**Supabase Realtime for Phase 1.** Custom WS server deferred to Phase 2+ if limits are reached.

### Rationale
- Supabase Realtime eliminates the need for a separate WebSocket server, Redis instance, and fan-out logic in Phase 1.
- It integrates directly with the RLS policies — users only receive events for their own data.
- Supabase Realtime has documented connection limits per plan tier. Monitoring from Phase 1 launch will determine if limits are approached.
- The frontend subscription code is isolated in `hooks/useRealtimeMessages.ts`. Swapping to a custom WS endpoint requires changes only to this layer.

### Consequences
- Phase 1 WebSocket capacity is bounded by Supabase plan limits.
- Must monitor connection counts. Trigger custom WS evaluation at 70% of plan limit.
- Phase 2+ ADR-008 describes the migration path if needed.

---

## ADL-003 — Provider Abstraction for SMS and AI

**Date:** November 2026  
**Status:** Accepted  
**Deciders:** Principal Architect  

### Context
The platform depends on external providers for SMS (Twilio) and AI (Amazon Bedrock). Provider APIs change, pricing changes, and providers become unavailable.

### Options Considered
1. Call Twilio and Bedrock directly from service layer.
2. Implement an abstract provider interface; implementations injected at runtime.

### Decision
**Provider abstraction via ABC classes** (`SmsProvider`, `AiProvider`).

### Rationale
- Swapping providers requires implementing a new class, not modifying service layer code.
- `MockSmsProvider` enables full SMS flow testing without real SMS or Twilio credentials.
- `MockAiProvider` enables AI feature testing without Bedrock access or cost.
- The abstraction enforces the contract: new providers must implement all interface methods.

### Consequences
- Two more files per provider type.
- All provider calls go through the interface — no direct HTTP calls from service layer.
- Provider selection at startup via `SMS_PROVIDER_MODE` environment variable.

---

## ADL-004 — Backend-Proxied AI Calls

**Date:** November 2026  
**Status:** Accepted  
**Deciders:** Principal Architect  

### Context
AI calls require AWS credentials (for Bedrock). Options include calling Bedrock from the frontend or proxying through the backend.

### Options Considered
1. Frontend calls Bedrock directly (AWS credentials in client bundle).
2. Backend proxies all AI calls (credentials server-side only).

### Decision
**All AI calls proxied through the FastAPI backend.**

### Rationale
- AWS credentials in the frontend bundle are trivially extractable and must never be done.
- Backend proxying also allows: rate limiting per user, usage logging (without message content), prompt sanitisation, and provider swap transparency.
- This is a security invariant with no exception.

### Consequences
- Additional network hop per AI request (frontend → backend → Bedrock).
- Latency overhead is acceptable given the 5-second SLA for AI features.
- Backend must have IAM credentials scoped to Bedrock inference only.

---

## ADL-005 — FastAPI Layered Architecture

**Date:** November 2026  
**Status:** Accepted  
**Deciders:** Principal Architect  

### Context
FastAPI allows putting business logic directly in route handlers, which is common in small apps but creates maintenance problems as complexity grows.

### Decision
**Strict four-layer architecture:** Route Handler → Service → Repository → Database (with Provider as an alternative leaf from Service).

### Rationale
- Route handlers remain thin and testable without running a server.
- Service layer has no HTTP concepts, making it independently unit-testable.
- Repository layer makes DB access mockable in service tests.
- Provider layer makes external APIs mockable without touching service logic.

### Consequences
- More files and indirection than a simple handler-does-everything approach.
- Tests at each layer are faster and more focused.
- Code review must enforce the layering rule (no route handler calling repository directly).

---

## ADL-006 — Supabase RLS as Primary Authorisation Layer

**Date:** November 2026  
**Status:** Accepted  
**Deciders:** Principal Architect  

### Context
User data authorisation can be enforced at the application layer only, or also at the database layer via PostgreSQL Row Level Security.

### Decision
**RLS on every table containing user data, as the primary authorisation layer.** Application-layer ownership checks are secondary.

### Rationale
- RLS enforces data access even if the application layer has a bug or is bypassed.
- Supabase RLS integrates with `auth.uid()` — no application-level user ID propagation needed for reads.
- Defence in depth: two independent layers must both be bypassed for unauthorised data access.

### Consequences
- Every table migration must include RLS policies.
- RLS policies must be tested (not just assumed to work).
- Slight query performance overhead from RLS evaluation — must be benchmarked.

---

## ADL-007 — Async SQLAlchemy Throughout Backend

**Date:** November 2026  
**Status:** Accepted  
**Deciders:** Principal Architect  

### Context
FastAPI is an async framework. Database access can be synchronous (blocking) or asynchronous (non-blocking).

### Decision
**SQLAlchemy 2.x async engine and sessions throughout the backend.**

### Rationale
- Synchronous DB calls in an async FastAPI handler block the event loop, degrading throughput.
- SQLAlchemy 2.x provides a stable async API.
- Connection pooling with `AsyncEngine` is well-supported.

### Consequences
- All repository methods are `async def`.
- Session management uses `async with session.begin()`.
- Requires care with SQLAlchemy lazy loading — use explicit `selectinload` or `joinedload` to avoid async lazy-load issues.

---

## ADL-008 — Custom WebSocket Server Deferred to Phase 2+

**Date:** November 2026  
**Status:** Accepted (Deferred)  
**Deciders:** Principal Architect  

### Context
Phase 1 uses Supabase Realtime. If connection limits are reached, a custom WebSocket layer with Redis pub/sub is the migration path.

### Decision
**Defer custom WS server to Phase 2+.** Trigger: Supabase Realtime connection usage reaching 70% of plan limit.

### Migration Path (when triggered)
1. Add `GET /ws/conversations/{id}` FastAPI WebSocket endpoint.
2. Add Redis pub/sub for cross-instance fan-out.
3. Update `hooks/useRealtimeMessages.ts` to subscribe to custom WS instead of Supabase Realtime channel.
4. Keep Supabase Realtime for notifications (lower volume, less critical).

### Consequences
- Phase 1 and 2 may need a plan upgrade if growth is faster than expected.
- Architecture is designed for this transition — no data model changes required.

---

## ADL-009 — Background Task Strategy (Pending)

**Date:** November 2026  
**Status:** Pending Decision  
**Deciders:** Engineering team — resolve before Phase 2  

### Context
SMS retry and data export require background task execution. FastAPI `BackgroundTasks` is lightweight but does not survive process restarts and has no retry semantics.

### Options Under Consideration
1. FastAPI `BackgroundTasks` — simple, no infrastructure, but ephemeral.
2. ARQ (async Redis queue) — lightweight, persistent, Redis required.
3. Celery + Redis/RabbitMQ — heavyweight, proven, more infrastructure.
4. Supabase Edge Functions (scheduled) — managed, limited runtime.

### Recommendation
ARQ for Phase 2 if retry volumes require persistence. Evaluate based on Phase 1 observed failure rates.

### Open Decision
ADL-009 will be formalised before Phase 2 begins. The SMS retry mechanism must be persistent to survive backend restarts.

---

## Decisions Pending (Open Decisions from PRD)

| OD ID | Decision | Status | Blocks |
|---|---|---|---|
| OD-001 | Payment gateway | Open | Phase 4 |
| OD-002 | Bedrock model selection | Open | Phase 3 |
| OD-003 | Backend hosting platform | Open | Phase 0 completion |
| OD-004 | Push notification service | Open | Phase 2 |
| OD-005 | Classic Mode design assets | Open | Phase 5 |
| OD-006 | Data retention period | Open | Phase 1 DB |
| OD-007 | Philippine SMS sender ID approach | Open | Phase 6 PH live |
| OD-008 | Supabase project region | Open | Phase 0 completion |

Each of these will become a new ADL entry when resolved.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft; ADL-001 through ADL-009 |
