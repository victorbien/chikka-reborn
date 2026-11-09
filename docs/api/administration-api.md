# Administration API

**Document:** CHKR-API-008  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all administration and credit management endpoints. All admin endpoints require `role = 'admin'` in the JWT claims.

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

All endpoints below require `role = 'admin'`.

### GET /admin/stats

Get platform-wide statistics.  
**Auth:** Required (admin)  
**Phase:** 2  
**FR:** FR-ADMIN-001

**Query params:** `period` — `24h` | `7d` | `30d` (default: `24h`)

**Response 200:**
```json
{
  "data": {
    "period": "24h",
    "total_users": 1250,
    "active_users": 87,
    "chikka_messages_sent": 3420,
    "sms_sent": 156,
    "sms_delivered": 149,
    "sms_failed": 7,
    "sms_delivery_rate": 0.955,
    "ai_requests": 89,
    "credits_consumed": 7.80,
    "sms_mode": "mock",
    "generated_at": "2026-11-09T12:00:00Z"
  },
  "request_id": "..."
}
```

---

### GET /admin/users

Get paginated user list.  
**Auth:** Required (admin)  
**Phase:** 2  
**FR:** FR-ADMIN-002

**Query params:** `q` (search email/username), `status` (`active` | `suspended`), `page`, `page_size`

**Response 200:**
```json
{
  "data": [
    {
      "id": "uuid",
      "email": "marites@example.com",
      "display_name": "Marites Santos",
      "role": "user",
      "is_active": true,
      "phone_verified": true,
      "email_verified": true,
      "created_at": "2026-11-01T00:00:00Z",
      "last_seen_at": "2026-11-09T11:55:00Z"
    }
  ],
  "pagination": { ... },
  "request_id": "..."
}
```

---

### PATCH /admin/users/:userId

Update a user's status or role.  
**Auth:** Required (admin)  
**Phase:** 2  
**FR:** FR-ADMIN-002

**Request:**
```json
{
  "is_active": false,
  "suspension_reason": "Reported for abusive messages."
}
```

Valid operations: suspend (`is_active: false`), reinstate (`is_active: true`), promote to admin (`role: "admin"`).

Admin cannot modify their own account via this endpoint.

**Response 200:** Updated user object.  
All admin actions are logged: admin_id, target_user_id, action, reason, timestamp.

---

### DELETE /admin/users/:userId

Permanently delete a user account.  
**Auth:** Required (admin)  
**Phase:** 2

**Response 202:** Deletion scheduled (same 30-day erasure policy as self-deletion).

---

### GET /admin/sms-logs

Get SMS audit log.  
**Auth:** Required (admin)  
**Phase:** 2  
**FR:** FR-ADMIN-004

**Query params:** `from_date`, `to_date`, `status`, `user_id`, `is_simulated`, `page`, `page_size`

**Response 200:**
```json
{
  "data": [
    {
      "id": "uuid",
      "sender_user_id": "uuid",
      "sender_email": "marites@example.com",
      "recipient_phone": "+63****1234",
      "status": "delivered",
      "is_simulated": true,
      "provider": "mock",
      "segment_count": 1,
      "credit_cost": 0.05,
      "created_at": "2026-11-09T12:00:00Z"
    }
  ],
  "pagination": { ... },
  "request_id": "..."
}
```

Log is read-only from the admin UI. Phone numbers are always masked.

---

### GET /admin/config

Get current platform configuration.  
**Auth:** Required (admin)  
**Phase:** 2  
**FR:** FR-ADMIN-003

**Response 200:**
```json
{
  "data": {
    "sms_provider_mode": "mock",
    "feature_flags": {
      "ai_enabled": false,
      "push_notifications_enabled": false,
      "classic_mode_enabled": false
    }
  },
  "request_id": "..."
}
```

---

### PATCH /admin/config

Update platform configuration.  
**Auth:** Required (admin + re-authentication for SMS mode change)  
**Phase:** 2  
**FR:** FR-ADMIN-003

**Request:**
```json
{
  "sms_provider_mode": "live",
  "reauth_token": "supabase-reauth-token"
}
```

Switching `sms_provider_mode` to `live` requires `reauth_token` — a fresh token obtained by re-authenticating the admin user. Without it, the request is rejected with `403`.

**Response 200:** Updated config object.  
Change is logged: admin_id, previous_mode, new_mode, timestamp.

---

### GET /admin/countries

List all country capability configurations.  
**Auth:** Required (admin)  
**Phase:** 2  
**FR:** FR-ADMIN-005

**Response 200:** Array of country capability objects.

---

### PUT /admin/countries/:countryCode

Update a country's SMS capability configuration.  
**Auth:** Required (admin)  
**Phase:** 2  
**FR:** FR-ADMIN-005

**Request:**
```json
{
  "outbound_enabled": true,
  "inbound_enabled": false,
  "alphanumeric_sender_id": false,
  "requires_registered_sender": true,
  "credit_cost_per_segment": 0.05,
  "notes": "Sender ID registration required. Inbound pending carrier verification."
}
```

**Response 200:** Updated country capability object. Changes take effect immediately.

---

### GET /admin/ai-metrics

Get AI usage metrics.  
**Auth:** Required (admin)  
**Phase:** 3  
**FR:** FR-ADMIN-006

**Query params:** `period` — `24h` | `7d` | `30d`

**Response 200:**
```json
{
  "data": {
    "period": "7d",
    "total_requests": 312,
    "by_feature": {
      "suggest_replies": 145,
      "translate": 87,
      "rewrite": 52,
      "optimise_sms": 18,
      "summarise": 10
    },
    "total_input_tokens": 125400,
    "total_output_tokens": 28700,
    "avg_latency_ms": 1340,
    "p95_latency_ms": 3890,
    "failure_rate": 0.032
  },
  "request_id": "..."
}
```

---

### GET /admin/credits

Get platform-wide credit transaction overview.  
**Auth:** Required (admin)  
**Phase:** 4

**Query params:** `from_date`, `to_date`, `user_id`, `type`, `page`, `page_size`

**Response 200:** Paginated credit transaction list (all users, not just self).

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
