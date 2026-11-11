# Acceptance Criteria

**Document:** CHKR-QA-003  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Defines the formal acceptance criteria for each development phase. A phase is considered complete only when all criteria in its section are met and verified on the staging environment.

## Scope

Phases 0–6. Each phase's criteria must be signed off by the engineering lead before the next phase begins.

---

## Phase 0 — Foundation

**All items must be verifiable without running the application.**

| AC-0-001 | All documentation files exist in their defined locations |
| AC-0-002 | All Kiro steering documents load correctly in the IDE |
| AC-0-003 | No broken cross-document links |
| AC-0-004 | Backend hosting platform decision recorded (OD-003 resolved) |
| AC-0-005 | Supabase region decision recorded (OD-008 resolved) |
| AC-0-006 | `frontend/` scaffold: `npm run build` exits 0 with no errors |
| AC-0-007 | `backend/` scaffold: `uvicorn app.main:app` starts with no errors |
| AC-0-008 | `GET /api/v1/health` (and `/healthz`) returns `{ "status": "ok", ... }` |
| AC-0-009 | CI pipeline runs on test PR; all checks pass |
| AC-0-010 | Staging frontend URL accessible and returns the app shell |
| AC-0-011 | `.env.example` files exist for frontend and backend with all required variables documented |
| AC-0-012 | No hardcoded secrets in any committed file |

**Sign-off required before Phase 1 begins.**

---

## Phase 1 — Core Platform

| ID | Criterion |
|---|---|
| AC-1-001 | New user can register with email + password and receive a verification email |
| AC-1-002 | Unverified user can log in but sees persistent verification prompt |
| AC-1-003 | Email verification link activates account |
| AC-1-004 | Login rate limiting: 5 failures → 15-minute lockout |
| AC-1-005 | Password reset flow: link emailed, expires after 1 hour, all sessions invalidated after reset |
| AC-1-006 | User profile: display name, avatar, bio, country code, UI mode editable |
| AC-1-007 | Profile visibility: private profiles excluded from contact search |
| AC-1-008 | User A can search for User B and add them as a Chikka contact |
| AC-1-009 | Block contact: blocked user cannot send messages or see presence |
| AC-1-010 | User A opens conversation with User B; message sent and received in real time (< 500ms p95) |
| AC-1-011 | Typing indicator visible within 500ms; disappears within 3s of stopping |
| AC-1-012 | Message delivery status shows Sent → Delivered → Read with timestamps |
| AC-1-013 | Conversation history loads most recent 50 messages; loads more on scroll |
| AC-1-014 | Date separators appear between messages from different days |
| AC-1-015 | Messages persist across page refresh |
| AC-1-016 | Emoji in messages display correctly in Modern Mode |
| AC-1-017 | In-app notification badge appears when a new message arrives |
| AC-1-018 | Unread count appears in browser tab title |
| AC-1-019 | Account deletion: re-authentication required; sessions invalidated immediately; data erasure scheduled |
| AC-1-020 | All Phase 1 backend tests pass in CI |
| AC-1-021 | No open critical or high OWASP findings from pre-phase review |
| AC-1-022 | Lighthouse score ≥ 80 on staging (provisional; target ≥ 85 by Phase 5) |
| AC-1-023 | All RLS isolation tests pass (users cannot read each other's data) |

**Sign-off required before Phase 2 begins.**

---

## Phase 2 — SMS Integration

| ID | Criterion |
|---|---|
| AC-2-001 | User with verified phone can associate it via OTP verification |
| AC-2-002 | SMS contact added with valid E.164 number |
| AC-2-003 | SMS country capability displayed accurately before composing |
| AC-2-004 | Character + segment counter updates in real time as user types |
| AC-2-005 | Credit cost displayed per segment before sending |
| AC-2-006 | Send button disabled when credit balance insufficient |
| AC-2-007 | Low-balance warning appears in UI |
| AC-2-008 | SMS sent in simulation mode returns `is_simulated: true` |
| AC-2-009 | SIMULATED badge permanently visible on every simulated message (list, detail, status) |
| AC-2-010 | Delivery status progresses: Queued → Sent → Delivered via mock callbacks |
| AC-2-011 | Credits deducted on acceptance; refunded on permanent failure |
| AC-2-012 | Duplicate idempotency key returns original response; no double-send, no double-deduction |
| AC-2-013 | Inbound SMS webhook with valid signature processes message |
| AC-2-014 | Inbound SMS webhook with invalid signature returns 403; not processed |
| AC-2-015 | Matched inbound SMS appears in correct conversation thread in real time |
| AC-2-016 | Inbound SMS messages show SMS origin label |
| AC-2-017 | Admin can view SMS audit log (masked recipient numbers) |
| AC-2-018 | Admin SMS mode toggle requires re-authentication + confirmation dialog |
| AC-2-019 | Philippines country capability: `outbound: true`, `inbound` marked as requires-verification |
| AC-2-020 | Opted-out phone number cannot receive SMS; sender notified |
| AC-2-021 | All Phase 2 backend tests pass in CI |
| AC-2-022 | E2E SMS simulation journey passes in Playwright |

**Sign-off required before Phase 3 begins.**

---

## Phase 3 — AI Features

| ID | Criterion |
|---|---|
| AC-3-001 | Smart reply suggestions appear in review panel; selecting one populates compose field only |
| AC-3-002 | Compose field remains fully functional while AI request is in progress |
| AC-3-003 | Translation suggestion shows before/after; user can edit before accepting |
| AC-3-004 | AI rewrite with `make_formal` instruction produces visibly formal output |
| AC-3-005 | SMS optimise: optimised text fits within target segments; `meaning_preserved` flag accurate |
| AC-3-006 | If meaning cannot be preserved, AI states this — never silently truncates |
| AC-3-007 | Conversation summary appears in panel; not inserted into conversation |
| AC-3-008 | AI-assisted badge visible on compose field when AI content present |
| AC-3-009 | AI-assisted badge NOT visible to recipient in sent message history |
| AC-3-010 | AI provider failure shows user-readable error; messaging continues normally |
| AC-3-011 | No AI call ever auto-sends a message |
| AC-3-012 | `ai_usage_logs` contains no message body content |
| AC-3-013 | Admin AI metrics dashboard shows feature counts, token totals, latency |
| AC-3-014 | All Phase 3 backend tests pass in CI |
| AC-3-015 | E2E AI translation journey passes in Playwright |

---

## Phase 4 — Credits and Administration

| ID | Criterion |
|---|---|
| AC-4-001 | Credit top-up flow initiated; credits added only after payment confirmation |
| AC-4-002 | Credit balance updates in real time after top-up |
| AC-4-003 | Admin can view credit transactions across all users |
| AC-4-004 | Concurrent send test: balance never goes below zero under race conditions |
| AC-4-005 | Admin can suspend a user; suspended user cannot log in but data preserved |

---

## Phase 5 — Classic Mode and Polish

| ID | Criterion |
|---|---|
| AC-5-001 | Classic Mode toggle available in settings; preference saved to profile |
| AC-5-002 | All core features functional in Classic Mode (messaging, SMS, contacts) |
| AC-5-003 | Classic Mode visually distinct from Modern Mode |
| AC-5-004 | Classic Mode does not reproduce licensed Chikka assets |
| AC-5-005 | axe accessibility scan: zero critical violations on all 24 screens |
| AC-5-006 | Keyboard navigation: every interactive element reachable without mouse |
| AC-5-007 | Lighthouse Performance ≥ 85 on mobile and desktop on staging |
| AC-5-008 | Filipino UI strings functional via i18n system (minimum: login, registration, settings screens) |
| AC-5-009 | All layouts verified at 375px, 768px, 1280px |

---

## Phase 6 — Production Hardening

| ID | Criterion |
|---|---|
| AC-6-001 | OWASP Top 10 review complete; no open critical or high findings |
| AC-6-002 | Load test: platform handles 1,000 concurrent users without API response time degradation |
| AC-6-003 | Load test: WebSocket connections stable at 1,000 concurrent clients |
| AC-6-004 | Privacy Policy and Terms of Service reviewed by a qualified party and published |
| AC-6-005 | Live SMS: test message delivered to a real phone in a supported country |
| AC-6-006 | Philippines live SMS: sender ID registration confirmed (or outbound marked pending) |
| AC-6-007 | Production monitoring: health check alert fires on injected failure |
| AC-6-008 | Disaster recovery drill: production restore from PITR backup verified |
| AC-6-009 | All production launch checklist items checked (see `docs/deployment/deployment-guide.md`) |

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
