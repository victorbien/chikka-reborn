# Module I — Privacy and Security (`PRIVACY`)

Part of the [Functional Requirements Specification](../functional-requirements.md). Technical controls are in `.kiro/steering/security.md` and `docs/architecture/security-architecture.md`. This module covers user-facing privacy and safety functions. Legal review of consent wording, retention periods and regional rules (for example the Philippine Data Privacy Act) is required before any live launch; the numbers below are engineering defaults.

---

### FR-PRIVACY-001 — Profile Visibility Settings

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Users control who can find and view their profile. |
| Preconditions | Signed in. |
| Trigger | User opens Settings, Privacy. |
| Main workflow | 1) Options: Everyone, Contacts only (default), Private. 2) The setting is saved. 3) Search and profile views apply it immediately. |
| Alternative workflows | A) Private users can still send requests, but cannot be found by search. |
| Expected result | Profile exposure matches choice. |
| Error scenarios | Save failure: setting reverts. |
| Dependencies | FR-CONTACTS-007. |
| Acceptance criteria | AC1 Private profiles never appear in search. AC2 Visibility is enforced server-side and by RLS. AC3 The default for new users is "Contacts only". |

### FR-PRIVACY-002 — Data Export

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** (simulated records are flagged in the export) |
| Description | Users can download a copy of their personal data. |
| Preconditions | Re-authentication. |
| Trigger | User requests an export. |
| Main workflow | 1) Re-authenticate. 2) A background job builds a JSON archive: profile, settings, contacts, conversations and messages, SMS history with statuses, consents, credit ledger, AI history. 3) The user is notified when ready. 4) Download via a signed link valid for 24 hours. |
| Alternative workflows | A) A new request is blocked while one is in progress. |
| Expected result | A complete, machine-readable archive. |
| Error scenarios | Job failure: retry and notify. |
| Dependencies | Background jobs, Storage. |
| Acceptance criteria | AC1 Ready within 48 hours (target under 10 minutes for demo data). AC2 Only the owner can download. AC3 Phone numbers of other people are included only as the user's own contact data. AC4 The export is audit logged and the file deleted after 7 days. |

### FR-PRIVACY-003 — SMS Recipient Opt-Out

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | SMS contact (recipient), System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | A person who receives SMS from the platform can opt out and stop all further messages. |
| Preconditions | The person has received an SMS from the platform. |
| Trigger | They reply with an opt-out keyword (FR-SMSRECV-012), or use a link in a message. |
| Main workflow | 1) The opt-out is recorded for the phone number. 2) Further outbound sends are blocked for all users. 3) Senders see "This recipient has opted out". |
| Alternative workflows | A) Re-subscribe by replying START (FR-PRIVACY-008). |
| Expected result | Honoured immediately and for everyone. |
| Error scenarios | Not applicable. |
| Dependencies | FR-SMSRECV-012. |
| Acceptance criteria | AC1 Block is enforced server-side. AC2 Opt-out applies platform-wide to that number. AC3 Opt-out events are audit logged with masked numbers. AC4 First messages to new recipients include opt-out instructions where required by the route or country rules. |

### FR-PRIVACY-004 — Message and User Reporting

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | Users report abusive messages or users. |
| Preconditions | The user is a participant in the conversation. |
| Trigger | User selects Report on a message, contact or request. |
| Main workflow | 1) Choose a reason: spam, harassment, scam, illegal content, other, plus an optional note. 2) The report stores the reported message content snapshot (for deleted or edited messages too). 3) Confirmation offers to block. 4) The report enters the admin queue (FR-ADMIN-011). |
| Alternative workflows | A) Report without blocking. B) Report an unknown inbound SMS. |
| Expected result | Abuse reaches moderators with evidence. |
| Error scenarios | Duplicate report for the same message: merged. Report spam: rate limited. |
| Dependencies | FR-ADMIN-011. |
| Acceptance criteria | AC1 The reporter is never revealed to the reported user. AC2 The snapshot includes only the reported message and a limited context window of 5 messages. AC3 Reports are limited to 10 per day per user. |

### FR-PRIVACY-005 — Presence and Activity Visibility Settings

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | User |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users control presence, last seen, typing indicators, read receipts and number discoverability. |
| Preconditions | Signed in. |
| Trigger | User changes a toggle. |
| Main workflow | 1) Controls: share online status (everyone, contacts, nobody), show last seen, send typing indicators, send read receipts (default off), allow discovery by mobile number (default off). 2) Changes apply immediately to new events. |
| Alternative workflows | A) Reciprocity: if you hide last seen, you cannot see others' last seen. |
| Expected result | Fine-grained control. |
| Error scenarios | Save failure: reverts. |
| Dependencies | FR-AUTH-013, FR-MSG-003, FR-MSG-008. |
| Acceptance criteria | AC1 Defaults are the most private choice for read receipts and number discovery. AC2 Enforcement is server-side. AC3 Each setting has a plain-language description. |

### FR-PRIVACY-006 — Blocking Enforcement

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | System |
| Priority / Phase | MVP / 1 |
| Mode | **Both** |
| Description | A block takes effect consistently across every feature. |
| Preconditions | A block record exists (FR-CONTACTS-004). |
| Trigger | Any interaction between blocker and blocked. |
| Main workflow | 1) Chikka messages from the blocked user are accepted but not delivered or notified; the sender sees normal Sent state. 2) Contact requests are discarded silently. 3) Presence and profile details are hidden. 4) Inbound SMS from a blocked number is stored hidden (FR-SMSRECV-005). 5) The blocker cannot send to a blocked contact until unblocking. |
| Alternative workflows | A) Admin override for a safety investigation is audit logged. |
| Expected result | The blocked party cannot tell they are blocked. |
| Error scenarios | Not applicable. |
| Dependencies | Module B, Module C, Module E. |
| Acceptance criteria | AC1 Tests cover messaging, requests, presence, search and inbound SMS. AC2 Enforcement lives in the service layer and RLS. AC3 No API response reveals a block. |

### FR-PRIVACY-007 — Consent Records

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | User, System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | The platform records consent events for terms, privacy, AI use, contact import, and SMS sender attestations. |
| Preconditions | A consent-requiring action occurs. |
| Trigger | User accepts a notice, or sends SMS to a new number. |
| Main workflow | 1) Each consent stores: user, type, notice version, decision, timestamp, and IP (coarse). 2) For outbound SMS to a new recipient number the user must tick "The recipient has agreed to receive messages from me" before the first send; the attestation is stored per recipient. 3) Withdrawn consent writes a new record and takes effect at once. |
| Alternative workflows | A) A new notice version triggers re-consent. B) Replies from the recipient (any inbound message) are recorded as recipient engagement, but are not treated as consent to promotional content. |
| Expected result | An auditable consent trail. |
| Error scenarios | Consent write failure: the action is blocked. |
| Dependencies | FR-SMS-001, FR-AI-013, FR-CONTACTS-008. |
| Acceptance criteria | AC1 Records are append-only. AC2 No SMS is sent to a new number without an attestation. AC3 Users can view their consent history. AC4 Unsolicited promotional content is prohibited by the terms and called out in the UI, especially for the Philippines. |

### FR-PRIVACY-008 — Opt-Out Management

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | User, Admin |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Users and admins can see which numbers have opted out, and handle re-subscription. |
| Preconditions | At least one opt-out exists. |
| Trigger | User opens Settings, Opt-outs; admin opens the opt-out list. |
| Main workflow | 1) Users see the contacts of theirs whose numbers have opted out, without the global list. 2) A START reply from the number lifts the opt-out. 3) Admins can see the platform-wide list (masked) and manually lift an opt-out only with evidence of the person's request, with the reason logged. |
| Alternative workflows | A) Users cannot lift an opt-out themselves. |
| Expected result | Opt-out state is visible and respected. |
| Error scenarios | Admin lift without a reason: 422. |
| Dependencies | FR-SMSRECV-012, FR-ADMIN-012. |
| Acceptance criteria | AC1 Lifting requires a recipient-originated action or documented evidence. AC2 Every lift is audit logged. AC3 Opted-out numbers are never shown unmasked to non-owners. |

### FR-PRIVACY-009 — Data Deletion and Retention

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | User, System |
| Priority / Phase | MVP / 1 (retention jobs POST-MVP / 6) |
| Mode | **Both** |
| Description | Personal data is deleted on request and expired by retention policy. |
| Preconditions | Deletion request (FR-AUTH-009) or retention schedule. |
| Trigger | Account deletion, or a scheduled job. |
| Main workflow | 1) Deletion removes profile, contacts, preferences, avatar, AI history and push subscriptions. 2) Messages in other users' histories are anonymised. 3) SMS audit logs are kept for at least 90 days in masked form, then purged. 4) Retention defaults: AI content 30 days, notifications 90 days, unrouted inbound events 90 days, exports 7 days. |
| Alternative workflows | A) Legal hold prevents deletion (admin flagged, FUTURE). |
| Expected result | No stranded personal data. |
| Error scenarios | Job failure: alert and retry. |
| Dependencies | FR-AUTH-009. |
| Acceptance criteria | AC1 Erasure completes within 30 days. AC2 Retention jobs are tested with time travel. AC3 Audit logs are never deleted before 90 days. |

### FR-PRIVACY-010 — Access Controls

| Field | Detail |
|---|---|
| Module | I — Privacy |
| User role | System |
| Priority / Phase | MVP / 1 |
| Mode | **Both** |
| Description | Role-based access control and Row Level Security protect all data. |
| Preconditions | None. |
| Trigger | Every API request and database query. |
| Main workflow | 1) Roles: `user`, `admin`. 2) The backend checks role and ownership in services. 3) RLS restricts rows by `auth.uid()`. 4) Server-only tables (webhook events, audit logs) allow no client access. 5) Admin actions require recent re-authentication for sensitive operations. |
| Alternative workflows | A) Service-role access is used only by the backend. |
| Expected result | Least-privilege access throughout. |
| Error scenarios | Unauthorised access: 403 with the standard error envelope and an audit log entry. |
| Dependencies | CC-04. |
| Acceptance criteria | AC1 Every table has RLS enabled. AC2 Tests prove cross-user reads and writes are denied. AC3 Client-supplied roles are ignored. AC4 No frontend code holds service-role keys. |
