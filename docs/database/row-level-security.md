# Row Level Security

**Document:** CHKR-DB-004  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Draft  
**Last Revised:** November 2026  

---

## Purpose

Defines all Supabase Row Level Security (RLS) policies for every Chikka Reborn table. RLS is the primary authorisation layer — it enforces data access at the database level, independent of application code.

## Scope

All 13 tables. All policies must be applied within the same migration file that creates the table.

---

## RLS Principles

1. **Every table has RLS enabled.** No exceptions.
2. **No table is accessible without an explicit policy.** When RLS is enabled without a policy, all access is denied by default.
3. **Policies use `auth.uid()`** — Supabase's built-in function returning the UUID of the authenticated user from the JWT.
4. **Admin access** uses a subquery against `profiles.role` — this is rechecked on every query, not cached.
5. **Policies are tested**, not assumed. Each policy has corresponding tests in `tests/api/test_rls.py`.
6. **Service role bypasses RLS.** The FastAPI backend uses `SUPABASE_SERVICE_ROLE_KEY` which bypasses RLS for server-side operations. The frontend uses the anon key and is fully subject to RLS.

---

## Helper Function

```sql
-- Reusable function to check if the current user is an admin
-- Used in policies that allow admin read access to all rows

CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM profiles
        WHERE id = auth.uid()
        AND role = 'admin'
        AND is_active = TRUE
        AND deleted_at IS NULL
    );
$$ LANGUAGE sql SECURITY DEFINER STABLE;
```

---

## `profiles`

```sql
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile (always)
CREATE POLICY "profiles_select_own" ON profiles
    FOR SELECT USING (auth.uid() = id);

-- Authenticated users can read non-private, active, non-deleted profiles (for contact search)
CREATE POLICY "profiles_select_public" ON profiles
    FOR SELECT USING (
        auth.uid() IS NOT NULL
        AND is_active = TRUE
        AND deleted_at IS NULL
        -- Note: privacy level filtering (private/contacts-only) is enforced in application layer
        -- The DB policy permits reads for authenticated users; the service layer further filters
    );

-- Users can update only their own profile
CREATE POLICY "profiles_update_own" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- Admins can read all profiles
CREATE POLICY "profiles_admin_select_all" ON profiles
    FOR SELECT USING (is_admin());

-- Admins can update any profile (for suspension, role changes)
CREATE POLICY "profiles_admin_update_all" ON profiles
    FOR UPDATE USING (is_admin());

-- Insert is handled by Supabase Auth trigger (not direct INSERT by users)
-- No INSERT policy needed for regular users
```

---

## `contacts`

```sql
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

-- Users can only access their own contacts
CREATE POLICY "contacts_owner_select" ON contacts
    FOR SELECT USING (auth.uid() = owner_id);

CREATE POLICY "contacts_owner_insert" ON contacts
    FOR INSERT WITH CHECK (auth.uid() = owner_id);

CREATE POLICY "contacts_owner_update" ON contacts
    FOR UPDATE USING (auth.uid() = owner_id);

CREATE POLICY "contacts_owner_delete" ON contacts
    FOR DELETE USING (auth.uid() = owner_id);
```

---

## `conversations`

Access is mediated via `conversation_participants`.

```sql
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- User can see a conversation if they are a participant
CREATE POLICY "conversations_participant_select" ON conversations
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM conversation_participants cp
            WHERE cp.conversation_id = id
            AND cp.user_id = auth.uid()
        )
    );

-- Users can create conversations (application layer enforces participant rules)
CREATE POLICY "conversations_authenticated_insert" ON conversations
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- Admins can read all conversations
CREATE POLICY "conversations_admin_select" ON conversations
    FOR SELECT USING (is_admin());
```

---

## `conversation_participants`

```sql
ALTER TABLE conversation_participants ENABLE ROW LEVEL SECURITY;

-- User can see their own participation records
CREATE POLICY "cp_own_select" ON conversation_participants
    FOR SELECT USING (auth.uid() = user_id);

-- User can update their own last_read_at
CREATE POLICY "cp_own_update" ON conversation_participants
    FOR UPDATE USING (auth.uid() = user_id);

-- Application (service role) manages participant records — no direct INSERT by users
```

---

## `messages`

```sql
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- User can read messages in conversations they participate in
CREATE POLICY "messages_participant_select" ON messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM conversation_participants cp
            WHERE cp.conversation_id = messages.conversation_id
            AND cp.user_id = auth.uid()
        )
    );

-- User can insert messages into conversations they participate in
CREATE POLICY "messages_participant_insert" ON messages
    FOR INSERT WITH CHECK (
        auth.uid() = sender_user_id
        AND EXISTS (
            SELECT 1 FROM conversation_participants cp
            WHERE cp.conversation_id = messages.conversation_id
            AND cp.user_id = auth.uid()
        )
    );

-- User can soft-delete their own messages (update deleted_at + clear body)
CREATE POLICY "messages_sender_update_own" ON messages
    FOR UPDATE USING (auth.uid() = sender_user_id);

-- Admins can read all messages
CREATE POLICY "messages_admin_select" ON messages
    FOR SELECT USING (is_admin());
```

---

## `notifications`

```sql
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- Users can only access their own notifications
CREATE POLICY "notifications_own_all" ON notifications
    FOR ALL USING (auth.uid() = user_id);
```

---

## `outbound_sms`

```sql
ALTER TABLE outbound_sms ENABLE ROW LEVEL SECURITY;

-- Users can read their own outbound SMS records
CREATE POLICY "outbound_sms_own_select" ON outbound_sms
    FOR SELECT USING (auth.uid() = sender_user_id);

-- Admins can read all outbound SMS (for audit log)
CREATE POLICY "outbound_sms_admin_select" ON outbound_sms
    FOR SELECT USING (is_admin());

-- No direct INSERT by frontend users — service role only
```

---

## `sms_delivery_events`

```sql
ALTER TABLE sms_delivery_events ENABLE ROW LEVEL SECURITY;

-- Only admins can read delivery events directly
CREATE POLICY "delivery_events_admin_select" ON sms_delivery_events
    FOR SELECT USING (is_admin());

-- No access for regular users — delivery status exposed via outbound_sms.status
-- Service role used for INSERT by webhook processor
```

---

## `inbound_sms`

```sql
ALTER TABLE inbound_sms ENABLE ROW LEVEL SECURITY;

-- Matched users can read their inbound SMS
CREATE POLICY "inbound_sms_matched_user_select" ON inbound_sms
    FOR SELECT USING (auth.uid() = matched_user_id);

-- Admins can read all inbound SMS
CREATE POLICY "inbound_sms_admin_select" ON inbound_sms
    FOR SELECT USING (is_admin());

-- No INSERT/UPDATE by frontend users — service role only (webhook processor)
```

---

## `credit_accounts`

```sql
ALTER TABLE credit_accounts ENABLE ROW LEVEL SECURITY;

-- Users can read their own credit account
CREATE POLICY "credit_accounts_own_select" ON credit_accounts
    FOR SELECT USING (auth.uid() = user_id);

-- Admins can read all credit accounts
CREATE POLICY "credit_accounts_admin_select" ON credit_accounts
    FOR SELECT USING (is_admin());

-- No direct UPDATE by frontend users — service role only
-- Updates use SELECT FOR UPDATE + atomic deduction in service layer
```

---

## `credit_transactions`

```sql
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;

-- Users can read their own transactions
CREATE POLICY "credit_tx_own_select" ON credit_transactions
    FOR SELECT USING (auth.uid() = user_id);

-- Admins can read all transactions
CREATE POLICY "credit_tx_admin_select" ON credit_transactions
    FOR SELECT USING (is_admin());

-- Immutable: no UPDATE or DELETE policies
-- INSERT by service role only
```

---

## `country_capabilities`

```sql
ALTER TABLE country_capabilities ENABLE ROW LEVEL SECURITY;

-- All authenticated users can read country capabilities (for capability check UI)
CREATE POLICY "country_capabilities_authenticated_select" ON country_capabilities
    FOR SELECT USING (auth.uid() IS NOT NULL);

-- Only admins can write
CREATE POLICY "country_capabilities_admin_write" ON country_capabilities
    FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "country_capabilities_admin_update" ON country_capabilities
    FOR UPDATE USING (is_admin());

CREATE POLICY "country_capabilities_admin_delete" ON country_capabilities
    FOR DELETE USING (is_admin());
```

---

## `ai_usage_logs`

```sql
ALTER TABLE ai_usage_logs ENABLE ROW LEVEL SECURITY;

-- Only admins can read AI usage logs (for metrics dashboard)
CREATE POLICY "ai_logs_admin_select" ON ai_usage_logs
    FOR SELECT USING (is_admin());

-- No access for regular users — logs contain aggregate usage metadata
-- INSERT by service role only
```

---

## RLS Testing Requirements

Every policy must be covered by a test in `tests/api/test_rls.py`:

| Test Pattern | Description |
|---|---|
| Positive — own data | User A can read their own row |
| Negative — other user's data | User A cannot read User B's row |
| Admin — all data | Admin can read any user's row |
| Non-admin trying admin endpoint | Non-admin gets 0 rows (not an error) |
| Unauthenticated | Unauthenticated request returns 0 rows or 401 |

Example test structure:
```python
async def test_contacts_owner_isolation(db_session, user_a_token, user_b_token):
    """User A cannot see User B's contacts via direct DB query or API."""
    # User A creates a contact
    contact = await create_contact(user_a_token, ...)
    
    # User B should not see User A's contact
    result = await api_client.get("/contacts", headers=user_b_token)
    assert contact["id"] not in [c["id"] for c in result["data"]]
```

---

## Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial draft — all 13 tables |
