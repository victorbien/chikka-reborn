---
inclusion: always
---

# SMS Provider Guidelines

Concise implementation checklist. Full rules, interface contract, and credit/segmentation/logging policy: `sms-guidelines.md`. Detailed docs: `docs/architecture/sms-gateway-architecture.md`, `docs/api/sms-api.md`.

## Provider Abstraction

- All providers implement `SmsProvider` (`send_message`, `get_message_status`, `handle_inbound_webhook`, `validate_webhook_signature`).
- Route handlers and services never import vendor SDKs; they use the interface via dependency injection.

## Simulation vs Live Modes

- `MockSmsProvider` (simulation): nothing is sent, zero cost, no credit deduction, every message stored as simulated and labelled "SIMULATED" in the UI.
- `TwilioSmsProvider` (live): real sends; requires explicit operator confirmation per environment.
- Mode is explicit configuration. If live fails to initialise, fail loudly; never fall back to simulation silently.
- Stored messages record their mode so simulated data is never counted or presented as real.

## Message Status Semantics

`queued` (stored locally) -> `accepted` (provider queued it) -> `sent` (handed to carrier) -> `delivered` (provider confirms handset delivery) | `failed` | `undelivered`.

- Provider acceptance is never "delivered". Only a delivery callback or status lookup sets `delivered`.
- Record every status event with provider message ID (e.g. Twilio SID) and timestamp. Statuses do not regress.
- If delivery receipts are unavailable for a route, show "sent" and say delivery is unconfirmed.

## Webhook Validation

- Validate the signature on raw bytes before parsing or processing. Reject invalid requests. No development bypass.
- Deduplicate events by provider event/message ID.

## Idempotency

- Every outbound send carries an idempotency key enforced by a unique constraint. Retries reuse the key and are not double-charged.
- Retry transient failures only, with exponential backoff and jitter and a configurable maximum.

## Consent and Opt-Out

- Require recorded user consent before messaging a recipient. Process STOP-style keywords and equivalents immediately and persistently.
- Block sends to opted-out numbers and tell the sender why.

## Country Capability Checks

- Check the country capability configuration before sending: outbound support, two-way support, alphanumeric sender ID, sender registration, content restrictions.
- Philippines: sender ID registration required for A2P, two-way depends on carrier/route, no unsolicited promotions, no grey routes in production.
- Never claim free or universal two-way SMS.

## Prohibited

- Hard-coded provider credentials, or credentials in frontend code.
- False delivery confirmations, or simulated delivery presented as real.
- Sending AI-generated content without explicit user approval.
- Real SMS to real numbers during development or tests without explicit human approval.
