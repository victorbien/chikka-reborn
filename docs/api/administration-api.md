# Administration API

**Document:** CHKR-API-008  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all administration and credit management endpoints. Every admin endpoint requires an active account whose `profiles.role` is `admin` in the database. The role is read from the database on each request. Role claims in the token, headers or query strings are ignored.

## Base Path

`/api/v1/admin`  
`/api/v1/credits`

---

## Credits Endpoints

### GET /credits/balance

Get the authenticated user's credit balance.  
**Auth:** Required  
**Phase:** 2  
**FR:** FR-CREDIT-001

**Response 200:**
```json
{
  "data": {
    "balance": 4.95,
    "reserved": 0.05,
    "available": 4.90,
    "currency": "USD",
    "updated_at": "2026-11-09T12:00:00Z"
  },
  "request_id": "..."
}
```

- `balance` — total credits including reserved
- `reserved` — credits held for pending SMS sends
- `available` — `balance - reserved` — what can actually be spent

---

### GET /credits/transactions

Get credit transaction history for the authenticated user.  
**Auth:** Required  
**Phase:** 2

**Query params:** `type` (filter by transaction type), `page`, `page_size`

**Response 200:**
```json
{
  "data": [
    {
      "id": "uuid",
      "type": "deduction",
      "amount": -0.05,
      "balance_after": 4.95,
      "description": "SMS to +63****1234 (1 segment)",
      "reference_type": "outbound_sms",
      "reference_id": "uuid",
      "created_at": "2026-11-09T12:00:00Z"
    },
    {
      "id": "uuid",
      "type": "refund",
      "amount": 0.05,
      "balance_after": 5.00,
      "description": "Refund: SMS permanently failed",
      "reference_type": "outbound_sms",
      "reference_id": "uuid",
      "created_at": "2026-11-09T11:00:00Z"
    }
  ],
  "pagination": { ... },
  "request_id": "..."
}
```

---

### POST /credits/topup

Initiate a credit top-up via payment gateway.  
**Auth:** Required  
**Phase:** 4 (payment gateway TBD — OD-001)  
**FR:** FR-CREDIT-004

**Request:**
```json
{
  "amount": 10.00,
  "currency": "USD",
  "payment_method_id": "payment-gateway-specific-id"
}
```

**Response 202:**
```json
{
  "data": {
    "topup_id": "uuid",
    "status": "pending",
    "amount": 10.00,
    "payment_url": "https://payment-gateway.example/pay/..."
  },
  "request_id": "..."
}
```

> **Note:** This endpoint structure is provisional pending payment gateway selection (OD-001).

---

## Admin Endpoints

Implemented in `backend/app/modules/admin`. All endpoints sit under `/api/v1/admin`, return the standard envelope with `request_id`, and answer `401` when anonymous and `403` when the caller is not an administrator. Each refusal is written to the audit log as `admin.access_denied` (category `security`, outcome `denied`) with the route template and no request data.

Nothing here returns message bodies, AI prompts or output, secrets, full phone numbers or full email addresses. Phone numbers are masked (`+63****1234`) and emails are shown as `m***@example.com`.

| Method and path | Purpose | FR |
|---|---|---|
| `GET /admin/dashboard` | Platform totals from live data | FR-ADMIN-001 |
| `GET /admin/users` | Search and list accounts (`q`, `status`, `role`, `page`, `page_size`) | FR-ADMIN-002 |
| `GET /admin/users/{id}` | Account details and activity overview | FR-ADMIN-002 |
| `POST /admin/users/{id}/restrict` | Suspend an account and end its sessions. Body: `{"reason_code": "abuse|spam|fraud|security|other"}` | FR-ADMIN-002 |
| `POST /admin/users/{id}/reinstate` | Lift a suspension | FR-ADMIN-002 |
| `GET /admin/sms/messages` | Outbound or inbound SMS (`direction`, `status`, `is_simulated`, `page`, `page_size`) | FR-ADMIN-004 |
| `GET /admin/sms/messages/{id}` | Delivery attempts, provider message IDs, failure reasons, retry history and status events | FR-ADMIN-004 |
| `GET /admin/providers/overview` | Provider health, mode, configuration status and country capabilities | FR-ADMIN-003 |
| `GET /admin/ai/metrics` | AI usage for `window_days` (1 to 90, default 30) | FR-ADMIN-006 |
| `GET /admin/audit-logs` | Audit trail (`category`, `action`, `outcome`, `actor_id`, `since`, `until`, `page`, `page_size`) | FR-ADMIN-012 |

Provider settings, capability editing, activation of live mode and the outbound pause switch live in `/admin/sms/*`. Credit adjustments live in `/admin/credits/*`. Notification announcements live in `/admin/notifications`. See `sms-api.md`, `credits-api.md` and `notifications-api.md`.

### GET /admin/dashboard

Counts come from SQL aggregates, not from caches or estimates.

- `users`: `total_registered` (not deleted), `active_accounts`, `pending_verification`, `suspended`, `administrators`, and `active_last_24h`, `active_last_7d`, `active_last_30d` (active accounts with `last_seen_at` inside the window).
- `conversations`: `total`, `chikka`, `sms`.
- `messages.chikka_messages_sent`: Chikka-to-Chikka messages.
- `sms.live` and `sms.simulated`: never added together. `sent` means handed to the provider (accepted, sent, delivered or undelivered), which is not delivery. `delivery_success_rate` is `delivered / (delivered + failed + undelivered)`, or `null` when nothing has settled.
- `ai`: request totals, failures and token counts.
- `credits`: per ledger (`demo` is the simulated ledger): entries, units granted, used, refunded and adjusted.

### Account restriction

- Only an active account with role `user` can be restricted. Restricting yourself or another administrator returns `409` (`cannot_restrict_self`, `cannot_restrict_administrator`). A non-active account returns `409 account_not_active`.
- Restriction sets `status = suspended`, deletes the account's sessions, and writes `admin.user_restricted` with `reason_code` and the number of sessions ended, in the same transaction.
- Reinstating a non-suspended account returns `409 account_not_suspended`.
- Refused attempts are audited as `admin.user_restrict_refused` or `admin.user_reinstate_refused` (outcome `denied`).
- Free-text reasons are not accepted, so personal data cannot enter the audit log through this route.

### Audit events written by this module

| Action | Category | When |
|---|---|---|
| `admin.access_denied` | security | A signed-in non-administrator calls an admin endpoint |
| `admin.user_viewed` | admin | An administrator opens account details |
| `admin.sms_message_viewed` | admin | An administrator opens a message's delivery attempts |
| `admin.user_restricted`, `admin.user_reinstated` | admin | Account status changes |
| `admin.user_restrict_refused`, `admin.user_reinstate_refused` | admin | A status change is refused |

Each row records actor, role, action, resource type and ID, outcome, request ID, coarse IP prefix and timestamp. `GET /admin/audit-logs` returns those fields and omits `metadata`.

### GET /admin/providers/overview

`health.health` is `healthy`, `degraded`, `paused` or `unavailable`, with plain-language `reasons`. It reports degraded when dispatch has stopped on a configuration error, the running provider differs from the active setting, fewer than half of at least five settled messages were delivered in 24 hours, provider callbacks failed, or callback signatures were rejected. `configuration` reports modes and whether credentials exist as booleans. Secret values and names are never returned.

### GET /admin/ai/metrics

Aggregates from `ai_assistance_logs`: totals, per-feature usage (requests, failures, results the user accepted or edited, average latency, tokens), error counts by outcome and code, and requests per day. `estimated_cost_usd` is `null` unless both `AI_COST_PER_1K_INPUT_USD` and `AI_COST_PER_1K_OUTPUT_USD` are configured.

### Not implemented

Re-authentication for sensitive actions (FR-ADMIN common rule), abuse report handling, feature flags, role promotion and account deletion from the admin area. These remain open work for Module J.

---
## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
