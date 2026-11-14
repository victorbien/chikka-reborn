# Decision Log

**Document:** CHKR-PM-005  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Living Document  
**Last Revised:** November 2026  

---

## Purpose

Records all significant project decisions — product, architectural, operational, and legal. This is a permanent, append-only log. Decisions are never deleted; superseded decisions are marked as such.

## Scope

All phases. All decision types.

---

## Decision ID Convention

- `DEC-ARCH-xxx` — Architectural decisions (maps to ADL entries in `docs/architecture/architecture-decisions.md`)
- `DEC-PROD-xxx` — Product decisions
- `DEC-OPS-xxx` — Operational decisions
- `DEC-LEGAL-xxx` — Legal and compliance decisions

---

## Open Decisions (Requiring Resolution)

These decisions are blocking or will block phase starts. Each has a `Due By` date.

| ID | Decision | Options | Blocks | Due By | Owner |
|---|---|---|---|---|---|
| OD-003 | Backend hosting platform | Render, Railway, Fly.io | Phase 0 completion | Immediately | DevOps |
| OD-008 | Supabase project region | ap-southeast-1 (Singapore), us-east-1, others | Phase 0 completion | Immediately | DevOps/Legal |
| OD-006 | Message data retention period | 90 days, 1 year, user-controlled | Phase 1 DB design | Immediately | Product/Legal |
| OD-001 | Payment gateway for credit top-up | Stripe, PayMongo, deferred | Phase 4 | Phase 3 end | Product |
| OD-002 | Bedrock model selection | Claude 3 Haiku, Claude 3 Sonnet, Titan | Phase 3 | Phase 2 end | Engineering |
| OD-004 | Push notification service | Supabase Realtime, Web Push API, third-party | Phase 2 | Phase 1 end | Engineering |
| OD-005 | Classic Mode design assets | Original-inspired originals, licensed assets | Phase 5 | Phase 4 end | Design |
| OD-007 | Philippine SMS sender ID approach | Pre-registered short code vs alphanumeric | Phase 6 PH live | Begin Phase 1 | Operations |
| OD-009 | Credit handling in simulation mode: docs say simulated SMS consume no credits, but also block sends on insufficient credits and test that behaviour in staging (AC-2-006, E2E-007) | (a) simulation skips balance checks and shows a "would cost" preview; (b) a separate simulated balance; (c) simulation deducts test credits | Phase 2 credit design | Phase 1 end | Product/Engineering |
| OD-010 | Profile bootstrap: no trigger creates a `profiles` row when a Supabase Auth user is created; `username` is required and unique | DB trigger on `auth.users` vs backend creates profile on register; username generation rule | Phase 1 DB | Immediately | Engineering |
| OD-011 | Inbound SMS routing: matching on `(from_phone, to_number)` is ambiguous if one platform number serves many users who text the same phone | Per-user or per-conversation numbers, reply codes, or a restriction of one active conversation per phone per number. Provider and cost implications need verification | Phase 2 inbound design | Phase 1 end | Engineering/Operations |
| OD-012 | `profiles` RLS lets any authenticated user read every active profile row (including `phone_number`) when queried with the anon key; privacy filtering is only in the application layer | Restrict direct SELECT to own row and serve public fields via a view or backend endpoint | Phase 1 DB | Immediately | Engineering |
| OD-013 | Message deletion model: "delete for me" cannot be represented by a single `messages.deleted_at` | Per-user hidden-message table vs per-participant deletion marker | Phase 2 | Phase 1 end | Engineering |
| OD-014 | Session token storage: Supabase JS stores sessions in `localStorage` by default, conflicting with the no-localStorage policy | Custom storage adapter vs accepting default with stricter CSP | Phase 1 auth | Immediately | Engineering |

---

## Recorded Decisions

### DEC-ARCH-001 — Modular Monolith Over Microservices
**Date:** November 2026  
**Status:** ✅ Decided  
**Decision:** Use a modular monolith for both frontend and backend. No microservices unless a specific, documented scaling or isolation requirement demands it.  
**Rationale:** Microservices add distributed systems overhead unjustified at this scale. A well-structured monolith is faster to build, easier to test, simpler to operate.  
**Full ADR:** `docs/architecture/architecture-decisions.md` ADL-001

---

### DEC-ARCH-002 — Supabase Realtime for Phase 1 WebSocket
**Date:** November 2026  
**Status:** Superseded by DEC-ARCH-011 and DEC-ARCH-021 (Implementation 04)  
**Decision:** Use Supabase Realtime for real-time message delivery in Phase 1. Custom WS server deferred to Phase 2+ if limits are reached.  
**Full ADR:** `docs/architecture/architecture-decisions.md` ADL-002

---

### DEC-ARCH-003 — Provider Abstraction for SMS and AI
**Date:** November 2026  
**Status:** ✅ Decided  
**Decision:** SMS and AI integrations go through abstract provider interfaces. MockSmsProvider and MockAiProvider used in all automated tests.  
**Full ADR:** `docs/architecture/architecture-decisions.md` ADL-003

---

### DEC-ARCH-004 — Backend-Proxied AI Calls
**Date:** November 2026  
**Status:** ✅ Decided  
**Decision:** All AI calls proxied through FastAPI backend. Frontend never calls Bedrock directly.  
**Rationale:** Security — AWS credentials must never be in the frontend bundle.  
**Full ADR:** `docs/architecture/architecture-decisions.md` ADL-004

---

### DEC-ARCH-005 — Layered Backend Architecture
**Date:** November 2026  
**Status:** ✅ Decided  
**Decision:** FastAPI backend enforces: Route Handler → Service → Repository → Database. No layer skips another.  
**Full ADR:** `docs/architecture/architecture-decisions.md` ADL-005

---

### DEC-ARCH-006 — Supabase RLS as Primary Authorisation Layer
**Date:** November 2026  
**Status:** ✅ Decided  
**Decision:** RLS on every table. Application-layer ownership checks are secondary defence.  
**Full ADR:** `docs/architecture/architecture-decisions.md` ADL-006

---

### DEC-ARCH-007 — Async SQLAlchemy Throughout Backend
**Date:** November 2026  
**Status:** ✅ Decided  
**Decision:** SQLAlchemy 2.x async engine and sessions. No synchronous DB calls in async handlers.  
**Full ADR:** `docs/architecture/architecture-decisions.md` ADL-007

---

### DEC-ARCH-008 to DEC-ARCH-015 — Target Architecture (Proposed)
**Date:** November 2026  
**Status:** 🟡 Proposed — awaiting review  
**Decision:** Eight proposed decisions. Details in `docs/architecture/architecture-decisions.md`.

| ID | Decision | ADR | Effect on earlier decisions |
|---|---|---|---|
| DEC-ARCH-008 | Modular monolith with enforced module boundaries | ADL-010 | Refines DEC-ARCH-001, DEC-ARCH-005 |
| DEC-ARCH-009 | Supabase DB/Auth; backend is the authorisation authority; RLS is defence in depth; cookie-based refresh | ADL-011 | Refines DEC-ARCH-006; proposes resolving OD-012, OD-014 |
| DEC-ARCH-010 | FastAPI async backend with module routers, `web` and `worker` processes | ADL-012 | Refines DEC-ARCH-005, DEC-ARCH-007 |
| DEC-ARCH-011 | Backend WebSocket gateway with Postgres NOTIFY fan-out | ADL-013 | Accepted; supersedes DEC-ARCH-002. NOTIFY fan-out deferred by DEC-ARCH-021 |
| DEC-ARCH-012 | SMS provider abstraction, policy pipeline, explicit modes | ADL-014 | Refines DEC-ARCH-003, DEC-PROD-001 |
| DEC-ARCH-013 | AI provider abstraction with staged, non-sending pipeline | ADL-015 | Refines DEC-ARCH-003, DEC-ARCH-004, DEC-PROD-002 |
| DEC-ARCH-014 | Postgres job queue and outbox for delivery and retry | ADL-016 | Resolves ADL-009 |
| DEC-ARCH-015 | Container deployment, two process types, gated production | ADL-017 | Partly informs OD-003, OD-008 |
| DEC-ARCH-017 | Frontend UI dependencies pinned: Tailwind CSS 4.3.5, Radix primitives (dialog, slot, switch, tabs, tooltip), class-variance-authority, clsx, tailwind-merge, lucide-react. Mode theming via CSS variables and `data-mode`. | Not yet an ADL entry | Implements `docs/design/design-system.md`; all are the shadcn/ui foundation already approved in the stack |
| DEC-ARCH-018 | Foundation dependencies pinned. Frontend: @tanstack/react-query 5.107.1, zod 4.6.7 (both in the approved stack); dev tooling eslint 10.14.0, typescript-eslint 8.72.2, eslint-plugin-react-hooks 7.1.1, prettier 3.9.10. Backend: fastapi 0.162.4, uvicorn 0.54.0, pydantic 2.14.3, pydantic-settings 2.16.2, sqlalchemy 2.1.8, asyncpg 0.32.0 (async PostgreSQL driver required by async SQLAlchemy), PyJWT 2.15.1 (verifies Supabase access tokens; chosen over python-jose, which is less maintained); dev: pytest, pytest-asyncio, pytest-cov, httpx (TestClient), ruff, mypy. Health is served at `/api/v1/health` and `/api/v1/health/ready` for clients, with `/healthz` and `/readyz` aliases for platforms (ADL health requirement). | Not yet an ADL entry | Implements Implementation 01; supersedes the `/health` path in older deployment docs (see api-overview section 12) |
| DEC-ARCH-019 | Authentication module (Implementation 02): backend-mediated Supabase Auth over REST, memory access token plus httpOnly refresh cookie with CSRF header, per-request session liveness check, backend-owned mobile OTP behind `OtpDelivery`, Postgres rate limits. New pinned dependencies with reasons. Backend: httpx 0.28.1 moved to runtime (GoTrue and Storage REST), email-validator 2.3.0 (Pydantic `EmailStr`), phonenumbers 9.0.43 (E.164 parsing and country), pillow 13.0.0 (photo validation and re-encoding), python-multipart 0.0.33 (FastAPI uploads), tzdata 2026.6 (IANA zones on Windows). Frontend: react-hook-form 7.91.0 and @hookform/resolvers 7.0.5 (approved stack), @vitest/coverage-v8 5.1.0 (dev; measures the coverage floors). Database tools: @electric-sql/pglite-socket 0.2.19 (dev; PGlite over the wire for flow tests). | ADL-019 | Implements ADL-011 for Module A |
| DEC-ARCH-021 | Real-time messaging (Implementation 04): FastAPI WebSocket gateway `/ws/v1` with first-frame auth, in-process fan-out for a single backend instance (Postgres NOTIFY deferred until a second instance), REST as source of truth with resync on reconnect and on `seq` gaps, "delivered" = recipient ack, read receipts only when both opt in. Supabase Realtime unused. No new dependencies (the emoji picker is built in; WebSockets are native). | ADL-020 | Accepts ADL-013; supersedes DEC-ARCH-002 |
| DEC-ARCH-022 | Administration dashboard (Implementation 08): one `admin` backend module with read-only SQL aggregates, a role read from the database on every request, denied admin access audited as `admin.access_denied`, account restriction by coded reason only (no free text in audit rows), SMS and AI views that never return message or prompt content, optional AI price settings for an approximate cost. No new dependencies. | Not yet an ADL entry | Implements FR-ADMIN-001 to 004, 006 and 012 in part; re-authentication, abuse reports and feature flags remain open |

---

### DEC-ARCH-016 — Database Design (Proposed)
**Date:** November 2026  
**Status:** 🟡 Proposed — awaiting review  
**Decision:** 29-table schema with message/delivery separation, column-level client grants, database-enforced status and ledger invariants, tombstoned profiles, versioned country capabilities and separate live/demo credit ledgers. Adds `@electric-sql/pglite` 0.5.16 as a development-only dependency for running migrations and SQL tests without Docker.  
**Proposed resolutions of open decisions:** OD-010 (profile created by trigger on `auth.users`), OD-012 (profiles own-row only; `public_profiles` view for others), OD-013 (`message_hides` table plus `deleted_for_everyone_at`). OD-009 follows the FRS demo ledger. OD-006, OD-007 and OD-008 remain open.  
**Full ADR:** `docs/architecture/architecture-decisions.md` ADL-018  
**Details:** `docs/database/database-schema.md`, `docs/database/requirements-traceability.md`

---

### DEC-ARCH-020 — Verify Supabase Access Tokens Through JWKS

**Status:** Recorded. **Phase:** 1. **Related:** FR-AUTH-006, security-architecture.

- **Context:** New Supabase projects sign access tokens with asymmetric signing keys (ES256). The backend only accepted HS256 with the legacy shared secret, so every authenticated request from such a project failed with 401.
- **Decision:** Choose the key by the token's algorithm. HS256 uses only `SUPABASE_JWT_SECRET`. ES256/RS256 use only the project's published public keys (`SUPABASE_URL/auth/v1/.well-known/jwks.json`, overridable with `SUPABASE_JWKS_URL`) and must carry the project's issuer. Any other algorithm, including `none`, is rejected. Keys are cached for 10 minutes; an unknown key id triggers a refetch, so key rotation works. An unreachable key endpoint returns 503, not 401.
- **New dependency:** `cryptography==50.0.2`, PyJWT's standard backend for ES256/RS256. No alternative avoids it short of hand-written crypto.
- **Consequences:** Verification may make a network call on a cold cache, so it runs in a worker thread. HS256 support stays for legacy projects and the test suite.
- **Alternatives considered:** Calling Supabase `GET /auth/v1/user` on every request (adds a network round trip per request); requiring projects to stay on the legacy secret (Supabase is phasing it out).
### DEC-PROD-001 — SMS Simulation Mode is the Default
**Date:** November 2026  
**Status:** ✅ Decided  
**Decision:** `SMS_PROVIDER_MODE=mock` is the default in all environments including production. Switching to live mode requires explicit operator approval and re-authentication.  
**Rationale:** Prevents accidental real SMS sends and real cost incurrence during development, testing, or misconfiguration.

---

### DEC-PROD-002 — AI Auto-Send is Permanently Prohibited
**Date:** November 2026  
**Status:** ✅ Decided — Permanent  
**Decision:** The AI assistant will never automatically send a message. This is a permanent architectural constraint with no exceptions, no configuration flags, and no future re-evaluation path.  
**Rationale:** User trust, safety, accountability. AI suggestions are proposals; humans send.

---

### DEC-PROD-003 — Philippine Sender Registration to Begin Phase 1
**Date:** November 2026  
**Status:** ✅ Decided (action not yet taken)  
**Decision:** Philippine A2P sender ID registration must be initiated during Phase 1 in parallel with development — not deferred to Phase 6.  
**Rationale:** Registration can take weeks to months. Starting late blocks PH live SMS at Phase 6.  
**Action:** Operations team to begin registration process within Phase 1 start.

---

### DEC-PROD-004 — Contact Discovery Without Enumeration

**Status:** Recorded. **Phase:** 1. **Related:** FR-CONTACTS-007, FR-PRIVACY-001, FR-PRIVACY-005.

- Strangers are found only by an exact username, email or verified mobile number. There is no browsing or prefix search of other users.
- Email and number lookup are opt-in (`discoverable_by_email`, `discoverable_by_phone`, both off by default). A username is findable unless the profile is `private`; the default `contacts` visibility still allows an exact-username request, because otherwise nobody could ever be added. The result card is limited to username, display name and photo.
- Not found, not discoverable, private, blocked and inactive all return the same empty result, and contact requests to such targets return the same "sent" response. A caller cannot learn whether an address or number is registered.
- Email lookup uses the service-role-only function `private.find_user_id_by_email`, because `auth.users` is not readable by clients.
- Rejected requests are invisible to the sender, who can ask again after 7 days. Blocks are invisible to the blocked person.
- Removing a Chikka contact deletes both directions of the relationship, since the relationship is mutual.
### DEC-SMS-001 — SMS Gateway Implementation (Phase 2)
**Date:** November 2026  
**Status:** ✅ Decided  
**Decision:** The SMS gateway follows `docs/architecture/sms-gateway-design.md`, implemented on the existing `messages` / `message_deliveries` / `provider_webhooks` schema, with these choices:
- **Provider interface:** `send_message`, `get_message_status`, `validate_webhook`, `parse_inbound_message`, `get_country_capabilities`, plus `parse_status_callback` (a delivery callback is not an inbound SMS). Twilio is called through `httpx` (no vendor SDK; no new dependency).
- **OD-011 (reply routing):** adopted the FRS route model. A (sender number, recipient number) pair belongs to one user for 30 days after their last message; no free sender number blocks the send with `sender_capacity`. Unmatched valid replies are kept server-side, hidden from users, listed for administrators, never auto-answered.
- **OD-009 (simulation and credits):** simulation never charges and shows a labelled demo "would cost" rate. Credits are not deducted in either mode in this phase; the ledger belongs to Phase 4.
- **Unverified routes:** unavailable in live mode, allowed in simulation with a visible warning. This deliberately refines FR-SMS-007 AC4 ("simulation uses the same rules").
- **Mode** is startup configuration, never a runtime toggle. If the database's active provider disagrees with the running provider, sends fail with `503 sms_mode_mismatch`.
- **Worker:** an in-process asyncio loop with row leases (`FOR UPDATE SKIP LOCKED`), not a broker. Dispatch is never inside a request handler. A claim that began and recorded no outcome is treated as an unknown outcome and is not resent.
- **Schema additions** (`20261112000001_sms_gateway.sql`): per-country price, supported number types, consent requirement and non-secret provider settings; a redacted `provider_response` per attempt.
- **Opt-out:** a keyword opt-out applies to every sender for that number; only the recipient's START or UNSTOP lifts it. "YES" is not an opt-in keyword.
**Open items:** see `docs/deployment/sms-live-activation.md` (facts to verify with Twilio, Philippine sender registration OD-007, Filipino keywords).
### DEC-LEGAL-001 — Independent Project Disclaimer Required
**Date:** November 2026  
**Status:** ✅ Decided — Permanent  
**Decision:** All public-facing surfaces of Chikka Reborn must clearly identify it as an independent, Chikka-inspired project. It must not imply official affiliation with or endorsement by the original Chikka owners or their telecom partners.  
**Implementation:** Disclaimer in README.md, product-vision.md, product-overview.md, and all marketing materials.

### DEC-ARCH-AI-001 - AI Assistant (Module F)
**Date:** November 2026  
**Status:** Decided  
**Decision:** Implemented as ADL-021: `AiProvider` abstraction with mock (default) and Bedrock (Converse over `httpx`, API key, no new dependency); opt-in per user (default off); drafts only; masked minimal context; metadata-only logging; server-side segment checks for SMS optimisation.  
**Open items:** OD-002 model choice; SigV4/IAM support if required; recording AI assistance on sent messages.

### DEC-ARCH-NOTIF-001 - Notifications and Simulated Credits (Modules G and H)
**Date:** November 2026  
**Status:** Decided. Supersedes the Phase 2 rule "simulation never charges" (OD-009) for the demo ledger.  
**Decision:** ADL-022. Simulated SMS reserve, spend and refund demo credits in an append-only ledger; real credit is never touched and live SMS is not metered until payments exist. Notifications are deduplicated by event key, grouped per chat, delivered after commit by an outbox dispatcher, with email through a configurable provider.  
**Open items:** admin UI for adjustments; purge job; web push; payments (out of scope).

---

## Decision Log Management

- All architectural decisions are recorded in both this log AND `docs/architecture/architecture-decisions.md` (full ADR format).
- When an open decision is resolved, it moves from the "Open Decisions" table to a "Recorded Decisions" entry.
- Decisions are never deleted. If a decision is reversed, a new entry records the reversal and references the original.
- This document is reviewed at the start of each phase.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft — 8 open, 9 recorded decisions |
