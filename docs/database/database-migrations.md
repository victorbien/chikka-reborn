# Database Migrations

**Document:** CHKR-DB-003  
**Project:** Chikka Reborn  
**Version:** 2.0  
**Status:** Proposed (migrations exist and apply cleanly to an empty database)  
**Last Revised:** November 2026  

---

## Purpose

Defines how Chikka Reborn database changes are written, ordered, applied and, when needed, corrected. The migration files are in `supabase/migrations/`. Setup steps for a developer are in [database-setup-guide.md](database-setup-guide.md).

## 1. Principles

- Every schema change is a migration file. No manual changes in any environment.
- A migration is one transaction (`begin; … commit;`). It succeeds completely or not at all.
- A table, its constraints, indexes, triggers, grants, RLS enablement and policies are created in the same migration.
- An applied migration is never edited. Fix forward with a new migration. (The files below were authored together and have not been applied to any shared environment yet.)
- Destructive changes (drop, truncate, bulk delete) and any production application need explicit human approval.
- Prefer expand-then-contract: add the new thing, move code over, remove the old thing in a later release.
- Reference data that every environment needs is a migration (idempotent). Development data is a seed and never runs in staging or production.

## 2. Naming

`supabase/migrations/YYYYMMDDHHMMSS_description.sql`, UTC timestamp, one concern per file. Each file starts with a header: migration name, phase, description, dependencies, rollback note.

## 3. Current Sequence

| File | Creates | Depends on |
|---|---|---|
| `20261110000001_foundation` | `private` schema, `e164` domain, `set_updated_at`, `reject_mutation`, masking helpers, safe function defaults | Supabase roles |
| `20261110000002_profiles` | `profiles`, `auth.users` trigger, `is_admin()`, RLS | foundation |
| `20261110000003_platform_configuration` | `system_settings`, `provider_configurations`, `sms_country_capabilities` | profiles |
| `20261110000004_phone_numbers_and_consents` | `phone_numbers`, `user_consents`, `has_active_consent()` | profiles |
| `20261110000005_contacts` | `contacts`, `contact_requests`, `contact_groups`, `contact_group_members`, `user_blocks`, `public_profiles`, `accept_contact_request()` | profiles |
| `20261110000006_conversations` | `conversations`, `conversation_members`, `get_or_create_*_conversation()` | profiles |
| `20261110000007_messages` | `messages`, `message_hides`, `message_segments`, seq assignment | conversations, capabilities |
| `20261110000008_message_deliveries` | `message_deliveries`, `provider_webhooks`, `message_delivery_events`, `sms_routes`, `sms_opt_outs`, status triggers | messages, provider configurations |
| `20261110000009_credits` | `messaging_credits`, `credit_transactions`, ledger trigger | messages, capabilities |
| `20261110000010_notifications` | `notification_preferences`, `notifications` | profiles |
| `20261110000011_ai_reports_audit` | `ai_assistance_logs`, `abuse_reports`, `audit_logs`, message to AI-log foreign key | messages |
| `20261110000012_profile_bootstrap` | Trigger creating credit rows, preferences and the demo grant for each new profile | credits, notifications |
| `20261110000013_reference_data` | System settings, mock (active) and Twilio (inactive) provider rows, six UNVERIFIED country rows | platform configuration |
| `20261110000014_lockdown_private_functions` | Explicit `EXECUTE` grants for the `private` schema | all |
| `20261110000015_rate_limit_counters` | `rate_limit_counters` | foundation |
| `20261111000001_avatars_bucket` | private Storage bucket `avatars` (WebP only, 512 KB); no client policies, backend writes with the service role; skipped where `storage` is absent | 20261110000002 |

Development seed: `supabase/seed/01_dev_seed.sql`. Test support and tests: `supabase/tests/`.

Tables are grouped by dependency rather than by phase because all tables must exist before the backend modules are built. Phase tags on each file show when the behaviour is first used. The old per-phase plan (outbound_sms, credit_accounts, and so on) no longer applies.

## 4. Applying Migrations

| Environment | Command | Rule |
|---|---|---|
| Local | `supabase db reset` (CLI) or `npm run migrate` in `supabase/tools` (no Docker) | Rebuilds from scratch. Safe. |
| Staging | `supabase db push --project-ref <staging>` | Automatic in CI is acceptable. Staging data is disposable. |
| Production | `supabase db push --project-ref <production>` | **Human operator only.** Never from CI. Steps below. |

Production checklist:

1. The same migration set has run on staging and the full test suite passed there.
2. A recent point-in-time backup is confirmed.
3. The change is backward compatible with the code currently deployed.
4. For destructive changes: second reviewer, 24 hours on staging, written sign-off (section 6).
5. Apply, then check `/readyz` and a short smoke test.

## 5. Rollback

Supabase does not roll migrations back. Options, in order of preference:

1. **Forward fix:** a new migration that reverses or corrects the change.
2. **Point-in-time restore** if data was damaged.

Each file states how to reverse it. For these migrations the answer is "forward-fix only" because dropping a table or schema destroys data.

## 6. Destructive Change Protocol

Applies to `DROP`, `TRUNCATE`, column removal, type narrowing, bulk `DELETE`, and constraints that could reject existing rows.

1. Review by a second engineer.
2. Run on staging for 24 hours.
3. Confirm point-in-time recovery.
4. Confirm deployed code no longer depends on what is removed.
5. Split into steps: add (expand), migrate data, remove (contract).
6. Written approval from the engineering lead before production.

Adding a `CHECK` or `NOT NULL` to a table that has data is treated as risky: add it `NOT VALID` first, fix the data, then `VALIDATE CONSTRAINT`.

## 7. Seed Data

| Kind | Location | Runs in |
|---|---|---|
| Reference data (settings, provider rows, UNVERIFIED capabilities) | A migration, idempotent (`ON CONFLICT DO NOTHING`) | Every environment |
| Development users and sample conversations | `supabase/seed/01_dev_seed.sql` | Local and disposable dev only |

The development seed refuses to run when `app.environment` is `production` or `staging`. It contains only fictional people, `.test` emails and numbers in the reserved `+1 555 01xx` range. Never put real numbers or personal data in seeds or tests.

Every country capability is seeded as `requires_verification`. Nothing is `supported` until an administrator records verification (the database rejects `supported` without it). The Philippines is additionally marked `not_registered` for sender registration.

## 8. Verification

Each change must pass, on an empty database: all migrations apply in order; the SQL tests in `supabase/tests/database/` pass; the seed applies. See [database-test-plan.md](database-test-plan.md).

## 9. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft |
| 2.0 | November 2026 | Kiro (Principal Architect) | Replaced planned sequence with the implemented 15 migrations |
