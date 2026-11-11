-- Migration: 20261110000007_messages
-- Phase: 1 (SMS columns used from Phase 2)
-- Description: messages, message_hides, message_segments, seq allocation, RLS.
-- Dependencies: 20261110000003 (capabilities), 20261110000006 (conversations)
-- Rollback: forward-fix only.
-- Model: a message is conversation content. Delivery attempts live in message_deliveries.

begin;

create table public.messages (
    id                      uuid primary key default gen_random_uuid(),
    conversation_id         uuid not null constraint fk_messages_conversation references public.conversations (id) on delete cascade,
    seq                     bigint not null,
    channel                 text not null,
    direction               text not null,
    sender_user_id          uuid constraint fk_messages_sender references public.profiles (id) on delete restrict,
    sender_phone            public.e164,
    body                    text,
    body_truncated          boolean not null default false,
    encoding                text,
    char_count              integer,
    segment_count           smallint,
    status                  text not null,
    status_version          integer not null default 1,
    idempotency_key         uuid,
    request_hash            text,
    is_simulated            boolean not null default false,
    is_ai_assisted          boolean not null default false,
    ai_assistance_log_id    uuid,
    capability_id           uuid constraint fk_messages_capability references public.sms_country_capabilities (id) on delete restrict,
    credit_cost_units       bigint,
    suppressed_at           timestamptz,
    suppressed_reason       text,
    edited_at               timestamptz,
    deleted_for_everyone_at timestamptz,
    admin_resolved_at       timestamptz,
    admin_resolved_by       uuid constraint fk_messages_admin_resolver references public.profiles (id) on delete restrict,
    admin_resolution_note   text,
    search_vector           tsvector generated always as (to_tsvector('simple'::regconfig, coalesce(body, ''))) stored,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),

    constraint ck_messages_channel check (channel in ('chikka', 'sms')),
    constraint ck_messages_direction check (direction in ('outbound', 'inbound')),
    -- Chikka messages always originate from an account; only SMS can be inbound.
    constraint ck_messages_chikka_outbound check (channel = 'sms' or direction = 'outbound'),
    constraint ck_messages_sender check (
        (direction = 'outbound' and sender_user_id is not null and sender_phone is null)
        or (direction = 'inbound' and sender_user_id is null and sender_phone is not null)),
    constraint ck_messages_body_presence check (
        (deleted_for_everyone_at is null and body is not null and char_length(body) >= 1)
        or (deleted_for_everyone_at is not null and body is null)),
    constraint ck_messages_body_length check (
        body is null or char_length(body) <= case channel when 'chikka' then 2000 else 1600 end),
    constraint ck_messages_encoding check (encoding is null or encoding in ('gsm7', 'ucs2')),
    constraint ck_messages_segments check (segment_count is null or segment_count between 1 and 10),
    constraint ck_messages_char_count check (char_count is null or char_count >= 0),
    constraint ck_messages_sms_outbound_segments check (
        not (channel = 'sms' and direction = 'outbound')
        or (encoding is not null and segment_count is not null and char_count is not null)),
    constraint ck_messages_chikka_no_sms_fields check (
        channel = 'sms'
        or (encoding is null and segment_count is null and capability_id is null
            and credit_cost_units is null and not is_simulated)),
    constraint ck_messages_status check (
        (channel = 'chikka' and status in ('sent', 'delivered', 'read', 'failed'))
        or (channel = 'sms' and status in
            ('queued', 'retrying', 'accepted', 'sent', 'delivered', 'undelivered', 'failed', 'received'))),
    constraint ck_messages_received_status check ((direction = 'inbound') = (status = 'received')),
    constraint ck_messages_idempotency check (direction = 'inbound' or idempotency_key is not null),
    constraint ck_messages_cost check (credit_cost_units is null or credit_cost_units >= 0),
    constraint ck_messages_suppressed check ((suppressed_at is null) = (suppressed_reason is null)),
    constraint ck_messages_suppressed_reason check (
        suppressed_reason is null or suppressed_reason in ('blocked', 'recipient_unavailable')),
    constraint ck_messages_ai_outbound check (not is_ai_assisted or direction = 'outbound'),
    constraint ck_messages_edit_chikka check (edited_at is null or channel = 'chikka'),
    constraint ck_messages_delete_chikka check (deleted_for_everyone_at is null or channel = 'chikka'),
    -- Failed-message triage by administrators (FR-ADMIN-009): resolved needs a note and a resolver.
    constraint ck_messages_admin_resolution check (
        (admin_resolved_at is null) = (admin_resolution_note is null)
        and (admin_resolved_at is null or admin_resolved_by is not null)
        and (admin_resolved_at is null or channel = 'sms')),
    constraint uq_messages_conversation_seq unique (conversation_id, seq)
);

comment on table public.messages is
    'Logical message content. status is a projection of the latest delivery attempt (see message_deliveries). Never log or copy body outside this table.';
comment on column public.messages.idempotency_key is
    'Client-generated UUID. Unique per sender. Covers FR-MSG-001 client IDs and FR-SMS-012 Idempotency-Key.';
comment on column public.messages.request_hash is
    'Hash of the request payload so a reused key with a different payload can be rejected (409).';
comment on column public.messages.suppressed_at is
    'Set when a blocked sender''s message is accepted but hidden from the recipient. Never expose to clients.';

create unique index uq_messages_sender_idempotency
    on public.messages (sender_user_id, idempotency_key) where idempotency_key is not null;
create index idx_messages_search on public.messages using gin (search_vector);
create index idx_messages_sms_queue on public.messages (status, created_at)
    where channel = 'sms' and status in ('queued', 'retrying');
create index idx_messages_sms_send_rate on public.messages (sender_user_id, created_at desc)
    where channel = 'sms' and direction = 'outbound';
create index idx_messages_sender on public.messages (sender_user_id) where sender_user_id is not null;

create trigger trg_messages_updated_at
    before update on public.messages
    for each row execute function private.set_updated_at();

-- Assigns the next per-conversation sequence number and checks sender membership.
-- The conversation row lock serialises concurrent senders, so seq has no gaps for committed rows.
create function private.assign_message_seq()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    v_type text;
begin
    select conversation_type into v_type from public.conversations where id = new.conversation_id;
    if v_type is null then
        raise exception 'CONVERSATION_NOT_FOUND' using errcode = '23503';
    end if;
    if v_type <> new.channel then
        raise exception 'CHANNEL_MISMATCH: % message in a % conversation', new.channel, v_type
            using errcode = '23514';
    end if;
    if new.direction = 'outbound' and not exists (
        select 1 from public.conversation_members
        where conversation_id = new.conversation_id and user_id = new.sender_user_id and left_at is null
    ) then
        raise exception 'NOT_A_MEMBER: sender does not belong to the conversation' using errcode = '42501';
    end if;

    update public.conversations
       set last_seq = last_seq + 1,
           last_message_at = now()
     where id = new.conversation_id
    returning last_seq into new.seq;

    return new;
end;
$$;

create trigger trg_messages_assign_seq
    before insert on public.messages
    for each row execute function private.assign_message_seq();

-- Identity and ordering columns never change after insert.
create function private.protect_message_identity()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if new.conversation_id is distinct from old.conversation_id
       or new.seq is distinct from old.seq
       or new.channel is distinct from old.channel
       or new.direction is distinct from old.direction
       or new.sender_user_id is distinct from old.sender_user_id
       or new.sender_phone is distinct from old.sender_phone
       or new.idempotency_key is distinct from old.idempotency_key
       or new.created_at is distinct from old.created_at then
        raise exception 'messages identity columns are immutable' using errcode = '55000';
    end if;
    return new;
end;
$$;

create trigger trg_messages_protect_identity
    before update on public.messages
    for each row execute function private.protect_message_identity();

alter table public.messages enable row level security;
revoke all on table public.messages from public, anon, authenticated;
-- Deliberately omitted: request_hash, suppressed_at, suppressed_reason, is_ai_assisted,
-- ai_assistance_log_id. Recipients must not learn that a sender was blocked or used AI.
grant select (
    id, conversation_id, seq, channel, direction, sender_user_id, sender_phone, body, body_truncated,
    encoding, char_count, segment_count, status, status_version, is_simulated, edited_at,
    deleted_for_everyone_at, created_at, updated_at
) on table public.messages to authenticated;
grant all on table public.messages to service_role;

-- message_hides: "Delete for me" on a single message (FR-MSG-005, resolves OD-013).
-- Delete-for-everyone is a column on messages. Writes are backend-only because deletion is audit logged.
create table public.message_hides (
    message_id  uuid not null constraint fk_message_hides_message references public.messages (id) on delete cascade,
    user_id     uuid not null constraint fk_message_hides_user references public.profiles (id) on delete cascade,
    created_at  timestamptz not null default now(),
    constraint pk_message_hides primary key (message_id, user_id)
);

create index idx_message_hides_user on public.message_hides (user_id);

alter table public.message_hides enable row level security;
revoke all on table public.message_hides from public, anon, authenticated;
grant select on table public.message_hides to authenticated;
grant all on table public.message_hides to service_role;

create policy message_hides_select_own on public.message_hides
    for select to authenticated using (user_id = (select auth.uid()));

-- A member can read messages in their conversations, except messages they cleared or hid for
-- themselves, and except messages suppressed by a block (the sender still sees their own).
-- Writes are backend-only: sending needs rate limits, blocks, SMS policy checks and idempotency.
create policy messages_select_member on public.messages
    for select to authenticated
    using (
        exists (
            select 1 from public.conversation_members cm
            where cm.conversation_id = messages.conversation_id
              and cm.user_id = (select auth.uid())
              and cm.left_at is null
              and messages.seq > cm.cleared_before_seq)
        and (messages.suppressed_at is null or messages.sender_user_id = (select auth.uid()))
        and not exists (
            select 1 from public.message_hides h
            where h.message_id = messages.id and h.user_id = (select auth.uid()))
    );

-- message_segments: per-part facts for multi-part SMS (FR-SMS-002, FR-SMSRECV-007).
-- Kept separate from messages because parts have their own provider IDs and, for inbound
-- messages, arrive separately and are reassembled using the concatenation reference.
create table public.message_segments (
    id                  uuid primary key default gen_random_uuid(),
    message_id          uuid not null constraint fk_message_segments_message references public.messages (id) on delete cascade,
    delivery_id         uuid,
    segment_index       smallint not null,
    segment_count       smallint not null,
    encoding            text not null,
    char_count          smallint not null,
    units               smallint not null,
    concat_reference    integer,
    provider_segment_id text,
    provider_status     text,
    created_at          timestamptz not null default now(),

    constraint ck_message_segments_index check (segment_index >= 1 and segment_index <= segment_count),
    constraint ck_message_segments_count check (segment_count between 1 and 10),
    constraint ck_message_segments_encoding check (encoding in ('gsm7', 'ucs2')),
    constraint ck_message_segments_sizes check (char_count >= 0 and units >= char_count),
    constraint uq_message_segments_index unique (message_id, segment_index)
);

comment on table public.message_segments is
    'Optional per-part detail. messages.segment_count is the authoritative total; rows here exist when a provider reports parts individually or inbound parts need reassembly. units counts GSM-7 septets (extension characters count 2) or UTF-16 code units.';

create index idx_message_segments_delivery on public.message_segments (delivery_id) where delivery_id is not null;
create index idx_message_segments_concat on public.message_segments (concat_reference) where concat_reference is not null;

alter table public.message_segments enable row level security;
revoke all on table public.message_segments from public, anon, authenticated;
grant select (id, message_id, segment_index, segment_count, encoding, char_count, units, created_at)
    on table public.message_segments to authenticated;
grant all on table public.message_segments to service_role;

-- Visible exactly when the parent message is visible (the subquery runs under messages RLS).
create policy message_segments_select_via_message on public.message_segments
    for select to authenticated
    using (exists (select 1 from public.messages m where m.id = message_segments.message_id));

commit;
