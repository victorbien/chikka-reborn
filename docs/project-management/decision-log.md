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
**Status:** ✅ Decided  
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

### DEC-LEGAL-001 — Independent Project Disclaimer Required
**Date:** November 2026  
**Status:** ✅ Decided — Permanent  
**Decision:** All public-facing surfaces of Chikka Reborn must clearly identify it as an independent, Chikka-inspired project. It must not imply official affiliation with or endorsement by the original Chikka owners or their telecom partners.  
**Implementation:** Disclaimer in README.md, product-vision.md, product-overview.md, and all marketing materials.

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
