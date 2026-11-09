# Database Schema

**Document:** CHKR-DB-001  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Complete SQL DDL for all Chikka Reborn database tables. This is the authoritative source for table structure. All schema changes must go through migration files (`supabase/migrations/`) — never applied manually.

## Scope

All 13 tables across all phases. RLS policies are in `docs/database/row-level-security.md`. Migration sequencing is in `docs/database/database-migrations.md`.

---

## Global Design Rules

```sql
-- All tables use these conventions:
-- Primary keys: UUID DEFAULT gen_random_uuid()
-- Timestamps: TIMESTAMPTZ NOT NULL DEFAULT NOW()
-- Phone numbers: TEXT in E.164 format
-- Soft deletes: deleted_at TIMESTAMPTZ NULL
-- Enum types: CREATE TYPE before table creation
-- RLS: ENABLE ROW LEVEL SECURITY on every table
```

---

## Phase 1 Tables

### `profiles`

Extends `auth.users`. One row per registered user.

```sql
CREATE TABLE profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username        TEXT UNIQUE NOT NULL
                        CONSTRAINT username_length CHECK (char_length(username) BETWEEN 3 AND 30)
                        CONSTRAINT username_format CHECK (username ~ '^[a-z0-9_]+$'),
    display_name    TEXT NOT NULL
                        CONSTRAINT display_name_length CHECK (char_length(display_name) BETWEEN 2 AND 50),
    bio             TEXT
                        CONSTRAINT bio_length CHECK (char_length(bio) <= 300),
    avatar_url      TEXT,
    country_code    CHAR(2),
    phone_number    TEXT UNIQUE,                    -- E.164, verified only
    phone_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    role            TEXT NOT NULL DEFAULT 'user'
                        CONSTRAINT valid_role CHECK (role IN ('user', 'admin')),
    ui_mode         TEXT NOT NULL DEFAULT 'modern'
                        CONSTRAINT valid_ui_mode CHECK (ui_mode IN ('modern', 'classic')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_profiles_username ON profiles (username);
CREATE INDEX idx_profiles_phone_number ON profiles (phone_number) WHERE phone_number IS NOT NULL;
CREATE INDEX idx_profiles_role ON profiles (role);
```

---

### `contacts`

User's contact list. Supports Chikka users and SMS-only contacts.

```sql
CREATE TYPE contact_type AS ENUM ('chikka', 'sms');
CREATE TYPE contact_status AS ENUM ('active', 'blocked', 'muted');

CREATE TABLE contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    contact_type    contact_type NOT NULL,
    chikka_user_id  UUID REFERENCES profiles(id) ON DELETE CASCADE,
    phone_number    TEXT,
    display_name    TEXT
                        CONSTRAINT display_name_length CHECK (char_length(display_name) <= 100),
    status          contact_status NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT contacts_chikka_xor_sms CHECK (
        (contact_type = 'chikka' AND chikka_user_id IS NOT NULL AND phone_number IS NULL)
        OR (contact_type = 'sms' AND phone_number IS NOT NULL AND chikka_user_id IS NULL)
    ),
    CONSTRAINT contacts_no_self CHECK (owner_id <> chikka_user_id),
    CONSTRAINT contacts_unique_chikka UNIQUE (owner_id, chikka_user_id),
    CONSTRAINT contacts_unique_sms    UNIQUE (owner_id, phone_number)
);

CREATE INDEX idx_contacts_owner_id ON contacts (owner_id);
CREATE INDEX idx_contacts_chikka_user_id ON contacts (chikka_user_id)
    WHERE chikka_user_id IS NOT NULL;
```

---

### `conversations`

A thread between two or more participants.

```sql
CREATE TYPE conversation_type AS ENUM ('chikka', 'sms', 'mixed');

CREATE TABLE conversations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_type   conversation_type NOT NULL DEFAULT 'chikka',
    last_message_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_last_message_at ON conversations (last_message_at DESC);
```

---

### `conversation_participants`

Junction table: users or SMS-only numbers in a conversation.

```sql
CREATE TABLE conversation_participants (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id             UUID REFERENCES profiles(id) ON DELETE SET NULL,
    phone_number        TEXT,
    last_read_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT participants_user_xor_phone CHECK (
        (user_id IS NOT NULL AND phone_number IS NULL)
        OR (user_id IS NULL AND phone_number IS NOT NULL)
    ),
    CONSTRAINT participants_unique_user UNIQUE (conversation_id, user_id),
    CONSTRAINT participants_unique_phone UNIQUE (conversation_id, phone_number)
);

CREATE INDEX idx_cp_conversation_id ON conversation_participants (conversation_id);
CREATE INDEX idx_cp_user_id ON conversation_participants (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_cp_phone_number ON conversation_participants (phone_number)
    WHERE phone_number IS NOT NULL;
```

---

### `messages`

All messages in all conversations (Chikka-origin and SMS-origin).

```sql
CREATE TYPE message_origin AS ENUM ('chikka', 'sms');
CREATE TYPE message_status AS ENUM ('sending', 'sent', 'delivered', 'read', 'failed');

CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_user_id      UUID REFERENCES profiles(id) ON DELETE SET NULL,
    sender_phone        TEXT,
    origin              message_origin NOT NULL DEFAULT 'chikka',
    body                TEXT,                       -- NULL when deleted_at is set
    status              message_status NOT NULL DEFAULT 'sent',
    is_ai_assisted      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT message_has_sender CHECK (
        (sender_user_id IS NOT NULL) OR (sender_phone IS NOT NULL)
    ),
    CONSTRAINT message_body_required CHECK (
        deleted_at IS NOT NULL OR (body IS NOT NULL AND char_length(body) > 0)
    )
);

CREATE INDEX idx_messages_conversation_id ON messages (conversation_id, created_at DESC);
CREATE INDEX idx_messages_sender_user_id ON messages (sender_user_id)
    WHERE sender_user_id IS NOT NULL;
CREATE INDEX idx_messages_status ON messages (status);
```

---

### `notifications`

In-app notification records per user.

```sql
CREATE TYPE notification_type AS ENUM (
    'new_message', 'sms_delivered', 'sms_failed',
    'low_balance', 'system', 'contact_request'
);

CREATE TABLE notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    notification_type   notification_type NOT NULL,
    title               TEXT NOT NULL,
    body                TEXT,
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    reference_type      TEXT,
    reference_id        UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread
    ON notifications (user_id, is_read, created_at DESC);
CREATE INDEX idx_notifications_user_type
    ON notifications (user_id, notification_type);
```

---

## Phase 2 Tables

### `outbound_sms`

All SMS messages sent from the platform.

```sql
CREATE TYPE sms_status AS ENUM (
    'pending', 'accepted', 'queued', 'sent',
    'delivered', 'failed', 'undelivered', 'permanently_failed'
);

CREATE TABLE outbound_sms (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_user_id      UUID NOT NULL REFERENCES profiles(id),
    recipient_phone     TEXT NOT NULL,
    body                TEXT NOT NULL,
    segment_count       SMALLINT NOT NULL DEFAULT 1
                            CONSTRAINT segment_count_positive CHECK (segment_count > 0),
    credit_cost         NUMERIC(10,4) NOT NULL
                            CONSTRAINT credit_cost_non_negative CHECK (credit_cost >= 0),
    status              sms_status NOT NULL DEFAULT 'pending',
    is_simulated        BOOLEAN NOT NULL DEFAULT FALSE,
    provider            TEXT
                            CONSTRAINT valid_provider CHECK (provider IN ('mock', 'twilio')),
    provider_message_id TEXT,
    idempotency_key     TEXT NOT NULL UNIQUE,
    conversation_id     UUID REFERENCES conversations(id),
    retry_count         SMALLINT NOT NULL DEFAULT 0
                            CONSTRAINT retry_count_non_negative CHECK (retry_count >= 0),
    max_retries         SMALLINT NOT NULL DEFAULT 3,
    last_retried_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outbound_sms_sender ON outbound_sms (sender_user_id, created_at DESC);
CREATE INDEX idx_outbound_sms_provider_id ON outbound_sms (provider_message_id)
    WHERE provider_message_id IS NOT NULL;
CREATE INDEX idx_outbound_sms_status ON outbound_sms (status);
CREATE INDEX idx_outbound_sms_retry
    ON outbound_sms (status, retry_count)
    WHERE status = 'failed' AND retry_count < max_retries;
```

---

### `sms_delivery_events`

Immutable log of all provider delivery status callbacks.

```sql
CREATE TABLE sms_delivery_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbound_sms_id     UUID NOT NULL REFERENCES outbound_sms(id),
    provider_message_id TEXT NOT NULL,
    provider_status     TEXT NOT NULL,
    mapped_status       sms_status NOT NULL,
    provider_timestamp  TIMESTAMPTZ,
    raw_payload         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT delivery_event_idempotent
        UNIQUE (provider_message_id, provider_status)
);

CREATE INDEX idx_delivery_events_sms_id ON sms_delivery_events (outbound_sms_id);
CREATE INDEX idx_delivery_events_provider_id ON sms_delivery_events (provider_message_id);
```

---

### `inbound_sms`

SMS messages received from provider webhooks.

```sql
CREATE TABLE inbound_sms (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_message_id TEXT NOT NULL UNIQUE,
    from_phone          TEXT NOT NULL,
    to_number           TEXT NOT NULL,
    body                TEXT NOT NULL,
    conversation_id     UUID REFERENCES conversations(id),
    matched_user_id     UUID REFERENCES profiles(id),
    is_matched          BOOLEAN NOT NULL DEFAULT FALSE,
    received_at         TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inbound_sms_from_phone ON inbound_sms (from_phone);
CREATE INDEX idx_inbound_sms_conversation ON inbound_sms (conversation_id)
    WHERE conversation_id IS NOT NULL;
CREATE INDEX idx_inbound_sms_unmatched ON inbound_sms (is_matched)
    WHERE is_matched = FALSE;
```

---

### `credit_accounts`

One credit account per user.

```sql
CREATE TABLE credit_accounts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
    balance     NUMERIC(12,4) NOT NULL DEFAULT 0
                    CONSTRAINT credit_balance_non_negative CHECK (balance >= 0),
    reserved    NUMERIC(12,4) NOT NULL DEFAULT 0
                    CONSTRAINT credit_reserved_non_negative CHECK (reserved >= 0),
    currency    CHAR(3) NOT NULL DEFAULT 'USD',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### `credit_transactions`

Immutable ledger of all credit movements.

```sql
CREATE TYPE credit_transaction_type AS ENUM (
    'top_up', 'deduction', 'refund',
    'reservation', 'reservation_release', 'adjustment'
);

CREATE TABLE credit_transactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credit_account_id   UUID NOT NULL REFERENCES credit_accounts(id),
    user_id             UUID NOT NULL REFERENCES profiles(id),
    transaction_type    credit_transaction_type NOT NULL,
    amount              NUMERIC(12,4) NOT NULL,
    balance_after       NUMERIC(12,4) NOT NULL,
    reference_type      TEXT,
    reference_id        UUID,
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_credit_tx_user ON credit_transactions (user_id, created_at DESC);
CREATE INDEX idx_credit_tx_account ON credit_transactions (credit_account_id);
CREATE INDEX idx_credit_tx_reference ON credit_transactions (reference_type, reference_id)
    WHERE reference_id IS NOT NULL;
```

---

### `country_capabilities`

Admin-managed per-country SMS configuration.

```sql
CREATE TABLE country_capabilities (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code                CHAR(2) NOT NULL UNIQUE,
    country_name                TEXT NOT NULL,
    outbound_enabled            BOOLEAN NOT NULL DEFAULT FALSE,
    inbound_enabled             BOOLEAN NOT NULL DEFAULT FALSE,
    alphanumeric_sender_id      BOOLEAN NOT NULL DEFAULT FALSE,
    requires_registered_sender  BOOLEAN NOT NULL DEFAULT FALSE,
    credit_cost_per_segment     NUMERIC(10,6) NOT NULL DEFAULT 0,
    notes                       TEXT,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by                  UUID REFERENCES profiles(id)
);

CREATE INDEX idx_country_capabilities_code ON country_capabilities (country_code);
```

---

## Phase 3 Tables

### `ai_usage_logs`

Metadata log for AI assistant usage. No message content stored.

```sql
CREATE TABLE ai_usage_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES profiles(id),
    feature         TEXT NOT NULL
                        CONSTRAINT valid_ai_feature CHECK (
                            feature IN ('suggest_replies', 'translate', 'rewrite',
                                        'optimise_sms', 'summarise', 'compose', 'tone_adjust')
                        ),
    model_id        TEXT NOT NULL,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    latency_ms      INTEGER,
    success         BOOLEAN NOT NULL,
    error_code      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_logs_user ON ai_usage_logs (user_id, created_at DESC);
CREATE INDEX idx_ai_logs_feature ON ai_usage_logs (feature, created_at DESC);
CREATE INDEX idx_ai_logs_success ON ai_usage_logs (success, created_at DESC);
```

---

## Automated Triggers

### `updated_at` auto-update trigger

Applied to all tables with `updated_at`:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to each mutable table:
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- (Repeat for contacts, conversations, outbound_sms, credit_accounts)
```

### Credit account auto-creation trigger

Creates a `credit_accounts` row when a new `profiles` row is inserted:

```sql
CREATE OR REPLACE FUNCTION create_credit_account_for_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO credit_accounts (user_id) VALUES (NEW.id);
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER on_profile_created_create_credit_account
    AFTER INSERT ON profiles
    FOR EACH ROW EXECUTE PROCEDURE create_credit_account_for_new_user();
```

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft — all 13 tables |
