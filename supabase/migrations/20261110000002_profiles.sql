-- Migration: 20261110000002_profiles
-- Phase: 1
-- Description: profiles table, auth.users bootstrap trigger, is_admin() helper, RLS.
-- Dependencies: 20261110000001_foundation, auth.users (Supabase)
-- Rollback: forward-fix only.
-- Decisions: resolves OD-010 (profile created by trigger on auth.users) and OD-012
--            (profiles are own-row only; other users see public_profiles, see contacts migration).

begin;

create table public.profiles (
    id                      uuid primary key
                                constraint fk_profiles_auth_user references auth.users (id) on delete restrict,
    username                text,
    display_name            text not null default 'New user',
    bio                     text,
    avatar_path             text,
    country_code            char(2),
    language                text not null default 'en',
    time_zone               text not null default 'UTC',
    ui_mode                 text not null default 'modern',
    theme                   text not null default 'system',
    display_options         jsonb not null default '{}'::jsonb,
    role                    text not null default 'user',
    status                  text not null default 'pending_verification',
    onboarding_completed_at timestamptz,
    profile_visibility      text not null default 'contacts',
    presence_preference     text not null default 'online',
    share_presence          text not null default 'contacts',
    show_last_seen          boolean not null default false,
    send_typing_indicators  boolean not null default true,
    send_read_receipts      boolean not null default false,
    discoverable_by_phone   boolean not null default false,
    ai_enabled              boolean not null default false,
    last_seen_at            timestamptz,
    suspended_at            timestamptz,
    deletion_requested_at   timestamptz,
    deleted_at              timestamptz,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),

    constraint ck_profiles_username check (username is null or username ~ '^[A-Za-z0-9_]{3,20}$'),
    constraint ck_profiles_display_name check (char_length(btrim(display_name)) between 2 and 50),
    constraint ck_profiles_bio check (bio is null or char_length(bio) <= 160),
    constraint ck_profiles_country check (country_code is null or country_code ~ '^[A-Z]{2}$'),
    constraint ck_profiles_language check (language ~ '^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$'),
    constraint ck_profiles_ui_mode check (ui_mode in ('modern', 'classic')),
    constraint ck_profiles_theme check (theme in ('system', 'light', 'dark')),
    constraint ck_profiles_display_options check (jsonb_typeof(display_options) = 'object'),
    constraint ck_profiles_role check (role in ('user', 'admin')),
    constraint ck_profiles_status check (status in ('pending_verification', 'active', 'suspended', 'deleted')),
    constraint ck_profiles_visibility check (profile_visibility in ('everyone', 'contacts', 'private')),
    constraint ck_profiles_presence_pref check (presence_preference in ('online', 'away', 'busy', 'invisible')),
    constraint ck_profiles_share_presence check (share_presence in ('everyone', 'contacts', 'nobody')),
    constraint ck_profiles_onboarding_needs_username
        check (onboarding_completed_at is null or username is not null),
    constraint ck_profiles_deleted_state check ((status = 'deleted') = (deleted_at is not null)),
    constraint ck_profiles_suspended_state check ((status = 'suspended') = (suspended_at is not null))
);

comment on table public.profiles is
    'One row per account. Rows are never hard-deleted; erasure scrubs personal fields and sets status=deleted so ledgers, messages and audit rows keep a valid reference.';

create unique index uq_profiles_username_lower on public.profiles (lower(username)) where username is not null;
create index idx_profiles_status on public.profiles (status);
create index idx_profiles_admin on public.profiles (id) where role = 'admin';

create trigger trg_profiles_updated_at
    before update on public.profiles
    for each row execute function private.set_updated_at();

-- Creates the profile row when Supabase Auth creates a user.
create function private.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_display_name text;
begin
    v_display_name := left(btrim(coalesce(new.raw_user_meta_data ->> 'display_name', '')), 50);
    if char_length(v_display_name) < 2 then
        v_display_name := 'New user';
    end if;

    insert into public.profiles (id, display_name)
    values (new.id, v_display_name)
    on conflict (id) do nothing;

    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function private.handle_new_auth_user();

-- Admin check. Reads the role from the database on every call; JWT claims are never trusted
-- because user_metadata is user-editable.
create function private.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.profiles p
        where p.id = auth.uid()
          and p.role = 'admin'
          and p.status = 'active'
          and p.deleted_at is null
    );
$$;

grant execute on function private.is_admin() to authenticated, service_role;

-- Row level security ---------------------------------------------------------
alter table public.profiles enable row level security;

revoke all on table public.profiles from public, anon, authenticated;
grant select on table public.profiles to authenticated;
grant update (
    display_name, bio, avatar_path, country_code, language, time_zone, ui_mode, theme,
    display_options, profile_visibility, presence_preference, share_presence,
    show_last_seen, send_typing_indicators, send_read_receipts, discoverable_by_phone
) on table public.profiles to authenticated;
grant all on table public.profiles to service_role;

create policy profiles_select_own on public.profiles
    for select to authenticated
    using (id = (select auth.uid()));

create policy profiles_select_admin on public.profiles
    for select to authenticated
    using ((select private.is_admin()));

-- Users may edit only their own row, and only the granted columns above.
-- role, status, username, ai_enabled and deletion fields are backend-only.
create policy profiles_update_own on public.profiles
    for update to authenticated
    using (id = (select auth.uid()) and status in ('pending_verification', 'active'))
    with check (id = (select auth.uid()));

commit;
