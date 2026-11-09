# Assumptions and Constraints

**Document:** CHKR-PM-004  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all assumptions made during planning and all constraints imposed on the project. Assumptions that prove false require re-evaluation of the affected requirements and designs. Constraints are non-negotiable boundaries.

## Scope

All phases.

---

## 1. Assumptions

Assumptions are things believed to be true that have not yet been confirmed. If an assumption is proven false, the relevant specification and architecture must be revisited.

### Technical Assumptions

| ID | Assumption | Risk if False | Verification Method | Status |
|---|---|---|---|---|
| ASS-001 | Supabase Realtime handles Phase 1–2 concurrency (< 1,000 connections) without plan upgrade | Real-time messaging degrades | Load test with 1,000 concurrent WS connections in Phase 2 | ⬜ Unverified |
| ASS-002 | Twilio supports two-way SMS delivery to the Philippines via available routing | Inbound SMS unavailable for PH | Contact Twilio PH routing team | ⬜ Unverified |
| ASS-003 | Amazon Bedrock (Claude 3 or equivalent) is accessible from the chosen backend hosting region | AI features blocked | Confirm Bedrock region support before Phase 3 | ⬜ Unverified |
| ASS-004 | PostgreSQL row-level locking (`SELECT FOR UPDATE`) is sufficient to prevent credit over-deduction under concurrent sends | Double-spend possible | Concurrency integration test (UT-CRED-002) | ⬜ Unverified |
| ASS-005 | Supabase RLS policies do not introduce unacceptable query performance overhead | API response times degrade | Benchmark RLS-protected queries in Phase 1 | ⬜ Unverified |
| ASS-006 | Vite SPA + Vercel CDN achieves Lighthouse ≥ 85 without significant optimisation work | Performance target missed | Run Lighthouse on Phase 1 staging build | ⬜ Unverified |
| ASS-007 | The chosen backend hosting platform supports WebSocket connections long-term (not just HTTP) | Phase 2+ real-time custom WS layer fails | Confirm WebSocket support during OD-003 resolution | ⬜ Unverified |
| ASS-008 | FastAPI + SQLAlchemy async handles Phase 2 SMS burst (100 sends/minute) within capacity | SMS send queue backs up | Phase 2 load test | ⬜ Unverified |

### Product Assumptions

| ID | Assumption | Risk if False | Status |
|---|---|---|---|
| ASS-009 | Basic phone users (SMS recipients) have SMS capability | Inbound/outbound SMS doesn't reach them | Accepted — core premise of the product |
| ASS-010 | The primary development and staging environments will remain in simulation SMS mode | Real SMS costs incurred in development | Enforced by policy; `SMS_PROVIDER_MODE=mock` in dev/staging |
| ASS-011 | Payment processing for credit top-up is not needed before Phase 4 | Users cannot top up credits | Accepted product decision; free credits for Phase 1–3 testing |
| ASS-012 | The Classic Mode design can evoke the original Chikka without reproducing licensed assets | IP infringement risk | Enforced by policy; no licensed Chikka assets used without permission |

### Operational Assumptions

| ID | Assumption | Risk if False | Status |
|---|---|---|---|
| ASS-013 | A small team (1–3 engineers) can deliver Phase 1–3 sequentially | Timeline extends significantly | Accepted; roadmap designed for small team |
| ASS-014 | Supabase Pro plan (or equivalent) will be available for production with PITR and sufficient connection limits | Backup and scaling limitations | Upgrade plan as needed before Phase 6 |

---

## 2. Constraints

Constraints are fixed, non-negotiable boundaries that the project must operate within.

### Product Constraints (Permanent)

| ID | Constraint | Rationale |
|---|---|---|
| CON-001 | AI-generated content must never be sent without explicit user approval | Safety, trust, and integrity of AI assistant |
| CON-002 | SMS simulation mode messages must be permanently labelled "SIMULATED" | Honesty; prevents users from being misled about SMS delivery |
| CON-003 | Live SMS mode may never be activated without explicit operator approval and re-authentication | Prevents accidental real SMS sends and real cost incurrence |
| CON-004 | The platform must not claim two-way SMS availability in countries where it is not confirmed | Honesty; prevents misleading users about capabilities |
| CON-005 | SMS delivery status must never be reported as "Delivered" based solely on provider acceptance | Honesty; "accepted" and "delivered" are different states |
| CON-006 | The application must not use original Chikka trademarks, logos, or licensed assets without confirmed written permission | IP compliance |
| CON-007 | The project must be identified as an independent, Chikka-inspired project — not an official relaunch | Legal and ethical clarity |

### Technical Constraints

| ID | Constraint | Rationale |
|---|---|---|
| CON-008 | No provider credentials (Twilio, Bedrock, Supabase service role) may be bundled in the frontend | Security |
| CON-009 | All database schema changes must go through Supabase migration files | Reproducibility, audit trail |
| CON-010 | All AI calls must be proxied through the FastAPI backend | Security; prevents credential exposure |
| CON-011 | SMS provider credentials must be stored in environment variables only | Security |
| CON-012 | All user data tables must have RLS enabled with explicit policies | Security; data isolation |
| CON-013 | The platform must not introduce microservices unless a specific, documented scaling or isolation requirement demands it | Architectural simplicity |

### Technology Constraints

| ID | Constraint |
|---|---|
| CON-014 | Frontend must use: React, TypeScript, Vite, Tailwind CSS, shadcn/ui, React Router, TanStack Query, React Hook Form, Zod |
| CON-015 | Backend must use: Python, FastAPI, Pydantic, SQLAlchemy |
| CON-016 | Database and auth must use: Supabase PostgreSQL, Supabase Auth, Supabase Realtime, Supabase RLS |
| CON-017 | AI must use: Amazon Bedrock (with provider abstraction for future swap) |
| CON-018 | New libraries or frameworks may only be introduced with documented justification |

### Compliance Constraints

| ID | Constraint |
|---|---|
| CON-019 | SMS opt-out must be honoured immediately and permanently |
| CON-020 | Personal data erasure must be completed within 30 days of account deletion request |
| CON-021 | Phone numbers must be masked in all application logs |
| CON-022 | Privacy Policy and Terms of Service must be presented and agreed to before account creation (Phase 6) |

---

## 3. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
