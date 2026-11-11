# Module D — Internet-to-SMS (`SMS`)

Part of the [Functional Requirements Specification](../functional-requirements.md). Outbound SMS from the web app to a mobile number, through the `SmsProvider` interface.

**Status model** (used by every requirement in this module and in Module E):

| Status | Meaning | Set by |
|---|---|---|
| `queued` | Stored locally, awaiting dispatch | Platform |
| `retrying` | A transient failure occurred and a retry is scheduled | Platform |
| `accepted` | The provider accepted the message into its queue. **Not delivery.** | Provider response |
| `sent` | Provider reports the message handed to the carrier | Provider callback |
| `delivered` | Provider confirms delivery to the handset | Provider callback only |
| `undelivered` | Carrier or handset did not accept it | Provider callback |
| `failed` | Provider rejected it, or retries are exhausted (`is_permanent = true`) | Provider or platform |

Simulation mode emits the same statuses on a timed schedule. Every simulated message carries `is_simulated = true` and a permanent SIMULATED label. Real sends require live mode, explicit operator confirmation (FR-ADMIN-003) and human approval before any real recipient is messaged.

---

### FR-SMS-001 — Compose and Send SMS

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (same flow; provider differs) |
| Description | End-to-end flow for a user to send an SMS from the browser. |
| Preconditions | Verified user. Credits sufficient (or demo credits in simulation). Recipient not opted out. Destination supported. |
| Trigger | User opens "Send SMS" or an SMS conversation and submits a message. |
| Main workflow | 1) Enter recipient (FR-SMS-006). 2) Capability check (FR-SMS-007). 3) Compose with live segment and cost preview (FR-SMS-002). 4) Confirmation (FR-SMS-008). 5) Backend validates, checks credits and consent, and stores the message as `queued` with an idempotency key (FR-SMS-012). 6) A background job sends through the provider (FR-SMS-009). 7) The user sees the status progress (FR-SMS-004). |
| Alternative workflows | A) Send from an existing SMS conversation with the recipient pre-filled. B) Draft saved locally if the user leaves. C) AI-assisted text enters only after user approval (FR-AI-006). |
| Expected result | A stored message with a status trail, visible in the conversation. |
| Error scenarios | Validation failure: 422 with field messages. Insufficient credits: FR-SMS-005. Unsupported country or opted-out recipient: blocked with explanation. Live mode misconfigured: explicit error to the operator, never silent fallback to simulation. Rate limit: 429. |
| Dependencies | FR-SMS-002 to FR-SMS-012, FR-CREDIT-003, FR-PRIVACY-007, FR-PRIVACY-008, CC-02. |
| Acceptance criteria | AC1 No provider call happens inside the request handler. AC2 The message is stored regardless of provider outcome. AC3 Each outbound attempt is logged with a masked recipient. AC4 Unverified users cannot send. AC5 Maximum 30 SMS per hour per user by default (configurable). AC6 The handler returns the message ID and `queued` status. |

### FR-SMS-002 — Segment Count and Cost Preview

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Users see character count, encoding, segments and estimated credit cost before sending. |
| Preconditions | A valid destination country is known (cost needs country). |
| Trigger | User types or edits the message or recipient. |
| Main workflow | 1) Client detects encoding: GSM-7 if every character is in the GSM-7 set (extension characters count as two), otherwise Unicode. 2) Segments are computed: GSM-7 160 single or 153 per part; Unicode 70 single or 67 per part. 3) Cost = segments x per-country rate (FR-CREDIT-002). 4) Preview shows "142/160 characters, GSM-7, 1 segment, 1 credit". 5) The server recomputes the same values at send time and treats its result as authoritative. |
| Alternative workflows | A) Rate not configured: show "Cost unavailable". In live mode sending is blocked; in simulation it uses the demo default rate and says so. B) Encoding switches to Unicode: a notice explains the segment change. |
| Expected result | No surprise cost. |
| Error scenarios | Message over the maximum of 10 segments: send disabled with explanation. |
| Dependencies | FR-CREDIT-002, FR-CREDIT-005. |
| Acceptance criteria | AC1 Client and server calculations match for a shared set of test vectors. AC2 The preview updates within 100 ms of typing. AC3 Cost is shown in credits, with currency only if configured. AC4 In simulation, the preview is labelled SIMULATED. AC5 Cost is an estimate until accepted; the label says "estimated". |

### FR-SMS-003 — Simulation Mode Labelling

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User, Admin |
| Priority / Phase | MVP / 2 |
| Mode | **Simulation** |
| Description | Everything produced by `MockSmsProvider` is permanently marked as simulated. |
| Preconditions | System runs in simulation mode. |
| Trigger | Any render of a simulated message, status or notification. |
| Main workflow | 1) Messages are stored with `is_simulated = true` and the mode at send time. 2) The SIMULATED badge appears in the message list, detail, delivery status, notifications, exports and admin views. 3) A persistent banner states that no real SMS is sent. |
| Alternative workflows | A) Switching to live later does not relabel older messages. |
| Expected result | A simulated message can never be mistaken for a real one. |
| Error scenarios | Missing flag on a message: treated as simulated-unknown and flagged to admins. |
| Dependencies | FR-ADMIN-003. |
| Acceptance criteria | AC1 The badge has text, not colour alone. AC2 The badge cannot be hidden by preferences or Classic Mode. AC3 Simulated and live messages are filterable. AC4 No simulated message ever shows a real-looking provider SID. |

### FR-SMS-004 — Delivery Status Tracking

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User, System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | The platform records and displays status events exactly as the provider reports them. |
| Preconditions | A message has a provider message ID (live) or simulated ID. |
| Trigger | Provider status callback (live), simulated timer event (simulation), or manual status poll. |
| Main workflow | 1) The callback is signature-validated (FR-SMSRECV-002). 2) The event is stored in `sms_status_events` with provider ID, status and timestamp. 3) The message status moves forward only. 4) The client is updated in real time. 5) Notifications fire on `delivered` and `failed` (FR-NOTIF-003). |
| Alternative workflows | A) No callback after 30 minutes: a reconciliation job polls `get_message_status`. B) Route lacks delivery receipts: status stays `sent` and the UI says "delivery not confirmed". |
| Expected result | Honest, auditable status. |
| Error scenarios | Unknown provider ID: event stored and flagged. Late callback after failure: recorded, status updated only if forward-valid. |
| Dependencies | FR-SMSRECV-002, FR-SMS-009. |
| Acceptance criteria | AC1 `delivered` is set only by a delivery confirmation. AC2 `accepted` is displayed as "Accepted by provider", never "Delivered". AC3 Every event has a timestamp and raw payload reference. AC4 Duplicate callbacks do not duplicate events. AC5 Simulated timelines use the same status names. |

### FR-SMS-005 — Insufficient Credit Prevention

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (simulation checks the demo balance) |
| Description | Users cannot send when their balance cannot cover the message. |
| Preconditions | Cost is known. |
| Trigger | Composing or submitting. |
| Main workflow | 1) UI compares cost to the available balance. 2) If insufficient, the Send button is disabled with "You need 3 credits, you have 1". 3) The backend enforces the same check. |
| Alternative workflows | A) Top-up link when payments exist (FR-CREDIT-004); otherwise contact-admin text. |
| Expected result | No send occurs without sufficient credit. |
| Error scenarios | Balance changes between preview and send: 402 with current balance. |
| Dependencies | FR-CREDIT-009. |
| Acceptance criteria | AC1 Server-side check cannot be bypassed. AC2 Failed check stores nothing and charges nothing. AC3 Message text is preserved in the compose box. |

### FR-SMS-006 — Recipient Entry and Phone Validation

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | Not provider-dependent |
| Description | Users enter a recipient number or pick an SMS contact, and the number is validated. |
| Preconditions | None. |
| Trigger | User types a number or selects a contact. |
| Main workflow | 1) Number is parsed with a phone library using the user's default country. 2) Normalised to E.164. 3) Validity and type (mobile, landline, unknown) are checked. 4) The formatted number and country are displayed. |
| Alternative workflows | A) Pick from SMS contacts. B) Local format (09xx for the Philippines) is accepted and converted to +63. |
| Expected result | A validated E.164 number with an identified country. |
| Error scenarios | Invalid number: inline error. Landline detected: warning that SMS may fail. Short code or premium number: blocked. |
| Dependencies | Phone number library, FR-SMS-007. |
| Acceptance criteria | AC1 Validation matches on client and server. AC2 Premium and short codes are rejected. AC3 The number is masked in logs. AC4 Sending to your own verified number is allowed. |

### FR-SMS-007 — Destination Country Capability Check

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User, System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (configuration-driven) |
| Description | Before sending, the platform checks what is possible for the destination country. |
| Preconditions | Country capability configuration exists (FR-ADMIN-005). |
| Trigger | Valid recipient entered or send submitted. |
| Main workflow | 1) Look up the country by dialling code. 2) Evaluate: outbound supported, two-way (replies) supported, alphanumeric sender allowed, registered sender required, content restrictions. 3) Display a capability summary, for example "Replies not supported in this country". 4) Block sending if outbound is unsupported or a required registered sender is unavailable. |
| Alternative workflows | A) Unknown country: treated as unsupported. B) Two-way unsupported: send allowed with a prominent warning that replies will not arrive. C) Philippines: shows sender registration status and content-restriction notice. |
| Expected result | No false promises about reach or replies. |
| Error scenarios | Configuration missing: send blocked, admin alerted. |
| Dependencies | FR-ADMIN-005. |
| Acceptance criteria | AC1 Capability is checked server-side on every send. AC2 The UI never claims universal two-way SMS. AC3 Unsupported destinations return a clear reason. AC4 Simulation uses the same rules so demos stay honest. |

### FR-SMS-008 — Confirm Message Before Sending

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Users review and confirm the final message, recipient, segments and cost. |
| Preconditions | Draft is valid. |
| Trigger | User presses Send. |
| Main workflow | 1) A confirmation dialog shows masked-but-recognisable recipient, full text, segments, estimated cost, mode badge (SIMULATED or LIVE) and an AI-assisted badge when relevant. 2) User confirms. 3) The request is submitted. |
| Alternative workflows | A) Cancel returns to editing. B) Live mode additionally shows "This will send a real SMS". |
| Expected result | Every send is a deliberate act. |
| Error scenarios | Dialog open while balance changes: values refresh. |
| Dependencies | FR-AI-007. |
| Acceptance criteria | AC1 Confirmation cannot be skipped for AI-generated text. AC2 Mode is visible in the dialog. AC3 Focus is trapped and Escape cancels. AC4 Double-click does not double-send (FR-SMS-012). |

### FR-SMS-009 — Send Through Provider and Store Provider Response

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | A background job sends via `SmsProvider` and stores the provider response. |
| Preconditions | A `queued` message exists. |
| Trigger | Background job picks up the message. |
| Main workflow | 1) Resolve the provider from configuration. 2) Call `send_message`. 3) Store provider name, provider message ID (for example Twilio SID), response status, error code and a redacted raw response. 4) Set status `accepted` on success. 5) Trigger credit deduction (FR-CREDIT-003). |
| Alternative workflows | A) Transient error: FR-SMS-011. B) Permanent rejection: FR-SMS-010. |
| Expected result | Message linked to its provider identifier. |
| Error scenarios | Live provider cannot initialise: operation fails explicitly, the operator is alerted, and the system does not fall back to simulation. Timeout: treated as transient, with a duplicate check by idempotency key. |
| Dependencies | `SmsProvider`, FR-SMS-012, CC-03. |
| Acceptance criteria | AC1 No credentials appear in logs or responses. AC2 Provider IDs are unique per message. AC3 Credit is deducted only after acceptance. AC4 In simulation the provider ID is prefixed `SIM-`. |

### FR-SMS-010 — Handle Failures

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User, System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Failures are classified, shown, and recorded. |
| Preconditions | Provider rejected the message, a callback reported failure, or retries were exhausted. |
| Trigger | Failure response or callback. |
| Main workflow | 1) Classify as transient (network, throttling, 5xx), permanent (invalid number, blocked, country not allowed) or carrier-level (undelivered). 2) Permanent: mark `failed` with `is_permanent = true`. 3) Refund any deducted credits (FR-CREDIT-003). 4) Notify the user with a readable reason (FR-NOTIF-003). 5) Show "Retry" or "Edit and resend" where valid. |
| Alternative workflows | A) User-initiated resend creates a new message with a new idempotency key. |
| Expected result | Users know what happened and what to do. |
| Error scenarios | Unknown error code: generic message plus a reference ID, details logged server-side. |
| Dependencies | FR-SMS-011, FR-NOTIF-003. |
| Acceptance criteria | AC1 Provider error text is not shown raw to users. AC2 Permanent failures refund credits exactly once. AC3 Failed messages remain visible in history. AC4 Admin failed-message view lists them (FR-ADMIN-009). |

### FR-SMS-011 — Retry Eligible Failures

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (simulation supports injected errors to test this) |
| Description | Transient failures are retried automatically with backoff. |
| Preconditions | Failure classified as transient. Attempts below the maximum. |
| Trigger | Transient failure. |
| Main workflow | 1) Status becomes `retrying`. 2) The next attempt is scheduled using exponential backoff with jitter (base 5 s, factor 2, cap 5 min). 3) The same idempotency key is reused. 4) After the configured maximum (default 3) the message is marked permanently `failed`. |
| Alternative workflows | A) Provider returns Retry-After: honoured. B) Admin manually re-queues a failed message (FR-ADMIN-009). |
| Expected result | Self-healing without duplicates or double charges. |
| Error scenarios | Worker crash mid-attempt: job is re-picked; idempotency prevents a duplicate send. |
| Dependencies | FR-SMS-012, FR-CREDIT-003. |
| Acceptance criteria | AC1 Maximum attempts are configurable per environment. AC2 Retries never double-deduct credit. AC3 Only transient errors retry. AC4 Each attempt is logged with attempt number. AC5 Tests can seed jitter for determinism. |

### FR-SMS-012 — Idempotent Send

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | User, System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Every outbound send carries an idempotency key so repeats never create duplicate messages. |
| Preconditions | Client generates a UUID per compose-and-confirm action. |
| Trigger | Send request received. |
| Main workflow | 1) The key is sent in an `Idempotency-Key` header. 2) A unique constraint on (user, key) stores the first request. 3) A repeat with the same key and payload returns the original result. |
| Alternative workflows | A) Same key with a different payload: 409 conflict. |
| Expected result | Network retries and double-clicks are safe. |
| Error scenarios | Missing key: 422. |
| Dependencies | Database unique constraint. |
| Acceptance criteria | AC1 Duplicate requests create one message and one charge. AC2 Keys are retained for at least 24 hours. AC3 Simulation supports idempotency test scenarios. |

### FR-SMS-013 — Simulated Delivery Scenarios

| Field | Detail |
|---|---|
| Module | D — Internet-to-SMS |
| User role | Developer, Admin |
| Priority / Phase | MVP / 2 |
| Mode | **Simulation only** |
| Description | `MockSmsProvider` emits realistic outcomes, including errors, so that retry and failure UX can be exercised. |
| Preconditions | Simulation mode and a non-production environment (or demo flag). |
| Trigger | Message sent to a reserved test number, or a scenario chosen in the simulation panel. |
| Main workflow | 1) Scenarios: `delivered`, `failed`, `undelivered`, `transient_error_then_success`, `permanent_error`, `delayed_delivery`, `no_receipt`, `duplicate_callback`. 2) Status callbacks follow a configurable timeline (default accepted +1 s, sent +3 s, delivered +6 s). 3) Callbacks go through the same signed webhook path using a mock signer. |
| Alternative workflows | A) Default scenario for ordinary numbers is `delivered`. |
| Expected result | Demos and tests cover the full state machine at zero cost. |
| Error scenarios | Scenario selector disabled in production. |
| Dependencies | FR-SMS-004, FR-SMSRECV-002. |
| Acceptance criteria | AC1 No network call to any SMS vendor occurs. AC2 Reserved test numbers are fictitious. AC3 Everything is labelled SIMULATED. AC4 Simulated callbacks still pass signature validation. |
