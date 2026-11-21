-- Migration: 20261111000002_contacts_discovery
-- Phase: 1
-- Description: status message and email discoverability on profiles; backend-only exact email lookup.
-- Dependencies: 20261110000002_profiles, 20261110000005_contacts
-- Rollback: forward-fix only.

begin;

alter table public.profiles
    add column status_message text,
    add column discoverable_by_email boolean not null default false,
    add constraint ck_profiles_status_message
        check (status_message is null or char_length(status_message) <= 80);

comment on column public.profiles.status_message is
    'Short free-text status shown in contacts'' buddy lists (FR-CONTACTS-003). Subject to profile_visibility.';
comment on column public.profiles.discoverable_by_email is
    'Opt-in. When false, an exact email search never returns this account (FR-PRIVACY-005). Default false.';

grant update (status_message, discoverable_by_email) on table public.profiles to authenticated;

-- Exact, case-insensitive email lookup. auth.users is not readable by clients, so this is the only
-- way the backend resolves an email to an account. Callers must apply discoverability rules and
-- must never reveal whether an address is registered.
create function private.find_user_id_by_email(p_email text)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
    select u.id
    from auth.users u
    where lower(u.email) = lower(p_email)
    limit 1;
$$;

revoke all on function private.find_user_id_by_email(text) from public, anon, authenticated;
grant execute on function private.find_user_id_by_email(text) to service_role;

commit;
