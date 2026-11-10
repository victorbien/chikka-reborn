-- Migration: 20261110000008_message_deliveries
-- Phase: 1 (internal channel), 2 (SMS)
-- Description: message_deliveries (one row per delivery attempt), provider_webhooks,
--              message_delivery_events, sms_routes, sms_opt_outs, status triggers, RLS.
-- Dependencies: 20261110000003, 20261110000005, 20261110000006, 20261110000007
-- Rollback: forward-fix only.
--
-- Model
--   messages            what was said
--   message_deliveries  one attempt to deliver it through one channel/provider (attempt_number 1..n)
--   provider_webhooks   raw, verified provider callbacks (server-only)
--   message_delivery_events  normalised status history per attempt (append-only)
-- Provider status names differ between providers, so the raw value is stored in provider_status
-- and mapped to the platform vocabulary in status.

begin;

create table public.message_deliveries (
    id                          uuid primary key default gen_random_uuid(),
    message_id                  uuid not null constraint fk_deliveries_message references public.messages (id) on delete cascade,
    attempt_number              smallint not null default 1,
    retry_of_delivery_id        uuid constraint fk_deliveries_retry_of references public.message_deliveries (id) on delete set null,
    channel                     text not null,
    provider_configuration_id   uuid constraint fk_deliveries_provider_cfg references public.provider_configurations (id) on delete restrict,
    recipient_user_id           uuid constraint fk_deliveries_recipient references public.profiles (id) on delete restrict,
    recipient_phone             public.e164,
    status                      text not null default 'queued',
    provider_status             text,
    provider_message_id         text,
    is_simulated                boolean not null default false,
    failure_class               text,
    is_permanent                boolean not null default false,
    failure_code                text,
    failure_reason              text,
    http_status                 smallint,
    status_version              integer not null default 1,
    next_attempt_at             timestamptz,
    locked_until                timestamptz,
    started_at                  timestamptz,
    accepted_at                 timestamptz,
    sent_at                     timestamptz,
    delivered_at                timestamptz,
    read_at                     timestamptz,
    terminal_at                 timestamptz,
    created_at                  timestamptz not null default now(),
    updated_at                  timestamptz not null default now(),

    constraint ck_deliveries_attempt check (attempt_number >= 1),
    constraint ck_deliveries_channel check (channel in ('chikka', 'sms')),
    constraint ck_deliveries_recipient check (recipient_user_id is not null or recipient_phone is not null),
    constraint ck_deliveries_status check (status in
        ('queued', 'accepted', 'sent', 'delivered', 'read', 'undelivered', 'failed')),
    constraint ck_deliveries_chikka check (
        channel = 'sms'
        or (provider_configuration_id is null and provider_message_id is null and not is_simulated
            and status in ('sent', 'delivered', 'read', 'failed'))),
    constraint ck_deliveries_sms_provider check (channel = 'chikka' or provider_configuration_id is not null),
    constraint ck_deliveries_read_chikka check (read_at is null or channel = 'chikka'),
    constraint ck_deliveries_failure_class check (
        failure_class is null
        or failure_class in ('policy', 'transient', 'ambiguous', 'permanent', 'configuration')),
    constraint ck_deliveries_failed_has_class check (status <> 'failed' or failure_class is not null),
    constraint ck_deliveries_permanent_terminal check (not is_permanent or status in ('failed', 'undelivered')),
    constraint ck_deliveries_failure_reason check (failure_reason is null or char_length(failure_reason) <= 500),
    constraint uq_deliveries_message_attempt unique (message_id, attempt_number)
);

comment on table public.message_deliveries is
    'One row per delivery attempt. A retry is a new row with attempt_number+1 and retry_of_delivery_id. For an inbound SMS the single row records receipt from the provider (status delivered). failure_reason must be redacted; never store message bodies or credentials.';
comment on column public.message_deliveries.provider_status is 'Raw status from the provider, unmodified.';
comment on column public.message_deliveries.status is 'Platform vocabulary mapped from provider_status.';
comment on column public.message_deliveries.locked_until is 'Worker lease. A row with a future locked_until is being processed.';

create unique index uq_deliveries_provider_message
    on public.message_deliveries (provider_configuration_id, provider_message_id)
    where provider_message_id is not null;
create index idx_deliveries_message on public.message_deliveries (message_id);
create index idx_deliveries_due on public.message_deliveries (next_attempt_at)
    where status = 'queued' and next_attempt_at is not null;
create index idx_deliveries_reconcile on public.message_deliveries (status, updated_at)
    where channel = 'sms' and status in ('accepted', 'sent');
create index idx_deliveries_recipient on public.message_deliveries (recipient_user_id, created_at desc)
    where recipient_user_id is not null;

create trigger trg_deliveries_updated_at
    before update on public.message_deliveries
    for each row execute function private.set_updated_at();

-- Validates a new attempt: simulation flag must match the provider mode.
create function private.validate_delivery_insert()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    v_mode text;
begin
    if new.provider_configuration_id is not null then
        select mode into v_mode from public.provider_configurations where id = new.provider_configuration_id;
        if new.is_simulated <> (v_mode = 'simulation') then
            raise exception 'SIMULATION_MISMATCH: is_simulated must match provider mode %', v_mode
                using errcode = '23514';
        end if;
    end if;
    if new.status in ('delivered', 'undelivered', 'failed', 'read') and new.terminal_at is null then
        new.terminal_at := now();
    end if;
    return new;
end;
$$;

create trigger trg_deliveries_validate_insert
    before insert on public.message_deliveries
    for each row execute function private.validate_delivery_insert();

-- Status only moves forward. Rank: queued 0, accepted 1, sent 2, terminal 3, read 4.
-- The first terminal state wins. One documented exception: an attempt that failed with an
-- ambiguous outcome may be corrected forward when a correlated provider event proves otherwise.
create function private.enforce_delivery_status_progress()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    v_old int;
    v_new int;
begin
    if new.status = old.status then
        return new;
    end if;

    v_old := case old.status when 'queued' then 0 when 'accepted' then 1 when 'sent' then 2
                             when 'delivered' then 3 when 'undelivered' then 3 when 'failed' then 3
                             when 'read' then 4 end;
    v_new := case new.status when 'queued' then 0 when 'accepted' then 1 when 'sent' then 2
                             when 'delivered' then 3 when 'undelivered' then 3 when 'failed' then 3
                             when 'read' then 4 end;

    if old.status = 'failed' and old.failure_class = 'ambiguous' and new.status <> 'queued' then
        null; -- correction path
    elsif v_new < v_old or (v_old = 3 and v_new = 3) then
        raise exception 'STATUS_REGRESSION: % -> % is not allowed', old.status, new.status
            using errcode = '55000';
    end if;

    new.status_version := old.status_version + 1;
    if new.status in ('delivered', 'undelivered', 'failed', 'read') and new.terminal_at is null then
        new.terminal_at := now();
    end if;
    return new;
end;
$$;

create trigger trg_deliveries_status_progress
    before update of status on public.message_deliveries
    for each row execute function private.enforce_delivery_status_progress();

-- Keeps messages.status as a projection of the latest attempt.
--   sms: transient failure or a queued retry attempt shows as 'retrying'
--   chikka: delivery status maps one-to-one
create function private.sync_message_status()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    v_direction text;
    v_latest smallint;
    v_status text;
begin
    select direction into v_direction from public.messages where id = new.message_id;
    if v_direction is null or v_direction = 'inbound' then
        return new;
    end if;

    select max(attempt_number) into v_latest from public.message_deliveries where message_id = new.message_id;
    if new.attempt_number < v_latest then
        return new;
    end if;

    v_status := new.status;
    if new.channel = 'sms' then
        if new.status = 'failed' and not new.is_permanent then
            v_status := 'retrying';
        elsif new.status = 'queued' and new.attempt_number > 1 then
            v_status := 'retrying';
        end if;
    end if;

    update public.messages
       set status = v_status,
           status_version = status_version + 1
     where id = new.message_id
       and status is distinct from v_status;

    return new;
end;
$$;

create trigger trg_deliveries_sync_message
    after insert or update of status, is_permanent on public.message_deliveries
    for each row execute function private.sync_message_status();

alter table public.message_segments
    add constraint fk_message_segments_delivery
    foreign key (delivery_id) references public.message_deliveries (id) on delete set null;

alter table public.message_deliveries enable row level security;
revoke all on table public.message_deliveries from public, anon, authenticated;
-- Operational detail (error codes, HTTP status, lease, provider IDs) stays server-side.
grant select (
    id, message_id, attempt_number, channel, recipient_user_id, status, is_simulated,
    sent_at, delivered_at, terminal_at, failure_class, is_permanent, created_at, updated_at
) on table public.message_deliveries to authenticated;
grant all on table public.message_deliveries to service_role;

-- The sender and the recipient of a message can see delivery state. Read receipts are written
-- only when the recipient has them enabled, so read_at is not part of the client column grant.
create policy deliveries_select_party on public.message_deliveries
    for select to authenticated
    using (
        recipient_user_id = (select auth.uid())
        or exists (
            select 1 from public.messages m
            where m.id = message_deliveries.message_id
              and m.sender_user_id = (select auth.uid())));

create policy deliveries_select_admin on public.message_deliveries
    for select to authenticated
    using ((select private.is_admin()));

-- provider_webhooks: verified raw provider callbacks. Server-only (FR-PRIVACY-010).
-- Only events with a valid signature are stored; rejected requests go to audit_logs.
create table public.provider_webhooks (
    id                          uuid primary key default gen_random_uuid(),
    provider                    text not null,
    provider_configuration_id   uuid constraint fk_webhooks_provider_cfg references public.provider_configurations (id) on delete set null,
    kind                        text not null,
    dedupe_key                  text not null,
    provider_message_id         text,
    raw_payload                 jsonb not null,
    signature_verified_at       timestamptz not null,
    is_simulated                boolean not null default false,
    processing_status           text not null default 'received',
    process_attempts            smallint not null default 0,
    next_process_at             timestamptz,
    processed_at                timestamptz,
    error_code                  text,
    routing_result              text,
    delivery_id                 uuid constraint fk_webhooks_delivery references public.message_deliveries (id) on delete set null,
    message_id                  uuid constraint fk_webhooks_message references public.messages (id) on delete set null,
    received_at                 timestamptz not null default now(),
    purge_after                 timestamptz not null default (now() + interval '90 days'),
    created_at                  timestamptz not null default now(),
    updated_at                  timestamptz not null default now(),

    constraint ck_webhooks_provider check (provider ~ '^[a-z][a-z0-9_]*$'),
    constraint ck_webhooks_kind check (kind in ('status', 'inbound')),
    constraint ck_webhooks_processing check (
        processing_status in ('received', 'processed', 'failed', 'ignored', 'orphaned')),
    constraint ck_webhooks_routing check (
        routing_result is null
        or routing_result in ('routed', 'unrouted', 'opt_out', 'blocked', 'duplicate', 'suppressed')),
    constraint ck_webhooks_payload_object check (jsonb_typeof(raw_payload) = 'object'),
    constraint ck_webhooks_payload_size check (octet_length(raw_payload::text) <= 65536),
    constraint ck_webhooks_attempts check (process_attempts >= 0),
    constraint uq_webhooks_dedupe unique (provider, kind, dedupe_key)
);

comment on table public.provider_webhooks is
    'Raw verified callbacks. Contains message content for inbound events, so it is server-only. Retention: at least 90 days (purge_after), then purged by a scheduled job.';

create index idx_webhooks_pending on public.provider_webhooks (next_process_at)
    where processing_status in ('received', 'failed', 'orphaned');
create index idx_webhooks_provider_message on public.provider_webhooks (provider, provider_message_id)
    where provider_message_id is not null;
create index idx_webhooks_unrouted on public.provider_webhooks (received_at desc) where routing_result = 'unrouted';
create index idx_webhooks_purge on public.provider_webhooks (purge_after);

create trigger trg_webhooks_updated_at
    before update on public.provider_webhooks
    for each row execute function private.set_updated_at();

alter table public.provider_webhooks enable row level security;
revoke all on table public.provider_webhooks from public, anon, authenticated;
grant all on table public.provider_webhooks to service_role;
-- No policies: no client access of any kind.

-- message_delivery_events: append-only normalised history per attempt (FR-SMS-004).
-- Not a copy of provider_webhooks: this records what the platform concluded and whether it applied.
create table public.message_delivery_events (
    id                  uuid primary key default gen_random_uuid(),
    delivery_id         uuid not null constraint fk_delivery_events_delivery references public.message_deliveries (id) on delete cascade,
    webhook_id          uuid constraint fk_delivery_events_webhook references public.provider_webhooks (id) on delete set null,
    dedupe_key          text not null,
    source              text not null,
    provider_status     text,
    normalised_status   text not null,
    provider_error_code text,
    occurred_at         timestamptz,
    received_at         timestamptz not null default now(),
    applied             boolean not null,
    ignore_reason       text,

    constraint ck_delivery_events_source check (source in ('send_response', 'webhook', 'poll', 'simulation', 'system')),
    constraint ck_delivery_events_status check (normalised_status in
        ('queued', 'accepted', 'sent', 'delivered', 'read', 'undelivered', 'failed')),
    constraint ck_delivery_events_ignored check (applied or ignore_reason is not null),
    constraint uq_delivery_events_dedupe unique (delivery_id, dedupe_key)
);

comment on table public.message_delivery_events is
    'Append-only. applied=false rows record out-of-order, duplicate or conflicting provider signals with the reason.';

create index idx_delivery_events_delivery on public.message_delivery_events (delivery_id, received_at);
create index idx_delivery_events_webhook on public.message_delivery_events (webhook_id) where webhook_id is not null;

create trigger trg_delivery_events_immutable
    before update or delete on public.message_delivery_events
    for each row execute function private.reject_mutation();

alter table public.message_delivery_events enable row level security;
revoke all on table public.message_delivery_events from public, anon, authenticated;
grant select, insert on table public.message_delivery_events to service_role;
-- Server-only. Clients see status via message_deliveries.

-- sms_routes: reply routing for inbound SMS (FR-SMSRECV routing model, OD-011).
-- A (platform number, remote number) pair is held by one user at a time for 30 days after the last outbound.
create table public.sms_routes (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null constraint fk_sms_routes_user references public.profiles (id) on delete restrict,
    conversation_id     uuid not null constraint fk_sms_routes_conversation references public.conversations (id) on delete cascade,
    platform_number     public.e164 not null,
    remote_number       public.e164 not null,
    status              text not null default 'active',
    last_outbound_at    timestamptz not null default now(),
    expires_at          timestamptz not null default (now() + interval '30 days'),
    released_at         timestamptz,
    release_reason      text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),

    constraint ck_sms_routes_status check (status in ('active', 'released')),
    constraint ck_sms_routes_released check ((status = 'released') = (released_at is not null))
);

comment on table public.sms_routes is
    'No two users hold the same active (platform_number, remote_number). If no platform number is free the send is blocked (FR-SMSRECV).';

create unique index uq_sms_routes_active_pair on public.sms_routes (platform_number, remote_number) where status = 'active';
create unique index uq_sms_routes_active_user_remote on public.sms_routes (user_id, remote_number) where status = 'active';
create index idx_sms_routes_expiry on public.sms_routes (expires_at) where status = 'active';
create index idx_sms_routes_conversation on public.sms_routes (conversation_id);

create trigger trg_sms_routes_updated_at
    before update on public.sms_routes
    for each row execute function private.set_updated_at();

alter table public.sms_routes enable row level security;
revoke all on table public.sms_routes from public, anon, authenticated;
grant select on table public.sms_routes to authenticated;
grant all on table public.sms_routes to service_role;

create policy sms_routes_select_own on public.sms_routes
    for select to authenticated using (user_id = (select auth.uid()));
create policy sms_routes_select_admin on public.sms_routes
    for select to authenticated using ((select private.is_admin()));

-- sms_opt_outs: recipient opt-outs, platform-wide per number (FR-SMSRECV-012, FR-PRIVACY-008).
-- platform_number null means the opt-out applies to every sender number.
create table public.sms_opt_outs (
    id                  uuid primary key default gen_random_uuid(),
    remote_phone        public.e164 not null,
    platform_number     public.e164,
    is_opted_out        boolean not null default true,
    source              text not null,
    keyword             text,
    source_webhook_id   uuid constraint fk_opt_outs_webhook references public.provider_webhooks (id) on delete set null,
    opted_out_at        timestamptz not null default now(),
    opted_in_at         timestamptz,
    lifted_by           uuid constraint fk_opt_outs_lifted_by references public.profiles (id) on delete set null,
    lift_source         text,
    lift_reason         text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),

    constraint ck_opt_outs_source check (source in ('keyword', 'provider_block', 'admin', 'user_request')),
    constraint ck_opt_outs_lift_source check (lift_source is null or lift_source in ('recipient_keyword', 'admin')),
    constraint ck_opt_outs_state check (is_opted_out = (opted_in_at is null)),
    constraint ck_opt_outs_admin_reason check (lift_source is distinct from 'admin' or (lift_reason is not null and lifted_by is not null))
);

comment on table public.sms_opt_outs is
    'Server-only. An opt-out blocks sends from every user to that number and survives account changes. Only the recipient (START keyword) or an admin with a recorded reason can lift it.';

create unique index uq_opt_outs_number_scope
    on public.sms_opt_outs (remote_phone, coalesce(platform_number::text, ''));
create index idx_opt_outs_active on public.sms_opt_outs (remote_phone) where is_opted_out;

create trigger trg_opt_outs_updated_at
    before update on public.sms_opt_outs
    for each row execute function private.set_updated_at();

alter table public.sms_opt_outs enable row level security;
revoke all on table public.sms_opt_outs from public, anon, authenticated;
grant all on table public.sms_opt_outs to service_role;
-- No policies: the backend exposes only a boolean "recipient opted out" flag per own contact.

commit;
