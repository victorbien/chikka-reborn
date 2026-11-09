# API Design

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  

---

## 1. API Design Principles

- All API routes are versioned under `/api/v1/`.
- HTTP methods are used semantically: GET reads, POST creates, PUT replaces, PATCH updates, DELETE removes.
- All responses include a `request_id` UUID for traceability.
- Successful responses use appropriate 2xx status codes.
- Error responses use a consistent structure (see Section 3).
- All list endpoints are paginated.
- Request bodies use JSON. Responses are JSON.
- All authenticated routes require a valid `Authorization: Bearer <supabase-jwt>` header.
- Rate limiting is applied per-endpoint as defined in `docs/nfrs.md`.

---

## 2. Base URL

| Environment | Base URL |
|---|---|
| Development | `http://localhost:8000/api/v1` |
| Staging | `https://api-staging.chikka-reborn.app/api/v1` |
| Production | `https://api.chikka-reborn.app/api/v1` |

---

## 3. Standard Response Structures

### Success Response

```json
{
  "data": { ... },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Paginated List Response

```json
{
  "data": [ ... ],
  "pagination": {
    "total": 120,
    "page": 1,
    "page_size": 20,
    "has_next": true,
    "has_prev": false
  },
  "request_id": "..."
}
```

### Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Phone number is not in a valid E.164 format.",
    "details": {
      "field": "to",
      "value": "09171234567"
    }
  },
  "request_id": "..."
}
```

### Standard Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or invalid authentication token |
| `FORBIDDEN` | 403 | Authenticated but not authorised for this action |
| `NOT_FOUND` | 404 | Resource does not exist |
| `VALIDATION_ERROR` | 422 | Request body or parameters failed validation |
| `INSUFFICIENT_CREDITS` | 422 | Not enough credits to perform the action |
| `SMS_COUNTRY_UNSUPPORTED` | 422 | Destination country does not support SMS |
| `PHONE_OPTED_OUT` | 422 | Recipient has opted out of SMS |
| `RATE_LIMITED` | 429 | Too many requests |
| `PROVIDER_ERROR` | 502 | External provider (SMS/AI) returned an error |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## 4. Authentication Endpoints

### `POST /auth/register`
Register a new user with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass1",
  "display_name": "Maria Santos"
}
```

**Response 201:**
```json
{
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "display_name": "Maria Santos",
    "email_verified": false
  },
  "request_id": "..."
}
```

---

### `POST /auth/login`
Authenticate with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass1"
}
```

**Response 200:**
```json
{
  "data": {
    "access_token": "...",
    "refresh_token": "...",
    "token_type": "bearer",
    "expires_in": 3600
  },
  "request_id": "..."
}
```

---

### `POST /auth/logout`
Invalidate the current session. **Auth required.**

**Response 204:** No content.

---

### `POST /auth/refresh`
Exchange a refresh token for a new access token.

**Request:**
```json
{ "refresh_token": "..." }
```

---

### `POST /auth/reset-password`
Request a password reset email.

**Request:**
```json
{ "email": "user@example.com" }
```

**Response 200:** Always returns success (prevents email enumeration).

---

### `POST /auth/verify-phone`
Send an OTP to the user's phone number. **Auth required.**

**Request:**
```json
{ "phone_number": "+639171234567" }
```

---

### `POST /auth/verify-phone/confirm`
Confirm the OTP for phone verification. **Auth required.**

**Request:**
```json
{ "otp": "123456" }
```

---

## 5. User / Profile Endpoints

### `GET /users/me`
Get the current user's profile. **Auth required.**

**Response 200:**
```json
{
  "data": {
    "id": "uuid",
    "username": "mariasantos",
    "display_name": "Maria Santos",
    "bio": "Hello!",
    "avatar_url": "https://...",
    "country_code": "PH",
    "phone_number": "+639171234567",
    "phone_verified": true,
    "role": "user",
    "ui_mode": "modern",
    "created_at": "2026-11-09T00:00:00Z"
  },
  "request_id": "..."
}
```

---

### `PATCH /users/me`
Update the current user's profile. **Auth required.**

**Request (any subset of updatable fields):**
```json
{
  "display_name": "Maria C. Santos",
  "bio": "Messaging enthusiast.",
  "country_code": "PH",
  "ui_mode": "classic"
}
```

---

### `DELETE /users/me`
Delete the current user's account. **Auth required.** Requires `confirm_password`.

**Request:**
```json
{ "confirm_password": "SecurePass1" }
```

**Response 202:** Deletion scheduled.

---

### `GET /users/search`
Search for Chikka users. **Auth required.**

**Query params:** `q` (string, min 2 chars), `page`, `page_size`

**Response 200:** Paginated list of matching public profiles.

---

## 6. Contact Endpoints

### `GET /contacts`
Get the current user's contact list. **Auth required.**

**Query params:** `type` (`chikka` | `sms` | `all`), `status` (`active` | `blocked`), `page`, `page_size`

---

### `POST /contacts`
Add a new contact. **Auth required.**

**Request (Chikka contact):**
```json
{
  "contact_type": "chikka",
  "chikka_user_id": "uuid"
}
```

**Request (SMS contact):**
```json
{
  "contact_type": "sms",
  "phone_number": "+639171234567",
  "display_name": "Lola Nena"
}
```

**Response 201:** Created contact record.

---

### `PATCH /contacts/{contact_id}`
Update a contact (e.g. display name, status). **Auth required.**

---

### `DELETE /contacts/{contact_id}`
Remove a contact. **Auth required.**

---

## 7. Conversation Endpoints

### `GET /conversations`
Get the current user's conversations. **Auth required.**

**Query params:** `page`, `page_size`

**Response 200:** Paginated list with last message preview per conversation.

---

### `POST /conversations`
Start a new conversation. **Auth required.**

**Request:**
```json
{
  "participant_user_id": "uuid"
}
```

**Response 201:** Conversation object, or returns existing conversation if one exists.

---

### `GET /conversations/{conversation_id}`
Get a conversation's details. **Auth required.** Caller must be a participant.

---

### `GET /conversations/{conversation_id}/messages`
Get paginated messages in a conversation. **Auth required.**

**Query params:** `before` (cursor: message `created_at` ISO timestamp), `limit` (default 50, max 100)

---

### `POST /conversations/{conversation_id}/messages`
Send a Chikka message in a conversation. **Auth required.**

**Request:**
```json
{
  "body": "Hello! How are you?",
  "is_ai_assisted": false
}
```

**Response 201:**
```json
{
  "data": {
    "id": "uuid",
    "conversation_id": "uuid",
    "sender_user_id": "uuid",
    "body": "Hello! How are you?",
    "origin": "chikka",
    "status": "sent",
    "is_ai_assisted": false,
    "created_at": "2026-11-09T12:00:00Z"
  },
  "request_id": "..."
}
```

---

### `DELETE /conversations/{conversation_id}/messages/{message_id}`
Delete a message. **Auth required.** Sender only.

**Query params:** `scope` (`me` | `everyone`)

---

## 8. SMS Endpoints

### `GET /sms/capability`
Check SMS capability for a destination. **Auth required.**

**Query params:** `phone_number` (E.164) or `country_code` (ISO 3166-1 alpha-2)

**Response 200:**
```json
{
  "data": {
    "country_code": "PH",
    "country_name": "Philippines",
    "outbound_enabled": true,
    "inbound_enabled": false,
    "credit_cost_per_segment": 0.05,
    "requires_registered_sender": true,
    "notes": "Sender ID registration required for A2P messaging."
  },
  "request_id": "..."
}
```

---

### `POST /sms/send`
Send an SMS to a phone number. **Auth required.**

**Request:**
```json
{
  "to": "+639171234567",
  "body": "Kumusta ka? Miss na kita!",
  "idempotency_key": "client-generated-uuid",
  "conversation_id": "uuid (optional)"
}
```

**Response 202:**
```json
{
  "data": {
    "message_id": "uuid",
    "status": "accepted",
    "is_simulated": true,
    "segment_count": 1,
    "credit_cost": 0.05,
    "credit_balance_after": 4.95
  },
  "request_id": "..."
}
```

---

### `GET /sms/outbound`
Get the current user's outbound SMS history. **Auth required.**

**Query params:** `status`, `page`, `page_size`

---

### `GET /sms/outbound/{message_id}`
Get details of a specific outbound SMS. **Auth required.**

---

## 9. Webhook Endpoints

These endpoints are called by the SMS provider, not by authenticated users. They use provider-specific signature validation instead of JWT auth.

### `POST /webhooks/sms/status`
Receive delivery status callbacks from the SMS provider.

**Headers:** `X-Twilio-Signature` (or provider equivalent)

**Request body:** Provider-specific webhook payload (URL-encoded or JSON per provider).

**Response 200:** `{ "received": true }` — always respond 200 quickly to avoid provider retries.

---

### `POST /webhooks/sms/inbound`
Receive inbound SMS messages from the provider.

**Headers:** `X-Twilio-Signature` (or provider equivalent)

**Response 200:** TwiML or provider-expected response format.

---

## 10. AI Assistant Endpoints

All AI endpoints are **Auth required**. All return suggestions only — they do not send messages.

### `POST /ai/suggest-replies`
Generate smart reply suggestions.

**Request:**
```json
{
  "conversation_id": "uuid",
  "context_message_count": 10,
  "count": 3
}
```

**Response 200:**
```json
{
  "data": {
    "suggestions": [
      "Salamat! Ikaw din!",
      "Maayos naman, salamat. Ikaw?",
      "Okay lang! Kumusta ka rin?"
    ],
    "model_id": "anthropic.claude-3-haiku-...",
    "latency_ms": 1240
  },
  "request_id": "..."
}
```

---

### `POST /ai/translate`
Translate a message.

**Request:**
```json
{
  "text": "Kumusta ka?",
  "target_language": "en",
  "source_language": "tl"
}
```

**Response 200:**
```json
{
  "data": {
    "translated_text": "How are you?",
    "source_language": "tl",
    "target_language": "en"
  },
  "request_id": "..."
}
```

---

### `POST /ai/rewrite`
Rewrite a message draft.

**Request:**
```json
{
  "text": "hey wanna meet up tmrw",
  "instruction": "make_formal"
}
```

**Valid instructions:** `improve_clarity`, `fix_grammar`, `make_formal`, `make_casual`

**Response 200:**
```json
{
  "data": {
    "rewritten_text": "Hi, would you be available to meet tomorrow?"
  },
  "request_id": "..."
}
```

---

### `POST /ai/optimise-sms`
Shorten a message for SMS.

**Request:**
```json
{
  "text": "I just wanted to let you know that the meeting has been rescheduled to next Thursday at 3pm instead of the originally planned time.",
  "max_segments": 1,
  "encoding": "gsm7"
}
```

**Response 200:**
```json
{
  "data": {
    "optimised_text": "Meeting rescheduled: next Thu 3pm.",
    "original_length": 134,
    "optimised_length": 34,
    "segment_count": 1,
    "meaning_preserved": true
  },
  "request_id": "..."
}
```

---

### `POST /ai/summarise`
Summarise a conversation.

**Request:**
```json
{
  "conversation_id": "uuid",
  "message_count": 20
}
```

**Response 200:**
```json
{
  "data": {
    "summary": "Maria and Jose discussed plans for the weekend, agreeing to meet on Saturday at 3pm."
  },
  "request_id": "..."
}
```

---

## 11. Credits Endpoints

### `GET /credits/balance`
Get the current user's credit balance. **Auth required.**

**Response 200:**
```json
{
  "data": {
    "balance": 4.95,
    "reserved": 0.05,
    "available": 4.90,
    "currency": "USD"
  },
  "request_id": "..."
}
```

---

### `GET /credits/transactions`
Get credit transaction history. **Auth required.**

**Query params:** `page`, `page_size`, `type`

---

## 12. Notification Endpoints

### `GET /notifications`
Get the current user's notifications. **Auth required.**

**Query params:** `is_read` (bool), `page`, `page_size`

---

### `PATCH /notifications/{notification_id}`
Mark a notification as read. **Auth required.**

---

### `POST /notifications/mark-all-read`
Mark all notifications as read. **Auth required.**

---

## 13. Admin Endpoints

All admin endpoints require `role = 'admin'` in the JWT. **Auth required.**

### `GET /admin/stats`
Platform statistics summary.

### `GET /admin/users`
Paginated user list with search and filter.

### `PATCH /admin/users/{user_id}`
Suspend, reinstate, or update a user's role.

### `GET /admin/sms-logs`
Paginated SMS audit log with search and filter.

### `GET /admin/ai-metrics`
AI usage metrics: feature usage counts, token totals, latency percentiles.

### `GET /admin/country-capabilities`
List all country capability configurations.

### `PUT /admin/country-capabilities/{country_code}`
Update a country's SMS capability configuration.

### `GET /admin/config`
Get current platform configuration (SMS mode, feature flags).

### `PATCH /admin/config`
Update platform configuration. Switching SMS mode to live requires re-authentication confirmation.

---

## 14. Health Endpoint

### `GET /health`
No authentication required.

**Response 200:**
```json
{
  "status": "healthy",
  "database": "connected",
  "sms_provider": "mock",
  "sms_provider_status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-11-09T12:00:00Z"
}
```

---

## 15. OpenAPI Specification

The FastAPI application auto-generates an OpenAPI 3.1 specification at:
- `/docs` — Swagger UI (disabled in production)
- `/redoc` — ReDoc UI (disabled in production)
- `/openapi.json` — Raw specification (available in all environments)

---

## 16. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
