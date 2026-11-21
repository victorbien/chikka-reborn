# Database Design

> **SUPERSEDED (November 2026).** Retained for history. The canonical version is in docs/database/ (schema, entity-relationships, migrations, row-level-security). Requirement IDs here use the older scheme (e.g. FR-A-001); see the 'Was:' fields in docs/product/functional-requirements.md for the mapping.

**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Date:** November 2026  

---

## 1. Overview

The database is a **Supabase PostgreSQL** instance. All schema changes are managed as numbered migration files in `supabase/migrations/`. No ad hoc schema changes in production.

### Design Principles

- All primary keys are UUIDs (`gen_random_uuid()`).
- All tables include `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
- All mutable tables include `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
- Sensitive records use soft-delete: `deleted_at TIMESTAMPTZ NULL`.
- Row Level Security (RLS) is defined for every table.
- Indexes are defined alongside tables for all foreign keys and frequent query patterns.
- Phone numbers are stored in E.164 format.
- Enum types are used for status and mode fields.
- Message content is stored as `TEXT`; no length limit imposed at the DB layer (limits enforced at the application layer).

---

## 2. Schema Diagram (Conceptual)

```
profiles ──────────────────────────────────────────────────────┐
    │                                                           │
    ├──< contacts >──── profiles (friend/SMS contact)          │
    │                                                           │
    ├──< conversation_participants >──< conversations          │
    │                                         │                │
    │                                         └──< messages    │
    │                                                          │
    ├──< outbound_sms >─────────────────────────────────────── │
    │         │                                                 │
    │         └──< sms_delivery_events                         │
    │                                                          │
    ├──< inbound_sms                                           │
    │                                                          │
    ├──< credit_accounts >──< credit_transactions             │
    │                                                          │
    ├──< ai_usage_logs                                        │
    │                                                          │
    └──< notifications                                        │
                                                              │
country_capabilities (admin-managed, no user FK)              │
sms_provider_config  (admin-managed)                          │
```

---

## 3. Table Definitions

### 3.1 `profiles`

Extends Supabase Auth's `auth.users` table. One profile per user account.

```sql
CREATE TABLE profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username        TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    bio             TEXT,
    avatar_url      TEXT,
    country_code    CHAR(2),                        -- ISO 3166-1 alpha-2
    phone_number    TEXT UNIQUE,                    -- E.164, verified only
    phone_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    role            TEXT NOT NULL DEFAULT 'user',   -- 'user' | 'admin'
    ui_mode         TEXT NOT NULL DEFAULT 'modern', -- 'modern' | 'classic'
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_profiles_username ON profiles (username);
CREATE INDEX idx_profiles_phone_number ON profiles (phone_number);

-- RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "profiles_select_own" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "profiles_select_public" ON profiles
    FOR SELECT USING (
        deleted_at IS NULL
        AND is_active = TRUE
        -- Full profile visible to all authenticated users (privacy settings applied in application layer)
    );

CREATE POLICY "profiles_update_own" ON profiles
    FOR UPDATE USING (auth.uid() = id);
```

---

### 3.2 `contacts`

Represents a user's contact list entry. Supports both Chikka users and SMS-only contacts.

```sql
CREATE TYPE contact_type AS ENUM ('chikka', 'sms');
CREATE TYPE contact_status AS ENUM ('active', 'blocked', 'muted');

CREATE TABLE contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    contact_type    contact_type NOT NULL,
    -- For Chikka contacts:
    chikka_user_id  UUID REFERENCES profiles(id) ON DELETE CASCADE,
    -- For SMS contacts:
    phone_number    TEXT,
    display_name    TEXT,                           -- User-set label for SMS contact
    status          contact_status NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT contacts_chikka_xor_sms CHECK (
        (contact_type = 'chikka' AND chikka_user_id IS NOT NULL AND phone_number IS NULL)
        OR (contact_type = 'sms' AND phone_number IS NOT NULL AND chikka_user_id IS NULL)
    ),
    CONSTRAINT contacts_unique_chikka UNIQUE (owner_id, chikka_user_id),
    CONSTRAINT contacts_unique_sms    UNIQUE (owner_id, phone_number)
);

CREATE INDEX idx_contacts_owner_id ON contacts (owner_id);
CREATE INDEX idx_contacts_chikka_user_id ON contacts (chikka_user_id);

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "contacts_owner_all" ON contacts
    FOR ALL USING (auth.uid() = owner_id);
```

---

### 3.3 `conversations`

A conversation thread between two or more participants. Phase 1: two-party only.

```sql
CREATE TYPE conversation_type AS ENUM ('chikka', 'sms', 'mixed');

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_type conversation_type NOT NULL DEFAULT 'chikka',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at TIMESTAMPTZ
);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- Access via conversation_participants (see below)
CREATE POLICY "conversations_participant_select" ON conversations
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM conversation_participants cp
            WHERE cp.conversation_id = id
            AND cp.user_id = auth.uid()
        )
    );
```

---

### 3.4 `conversation_participants`

Junction table linking users to conversations.

```sql
CREATE TABLE conversation_participants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES profiles(id) ON DELETE SET NULL,
    phone_number    TEXT,                           -- For SMS-only participants
    last_read_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT participants_user_xor_phone CHECK (
        (user_id IS NOT NULL AND phone_number IS NULL)
        OR (user_id IS NULL AND phone_number IS NOT NULL)
    )
);

CREATE INDEX idx_cp_conversation_id ON conversation_participants (conversation_id);
CREATE INDEX idx_cp_user_id ON conversation_participants (user_id);
CREATE INDEX idx_cp_phone_number ON conversation_participants (phone_number);

ALTER TABLE conversation_participants ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cp_own_rows" ON conversation_participants
    FOR SELECT USING (auth.uid() = user_id);
```

---

### 3.5 `messages`

All messages in a conversation, regardless of origin (Chikka or SMS).

```sql
CREATE TYPE message_origin AS ENUM ('chikka', 'sms');
CREATE TYPE message_status AS ENUM ('sending', 'sent', 'delivered', 'read', 'failed');

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_user_id  UUID REFERENCES profiles(id) ON DELETE SET NULL,
    sender_phone    TEXT,                           -- For SMS-origin messages
    origin          message_origin NOT NULL DEFAULT 'chikka',
    body            TEXT NOT NULL,
    status          message_status NOT NULL DEFAULT 'sent',
    is_ai_assisted  BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages (conversation_id, created_at DESC);
CREATE INDEX idx_messages_sender_user_id ON messages (sender_user_id);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "messages_conversation_participant" ON messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM conversation_participants cp
            WHERE cp.conversation_id = messages.conversation_id
            AND cp.user_id = auth.uid()
        )
    );

CREATE POLICY "messages_insert_own" ON messages
    FOR INSERT WITH CHECK (auth.uid() = sender_user_id);
```

---

### 3.6 `outbound_sms`

All SMS messages sent from the platform to external phone numbers.

```sql
CREATE TYPE sms_status AS ENUM (
    'pending', 'accepted', 'queued', 'sent',
    'delivered', 'failed', 'undelivered', 'permanently_failed'
);

CREATE TABLE outbound_sms (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_user_id      UUID NOT NULL REFERENCES profiles(id),
    recipient_phone     TEXT NOT NULL,              -- E.164
    body                TEXT NOT NULL,
    segment_count       SMALLINT NOT NULL DEFAULT 1,
    credit_cost         NUMERIC(10,4) NOT NULL,
    status              sms_status NOT NULL DEFAULT 'pending',
    is_simulated        BOOLEAN NOT NULL DEFAULT FALSE,
    provider            TEXT,                       -- 'mock' | 'twilio'
    provider_message_id TEXT,                       -- Provider's message SID
    idempotency_key     TEXT NOT NULL UNIQUE,
    conversation_id     UUID REFERENCES conversations(id),
    retry_count         SMALLINT NOT NULL DEFAULT 0,
    max_retries         SMALLINT NOT NULL DEFAULT 3,
    last_retried_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outbound_sms_sender ON outbound_sms (sender_user_id, created_at DESC);
CREATE INDEX idx_outbound_sms_provider_id ON outbound_sms (provider_message_id);
CREATE INDEX idx_outbound_sms_status ON outbound_sms (status);
CREATE INDEX idx_outbound_sms_idempotency ON outbound_sms (idempotency_key);

ALTER TABLE outbound_sms ENABLE ROW LEVEL SECURITY;

CREATE POLICY "outbound_sms_own" ON outbound_sms
    FOR SELECT USING (auth.uid() = sender_user_id);
```

---

### 3.7 `sms_delivery_events`

Immutable log of delivery status callbacks from the SMS provider.

```sql
CREATE TABLE sms_delivery_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbound_sms_id     UUID NOT NULL REFERENCES outbound_sms(id),
    provider_message_id TEXT NOT NULL,
    provider_status     TEXT NOT NULL,              -- Raw provider status string
    mapped_status       sms_status NOT NULL,        -- Normalised internal status
    provider_timestamp  TIMESTAMPTZ,
    raw_payload         JSONB,                      -- Full webhook payload
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_delivery_events_sms_id ON sms_delivery_events (outbound_sms_id);
CREATE INDEX idx_delivery_events_provider_id ON sms_delivery_events (provider_message_id);

ALTER TABLE sms_delivery_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "delivery_events_admin_only" ON sms_delivery_events
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );
```

---

### 3.8 `inbound_sms`

SMS messages received from external phones via provider webhooks.

```sql
CREATE TABLE inbound_sms (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_message_id TEXT NOT NULL UNIQUE,
    from_phone          TEXT NOT NULL,              -- E.164
    to_number           TEXT NOT NULL,              -- Platform virtual number
    body                TEXT NOT NULL,
    conversation_id     UUID REFERENCES conversations(id),
    matched_user_id     UUID REFERENCES profiles(id),
    is_matched          BOOLEAN NOT NULL DEFAULT FALSE,
    received_at         TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inbound_sms_from_phone ON inbound_sms (from_phone);
CREATE INDEX idx_inbound_sms_conversation ON inbound_sms (conversation_id);

ALTER TABLE inbound_sms ENABLE ROW LEVEL SECURITY;

CREATE POLICY "inbound_sms_participant" ON inbound_sms
    FOR SELECT USING (
        auth.uid() = matched_user_id
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );
```

---

### 3.9 `credit_accounts`

One credit account per user.

```sql
CREATE TABLE credit_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
    balance         NUMERIC(12,4) NOT NULL DEFAULT 0,
    reserved        NUMERIC(12,4) NOT NULL DEFAULT 0,  -- Credits held for pending sends
    currency        CHAR(3) NOT NULL DEFAULT 'USD',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT credit_balance_non_negative CHECK (balance >= 0),
    CONSTRAINT credit_reserved_non_negative CHECK (reserved >= 0)
);

ALTER TABLE credit_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "credit_accounts_own" ON credit_accounts
    FOR SELECT USING (auth.uid() = user_id);
```

---

### 3.10 `credit_transactions`

Immutable ledger of all credit movements.

```sql
CREATE TYPE credit_transaction_type AS ENUM (
    'top_up', 'deduction', 'refund', 'reservation', 'reservation_release', 'adjustment'
);

CREATE TABLE credit_transactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credit_account_id   UUID NOT NULL REFERENCES credit_accounts(id),
    user_id             UUID NOT NULL REFERENCES profiles(id),
    transaction_type    credit_transaction_type NOT NULL,
    amount              NUMERIC(12,4) NOT NULL,         -- Positive = credit, negative = debit
    balance_after       NUMERIC(12,4) NOT NULL,
    reference_type      TEXT,                           -- 'outbound_sms', 'top_up', etc.
    reference_id        UUID,                           -- FK to source record
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_credit_tx_user ON credit_transactions (user_id, created_at DESC);
CREATE INDEX idx_credit_tx_account ON credit_transactions (credit_account_id);

ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "credit_tx_own" ON credit_transactions
    FOR SELECT USING (auth.uid() = user_id);
```

---

### 3.11 `notifications`

In-app notification records per user.

```sql
CREATE TYPE notification_type AS ENUM (
    'new_message', 'sms_delivered', 'sms_failed',
    'low_balance', 'system', 'contact_request'
);

CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    notification_type notification_type NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    reference_type  TEXT,                           -- 'message', 'outbound_sms', etc.
    reference_id    UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread ON notifications (user_id, is_read, created_at DESC);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "notifications_own" ON notifications
    FOR ALL USING (auth.uid() = user_id);
```

---

### 3.12 `country_capabilities`

Admin-managed configuration for per-country SMS capabilities.

```sql
CREATE TABLE country_capabilities (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code            CHAR(2) NOT NULL UNIQUE,    -- ISO 3166-1 alpha-2
    country_name            TEXT NOT NULL,
    outbound_enabled        BOOLEAN NOT NULL DEFAULT FALSE,
    inbound_enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    alphanumeric_sender_id  BOOLEAN NOT NULL DEFAULT FALSE,
    requires_registered_sender BOOLEAN NOT NULL DEFAULT FALSE,
    credit_cost_per_segment NUMERIC(10,6) NOT NULL DEFAULT 0,
    notes                   TEXT,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by              UUID REFERENCES profiles(id)
);

ALTER TABLE country_capabilities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "country_capabilities_select_all" ON country_capabilities
    FOR SELECT USING (TRUE);                        -- All authenticated users can read

CREATE POLICY "country_capabilities_admin_write" ON country_capabilities
    FOR ALL USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );
```

---

### 3.13 `ai_usage_logs`

Metadata log for AI assistant usage. No message content is stored here.

```sql
CREATE TABLE ai_usage_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES profiles(id),
    feature         TEXT NOT NULL,      -- 'smart_reply', 'translate', 'rewrite', etc.
    model_id        TEXT NOT NULL,      -- Bedrock model identifier
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    latency_ms      INTEGER,
    success         BOOLEAN NOT NULL,
    error_code      TEXT,               -- NULL on success
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_logs_user ON ai_usage_logs (user_id, created_at DESC);
CREATE INDEX idx_ai_logs_feature ON ai_usage_logs (feature);

ALTER TABLE ai_usage_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_logs_admin_only" ON ai_usage_logs
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );
```

---

## 4. Real-Time Events

Supabase Realtime is not used (ADL-020). No table is in the `supabase_realtime` publication. The backend pushes events through its own WebSocket gateway after each commit ([realtime-api.md](api/realtime-api.md)), so recipients, blocks and per-user visibility are checked in one place. The tables each push relates to:

| Event | Source tables |
|---|---|
| `message.created` | `messages` (seq allocated by `trg_messages_assign_seq`) |
| `message.status_changed` | `message_deliveries` (forward-only status, projected onto `messages.status` by `trg_deliveries_sync_message`) |
| `conversation.read` | `conversation_members.last_read_seq` |

---

## 5. Supabase Storage

| Bucket | Contents | Access |
|---|---|---|
| `avatars` | User profile photos (re-encoded WebP) | Private; backend writes, signed URLs (1 hour) |
| `message-attachments` | Chat attachments (JPEG, PNG, WebP, GIF, PDF, up to 10 MB) | Private; backend writes after content checks, signed URLs (1 hour) for conversation members. Rows in `message_attachments` |
| `exports` | User data export archives | Owner read only, signed URL |

---

## 6. Migration Strategy

- Migrations are stored in `supabase/migrations/` as numbered SQL files: `YYYYMMDDHHMMSS_description.sql`.
- Each migration is atomic. It should succeed or fail in full — no partial migrations.
- Migrations include both the schema change and the corresponding RLS policies.
- Destructive migrations (DROP TABLE, DROP COLUMN) require a human approval step before being applied to production.
- Seed data for `country_capabilities` is managed as a separate seed file: `supabase/seed.sql`.

---

## 7. Open Database Decisions

| ID | Question | Impact |
|---|---|---|
| DB-OD-001 | Data retention: how long to retain messages and SMS records? | Affects storage costs and regulatory compliance |
| DB-OD-002 | Message encryption at rest: Supabase default or application-level encryption? | Security posture |
| DB-OD-003 | Supabase region selection for data residency | Compliance |
| DB-OD-004 | Archive strategy for old messages (partition, separate table, external storage) | Long-term scalability |

---

## 8. Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
