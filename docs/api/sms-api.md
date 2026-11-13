# SMS API

**Document:** CHKR-API-005  
**Project:** Chikka Reborn  
**Version:** 1.1  
**Status:** Implemented (Phase 2)  
**Last Revised:** November 2026  

---

## Purpose

All SMS endpoints: country capability, quote, consent, sending, history, retry, provider webhooks and administration. Behaviour is defined in [sms-gateway-design.md](../architecture/sms-gateway-design.md). Where this file and the earlier draft differ, this file matches the code.

Every success response is `{ "data": ..., "request_id": "..." }`; lists add `pagination`. Every error is `{ "error": { "code", "message", "details" }, "request_id" }`. Phone numbers are masked (`+63****4567`) in every response.

## Base paths

| Path | Auth |
|---|---|
| `/api/v1/sms/*` | Bearer token, active (verified email) account |
| `/api/v1/admin/sms/*` | Bearer token, `admin` role (checked from the database on each call) |
| `/api/v1/webhooks/{provider}/{inbound,status}` | Provider signature over the raw body. No JWT |

## Modes and honesty rules

- The server runs in exactly one mode, `simulation` (provider `mock`) or `live` (provider `twilio`). `GET /sms/status` reports it; every message carries `is_simulated`.
- If the active provider row in the database does not match the running provider, sends fail with `503 sms_mode_mismatch`. Nothing is sent in another mode.
- `accepted` means the provider queued the message. `delivered` is set only by a provider delivery confirmation or status lookup. After 24 hours in `sent` the response carries `delivery.confirmation = "unconfirmed"`.
- A country with no capability row, or with outbound `unsupported`, is blocked in both modes. A route that is not verified (`requires_verification`) is blocked in **live** mode and allowed in **simulation** only, flagged `availability: "simulation_only"` with a warning. This is a deliberate refinement of FR-SMS-007 AC4, so demos can show a route without implying it works.

---

## GET /sms/status

Mode, provider and whether this user may send.

```json
{ "data": { "mode": "simulation", "provider": "mock", "is_simulated": true,
            "outbound_paused": false, "sender_verified": true,
            "notice": "Simulation mode: no real SMS is sent and nothing costs money." } }
```

`sender_verified` means a mobile number verified **in the current mode** (a number verified in simulation is not enough for live).

## GET /sms/countries

Current capability per country for the country selector: `availability` (`available`, `simulation_only`, `unavailable`), `unavailable_reason`, `replies` (`supported`, `unverified`, `unsupported`), `registered_sender_required`, `registered_sender_status`, `content_restrictions`, `consent_required`, `credits_per_segment` (null when pricing is not configured), `max_segments`, `verified`. Two-way is never described as universal.

## GET /sms/capability?country_code=PH | ?phone_number=%2B63...

One country, same shape. Exactly one parameter is required (422 otherwise). A country with no row returns `404 country_unsupported`.

## POST /sms/quote

Everything the compose screen shows. No side effects.

```json
{ "to": "0917 123 4567", "country_code": "PH", "body": "Kumusta?" }
```

Name the recipient with exactly one of `to` (E.164, or a local format together with `country_code`), `contact_id` (one of your SMS contacts) or `conversation_id` (one of your SMS conversations).

Response: `recipient` (masked), `mode`, `is_simulated`, `availability`, `replies`, `warnings[]`, `segment` (`encoding` `gsm7|ucs2`, `characters`, `units`, `segments`, `per_segment`, `remaining_in_segment`, `max_segments`, `too_long`), `cost` (`units`, `credits`, `source` `configured|demo_default|unavailable`, `estimated: true`), `consent` (`required`, `granted`, `notice_version`), `recipient_opted_out`, `blockers[]` (`code`, `message`) and `can_send`. Cost is an estimate until the provider accepts the message. In live mode a country without a configured price is blocked (`pricing_not_configured`); simulation uses a labelled demo rate. 1 credit = 100 units.

## PUT /sms/consents

Records (or withdraws) your attestation that you have permission to text a recipient. Body: a recipient field plus `decision: "granted" | "withdrawn"`. Consent is per recipient and is appended to `user_consents`. A recipient replying is not consent. Response: the `consent` object.

## POST /sms/messages

Queue an SMS. The handler never calls the provider.

**Headers:** `Idempotency-Key: <uuid>` (required, one per user action).  
**Body:** a recipient field, `body` (1 to 1600 characters), `confirmed: true` (the user reviewed recipient, text and cost; `false` or missing is 422).

**202** with the stored message in status `queued`. Repeating the same key with the same content returns **200** with the original message and sends nothing. The same key with different content returns `409 idempotency_conflict`.

Checks, in order (nothing is stored if one fails): verified sender number, provider mode and pause switch, valid destination (E.164, no premium or special numbers), country capability, message size, you have not blocked the number, the number has not opted out, sender consent, rate limits (per user per hour and per day, per recipient per hour, per IP), a free sender number for this recipient.

| Error | Status | Meaning |
|---|---|---|
| `sender_not_verified` | 403 | Verify your mobile number (in the current mode) |
| `invalid_phone`, `number_type_blocked` | 422 | Not a valid destination |
| `country_unsupported`, `number_type_unsupported` | 422 | No usable route |
| `route_unverified`, `sender_registration_required`, `pricing_not_configured` | 422 | Live only: route not ready |
| `message_too_long` | 422 | More segments than the destination allows (at most 10) |
| `user_blocked` | 403 | You blocked this number |
| `recipient_opted_out` | 422 | The recipient replied STOP; blocked for every user |
| `consent_required` | 422 | Record consent first |
| `rate_limited` | 429 | `Retry-After` header set |
| `sms_paused`, `sms_mode_mismatch`, `live_not_confirmed`, `sender_capacity` | 503 | Operational; see messages |

The message object: `id`, `conversation_id`, `seq`, `direction`, `body`, `status`, `status_version`, `is_simulated`, `segment_count`, `client_message_id`, `delivery` (`attempt_number`, `provider`, `accepted_at`, `sent_at`, `delivered_at`, `next_attempt_at`, `confirmation`), `failure` (`code`, `reason`, `is_permanent`, `may_have_been_delivered`), `can_retry`, `attempt_count`. Statuses: `queued`, `retrying`, `accepted`, `sent`, `delivered`, `undelivered`, `failed`, and `received` (inbound only). Provider error text is never returned; `failure.reason` is our own wording.

## POST /sms/messages/{id}/retry

Sends a failed or undelivered message again as a **new** message (new `Idempotency-Key` required, body `{ "confirmed": true }`). Every check runs again. `409 not_retryable` for messages that did not fail. When `failure.may_have_been_delivered` is true the outcome is unknown and the user is told so before resending.

## GET /sms/messages/{id}

The message plus `events[]`: every provider signal recorded for it (`status`, `source` `send_response|webhook|poll|simulation|system`, `applied`, timestamps). Signals that were ignored (out of order, duplicate, conflicting) are listed with `applied: false`.

## GET /sms/conversations, GET /sms/conversations/{id}/messages, POST /sms/conversations/{id}/read

Paginated conversation list (masked number, contact name if saved, last message, `unread_count`, `replies`), message history (`before_seq`, `limit`) and read marker (`{ "up_to_seq": n }`). Another user's conversation is `404`.

---

## Webhooks

`POST /api/v1/webhooks/twilio/inbound` and `/status` (live) and `/api/v1/webhooks/mock/inbound` and `/status` (simulation). Only the running provider's endpoints exist; the other answers `404`.

Order of work: size limit (64 KB) -> per-IP rate limit -> signature check over the raw bytes -> parse -> store the verified event once (duplicates are acknowledged and ignored) -> process -> 2xx. An invalid or missing signature is `403 invalid_signature`, audit-logged with a masked, body-free entry, with no side effects. There is no development bypass: simulation signs with HMAC-SHA256 (`X-Mock-Signature`, `X-Mock-Timestamp`, five-minute tolerance); Twilio uses `X-Twilio-Signature` over the URL built from `SMS_PUBLIC_BASE_URL`. A malformed signed payload is `400 malformed_webhook`. Processing failures after storage are retried by the worker and still answer 2xx.

- **Status callbacks** carry our delivery id in the callback URL (`?sms_id=`), so a callback that overtakes our own commit is still matched. Status only moves forward; the first terminal state wins; a late proof can correct an "unknown outcome" failure forward.
- **Inbound replies** are matched on (our sender number, the sender's number). They appear in the sender's existing conversation (`received`, `is_simulated` from the webhook). STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT (whole message only) record a persistent opt-out; START or UNSTOP lifts it. Replies from a number you blocked are stored hidden with no notification.
- **Unrouted replies** (no active route, expired route, unknown sender) are kept, never shown to users, never auto-answered, and listed for administrators.

---

## Administration (`/admin/sms`, admin role)

| Endpoint | Purpose |
|---|---|
| `GET /providers` | Providers without secrets: `credentials_configured` (boolean only), registration status, retry settings, masked sender numbers, live confirmation |
| `PATCH /providers/{id}` | Non-secret settings only (`max_retry_attempts`, `retry_base_seconds`, `retry_cap_seconds`, `retry_multiplier`, `sender_registration_status`, `sender_numbers`). Unknown fields, including anything credential-like, are rejected |
| `POST /providers/{id}/activate` | Body `{ "confirm_environment": "<APP_ENV>" }`. Only the provider the server was started with can be activated; live also needs `SMS_LIVE_CONFIRMED`. Records who confirmed it and for which environment |
| `PUT /outbound-paused` | `{ "paused": true }` stops all sending |
| `GET /capabilities`, `PUT /capabilities/{cc}` | Read current rules; publish a new immutable version. The database refuses `supported` without recorded verification, `supported` while a required sender is unregistered, and a Philippine row without a registration status |
| `GET /monitoring` | 24-hour counts, delivery and failure rates, queue depth, unrouted and failed callbacks, rejected signatures, opt-outs, pause state, recent failures (masked, no text) |
| `GET /inbound/unrouted` | Unmatched replies (masked, no text, retention date) |
| `POST /simulate/inbound` | Simulation only, never in production: injects a signed reply through the real webhook path. `replay_id` replays an event to test duplicates |

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
| 1.1 | November 2026 | Kiro | Matches the Phase 2 implementation: quote, consent, retry, admin, webhook behaviour |