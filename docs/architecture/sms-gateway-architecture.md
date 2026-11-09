# SMS Gateway Architecture

**Document:** CHKR-ARCH-005  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

This document defines the complete SMS subsystem architecture — provider abstraction, outbound flow, inbound flow, retry mechanism, idempotency, country capability, credit integration, and the two operating modes (simulation and live).

## Scope

All SMS-related backend components and their interactions with the database, the frontend, and external SMS providers.

---

## 1. SMS Subsystem Overview

```mermaid
graph TB
    subgraph "Frontend"
        COMPOSE[SMS Compose Screen]
        STATUS[Delivery Status Display]
    end

    subgraph "FastAPI Backend"
        SMS_ROUTE[POST /api/v1/sms/send]
        WEBHOOK_STATUS[POST /api/v1/webhooks/sms/status]
        WEBHOOK_INBOUND[POST /api/v1/webhooks/sms/inbound]
        SMS_SVC[SmsService]
        CREDIT_SVC[CreditService]
        NOTIF_SVC[NotificationService]
        RETRY[SMS Retry Task]
    end

    subgraph "Provider Layer"
        MOCK[MockSmsProvider]
        TWILIO[TwilioSmsProvider]
    end

    subgraph "Supabase"
        DB[(outbound_sms\nsms_delivery_events\ninbound_sms\ncredit_accounts)]
        RT[Realtime]
    end

    COMPOSE -->|send request| SMS_ROUTE
    SMS_ROUTE --> SMS_SVC
    SMS_SVC --> CREDIT_SVC
    SMS_SVC -->|mock mode| MOCK
    SMS_SVC -->|live mode| TWILIO
    MOCK --> DB
    TWILIO -->|HTTP| TWILIO_API[Twilio API]
    TWILIO_API -->|webhook| WEBHOOK_STATUS
    TWILIO_API -->|webhook| WEBHOOK_INBOUND
    WEBHOOK_STATUS --> SMS_SVC
    WEBHOOK_INBOUND --> SMS_SVC
    SMS_SVC --> DB
    SMS_SVC --> NOTIF_SVC
    SMS_SVC --> RT
    RT --> STATUS
    RETRY --> SMS_SVC
```

---

## 2. Provider Abstraction

All SMS providers implement `SmsProvider` (see `docs/architecture/backend-architecture.md`). The active provider is selected at runtime from `SMS_PROVIDER_MODE`.

| Mode | Provider | Real SMS | Credits | UI Badge |
|---|---|---|---|---|
| `mock` | `MockSmsProvider` | No | Not consumed | "SIMULATED" |
| `live` | `TwilioSmsProvider` | Yes | Consumed | Status per provider |

**Invariant:** The system never silently falls back from live to mock. If live mode fails to initialise, the application fails to start with a clear error.

---

## 3. Outbound SMS Flow

```mermaid
sequenceDiagram
    participant F as Frontend
    participant API as FastAPI /sms/send
    participant SVC as SmsService
    participant CREDIT as CreditService
    participant REPO as SmsRepository
    participant PROV as SmsProvider
    participant DB as Database
    participant RT as Supabase Realtime

    F->>API: POST {to, body, idempotency_key}
    API->>API: Validate JWT, parse Pydantic input
    API->>SVC: send_sms(user, to, body, idempotency_key)

    SVC->>SVC: Validate E.164 phone number
    SVC->>SVC: Check country capability
    SVC->>SVC: Calculate segment count + credit cost
    SVC->>CREDIT: check_and_reserve(user_id, cost)
    CREDIT->>DB: SELECT FOR UPDATE credit_accounts\nDeduct reserved amount
    CREDIT-->>SVC: ok

    SVC->>REPO: create_outbound_sms(status=pending, is_simulated=...)
    REPO->>DB: INSERT outbound_sms
    REPO-->>SVC: sms_record

    SVC->>PROV: send_message(to, body, from_, idempotency_key)
    
    alt Provider success
        PROV-->>SVC: SmsResult(provider_id, status=accepted)
        SVC->>REPO: update status=accepted, provider_id=...
        SVC->>CREDIT: confirm_deduction(reservation_id)
        SVC->>RT: publish status update
        API-->>F: 202 {message_id, status: accepted}
    else Provider failure
        PROV-->>SVC: SmsResult(status=failed, error=...)
        SVC->>REPO: update status=failed
        SVC->>CREDIT: release_reservation(reservation_id)
        SVC->>RETRY: schedule_retry(sms_id) if eligible
        API-->>F: 202 {message_id, status: failed} or 502
    end
```

---

## 4. Delivery Status Webhook Flow

```mermaid
sequenceDiagram
    participant TWILIO as Twilio
    participant WH as /webhooks/sms/status
    participant SVC as SmsService
    participant DB as Database
    participant RT as Supabase Realtime
    participant CREDIT as CreditService

    TWILIO->>WH: POST delivery event (provider_id, status)
    WH->>WH: Validate webhook signature
    alt Signature invalid
        WH-->>TWILIO: 403 Forbidden
        note over WH: Log warning, no processing
    else Signature valid
        WH->>SVC: process_delivery_event(provider_id, status)
        SVC->>DB: SELECT outbound_sms WHERE provider_message_id = ?
        SVC->>DB: INSERT sms_delivery_events (idempotent check)
        SVC->>DB: UPDATE outbound_sms SET status = mapped_status
        
        alt Status = permanently_failed
            SVC->>CREDIT: refund(user_id, credit_amount)
            SVC->>RT: publish failure + refund event
        else Status = delivered
            SVC->>RT: publish delivered event
        end
        
        WH-->>TWILIO: 200 OK
    end
```

---

## 5. Inbound SMS Webhook Flow

```mermaid
sequenceDiagram
    participant PHONE as Basic Phone User
    participant CARRIER as Carrier Network
    participant TWILIO as Twilio
    participant WH as /webhooks/sms/inbound
    participant SVC as SmsService
    participant DB as Database
    participant RT as Supabase Realtime
    participant BROWSER as Sender's Browser

    PHONE->>CARRIER: SMS reply
    CARRIER->>TWILIO: Inbound SMS delivery
    TWILIO->>WH: POST {From, To, Body, MessageSid}
    WH->>WH: Validate webhook signature
    
    alt Signature invalid
        WH-->>TWILIO: 403
    else Signature valid
        WH->>SVC: process_inbound_sms(from, to, body, provider_id)
        SVC->>DB: Check idempotency (provider_message_id)
        
        alt Already processed
            SVC-->>WH: skip (idempotent)
        else New message
            SVC->>DB: Match conversation by (from_phone, to_number)
            
            alt Matched
                SVC->>DB: INSERT messages (origin=sms, sender_phone=from)
                SVC->>DB: INSERT inbound_sms (is_matched=true)
                SVC->>RT: publish new message to conversation channel
                RT->>BROWSER: New SMS message event
            else Unmatched
                SVC->>DB: INSERT inbound_sms (is_matched=false)
                note over SVC: Admin notification generated
            end
        end
        WH-->>TWILIO: 200 OK (TwiML empty response)
    end
```

---

## 6. Retry Architecture

```mermaid
stateDiagram-v2
    [*] --> pending: SMS created
    pending --> accepted: Provider accepts
    pending --> failed: Provider rejects
    accepted --> sent: Provider sends to carrier
    accepted --> failed: Provider error
    sent --> delivered: Carrier confirms delivery
    sent --> undelivered: Carrier cannot deliver
    failed --> pending: Retry scheduled (if retry_count < max_retries)
    failed --> permanently_failed: retry_count >= max_retries
    undelivered --> permanently_failed: No more retries
    delivered --> [*]
    permanently_failed --> [*]: Credits refunded, user notified
```

### Retry Configuration

| Parameter | Default | Configurable |
|---|---|---|
| Max retries | 3 | Yes (env var) |
| Base delay | 30 seconds | Yes |
| Backoff multiplier | 2x | Yes |
| Jitter | ±25% of delay | Fixed |
| Retry-eligible statuses | `failed` (transient) | Fixed in code |
| Non-retry statuses | `undelivered`, provider opt-out errors | Fixed in code |

### Idempotency

Every outbound SMS carry a client-generated `idempotency_key` (UUID). The `outbound_sms` table has a `UNIQUE` constraint on this key. If the same key is submitted twice:
- The original record is returned with its current status.
- No double send occurs.
- No double credit deduction occurs.

---

## 7. Country Capability System

The `country_capabilities` table (admin-managed) defines per-country SMS behaviour:

```python
class CountryCapability:
    country_code: str          # ISO 3166-1 alpha-2 (e.g. "PH")
    country_name: str
    outbound_enabled: bool
    inbound_enabled: bool      # Two-way SMS availability
    alphanumeric_sender_id: bool
    requires_registered_sender: bool
    credit_cost_per_segment: Decimal
    notes: str | None
```

### Philippines Configuration (Initial)

| Field | Value | Notes |
|---|---|---|
| `outbound_enabled` | `true` | Outbound SMS supported |
| `inbound_enabled` | **requires verification** | ⚠ Depends on Twilio PH routing and carrier agreements |
| `alphanumeric_sender_id` | `false` | Not universally supported by PH carriers |
| `requires_registered_sender` | `true` | A2P sender registration required |
| `credit_cost_per_segment` | TBD | Set when Twilio PH rates confirmed |

> **⚠ Provider Verification Required:** Two-way SMS (inbound) availability in the Philippines is dependent on Twilio's carrier routing agreements for PH numbers. This capability must be verified with Twilio before it is exposed to users or marketed as available. See RISK-001 in `docs/project-management/risk-register.md`.

---

## 8. Simulation Mode Behaviour

MockSmsProvider simulates the full provider lifecycle without sending any real SMS:

| Event | Behaviour |
|---|---|
| Send | Records message as `accepted` immediately |
| Delivery callback | After configurable delay (default 2s), transitions to `delivered` |
| Provider error simulation | Triggered by special test phone numbers (e.g. `+15005550001` = failure) |
| Inbound SMS simulation | Admin can POST to a test endpoint to simulate an inbound SMS |
| UI label | "SIMULATED" badge on every affected message — permanent, not removable |

---

## 9. SMS Audit Logging

All SMS events are logged with:

| Field | Description |
|---|---|
| `message_id` | Internal UUID |
| `idempotency_key` | Client-provided dedup key |
| `provider` | `mock` or `twilio` |
| `recipient_phone` | Masked: country code + last 4 digits |
| `status` | Current status enum value |
| `is_simulated` | Boolean |
| `segment_count` | Number of SMS segments |
| `credit_cost` | Credits deducted |
| `timestamp` | UTC timestamp |

Audit logs retained for minimum 90 days. Read-only from admin UI.

---

## 10. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
