-- Migration: 20261110000006_conversations
-- Phase: 1
-- Description: conversations, conversation_members, get_or_create_* functions, RLS.
-- Dependencies: 20261110000002_profiles
-- Rollback: forward-fix only.

begin;

-- conversations: a thread. Two kinds (FR-MSG module header): 'chikka' between two accounts,
-- 'sms' between one account and one external number. Group chat is out of scope.
create table public.conversations (
    id                  uuid primary key default gen_random_uuid(),
    conversation_type   text not null,
    direct_key          text not null,
    remote_phone        public.e164,
    last_seq            bigint not null default 0,
    last_message_at     timestamptz,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),

    constraint ck_conversations_type check (conversation_type in ('chikka', 'sms')),
    constraint ck_conversations_remote check ((conversation_type = 'sms') = (remote_phone is not null)),
    constraint ck_conversations_key check (
        (conversation_type = 'chikka' and direct_key like 'c:%')
        or (conversation_type = 'sms' and direct_key like 's:%')),
    constraint ck_conversations_seq check (last_seq >= 0),
    constraint uq_conversations_direct_key unique (direct_key)
);

comment on table public.conversations is
    'direct_key makes pair creation idempotent: c:<lower uuid>:<higher uuid> for chikka, s:<owner uuid>:<E.164> for sms. last_seq is the per-conversation message counter.';

create index idx_conversations_last_message on public.conversations (last_message_at desc nulls last);

create trigger trg_conversations_updated_at
    before update on public.conversations
    for each row execute function private.set_updated_at();

-- conversation_members: membership plus each member's own view state (FR-MSG-012).
create table public.conversation_members (
    conversation_id     uuid not null constraint fk_cm_conversation references public.conversations (id) on delete cascade,
    user_id             uuid not null constraint fk_cm_user references public.profiles (id) on delete cascade,
    joined_at           timestamptz not null default now(),
    left_at             timestamptz,
    last_read_seq       bigint not null default 0,
    last_read_at        timestamptz,
    is_pinned           boolean not null default false,
    pinned_at           timestamptz,
    is_archived         boolean not null default false,
    marked_unread       boolean not null default false,
    muted_until         timestamptz,
    muted_indefinitely  boolean not null default false,
    cleared_before_seq  bigint not null default 0,
    ai_enabled          boolean not null default true,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),

    constraint pk_conversation_members primary key (conversation_id, user_id),
    constraint ck_cm_pin check (is_pinned = (pinned_at is not null)),
    constraint ck_cm_mute check (not (muted_until is not null and muted_indefinitely)),
    constraint ck_cm_seqs check (last_read_seq >= 0 and cleared_before_seq >= 0)
);

comment on column public.conversation_members.cleared_before_seq is
    'Messages with seq <= this value are hidden from this member (delete conversation for me).';
comment on column public.conversation_members.ai_enabled is 'Per-conversation AI exclusion (FR-AI-005 AC4).';

create index idx_cm_user_active on public.conversation_members (user_id, is_archived, is_pinned desc) where left_at is null;

create function private.enforce_pin_limit()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if new.is_pinned and (tg_op = 'INSERT' or not old.is_pinned) then
        perform pg_advisory_xact_lock(hashtextextended('pins:' || new.user_id::text, 0));
        if (select count(*) from public.conversation_members
             where user_id = new.user_id and is_pinned
               and (conversation_id, user_id) <> (new.conversation_id, new.user_id)) >= 5 then
            raise exception 'PIN_LIMIT_REACHED: at most 5 pinned conversations'
                using errcode = '23514';
        end if;
    end if;
    return new;
end;
$$;

create trigger trg_cm_pin_limit
    before insert or update of is_pinned on public.conversation_members
    for each row execute function private.enforce_pin_limit();
create trigger trg_cm_updated_at
    before update on public.conversation_members
    for each row execute function private.set_updated_at();

-- Row level security ---------------------------------------------------------
alter table public.conversation_members enable row level security;
revoke all on table public.conversation_members from public, anon, authenticated;
grant select on table public.conversation_members to authenticated;
-- Read markers and clearing are backend-only because they drive read receipts and events.
grant update (is_pinned, pinned_at, is_archived, marked_unread, muted_until, muted_indefinitely, ai_enabled)
    on table public.conversation_members to authenticated;
grant all on table public.conversation_members to service_role;

-- A member sees only their own membership row. This hides other members' read positions.
create policy cm_select_own on public.conversation_members
    for select to authenticated using (user_id = (select auth.uid()));
create policy cm_update_own on public.conversation_members
    for update to authenticated
    using (user_id = (select auth.uid()) and left_at is null)
    with check (user_id = (select auth.uid()));

alter table public.conversations enable row level security;
revoke all on table public.conversations from public, anon, authenticated;
grant select (id, conversation_type, remote_phone, last_seq, last_message_at, created_at, updated_at)
    on table public.conversations to authenticated;
grant all on table public.conversations to service_role;

-- No administrator policy: admins review conversations only through report snapshots.
create policy conversations_select_member on public.conversations
    for select to authenticated
    using (exists (
        select 1 from public.conversation_members cm
        where cm.conversation_id = conversations.id
          and cm.user_id = (select auth.uid())
          and cm.left_at is null));

-- Idempotent creation of the single chikka conversation for a pair (FR-MSG-013).
create function private.get_or_create_chikka_conversation(p_user_a uuid, p_user_b uuid)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_key text;
    v_id uuid;
begin
    if p_user_a is null or p_user_b is null or p_user_a = p_user_b then
        raise exception 'INVALID_PARTICIPANTS' using errcode = '22023';
    end if;
    if (select count(*) from public.profiles
         where id in (p_user_a, p_user_b) and status = 'active' and deleted_at is null) <> 2 then
        raise exception 'PARTICIPANT_NOT_ACTIVE' using errcode = '55000';
    end if;

    v_key := 'c:' || least(p_user_a, p_user_b)::text || ':' || greatest(p_user_a, p_user_b)::text;

    insert into public.conversations (conversation_type, direct_key)
    values ('chikka', v_key)
    on conflict (direct_key) do nothing
    returning id into v_id;

    if v_id is null then
        select id into v_id from public.conversations where direct_key = v_key;
    end if;

    insert into public.conversation_members (conversation_id, user_id)
    values (v_id, p_user_a), (v_id, p_user_b)
    on conflict (conversation_id, user_id) do nothing;

    return v_id;
end;
$$;

-- Idempotent creation of the single sms conversation for (owner, remote number) (FR-SMSRECV-006).
create function private.get_or_create_sms_conversation(p_owner uuid, p_remote public.e164)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_key text;
    v_id uuid;
begin
    if not exists (select 1 from public.profiles where id = p_owner and deleted_at is null) then
        raise exception 'PARTICIPANT_NOT_ACTIVE' using errcode = '55000';
    end if;

    v_key := 's:' || p_owner::text || ':' || p_remote::text;

    insert into public.conversations (conversation_type, direct_key, remote_phone)
    values ('sms', v_key, p_remote)
    on conflict (direct_key) do nothing
    returning id into v_id;

    if v_id is null then
        select id into v_id from public.conversations where direct_key = v_key;
    end if;

    insert into public.conversation_members (conversation_id, user_id)
    values (v_id, p_owner)
    on conflict (conversation_id, user_id) do nothing;

    return v_id;
end;
$$;

grant execute on function private.get_or_create_chikka_conversation(uuid, uuid) to service_role;
grant execute on function private.get_or_create_sms_conversation(uuid, public.e164) to service_role;

commit;
