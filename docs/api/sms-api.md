# SMS API

**Document:** CHKR-API-005  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Documents all SMS-related endpoints: outbound SMS sending, country capability checking, delivery status, and the inbound webhook endpoints for SMS providers.

## Base Path

`/api/v1/sms`  
`/api/v1/webhooks/sms`

---

## GET /sms/capability

Check SMS capability for a destination country or phone number.  
**Auth:** Required  
**Phase:** 2  
**FR:** FR-SMS-001, FR-SMS-003

**Query params (one required):**
- `phone_number` — E.164 phone number (e.g. `+639171234567`)
- `country_code` — ISO 3166-1 alpha-2 (e.g. `PH`)

**Response 200:**
```json
{
  "data": {
    "country_code": "PH",
    "country_name": "Philippines",
    "outbound_enabled": true,
    "inbound_enabled": false,
    "inbound_requires_verification": true,
    "alphanumeric_sender_id": false,
    "requires_registered_sender": true,
    "credit_cost_per_segment": 0.05,
    "notes": "Sender ID registration required for A2P messaging in the Philippines. Inbound SMS availability requires carrier verification — see RISK-001."
  },
  "request_id": "..."
}
```

> **⚠ Provider Verification Required:** The `inbound_enabled` field for Philippines and other markets reflects current capability knowledge only. Actual two-way SMS availability is subject to Twilio carrier routing agreements. Do not display inbound as guaranteed until confirmed with the provider.

**Errors:**
- `422 VALIDATION_ERROR` — invalid phone number format or country code

---

## POST /sms/send

Send an SMS message to a phone number.  
**Auth:** Required (phone number must be verified — FR-AUTH-008)  
**Phase:** 2  
**FR:** FR-SMS-001 through FR-SMS-005

**Request:**
```json
{
  "to": "+639171234567",
  "body": "Kumusta ka, Nanay? Nagpadala na ako ng pera.",
  "idempotency_key": "client-generated-uuid-v4",
  "conversation_id": "uuid-optional"
}
```

Fields:
- `to` (required) — E.164 phone number
- `body` (required) — message text (max 1600 chars)
- `idempotency_key` (required) — UUID v4, unique per send attempt
- `conversation_id` (optional) — links the SMS to an existing conversation thread

**Response 202:**
```json
{
  "data": {
    "message_id": "uuid",
    "to": "+639171234567",
    "status": "accepted",
    "is_simulated": true,
    "segment_count": 1,
    "credit_cost": 0.05,
    "credit_balance_after": 4.95,
    "provider": "mock",
    "created_at": "2026-11-09T12:00:00Z"
  },
  "request_id": "..."
}
```

Note: `status: "accepted"` means the provider has received the request. It does **not** mean the message has been delivered. Track delivery via `GET /sms/outbound/:id` or Supabase Realtime events.

**Errors:**
- `422 PHONE_NOT_VERIFIED` — sender's phone not verified
- `422 SMS_COUNTRY_UNSUPPORTED` — destination country not supported
- `422 PHONE_OPTED_OUT` — recipient has opted out
- `422 INSUFFICIENT_CREDITS` — insufficient credit balance
- `409 DUPLICATE_IDEMPOTENCY_KEY` — returns original response, no re-send
- `502 PROVIDER_ERROR` — provider rejected the request (transient error, retry eligible)

---

## GET /sms/outbound

Get the authenticated user's outbound SMS history.  
**Auth:** Required  
**Phase:** 2  
**FR:** FR-SMS-004

**Query params:**
- `status` — filter by status (`accepted`, `sent`, `delivered`, `failed`, `permanently_failed`)
- `is_simulated` — `true` | `false`
- `page`, `page_size`

**Response 200:** Paginated list.
```json
{
  "data": [
    {
      "id": "uuid",
      "to": "+639171234567",
      "body": "Kumusta ka, Nanay?",
      "status": "delivered",
      "is_simulated": true,
      "segment_count": 1,
      "credit_cost": 0.05,
      "provider": "mock",
      "provider_message_id": "mock-sid-abc123",
      "retry_count": 0,
      "created_at": "2026-11-09T12:00:00Z",
      "updated_at": "2026-11-09T12:00:05Z"
    }
  ],
  "pagination": { ... },
  "request_id": "..."
}
```

---

## GET /sms/outbound/:messageId

Get details of a specific outbound SMS.  
**Auth:** Required (must be the sender)  
**Phase:** 2

**Response 200:** Single outbound SMS object with full delivery event history:
```json
{
  "data": {
    "id": "uuid",
    "to": "+63****1234",
    "body": "Kumusta ka, Nanay?",
    "status": "delivered",
    "is_simulated": true,
    "delivery_events": [
      { "status": "queued", "timestamp": "2026-11-09T12:00:00Z" },
      { "status": "sent", "timestamp": "2026-11-09T12:00:02Z" },
      { "status": "delivered", "timestamp": "2026-11-09T12:00:05Z" }
    ]
  },
  "request_id": "..."
}
```

Note: The `to` field is masked in this response for privacy. Full number stored in DB, accessible only by the sender and admins.

---

## POST /webhooks/sms/status

Receive SMS delivery status callbacks from the provider.  
**Auth:** Provider webhook signature validation (not JWT)  
**Phase:** 2  
**FR:** FR-SMSRECV-002

**Headers:**
```
X-Twilio-Signature: <computed signature>
Content-Type: application/x-www-form-urlencoded
```

**Request body (Twilio format, URL-encoded):**
```
MessageSid=SMxxx&MessageStatus=delivered&To=%2B639171234567&From=%2B12025551234
```

**Response 200:**
```json
{ "received": true }
```

Respond with 200 immediately to prevent provider retries. Processing is asynchronous.

**Errors:**
- `403 FORBIDDEN` — invalid webhook signature (logged, not processed)

---

## POST /webhooks/sms/inbound

Receive inbound SMS from the provider.  
**Auth:** Provider webhook signature validation (not JWT)  
**Phase:** 2  
**FR:** FR-SMSRECV-001, FR-SMSRECV-002

**Headers:**
```
X-Twilio-Signature: <computed signature>
Content-Type: application/x-www-form-urlencoded
```

**Request body (Twilio format):**
```
MessageSid=SMyyy&From=%2B639171234567&To=%2B14155551234&Body=Okay+sige+anak.
```

**Response 200 (TwiML — empty response):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>
```

**Errors:**
- `403 FORBIDDEN` — invalid webhook signature (logged, not processed)

---

## POST /sms/simulate/inbound (Development/Staging Only)

Simulate an inbound SMS reply for testing purposes. Not available in production.  
**Auth:** Required (admin)  
**Environments:** Development, Staging only

**Request:**
```json
{
  "from_phone": "+639171234567",
  "to_number": "+14155551234",
  "body": "Okay sige anak, maingat ka."
}
```

**Response 200:** Simulated inbound SMS record.

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
