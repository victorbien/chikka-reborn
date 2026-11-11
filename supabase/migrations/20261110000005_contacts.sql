-- Migration: 20261110000005_contacts
-- Phase: 1
-- Description: contacts, contact_requests, contact_groups, contact_group_members,
--              user_blocks, public_profiles view, accept_contact_request().
-- Dependencies: 20261110000002_profiles
-- Rollback: forward-fix only.

begin;

-- contacts: one row per owner per contact (FR-CONTACTS-001..003, 005, 006, 011, 013).
-- A mutual Chikka contact is two rows, one per owner, created together by accept_contact_request().
create table public.contacts (
    id                  uuid primary key default gen_random_uuid(),
    owner_id            uuid not null constraint fk_contacts_owner references public.profiles (id) on delete cascade,
    contact_type        text not null,
    contact_user_id     uuid constraint fk_contacts_contact_user references public.profiles (id) on delete cascade,
    phone_e164          public.e164,
    display_name        text,
    is_favourite        boolean not null default false,
    muted_until         timestamptz,
    muted_indefinitely  boolean not null default false,
    recent_cleared_at   timestamptz,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),

    constraint ck_contacts_type check (contact_type in ('chikka', 'sms')),
    constraint ck_contacts_target check (
        (contact_type = 'chikka' and contact_user_id is not null and phone_e164 is null)
        or (contact_type = 'sms' and phone_e164 is not null and contact_user_id is null)),
    constraint ck_contacts_not_self check (owner_id <> contact_user_id),
    constraint ck_contacts_display_name check (
        display_name is null or char_length(btrim(display_name)) between 1 and 100),
    constraint ck_contacts_sms_named check (contact_type = 'chikka' or display_name is not null),
    constraint ck_contacts_mute check (not (muted_until is not null and muted_indefinitely)),
    constraint uq_contacts_owner_user unique (owner_id, contact_user_id),
    constraint uq_contacts_owner_phone unique (owner_id, phone_e164),
    constraint uq_contacts_id_owner unique (id, owner_id)
);

comment on table public.contacts is
    'Owner-scoped address book. Adding an SMS contact does not record consent; consent is per recipient in user_consents.';

create index idx_contacts_owner_favourite on public.contacts (owner_id, is_favourite desc);
create index idx_contacts_contact_user on public.contacts (contact_user_id) where contact_user_id is not null;

create trigger trg_contacts_updated_at
    before update on public.contacts
    for each row execute function private.set_updated_at();

alter table public.contacts enable row level security;
revoke all on table public.contacts from public, anon, authenticated;
grant select on table public.contacts to authenticated;
grant insert (owner_id, contact_type, phone_e164, display_name) on table public.contacts to authenticated;
grant update (display_name, is_favourite, muted_until, muted_indefinitely, recent_cleared_at)
    on table public.contacts to authenticated;
grant delete on table public.contacts to authenticated;
grant all on table public.contacts to service_role;

create policy contacts_select_own on public.contacts
    for select to authenticated using (owner_id = (select auth.uid()));
-- Chikka contacts only come from an accepted request (backend). Clients may add SMS contacts.
create policy contacts_insert_own_sms on public.contacts
    for insert to authenticated
    with check (owner_id = (select auth.uid()) and contact_type = 'sms');
create policy contacts_update_own on public.contacts
    for update to authenticated
    using (owner_id = (select auth.uid()))
    with check (owner_id = (select auth.uid()));
create policy contacts_delete_own on public.contacts
    for delete to authenticated using (owner_id = (select auth.uid()));

-- contact_requests (FR-CONTACTS-001, 009, 010).
create table public.contact_requests (
    id              uuid primary key default gen_random_uuid(),
    from_user_id    uuid not null constraint fk_contact_requests_from references public.profiles (id) on delete cascade,
    to_user_id      uuid not null constraint fk_contact_requests_to references public.profiles (id) on delete cascade,
    note            text,
    status          text not null default 'pending',
    expires_at      timestamptz not null default (now() + interval '30 days'),
    responded_at    timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    constraint ck_contact_requests_not_self check (from_user_id <> to_user_id),
    constraint ck_contact_requests_note check (note is null or char_length(note) <= 140),
    constraint ck_contact_requests_status check (status in ('pending', 'accepted', 'rejected', 'cancelled', 'expired')),
    constraint ck_contact_requests_responded check (status in ('pending', 'expired') or responded_at is not null)
);

comment on table public.contact_requests is
    'Pending requests expire after 30 days. A rejected sender may re-request after 7 days (rule applied by the backend from responded_at).';

-- One pending request per pair, in either direction. A reverse request is handled by accepting.
create unique index uq_contact_requests_pending_pair
    on public.contact_requests (least(from_user_id, to_user_id), greatest(from_user_id, to_user_id))
    where status = 'pending';
create index idx_contact_requests_inbox on public.contact_requests (to_user_id, status, created_at desc);
create index idx_contact_requests_sent on public.contact_requests (from_user_id, created_at desc);
create index idx_contact_requests_expiry on public.contact_requests (expires_at) where status = 'pending';

create trigger trg_contact_requests_updated_at
    before update on public.contact_requests
    for each row execute function private.set_updated_at();

alter table public.contact_requests enable row level security;
revoke all on table public.contact_requests from public, anon, authenticated;
grant select on table public.contact_requests to authenticated;
grant all on table public.contact_requests to service_role;

-- Participants only. Writes are backend-only because blocked senders must see a silent success
-- and decisions are audit logged.
create policy contact_requests_select_party on public.contact_requests
    for select to authenticated
    using (from_user_id = (select auth.uid()) or to_user_id = (select auth.uid()));

-- Limits enforced under an advisory lock so concurrent inserts cannot slip past a count check.
create function private.enforce_group_limit()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    perform pg_advisory_xact_lock(hashtextextended('contact_groups:' || new.owner_id::text, 0));
    if (select count(*) from public.contact_groups where owner_id = new.owner_id) >= 20 then
        raise exception 'GROUP_LIMIT_REACHED: a user may have at most 20 contact groups'
            using errcode = '23514';
    end if;
    return new;
end;
$$;

-- contact_groups (FR-CONTACTS-005).
create table public.contact_groups (
    id          uuid primary key default gen_random_uuid(),
    owner_id    uuid not null constraint fk_contact_groups_owner references public.profiles (id) on delete cascade,
    name        text not null,
    color       text,
    position    integer not null default 0,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),

    constraint ck_contact_groups_name check (char_length(btrim(name)) between 1 and 30),
    constraint ck_contact_groups_color check (color is null or color ~ '^#[0-9A-Fa-f]{6}$'),
    constraint uq_contact_groups_id_owner unique (id, owner_id)
);

create unique index uq_contact_groups_owner_name on public.contact_groups (owner_id, lower(name));
create index idx_contact_groups_owner_position on public.contact_groups (owner_id, position);

create trigger trg_contact_groups_limit
    before insert on public.contact_groups
    for each row execute function private.enforce_group_limit();
create trigger trg_contact_groups_updated_at
    before update on public.contact_groups
    for each row execute function private.set_updated_at();

alter table public.contact_groups enable row level security;
revoke all on table public.contact_groups from public, anon, authenticated;
grant select, delete on table public.contact_groups to authenticated;
grant insert (owner_id, name, color, position) on table public.contact_groups to authenticated;
grant update (name, color, position) on table public.contact_groups to authenticated;
grant all on table public.contact_groups to service_role;

create policy contact_groups_select_own on public.contact_groups
    for select to authenticated using (owner_id = (select auth.uid()));
create policy contact_groups_insert_own on public.contact_groups
    for insert to authenticated with check (owner_id = (select auth.uid()));
create policy contact_groups_update_own on public.contact_groups
    for update to authenticated
    using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
create policy contact_groups_delete_own on public.contact_groups
    for delete to authenticated using (owner_id = (select auth.uid()));

-- contact_group_members: many-to-many. Composite foreign keys force group and contact to share an owner.
create table public.contact_group_members (
    group_id    uuid not null,
    contact_id  uuid not null,
    owner_id    uuid not null,
    position    integer not null default 0,
    created_at  timestamptz not null default now(),

    constraint pk_contact_group_members primary key (group_id, contact_id),
    constraint fk_cgm_group foreign key (group_id, owner_id)
        references public.contact_groups (id, owner_id) on delete cascade,
    constraint fk_cgm_contact foreign key (contact_id, owner_id)
        references public.contacts (id, owner_id) on delete cascade
);

create index idx_cgm_contact on public.contact_group_members (contact_id);
create index idx_cgm_owner on public.contact_group_members (owner_id);

alter table public.contact_group_members enable row level security;
revoke all on table public.contact_group_members from public, anon, authenticated;
grant select, delete on table public.contact_group_members to authenticated;
grant insert (group_id, contact_id, owner_id, position) on table public.contact_group_members to authenticated;
grant update (position) on table public.contact_group_members to authenticated;
grant all on table public.contact_group_members to service_role;

create policy cgm_select_own on public.contact_group_members
    for select to authenticated using (owner_id = (select auth.uid()));
create policy cgm_insert_own on public.contact_group_members
    for insert to authenticated with check (owner_id = (select auth.uid()));
create policy cgm_update_own on public.contact_group_members
    for update to authenticated
    using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
create policy cgm_delete_own on public.contact_group_members
    for delete to authenticated using (owner_id = (select auth.uid()));

-- user_blocks (FR-CONTACTS-004, FR-PRIVACY-006). Applies to accounts and to SMS numbers.
create table public.user_blocks (
    id              uuid primary key default gen_random_uuid(),
    blocker_id      uuid not null constraint fk_user_blocks_blocker references public.profiles (id) on delete cascade,
    blocked_user_id uuid constraint fk_user_blocks_blocked references public.profiles (id) on delete cascade,
    blocked_phone   public.e164,
    created_at      timestamptz not null default now(),

    constraint ck_user_blocks_target check ((blocked_user_id is not null) <> (blocked_phone is not null)),
    constraint ck_user_blocks_not_self check (blocker_id <> blocked_user_id),
    constraint uq_user_blocks_user unique (blocker_id, blocked_user_id),
    constraint uq_user_blocks_phone unique (blocker_id, blocked_phone)
);

comment on table public.user_blocks is
    'A block is invisible to the blocked party: no client policy lets them read it. Block and unblock are audit logged, so writes are backend-only.';

create index idx_user_blocks_blocked_user on public.user_blocks (blocked_user_id) where blocked_user_id is not null;
create index idx_user_blocks_blocked_phone on public.user_blocks (blocked_phone) where blocked_phone is not null;

alter table public.user_blocks enable row level security;
revoke all on table public.user_blocks from public, anon, authenticated;
grant select on table public.user_blocks to authenticated;
grant all on table public.user_blocks to service_role;

create policy user_blocks_select_own on public.user_blocks
    for select to authenticated using (blocker_id = (select auth.uid()));

-- Helper: has either user blocked the other?
create function private.is_blocked_between(a uuid, b uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1 from public.user_blocks
        where (blocker_id = a and blocked_user_id = b)
           or (blocker_id = b and blocked_user_id = a)
    );
$$;
grant execute on function private.is_blocked_between(uuid, uuid) to service_role;

-- public_profiles: the only way a client reads another user's profile (resolves OD-012).
-- It exposes four non-sensitive columns and applies the visibility setting.
-- Intentionally runs with the view owner's rights so it can read profiles the caller has no RLS access to.
create view public.public_profiles
    with (security_barrier = true)
as
select p.id, p.username, p.display_name, p.avatar_path, p.country_code
from public.profiles p
where p.status = 'active'
  and p.deleted_at is null
  and p.username is not null
  and auth.uid() is not null
  and (
        p.id = auth.uid()
        or (
            not exists (
                select 1 from public.user_blocks b
                where b.blocker_id = p.id and b.blocked_user_id = auth.uid())
            and (
                p.profile_visibility = 'everyone'
                or (p.profile_visibility = 'contacts'
                    and exists (
                        select 1 from public.contacts c
                        where c.owner_id = p.id and c.contact_user_id = auth.uid()))
            )
        )
      );

comment on view public.public_profiles is
    'Visibility-filtered directory of profiles. Reads run as the view owner; the filter uses auth.uid(). Never add columns without a privacy review.';

revoke all on table public.public_profiles from public, anon, authenticated;
grant select on table public.public_profiles to authenticated;
grant select on table public.public_profiles to service_role;

-- Atomic accept: marks the request accepted and creates both contact rows (FR-CONTACTS-010).
-- Backend-only (service_role). Idempotent for an already accepted request.
create function private.accept_contact_request(p_request_id uuid, p_acting_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_request public.contact_requests%rowtype;
begin
    select * into v_request from public.contact_requests where id = p_request_id for update;
    if not found then
        raise exception 'CONTACT_REQUEST_NOT_FOUND' using errcode = 'P0002';
    end if;
    if v_request.to_user_id <> p_acting_user_id then
        raise exception 'FORBIDDEN: only the recipient may accept' using errcode = '42501';
    end if;
    if v_request.status = 'accepted' then
        return;
    end if;
    if v_request.status <> 'pending' or v_request.expires_at <= now() then
        raise exception 'CONTACT_REQUEST_NOT_PENDING' using errcode = '55000';
    end if;

    update public.contact_requests
       set status = 'accepted', responded_at = now()
     where id = p_request_id;

    insert into public.contacts (owner_id, contact_type, contact_user_id)
    values (v_request.from_user_id, 'chikka', v_request.to_user_id),
           (v_request.to_user_id, 'chikka', v_request.from_user_id)
    on conflict (owner_id, contact_user_id) do nothing;
end;
$$;
grant execute on function private.accept_contact_request(uuid, uuid) to service_role;

commit;
