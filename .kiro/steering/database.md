---
inclusion: always
---

# Database

Detailed docs: `docs/database-design.md`, `docs/database/database-schema.md`, `entity-relationships.md`, `database-migrations.md`, `row-level-security.md`.

## Naming

- Tables: plural `snake_case` (`sms_messages`). Columns: `snake_case`. Booleans: `is_`/`has_` prefix.
- Primary key: `id uuid` (default `gen_random_uuid()`). Foreign keys: `<entity>_id`.
- Indexes: `idx_<table>_<columns>`. Constraints: `fk_`, `uq_`, `ck_` prefixes.
- Every table has `created_at` and `updated_at` (`timestamptz`, maintained by trigger). Add `deleted_at` for soft-deleted sensitive records.
- Enums for statuses via check constraints or enum types, matching the status semantics in `sms-provider-guidelines.md`.

## Migrations

- All schema changes are Supabase migrations in `supabase/migrations/`, timestamp-ordered, one concern each.
- Never edit an applied migration; add a new one. Never change schema manually.
- Include RLS policies in the creating migration. Seed data lives in `supabase/seed/`.
- Destructive changes (DROP, TRUNCATE, bulk DELETE) and production application need explicit human approval. Prefer expand-then-contract changes.

## Indexing

- Index foreign keys and columns used in frequent filters, joins, and ordering (e.g. `(conversation_id, created_at)`).
- Unique indexes enforce idempotency keys and provider message IDs.
- Use partial indexes for soft-deleted data. Do not add speculative indexes; justify with a query.

## Foreign Keys

- Declare foreign keys for every relationship. Choose `ON DELETE` explicitly (`RESTRICT` by default; `CASCADE` only for owned child data; `SET NULL` for optional links).
- Audit and credit ledger rows must survive user deletion (anonymise instead of cascade).

## RLS Policies

- Enable RLS on every table; no table is exposed without policies.
- Policies are per operation (SELECT/INSERT/UPDATE/DELETE) and keyed on `auth.uid()`.
- Server-only tables (webhook events, audit logs) permit no client access.
- Test policies for both allowed and denied cases.

## Transactions and Consistency

- One service operation = one transaction. Repositories do not commit; the unit of work does.
- Credit deduction/refund and ledger entry commit atomically; the ledger is append-only.
- Status updates only move forward (`queued -> sent -> delivered`, or failed); reject out-of-order regressions.
- Use row locks or optimistic versioning for balance changes. Handle duplicates through unique constraints, not check-then-insert.
