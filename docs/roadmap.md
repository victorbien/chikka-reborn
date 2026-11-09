# Feature Development Roadmap

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  

---

## 1. Overview

The roadmap is structured as seven development phases. Each phase has a defined focus, a list of deliverables, a set of acceptance criteria, and explicit dependencies on previous phases.

No phase should be started until the previous phase's acceptance criteria are met. Major feature implementation must not begin before the relevant specification has been reviewed.

---

## 2. Phase Summary

| Phase | Name | Focus | Status |
|---|---|---|---|
| 0 | Foundation | Documentation, project setup, tooling | ✅ In Progress |
| 1 | Core Platform | Auth, profiles, Chikka-to-Chikka messaging | Not started |
| 2 | SMS Integration | Internet-to-SMS, SMS-to-Internet, simulation mode | Not started |
| 3 | AI Features | Smart replies, translation, rewriting, summaries | Not started |
| 4 | Credits and Admin | Credit management, billing, admin dashboard | Not started |
| 5 | Classic Mode and Polish | Nostalgic UI, accessibility, i18n | Not started |
| 6 | Production Hardening | Security audit, load testing, final deployment | Not started |

---

## 3. Phase 0 — Foundation

**Goal:** Establish the complete documentation, tooling, and project scaffolding foundation before any feature code is written.

### Deliverables

| # | Deliverable | Owner | Status |
|---|---|---|---|
| 0.1 | Repository initialised | Engineering | ✅ Done |
| 0.2 | README.md | Engineering | ✅ Done |
| 0.3 | Kiro steering documents | Engineering | ✅ Done |
| 0.4 | Product Requirements Document (PRD) | Product | ✅ Done |
| 0.5 | Functional Requirements Specification (FRS) | Engineering | ✅ Done |
| 0.6 | Non-Functional Requirements Specification (NFRS) | Engineering | ✅ Done |
| 0.7 | Architecture documentation | Engineering | ✅ Done |
| 0.8 | Database design documentation | Engineering | ✅ Done |
| 0.9 | API design documentation | Engineering | ✅ Done |
| 0.10 | Testing strategy | Engineering | ✅ Done |
| 0.11 | Deployment strategy | Engineering | ✅ Done |
| 0.12 | Feature roadmap (this document) | Product | ✅ Done |
| 0.13 | Risks and dependencies register | Engineering | ✅ Done |
| 0.14 | Supabase project created (dev + staging) | DevOps | ⬜ Pending |
| 0.15 | Frontend scaffold (Vite + React + Tailwind + shadcn) | Engineering | ⬜ Pending |
| 0.16 | Backend scaffold (FastAPI + SQLAlchemy + config) | Engineering | ⬜ Pending |
| 0.17 | CI pipeline configured (lint, type check, test) | DevOps | ⬜ Pending |
| 0.18 | Vercel project connected | DevOps | ⬜ Pending |
| 0.19 | Backend hosting project created | DevOps | ⬜ Pending |
| 0.20 | `.env.example` files created | Engineering | ⬜ Pending |

### Phase 0 Acceptance Criteria

- All documentation files exist in `docs/` and are internally consistent.
- Steering documents load correctly in Kiro.
- Frontend scaffold builds without errors: `npm run build`.
- Backend scaffold starts without errors: `uvicorn main:app`.
- CI pipeline runs on a test PR and passes.
- Empty staging deployment accessible at its URL.

---

## 4. Phase 1 — Core Platform

**Goal:** A working, deployable messaging platform. Registered users can exchange real-time messages. No SMS yet.

**Dependencies:** Phase 0 complete. Supabase project operational.

### Deliverables

| # | Deliverable | Modules | Key FRs |
|---|---|---|---|
| 1.1 | User registration and login | A | FR-A-001, FR-A-002, FR-A-003, FR-A-004 |
| 1.2 | Password reset | A | FR-A-005 |
| 1.3 | Login rate limiting | A | FR-A-006 |
| 1.4 | User profile create/edit | A | FR-A-007 |
| 1.5 | Account deletion | A | FR-A-009 |
| 1.6 | Add Chikka contacts | B | FR-B-001 |
| 1.7 | Contact list display with presence | B | FR-B-003 |
| 1.8 | Block contact | B | FR-B-004 |
| 1.9 | Real-time messaging (Modern Mode) | C | FR-C-001, FR-C-002, FR-C-003 |
| 1.10 | Conversation history with pagination | C | FR-C-004 |
| 1.11 | Emoji support | C | FR-C-006 |
| 1.12 | In-app notifications (new message badge) | G | FR-G-001 |
| 1.13 | Profile visibility controls | I | FR-I-001 |
| 1.14 | Modern Mode UI (split panel, responsive) | K | FR-K-003 |
| 1.15 | Database migrations: profiles, contacts, conversations, messages | — | — |
| 1.16 | RLS policies for all Phase 1 tables | — | — |
| 1.17 | Backend unit and API integration tests | — | — |
| 1.18 | Frontend component tests | — | — |
| 1.19 | Staging deployment | — | — |

### Phase 1 Acceptance Criteria

- User A can register, verify email, and log in.
- User A can find User B and add them as a contact.
- User A can open a conversation with User B and exchange messages in real time.
- Messages persist across page refresh.
- User A sees a badge when User B sends a message while A is elsewhere.
- Typing indicator works.
- All Phase 1 backend tests pass in CI.
- No known security issues from OWASP review.
- Staging URL is publicly accessible.

---

## 5. Phase 2 — SMS Integration

**Goal:** Internet-to-SMS messaging works in simulation mode. Inbound SMS appears in conversations. SMS-to-Internet messaging works. Basic credit tracking is in place.

**Dependencies:** Phase 1 complete. SMS provider account created (Twilio or mock-only for Phase 2).

### Deliverables

| # | Deliverable | Modules | Key FRs |
|---|---|---|---|
| 2.1 | MockSmsProvider and TwilioSmsProvider | D | (architecture) |
| 2.2 | SMS compose and send (simulation mode) | D | FR-D-001, FR-D-002, FR-D-003 |
| 2.3 | SMS segment and credit preview | D | FR-D-002 |
| 2.4 | Simulation mode labelling | D | FR-D-003 |
| 2.5 | SMS delivery status tracking | D | FR-D-004 |
| 2.6 | Insufficient credit prevention | D | FR-D-005 |
| 2.7 | Inbound SMS webhook | E | FR-E-001, FR-E-002 |
| 2.8 | Inbound SMS matched to conversation | E | FR-E-001 |
| 2.9 | SMS origin labelling in conversation | E | FR-E-003 |
| 2.10 | Webhook signature validation | E | FR-E-002 |
| 2.11 | Phone number verification (OTP) | A | FR-A-008 |
| 2.12 | Add SMS contacts | B | FR-B-002 |
| 2.13 | Country capability check API | — | — |
| 2.14 | Credit balance display | H | FR-H-001 |
| 2.15 | Per-country credit pricing config | H | FR-H-002 |
| 2.16 | Credit deduction and refund logic | H | FR-H-003 |
| 2.17 | SMS retry with exponential backoff | — | (NFRS) |
| 2.18 | Idempotency key enforcement | — | (sms-guidelines) |
| 2.19 | Browser push notifications | G | FR-G-002 |
| 2.20 | SMS delivery notifications | G | FR-G-003 |
| 2.21 | Data export (user data) | I | FR-I-002 |
| 2.22 | SMS opt-out handling | I | FR-I-003 |
| 2.23 | Message reporting | I | FR-I-004 |
| 2.24 | Basic admin dashboard (stats, user mgmt) | J | FR-J-001, FR-J-002 |
| 2.25 | Admin SMS provider mode toggle | J | FR-J-003 |
| 2.26 | SMS audit log view | J | FR-J-004 |
| 2.27 | Country capability management (admin) | J | FR-J-005 |
| 2.28 | Database migrations: outbound_sms, inbound_sms, credits, notifications | — | — |
| 2.29 | SMS webhook tests (signature valid/invalid, delivery events) | — | — |
| 2.30 | E2E SMS simulation journey | — | — |

### Phase 2 Acceptance Criteria

- User can send an SMS in simulation mode; "SIMULATED" badge is visible.
- Delivery status progresses from Queued → Sent → Delivered via mock callbacks.
- An SMS reply from a simulated phone number appears in the conversation.
- Webhook with invalid signature is rejected with 403.
- User with zero credits cannot send an SMS.
- Credits are correctly deducted and refunded on simulated failure.
- Admin can toggle SMS mode (simulation only; live mode requires explicit approval).
- Country capability API returns correct data for Philippines and test countries.

---

## 6. Phase 3 — AI Features

**Goal:** The AI assistant is available in the messaging interface. All AI features require user approval before sending.

**Dependencies:** Phase 1 complete. Amazon Bedrock access confirmed in target AWS region.

### Deliverables

| # | Deliverable | Modules | Key FRs |
|---|---|---|---|
| 3.1 | Amazon Bedrock provider implementation | F | (ai-guidelines) |
| 3.2 | AI provider abstraction layer | F | (ai-guidelines) |
| 3.3 | Smart reply suggestions | F | FR-F-001 |
| 3.4 | Message translation | F | FR-F-002 |
| 3.5 | Message rewriting | F | FR-F-003 |
| 3.6 | SMS length optimisation | F | FR-F-004 |
| 3.7 | Conversation summary | F | FR-F-005 |
| 3.8 | Mandatory approval gate (no auto-send) | F | FR-F-006 |
| 3.9 | AI-assisted badge (pre-send) | F | (ai-guidelines) |
| 3.10 | AI usage metadata logging (no content) | F | (ai-guidelines) |
| 3.11 | AI feature graceful failure | F | (ai-guidelines) |
| 3.12 | AI metrics in admin dashboard | J | — |
| 3.13 | AI provider tests (mocked Bedrock) | — | — |
| 3.14 | E2E AI assistant journey | — | — |

### Phase 3 Acceptance Criteria

- Smart reply suggestions appear in a panel; selecting one populates compose field but does not send.
- AI-assisted badge is visible before sending; not visible in sent message history to recipient.
- AI failure (mocked timeout) shows error message; compose field remains fully usable.
- AI calls never appear in application logs with message content.
- Admin dashboard shows AI usage metrics (feature, count, tokens, latency).

---

## 7. Phase 4 — Credits and Administration

**Goal:** Full credit management including top-up. Complete admin dashboard.

**Dependencies:** Phase 2 complete. Payment gateway decision finalised (OD-001).

### Deliverables

| # | Deliverable | Modules | Key FRs |
|---|---|---|---|
| 4.1 | Credit top-up flow (payment gateway TBD) | H | FR-H-004 |
| 4.2 | Credit transaction history | H | — |
| 4.3 | Low-balance warning notifications | H | — |
| 4.4 | Full admin dashboard (all metrics) | J | FR-J-001–005 |
| 4.5 | Admin credit adjustment | J | — |
| 4.6 | Admin user suspension / reinstatement | J | FR-J-002 |
| 4.7 | Per-user AI rate limiting | F | (ai-guidelines) |
| 4.8 | Contact groups | B | FR-B-005 |
| 4.9 | Message deletion (both scopes) | C | FR-C-005 |

### Phase 4 Acceptance Criteria

- User can top up credits via payment gateway and see updated balance.
- Admin can adjust a user's credit balance with audit trail.
- Admin can suspend a user; suspended user cannot log in.
- Low-balance notification appears before attempted send.

---

## 8. Phase 5 — Classic Mode and Polish

**Goal:** Classic Chikka Mode is implemented. Accessibility is fully audited. Internationalisation is ready.

**Dependencies:** Phase 1–2 complete. Classic Mode design assets finalised.

### Deliverables

| # | Deliverable | Modules | Key FRs |
|---|---|---|---|
| 5.1 | Classic Chikka Mode UI | K | FR-K-001, FR-K-002 |
| 5.2 | Mode toggle with profile persistence | K | FR-K-001 |
| 5.3 | WCAG 2.1 AA accessibility audit and remediation | — | NFR-U-001 |
| 5.4 | i18n string externalisation (Filipino, English minimum) | — | NFR-U-004 |
| 5.5 | Responsive layout audit (mobile, tablet, desktop) | — | NFR-U-002 |
| 5.6 | Lighthouse performance audit and optimisation | — | NFR-P-004 |
| 5.7 | Full E2E test suite coverage for Classic Mode | — | — |

### Phase 5 Acceptance Criteria

- Classic Mode is visually distinct and evokes the original Chikka aesthetic using original-inspired design (no licensed assets without permission).
- All core features function in Classic Mode.
- Lighthouse score ≥ 85 on mobile and desktop.
- axe accessibility scan reports zero critical violations.
- Filipino and English UI strings available via i18n system.

---

## 9. Phase 6 — Production Hardening

**Goal:** The platform is ready for real users. Security audited, load tested, monitoring complete.

**Dependencies:** All previous phases complete.

### Deliverables

| # | Deliverable | Focus |
|---|---|---|
| 6.1 | OWASP Top 10 security review | Security |
| 6.2 | Load testing (k6 or Locust) | Performance |
| 6.3 | Penetration testing (scope TBD) | Security |
| 6.4 | Live SMS mode activation (Philippines pilot) | SMS |
| 6.5 | Twilio Philippine sender ID registration | Compliance |
| 6.6 | Privacy Policy and Terms of Service (legal review) | Legal/Compliance |
| 6.7 | Production monitoring and alerting | Operations |
| 6.8 | Disaster recovery drill | Operations |
| 6.9 | Final production launch checklist | — |

### Phase 6 Acceptance Criteria

- Load test: platform handles 1,000 concurrent users without degradation.
- Security review: no critical or high-severity open findings.
- Live SMS: test message successfully delivered to a real Philippine mobile number.
- Privacy Policy and ToS reviewed by a qualified party.
- Monitoring alerts fire correctly on test error injection.

---

## 10. Cross-Phase Constraints

- **SMS live mode** requires explicit operator approval at every stage. It must never be activated automatically.
- **AI auto-send** is permanently prohibited in all phases. This is not a feature to be added in a later phase.
- **Phase gate reviews** are required before starting Phase 2, Phase 3, and Phase 6. No gate for Phase 4 and 5 assuming Phase 1–2 are stable.
- **Documentation must remain current.** Architecture, database, and API documents must be updated when implementation deviates from them.

---

## 11. Out-of-Scope (Deferred Indefinitely)

| Feature | Reason |
|---|---|
| Native mobile apps (iOS/Android) | Out of scope this version |
| Group SMS / MMS | Technically complex, low Phase 1–2 priority |
| Voice/video calling | Out of scope |
| End-to-end encryption for SMS | SMS is inherently unencrypted at the carrier level |
| AI auto-send | **Permanently prohibited** |
| Official Chikka branding | Requires IP permissions not yet obtained |

---

## 12. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
