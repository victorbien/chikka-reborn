# Development Backlog

**Document:** CHKR-PM-002  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Living Document — updated each phase  
**Last Revised:** November 2026  

---

## Purpose

The initial development backlog for Chikka Reborn — organised by phase, with user stories and implementation tasks. This document is updated at the start of each phase as open decisions are resolved and task estimates are refined.

## Scope

Phase 0 (current) through Phase 2 (planned). Phase 3+ backlog is outlined pending resolution of OD-002 (Bedrock model).

---

## Phase 0 — Foundation (Current)

### Status: In Progress

| ID | Task | Owner | Status |
|---|---|---|---|
| BL-P0-001 | Resolve OD-003: Select backend hosting platform | DevOps | ⬜ Open |
| BL-P0-002 | Resolve OD-008: Select Supabase region | DevOps/Legal | ⬜ Open |
| BL-P0-003 | Create Supabase dev project | DevOps | ⬜ Open |
| BL-P0-004 | Create Supabase staging project | DevOps | ⬜ Open |
| BL-P0-005 | Connect Vercel to GitHub repository | DevOps | ⬜ Open |
| BL-P0-006 | Create backend hosting project | DevOps | ⬜ Open |
| BL-P0-007 | Scaffold frontend (Vite + React + Tailwind + shadcn) | Engineering | ⬜ Open |
| BL-P0-008 | Scaffold backend (FastAPI + SQLAlchemy + pydantic-settings) | Engineering | ⬜ Open |
| BL-P0-009 | Implement /health endpoint | Engineering | ⬜ Open |
| BL-P0-010 | Configure GitHub Actions CI pipeline (lint + type + test + build) | DevOps | ⬜ Open |
| BL-P0-011 | Create backend `.env.example` | Engineering | ⬜ Open |
| BL-P0-012 | Create frontend `.env.example` | Engineering | ⬜ Open |
| BL-P0-013 | Deploy empty scaffold to staging | DevOps | ⬜ Open |
| BL-P0-014 | Verify Phase 0 acceptance criteria (AC-0-001 through AC-0-012) | Engineering | ⬜ Open |

---

## Phase 1 — Core Platform

### Database

| ID | Story | Tasks |
|---|---|---|
| BL-P1-DB-001 | Create initial schema migrations | Write and apply: profiles, contacts, conversations, conversation_participants, messages, notifications |
| BL-P1-DB-002 | Implement RLS policies | All Phase 1 tables — in same migration files |
| BL-P1-DB-003 | Write RLS isolation tests | `tests/rls/test_rls.py` covering all tables |
| BL-P1-DB-004 | Create `updated_at` trigger function | Applied to all mutable tables |

### Backend — Auth

| ID | Story | Tasks |
|---|---|---|
| BL-P1-BE-AUTH-001 | As a new user, I can register with email and password | `POST /auth/register`, Supabase Auth integration, email verification trigger |
| BL-P1-BE-AUTH-002 | As a user, I can log in | `POST /auth/login`, JWT validation dependency |
| BL-P1-BE-AUTH-003 | As a user, I can reset my password | `POST /auth/reset-password`, confirm endpoint |
| BL-P1-BE-AUTH-004 | Login is rate-limited | Rate limiting middleware; 5 attempts / 15 min / IP |
| BL-P1-BE-AUTH-005 | As a user, I can manage my profile | `GET/PATCH /users/me`, avatar upload |
| BL-P1-BE-AUTH-006 | As a user, I can delete my account | `DELETE /users/me`, re-auth requirement |
| BL-P1-BE-AUTH-007 | As a user, I can control profile visibility | Privacy settings stored in profile |
| BL-P1-BE-AUTH-008 | Auth tests | `tests/api/test_auth_routes.py` covering UT-AUTH-001 through UT-AUTH-018 |

### Backend — Contacts

| ID | Story | Tasks |
|---|---|---|
| BL-P1-BE-CONT-001 | As a user, I can search for Chikka users | `GET /users/search` with pagination |
| BL-P1-BE-CONT-002 | As a user, I can add a Chikka user as a contact | `POST /contacts` (chikka type) |
| BL-P1-BE-CONT-003 | As a user, I can view my contact list | `GET /contacts` with pagination |
| BL-P1-BE-CONT-004 | As a user, I can block a contact | `POST /contacts/:id/block` |
| BL-P1-BE-CONT-005 | Contacts tests | `tests/api/test_contacts_routes.py` |

### Backend — Messaging

| ID | Story | Tasks |
|---|---|---|
| BL-P1-BE-MSG-001 | As a user, I can start a conversation | `POST /conversations` |
| BL-P1-BE-MSG-002 | As a user, I can send a message | `POST /conversations/:id/messages` |
| BL-P1-BE-MSG-003 | As a user, I can see message delivery status | `PATCH .../messages/:id/status`, Realtime publication |
| BL-P1-BE-MSG-004 | As a user, I can load message history | `GET .../messages` with cursor pagination |
| BL-P1-BE-MSG-005 | Messaging tests | `tests/api/test_messaging_routes.py` |

### Frontend — Auth

| ID | Story | Tasks |
|---|---|---|
| BL-P1-FE-AUTH-001 | Login screen | SCR-AUTH-001: form, validation, OAuth buttons |
| BL-P1-FE-AUTH-002 | Registration screen | SCR-AUTH-002: form, Zod validation |
| BL-P1-FE-AUTH-003 | Email verification prompt | SCR-AUTH-003 |
| BL-P1-FE-AUTH-004 | Password reset screens | SCR-AUTH-004, SCR-AUTH-005 |
| BL-P1-FE-AUTH-005 | Route protection | Redirect to /login if unauthenticated |

### Frontend — Messaging

| ID | Story | Tasks |
|---|---|---|
| BL-P1-FE-MSG-001 | Conversation list screen | SCR-MAIN-001 with all states |
| BL-P1-FE-MSG-002 | Active conversation screen | SCR-MAIN-002: message bubbles, compose area |
| BL-P1-FE-MSG-003 | Real-time message delivery | Supabase Realtime subscription |
| BL-P1-FE-MSG-004 | Typing indicator | Realtime broadcast |
| BL-P1-FE-MSG-005 | Contacts screen | SCR-MAIN-003 with search and add |

---

## Phase 2 — SMS Integration (Planned)

High-level backlog items. Detailed tasks to be written at Phase 2 planning.

| ID | Epic | Key Deliverables |
|---|---|---|
| BL-P2-SMS-001 | SMS Provider Abstraction | `SmsProvider` ABC, `MockSmsProvider`, `TwilioSmsProvider` |
| BL-P2-SMS-002 | Outbound SMS Send | `/sms/send` endpoint with idempotency, credits, simulation mode |
| BL-P2-SMS-003 | Delivery Webhooks | `/webhooks/sms/status` with signature validation |
| BL-P2-SMS-004 | Inbound SMS | `/webhooks/sms/inbound` with conversation matching |
| BL-P2-SMS-005 | SMS Retry System | Exponential backoff, permanent failure, credit refund |
| BL-P2-CREDIT-001 | Credit System | Accounts, deduction, refund, transaction ledger |
| BL-P2-ADMIN-001 | Admin Dashboard | Stats, user management, SMS audit log, mode toggle |
| BL-P2-FE-SMS-001 | SMS Compose Screen | SCR-SMS-001 with segment counter, credit cost |
| BL-P2-FE-ADMIN-001 | Admin Screens | SCR-ADMIN-001 through SCR-ADMIN-005 |

---

## Phase 3+ Backlog (Outline)

| Phase | Epics |
|---|---|
| 3 | AI provider abstraction, Bedrock integration, all 7 AI features, AI suggestion panel |
| 4 | Payment gateway integration, credit top-up, full admin credit views |
| 5 | Classic Mode UI, WCAG audit, i18n (Filipino + English), Lighthouse ≥ 85 |
| 6 | OWASP audit, k6 load tests, PH live SMS, Privacy Policy, production launch |

---

## Backlog Management Rules

- Tasks are written with enough detail for any team member to pick up and implement.
- Each task links to its feature catalogue entry (`FEAT-xxx-nnn`) and functional requirement (`FR-xxx-nnn`).
- When an open decision is resolved, affected backlog items are updated.
- Completed tasks are marked with ✅; they remain in the backlog for historical reference.
- This document is updated at the start of each phase with detailed tasks for that phase.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft — Phase 0 detailed, Phase 1-2 planned |
