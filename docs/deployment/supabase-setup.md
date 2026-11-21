# Supabase Setup

**Project:** Chikka Reborn
**Status:** Prepared. No hosted project has been configured or migrated from this document.
**Last Revised:** November 2026

Create **two** Supabase projects, staging and production. Never point staging at production data.

## 1. Project configuration

| Item | Setting |
|---|---|
| Region | Closest to the backend host and most users. Decision OD-008 |
| Plan | Must include daily backups. Enable Point-in-Time Recovery for production before launch (needed by [rollback-procedure.md](rollback-procedure.md)) |
| Database password | Generate a long random value; store it only in the backend's secret store |
| API keys | Copy the project URL, the anon (publishable) key and the service-role (secret) key into the backend's secret store. The service-role key bypasses RLS and never goes to Vercel or the browser |
| JWT signing | Use asymmetric signing keys (ES256). The backend reads the public keys from `<project url>/auth/v1/.well-known/jwks.json`, so leave `SUPABASE_JWT_SECRET` unset. Legacy HS256 projects set it instead |
| Data API (PostgREST) | The frontend does not use it; the backend connects directly to Postgres. **Disable it** or expose no schema (Settings -> API). This closes audit finding SEC-002 (direct reads of `public_profiles`, direct writes of profile text) |
| Network | If available, restrict direct database access to the backend host's addresses |

## 2. Authentication settings

Set in Dashboard -> Authentication, or with `supabase config push` from `supabase/config.toml` (review the diff first; the local file uses `localhost` URLs).

| Setting | Value | Why |
|---|---|---|
| Site URL | `https://<app domain>` | Email templates build links from `{{ .SiteURL }}` |
| Redirect URLs | `https://<app domain>/auth/verify-email` and `https://<app domain>/auth/reset-password` | The backend passes these as `redirect_to`. Add the staging equivalents to the staging project only. Remove `localhost` entries from production |
| Confirm email | On (`enable_confirmations = true`) | No session until the address is verified |
| Secure email change | On (`double_confirm_changes`) | |
| Password rules | Minimum 8, lower + upper + digit | Matches the backend validator |
| Email OTP / link expiry | 3600 s | Matches `config.toml` |
| Email rate limits | Keep Supabase defaults or lower | The backend adds its own per-IP and per-email limits |
| Phone sign-in | Off | The backend owns mobile verification |
| Email templates | Paste `supabase/templates/confirmation.html` and `recovery.html` | They link to `/auth/verify-email?token_hash=...` and `/auth/reset-password?token_hash=...`, which the SPA posts to the backend |
| Custom SMTP | **Required for real users** | Supabase's built-in sender is rate-limited and meant for testing. Configure your own SMTP provider with SPF, DKIM and DMARC on the sending domain |
| Public sign-ups | Keep on only while the backend registration path is the intended one. Direct Auth sign-ups skip consent capture (SEC-002). If your plan supports a before-user-created hook, record consent there or disable public sign-up and create users from the backend |

Test both email links on staging before production. Wrong Site URL or redirect entries are the most common cause of "link goes to localhost" and "redirect not allowed" errors.

## 3. Database migrations

Migrations are plain SQL in `supabase/migrations/`, applied in filename order, once. Nothing applies them automatically. **Applying to production needs explicit human approval** (development principles), and so does anything destructive.

Current set: 22 files, `20261110000001` to `20261120000001`. See [database-migrations.md](../database/database-migrations.md).

### Staging

```powershell
# 1. Prove the full set on a throwaway database first
cd supabase\tools; npm ci; node run-db.mjs --tests     # expects ALL OK

# 2. Link and review what would run
supabase link --project-ref <staging-ref>
supabase db push --dry-run

# 3. Apply
supabase db push
```

### Production

Run only when all of these are true; record who approved and when.

- [ ] The same migrations ran on staging and the app was exercised for at least 24 hours
- [ ] Backups confirmed, PITR enabled, restore point noted (time in UTC)
- [ ] Each new migration is additive or backward-compatible with the version still deployed
- [ ] A named person approved the production push
- [ ] Off-peak window

Then `supabase db push --project-ref <production-ref>` (use `--dry-run` first), and run the verification in section 4.

### Migration `20261120000001` needs a follow-up

It adds `ck_profiles_avatar_path` as `NOT VALID`. After applying, find and clear any legacy rows, then validate:

```sql
select id from public.profiles
 where avatar_path is not null
   and avatar_path !~ ('^' || id::text || '/[0-9a-f]{32}\.webp$');
-- update those rows' avatar_path to null (a person reviews the list first), then:
alter table public.profiles validate constraint ck_profiles_avatar_path;
```

### Seed data

`supabase/seed/` is for development only. Do not run it on staging or production. The reference data the app needs (countries, system settings) comes from migration `20261110000013_reference_data.sql`.

## 4. Verifying RLS and database permissions

Run after every production migration, as the SQL editor or `psql` with the backend's connection.

```sql
-- 1. RLS is on for every table in public (expect zero rows)
select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;

-- 2. anon has no table privileges (expect zero rows)
select table_name, privilege_type from information_schema.role_table_grants
 where grantee = 'anon' and table_schema = 'public';

-- 3. Server-only tables have no client grants (expect zero rows)
select table_name from information_schema.role_table_grants
 where grantee = 'authenticated' and table_schema = 'public'
   and table_name in ('system_settings','provider_webhooks','message_delivery_events',
                      'sms_opt_outs','audit_logs','rate_limit_counters');

-- 4. Clients cannot write avatar_path or role/status (expect zero rows)
select column_name from information_schema.column_privileges
 where grantee = 'authenticated' and table_name = 'profiles' and privilege_type = 'UPDATE'
   and column_name in ('avatar_path','role','status','username','ai_enabled');

-- 5. Private functions are not callable by clients (expect zero rows)
select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace
 where n.nspname = 'private'
   and (has_function_privilege('anon', p.oid, 'execute')
        or has_function_privilege('authenticated', p.oid, 'execute'))
   and p.proname not in ('is_admin', 'valid_notification_overrides', 'can_see_attachment_message');
```

The same properties are asserted by `supabase/tests/database/*.test.sql`, which run against a local PGlite database, not against Supabase's Postgres. The queries above are the check on the hosted database. Also create two test accounts and confirm from the app that user A cannot open user B's conversation by ID (expect 404).

## 5. Storage configuration

Migrations `20261111000001` and `20261111000003` create two buckets **if** `storage.buckets` exists. Confirm both in Dashboard -> Storage:

| Bucket | Public | Size limit | Allowed types |
|---|---|---|---|
| `avatars` | No | 512 KB | `image/webp` |
| `message-attachments` | No | 10 MB | JPEG, PNG, WebP, GIF, PDF |

- Both are private and have **no** `storage.objects` policies for clients. Only the backend (service role) reads and writes; users receive short-lived signed URLs. Verify there are no policies on `storage.objects` granting `anon` or `authenticated` access.
- Bucket names must match `AVATAR_BUCKET` and `ATTACHMENT_BUCKET`.
- Avatars are re-encoded to WebP by the backend before upload.

## 6. Values to hand to the backend

| Variable | Source |
|---|---|
| `SUPABASE_URL` | Settings -> API -> Project URL |
| `SUPABASE_ANON_KEY` | Settings -> API keys |
| `SUPABASE_SERVICE_ROLE_KEY` | Settings -> API keys (secret) |
| `DATABASE_URL` | Connect -> Session pooler or Direct |

Rotate the service-role key and the database password if they were ever pasted into a chat, ticket or shared file. `docs/quality/test-report.md` (DEF-01) recommends rotating the values that once sat in a tracked file.
