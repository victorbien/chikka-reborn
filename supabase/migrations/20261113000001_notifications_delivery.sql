-- Migration: 20261113000001_notifications_delivery
-- Phase: 4 (notifications and demo credits)
-- Description: notification de-duplication and grouping, a delivery outbox (live push and email),
--              and a 'security' notification type.
-- Dependencies: 20261110000010_notifications
-- Rollback: forward-fix only.
-- Notes: the credit ledger needs no schema change. Its constraints (one entry of each type per
--        message, demo/live ledger separation, adjustments need actor and reason) already cover
--        idempotent reserve, deduct, release, refund and admin adjustment.

begin;

-- 'security' joins the types; mandatory in-app notices now include it.
alter table public.notifications drop constraint ck_notifications_type;
alter table public.notifications add constraint ck_notifications_type check (notification_type in
    ('new_message', 'sms_inbound', 'sms_delivered', 'sms_failed', 'contact_request',
     'contact_accepted', 'low_balance', 'system', 'security'));

create or replace function private.valid_notification_overrides(p_overrides jsonb)
returns boolean
language sql
immutable
set search_path = ''
as $$
    select jsonb_typeof(p_overrides) = 'object'
       and not exists (
            select 1 from jsonb_each(p_overrides) as e(key, value)
            where e.key !~ '^(new_message|sms_inbound|sms_delivered|sms_failed|contact_request|contact_accepted|low_balance|system|security)\.(in_app|push|email)$'
               or jsonb_typeof(e.value) <> 'boolean'
               or (e.key in ('sms_failed.in_app', 'system.in_app', 'security.in_app') and e.value = 'false'::jsonb)
       );
$$;

-- De-duplication and grouping.
--   dedupe_key  one notification per (user, key): the same event can never notify twice.
--   group_key   while a grouped notification is unread, further events update it
--               (occurrence_count, created_at) instead of adding rows.
alter table public.notifications
    add column dedupe_key         text,
    add column occurrence_count   integer not null default 1,
    -- Delivery outbox, drained by the backend worker after the creating transaction commits.
    add column browser_push       boolean not null default false,
    add column announced_at       timestamptz,
    add column email_requested_at timestamptz,
    add column email_sent_at      timestamptz,
    add column email_attempts     smallint not null default 0,
    add column email_attempted_at timestamptz;

alter table public.notifications
    add constraint ck_notifications_dedupe_key check (dedupe_key is null or char_length(dedupe_key) between 1 and 200),
    add constraint ck_notifications_occurrences check (occurrence_count >= 1),
    add constraint ck_notifications_email_attempts check (email_attempts >= 0);

-- Existing rows were already visible in the feed: nothing to announce.
update public.notifications set announced_at = created_at where announced_at is null;

create unique index uq_notifications_dedupe
    on public.notifications (user_id, dedupe_key) where dedupe_key is not null;
create unique index uq_notifications_open_group
    on public.notifications (user_id, group_key)
    where group_key is not null and read_at is null and dismissed_at is null;
create index idx_notifications_outbox
    on public.notifications (created_at)
    where announced_at is null or (email_requested_at is not null and email_sent_at is null);

comment on column public.notifications.dedupe_key is
    'Idempotency key for the event that caused the notification, for example sms_status:<message>:delivered.';
comment on column public.notifications.occurrence_count is
    'How many events a grouped notification stands for (for example 3 new messages in one chat).';
comment on column public.notifications.browser_push is
    'Whether the browser should also show a system notification when the app is open (decided at creation from preferences and quiet hours).';

commit;
