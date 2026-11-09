# Entity Relationships

**Document:** CHKR-DB-002  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Describes all entity relationships in the Chikka Reborn database — cardinality, constraints, and the business rules encoded in those relationships.

## Scope

All 13 tables. Complements the DDL in `docs/database/database-schema.md`.

---

## 1. Full Entity Relationship Diagram

```mermaid
erDiagram
    profiles {
        uuid id PK
        text username UK
        text display_name
        text phone_number UK
        text role
        text ui_mode
        bool is_active
        timestamptz deleted_at
        timestamptz created_at
    }

    contacts {
        uuid id PK
        uuid owner_id FK
        contact_type contact_type
        uuid chikka_user_id FK
        text phone_number
        text display_name
        contact_status status
    }

    conversations {
        uuid id PK
        conversation_type type
        timestamptz last_message_at
    }

    conversation_participants {
        uuid id PK
        uuid conversation_id FK
        uuid user_id FK
        text phone_number
        timestamptz last_read_at
    }

    messages {
        uuid id PK
        uuid conversation_id FK
        uuid sender_user_id FK
        text sender_phone
        message_origin origin
        text body
        message_status status
        bool is_ai_assisted
        timestamptz deleted_at
    }

    notifications {
        uuid id PK
        uuid user_id FK
        notification_type type
        bool is_read
    }

    outbound_sms {
        uuid id PK
        uuid sender_user_id FK
        text recipient_phone
        text body
        sms_status status
        bool is_simulated
        text idempotency_key UK
        uuid conversation_id FK
        int retry_count
    }

    sms_delivery_events {
        uuid id PK
        uuid outbound_sms_id FK
        text provider_message_id
        sms_status mapped_status
        jsonb raw_payload
    }

    inbound_sms {
        uuid id PK
        text provider_message_id UK
        text from_phone
        text body
        uuid conversation_id FK
        uuid matched_user_id FK
        bool is_matched
    }

    credit_accounts {
        uuid id PK
        uuid user_id FK
        numeric balance
        numeric reserved
    }

    credit_transactions {
        uuid id PK
        uuid credit_account_id FK
        uuid user_id FK
        credit_transaction_type type
        numeric amount
        numeric balance_after
    }

    country_capabilities {
        uuid id PK
        char country_code UK
        bool outbound_enabled
        bool inbound_enabled
        numeric credit_cost_per_segment
    }

    ai_usage_logs {
        uuid id PK
        uuid user_id FK
        text feature
        text model_id
        int input_tokens
        int output_tokens
        bool success
    }

    profiles ||--o{ contacts : "owner_id — owns"
    profiles ||--o{ contacts : "chikka_user_id — is target of"
    profiles ||--o{ conversation_participants : "user_id — participates in"
    profiles ||--o{ messages : "sender_user_id — sends"
    profiles ||--o{ outbound_sms : "sender_user_id — sends"
    profiles ||--|| credit_accounts : "user_id — has exactly one"
    profiles ||--o{ credit_transactions : "user_id — records"
    profiles ||--o{ notifications : "user_id — receives"
    profiles ||--o{ ai_usage_logs : "user_id — generates"

    conversations ||--o{ conversation_participants : "conversation_id"
    conversations ||--o{ messages : "conversation_id — contains"
    conversations ||--o{ outbound_sms : "conversation_id — linked"
    conversations ||--o{ inbound_sms : "conversation_id — linked"

    outbound_sms ||--o{ sms_delivery_events : "outbound_sms_id — events"
    credit_accounts ||--o{ credit_transactions : "credit_account_id — ledger"
```

---

## 2. Relationship Descriptions

### profiles → contacts (owner)
**Cardinality:** One profile owns zero or many contacts.  
**Rule:** `contacts.owner_id = profiles.id`. Cascade delete: when a profile is deleted, their contact list is deleted.

### profiles → contacts (target)
**Cardinality:** One profile may appear as the target (`chikka_user_id`) in zero or many other users' contact lists.  
**Rule:** `contacts.chikka_user_id = profiles.id`. Set null on delete: if a user deletes their account, they are removed as the contact target but the contact record persists (shows as "Deleted User").

### profiles → conversation_participants
**Cardinality:** One profile participates in zero or many conversations.  
**Rule:** A conversation participant is either a registered user (`user_id IS NOT NULL`) or an SMS-only phone number (`phone_number IS NOT NULL`). Never both. This constraint is enforced by a CHECK constraint.

### conversations → conversation_participants
**Cardinality:** One conversation has two or more participants.  
**Rule:** Phase 1 enforces exactly two participants per conversation. The application layer enforces this; the DB allows more for future group support.

### conversations → messages
**Cardinality:** One conversation has zero or many messages.  
**Rule:** Messages belong to exactly one conversation. Cascade delete: deleting a conversation deletes all its messages.

### messages (deleted)
**Rule:** When a message is deleted, `body` is set to `NULL` and `deleted_at` is set. The row is not removed — this preserves thread continuity and allows the "This message was deleted" placeholder. The CHECK constraint requires `body IS NOT NULL` only when `deleted_at IS NULL`.

### outbound_sms → sms_delivery_events
**Cardinality:** One outbound SMS has zero or many delivery events.  
**Rule:** Delivery events are immutable — they are never updated, only appended. The unique constraint `(provider_message_id, provider_status)` prevents duplicate event processing.

### profiles → credit_accounts
**Cardinality:** Exactly one credit account per profile.  
**Rule:** Created automatically by a trigger when a new profile is inserted. UNIQUE constraint on `user_id`. Balance and reserved are non-negative by CHECK constraint — the application layer uses `SELECT FOR UPDATE` to prevent concurrent over-deduction.

### credit_accounts → credit_transactions
**Cardinality:** One account has zero or many transactions.  
**Rule:** Transactions are immutable — they are never updated or deleted. They form an append-only ledger. `balance_after` records the account balance at the time of the transaction, enabling audit and reconstruction.

### inbound_sms → conversations (optional)
**Cardinality:** An inbound SMS is optionally linked to one conversation.  
**Rule:** Matching logic: find a conversation where one participant's `phone_number` matches `inbound_sms.from_phone` and another participant's virtual number matches `inbound_sms.to_number`. If matched, `is_matched = TRUE` and `conversation_id` is set. If not matched, `is_matched = FALSE` and `conversation_id` is NULL — logged for admin review.

### country_capabilities (standalone)
**Cardinality:** Zero or many capabilities records; one per country code.  
**Rule:** Not linked to any user data. Admin-managed reference data. Read by the SMS service to determine capability before allowing a send.

---

## 3. Constraints Summary

| Table | Constraint | Type | Description |
|---|---|---|---|
| `profiles` | `username_length` | CHECK | 3–30 characters |
| `profiles` | `username_format` | CHECK | Lowercase alphanumeric + underscore only |
| `profiles` | `valid_role` | CHECK | `user` or `admin` only |
| `profiles` | `valid_ui_mode` | CHECK | `modern` or `classic` only |
| `contacts` | `contacts_chikka_xor_sms` | CHECK | Either Chikka user OR phone, never both |
| `contacts` | `contacts_no_self` | CHECK | Cannot add yourself as a contact |
| `contacts` | `contacts_unique_chikka` | UNIQUE | One contact entry per Chikka user pair |
| `contacts` | `contacts_unique_sms` | UNIQUE | One SMS contact entry per phone number per owner |
| `conversation_participants` | `participants_user_xor_phone` | CHECK | Either user_id OR phone_number, never both |
| `messages` | `message_has_sender` | CHECK | Must have sender_user_id or sender_phone |
| `messages` | `message_body_required` | CHECK | Body only NULL when deleted_at is set |
| `outbound_sms` | `idempotency_key` | UNIQUE | Prevents duplicate sends |
| `outbound_sms` | `valid_provider` | CHECK | `mock` or `twilio` only |
| `sms_delivery_events` | `delivery_event_idempotent` | UNIQUE | `(provider_message_id, provider_status)` |
| `inbound_sms` | `provider_message_id` | UNIQUE | Prevents duplicate inbound processing |
| `credit_accounts` | `credit_balance_non_negative` | CHECK | Balance ≥ 0 always |
| `credit_accounts` | `credit_reserved_non_negative` | CHECK | Reserved ≥ 0 always |
| `ai_usage_logs` | `valid_ai_feature` | CHECK | Known feature names only |

---

## 4. Nullable Fields and Their Meaning

| Table | Field | Nullable? | Meaning when NULL |
|---|---|---|---|
| `profiles` | `phone_number` | Yes | No phone number associated |
| `profiles` | `deleted_at` | Yes | Account is active |
| `messages` | `sender_user_id` | Yes | Message originated from an SMS-only sender |
| `messages` | `sender_phone` | Yes | Message originated from a registered user |
| `messages` | `body` | Yes | Message has been deleted |
| `messages` | `deleted_at` | Yes | Message is not deleted |
| `outbound_sms` | `provider_message_id` | Yes | Not yet sent to provider |
| `outbound_sms` | `conversation_id` | Yes | Standalone SMS, not part of a conversation thread |
| `inbound_sms` | `conversation_id` | Yes | Inbound SMS could not be matched to a conversation |
| `inbound_sms` | `matched_user_id` | Yes | Inbound SMS could not be matched to a user |
| `ai_usage_logs` | `error_code` | Yes | AI call succeeded |

---

## 5. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
