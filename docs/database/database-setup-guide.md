# Database Setup Guide

**Document:** CHKR-DB-005  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Proposed  
**Last Revised:** November 2026  

---

## Purpose

Step-by-step instructions to create, test and reset the Chikka Reborn database. Choose the path that matches what you have installed.

| Path | Needs | Use it for |
|---|---|---|
| A. In-process check | Node.js 20+ | Fast check that migrations, seed and tests pass. No Docker, no accounts. |
| B. Local Supabase | Docker Desktop, Supabase CLI | Day-to-day development with Auth, Studio and the real Supabase Postgres |
| C. Hosted staging | Supabase account, CLI | Shared testing. Simulation mode only |
| D. Production | Human operator | Controlled release. Never automated |

Nothing in this guide sends an SMS or calls an external service.

## 1. Repository Layout

```text
supabase/
├── config.toml                 CLI settings (database port, seed path)
├── migrations/                 15 ordered SQL files (schema, RLS, triggers, reference data)
├── seed/01_dev_seed.sql        Fictional development data. Dev only
├── tests/
│   ├── support/                Supabase stub (plain Postgres only) and test helpers
│   └── database/               SQL tests
└── tools/                      Node scripts: run-db, schema reference generator
```

## 2. Path A: In-Process Check (No Docker)

```powershell
cd supabase\tools
npm ci
npm run migrate      # apply all migrations to an empty in-memory database
npm run seed         # migrations + development seed
npm test             # migrations + SQL tests (do not combine with seed)
npm run schema:docs  # regenerate docs/database/schema-reference.md
```

Expected: every line says `ok` and the run ends with `ALL OK`. Each run starts from an empty database, so there is nothing to clean up.

`npm ci` installs one development-only package, `@electric-sql/pglite` (pinned to 0.5.16), which embeds PostgreSQL. It is used only by these scripts. It reports its PostgreSQL version at the start of each run; Supabase hosts its own version, so also run Path B or C before release.

The tests and the seed use the same sample usernames, so run them separately. Tests expect a database with no seed data.

## 3. Path B: Local Supabase

1. Install Docker Desktop and the [Supabase CLI](https://supabase.com/docs/guides/local-development).
2. From the repository root:

```powershell
supabase start                 # starts Postgres, Auth, Studio, Realtime, Storage locally
supabase db reset              # drops the local database, applies migrations, then runs seed/*.sql
```

3. Open Studio at the URL printed by `supabase start` to browse tables.
4. To run the SQL tests against the local database, apply the test support files first, then each test (the stub is **not** needed because Supabase provides the roles and `auth.uid()`):

```powershell
$db = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
psql $db -v ON_ERROR_STOP=1 -f supabase/tests/support/01_test_helpers.sql
Get-ChildItem supabase/tests/database/*.test.sql | Sort-Object Name | ForEach-Object { psql $db -v ON_ERROR_STOP=1 -f $_.FullName }
```

The tests expect a database **without** seed data. Set `enabled = false` under `[db.seed]` in `supabase/config.toml` (or use a scratch database), run `supabase db reset`, then run the tests. With seed data present the first test fails on username collisions.

Each test file runs inside a transaction and rolls back, so it leaves nothing behind. These psql commands are written from the documented defaults and were not run during authoring (no Docker or psql on the authoring machine); the same SQL files were verified through Path A.

### Development accounts

The seed creates five fictional users (all `@chikka.test`) with fixed IDs:

| User | Role / status | Purpose |
|---|---|---|
| `admin@chikka.test` | admin, active | Admin policies |
| `alice@chikka.test` | user, active, PH | Main sample: contacts, a Chikka chat, a simulated SMS thread |
| `bob@chikka.test` | user, active, SG | Chikka contact of Alice |
| `carol@chikka.test` | user, pending verification | Pending contact request |
| `dave@chikka.test` | user, suspended | Suspension behaviour |

When pgcrypto is available the seed sets the development-only password `dev-password-only`. Never reuse it anywhere else. Phone numbers are fictional (`+1 555 01xx`).

## 4. Path C: Hosted Staging

1. Create a separate Supabase project for staging. Do not share it with production.
2. Link and push:

```powershell
supabase link --project-ref <staging-project-ref>
supabase db push
```

3. Do **not** run the development seed on staging. If sample data is needed, create it through the application in simulation mode.
4. Keep `SMS_PROVIDER_MODE=mock`. The reference-data migration already makes the mock provider the only active provider.

## 5. Path D: Production

Production migrations are applied by a human operator only, after the checklist in [database-migrations.md](database-migrations.md) section 4. Never from CI. Never with the seed.

## 6. Configuration the Backend Needs

| Setting | Source | Notes |
|---|---|---|
| Database URL for requests | Supabase connection string, **transaction pooler** | asyncpg with prepared-statement caching off |
| Database URL for `LISTEN`/job wake-ups | Direct or session-mode connection | The transaction pooler cannot hold `LISTEN` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase project API settings | Backend only. Bypasses RLS. Never in the frontend or logs |
| `SUPABASE_JWT_SECRET` / JWKS | Supabase project API settings | Backend verifies user tokens |
| `SUPABASE_ANON_KEY` | Supabase project API settings | Safe for the frontend; has no table privileges |
| `SMS_PROVIDER_MODE` | Environment | `mock` by default |

Secrets live in environment variables or a secret manager. `provider_configurations.secret_ref` stores only the *name* of a secret.

## 7. Creating the First Administrator

An administrator is a profile with `role = 'admin'`. Clients cannot set this. Use a one-off, audited operator step:

1. Create the user normally (sign up or the Auth dashboard).
2. As the database owner, run:

```sql
update public.profiles
   set role = 'admin', status = 'active'
 where id = '<user uuid>';

insert into public.audit_logs (category, action, outcome, target_type, target_id, reason)
values ('admin', 'admin.role.granted', 'success', 'profile', '<user uuid>', 'initial administrator, approved by <name>');
```

Granting the admin role changes authorisation, so it needs explicit human approval.

## 8. Common Tasks

| Task | How |
|---|---|
| Add a column or table | New migration file with a later timestamp. Include RLS, grants, indexes, tests. Never edit an applied migration |
| Reset local data | `supabase db reset` (Path B) or just re-run Path A |
| See what a policy allows | `schema-reference.md` (policies per table), `row-level-security.md` (matrix) |
| Check masked phone output | `select private.mask_phone('+15550109876');` returns `+15****9876` |
| Regenerate docs | `npm run schema:docs` in `supabase/tools` |

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `permission denied for table …` from the app with a user token | Expected if the table is server-only or the column is not granted. Use the backend or name allowed columns |
| `permission denied for function …` | A new function was added without an explicit grant. Add it to a lockdown-style migration |
| `duplicate key … uq_profiles_username_lower` when running tests | The seed data is present. Reset and run tests without seed |
| `new row violates check constraint ck_sms_cap_verified_for_support` | Tried to mark a country `supported` without `verified_at` and `verified_by` |
| `STATUS_REGRESSION` | A status update would move backwards. Provider events must be applied in rank order or stored as ignored |
| `INSUFFICIENT_CREDITS` / `LEDGER_MISMATCH` | Reservation larger than the available balance / simulated message used the live ledger (or the reverse) |

## 10. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial guide |
