# Functional Requirements Specification (FRS)

**Document:** CHKR-PROD-005
**Project:** Chikka Reborn
**Version:** 2.0
**Status:** Draft for review
**Last revised:** November 2026

This is the canonical FRS. It replaces version 1.0 of this file and the earlier `docs/frs.md` (superseded, `FR-A-xxx` IDs). Requirement IDs from version 1.0 are unchanged in meaning except where listed under [Changes from version 1.0](#9-changes-from-version-10).

---

## 1. Purpose and Scope

This specification describes every user-facing and administrator-facing function of Chikka Reborn, across Modules A to K, with testable acceptance criteria. It states what the system does, not how it is built. Design lives in `docs/architecture/`, `docs/api-design.md` and `docs/database-design.md`. Non-functional needs are in `docs/nfrs.md`. Rules from `.kiro/steering/` (SMS, AI, security, database, testing) apply to every requirement.

Chikka Reborn is an independent, Chikka-inspired project. It is not affiliated with or endorsed by the original owners or telecom partners.

Scope is sized for a hackathon: the MVP (Phases 1 and 2) is deliverable by a small team using simulation mode, with live SMS, AI, billing and Classic Mode as later phases. Nothing here authorises sending real SMS, spending money or deploying to production without explicit human approval.

## 2. How to Read This Document

### 2.1 Requirement IDs

`FR-<MODULE>-<nnn>`. IDs are permanent and never reused.

| Module | Code | File |
|---|---|---|
| A — Authentication and User Management | `AUTH` | [module-a-auth.md](frs/module-a-auth.md) |
| B — Contacts and Buddy List | `CONTACTS` | [module-b-contacts.md](frs/module-b-contacts.md) |
| C — Chikka-to-Chikka Messaging | `MSG` | [module-c-messaging.md](frs/module-c-messaging.md) |
| D — Internet-to-SMS | `SMS` | [module-d-internet-to-sms.md](frs/module-d-internet-to-sms.md) |
| E — SMS-to-Internet | `SMSRECV` | [module-e-sms-to-internet.md](frs/module-e-sms-to-internet.md) |
| F — AI Chikka Assistant | `AI` | [module-f-ai-assistant.md](frs/module-f-ai-assistant.md) |
| G — Notifications | `NOTIF` | [module-g-notifications.md](frs/module-g-notifications.md) |
| H — SMS Credits | `CREDIT` | [module-h-credits.md](frs/module-h-credits.md) |
| I — Privacy and Security | `PRIVACY` | [module-i-privacy.md](frs/module-i-privacy.md) |
| J — Administration | `ADMIN` | [module-j-administration.md](frs/module-j-administration.md) |
| K — Classic and Modern Experience | `CLASSIC` | [module-k-classic-modern.md](frs/module-k-classic-modern.md) |

### 2.2 Requirement template

Every requirement is a table with these fields: Module, User role, Priority / Phase, Mode, Description, Preconditions, Trigger, Main workflow, Alternative workflows, Expected result, Error scenarios, Dependencies, Acceptance criteria. "Mode" is added to separate simulated from live behaviour.

### 2.3 Priority

- **MVP**: required for the Phase 1 and 2 release.
- **POST-MVP**: required, delivered in the stated later phase.
- **FUTURE**: desirable, not scheduled.

Phases follow `.kiro/steering/project-overview.md` (1 Auth and chat, 2 SMS and simulation, 3 AI, 4 Credits and administration, 5 Classic Mode, accessibility and i18n, 6 Hardening).

### 2.4 Mode tags

| Tag | Meaning |
|---|---|
| Not provider-dependent | Behaves the same regardless of SMS mode |
| Both | Same flow in simulation and live; the provider differs. Behaviour differences are in the requirement text |
| Simulation | Exists only in simulation mode (`MockSmsProvider`) |
| Live only | Exists only in live mode (`TwilioSmsProvider` or equivalent) |
| Live (Bedrock) | AI features, which always use the real model through `AiProvider` |

## 3. User Roles

| Role | Description |
|---|---|
| Visitor | Not signed in |
| User | Registered, verified account holder |
| SMS contact | A person reached by SMS who may not be registered. Acts only through SMS replies and opt-out |
| Admin | Operator with the `admin` role. Sensitive actions require re-authentication |
| Developer | Engineer using non-production simulation tools |
| System | Background jobs, webhooks and automated processes |

## 4. Simulated and Live Functionality

### 4.1 Definitions

- **Simulation mode** (`MockSmsProvider`): no real SMS is ever sent, no cost is incurred, and all messages are stored with `is_simulated = true`. The UI shows a permanent SIMULATED label on every message, status, notification and estimate. Safe for development, staging and demos.
- **Live mode** (`TwilioSmsProvider` or equivalent): real SMS to real numbers with signed webhooks, provider message IDs and real cost. It needs explicit operator confirmation per environment (FR-ADMIN-003) and human approval before any real recipient is contacted.

### 4.2 Behaviour by mode

| Capability | Simulation | Live |
|---|---|---|
| Outbound SMS | Stored, never transmitted | Sent via provider |
| Provider message ID | `SIM-` prefixed | Provider SID |
| Status callbacks | Timed, scripted, via signed mock webhook | Real provider callbacks |
| Delivery claims | Same status names, labelled SIMULATED | `delivered` only on provider confirmation |
| Inbound SMS | "Simulate reply" tool through the real pipeline | Real signed webhooks |
| Mobile OTP | Shown in simulated inbox, non-production only | Real SMS |
| Credits | Demo credits (separate ledger), labelled SIMULATED | Live credits |
| Cost | Zero | Real |
| Failure injection | Scenarios available | Not available |
| Failure to initialise | n/a | Explicit failure; never a silent fallback to simulation |

Chikka-to-Chikka messaging, contacts, notifications, privacy and the Classic/Modern experience do not depend on SMS mode. AI always uses the real model (or a fake provider in automated tests only).

### 4.3 Mandatory rules

1. Simulated output is never presented as real.
2. Provider acceptance is never reported as delivery.
3. Live mode never starts silently.
4. AI content is never sent without explicit user approval.
5. Provider credentials never reach frontend code.

## 5. Cross-Cutting Requirements

These apply to every requirement and are referenced as `CC-xx`.

| ID | Requirement |
|---|---|
| CC-01 | All errors use `{ "error": { "code", "message", "details" }, "request_id" }`. Stack traces and internals are never returned. Every response carries a `request_id`. |
| CC-02 | Rate limits apply to authentication, SMS sending, AI, search, contact requests and webhooks. Exceeded limits return 429 with `Retry-After`. |
| CC-03 | Security-relevant and compliance events are audit logged: actor, action, target, timestamp, request ID. Phone numbers are masked as `+63****1234`. SMS audit logs are retained for at least 90 days. |
| CC-04 | Authorisation is deny-by-default and checked in the service layer. Row Level Security is enabled on every table and tested. |
| CC-05 | All input is validated (Zod on the client, Pydantic on the server). User-generated content is sanitised before storing and rendering. |
| CC-06 | Inbound webhooks are signature-validated on the raw body before any processing. There is no bypass. |
| CC-07 | Message bodies and AI content are never written to application logs. Logs hold metadata only. |
| CC-08 | Every data view handles loading, empty, error and success states. |
| CC-09 | The UI follows WCAG 2.1 AA practices: semantic HTML, keyboard operability, text alternatives, sufficient contrast. Status is never conveyed by colour alone. |
| CC-10 | Slow work (SMS dispatch, AI, exports) runs in background jobs. Handlers do not block on external providers. |

## 6. Hackathon Delivery Guidance

**Demo-critical path (Phases 1 and 2, all in simulation mode):** register and verify, onboard, add and accept contacts, chat in real time with statuses, send simulated SMS with segment and demo-credit preview, watch the status timeline, simulate a reply, opt-out handling, notifications, and the admin view of SMS activity and mode.

**Realistic cut lines if time is short:**
- Drop first: attachments (FR-MSG-010), editing (FR-MSG-011), groups (FR-CONTACTS-005), import (FR-CONTACTS-008), push and email (FR-NOTIF-002, FR-NOTIF-008), session list (FR-AUTH-014), data export (FR-PRIVACY-002).
- Never drop: signature validation, idempotency, SIMULATED labelling, status semantics, opt-out blocking, RLS, approval-before-send.
- Live SMS, payments and Classic Mode are Phases 4 to 5 and not part of the demo-critical path.

## 7. Assumptions and Open Issues

**Assumptions**
- Supabase provides identity, storage and realtime; the FastAPI backend enforces business rules.
- The SMS number pool and sender registration for live use are outside the hackathon scope.
- Country capability data is seeded manually and maintained by admins.
- Legal review of consent text, retention periods and Philippine rules is needed before live use.

| ID | Open issue | Proposed handling |
|---|---|---|
| OPEN-01 | Version 1.0 used a one-way follow model for contacts. This version requires requests and acceptance. | Adopted (FR-CONTACTS-001, 009, 010). Confirm with the product owner |
| OPEN-02 | Steering says simulation must not deduct credits, yet the brief asks for simulated deduction. | Implemented as a separate demo ledger that never touches live credits (Module H). Alternative is to show costs without any ledger |
| OPEN-03 | No AI mock is specified. A demo without Bedrock access would need a clearly labelled mock. | Not specified. If needed, label "DEMO AI" and record as a decision |
| OPEN-04 | Account deletion grace period (7 days) is a proposal. | Confirm with legal and product |
| OPEN-05 | Payment gateway for top-up undecided (OD-001). | Phase 4 |

## 8. Requirement Counts

| Module | Count | Module | Count |
|---|---|---|---|
| AUTH | 15 | AI | 13 |
| CONTACTS | 14 | NOTIF | 8 |
| MSG | 13 | CREDIT | 10 |
| SMS | 13 | PRIVACY | 10 |
| SMSRECV | 13 | ADMIN | 14 |
| CLASSIC | 7 | **Total** | **130** |

## 9. Changes from Version 1.0

- Restructured into a per-requirement template and split into module files under `docs/product/frs/`.
- Added 71 requirements (59 existed in version 1.0) to cover the full brief (for example logout, presence, sessions, search, import, requests, attachments, editing, capability checks, retry, idempotency, inbound handling, tone, composition, history, email notifications, consent, admin monitoring).
- FR-CONTACTS-001 changed from a follow model to request and acceptance.
- FR-SMS-004 now uses the full status model (queued, accepted, sent, delivered, undelivered, failed).
- FR-CREDIT-003 clarified as live-only; simulated deduction is FR-CREDIT-006.
- FR-NOTIF-004 to FR-NOTIF-006 and FR-AI-007 retained from the v1.0 additions.
- FR-AUTH-008 phase unchanged (2); behaviour now differs by mode.

Related files that cite requirement IDs (`docs/quality/acceptance-criteria.md`, `docs/quality/test-plan.md`, `docs/project-management/development-backlog.md`) should be checked for consistency with this version.

## 10. Requirement Matrix

| ID | Title | Priority / Phase | Mode |
|---|---|---|---|
| FR-AUTH-001 | Email Registration | MVP / 1 | Not provider-dependent |
| FR-AUTH-002 | Email Verification | MVP / 1 | Not provider-dependent |
| FR-AUTH-003 | Social Login (Google, GitHub) | MVP / 1 | Not provider-dependent |
| FR-AUTH-004 | Login | MVP / 1 | Not provider-dependent |
| FR-AUTH-005 | Password Reset | MVP / 1 | Not provider-dependent |
| FR-AUTH-006 | Login Rate Limiting and Lockout | MVP / 1 | Not provider-dependent |
| FR-AUTH-007 | Profile Editing | MVP / 1 | Not provider-dependent |
| FR-AUTH-008 | Mobile Number Verification (OTP) | MVP / 2 | Both |
| FR-AUTH-009 | Account Deletion | MVP / 1 | Not provider-dependent |
| FR-AUTH-010 | Logout | MVP / 1 | Not provider-dependent |
| FR-AUTH-011 | Profile Photo | MVP / 1 | Not provider-dependent |
| FR-AUTH-012 | Mobile Number Management | POST-MVP / 2 | Both |
| FR-AUTH-013 | User Presence | MVP / 1 | Not provider-dependent |
| FR-AUTH-014 | Session Management | POST-MVP / 2 | Not provider-dependent |
| FR-AUTH-015 | Profile Creation (Onboarding) | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-001 | Add Chikka Contact (Send Request) | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-002 | Add SMS Contact | MVP / 2 | Both |
| FR-CONTACTS-003 | Contact List Display | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-004 | Block Contact | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-005 | Contact Groups | POST-MVP / 2 | Not provider-dependent |
| FR-CONTACTS-006 | Mute Contact | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-007 | Search Contacts and Users | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-008 | Import Contacts (With Permission) | POST-MVP / 2 | Not provider-dependent |
| FR-CONTACTS-009 | Contact Requests (Pending List) | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-010 | Accept or Reject Contact Request | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-011 | Favourite Contacts | POST-MVP / 2 | Not provider-dependent |
| FR-CONTACTS-012 | Unblock Contact | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-013 | Recent Contacts | MVP / 1 | Not provider-dependent |
| FR-CONTACTS-014 | Online and Offline Status Display | MVP / 1 | Not provider-dependent |
| FR-MSG-001 | Send Chikka Message | MVP / 1 | Not provider-dependent |
| FR-MSG-002 | Message Status Indicators | MVP / 1 | Not provider-dependent |
| FR-MSG-003 | Typing Indicator | MVP / 1 | Not provider-dependent |
| FR-MSG-004 | Message History and Timestamps | MVP / 1 | Not provider-dependent |
| FR-MSG-005 | Message Deletion Policy | POST-MVP / 2 | Not provider-dependent |
| FR-MSG-006 | Emoji Support | MVP / 1 | Not provider-dependent |
| FR-MSG-007 | Real-Time Message Updates | MVP / 1 | Not provider-dependent |
| FR-MSG-008 | Read Receipts | POST-MVP / 2 | Not provider-dependent |
| FR-MSG-009 | Message Search | POST-MVP / 2 | Not provider-dependent |
| FR-MSG-010 | Attachments | POST-MVP / 2 | Not provider-dependent |
| FR-MSG-011 | Message Editing Policy | POST-MVP / 2 | Not provider-dependent |
| FR-MSG-012 | Conversation Management | MVP / 1 | Not provider-dependent |
| FR-MSG-013 | Start or Open Conversation | MVP / 1 | Not provider-dependent |
| FR-SMS-001 | Compose and Send SMS | MVP / 2 | Both |
| FR-SMS-002 | Segment Count and Cost Preview | MVP / 2 | Both |
| FR-SMS-003 | Simulation Mode Labelling | MVP / 2 | Simulation |
| FR-SMS-004 | Delivery Status Tracking | MVP / 2 | Both |
| FR-SMS-005 | Insufficient Credit Prevention | MVP / 2 | Both |
| FR-SMS-006 | Recipient Entry and Phone Validation | MVP / 2 | Not provider-dependent |
| FR-SMS-007 | Destination Country Capability Check | MVP / 2 | Both |
| FR-SMS-008 | Confirm Message Before Sending | MVP / 2 | Both |
| FR-SMS-009 | Send Through Provider and Store Provider Response | MVP / 2 | Both |
| FR-SMS-010 | Handle Failures | MVP / 2 | Both |
| FR-SMS-011 | Retry Eligible Failures | MVP / 2 | Both |
| FR-SMS-012 | Idempotent Send | MVP / 2 | Both |
| FR-SMS-013 | Simulated Delivery Scenarios | MVP / 2 | Simulation only |
| FR-SMSRECV-001 | Inbound SMS to Conversation (End to End) | MVP / 2 | Both |
| FR-SMSRECV-002 | Webhook Signature Validation | MVP / 2 | Both |
| FR-SMSRECV-003 | SMS Origin Labelling | MVP / 2 | Both |
| FR-SMSRECV-004 | Receive Inbound Webhook | MVP / 2 | Both |
| FR-SMSRECV-005 | Resolve Destination Chikka Account | MVP / 2 | Both |
| FR-SMSRECV-006 | Resolve Conversation | MVP / 2 | Both |
| FR-SMSRECV-007 | Create Inbound Message | MVP / 2 | Both |
| FR-SMSRECV-008 | Notify Recipient | MVP / 2 | Both |
| FR-SMSRECV-009 | Prevent Duplicate Processing | MVP / 2 | Both |
| FR-SMSRECV-010 | Handle Unknown Sender | MVP / 2 | Both |
| FR-SMSRECV-011 | Handle Unsupported Destination | MVP / 2 | Both |
| FR-SMSRECV-012 | Handle Opt-Out Messages | MVP / 2 | Both |
| FR-SMSRECV-013 | Simulate Inbound SMS | MVP / 2 | Simulation only |
| FR-AI-001 | Smart Reply Suggestions | POST-MVP / 3 | Live |
| FR-AI-002 | Message Translation | POST-MVP / 3 | Live |
| FR-AI-003 | Message Rewriting | POST-MVP / 3 | Live |
| FR-AI-004 | SMS Length Optimisation | POST-MVP / 3 | Live |
| FR-AI-005 | Conversation Summary | POST-MVP / 3 | Live |
| FR-AI-006 | Mandatory User Approval Before Sending | POST-MVP / 3 (applies from the first release of any AI feature) | Live and Simulation |
| FR-AI-007 | AI-Assisted Badge | POST-MVP / 3 | Live and Simulation |
| FR-AI-008 | Tone Adjustment | POST-MVP / 3 | Live |
| FR-AI-009 | AI Message Composition | POST-MVP / 3 | Live |
| FR-AI-010 | Language Selection | POST-MVP / 3 | Live |
| FR-AI-011 | AI Request History | POST-MVP / 3 | Live |
| FR-AI-012 | Failure Handling, Fallback and Rate Limits | POST-MVP / 3 | Live |
| FR-AI-013 | AI Privacy Controls and Data Minimisation | POST-MVP / 3 | Live |
| FR-NOTIF-001 | In-App Message Alerts | MVP / 1 | Not provider-dependent |
| FR-NOTIF-002 | Browser Push Notifications | POST-MVP / 2 | Not provider-dependent |
| FR-NOTIF-003 | SMS Delivery Alerts | MVP / 2 | Both |
| FR-NOTIF-004 | Low-Balance Notification | MVP / 2 | Both |
| FR-NOTIF-005 | Notification Preferences | POST-MVP / 2 | Not provider-dependent |
| FR-NOTIF-006 | Notification History | POST-MVP / 2 | Not provider-dependent |
| FR-NOTIF-007 | Contact Request Alerts | MVP / 1 | Not provider-dependent |
| FR-NOTIF-008 | Email Notifications | POST-MVP / 2 | Not provider-dependent |
| FR-CREDIT-001 | Credit Balance Display | MVP / 2 | Both |
| FR-CREDIT-002 | Per-Country Pricing | MVP / 2 | Both |
| FR-CREDIT-003 | Credit Deduction and Refund (Live) | MVP / 2 | Live only |
| FR-CREDIT-004 | Credit Top-Up | POST-MVP / 4 | Live only |
| FR-CREDIT-005 | Estimated SMS Cost | MVP / 2 | Both |
| FR-CREDIT-006 | Simulated Credit Deduction | MVP / 2 | Simulation only |
| FR-CREDIT-007 | Transaction History | MVP / 2 | Both |
| FR-CREDIT-008 | Low-Credit Warning | MVP / 2 | Both |
| FR-CREDIT-009 | Insufficient Credit Handling | MVP / 2 | Both |
| FR-CREDIT-010 | Administrator Credit Adjustments | POST-MVP / 4 (demo-credit adjustments MVP / 2) | Both |
| FR-PRIVACY-001 | Profile Visibility Settings | MVP / 1 | Not provider-dependent |
| FR-PRIVACY-002 | Data Export | POST-MVP / 2 | Both |
| FR-PRIVACY-003 | SMS Recipient Opt-Out | MVP / 2 | Both |
| FR-PRIVACY-004 | Message and User Reporting | POST-MVP / 2 | Both |
| FR-PRIVACY-005 | Presence and Activity Visibility Settings | POST-MVP / 2 | Not provider-dependent |
| FR-PRIVACY-006 | Blocking Enforcement | MVP / 1 | Both |
| FR-PRIVACY-007 | Consent Records | MVP / 2 | Both |
| FR-PRIVACY-008 | Opt-Out Management | MVP / 2 | Both |
| FR-PRIVACY-009 | Data Deletion and Retention | MVP / 1 (retention jobs POST-MVP / 6) | Both |
| FR-PRIVACY-010 | Access Controls | MVP / 1 | Both |
| FR-ADMIN-001 | Platform Statistics | POST-MVP / 2 | Both |
| FR-ADMIN-002 | User Management | POST-MVP / 2 | Not provider-dependent |
| FR-ADMIN-003 | SMS Mode Control | POST-MVP / 2 | Both |
| FR-ADMIN-004 | SMS Audit Log | POST-MVP / 2 | Both |
| FR-ADMIN-005 | Country Capability Management | POST-MVP / 2 | Both |
| FR-ADMIN-006 | AI Usage Monitoring | POST-MVP / 3 | Live |
| FR-ADMIN-007 | SMS Activity Monitoring | POST-MVP / 2 | Both |
| FR-ADMIN-008 | Delivery Monitoring | POST-MVP / 2 | Both |
| FR-ADMIN-009 | Failed Message Monitoring | POST-MVP / 2 | Both |
| FR-ADMIN-010 | Credit Management | POST-MVP / 4 | Both |
| FR-ADMIN-011 | Abuse Report Management | POST-MVP / 2 | Both |
| FR-ADMIN-012 | Audit Logs (Admin and Security Events) | POST-MVP / 2 | Both |
| FR-ADMIN-013 | System Health and Feature Switches | POST-MVP / 2 | Both |
| FR-ADMIN-014 | Provider Configuration | POST-MVP / 2 | Both |
| FR-CLASSIC-001 | Mode Toggle | POST-MVP / 5 | Not provider-dependent |
| FR-CLASSIC-002 | Classic Mode | POST-MVP / 5 | Not provider-dependent |
| FR-CLASSIC-003 | Modern Mode (Default) | MVP / 1 | Not provider-dependent |
| FR-CLASSIC-004 | Theme Switching | POST-MVP / 5 | Not provider-dependent |
| FR-CLASSIC-005 | Responsive Layouts | MVP / 1 | Not provider-dependent |
| FR-CLASSIC-006 | Preference Persistence | MVP / 1 (mode and theme values added in Phase 5) | Not provider-dependent |
| FR-CLASSIC-007 | Accessibility Parity | POST-MVP / 5 | Not provider-dependent |
