-- Deletes ALL application data and ALL auth users so the dev seed can be re-run from scratch.
--
--   DEVELOPMENT ONLY. This permanently deletes every user, message, contact, credit ledger entry
--   and audit log in this database. It cannot be undone. Never run it on staging or production.
--
-- What is kept: the reference data that migrations install (system_settings,
-- provider_configurations, sms_country_capabilities) and the schema itself.
-- What is not touched: files in Supabase Storage (avatars). Empty the "avatars" bucket from the
-- dashboard (Storage) if you want those gone too; Supabase blocks deleting them with SQL.
--
-- Run it in the Supabase SQL editor (or psql), then run supabase/seed/01_dev_seed.sql.
-- Everything happens in one transaction: if any step fails, nothing is deleted.

begin;

do $$
declare
    -- Every table this script deletes from or deliberately keeps.
    v_known text[] := array[
        'profiles', 'phone_numbers', 'user_consents', 'contacts', 'contact_requests',
        'contact_groups', 'contact_group_members', 'user_blocks', 'abuse_reports',
        'conversations', 'conversation_members', 'messages', 'message_hides', 'message_segments',
        'message_deliveries', 'message_delivery_events', 'provider_webhooks', 'sms_routes',
        'sms_opt_outs', 'messaging_credits', 'credit_transactions', 'notification_preferences',
        'notifications', 'ai_assistance_logs', 'rate_limit_counters', 'audit_logs',
        'system_settings', 'provider_configurations', 'sms_country_capabilities'];
    v_unknown text;
begin
    if coalesce(current_setting('app.environment', true), 'development') in ('production', 'staging') then
        raise exception 'Refusing to wipe data in environment %', current_setting('app.environment', true);
    end if;

    -- A table added by a later migration must be reviewed here, not silently left behind.
    select string_agg(tablename, ', ') into v_unknown
      from pg_tables
     where schemaname = 'public' and tablename <> all (v_known);
    if v_unknown is not null then
        raise exception 'Unlisted tables found: %. Add them to this script before running it.', v_unknown;
    end if;
end
$$;

-- 1. Application data. TRUNCATE is used because the append-only tables (consents, credit
--    transactions, delivery events, audit logs) reject row-by-row DELETE by design.
--    All tables that reference each other are listed together, so no CASCADE is needed and
--    nothing outside this list can be emptied by accident.
truncate table
    public.message_delivery_events,
    public.message_deliveries,
    public.provider_webhooks,
    public.message_segments,
    public.message_hides,
    public.ai_assistance_logs,
    public.abuse_reports,
    public.messages,
    public.conversation_members,
    public.conversations,
    public.contact_group_members,
    public.contact_groups,
    public.contacts,
    public.contact_requests,
    public.user_blocks,
    public.sms_opt_outs,
    public.sms_routes,
    public.notifications,
    public.notification_preferences,
    public.credit_transactions,
    public.messaging_credits,
    public.user_consents,
    public.phone_numbers,
    public.rate_limit_counters,
    public.audit_logs
restart identity;

-- 2. Profiles. Not truncated because the reference tables point at them (ON DELETE SET NULL).
delete from public.profiles;

-- 3. Auth users. Also removes their identities, sessions and refresh tokens.
delete from auth.users;

commit;

-- Check (should return 0 for every row):
-- select 'auth.users' as t, count(*) from auth.users
-- union all select 'profiles', count(*) from public.profiles
-- union all select 'contacts', count(*) from public.contacts
-- union all select 'audit_logs', count(*) from public.audit_logs;
