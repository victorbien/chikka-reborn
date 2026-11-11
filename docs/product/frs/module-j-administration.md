# Module J — Administration (`ADMIN`)

Part of the [Functional Requirements Specification](../functional-requirements.md).

**Common rules for every admin requirement:**
- Role `admin` is required, checked server-side. Admin routes live under `/api/v1/admin/`.
- Sensitive actions (provider mode, credit adjustments, deletions, suspensions) require re-authentication within the last 10 minutes.
- Every state-changing action is audit logged with admin ID, target, reason and timestamp (FR-ADMIN-012).
- Phone numbers are masked by default. Message bodies are not shown in monitoring views. Unmasking is a separate, logged action available only for investigating a report.
- Secrets and credentials are never displayed. Only "configured / not configured" is shown.
- Live and simulated data are distinguishable and filterable everywhere.
- Lists are paginated with filters.

---

### FR-ADMIN-001 — Platform Statistics

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** (split by live and simulated) |
| Description | A dashboard summarises usage. |
| Preconditions | Admin signed in. |
| Trigger | Admin opens the dashboard. |
| Main workflow | 1) Tiles show total users, active users (24 hours, 7 days, 30 days), Chikka messages, SMS sent and received, delivery rate, failure rate, AI requests, credits consumed. 2) Date range filter. 3) Metrics refresh every 5 minutes. |
| Alternative workflows | A) Export a CSV of the aggregates. |
| Expected result | An overview at a glance. |
| Error scenarios | A metric query fails: that tile shows an error, others still render. |
| Dependencies | Aggregation queries or materialised views. |
| Acceptance criteria | AC1 Delivery rate counts only `delivered` over `accepted` (never acceptance alone). AC2 Simulated and live are shown separately. AC3 Non-admins receive 403. |

### FR-ADMIN-002 — User Management

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | Not provider-dependent |
| Description | Admins search for users and manage their status. |
| Preconditions | Admin signed in. |
| Trigger | Admin opens Users. |
| Main workflow | 1) Search by email, username, or ID. 2) View profile status, verification, last active, counts, credit balances and reports against the user. 3) Actions: suspend, reinstate, force logout, clear lockout, delete. 4) Each requires a reason and confirmation. |
| Alternative workflows | A) Suspended users see a notice and cannot use the app. B) Bulk actions are not supported. |
| Expected result | Controlled moderation. |
| Error scenarios | An admin cannot suspend or delete themselves or the last admin: 409. |
| Dependencies | FR-AUTH-006, FR-AUTH-009, FR-ADMIN-012. |
| Acceptance criteria | AC1 Message content is not shown in user detail. AC2 Suspension takes effect on the next request and revokes sessions. AC3 All actions are audit logged with reason. |

### FR-ADMIN-003 — SMS Mode Control

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** (this switches between them) |
| Description | Admins view and switch between simulation and live mode. |
| Preconditions | Re-authentication. Live credentials are configured (FR-ADMIN-014) for live. |
| Trigger | Admin toggles the mode. |
| Main workflow | 1) The current mode is shown prominently in the admin header and as a banner for all users in simulation. 2) Switching to live shows a warning dialog: real messages, real cost, regulatory duties, and requires typing "ENABLE LIVE SMS" and the environment name. 3) The backend runs a provider health check. 4) On success the mode changes and the event is audit logged. 5) Switching back to simulation is immediate. |
| Alternative workflows | A) Live mode is only available in environments whitelisted by configuration (for example never in local development). |
| Expected result | Mode changes are deliberate and traceable. |
| Error scenarios | Health check or credentials failure: the mode stays unchanged and a clear error is shown. The system never silently falls back to simulation: if live is configured and later fails, sends fail explicitly and admins are alerted. |
| Dependencies | FR-ADMIN-014, FR-SMS-009. |
| Acceptance criteria | AC1 Live requires explicit operator confirmation per environment. AC2 No real SMS is sent before confirmation. AC3 Mode change is audit logged. AC4 In-flight simulated messages remain simulated. |

### FR-ADMIN-004 — SMS Audit Log

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | A read-only log of every SMS attempt and status event. |
| Preconditions | Admin signed in. |
| Trigger | Admin opens SMS Audit. |
| Main workflow | 1) Rows: message ID, idempotency key, provider, mode, masked recipient (+63****1234), status, country, segments, timestamp. 2) Filter by date, status, user, mode, country. 3) Open a message to see the status event timeline. |
| Alternative workflows | A) Export a masked CSV. |
| Expected result | An investigable trail. |
| Error scenarios | Query too broad: requires a date range. |
| Dependencies | FR-SMS-004. |
| Acceptance criteria | AC1 Read-only; no edit or delete controls. AC2 Entries are retained at least 90 days. AC3 Bodies are not shown. AC4 Inbound events and callbacks are included. |

### FR-ADMIN-005 — Country Capability Management

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | Admins maintain the per-country SMS capability and pricing configuration. |
| Preconditions | Admin signed in. |
| Trigger | Admin edits a country row. |
| Main workflow | 1) Fields: outbound supported, inbound/two-way supported, alphanumeric sender allowed, registered sender required, registered sender status, content restrictions note, credit multiplier. 2) Save creates a new version. 3) Changes take effect immediately. |
| Alternative workflows | A) Seed data ships with the Philippines, a few supported countries and an unsupported example. B) Import and export as JSON. |
| Expected result | The platform's promises match reality. |
| Error scenarios | Invalid country code: 422. |
| Dependencies | FR-SMS-007, FR-CREDIT-002. |
| Acceptance criteria | AC1 The Philippines row requires registered sender status. AC2 Changes are versioned and audit logged. AC3 Defaults for unknown countries are unsupported. |

### FR-ADMIN-006 — AI Usage Monitoring

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 3 |
| Mode | Live (Bedrock) |
| Description | Admins view AI usage and cost indicators. |
| Preconditions | AI requests have occurred. |
| Trigger | Admin opens AI Usage. |
| Main workflow | 1) Charts and tables: requests by feature, input and output tokens, average latency, error rate, acceptance rate, top users by volume (pseudonymised IDs). 2) Date range filter. 3) Per-user rate limit settings. |
| Alternative workflows | A) Cost estimate from configured token prices. |
| Expected result | Cost awareness and abuse detection. |
| Error scenarios | No data: empty state. |
| Dependencies | FR-AI-011. |
| Acceptance criteria | AC1 Only metadata is shown. AC2 Content is never visible. AC3 Limits can be changed without deployment. |

### FR-ADMIN-007 — SMS Activity Monitoring

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | Real-time view of outbound and inbound SMS volume and anomalies. |
| Preconditions | Admin signed in. |
| Trigger | Admin opens SMS Activity. |
| Main workflow | 1) Time series for sent, accepted, delivered, failed. 2) Top senders by volume. 3) Unrouted inbound messages (FR-SMSRECV-010) and capability mismatches (FR-SMSRECV-011). 4) Spike alerts when volume exceeds a threshold. |
| Alternative workflows | A) Drill down to a user's SMS activity. |
| Expected result | Early detection of abuse or misconfiguration. |
| Error scenarios | Not applicable. |
| Dependencies | FR-ADMIN-004. |
| Acceptance criteria | AC1 Refresh at most every 30 seconds. AC2 Spikes are flagged at configurable thresholds. AC3 Unrouted items link to review. |

### FR-ADMIN-008 — Delivery Monitoring

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | Delivery performance by country and provider. |
| Preconditions | Messages exist. |
| Trigger | Admin opens Delivery. |
| Main workflow | 1) Table by country and provider: accepted, sent, delivered, undelivered, failed, no receipt, median time to deliver. 2) Highlight countries under a delivery rate threshold. 3) Show "receipts unavailable" for routes that do not report delivery. |
| Alternative workflows | A) Compare modes. |
| Expected result | Honest delivery reporting. |
| Error scenarios | Not applicable. |
| Dependencies | FR-SMS-004. |
| Acceptance criteria | AC1 Delivered rates exclude acceptance-only messages. AC2 Messages without receipts are a separate category. AC3 Simulated data are separate. |

### FR-ADMIN-009 — Failed Message Monitoring

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | Admins review failed and stuck messages and can re-queue eligible ones. |
| Preconditions | Failed or retrying messages exist. |
| Trigger | Admin opens Failed Messages. |
| Main workflow | 1) List with failure category, error code, attempts, age and user. 2) Stuck messages (queued longer than 10 minutes) are highlighted. 3) Admin can re-queue transient failures. 4) Re-queuing reuses the idempotency key and does not double-charge. |
| Alternative workflows | A) Mark as resolved with a note. |
| Expected result | Visible recovery path. |
| Error scenarios | Re-queue of a permanent failure: refused. |
| Dependencies | FR-SMS-010, FR-SMS-011. |
| Acceptance criteria | AC1 Provider raw errors are visible only to admins. AC2 Re-queue is audit logged. AC3 No duplicate sends result. |

### FR-ADMIN-010 — Credit Management

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 4 |
| Mode | **Both** |
| Description | Admins view balances and the ledger, and make adjustments (FR-CREDIT-010). |
| Preconditions | Admin signed in. |
| Trigger | Admin opens Credits. |
| Main workflow | 1) Search a user to see live and demo balances and ledger. 2) Adjust with reason. 3) View total credits issued and consumed. 4) Configure the default demo grant. |
| Alternative workflows | A) Reset demo balance. |
| Expected result | Controlled credit operations. |
| Error scenarios | See FR-CREDIT-010. |
| Dependencies | FR-CREDIT-010. |
| Acceptance criteria | AC1 Ledger is read-only except through adjustments. AC2 Totals reconcile with the ledger. |

### FR-ADMIN-011 — Abuse Report Management

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | Admins triage reports from users. |
| Preconditions | Reports exist. |
| Trigger | Admin opens Reports. |
| Main workflow | 1) Queue with status (open, reviewing, actioned, dismissed). 2) Open a report to see the snapshot, reporter (visible only to admins), reported user history and prior reports. 3) Actions: dismiss, warn, suspend, block number from SMS. 4) Add a resolution note. |
| Alternative workflows | A) Escalate for legal review (FUTURE). |
| Expected result | Documented moderation decisions. |
| Error scenarios | Reporter or reported user deleted: snapshot is kept. |
| Dependencies | FR-PRIVACY-004. |
| Acceptance criteria | AC1 Reporter identity is never shared with the reported user. AC2 Every decision has a note. AC3 SLA indicators show reports older than 48 hours. |

### FR-ADMIN-012 — Audit Logs (Admin and Security Events)

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | An immutable log of admin, security and compliance events. |
| Preconditions | Events have occurred. |
| Trigger | Admin opens Audit Logs. |
| Main workflow | 1) Entries cover: admin actions, mode changes, credit adjustments, opt-out lifts, auth lockouts, permission denials, data exports and deletions. 2) Filter by actor, action, target, date. 3) Entries are read-only. |
| Alternative workflows | A) Export masked CSV. |
| Expected result | Accountability. |
| Error scenarios | Not applicable. |
| Dependencies | CC-03. |
| Acceptance criteria | AC1 No edit or delete UI or API exists. AC2 Entries retained at least 90 days (SMS) or longer per policy for security events. AC3 No message bodies, tokens, or secrets in entries. |

### FR-ADMIN-013 — System Health and Feature Switches

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | Admins see component health and can disable risky features. |
| Preconditions | Admin signed in. |
| Trigger | Admin opens System Health. |
| Main workflow | 1) Status cards for the API, database, realtime, background worker queue depth, SMS provider (live or mock) and AI provider with the last check time. 2) Webhook failure counts and signature rejection counts. 3) Switches: pause outbound SMS, disable AI, disable registration. |
| Alternative workflows | A) Health check history for the past 24 hours. |
| Expected result | Operators can detect and contain problems. |
| Error scenarios | A check fails: that component shows degraded with an error code. |
| Dependencies | Health endpoints. |
| Acceptance criteria | AC1 Switches take effect within 1 minute. AC2 Switch changes are audit logged. AC3 Users see friendly messages when a feature is paused. |

### FR-ADMIN-014 — Provider Configuration

| Field | Detail |
|---|---|
| Module | J — Administration |
| User role | Admin |
| Priority / Phase | POST-MVP / 2 |
| Mode | **Both** |
| Description | Admins view and manage non-secret provider settings. |
| Preconditions | Admin signed in. |
| Trigger | Admin opens SMS Provider. |
| Main workflow | 1) View active provider (`MockSmsProvider` or `TwilioSmsProvider`) and credential status (configured or missing). 2) Manage sender numbers and the pool, sender ID registration status, webhook URL, max retry attempts, backoff base and cap. 3) Run a health check. 4) Send a test message only to an admin-verified number and only in live mode, after confirmation. |
| Alternative workflows | A) Secrets are rotated outside the app via environment configuration. |
| Expected result | Operators can configure safely. |
| Error scenarios | Missing credentials: live mode cannot be enabled. |
| Dependencies | FR-ADMIN-003. |
| Acceptance criteria | AC1 Credential values are never displayed or returned by the API. AC2 Test sends need explicit confirmation. AC3 Changes are audit logged. |
