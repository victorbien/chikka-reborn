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
**Status:** Superseded by ADL-013 and ADL-020 (Implementation 04)  
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
**Status:** Superseded by ADL-013 and ADL-020 (Implementation 04)  
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

## Proposed Decisions (Awaiting Review)

ADL-010 to ADL-017 are **Proposed**. They refine or supersede earlier entries only once accepted. Until then, ADL-001 to ADL-009 stand. Design detail: `modular-monolith-design.md`, `sms-gateway-design.md`, `ai-assistant-design.md`, `realtime-design.md`.

| Proposed ADR | Relationship to existing entries |
|---|---|
| ADL-010 | Refines ADL-001; replaces the directory layout in ADL-005 |
| ADL-011 | Refines ADL-006 (reorders primary/secondary); resolves OD-014 |
| ADL-012 | Refines ADL-005 and ADL-007 |
| ADL-013 | Would supersede ADL-002 and ADL-008 |
| ADL-014 | Refines ADL-003 (SMS) |
| ADL-015 | Refines ADL-003 and ADL-004 (AI); changes the provider interface shape |
| ADL-016 | Resolves ADL-009 |
| ADL-017 | New; partly resolves OD-003 and OD-008 |
| ADL-018 | New; implements ADL-011 in the schema; resolves OD-010, OD-012, OD-013 (proposed) |
| ADL-019 | Implements ADL-011 for Module A; refines how OD-014 is resolved |

---

## ADL-010 — Modular Monolith with Enforced Module Boundaries

**Date:** November 2026  
**Status:** Proposed  
**Deciders:** Principal Architect (review pending)  

### Context
ADL-001 chose a modular monolith but left enforcement informal ("code review"). The backend layout in `backend-architecture.md` is organised by technical type (`services/`, `repositories/`), which lets any service import any repository and makes cycles easy. Eleven domains with real coupling risk exist: messaging needs SMS, SMS needs messaging, notifications need everything.

### Options Considered
1. Layout by technical type, boundaries by convention (current).
2. Layout by domain module, with a layer order, public interfaces, ports for inversion, and automated import checks.
3. Separate Python packages per module in a workspace.
4. Microservices.

### Decision
Option 2. Eleven modules under `backend/app/modules/`, a fixed layer order (audit/users → authentication → contacts/credits → conversations → messaging → sms/notifications/ai_assistant → administration), `public.py` as the only importable surface, `ports.py` for dependency inversion, and an architecture test built on the standard library `ast` module that fails CI on violations.

### Advantages
- Cycles are structurally impossible, and the one real cycle (messaging ↔ SMS) is broken by a port.
- Each module is independently testable and could be extracted later.
- Domain ownership of tables is explicit.
- No new tooling dependency.

### Disadvantages
- More ceremony: `public.py` and ports for every cross-module call.
- Some duplication of DTOs at boundaries.
- The architecture test needs maintenance as modules evolve.
- Event contracts form a small shared kernel that all modules can see.

### Consequences
- `backend-architecture.md` layout is replaced.
- Steering module names change (flag F2); `architecture.md` steering must be updated with this ADR (steering rule: boundary changes need an ADR first).
- Cross-module side effects use events through the outbox; invariants use direct service calls in one transaction.
- Adding `import-linter` later requires its own decision-log entry.

---

## ADL-011 — Supabase for Database and Authentication, Backend as Authorisation Authority

**Date:** November 2026  
**Status:** Proposed  
**Deciders:** Principal Architect (review pending)  

### Context
Supabase supplies PostgreSQL, Auth, Storage and RLS. ADL-006 calls RLS the "primary" authorisation layer, but the backend connects with a privileged role, which bypasses RLS, and steering (`architecture.md`, `security.md`) says RLS is the last line of defence and the service layer must check ownership on every access. OD-012 (profiles readable by any authenticated user) and OD-014 (session tokens in `localStorage`) are unresolved.

### Options Considered
1. Browser talks to Supabase directly for data; RLS is the only authorisation.
2. Backend mediates all data access with a privileged role; RLS defends non-backend paths.
3. Backend queries as the end user (`SET LOCAL role` plus JWT claims) so RLS applies to every query.
4. Replace Supabase Auth with a custom identity service.

### Decision
Option 2. Supabase Auth issues identities and tokens. The backend verifies the JWT on every protected request, loads role and active state from `users`, and enforces ownership in services. RLS is enabled on every table with default-deny for `anon` and `authenticated`, plus tests proving cross-user denial. The browser does not query tables. Auth flows go through backend `/auth/*` endpoints; the access token lives in memory and the refresh token in an httpOnly Secure cookie set by the backend (resolves OD-014, subject to hosting on a shared registrable domain). Storage is used directly by the browser for avatars under per-user RLS-style policies.

### Advantages
- One authorisation path, easy to reason about and audit.
- Rate limiting and audit of auth events happen in the backend.
- No token in script-readable storage.
- RLS still protects against a leaked anon key or a mistaken direct client.
- Resolves OD-012 by removing browser table access.

### Disadvantages
- RLS is no longer the first defence. A bug in a service is not caught by the database for backend queries.
- The backend becomes a thin proxy for sign-in, adding a hop and some code.
- Cookie handling needs CSRF care (SameSite and a custom header requirement on the refresh endpoint).
- Supabase client features (browser-side auth state, OAuth helpers) are used less.

### Consequences
- ADL-006 wording is amended: backend authorisation is primary; RLS is defence in depth.
- Option 3 stays available as a later hardening step for read paths; it is not needed now.
- Social login (Google, GitHub) uses an authorisation-code flow completed by the backend callback.
- Hosting must support a same-site domain for SPA and API (affects OD-003).
- Every migration still ships its RLS policies and tests.

---

## ADL-012 — FastAPI Async Backend with Module Routers

**Date:** November 2026  
**Status:** Proposed  
**Deciders:** Principal Architect (review pending)  

### Context
The backend needs REST, WebSockets, webhooks and background work, with strong validation, typed contracts, and dependency injection for provider swapping and tests.

### Options Considered
1. FastAPI with async SQLAlchemy and Pydantic v2.
2. Django with Channels.
3. Node/NestJS.
4. Litestar or Starlette-only.

### Decision
Option 1, as already fixed in `technology-stack.md`. Refinement: routers live inside modules and are aggregated under `/api/v1`; webhooks are separate routes under `/api/v1/webhooks`; the WebSocket gateway is a separate adapter; the same code runs as `web` and `worker` process types; all I/O is async and vendor SDKs with blocking APIs run in a bounded thread pool inside `integrations/`.

### Advantages
- Native async, WebSocket support, Pydantic validation, OpenAPI.
- `Depends` gives clean injection and test overrides.
- Fits team and stack already agreed.

### Disadvantages
- Fewer batteries than Django (admin, migrations ORM). Mitigated: Supabase migrations and our own admin module.
- Async discipline required; one blocking call degrades the loop.
- SQLAlchemy async needs explicit eager loading.

### Consequences
- Handlers stay thin; services own transactions via `UnitOfWork`.
- Uniform error envelope and `request_id` are mandatory.
- Blocking SDKs (boto3) must be wrapped and bounded.
- Connection mode matters: transaction pooler for requests, direct or session mode for `LISTEN`.

---

## ADL-013 — WebSocket Strategy: Backend Gateway with Postgres Fan-Out

**Date:** November 2026  
**Status:** Accepted, supersedes ADL-002 and ADL-008. Phase 1 fan-out amended by ADL-020.  
**Deciders:** Principal Architect (review pending)  

### Context
ADL-002 uses Supabase Realtime for Phase 1 and defers a custom server. Since then the requirements show needs Supabase Realtime does not cover cleanly: backend-originated events (SMS status from webhooks and jobs), membership re-checked at delivery time, per-user hidden messages (OD-013), per-conversation ordering and deduplication, delivery acknowledgement for offline-notification decisions, and session revocation. Supabase Realtime change streams evaluate RLS per subscriber per change and would push us toward browser table access (conflicts with ADL-011).

### Options Considered
1. Supabase Realtime for everything (ADL-002).
2. Backend WebSocket gateway, fan-out across instances through Postgres `LISTEN/NOTIFY`.
3. Backend WebSocket gateway with Redis pub/sub.
4. Third-party managed service (Pusher, Ably).
5. Hybrid: Supabase Realtime for notifications only.

### Decision
Option 2. A FastAPI WebSocket gateway authenticates with a first-frame JWT, delivers events to recipients resolved at delivery time, uses a server-assigned per-conversation `seq` for ordering, and relies on REST resync for repair. Cross-instance fan-out uses `NOTIFY` on committed events. Writes use REST. Supabase Realtime is not used in Phases 1 to 2 and can stay enabled but unused. Redis is introduced only through a new ADR if listener lag or fan-out cost requires it.

### Advantages
- No additional datastore or vendor.
- One authorisation path (service layer).
- Producers include webhooks, workers and REST handlers uniformly.
- Event delivery is atomic with the commit (NOTIFY is transactional).
- Full control of auth, ordering, throttling and protocol.

### Disadvantages
- We own connection management, heartbeats, backpressure and draining.
- NOTIFY is not durable. Correctness depends on client REST resync.
- A `LISTEN` connection per web instance must bypass the transaction pooler.
- Counter-based `seq` serialises writes per conversation.
- More backend code than Option 1 and more to test.

### Consequences
- Replaces the "Supabase Realtime" statements in `api/messaging-api.md`, `api/notifications-api.md`, `api/sms-api.md`, `frontend-architecture.md`.
- A wire protocol document is added with the first implementation.
- Capacity is bounded by backend instances, not a Supabase plan limit; the 70 % plan-limit trigger in ADL-008 goes away.
- Redis revisit trigger: sustained NOTIFY lag or cross-instance fan-out cost.
- Presence is stored in the database with expiry; "delivered" for chat means client acknowledgement.

---

## ADL-014 — SMS Provider Abstraction with Policy Pipeline and Explicit Modes

**Date:** November 2026  
**Status:** Proposed  
**Deciders:** Principal Architect (review pending)  

### Context
SMS must support free simulation and real sends, multiple countries with different rules, and honest delivery status. Messaging must not know the provider. Live sends cost money and reach real people.

### Options Considered
1. Call Twilio directly from services.
2. `SmsProvider` interface; mock and Twilio implementations; messaging coupled to `sms` module directly.
3. As 2, with messaging decoupled through an `OutboundChannel` port and a dispatch queue; policy checks run before queueing; mode fixed at startup with a confirmation token.

### Decision
Option 3. Interface: `send_message`, `get_message_status`, `validate_webhook`, `parse_inbound_message`, `parse_status_callback`. Status vocabulary `queued → accepted → sent → delivered | failed | undelivered`, with acceptance, carrier submission and delivery kept distinct. Failure classes `policy, transient, ambiguous, permanent, configuration`. Retry only transient failures, never resend ambiguous ones automatically. Per-message callback URL carries our correlation ID. Simulation uses a mock signer and the same webhook pipeline. Live requires `SMS_LIVE_CONFIRMATION` bound to the environment name; failure to initialise exits the process.

### Advantages
- Simulation tests the real pipeline (signature, dedupe, ordering, persistence).
- Duplicate sends to real people are avoided by design.
- Country rules, consent and rate limits are enforced before cost is incurred.
- Mode and provider are recorded per message, so simulated data cannot be mistaken for real.
- New providers implement five methods.

### Disadvantages
- More moving parts than a direct call: attempts table, callback correlation, resolution window.
- Ambiguous failures can leave a message undelivered until the user resends.
- Mock fidelity needs upkeep to stay representative.
- Twilio-specific assumptions need verification (marked in the design).

### Consequences
- `outbound_sms` is replaced by `sms_messages` plus `sms_send_attempts`; statuses `pending` and `permanently_failed` are removed (flag F8).
- Steering interface names are updated (flag F4).
- A phone-number parsing library decision is needed.
- Consent and opt-out are platform-level persistent data.
- Inbound routing (OD-011) must be decided before Phase 2 inbound.

---

## ADL-015 — AI Provider Abstraction with a Staged, Non-Sending Pipeline

**Date:** November 2026  
**Status:** Proposed  
**Deciders:** Principal Architect (review pending)  

### Context
AI features need Bedrock, model swappability, prompt-injection resistance, minimal data exposure, and a hard guarantee that AI never sends. The existing abstraction exposes one method per feature, which puts prompts inside vendor code.

### Options Considered
1. Per-feature methods on `AiProvider` (current steering sketch).
2. Single `complete()` primitive; prompts, validation and context handling in `ai_assistant`.
3. Call Bedrock through an agent framework.

### Decision
Option 2. Nine stages (validate, authorise, retrieve context, minimise and redact, build prompt, call, validate output, record usage, issue suggestion). Prompts are static, versioned constants; user data is passed as JSON-escaped structured turns. `ai_assistant` has read-only access to conversations and no import path to any send function, enforced by the architecture test. Usage rows hold metadata only.

### Advantages
- Changing the model or vendor touches one adapter.
- Prompts and validators are unit testable without a model.
- No-send guarantee is structural.
- Sensitive data exposure is limited and auditable.

### Disadvantages
- More components than a thin wrapper.
- Redaction is best-effort for free text.
- `is_ai_assisted` is client-reported across the module boundary.
- Quality tuning across models needs per-model prompt checks.

### Consequences
- Steering `ai-guidelines.md` interface sketch is updated (flag F5).
- Tests use `MockAiProvider` only.
- Bedrock calls run in a bounded thread pool unless an async client is adopted.
- OD-002 (model) is still required before Phase 3.

---

## ADL-016 — Message Delivery and Retry Model: Durable Postgres Job Queue and Outbox

**Date:** November 2026  
**Status:** Proposed (resolves ADL-009)  
**Deciders:** Principal Architect (review pending)  

### Context
ADL-009 is pending. SMS dispatch, status reconciliation, webhook processing, email, and event relays must survive restarts, retry with backoff and jitter, be idempotent, and have a permanent-failure end state. `BackgroundTasks` does not survive restarts. Redis-based queues are an extra datastore (restricted without an ADR).

### Options Considered
1. FastAPI `BackgroundTasks`.
2. ARQ with Redis.
3. Celery with a broker.
4. Postgres-backed queue (`jobs` table, `FOR UPDATE SKIP LOCKED`) and transactional outbox.
5. Supabase scheduled functions.

### Decision
Option 4. `jobs` (kind, payload, `run_at`, attempts, max attempts, lease, dedupe key, status `pending/running/succeeded/dead`) and `outbox_events`. Jobs are enqueued in the same transaction as the business change. A worker process claims with `SKIP LOCKED` and a lease, runs handlers, and reschedules failures with exponential backoff and jitter drawn from an injected RNG. Dead jobs raise alerts and appear in the admin view. `NOTIFY` wakes workers; polling is the backstop. Delivery model: message persisted `queued` → dispatch job → provider → callbacks move status forward → versioned events pushed to clients.

### Advantages
- Atomic with business writes: no lost or phantom jobs.
- No additional infrastructure.
- Restart-safe, inspectable with SQL, testable with a frozen clock.
- Natural place for idempotency (dedupe keys, attempt rows).

### Disadvantages
- Throughput ceiling lower than a dedicated broker.
- Queue load shares the primary database.
- Must build and test lease, retry and dead-letter logic ourselves.
- Polling and NOTIFY need a non-pooled connection.

### Consequences
- Migration adds `jobs`, `outbox_events`, `rate_limit_counters`.
- Deployment has a second process type (`worker`).
- Revisit trigger: sustained queue latency or database CPU attributable to queue polling. Move to ARQ/Redis through a new ADR.
- Handlers must be idempotent; duplicates are expected.

---

## ADL-017 — Deployment Strategy: Container Image, Two Process Types, Gated Production

**Date:** November 2026  
**Status:** Proposed  
**Deciders:** Principal Architect (review pending)  

### Context
Frontend is on Vercel. The backend needs long-lived WebSocket connections, an always-on worker, graceful draining, a same-site domain with the SPA, and a region near the Supabase project. OD-003 (host) and OD-008 (region) are open. Live SMS and production migrations need human approval.

### Options Considered
1. Serverless functions for the API.
2. Single container running web and worker together.
3. One container image deployed as separate `web` and `worker` services on a managed container platform (Render, Railway or Fly.io).
4. Kubernetes.

### Decision
Option 3 as the strategy. Host selection stays open under OD-003 against criteria: WebSocket support and idle timeouts, graceful shutdown, separate worker service, custom domain on the same registrable domain as the frontend, region options near the database, secret management, zero-downtime deploys, cost. Staging and production are separate Supabase projects and separate backend services. Staging runs `mock` SMS only. Production defaults to `mock`; live requires the confirmation token. CI runs lint, type checks, unit and integration tests, architecture tests, and E2E; production deploy and production migrations need manual approval.

### Advantages
- Simple operations; horizontal scale for web and worker independently.
- Matches WebSocket and worker requirements.
- Clear promotion path and approval gates.
- Same image everywhere.

### Disadvantages
- Two services to monitor and configure.
- Not scale-to-zero; some baseline cost.
- Same-site domain requirement constrains DNS and hosting choices.
- Kubernetes-grade features (autoscaling policies, service mesh) are out of scope.

### Consequences
- OD-003 and OD-008 still need your decision; Singapore is the leading region candidate for Philippine users, pending legal input.
- `deployment-guide.md` and `environment-configuration.md` are updated (live confirmation token, webhook base URL, job and retry settings).
- Health endpoints `/healthz` and `/readyz` are mandatory.
- Rollback is image redeploy; migrations follow expand-then-contract so rollback stays safe.

---

## ADL-018 — Database Design: Message/Delivery Separation, Column-Level Access, Ledger Integrity

**Date:** November 2026  
**Status:** Proposed  
**Deciders:** Principal Architect (review pending)  

### Context
The schema had to support internal chat, outbound and inbound SMS, retries, provider-specific statuses, two credit ledgers, consent, moderation and audit, against 130 functional requirements. The first draft (13 tables) stored SMS state in `outbound_sms` and `inbound_sms`, mixed content with delivery, and relied on row policies alone. Several open decisions (OD-010, OD-012, OD-013) blocked the database design.

### Options Considered
1. Keep SMS-specific tables (`outbound_sms`, `inbound_sms`) beside `messages`.
2. One `messages` table with delivery columns on it.
3. `messages` for content and `message_deliveries` for attempts, plus an event history.
4. Status fields as PostgreSQL enum types versus `text` with `CHECK` constraints.
5. Row policies only, versus row policies plus column-level grants.
6. Hard-delete profiles on account deletion, versus tombstone them.

### Decision
- Option 3: a message is content; a delivery row is one attempt through a channel/provider; raw provider status is stored beside the normalised status; an append-only event table records every signal and whether it applied.
- `text` with named `CHECK` constraints for status vocabularies (safer to evolve than enum types).
- Row policies plus column-level grants. Sensitive columns (OTP state, provider IDs, block suppression, AI flags, request hashes) are not granted to clients. Business-rule writes are backend-only. Six server-only tables have no policies.
- Profiles are tombstoned, never hard-deleted; `auth.users` deletion is `RESTRICT`.
- Integrity enforced in the database where an application bug would be costly: forward-only delivery status, gap-free per-conversation `seq`, ledger shape and no overdraw, simulated messages confined to the demo ledger, immutable ledger and audit rows.
- Country capabilities are versioned, and a message records the version (rate) used.
- Two credit ledgers (`live`, `demo`) in one balance table and one transaction table. This follows the FRS and refines the earlier proposal to skip the ledger in simulation.
- Development tooling: `@electric-sql/pglite` 0.5.16, a development-only dependency in `supabase/tools`, runs migrations, seed and SQL tests on an embedded PostgreSQL. Reason: the authoring machine had no running Docker or `psql`, and a Docker-free path makes the suite fast enough to run on every change. It ships nowhere and touches no network. It does not replace running the suite on Supabase's own Postgres.

### Advantages
- Retries, provider quirks and duplicate or out-of-order callbacks have a place to live without distorting the message record.
- Authorisation holds even if a backend query is wrong, for every path that uses a user token.
- Money and status invariants cannot be violated by a buggy service.
- The schema can be verified in seconds on any machine; the same SQL runs on Supabase.

### Disadvantages
- More tables (29) and more joins than a single wide message table.
- Clients cannot `select *` on some tables; every query must name its columns.
- Many rules live in triggers, which are harder to see than application code. Mitigated by tests and the generated reference.
- The embedded PostgreSQL is a different version from Supabase's, so results must be confirmed on Supabase.
- Triggers add write-path cost; the ledger trigger takes a row lock per user and ledger.

### Consequences
- Supersedes the 13-table schema in `database-schema.md` 1.0 and the per-phase migration plan.
- `ADL-006` wording (RLS as the primary authorisation layer) is already proposed to change in ADL-011; this design implements that reorder.
- OD-010, OD-012 and OD-013 have a proposed resolution in the schema; OD-006 (message retention), OD-007 and OD-008 remain open.
- Deferred tables (sessions, attachments, edit history, push subscriptions, exports, payments) are additive migrations tied to their features.
- Migration 20261110000001 to 15 must pass the SQL suite on a clean database before any shared environment applies them.
- Adding a dependency on `@electric-sql/pglite` is recorded here per the technology-stack rule; upgrading it needs a re-run of the suite and a note in the decision log.

---

## ADL-019 — Authentication Module Implementation

**Date:** November 2026  
**Status:** Accepted (implemented in Implementation 02)  
**Deciders:** Engineering  

### Context
ADL-011 makes the backend the authorisation authority and keeps tokens out of script-readable storage. Module A needed concrete choices for talking to Supabase Auth, mobile verification, session revocation, presence and photos, and a way to test all of it without a Supabase project or Docker.

### Decision
1. **Backend-mediated Supabase Auth over REST.** `SupabaseAuthProvider` (behind the `AuthProvider` interface in `integrations/`) calls GoTrue with httpx. No Supabase SDK in the backend or browser.
2. **Tokens.** The access token is returned in the body and held in SPA memory. The refresh token is an `HttpOnly`, `SameSite=Lax` cookie scoped to `/api/v1/auth`; refresh also requires `X-Chikka-CSRF: 1`.
3. **Email links carry a token hash to the SPA**, which posts it to the backend (`/auth/verify-email`, `/auth/reset-password/confirm`). Templates live in `supabase/templates/`.
4. **Immediate revocation.** Every protected request checks that the token's `session_id` still exists in `auth.sessions` and that the profile is usable. Logout, "sign out other devices" and password reset delete those rows.
5. **Mobile OTP is owned by the backend**, behind `OtpDelivery`: a simulated inbox in mock mode, and a live implementation that fails explicitly until the Phase 2 `SmsProvider` exists. Supabase phone auth is not used.
6. **Rate limits and lockout** use `rate_limit_counters`, with keyed hashes as subjects. Each counter commits in its own transaction so failed requests still count.
7. **Presence** keeps heartbeats in a per-process registry and persists only `last_seen_at`.
8. **Profile photos** are decoded and re-encoded to WebP by the backend (Pillow), stored in a private bucket, and served through one-hour signed URLs.
9. **Testing without Supabase.** `supabase/tools/serve-db.mjs` serves PGlite (all migrations) over the PostgreSQL protocol. `backend/tests/support/fake_supabase.py` implements the GoTrue and Storage endpoints the backend uses, so tests exercise the real provider code.

### Options Considered
- Supabase JS in the browser with `localStorage` sessions: rejected by ADL-011 and OD-014.
- Supabase phone auth for OTP: needs a provider configured inside Supabase and hides the mode, so simulated and real verifications would be indistinguishable.
- Relying on JWT expiry for logout: leaves revoked sessions usable for up to an hour (fails FR-AUTH-010 AC2).
- Redis for rate limits and presence: an extra datastore with no ADR; Postgres counters are sufficient at this scale.

### Consequences
- One extra indexed lookup per protected request (`auth.sessions` and `profiles`).
- The backend needs read and delete access to `auth.sessions`, which it has through the privileged database role.
- Presence is correct for a single backend instance only. It must move to the realtime layer (ADL-013) before scaling out.
- The SPA and API must share a registrable domain in production for the cookie (already noted in ADL-011; affects OD-003).
- Social login (FR-AUTH-003) still needs a backend authorisation-code callback; not built yet.

---
## ADL-020 — Real-Time Messaging Implementation (Phase 1)

**Date:** November 2026  
**Status:** Accepted (implemented in Implementation 04)  
**Deciders:** Engineering  

### Context
The repository held two conflicting real-time records: ADL-002 (Supabase Realtime, accepted) and ADL-013 (backend WebSocket gateway, proposed). Module C needed one mechanism. Facts that decided it:

- Authentication is backend-mediated (ADL-011, ADL-019). The browser has no Supabase client and no direct table access, so Supabase Realtime would add a second client and a second authorisation path.
- "Delivered" must mean the recipient's app acknowledged a message. That needs an uplink frame the backend records. Pushing a frame is not proof of anything.
- Blocked senders' messages must never reach the recipient, and recipients must be re-checked at delivery time. Both are simple server-side and awkward with `postgres_changes`.
- The project runs one backend instance today.

### Decision
1. **Adopt ADL-013's gateway**: `GET /ws/v1`, authenticated by the first frame within 5 seconds (never a URL token), with the same checks as REST (valid token, live Supabase session, active and onboarded account). Writes stay on REST.
2. **Fan-out in process for Phase 1.** `RealtimeHub` holds this instance's connections. Services publish after commit, to recipients they have checked. The Postgres `NOTIFY` listener in ADL-013 is deferred until a second backend instance is needed.
3. **REST is the source of truth.** Clients resync after every (re)connect and on a gap in `seq`. There is no server replay buffer.
4. **Lifecycle**: `sent` = stored; `delivered` = recipient ack frame, or the recipient loading the conversation over REST; `read` = only when both people enable read receipts. `pending` and `failed` exist only on the sender's device, which retries with the same `client_message_id` (unique per sender) so a message is stored once.
5. **Supabase Realtime is not used.** It stays enabled in the project but unused, so there are not two competing systems.

### Options Considered
- **Supabase Realtime (ADL-002)**: no gateway to run, but needs the Supabase JS client and browser table access (conflicts with ADL-011), cannot record acknowledgements, and filters by RLS only.
- **Gateway plus NOTIFY now**: correct for several instances, but adds a long-lived `LISTEN` connection (needs a session-mode connection, not the pooler) and is harder to test, with no benefit on one instance.
- **Redis pub/sub**: an extra datastore without an ADR (technology-stack restriction).

### Consequences
- **Single instance only.** Running two backend instances without the NOTIFY listener would deliver pushes only to clients on the sending instance. Messages are still stored, and clients catch up through REST (the list refreshes every 60 seconds), but real-time push would be partial. Adding the listener is the trigger before scaling out. Presence has the same limitation (ADL-019).
- Sockets close on sign-out (`4401`), account deletion, and token expiry plus 30 seconds unless refreshed with `auth.refresh`.
- New table `message_attachments` and private bucket `message-attachments` (migration `20261111000003`). Images are re-encoded to drop EXIF, except GIFs, which are only validated so animation survives.
- Wire protocol: `docs/api/realtime-api.md`. REST contract: `docs/api/messaging-api.md`.

## ADL-021 - AI Assistant Implementation

**Date:** November 2026  
**Status:** Accepted  

### Context
Module F adds smart replies, translation, rewriting, tone changes, summaries, SMS optimisation and composition. The design rules in `ai-guidelines.md` require a provider abstraction, drafts only, minimal context and no content in logs.

### Decision
- **`AiProvider`** (`integrations/ai/base.py`) is one primitive, `complete(request)`. Prompts, parsing and validation live in `modules/ai`, so changing the model or vendor is configuration. Providers: `MockAiProvider` (default, canned drafts, scriptable in tests) and `BedrockAiProvider`.
- **Bedrock is called over HTTPS with `httpx`** (Converse API, Bedrock API key as a bearer token). No `boto3` and no new dependency, as the SMS gateway does for Twilio. Consequence: IAM access keys and roles (SigV4) are not supported yet. If the deployment needs them, add `boto3` with an ADR and pinned version, inside `integrations/ai/` only.
- **Selection** is startup configuration (`AI_PROVIDER_MODE`). Bedrock without full configuration fails at startup and never becomes the mock.
- **Opt-in.** `profiles.ai_enabled` defaults to off. The user turns it on in the assistant panel (audited as a `consent` event). Gates, in order: admin kill switch (`system_settings.ai_enabled`), the user's opt-in, the hourly limit (`system_settings.ai_user_limit_per_hour`), then for conversation features the member's per-conversation switch.
- **Drafts only.** No AI endpoint sends. The only follow-up call records the user's decision (`accepted`, `edited`, `dismissed`) against the log row. The composer shows an "AI-assisted" badge on text that came from the assistant.
- **Privacy.** Conversation features read at most 20 (replies) or 50 (summary) recent text messages through `ChatService.ai_context`, which has no read-receipt side effects and respects cleared history and hidden messages. Lines are labelled me/them (no names or ids), emails and numbers of eight or more digits are masked, and a character budget applies. The user's own draft is sent unmasked, because masking would change the translation. Logs and `ai_assistance_logs` hold metadata and an output hash, never text.
- **Output is untrusted.** Model JSON is parsed and bounded. Empty or invalid output returns `200` with no draft and a message. Provider failures return `502 ai_unavailable` after one retry for timeouts and unavailability (not for throttling).
- **SMS optimisation** recomputes segments server-side with `modules/sms/segments.analyse` (GSM-7 or Unicode, concatenated limits), never calls the model when the message already fits, drops a result that saves no segment, and normalises typographic characters to GSM-7. `meaning_preserved` is the model's own claim and is shown as such. No price or saving is claimed.

### Alternatives considered
- `boto3`: supports IAM, but adds a synchronous SDK and a dependency.
- Per-feature provider methods (`translate`, `summarise`, ...): more surface to implement per vendor for no gain.

### Consequences
- The AI feature in the frontend is imported directly by the chat and SMS composers (`features/ai`), a deliberate exception to the no-cross-feature rule because the assistant is an optional add-on to both.
- Sent messages do not yet record `messages.is_ai_assisted` or `ai_assistance_log_id`. Linking them needs a field on the send request.
- Replies and summaries work for Chikka conversations only. SMS threads have no AI context endpoint yet.
- Model choice (OD-002), language quality for `ceb`, `ilo` and `hil`, and token pricing are still open.

## ADL-022 - Notifications and Simulated Credits

**Date:** November 2026  
**Status:** Accepted  

### Context
Module G (notifications) and Module H (credits) were specified and had tables (migrations 09 and 10) but no code. The task asks for a simulated credit ledger for the hackathon, no real payments, no duplicate notifications, and email through a configurable provider.

### Decision
**Credits**
- **Simulated credits only, on the existing `demo` ledger.** Simulated SMS reserve, spend and refund demo credits. The `live` ledger is untouched and live SMS is not metered, because there is no payment system to fund it. The database already rejects a live message on the demo ledger and the reverse.
- **This supersedes** the Phase 2 rule "simulation never charges" (DEC-SMS-001, OD-009) and the matching line in `sms-guidelines.md` ("never deduct credits for simulation mode messages"). The intent of that rule, that simulation must never cost real money, is kept by the ledger separation. The guideline text should be read as "never real credit".
- **One ledger module** (`modules/credits/ledger.py`) is the only code that changes a balance. It appends rows to `credit_transactions`; the trigger applies them. Reserve at queue time (inside the send transaction, so an overdraw refuses the send and rolls the message back), spend on provider acceptance, release if never accepted, refund if it fails after acceptance. Every step checks for its own entry first (unique `(message_id, entry_type)`), so repeats are no-ops. A capture that cannot be afforded (only possible after a release and a late correction) is logged and skipped rather than failing the status update.
- **Administrator adjustments** are `adjustment` entries with actor, reason, audit row and a user notification. The `Idempotency-Key` becomes the entry's `external_reference`; the account row is locked first so concurrent repeats replay. Only the demo ledger can be adjusted.
- **Low balance** fires once per crossing using `messaging_credits.low_balance_alerted`, against the user's own threshold.

**Notifications**
- **Dedupe and grouping in the database** (migration `20261113000001`): unique `(user_id, dedupe_key)`, and a unique open-group index so unread events of one chat fold into one row with `occurrence_count`.
- **A delivery outbox** on the same table (`announced_at`, `email_*`, `browser_push`). An in-process dispatcher (like the SMS worker; single instance) announces rows over WebSocket and sends email after commit, so a rollback never notifies and a crash never loses a notification.
- **Email** goes through `EmailProvider` (`mock`, `smtp` via the standard library; no new dependency). SMTP that cannot be built fails at startup and never becomes the mock. Emails never contain SMS text.
- **Browser notifications** use the Notification API while the app is open and the tab is in the background. The server decides `browser` (preference, quiet hours); the browser asks for permission only on a button press. No service-worker push or push service.
- Types gain `security`. Failed SMS, system and security notices cannot be switched off in the app.

### Alternatives considered
- Charging at queue time and refunding on failure: simpler, but shows spent credit for messages that never left. Reservation keeps balance and holds separate.
- Updating balances in application code: rejected; the ledger and trigger make "balance equals sum of entries" a database guarantee.
- Sending email inside the request transaction: couples user actions to SMTP latency and can email about a change that rolls back.
- Redis or a queue for delivery: an extra datastore needs its own ADR (ADL-009 remains open).

### Consequences
- Live SMS is unmetered until payments exist. Adding live charging means funding the live ledger first.
- Dispatch and announce are single-instance, same limit as ADL-020 and the SMS worker.
- Notification email addresses are read from `auth.users` by the backend's database role.
- Open items: a scheduled purge of expired notifications and old rate-limit rows; an admin UI for adjustments (the API exists); web push for closed browsers.

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
| 1.1 | November 2026 | Kiro | ADL-019 authentication module implementation |
| 1.2 | November 2026 | Kiro | ADL-020 real-time messaging; ADL-013 accepted; ADL-002 and ADL-008 superseded |
