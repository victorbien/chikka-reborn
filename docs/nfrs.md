# Non-Functional Requirements Specification (NFRS)

> **SUPERSEDED (November 2026).** Retained for history. The canonical version is in docs/product/non-functional-requirements.md. Requirement IDs here use the older scheme (e.g. FR-A-001); see the 'Was:' fields in docs/product/functional-requirements.md for the mapping.

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  

---

## 1. Introduction

This document specifies the non-functional requirements for Chikka Reborn. These requirements define the quality attributes of the system — how it performs, scales, remains available, stays secure, and can be maintained — rather than what it does.

Requirements are identified as `NFR-xxx` and categorised by quality attribute.

---

## 2. Performance

### NFR-P-001 — Chikka-to-Chikka Message Latency
**Requirement:** End-to-end message delivery between two online Chikka users must complete in under 500ms at the 95th percentile under normal load.  
**Rationale:** Real-time messaging expectations require near-instant delivery to feel responsive.  
**Measurement:** Measured from sender WebSocket send event to recipient WebSocket receive event.

### NFR-P-002 — API Response Time
**Requirement:** 95% of REST API responses must complete within 300ms under normal load, excluding SMS-send and AI-call endpoints.  
**Rationale:** Slow API responses degrade user experience across all UI interactions.

### NFR-P-003 — AI Feature Response Time
**Requirement:** AI suggestion generation must complete within 5 seconds at the 95th percentile.  
**Rationale:** AI calls to Amazon Bedrock involve external network round-trips and model inference. A 5-second limit is a practical threshold that avoids indefinite waits while remaining acceptable for a non-blocking UX feature.

### NFR-P-004 — Page Load Performance
**Requirement:** The frontend application must achieve a Lighthouse Performance score of ≥ 85 on both mobile and desktop.  
**Rationale:** Performance directly affects usability, especially for users on lower-end devices or slower connections.

### NFR-P-005 — SMS Send Throughput
**Requirement:** The backend must be capable of initiating up to 100 outbound SMS messages per minute per environment without degradation.  
**Rationale:** In Phase 2 the platform will handle modest SMS volumes. This limit applies to the application tier; actual provider throughput is subject to Twilio rate limits.

---

## 3. Scalability

### NFR-S-001 — Horizontal Backend Scalability
**Requirement:** The FastAPI backend must be stateless and capable of horizontal scaling by adding additional instances behind a load balancer.  
**Rationale:** Stateless design ensures any instance can handle any request, enabling simple horizontal scale-out.

### NFR-S-002 — WebSocket Connection Handling
**Requirement:** The WebSocket layer must support at least 1,000 concurrent connections in Phase 1, with a clear path to 10,000 in later phases.  
**Rationale:** Concurrent connections are the primary scalability constraint for real-time messaging. The architecture must avoid designs that make scaling WebSockets fundamentally difficult.

### NFR-S-003 — Database Connection Pooling
**Requirement:** The backend must use connection pooling to limit the number of active database connections to a configurable maximum.  
**Rationale:** Supabase PostgreSQL has connection limits per plan tier. Connection exhaustion causes hard failures.

### NFR-S-004 — Frontend Asset Delivery
**Requirement:** Frontend static assets must be served through Vercel's edge CDN with cache-control headers appropriate for each asset type.  
**Rationale:** CDN delivery reduces latency for geographically distributed users.

---

## 4. Availability and Reliability

### NFR-A-001 — Target Uptime
**Requirement:** The platform must target 99.5% monthly uptime in production, excluding planned maintenance windows.  
**Rationale:** Messaging platforms must be reliably available. 99.5% allows approximately 3.6 hours of unplanned downtime per month.

### NFR-A-002 — Graceful Degradation
**Requirement:** A failure in the AI subsystem must not degrade core messaging functionality. A failure in the SMS subsystem must not degrade Chikka-to-Chikka messaging.  
**Rationale:** The application is composed of distinct feature domains. Each must fail independently without cascading.

### NFR-A-003 — SMS Retry Reliability
**Requirement:** Transient SMS failures must be retried with exponential backoff. Maximum retry attempts must be configurable. Messages that exhaust retries must be marked as permanently failed and the user notified.  
**Rationale:** Provider transient errors are common. Silent failure or infinite retry both cause harm.

### NFR-A-004 — Database Backup
**Requirement:** The Supabase PostgreSQL database must be backed up daily with a minimum 7-day retention period. Point-in-time recovery must be available.  
**Rationale:** Data loss from a production incident must be recoverable.

### NFR-A-005 — WebSocket Reconnection
**Requirement:** The frontend WebSocket client must automatically attempt reconnection on disconnection, with backoff, up to a configurable maximum retry count.  
**Rationale:** Network interruptions are common on mobile devices. Reconnection must be transparent to the user.

---

## 5. Security

### NFR-SEC-001 — Authentication
**Requirement:** All authenticated API routes must require a valid Supabase JWT. Expired or invalid tokens must result in HTTP 401.  
**Rationale:** Unauthenticated access to user data or messaging must be impossible by default.

### NFR-SEC-002 — Authorisation (Row Level Security)
**Requirement:** All database tables containing user data must have Supabase RLS policies that enforce user-scoped access. No table may be accessible to any authenticated user without a specific, tested RLS policy.  
**Rationale:** RLS is the primary authorisation enforcement layer. Missing policies create data exposure vulnerabilities.

### NFR-SEC-003 — Secret Management
**Requirement:** All secrets, API keys, provider credentials, and tokens must be stored as environment variables and injected at runtime. They must never appear in source code, version control, or frontend bundles.  
**Rationale:** Credential exposure is one of the most common and damaging security failures.

### NFR-SEC-004 — Transport Security
**Requirement:** All communication between client and server, server and database, and server and external providers must use TLS. HTTP must not be used in production.  
**Rationale:** Unencrypted transport exposes messages, credentials, and user data.

### NFR-SEC-005 — Input Validation
**Requirement:** All inputs from external sources (user input, webhooks, API requests) must be validated before processing. Invalid input must be rejected with a descriptive error.  
**Rationale:** Unvalidated input is the root cause of injection attacks, data corruption, and unexpected behaviour.

### NFR-SEC-006 — Rate Limiting
**Requirement:** The following endpoints must be rate-limited:
- Login: 5 attempts per 15 minutes per IP.
- Password reset: 3 attempts per hour per IP.
- OTP send: 3 attempts per 30 minutes per account.
- SMS send: configurable per user per day.
- AI requests: configurable per user per hour.  
**Rationale:** Rate limiting prevents brute-force attacks, spam, and abuse.

### NFR-SEC-007 — Webhook Signature Validation
**Requirement:** All inbound webhooks (SMS delivery status, inbound SMS) must have their signatures validated against the provider's signing secret before the payload is processed.  
**Rationale:** Without signature validation, any actor can POST fake delivery events or inject messages.

### NFR-SEC-008 — Sensitive Data Masking
**Requirement:** Phone numbers must be masked in logs: display only country code and last 4 digits. Email addresses must not appear in application logs.  
**Rationale:** Logs are often accessible to a broader audience than the application itself. PII in logs creates compliance and security risks.

### NFR-SEC-009 — Content Security Policy
**Requirement:** The frontend must serve a Content-Security-Policy header that disallows inline scripts, restricts script sources, and prevents framing by unauthorised origins.  
**Rationale:** CSP is the primary browser-side defence against XSS and clickjacking.

### NFR-SEC-010 — Dependency Security
**Requirement:** All dependencies must be pinned to exact versions. Dependency vulnerability scans must be run as part of CI.  
**Rationale:** Unpinned dependencies may silently upgrade to vulnerable versions. Scans catch known vulnerabilities before deployment.

---

## 6. Maintainability

### NFR-M-001 — Code Structure
**Requirement:** Frontend and backend codebases must follow the module structure defined in `docs/architecture.md`. New modules must not introduce circular dependencies.  
**Rationale:** Clear structure makes onboarding, debugging, and modification tractable.

### NFR-M-002 — Type Safety
**Requirement:** The TypeScript compiler must be configured with `strict: true`. Python code must pass mypy or equivalent type checking in CI.  
**Rationale:** Strong typing catches bugs at compile/lint time rather than runtime.

### NFR-M-003 — Linting and Formatting
**Requirement:** All code must pass lint and formatting checks as part of CI. Frontend uses ESLint + Prettier. Backend uses Ruff (or equivalent).  
**Rationale:** Consistent formatting reduces cognitive overhead in code review and prevents trivial diffs.

### NFR-M-004 — Environment Configuration
**Requirement:** All environment-specific configuration (API URLs, feature flags, provider modes) must use environment variables. The application must fail fast with a clear error if required environment variables are missing.  
**Rationale:** Configuration in code creates environment-specific bugs. Fail-fast prevents silent misconfiguration.

### NFR-M-005 — Database Migration Management
**Requirement:** All schema changes must be applied through numbered, sequential Supabase migration files. No ad hoc schema changes in production.  
**Rationale:** Migration-based schema management ensures reproducibility across environments and maintains a full audit trail of schema history.

---

## 7. Testability

### NFR-T-001 — Test Coverage
**Requirement:** Backend business logic and service layer must maintain ≥ 80% line coverage. Critical paths (auth, SMS send, credit deduction) must have 100% branch coverage.  
**Rationale:** Coverage targets ensure that important code paths are exercised by automated tests.

### NFR-T-002 — Test Isolation
**Requirement:** All automated tests must be runnable in isolation without requiring real external services. External dependencies (Supabase, Twilio, Bedrock) must be mocked in unit and integration tests.  
**Rationale:** Tests that depend on external services are slow, flaky, and cannot run in CI without credentials.

### NFR-T-003 — CI Test Execution
**Requirement:** All unit and integration tests must run on every pull request in CI. End-to-end tests must run on merge to the main branch.  
**Rationale:** Automated testing on every change catches regressions before they reach production.

### NFR-T-004 — Determinism
**Requirement:** All automated tests must be deterministic. Tests must not depend on execution order, wall-clock time, or external network calls.  
**Rationale:** Flaky tests erode trust in the test suite and slow down development.

---

## 8. Usability and Accessibility

### NFR-U-001 — WCAG 2.1 AA Compliance
**Requirement:** The application must meet WCAG 2.1 Level AA accessibility guidelines.  
**Specific requirements:**
- All interactive elements are keyboard-navigable.
- All images have descriptive `alt` text.
- Colour contrast ratio of at least 4.5:1 for normal text, 3:1 for large text.
- Form fields have associated labels.
- Error messages are programmatically associated with their fields.
- Focus indicators are visible.

### NFR-U-002 — Responsive Design
**Requirement:** All application views must be fully functional and usable on:
- Mobile: viewport width 375px and above.
- Tablet: viewport width 768px and above.
- Desktop: viewport width 1280px and above.

### NFR-U-003 — Loading, Empty, and Error States
**Requirement:** Every data-dependent UI component must handle and display appropriate UI for loading, empty, success, and error states.  
**Rationale:** Components that silently show nothing or throw unhandled errors create confusing user experiences.

### NFR-U-004 — Internationalisation Readiness
**Requirement:** UI text must be externalisable to a translation layer. Hard-coded English strings directly in JSX are prohibited from Phase 2 onwards.  
**Rationale:** The platform targets global users including non-English speakers. i18n readiness from early on avoids expensive retrofitting.

---

## 9. Compliance and Legal

### NFR-C-001 — Data Residency
**Requirement:** User data must be stored in a Supabase region that aligns with applicable data protection regulations. The chosen region must be documented.  
**Status:** Region selection is an open decision (see `docs/prd.md` OD-xxx).

### NFR-C-002 — SMS Regulatory Compliance
**Requirement:** The platform must not send SMS to recipients who have opted out. Opt-out must be honoured immediately and permanently.  
**Rationale:** Sending to opted-out recipients violates regulations including TCPA (US), GDPR (EU/UK), and NPC rules (Philippines).

### NFR-C-003 — Privacy Policy and Terms of Service
**Requirement:** The platform must display a Privacy Policy and Terms of Service before users complete registration. Users must explicitly agree before account creation is finalised.  
**Status:** Legal documents are deferred to Phase 1 — requires legal review.

### NFR-C-004 — IP and Branding
**Requirement:** The platform must not use Chikka's original logo, trade name as a product name, or other trademarked assets without confirmed permission.  
**Rationale:** This project is independent and Chikka-inspired. Proper independent branding avoids IP infringement.

---

## 10. Operational

### NFR-O-001 — Structured Logging
**Requirement:** All backend services must emit structured JSON logs including: timestamp, log level, request ID, service name, and message. Personally identifiable information must be masked.  
**Rationale:** Structured logs can be indexed and queried by log management tools, enabling efficient incident investigation.

### NFR-O-002 — Health Check Endpoints
**Requirement:** The backend must expose a `/health` endpoint that returns the service status and key dependency status (database connectivity, SMS provider reachability in live mode).  
**Rationale:** Health checks enable load balancers and monitoring systems to detect and route around unhealthy instances.

### NFR-O-003 — Environment Parity
**Requirement:** Development, staging, and production environments must use the same infrastructure components and configuration structure, differing only in configuration values.  
**Rationale:** Environment-specific bugs are prevented when environments are structurally identical.

### NFR-O-004 — Deployment Without Downtime
**Requirement:** Application deployments must not require downtime. Rolling deploys, blue/green, or feature-flagged releases are acceptable strategies.  
**Rationale:** A messaging platform that goes offline for every deploy is unacceptable for users.

---

## 11. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
