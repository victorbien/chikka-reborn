-- Migration: 20261110000009_credits
-- Phase: 2 (demo ledger), 4 (live top-up)
-- Description: messaging_credits (balances) and credit_transactions (append-only ledger).
-- Dependencies: 20261110000003, 20261110000007
-- Rollback: forward-fix only. The ledger is never deleted.
--
-- Units: credits x 100 stored as bigint (FR-CREDIT). 1.00 credit = 100 units.
-- Two ledgers per user: 'live' (real) and 'demo' (simulation). They never convert into each other.
-- The balance row is changed only by the trigger on credit_transactions, in the same transaction,
-- under a row lock. That makes concurrent sends unable to overdraw (AC-4-004).

begin;

create table public.messaging_credits (
    user_id             uuid not null constraint fk_credits_user references public.profiles (id) on delete restrict,
    ledger_type         text not null,
    balance_units       bigint not null default 0,
    reserved_units      bigint not null default 0,
    low_balance_alerted boolean not null default false,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),

    constraint pk_messaging_credits primary key (user_id, ledger_type),
    constraint ck_credits_ledger check (ledger_type in ('live', 'demo')),
    constraint ck_credits_balance check (balance_units >= 0),
    constraint ck_credits_reserved check (reserved_units >= 0),
    constraint ck_credits_reserved_within_balance check (reserved_units <= balance_units)
);

comment on table public.messaging_credits is
    'Current balance per user and ledger. Derived state: always equals the sum of credit_transactions. Available = balance_units - reserved_units.';
comment on column public.messaging_credits.low_balance_alerted is
    'Set once a low-balance notification fires; cleared when the balance rises above the threshold (fires once per crossing).';

create trigger trg_credits_updated_at
    before update on public.messaging_credits
    for each row execute function private.set_updated_at();

create table public.credit_transactions (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null,
    ledger_type         text not null,
    entry_type          text not null,
    balance_delta       bigint not null,
    reserved_delta      bigint not null default 0,
    balance_after       bigint,
    reserved_after      bigint,
    message_id          uuid constraint fk_credit_tx_message references public.messages (id) on delete restrict,
    capability_id       uuid constraint fk_credit_tx_capability references public.sms_country_capabilities (id) on delete restrict,
    provider            text,
    country_code        char(2),
    segment_count       smallint,
    external_reference  text,
    reason              text,
    actor_id            uuid constraint fk_credit_tx_actor references public.profiles (id) on delete restrict,
    created_at          timestamptz not null default now(),

    constraint fk_credit_tx_account foreign key (user_id, ledger_type)
        references public.messaging_credits (user_id, ledger_type) on delete restrict,
    constraint ck_credit_tx_entry_shape check (
        (entry_type = 'grant'               and balance_delta > 0 and reserved_delta = 0)
     or (entry_type = 'top_up'              and balance_delta > 0 and reserved_delta = 0)
     or (entry_type = 'reservation'         and balance_delta = 0 and reserved_delta > 0)
     or (entry_type = 'reservation_release' and balance_delta = 0 and reserved_delta < 0)
     or (entry_type = 'deduction'           and balance_delta < 0 and reserved_delta <= 0)
     or (entry_type = 'refund'              and balance_delta > 0 and reserved_delta = 0)
     or (entry_type = 'adjustment'          and balance_delta <> 0 and reserved_delta = 0)),
    -- Demo credits can never be bought or converted.
    constraint ck_credit_tx_demo_no_topup check (ledger_type = 'live' or entry_type <> 'top_up'),
    constraint ck_credit_tx_message_required check (
        entry_type not in ('reservation', 'reservation_release', 'deduction', 'refund') or message_id is not null),
    constraint ck_credit_tx_adjustment_audit check (
        entry_type <> 'adjustment' or (reason is not null and char_length(btrim(reason)) > 0 and actor_id is not null)),
    constraint ck_credit_tx_segments check (segment_count is null or segment_count between 1 and 10),
    constraint ck_credit_tx_country check (country_code is null or country_code ~ '^[A-Z]{2}$')
);

comment on table public.credit_transactions is
    'Append-only ledger. balance_after and reserved_after are filled by trigger. Every send-related entry records message, provider, country, segments and the capability version (rate) used.';

-- Idempotency: each message gets at most one entry of each type (refund exactly once, FR-SMS-010).
create unique index uq_credit_tx_message_entry
    on public.credit_transactions (message_id, entry_type) where message_id is not null;
-- Payment gateway events apply once.
create unique index uq_credit_tx_external_reference
    on public.credit_transactions (external_reference) where external_reference is not null;
create index idx_credit_tx_user on public.credit_transactions (user_id, ledger_type, created_at desc);

create function private.apply_credit_transaction()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    v_balance bigint;
    v_reserved bigint;
    v_message_reserved bigint;
    v_simulated boolean;
begin
    -- Simulated messages use only the demo ledger; real messages use only the live ledger.
    -- Real credits can therefore never be charged for a simulated send (and the reverse).
    if new.message_id is not null then
        select is_simulated into v_simulated from public.messages where id = new.message_id;
        if v_simulated is distinct from (new.ledger_type = 'demo') then
            raise exception 'LEDGER_MISMATCH: % message cannot use the % ledger',
                case when v_simulated then 'simulated' else 'live' end, new.ledger_type
                using errcode = '23514';
        end if;
    end if;

    select balance_units, reserved_units
      into v_balance, v_reserved
      from public.messaging_credits
     where user_id = new.user_id and ledger_type = new.ledger_type
       for update;

    -- A release or capture can only consume what this same message reserved.
    if new.reserved_delta < 0 then
        select coalesce(sum(reserved_delta), 0)
          into v_message_reserved
          from public.credit_transactions
         where message_id is not distinct from new.message_id
           and user_id = new.user_id
           and ledger_type = new.ledger_type;
        if new.message_id is null or v_message_reserved + new.reserved_delta < 0 then
            raise exception 'RESERVATION_UNDERFLOW: message has % reserved units, cannot consume %',
                coalesce(v_message_reserved, 0), -new.reserved_delta using errcode = '55000';
        end if;
    end if;

    new.balance_after := v_balance + new.balance_delta;
    new.reserved_after := v_reserved + new.reserved_delta;

    if new.reserved_after < 0 then
        raise exception 'RESERVATION_UNDERFLOW: cannot release more than is reserved' using errcode = '55000';
    end if;
    if new.balance_after < 0 or new.balance_after < new.reserved_after then
        raise exception 'INSUFFICIENT_CREDITS: available % units, required % units',
            (v_balance - v_reserved), greatest(-new.balance_delta, new.reserved_delta)
            using errcode = 'P0001';
    end if;

    update public.messaging_credits
       set balance_units = new.balance_after,
           reserved_units = new.reserved_after
     where user_id = new.user_id and ledger_type = new.ledger_type;

    return new;
end;
$$;

create trigger trg_credit_tx_apply
    before insert on public.credit_transactions
    for each row execute function private.apply_credit_transaction();
create trigger trg_credit_tx_immutable
    before update or delete on public.credit_transactions
    for each row execute function private.reject_mutation();

-- Row level security ---------------------------------------------------------
alter table public.messaging_credits enable row level security;
revoke all on table public.messaging_credits from public, anon, authenticated;
grant select (user_id, ledger_type, balance_units, reserved_units, updated_at)
    on table public.messaging_credits to authenticated;
grant select, insert, update on table public.messaging_credits to service_role;

create policy credits_select_own on public.messaging_credits
    for select to authenticated using (user_id = (select auth.uid()));
create policy credits_select_admin on public.messaging_credits
    for select to authenticated using ((select private.is_admin()));
-- No write policies. Balances change only through credit_transactions.

alter table public.credit_transactions enable row level security;
revoke all on table public.credit_transactions from public, anon, authenticated;
grant select (id, user_id, ledger_type, entry_type, balance_delta, reserved_delta, balance_after,
              reserved_after, message_id, provider, country_code, segment_count, reason, created_at)
    on table public.credit_transactions to authenticated;
grant select, insert on table public.credit_transactions to service_role;

create policy credit_tx_select_own on public.credit_transactions
    for select to authenticated using (user_id = (select auth.uid()));
create policy credit_tx_select_admin on public.credit_transactions
    for select to authenticated using ((select private.is_admin()));
-- Inserts: service role only. Admin adjustments go through the backend so the actor, reason
-- and re-authentication are enforced and audit logged.

commit;
