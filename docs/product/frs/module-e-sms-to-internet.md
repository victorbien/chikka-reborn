# Module E — SMS-to-Internet (`SMSRECV`)

Part of the [Functional Requirements Specification](../functional-requirements.md). Inbound SMS and provider status callbacks arrive as webhooks and become messages in Chikka conversations.

**Reply routing model.** Replies are routed by the pair (platform number the SMS was sent from, remote mobile number). When a user sends the first SMS to a remote number, the system allocates a sender number from the configured pool such that no other user has an active route for the same (platform number, remote number) pair. The route is active for 30 days after the last outbound message and is then released. If no free pool number exists, the send is blocked with a capacity message. This keeps routing unambiguous without keywords. Keyword reply codes are FUTURE. In the Philippines and other regions, two-way availability depends on carrier and route (FR-SMS-007), so inbound handling must tolerate zero traffic.

**Modes.** Live mode receives provider webhooks. Simulation mode uses the same endpoint and code path with a mock signer and a "Simulate inbound SMS" tool (FR-SMSRECV-013). Simulated inbound messages carry the SIMULATED label.

---

### FR-SMSRECV-001 — Inbound SMS to Conversation (End to End)

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System, User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | An SMS reply from a mobile phone appears in the correct Chikka SMS conversation. |
| Preconditions | The user previously sent an SMS to that number from an active route. Two-way is available for the country and route. |
| Trigger | Provider posts an inbound message webhook. |
| Main workflow | 1) Receive and persist the raw event (FR-SMSRECV-004). 2) Validate the signature (FR-SMSRECV-002). 3) Deduplicate (FR-SMSRECV-009). 4) Check opt-out keywords (FR-SMSRECV-012). 5) Resolve account (FR-SMSRECV-005) and conversation (FR-SMSRECV-006). 6) Create the message (FR-SMSRECV-007). 7) Notify the user (FR-SMSRECV-008). 8) Respond 2xx. |
| Alternative workflows | A) Unknown sender: FR-SMSRECV-010. B) Unsupported or unrouted destination: FR-SMSRECV-011. C) Opt-out keyword: FR-SMSRECV-012. |
| Expected result | The reply appears in real time in the conversation with an SMS origin label. |
| Error scenarios | Processing failure after persistence: event marked `failed` and retried by job, webhook still returns 2xx to avoid provider storms. Database unavailable: 503 so the provider retries. |
| Dependencies | FR-SMSRECV-002 to FR-SMSRECV-012, `SmsProvider.handle_inbound_webhook`. |
| Acceptance criteria | AC1 A valid reply is visible within 5 seconds of webhook receipt (live or simulated). AC2 No processing happens before signature validation. AC3 Each inbound event is logged with provider message ID, masked sender, timestamp and matched user. AC4 Replies never appear in another user's conversation. |

### FR-SMSRECV-002 — Webhook Signature Validation

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (live: provider signing secret; simulation: mock signer with a test secret) |
| Description | All inbound webhooks, including status callbacks, are authenticated before any processing. |
| Preconditions | Signing secret configured via environment variable. |
| Trigger | Any request to `/api/v1/webhooks/<provider>/...`. |
| Main workflow | 1) Read the raw request bytes and signature header. 2) Call `validate_webhook_signature`. 3) Valid: continue. 4) Invalid or missing: respond 403, log a warning with source IP and no payload body, and stop. |
| Alternative workflows | A) Timestamp outside tolerance (replay): reject. |
| Expected result | Only authentic provider events are processed. |
| Error scenarios | Secret not configured: the endpoint fails closed with 503 and alerts the operator. |
| Dependencies | CC-06, secrets management. |
| Acceptance criteria | AC1 Invalid signatures return 403 and trigger no side effects. AC2 There is no development bypass flag. AC3 Validation uses constant-time comparison. AC4 Tests cover valid, invalid, missing and replayed signatures. |

### FR-SMSRECV-003 — SMS Origin Labelling

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Messages that came via SMS are visibly distinguished. |
| Preconditions | An inbound or outbound SMS message exists. |
| Trigger | Conversation render. |
| Main workflow | 1) SMS messages show an "SMS" icon and text label. 2) Simulated ones also show SIMULATED. 3) Status details use the SMS status model, not the Chikka-to-Chikka one. |
| Alternative workflows | A) Classic Mode uses its own icon with the same text. |
| Expected result | No confusion between channels. |
| Error scenarios | Not applicable. |
| Dependencies | FR-SMS-003, FR-MSG-002. |
| Acceptance criteria | AC1 Label has a text alternative. AC2 Present in list, detail and notification views. AC3 Cannot be disabled. |

### FR-SMSRECV-004 — Receive Inbound Webhook

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | A dedicated endpoint accepts inbound SMS and status callbacks quickly and durably. |
| Preconditions | Endpoint is reachable over HTTPS. |
| Trigger | Provider HTTP POST. |
| Main workflow | 1) Read the raw body (size limit 64 KB). 2) Validate the signature first. 3) Parse and validate the payload with Pydantic. 4) Store the raw event in `webhook_events` (server-only table). 5) Enqueue background processing. 6) Return 200 with an empty body within 2 seconds. |
| Alternative workflows | A) Unknown event type: stored and ignored with 200. |
| Expected result | Durable receipt even if processing is delayed. |
| Error scenarios | Malformed payload after a valid signature: 400 and logged. Queue unavailable: process inline as a fallback, or 503. |
| Dependencies | FR-SMSRECV-002, background worker. |
| Acceptance criteria | AC1 Endpoint rate limited by source. AC2 Raw events are retained for at least 90 days. AC3 Webhook payloads are not exposed to clients. AC4 Phone numbers are masked in application logs. |

### FR-SMSRECV-005 — Resolve Destination Chikka Account

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Determine which Chikka user an inbound SMS is for. |
| Preconditions | Event is authenticated and unique. |
| Trigger | Inbound message processing. |
| Main workflow | 1) Look up the active route for (To, From). 2) Retrieve the owning user. 3) Check that the user is active and not suspended. 4) Check the sender is not blocked by that user. |
| Alternative workflows | A) No route: FR-SMSRECV-011. B) User suspended or deleted: message stored as undeliverable, nothing shown. |
| Expected result | A single destination user, or an explicit non-match. |
| Error scenarios | Route points to a deleted user: treated as no route. |
| Dependencies | Route table, FR-SMS-009. |
| Acceptance criteria | AC1 Resolution is deterministic and tested. AC2 Blocked senders produce stored-but-hidden messages without notification. AC3 Unresolved messages are flagged for admin review. |

### FR-SMSRECV-006 — Resolve Conversation

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Attach the inbound message to the right `sms` conversation. |
| Preconditions | Destination user resolved. |
| Trigger | After account resolution. |
| Main workflow | 1) Find the user's `sms` conversation for the remote number. 2) If found, use it. 3) If absent (for example the conversation was deleted by the user), create a new one and link the contact if it exists. 4) Update conversation last-activity time. |
| Alternative workflows | A) Conversation archived: it is un-archived unless muted. B) Conversation deleted for the user: a new thread starts and old history stays hidden. |
| Expected result | Replies join the existing thread. |
| Error scenarios | Concurrent creation: unique constraint ensures one conversation. |
| Dependencies | FR-MSG-012. |
| Acceptance criteria | AC1 At most one `sms` conversation per (user, remote number). AC2 Inbound messages never create a Chikka-to-Chikka conversation. AC3 Race conditions are covered by a test. |

### FR-SMSRECV-007 — Create Inbound Message

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Persist the inbound SMS as a message. |
| Preconditions | Conversation resolved. |
| Trigger | After conversation resolution. |
| Main workflow | 1) Sanitise the body and keep the original encoding. 2) Store direction `inbound`, provider message ID, received timestamp and `is_simulated`. 3) Truncate the body at 1600 characters and flag it if truncated. 4) Broadcast to the user's realtime channel. |
| Alternative workflows | A) MMS or media: attachments ignored, text kept, and a note "media not supported" shown. |
| Expected result | A stored inbound message in the thread. |
| Error scenarios | Empty body (for example media only): stored with a placeholder. |
| Dependencies | FR-MSG-007. |
| Acceptance criteria | AC1 Provider message ID is unique. AC2 No credit is charged for inbound messages. AC3 Content is escaped on render. AC4 Inbound messages do not use the Chikka-to-Chikka delivered and read states. |

### FR-SMSRECV-008 — Notify Recipient

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System, User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | The user is alerted about a new SMS reply. |
| Preconditions | Message created and sender not blocked. |
| Trigger | Inbound message created. |
| Main workflow | 1) Create an in-app notification. 2) Update unread count. 3) Push and email follow the user's preferences (FR-NOTIF-005). 4) Muted conversations skip alerts. |
| Alternative workflows | A) User viewing the thread: no alert, message marked seen. |
| Expected result | The user knows a reply arrived. |
| Error scenarios | Push service failure: in-app notification remains. |
| Dependencies | Module G. |
| Acceptance criteria | AC1 Notification text shows a truncated preview and the SMS label. AC2 Respects mute and block. AC3 Simulated messages say SIMULATED in notifications. |

### FR-SMSRECV-009 — Prevent Duplicate Processing

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System |
| Priority / Phase | MVP / 2 |
| Mode | **Both** (simulation includes a `duplicate_callback` scenario) |
| Description | Provider retries or replays must not create duplicate messages or events. |
| Preconditions | None. |
| Trigger | Webhook with a provider message ID already seen. |
| Main workflow | 1) A unique constraint covers (provider, provider message ID, event type). 2) On conflict the handler returns 200 and does nothing further. 3) The duplicate is counted in metrics. |
| Alternative workflows | A) Same ID with different content: logged as an anomaly, the first is kept. |
| Expected result | Exactly-once effect. |
| Error scenarios | Race between two simultaneous deliveries: one succeeds, the other hits the constraint. |
| Dependencies | Database constraints. |
| Acceptance criteria | AC1 Replaying a webhook 10 times yields one message. AC2 Duplicate attempts are logged. AC3 Test covers concurrent duplicates. |

### FR-SMSRECV-010 — Handle Unknown Sender

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System, Admin |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Inbound SMS from a number with no route is handled safely. |
| Preconditions | Signature valid, no route for (To, From). |
| Trigger | Inbound webhook. |
| Main workflow | 1) Store the event as `unrouted`. 2) Do not display it to any user. 3) Flag it in the admin dashboard with a masked sender. 4) Do not auto-reply. |
| Alternative workflows | A) If the sender's text is an opt-out keyword, FR-SMSRECV-012 still applies. B) Repeated unrouted messages from one sender (over 10 per hour) are rate limited and flagged as possible abuse. |
| Expected result | No misdelivery; admins can investigate. |
| Error scenarios | Not applicable. |
| Dependencies | FR-ADMIN-007. |
| Acceptance criteria | AC1 Unrouted messages are retained for 90 days then purged. AC2 No user can see them. AC3 No automatic reply is sent. |

### FR-SMSRECV-011 — Handle Unsupported Destination

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System, User |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Inbound (two-way) handling for countries or routes where it is not supported is explicit rather than silent. |
| Preconditions | Country capability marks inbound unsupported, or the destination number is not part of the pool. |
| Trigger | Webhook for such a number, or a send to such a country. |
| Main workflow | 1) On send, the user is warned "replies are not supported for this destination" (FR-SMS-007). 2) On an unexpected inbound message, handle it as unrouted (FR-SMSRECV-010) and flag a capability configuration mismatch for admins. |
| Alternative workflows | A) Admin corrects the capability table. |
| Expected result | No misleading promise of replies; inconsistencies are detected. |
| Error scenarios | Not applicable. |
| Dependencies | FR-ADMIN-005. |
| Acceptance criteria | AC1 UI never implies replies work where unsupported. AC2 Mismatches generate an admin alert. AC3 Capability lookups are covered by tests for at least the Philippines, a supported country and an unsupported country. |

### FR-SMSRECV-012 — Handle Opt-Out Messages

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | System, SMS contact |
| Priority / Phase | MVP / 2 |
| Mode | **Both** |
| Description | Recipients can opt out by replying with a keyword. |
| Preconditions | Inbound message processed after signature and duplicate checks. |
| Trigger | Message body, after trimming and case folding, matches STOP, STOPALL, UNSUBSCRIBE, CANCEL, END or QUIT (configurable; local-language equivalents allowed). |
| Main workflow | 1) Record the opt-out for the remote number scoped to the platform sender, with timestamp and source message. 2) Block further outbound SMS to that number from the platform. 3) Notify affected senders in-app that the recipient opted out. 4) Send the confirmation required by regulation or the provider (live) or a simulated confirmation (simulation). |
| Alternative workflows | A) START or UNSTOP reply restores consent (FR-PRIVACY-008). B) Provider handles opt-out natively: the platform mirrors the provider's event. |
| Expected result | Opt-outs are honoured immediately and persistently. |
| Error scenarios | Confirmation fails: opt-out still stands. |
| Dependencies | FR-PRIVACY-003, FR-PRIVACY-008. |
| Acceptance criteria | AC1 After opt-out, any send attempt to the number is blocked server-side. AC2 Opt-out is audit logged with a masked number. AC3 Keywords match whole message only, not substrings. AC4 Opt-out persists across account changes. |

### FR-SMSRECV-013 — Simulate Inbound SMS

| Field | Detail |
|---|---|
| Module | E — SMS-to-Internet |
| User role | Developer, Admin |
| Priority / Phase | MVP / 2 |
| Mode | **Simulation only** |
| Description | A tool injects fake inbound SMS through the real webhook path. |
| Preconditions | Simulation mode. Non-production or demo environment. |
| Trigger | Admin submits the "Simulate reply" form for an existing simulated route. |
| Main workflow | 1) Choose route and enter text (including opt-out keywords). 2) The tool builds a payload and signs it with the mock signer. 3) It posts to the webhook endpoint. 4) The normal pipeline runs and the message appears labelled SIMULATED. |
| Alternative workflows | A) Replay the last payload to test duplicate handling. |
| Expected result | Full two-way flow can be demonstrated without a real phone. |
| Error scenarios | Used in live mode: refused. |
| Dependencies | FR-SMSRECV-002, FR-SMS-013. |
| Acceptance criteria | AC1 Unavailable in live mode and in production. AC2 Output passes through signature validation. AC3 Simulated messages are labelled. |
