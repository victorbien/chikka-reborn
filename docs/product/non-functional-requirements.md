# Non-Functional Requirements

**Document:** CHKR-PROD-006  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document specifies the quality attributes of Chikka Reborn — how it performs, scales, stays available, remains secure, and can be maintained. It uses domain-prefixed requirement IDs that supersede the `NFR-xxx` scheme in `docs/nfrs.md`.

## Scope

All environments (development, staging, production) unless otherwise stated. Production targets are explicitly labelled.

---

## Performance

### NFR-PERF-001 — Real-Time Message Latency
**Priority:** MVP | **Phase:** 1  
End-to-end Chikka-to-Chikka message delivery must complete in under 500ms (p95) when both users are online.  
*Measurement: sender WebSocket send → recipient WebSocket receive.*

### NFR-PERF-002 — API Response Time
**Priority:** MVP | **Phase:** 1  
95% of REST API responses must complete within 300ms under normal load, excluding SMS-send and AI endpoints.

### NFR-PERF-003 — AI Feature Latency
**Priority:** POST-MVP | **Phase:** 3  
AI suggestion generation must complete within 5 seconds (p95). UI must show a loading indicator during processing. AI failures must not block manual messaging.

### NFR-PERF-004 — Frontend Performance Score
**Priority:** POST-MVP | **Phase:** 5  
Lighthouse Performance score ≥ 85 on both mobile and desktop.  
*Measured against the production Vercel deployment.*

### NFR-PERF-005 — SMS Send Throughput
**Priority:** POST-MVP | **Phase:** 2  
The backend must handle up to 100 outbound SMS initiations per minute per environment without degradation.  
*Note: actual provider throughput is subject to Twilio rate limits — verification required.*

---

## Scalability

### NFR-SCALE-001 — Stateless Backend
**Priority:** MVP | **Phase:** 1  
The FastAPI backend must be stateless. Any instance must be able to handle any request. No in-process session state.

### NFR-SCALE-002 — WebSocket Connection Capacity
**Priority:** MVP | **Phase:** 1  
The platform must support at least 1,000 concurrent WebSocket connections in Phase 1, with a documented path to 10,000 by Phase 3.  
*Phase 1: Supabase Realtime. Phase 2+: custom FastAPI WebSocket + Redis pub/sub if limits are reached.*

### NFR-SCALE-003 — Database Connection Pooling
**Priority:** MVP | **Phase:** 1  
The backend must use SQLAlchemy async connection pooling. Maximum pool size must be configurable via environment variable. The application must degrade gracefully (queue requests) rather than crash when the pool is exhausted.

### NFR-SCALE-004 — CDN Asset Delivery
**Priority:** MVP | **Phase:** 1  
Frontend static assets must be served via Vercel's edge CDN. Versioned assets (hashed filenames) must have `Cache-Control: public, max-age=31536000, immutable`.

---

## Availability and Reliability

### NFR-AVAIL-001 — Production Uptime Target
**Priority:** POST-MVP | **Phase:** 6  
Platform target: 99.5% monthly uptime in production, excluding planned maintenance windows.  
*(Approx. 3.6 hours unplanned downtime per month maximum.)*

### NFR-AVAIL-002 — Graceful Subsystem Degradation
**Priority:** MVP | **Phase:** 2  
An AI subsystem failure must not degrade core messaging. An SMS subsystem failure must not degrade Chikka-to-Chikka messaging. Each subsystem fails independently.

### NFR-AVAIL-003 — SMS Retry Reliability
**Priority:** MVP | **Phase:** 2  
Transient SMS failures must be retried with exponential backoff and jitter. Maximum retries: configurable (default 3). Exhausted retries → message permanently failed, user notified, credits refunded.

### NFR-AVAIL-004 — Database Backup
**Priority:** POST-MVP | **Phase:** 2  
Daily automated backups with minimum 7-day retention. Point-in-time recovery available on Supabase Pro plan or equivalent.

### NFR-AVAIL-005 — WebSocket Auto-Reconnect
**Priority:** MVP | **Phase:** 1  
The frontend WebSocket client must reconnect automatically on disconnect, using exponential backoff, up to a configurable retry limit.

---

## Security

### NFR-SEC-001 — JWT Authentication on All Protected Routes
**Priority:** MVP | **Phase:** 1  
All authenticated API routes must validate a Supabase JWT. Expired or invalid tokens return HTTP 401.

### NFR-SEC-002 — Row Level Security on All Tables
**Priority:** MVP | **Phase:** 1  
Every table containing user data must have tested RLS policies. No table accessible to authenticated users without an explicit policy.

### NFR-SEC-003 — Secrets Management
**Priority:** MVP | **Phase:** 1  
All secrets, API keys, and credentials stored as environment variables. Never committed to version control. Never bundled into frontend assets.

### NFR-SEC-004 — TLS Everywhere
**Priority:** MVP | **Phase:** 1  
All client↔server, server↔database, and server↔provider communication must use TLS. HTTP not used in production.

### NFR-SEC-005 — Input Validation on All External Data
**Priority:** MVP | **Phase:** 1  
All inputs from users, webhooks, and provider APIs must be validated with Pydantic models before processing. Invalid input rejected with structured error.

### NFR-SEC-006 — Rate Limiting
**Priority:** MVP | **Phase:** 1  
Mandatory rate limits:
- Login: 5 attempts / 15 min / IP.
- Password reset: 3 attempts / 1 hr / IP.
- OTP send: 3 attempts / 30 min / account.
- SMS send: configurable per user per day.
- AI requests: configurable per user per hour.

### NFR-SEC-007 — Webhook Signature Validation
**Priority:** MVP | **Phase:** 2  
All inbound webhooks must validate provider signatures before processing. Invalid signatures: HTTP 403, no processing, logged.

### NFR-SEC-008 — PII Masking in Logs
**Priority:** MVP | **Phase:** 1  
Phone numbers in logs: country code + last 4 digits only (e.g. `+63****1234`). Email addresses not logged in application logs.

### NFR-SEC-009 — Content Security Policy
**Priority:** MVP | **Phase:** 1  
Frontend must serve a CSP header disallowing inline scripts, restricting script sources, and preventing framing by unauthorised origins.

### NFR-SEC-010 — Dependency Vulnerability Scanning
**Priority:** MVP | **Phase:** 1  
`pip-audit` (backend) and `npm audit` (frontend) run on every pull request in CI. High-severity findings block merge.

---

## Maintainability

### NFR-MAINT-001 — Layered Backend Architecture
**Priority:** MVP | **Phase:** 1  
No route handler may call the database directly. The layered order is enforced: handler → service → repository → provider.

### NFR-MAINT-002 — TypeScript Strict Mode
**Priority:** MVP | **Phase:** 1  
Frontend TypeScript compiled with `strict: true`. No `any` types in application code (third-party types excepted).

### NFR-MAINT-003 — Python Type Annotations
**Priority:** MVP | **Phase:** 1  
All Python functions must have complete type annotations. mypy (or equivalent) runs in CI.

### NFR-MAINT-004 — Linting and Formatting
**Priority:** MVP | **Phase:** 1  
All code passes lint and formatting checks in CI. Frontend: ESLint + Prettier. Backend: Ruff.

### NFR-MAINT-005 — Environment-Driven Configuration
**Priority:** MVP | **Phase:** 1  
All environment-specific values in environment variables. Application fails fast with a descriptive error if required variables are missing at startup.

### NFR-MAINT-006 — Migration-Based Schema Management
**Priority:** MVP | **Phase:** 1  
All schema changes in Supabase migration files under `supabase/migrations/`. No ad hoc schema changes in any environment.

---

## Testability

### NFR-TEST-001 — Backend Service Layer Coverage
**Priority:** MVP | **Phase:** 1  
Backend business logic and service layer: ≥ 80% line coverage. Auth flow, SMS send flow, credit deduction: 100% branch coverage.

### NFR-TEST-002 — External Dependency Isolation
**Priority:** MVP | **Phase:** 1  
All automated tests must mock external services (Supabase, Twilio, Bedrock). No real external calls in unit or integration tests.

### NFR-TEST-003 — CI Test Execution
**Priority:** MVP | **Phase:** 1  
All unit and integration tests run on every pull request. E2E tests run on merge to main.

### NFR-TEST-004 — Deterministic Tests
**Priority:** MVP | **Phase:** 1  
No test depends on execution order, wall-clock time, or external network calls.

---

## Usability and Accessibility

### NFR-UX-001 — WCAG 2.1 AA Compliance
**Priority:** MVP | **Phase:** 1 (baseline), **Phase:** 5 (full audit)  
All interactive elements keyboard-navigable. Images have alt text. Colour contrast ≥ 4.5:1 (normal text). Form fields labelled. Focus indicators visible.

### NFR-UX-002 — Responsive Design Breakpoints
**Priority:** MVP | **Phase:** 1  
Fully functional at: mobile (375px+), tablet (768px+), desktop (1280px+).

### NFR-UX-003 — All UI States Handled
**Priority:** MVP | **Phase:** 1  
Every data-dependent component renders an appropriate state for: loading, empty, success, and error.

### NFR-UX-004 — Internationalisation Readiness
**Priority:** POST-MVP | **Phase:** 2  
All UI strings externalisable via i18n layer from Phase 2 onwards. Hard-coded English strings in JSX prohibited from Phase 2.

---

## Compliance

### NFR-COMP-001 — SMS Opt-Out Compliance
**Priority:** MVP | **Phase:** 2  
No SMS sent to opted-out numbers. Opt-out stored per phone number and honoured immediately. Compliant with TCPA, GDPR, NPC Philippines.

### NFR-COMP-002 — Privacy Policy and Terms of Service
**Priority:** POST-MVP | **Phase:** 6  
Privacy Policy and Terms of Service presented before registration. User must explicitly agree before account creation.  
*Status: Requires legal review (OD-006).*

### NFR-COMP-003 — IP and Branding Compliance
**Priority:** MVP | **Phase:** 0  
No original Chikka trademarks, logos, or licensed assets used without confirmed written permission.

---

## Operational

### NFR-OPS-001 — Structured Logging
**Priority:** MVP | **Phase:** 1  
All backend logs emitted as JSON: timestamp, level, request_id, service, message. PII masked.

### NFR-OPS-002 — Health Check Endpoint
**Priority:** MVP | **Phase:** 1  
`GET /health` returns service status, database connectivity, and SMS provider mode. No authentication required.

### NFR-OPS-003 — Zero-Downtime Deploys
**Priority:** POST-MVP | **Phase:** 2  
Deployments use rolling deploy or equivalent strategy. No planned downtime for routine releases.

### NFR-OPS-004 — Environment Parity
**Priority:** MVP | **Phase:** 1  
Development, staging, and production use identical infrastructure components and configuration structure. Values differ; structure does not.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft with domain-prefixed IDs |
