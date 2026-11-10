# Row Level Security

**Document:** CHKR-DB-004  
**Project:** Chikka Reborn  
**Version:** 2.0  
**Status:** Proposed (implemented and tested in `supabase/migrations/` and `supabase/tests/database/`)  
**Last Revised:** November 2026  

---

## Purpose

Documents who can read and write what, at the database level. Policies are defined in the same migration that creates each table. They back the backend's own authorisation checks; they do not replace them (see ADL-011).

## 1. Model

There are three database roles in play.

| Role | Who | Access |
|---|---|---|
| `anon` | Anyone without a session | **Nothing.** No table privileges, no policies. |
| `authenticated` | A signed-in user, through the API key and their JWT | Narrow, column-level grants plus row policies keyed on `auth.uid()`. |
| `service_role` | The FastAPI backend | Bypasses RLS and holds the writes. Its key is backend-only and never reaches the browser. |

Administrators are `authenticated` users whose `profiles.role = 'admin'`. There is no administrator database role.

### Principles

1. **RLS is enabled on every table**, and a test fails the build if one is missed.
2. **Deny by default.** With RLS on and no policy, access is refused. Six tables deliberately have no policy at all (server-only).
3. **Two layers of restriction.** Row policies decide *which rows*. Column grants decide *which columns*. Sensitive columns (OTP state, provider IDs, block suppression, AI flags, request hashes) are not granted to clients even for their own rows.
4. **Writes with rules are backend-only.** Anything that needs rate limits, idempotency, block handling, consent, credit movement, audit logging or re-authentication is written by the backend. Clients keep direct write access only for harmless self-service preferences.
5. **The role comes from the database.** `private.is_admin()` reads `profiles` on every call. JWT claims such as `user_metadata` are user-editable and are never trusted.
6. **Performance.** Policies call `(select auth.uid())` so PostgreSQL evaluates it once per statement. Membership checks use the `(conversation_id, user_id)` primary key.
7. **Backend checks still apply.** The backend uses a privileged role, so RLS does not protect backend queries. It protects every path that reaches the database with a user's token, and limits damage if a key leaks.

### Helper functions (schema `private`, not exposed by the API)

| Function | Used for | Callable by |
|---|---|---|
| `private.is_admin()` | Admin policies | `authenticated`, `service_role` (security definer, fixed `search_path`) |
| `private.valid_notification_overrides(jsonb)` | CHECK on notification preferences | `authenticated`, `service_role` |
| `private.accept_contact_request`, `get_or_create_chikka_conversation`, `get_or_create_sms_conversation`, `has_active_consent`, `is_blocked_between`, `mask_phone`, `contains_unmasked_phone` | Backend operations | `service_role` only |

PostgreSQL grants `EXECUTE` on new functions to `PUBLIC` by default, and a schema-scoped default-privileges revoke does not remove that. The foundation migration revokes it for the migration role, and a lockdown migration states every grant explicitly. A test calls these functions as a signed-in user and requires a refusal.

## 2. Access Matrix

S = select, I = insert, U = update, D = delete. "Own" means the row belongs to `auth.uid()`. "Backend" means `service_role` only.

| Table | Signed-in user | Administrator (extra) |
|---|---|---|
| `profiles` | S own. U own, only: display name, bio, avatar path, country, language, time zone, ui mode, theme, display options, visibility, presence settings, receipts, typing, discoverability. **Not** username, role, status, AI flag, deletion fields | S all rows. No write |
| `public_profiles` (view) | S id, username, display name, avatar, country of profiles that are active, named, and visible to the caller (self, `everyone`, or `contacts` when the owner has the caller as a contact). Hidden if the owner blocked the caller | – |
| `phone_numbers` | S own, excluding all OTP columns | – |
| `user_consents` | S own | – |
| `contacts` | S own. I own SMS contacts only. U own: name, favourite, mute, recent-cleared. D own | – |
| `contact_requests` | S where sender or recipient | – |
| `contact_groups` | S, I, U, D own | – |
| `contact_group_members` | S, I, D own; U position. Composite foreign keys reject cross-owner links | – |
| `user_blocks` | S own as blocker. A blocked user sees nothing | – |
| `abuse_reports` | S own as reporter. The reported user sees nothing | S all. U status, resolution note, resolver, resolved time only. Evidence and ownership are immutable |
| `conversations` | S where an active member | **None.** Admins review conversations only through report snapshots |
| `conversation_members` | S own rows only (hides other members' read positions). U own: pin, archive, mark unread, mute, per-conversation AI switch. Read markers and clearing are backend-only | – |
| `messages` | S in conversations where an active member, **except** messages at or before the member's `cleared_before_seq`, messages the member hid, and messages suppressed by a block (unless the member is the sender). Columns `is_ai_assisted`, `ai_assistance_log_id`, `request_hash`, `suppressed_at`, `suppressed_reason`, `admin_resolved_at`, `admin_resolved_by`, `admin_resolution_note` are not granted. No client writes | **None** |
| `message_hides` | S own | – |
| `message_segments` | S exactly when the parent message is visible | – |
| `message_deliveries` | S where the user is the sender of the message or the recipient. Columns limited to status, timestamps and failure class; provider IDs, error codes, HTTP status and lease are server-only | S all (same columns) |
| `sms_routes` | S own | S all |
| `sms_country_capabilities` | S current versions | S all versions. I new versions. U only `is_current` |
| `provider_configurations` | None | S all |
| `messaging_credits` | S own, balance columns only | S all |
| `credit_transactions` | S own, excluding payment references and actor | S all (same columns). No write: adjustments go through the audited backend |
| `notification_preferences` | S own. U own: overrides, quiet hours, previews, threshold. Bounce counters are server-only | – |
| `notifications` | S own. U own: `read_at`, `dismissed_at` | – |
| `ai_assistance_logs` | S own. D own (delete one entry or clear all) | **None.** Administrators see aggregates computed by the backend, never content |
| `provider_webhooks` | None | None |
| `message_delivery_events` | None | None |
| `sms_opt_outs` | None | None |
| `audit_logs` | None | None. Read through the backend |
| `system_settings` | None | None |
| `rate_limit_counters` | None | None |

### Why the administrator column is short

The brief asks for explicitly controlled administrator permissions. The database therefore grants an administrator only what a dashboard needs to read: profiles, delivery state, credits, reports, routes, provider configuration, and country capabilities (with a narrow write). Message content, conversations and AI content are not readable. Every state change an administrator makes (suspend a user, adjust credits, change provider settings, lift an opt-out) goes through the backend, which checks recent re-authentication, requires a reason, and writes `audit_logs`. The database refuses direct writes for those actions even if an administrator's token is stolen.

## 3. Policy Catalogue

Policy names combine the table (or an abbreviation), the operation and the audience, for example `messages_select_member` or `profiles_update_own`. Selected, non-obvious ones:

| Policy | Definition (summary) |
|---|---|
| `messages_select_member` | Active member of the conversation AND `seq > cleared_before_seq` AND (not suppressed OR caller is sender) AND no `message_hides` row for the caller |
| `conversations_select_member` | `EXISTS` active `conversation_members` row for the caller |
| `deliveries_select_party` | Caller is the recipient, or the sender of the parent message |
| `contacts_insert_own_sms` | `owner_id = auth.uid()` AND `contact_type = 'sms'` (Chikka contacts exist only after an accepted request) |
| `profiles_update_own` | Own row AND status is `pending_verification` or `active` (suspended users cannot edit) |
| `sms_cap_select_current` / `sms_cap_*_admin` | Everyone reads current versions; only admins read history, insert, or retire a version |
| `reports_update_admin` | `is_admin()`; column grants limit the update to workflow fields |

The complete, current list for every table is in [schema-reference.md](schema-reference.md) (each table ends with its policies), generated from the database.

## 4. Behaviours Worth Knowing

- **`select *` on `messages` and some other tables fails for clients.** Column grants exclude sensitive columns, so a client must name the columns it needs. This is intentional.
- **Blocks are invisible.** A blocked sender's message is stored with `suppressed_at`; the recipient's policy hides it, and the sender still sees it as normal. The suppression columns are not granted to anyone but the backend.
- **A member who leaves loses access** to the conversation and its messages immediately (`left_at`).
- **`public_profiles` runs with the view owner's rights** so it can read profiles the caller cannot read directly. Its filter uses `auth.uid()`, and its column list is deliberately four fields. Adding a column needs a privacy review.
- **Token lifetime.** A JWT stays valid until it expires. Suspension and deletion take effect in the database at once (policies check `profiles.status` for updates and the backend checks `is_active`), but Supabase tokens already issued are valid until expiry unless the backend also revokes the session.
- **The service key bypasses everything.** It must exist only in the backend's environment.

## 5. Testing

`supabase/tests/database/04_rls_isolation.test.sql` covers every row in the matrix above: positive cases, cross-user denial, administrator limits, column refusals, server-only tables, anonymous refusal, function privileges, and structural checks (RLS enabled everywhere, no `anon` or `PUBLIC` grants, no policy for those roles, no client write grants on core tables). Details: [database-test-plan.md](database-test-plan.md).

## 6. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft, 13 tables |
| 2.0 | November 2026 | Kiro (Principal Architect) | 29 tables; column-level grants; narrower admin model; resolves OD-012 |
