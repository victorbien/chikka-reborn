# Database Test Plan

**Document:** CHKR-DB-007  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Proposed (suite implemented and passing)  
**Last Revised:** November 2026  

---

## Purpose

Defines how the database schema, triggers and Row Level Security are tested, what each test file proves, what the suite does not cover, and how to run it. It complements `docs/quality/test-plan.md` and `docs/quality/security-test-plan.md`.

## 1. Approach

- **Tests are plain SQL** in `supabase/tests/database/`. Each file runs inside one transaction and ends with `rollback`, so tests are isolated and leave no data. They need no test framework beyond helper functions in `supabase/tests/support/01_test_helpers.sql` (assert helpers, role switching, fake-user creation).
- **Role switching mimics the API.** `tests.as_user(uuid)` sets the JWT claim and `SET LOCAL ROLE authenticated`; `as_anon()` and `as_service()` do the same for `anon` and `service_role`. Row visibility is therefore tested exactly as a request would see it.
- **Real database, no mocks.** Constraints, triggers and policies run in PostgreSQL. Nothing external is called. Fixtures use fictional data only.
- **Deterministic.** No wall-clock assertions beyond transaction time; no random values affect outcomes.
- **Negative tests are first-class.** Most assertions check that something is refused, with the specific SQLSTATE where it matters (`23514` check, `23505` unique, `42501` privilege or RLS, `55000` state, `P0001` business rule).
- **The test suite is itself tested.** Mutation checks (section 5) break a protection on a scratch copy and require a failure.

## 2. Running the Suite

```powershell
cd supabase\tools
npm ci
npm test                 # all files, on a fresh in-memory database
node run-db.mjs --tests --only=04     # one file
```

Against Supabase Postgres, see [database-setup-guide.md](database-setup-guide.md) path B. Run the suite on every pull request that touches `supabase/`. It takes seconds.

## 3. Coverage Map

| File | Assertions | Covers |
|---|---|---|
| `01_constraints_and_triggers` | 81 | Profile bootstrap (credit rows, demo grant, preferences); username format, case-insensitive uniqueness, bio and display-name limits; E.164 domain; per-mode phone uniqueness; contact shape, self-add, duplicates, mute rule; contact request pair uniqueness; group limit (20), name rules, cross-owner membership refusal; `accept_contact_request` (atomic, recipient only, idempotent); provider configuration (single active, live needs confirmation, mock is simulation); country capability rules (no `supported` without verification, Philippines registration, one current version, positive multiplier, seeded unverified); consent immutability and `has_active_consent`; opt-out scope and lift rules; audit-log guard rails (no bodies, no unmasked numbers, immutable, retention); AI-log expiry; report rules; notification preference validation |
| `02_messaging_and_deliveries` | 62 | Idempotent conversation creation (both orders, SMS per user); gap-free `seq` assigned by the database; membership and channel checks; message validation (length, empty, SMS fields, statuses, idempotency key required); per-sender idempotency; identity immutability; delete-for-everyone consistency; delivery attempt rules (simulation flag, provider required, recipient required); `retrying` projection; **`accepted` never becomes `delivered`**; status cannot regress; first terminal state wins; skipped states allowed; ambiguous-failure correction; inbound SMS shape; chat delivered and read; delivery events dedupe and immutability; webhook dedupe, size cap, signature required; route exclusivity |
| `03_credits_ledger` | 32 | Reserve, capture, refund flow; **refund exactly once**; double reservation refused; overdraw refused (available excludes reserved); release/capture limited to what the message reserved; entry shapes; demo credits cannot be bought; adjustments need reason and actor; payment event applies once; ledger immutable; balance equals sum of ledger; **simulated messages cannot touch live credits (and the reverse)** |
| `04_rls_isolation` | 133 | RLS enabled on every table; no `anon`/`PUBLIC` privileges or policies; six server-only tables unreachable by users and admins; anonymous refusal on every table; own-profile only, no self-promotion, no status/username/AI changes; `public_profiles` visibility (everyone, contacts, private, blocked, self) and no sensitive columns; contacts and groups isolation; Chikka contacts cannot be self-created; block invisibility; conversation and message isolation for non-members; suppressed and self-hidden messages; cleared history and left members; sensitive message columns refused; clients cannot write messages, deliveries, credits; delivery visibility by party and column limits; notification and preference scoping; OTP columns unreadable; consent write refusal; credits isolation and admin read-only; AI history private, admin sees none; report workflow limits; capability admin write limits; backend-only function privileges |

Counts are assertion calls in the source; loops (for example the anonymous check over every table) execute more.

## 4. Requirements Mapped to Tests

| Requirement or rule | Tests |
|---|---|
| Unauthorised access denied (testing.md must-have) | 04: every isolation section; anonymous loop |
| Duplicate idempotency key ignored | 02: per-sender uniqueness; webhook and event dedupe |
| `accepted` is not shown as delivered | 02: `accepted` stays `accepted`; `delivered_at` empty until the receipt |
| No credit charge for simulation | 03: ledger mismatch refused; live balance unchanged |
| Refund on permanent failure, exactly once | 03: one refund per message; release only what was reserved |
| Invalid webhook signature rejected | **Backend test** (the database stores only verified events: `signature_verified_at` is required, covered in 02) |
| AC-4-004 balance never below zero | 03: overdraw and underflow refusals |
| RLS on every table, deny cross-user access | 04 structural and per-table sections |
| FR-PRIVACY-010 server-only tables | 04: server-only loop for users and admins |
| FR-SMS-004 duplicate callbacks, FR-SMSRECV-009 duplicate processing | 02: events, webhooks |
| FR-CONTACTS-005 group limits | 01 |
| FR-NOTIF-003/005 mandatory alerts cannot be disabled | 01 |

The full requirement-by-requirement review is in [requirements-traceability.md](requirements-traceability.md).

## 5. Test the Tests: Mutation Checks

During authoring, each protection below was removed on a scratch copy of the migrations and the suite was required to fail. All seven were caught.

| Broken protection | Caught by |
|---|---|
| Suppressed (blocked) messages visible to the recipient | 04 message visibility |
| Overdraw check removed from the ledger trigger | 03 (a table CHECK also backs this up, which is intended defence in depth) |
| Status regression allowed | 02 |
| `role` added to client-updatable profile columns | 04 self-promotion test |
| `anon` granted select on contacts | 04 structural grant check |
| RLS disabled on notifications | 04 structural RLS check |
| A client policy and grant added to `provider_webhooks` | 04 server-only checks |

A real defect was also found by the suite during authoring: a schema-scoped `ALTER DEFAULT PRIVILEGES … REVOKE` did not stop clients executing backend-only functions. It was fixed in the foundation migration and an explicit lockdown migration.

## 6. What This Suite Does Not Cover

| Gap | Plan |
|---|---|
| **Concurrency.** The in-process engine uses one connection, so races (two senders in one conversation, two reservations at once) are not exercised | Add a multi-connection test on real PostgreSQL in CI: parallel inserts must produce gap-free `seq`, and parallel reservations must not overdraw |
| **Engine version.** Verified on the embedded PostgreSQL, not on Supabase's hosted version | Run the same files against local Supabase (path B) and staging before release |
| **Supabase-managed behaviour.** Real `auth.users` columns, GoTrue, Realtime publications, Storage policies, the pooler | Covered by staging smoke tests and backend integration tests |
| **API-level RLS.** These tests set the role directly; they do not go through PostgREST or a signed JWT | Add `tests/rls/` API tests in the backend suite (see `row-level-security.md` testing note) |
| **Performance.** Query plans for the message list, membership checks and RLS overhead | Run `EXPLAIN` on the hot queries with representative data volumes; see `docs/quality/performance-test-plan.md` |
| **Migrations on non-empty databases** | Rehearse each production migration on a staging copy; expand-then-contract |
| **Backup and restore** | Disaster-recovery drill, not a SQL test |
| **Backend logic** (webhook signature checks, retry timing, rate limits) | pytest in the backend. The schema only supplies the storage and invariants |

Coverage targets from `testing.md` (85 % business logic, 80 % backend) apply to application code, not SQL. For the database the target is: every constraint, trigger rule and policy has at least one positive and one negative test.

## 7. Adding Tests

1. New table: add it to the structural lists in file 04 (server-only or not), add isolation tests, add constraint tests.
2. New trigger or function: add a test per rule and one test for who may call it.
3. Bug fix: add a test that fails without the fix.
4. Keep tests self-contained: create users with `tests.create_user`, never rely on seed data, end with `rollback`.

## 8. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial plan and implemented suite |
