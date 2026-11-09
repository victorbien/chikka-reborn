# Database Migrations

**Document:** CHKR-DB-003  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Defines the migration strategy, file naming convention, sequencing, and safety rules for all Chikka Reborn database schema changes.

## Scope

All Supabase migration files in `supabase/migrations/`. All environments.

---

## 1. Migration Principles

- Every schema change is a migration file. No ad hoc SQL in any environment.
- Migrations are **atomic**: they succeed in full or fail in full. No partial migrations.
- Migrations are **sequential**: each file builds on the previous.
- Migrations include their **RLS policies**: a table is never created without its access policies.
- **Destructive migrations require human approval** before production application.
- Migration files are **never edited after being applied** to any environment. Fix forward with a new migration.

---

## 2. File Naming Convention

```
supabase/migrations/YYYYMMDDHHMMSS_description.sql
```

Examples:
```
20261101000000_create_profiles.sql
20261101000001_create_contacts.sql
20261115000000_create_outbound_sms.sql
20261201000000_create_ai_usage_logs.sql
```

The timestamp prefix ensures lexicographic ordering matches chronological order. Use UTC time. Increment by 1 second minimum between files created in the same session.

---

## 3. Migration Sequence

### Phase 1 Migrations

| File | Creates | Notes |
|---|---|---|
| `20261101000000_create_enum_types.sql` | All PostgreSQL ENUM types | Must be first — types referenced by tables |
| `20261101000001_create_profiles.sql` | `profiles` + indexes + RLS + `updated_at` trigger | Depends on `auth.users` (Supabase built-in) |
| `20261101000002_create_contacts.sql` | `contacts` + indexes + RLS | Depends on `profiles` |
| `20261101000003_create_conversations.sql` | `conversations` + `conversation_participants` + indexes + RLS | Depends on `profiles` |
| `20261101000004_create_messages.sql` | `messages` + indexes + RLS + Realtime publication | Depends on `conversations`, `profiles` |
| `20261101000005_create_notifications.sql` | `notifications` + indexes + RLS + Realtime publication | Depends on `profiles` |
| `20261101000006_create_credit_accounts_trigger.sql` | Auto-create `credit_accounts` trigger on profile insert | Note: credit_accounts table created in Phase 2 — this trigger added in Phase 2 |
| `20261101000007_seed_profiles_rls.sql` | Additional RLS policies for profile search | Depends on `profiles` |

### Phase 2 Migrations

| File | Creates | Notes |
|---|---|---|
| `20261115000000_create_outbound_sms.sql` | `outbound_sms` + indexes + RLS | Depends on `profiles`, `conversations` |
| `20261115000001_create_sms_delivery_events.sql` | `sms_delivery_events` + indexes + RLS | Depends on `outbound_sms` |
| `20261115000002_create_inbound_sms.sql` | `inbound_sms` + indexes + RLS + Realtime publication | Depends on `conversations`, `profiles` |
| `20261115000003_create_credit_accounts.sql` | `credit_accounts` + `credit_transactions` + indexes + RLS + trigger | Depends on `profiles` |
| `20261115000004_create_country_capabilities.sql` | `country_capabilities` + indexes + RLS | No FK dependencies |
| `20261115000005_seed_country_capabilities.sql` | Initial country data | Depends on `country_capabilities` |
| `20261115000006_add_outbound_sms_realtime.sql` | Add `outbound_sms` to Realtime publication | Depends on `outbound_sms` |

### Phase 3 Migrations

| File | Creates | Notes |
|---|---|---|
| `20261201000000_create_ai_usage_logs.sql` | `ai_usage_logs` + indexes + RLS | Depends on `profiles` |

---

## 4. Migration File Template

```sql
-- Migration: YYYYMMDDHHMMSS_description
-- Phase: X
-- Description: What this migration does
-- Dependencies: List of tables/types this depends on
-- Rollback: How to reverse this migration if needed

BEGIN;

-- ============================================================
-- 1. Schema changes
-- ============================================================

CREATE TABLE example (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- ... columns ...
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_example_... ON example (...);

-- ============================================================
-- 2. Triggers
-- ============================================================

CREATE TRIGGER update_example_updated_at
    BEFORE UPDATE ON example
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- ============================================================
-- 3. Row Level Security
-- ============================================================

ALTER TABLE example ENABLE ROW LEVEL SECURITY;

CREATE POLICY "example_select_own" ON example
    FOR SELECT USING (auth.uid() = user_id);

-- ============================================================
-- 4. Realtime (if applicable)
-- ============================================================

-- ALTER PUBLICATION supabase_realtime ADD TABLE example;

COMMIT;
```

---

## 5. Applying Migrations

### Development
```bash
# Apply all pending migrations to local/dev Supabase
supabase db push --project-ref <dev-project-ref>

# Or via Supabase CLI local setup
supabase db reset  # Drops and rebuilds from migrations
```

### Staging
```bash
# Apply to staging (safe — no production data)
supabase db push --project-ref <staging-project-ref>
```

### Production
```bash
# Production migration — requires explicit operator command
# Step 1: Verify migration on staging ✓
# Step 2: Confirm PITR backup available ✓
# Step 3: Confirm migration is backward-compatible with deployed code ✓
# Step 4: Apply

supabase db push --project-ref <production-project-ref>

# Step 5: Verify application is healthy after migration
# GET /health → database: connected
```

**Production migrations are never triggered automatically by CI/CD.** They require a human operator to run the command.

---

## 6. Destructive Migration Protocol

Migrations that DROP columns, DROP tables, TRUNCATE, or make breaking schema changes require:

1. **Review** — migration reviewed by at least one other engineer.
2. **Staging run** — migration applied and verified on staging for minimum 24 hours.
3. **Backup confirmation** — point-in-time recovery confirmed available for production.
4. **Backward-compatibility check** — deployed application code must not depend on the column/table being removed.
5. **Multi-step deploy** if needed:
   - Step A: Add new column; deploy code that reads both old and new.
   - Step B: Migrate data; deploy code that reads only new.
   - Step C: Drop old column.
6. **Human sign-off** — explicit approval from engineering lead before production execution.

---

## 7. Rollback Strategy

Supabase does not support automatic migration rollback. Instead:

- **Forward fix:** Create a new migration that reverses the change.
- **PITR restore:** If the migration caused data corruption, restore the production database from the point-in-time backup taken before the migration.
- For each migration, the template includes a `-- Rollback:` comment describing how to reverse it.

---

## 8. Seed Data

Production seed data (initial `country_capabilities` records) is in `supabase/seed.sql`:

```sql
-- supabase/seed.sql
-- Run once on new environment setup, not as a migration

INSERT INTO country_capabilities
    (country_code, country_name, outbound_enabled, inbound_enabled,
     alphanumeric_sender_id, requires_registered_sender, credit_cost_per_segment, notes)
VALUES
    ('PH', 'Philippines', TRUE, FALSE, FALSE, TRUE, 0.05,
     'Sender registration required. Inbound availability requires carrier verification.'),
    ('US', 'United States', TRUE, TRUE, TRUE, FALSE, 0.03, NULL),
    ('AU', 'Australia', TRUE, TRUE, FALSE, FALSE, 0.04, NULL),
    ('AE', 'United Arab Emirates', TRUE, FALSE, FALSE, FALSE, 0.06,
     'Inbound SMS not supported on most routes.'),
    ('SG', 'Singapore', TRUE, TRUE, FALSE, FALSE, 0.04, NULL),
    ('GB', 'United Kingdom', TRUE, TRUE, TRUE, FALSE, 0.04, NULL)
    -- Add more as verified with SMS provider
ON CONFLICT (country_code) DO NOTHING;
```

---

## 9. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
