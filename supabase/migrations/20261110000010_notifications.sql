-- Migration: 20261110000010_notifications
-- Phase: 2
-- Description: notification_preferences (one row per user) and notifications.
-- Dependencies: 20261110000002_profiles
-- Rollback: forward-fix only.

begin;

-- Valid override keys look like 'sms_failed.email' with a boolean value.
-- Mandatory notices (failed SMS, system/security) cannot be switched off in-app (FR-NOTIF-003, FR-NOTIF-005).
create function private.valid_notification_overrides(p_overrides jsonb)
returns boolean
language sql
immutable
set search_path = ''
as $$
    select jsonb_typeof(p_overrides) = 'object'
       and not exists (
            select 1 from jsonb_each(p_overrides) as e(key, value)
            where e.key !~ '^(new_message|sms_inbound|sms_delivered|sms_failed|contact_request|contact_accepted|low_balance|system)\.(in_app|push|email)$'
               or jsonb_typeof(e.value) <> 'boolean'
               or (e.key in ('sms_failed.in_app', 'system.in_app') and e.value = 'false'::jsonb)
       );
$$;

create table public.notification_preferences (
    user_id                     uuid primary key
                                    constraint fk_notif_prefs_user references public.profiles (id) on delete cascade,
    overrides                   jsonb not null default '{}'::jsonb,
    quiet_hours_start           time,
    quiet_hours_end             time,
    show_previews               boolean not null default false,
    low_balance_threshold_units bigint not null default 500,
    email_hard_bounce_count     smallint not null default 0,
    email_disabled_at           timestamptz,
    created_at                  timestamptz not null default now(),
    updated_at                  timestamptz not null default now(),

    constraint ck_notif_prefs_overrides check (private.valid_notification_overrides(overrides)),
    constraint ck_notif_prefs_quiet_hours check ((quiet_hours_start is null) = (quiet_hours_end is null)),
    -- 1 to 100 credits (FR-CREDIT-008).
    constraint ck_notif_prefs_threshold check (low_balance_threshold_units between 100 and 10000),
    constraint ck_notif_prefs_bounces check (email_hard_bounce_count >= 0)
);

comment on table public.notification_preferences is
    'Stores only deviations from defaults: overrides maps "<type>.<channel>" to true/false. The matrix is 8 types x 3 channels, always read as one unit, so a validated jsonb object keeps it to one row per user.';

create trigger trg_notif_prefs_updated_at
    before update on public.notification_preferences
    for each row execute function private.set_updated_at();

alter table public.notification_preferences enable row level security;
revoke all on table public.notification_preferences from public, anon, authenticated;
grant select on table public.notification_preferences to authenticated;
-- Bounce counters are managed by the email webhook handler, not by the user.
grant update (overrides, quiet_hours_start, quiet_hours_end, show_previews, low_balance_threshold_units)
    on table public.notification_preferences to authenticated;
grant all on table public.notification_preferences to service_role;

create policy notif_prefs_select_own on public.notification_preferences
    for select to authenticated using (user_id = (select auth.uid()));
create policy notif_prefs_update_own on public.notification_preferences
    for update to authenticated
    using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
-- The row is created with the profile; there is no client insert or delete.

create table public.notifications (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null constraint fk_notifications_user references public.profiles (id) on delete cascade,
    notification_type   text not null,
    title               text not null,
    body                text,
    reference_type      text,
    reference_id        uuid,
    group_key           text,
    read_at             timestamptz,
    dismissed_at        timestamptz,
    expires_at          timestamptz not null default (now() + interval '90 days'),
    created_at          timestamptz not null default now(),

    constraint ck_notifications_type check (notification_type in
        ('new_message', 'sms_inbound', 'sms_delivered', 'sms_failed', 'contact_request',
         'contact_accepted', 'low_balance', 'system')),
    constraint ck_notifications_title check (char_length(btrim(title)) between 1 and 200),
    constraint ck_notifications_body check (body is null or char_length(body) <= 500),
    constraint ck_notifications_reference check ((reference_type is null) = (reference_id is null))
);

comment on table public.notifications is
    'In-app notification feed. Removed after 90 days (expires_at, purged by a scheduled job). body is null when the user disabled previews.';

create index idx_notifications_feed on public.notifications (user_id, created_at desc) where dismissed_at is null;
create index idx_notifications_unread on public.notifications (user_id, created_at desc)
    where read_at is null and dismissed_at is null;
create index idx_notifications_expiry on public.notifications (expires_at);
create index idx_notifications_group on public.notifications (user_id, group_key) where group_key is not null;

alter table public.notifications enable row level security;
revoke all on table public.notifications from public, anon, authenticated;
grant select on table public.notifications to authenticated;
grant update (read_at, dismissed_at) on table public.notifications to authenticated;
grant all on table public.notifications to service_role;

create policy notifications_select_own on public.notifications
    for select to authenticated using (user_id = (select auth.uid()));
create policy notifications_update_own on public.notifications
    for update to authenticated
    using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
-- Creation is backend-only. Dismiss replaces delete so the feed stays consistent.

commit;
