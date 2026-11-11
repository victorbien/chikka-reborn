# API Overview

**Document:** CHKR-API-001  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document is the entry point for the Chikka Reborn API documentation. It defines the global conventions, authentication model, request/response structure, error handling, versioning, and rate limiting that apply to every endpoint across all API modules.

## Scope

All REST API endpoints at `/api/v1/*`. Webhook endpoints at `/api/v1/webhooks/*`. WebSocket considerations are covered in `docs/architecture/frontend-architecture.md`.

---

## 1. Base URLs

| Environment | Base URL |
|---|---|
| Development | `http://localhost:8000/api/v1` |
| Staging | `https://api-staging.chikka-reborn.app/api/v1` |
| Production | `https://api.chikka-reborn.app/api/v1` |

---

## 2. Authentication

All endpoints except `/health` and `/webhooks/*` require a valid Supabase JWT.

**Header format:**
```
Authorization: Bearer <supabase_access_token>
```

Tokens are issued by Supabase Auth on login. The FastAPI backend validates the token signature using `SUPABASE_JWT_SECRET`. Expired tokens return `HTTP 401`.

Admin endpoints additionally require `role = 'admin'` in the JWT claims. Missing role returns `HTTP 403`.

Webhook endpoints use provider-specific signature validation (not JWT). See `docs/api/sms-api.md` for webhook authentication details.

---

## 3. Request Format

- Content-Type: `application/json`
- All request bodies are validated with Pydantic v2 models.
- Query parameters are validated with FastAPI's type system.
- Phone numbers must be in **E.164 format** (e.g. `+639171234567`).
- Timestamps use **ISO 8601 UTC** (e.g. `2026-11-09T12:00:00Z`).
- UUIDs use lowercase hyphenated format.

---

## 4. Response Format

### Success Response
```json
{
  "data": { },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Paginated List Response
```json
{
  "data": [ ],
  "pagination": {
    "total": 120,
    "page": 1,
    "page_size": 20,
    "has_next": true,
    "has_prev": false
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Every response includes `request_id` — a UUID assigned per request by the middleware. Use this for support and debugging.

---

## 5. Error Response Format

All errors use a consistent structure regardless of the error source:

```json
{
  "error": {
    "code": "INSUFFICIENT_CREDITS",
    "message": "You do not have enough credits to send this message.",
    "details": {
      "required": 2,
      "available": 1
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Standard Error Codes

| Code | HTTP | Description |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `FORBIDDEN` | 403 | Authenticated but not authorised |
| `NOT_FOUND` | 404 | Resource does not exist |
| `VALIDATION_ERROR` | 422 | Request body/params failed validation |
| `INSUFFICIENT_CREDITS` | 422 | Not enough credits for the operation |
| `SMS_COUNTRY_UNSUPPORTED` | 422 | Destination country not supported for SMS |
| `PHONE_NOT_VERIFIED` | 422 | User's phone number is not verified |
| `PHONE_OPTED_OUT` | 422 | Recipient has opted out of SMS |
| `DUPLICATE_IDEMPOTENCY_KEY` | 409 | Request already processed (returns original) |
| `WEBHOOK_SIGNATURE_INVALID` | 403 | Webhook signature validation failed |
| `RATE_LIMITED` | 429 | Too many requests |
| `PROVIDER_ERROR` | 502 | External SMS or AI provider error |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## 6. HTTP Status Codes

| Status | Usage |
|---|---|
| 200 | Successful GET / PATCH |
| 201 | Successful POST (resource created) |
| 202 | Accepted — async processing started (SMS send) |
| 204 | Successful DELETE (no body) |
| 400 | Bad request — malformed JSON |
| 401 | Unauthenticated |
| 403 | Forbidden |
| 404 | Not found |
| 409 | Conflict (duplicate idempotency key) |
| 422 | Validation error or business rule violation |
| 429 | Rate limited |
| 500 | Internal server error |
| 502 | Provider (SMS / AI) error |

---

## 7. Pagination

All list endpoints support pagination via query parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | integer | 1 | Page number (1-indexed) |
| `page_size` | integer | 20 | Items per page (max: 100) |

Cursor-based pagination is used for real-time message history:

| Parameter | Type | Description |
|---|---|---|
| `before` | ISO timestamp | Load messages created before this timestamp |
| `limit` | integer (default 50, max 100) | Number of messages to return |

---

## 8. Rate Limits

| Endpoint Group | Limit | Window | Scope |
|---|---|---|---|
| `POST /auth/login` | 5 requests | 15 minutes | Per IP |
| `POST /auth/reset-password` | 3 requests | 1 hour | Per IP |
| `POST /auth/verify-phone` | 3 requests | 30 minutes | Per account |
| `POST /sms/send` | Configurable | Per day | Per user |
| `POST /ai/*` | Configurable | Per hour | Per user |
| All other endpoints | 300 requests | 1 minute | Per user |

Rate limit response includes headers:
```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1731153600
```

---

## 9. Idempotency

SMS send operations require a client-generated idempotency key:

```json
{ "idempotency_key": "client-uuid-here" }
```

If the same key is submitted twice:
- Returns `HTTP 409` with the original response body.
- No duplicate operation is performed.
- No duplicate credit deduction occurs.

Generate a fresh UUID per send attempt. Reuse the same UUID only when retrying a genuinely failed request.

---

## 10. OpenAPI Specification

The FastAPI application auto-generates an OpenAPI 3.1 specification:

| URL | Environment | Access |
|---|---|---|
| `/docs` | Dev / Staging | Swagger UI |
| `/redoc` | Dev / Staging | ReDoc UI |
| `/openapi.json` | All | Raw JSON spec |

The Swagger UI and ReDoc are disabled in production for security. The raw spec is available in all environments.

---

## 11. API Module Index

| Module | Document | Base Path |
|---|---|---|
| Authentication | `docs/api/authentication-api.md` | `/api/v1/auth` |
| Contacts | `docs/api/contacts-api.md` | `/api/v1/contacts`, `/api/v1/users` |
| Messaging | `docs/api/messaging-api.md` | `/api/v1/conversations`, `/api/v1/messages` |
| SMS | `docs/api/sms-api.md` | `/api/v1/sms`, `/api/v1/webhooks/sms` |
| AI Assistant | `docs/api/ai-api.md` | `/api/v1/ai` |
| Notifications | `docs/api/notifications-api.md` | `/api/v1/notifications` |
| Administration | `docs/api/administration-api.md` | `/api/v1/admin`, `/api/v1/credits` |
| Health | This document | `/api/v1/health`, `/healthz`, `/readyz` |

---

## 12. Health Endpoints

| Path | Purpose |
|---|---|
| `GET /api/v1/health` | Liveness plus configuration summary. Always 200 while the process is up. |
| `GET /api/v1/health/ready` | Readiness. 503 when a configured dependency (the database) is unavailable. |
| `GET /healthz`, `GET /readyz` | Unversioned aliases of the two above, for hosting-platform checks. |

No authentication required. Used by load balancers, monitoring and the frontend status card.

**Response 200:**
```json
{
  "status": "ok",
  "service": "chikka-reborn-api",
  "version": "0.1.0",
  "environment": "staging",
  "sms_mode": "simulation",
  "database": "ok",
  "request_id": "8b39e0a6d8c5499193a646b9737afdd0"
}
```

`status` is `ok` or `degraded`. `database` is `ok`, `unavailable` or `not_configured`. `sms_mode` is `simulation` (mock provider) or `live`. The readiness route returns the same body with HTTP 503 when `status` is `degraded`.

> Deployment and monitoring documents that still say `GET /health` returning `healthy`/`unhealthy` should be read as `/healthz` and `/readyz` with the shape above.

---
## 13. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
