# Credits API

**Document:** CHKR-API-009  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Implemented (Module H, simulated credits)  
**Last Revised:** November 2026  

---

## Purpose

Simulated SMS credits for demonstration. They are not money: they cannot be bought, sold, withdrawn or converted, and the application has no payment system. Design: ADL-022 in [architecture-decisions.md](../architecture/architecture-decisions.md).

Base path `/api/v1`. Units are credits x 100 (150 units is 1.50 credits). Responses use the standard envelope.

## Ledgers

| Ledger | Used for | Starts with | Metered |
|---|---|---|---|
| `demo` | Simulated SMS (mock provider) | 5000 units (50 credits), `system_settings.demo_grant_units` | Yes |
| `live` | Real SMS (future, with payments) | 0 | No. Live sends are not charged or blocked by credits in this version |

The database refuses to charge a simulated message to the live ledger and the reverse. Real credit can therefore never be spent by a simulated send.

## How a message is charged

All steps are keyed on the message, not the delivery attempt, so retries never charge twice. Each ledger entry type exists at most once per message (unique index), and every step checks first, so repeated callbacks and worker passes change nothing.

| Moment | Ledger entry | Effect |
|---|---|---|
| Message queued | `reservation` | Holds the estimated cost. Refused with `402 insufficient_credits` if available credit (balance minus holds) is too low; the message is not created |
| Provider accepts it | `deduction` | The hold becomes spend |
| Permanently fails before acceptance (retries exhausted, queue expiry) | `reservation_release` | The hold is returned |
| Fails or is undelivered after acceptance | `refund` | The spend is returned |
| Administrator adjusts | `adjustment` | Adds or removes credits with an actor and reason |

A repeated send with the same `Idempotency-Key` returns the original message and charges nothing more. Balances are never written directly: a database trigger applies each append-only entry, so the balance always equals the sum of the ledger and cannot drop below what is held.

Low balance: when available credit falls to the user's threshold (`low_balance_threshold_units`, default 500, set in notification settings) one `low_balance` notification is raised. It is raised again only after the balance has risen above the threshold and dropped again.

## GET /credits

Your balances.

```json
{ "data": {
  "ledgers": [
    { "ledger": "demo", "balance_units": 4900, "reserved_units": 100, "available_units": 4800,
      "available_credits": 48.0, "charges_apply": true },
    { "ledger": "live", "balance_units": 0, "reserved_units": 0, "available_units": 0,
      "available_credits": 0.0, "charges_apply": false } ],
  "active_ledger": "demo", "is_simulated": true,
  "low_balance_threshold_units": 500, "is_low": false,
  "notice": "These are simulated credits for demonstration. They are not money..." } }
```

## GET /credits/transactions

Your ledger, newest first. Query: `page`, `page_size` (1-100), `ledger` (`demo` or `live`). Paginated.

Each entry has `entry_type` (`grant`, `reservation`, `reservation_release`, `deduction`, `refund`, `adjustment`, `top_up`), a plain-language `description`, `balance_delta`, `reserved_delta`, `credits_delta`, `balance_after`, and for sends `message_id`, `provider`, `country_code`, `segment_count`. `reason` is set for adjustments and grants.

## SMS quote

`POST /sms/quote` (see [sms-api.md](sms-api.md)) includes the cost preview:

```json
"cost": { "units": 100, "credits": 1.0, "source": "demo_default", "estimated": true },
"balance": { "ledger": "demo", "is_simulated": true, "available_units": 5000,
  "available_credits": 50.0, "sufficient": true, "charges_apply": true, "is_low": false }
```

When the cost exceeds available credit, `can_send` is `false` and `blockers` contains `insufficient_credits` with the amounts in the message. `POST /sms/messages` then answers `402 insufficient_credits`.

## Administration

All admin endpoints need an administrator with a verified email (`403` otherwise, `401` when signed out).

### POST /admin/credits/adjustments

Header `Idempotency-Key` (UUID, required). Body:

```json
{ "user_id": "uuid", "amount_units": 2500, "reason": "Hackathon demo top-up", "ledger": "demo" }
```

- `amount_units`: non-zero, -1,000,000 to 1,000,000. Negative removes credits.
- `reason`: 3-300 characters. Visible to the user in their history.
- `ledger`: only `demo`. `live` answers `422 ledger_not_adjustable`.
- A removal that would take the balance below zero or below what is held for queued messages answers `422 adjustment_exceeds_balance`.
- The same key with the same content returns the original entry (`replayed: true`). The same key with different content answers `409 idempotency_conflict`.
- Recorded in the audit log (`credit.adjusted`, actor, target, amount; never the reason text) and the user receives a `system` notification.

Returns `{ transaction, balance, replayed }`.

### GET /admin/credits/users/{user_id}

A user's balances (same shape as `GET /credits`).

### GET /admin/credits/users/{user_id}/transactions

A user's ledger, paginated.

## Errors

| Status | Code | When |
|---|---|---|
| 402 | `insufficient_credits` | Not enough available credit to send |
| 409 | `idempotency_conflict` | Adjustment key reused with different content |
| 422 | `ledger_not_adjustable`, `adjustment_exceeds_balance`, `validation_error` | See above |
| 404 | `not_found` | Unknown or inactive user (admin endpoints) |

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro | Initial version |
