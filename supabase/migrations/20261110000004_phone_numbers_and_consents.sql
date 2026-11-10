-- Migration: 20261110000004_phone_numbers_and_consents
-- Phase: 1
-- Description: phone_numbers (account numbers + OTP state) and user_consents (append-only).
-- Dependencies: 20261110000002_profiles
-- Rollback: forward-fix only.

begin;

-- phone_numbers: numbers claimed by or verified for an account (FR-AUTH-008, FR-AUTH-012).
-- SMS recipients that are not accounts live in contacts, not here.
create table public.phone_numbers (
    id                      uuid primary key default gen_random_uuid(),
    user_id                 uuid not null constraint fk_phone_numbers_user references public.profiles (id) on delete cascade,
    e164                    public.e164 not null,
    country_code            char(2) not null,
    verification_mode       text not null,
    status                  text not null default 'pending',
    otp_hash                text,
    otp_expires_at          timestamptz,
    otp_attempts            smallint not null default 0,
    otp_sent_count          smallint not null default 0,
    otp_window_started_at   timestamptz,
    last_otp_sent_at        timestamptz,
    verified_at             timestamptz,
    released_at             timestamptz,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),

    constraint ck_phone_numbers_country check (country_code ~ '^[A-Z]{2}$'),
    constraint ck_phone_numbers_mode check (verification_mode in ('live', 'simulated')),
    constraint ck_phone_numbers_status check (status in ('pending', 'verified', 'released')),
    constraint ck_phone_numbers_otp_attempts check (otp_attempts between 0 and 5),
    constraint ck_phone_numbers_otp_sent check (otp_sent_count between 0 and 10),
    constraint ck_phone_numbers_verified check ((status = 'verified') = (verified_at is not null) or status = 'released'),
    constraint ck_phone_numbers_released check ((status = 'released') = (released_at is not null)),
    constraint ck_phone_numbers_no_otp_when_done check (status = 'pending' or otp_hash is null)
);

comment on table public.phone_numbers is
    'Account phone numbers and their verification state. otp_hash stores a hash, never the code. Numbers verified in simulation must be re-verified for live.';

-- A verified number belongs to exactly one account per mode (FR-AUTH-008 AC3).
create unique index uq_phone_numbers_verified_number
    on public.phone_numbers (e164, verification_mode) where status = 'verified';
-- An account has at most one verified number per mode (FR-AUTH-012).
create unique index uq_phone_numbers_verified_per_user
    on public.phone_numbers (user_id, verification_mode) where status = 'verified';
-- Repeated verification attempts for the same number reuse the pending row.
create unique index uq_phone_numbers_pending
    on public.phone_numbers (user_id, e164, verification_mode) where status = 'pending';
create index idx_phone_numbers_user on public.phone_numbers (user_id);

create trigger trg_phone_numbers_updated_at
    before update on public.phone_numbers
    for each row execute function private.set_updated_at();

alter table public.phone_numbers enable row level security;
revoke all on table public.phone_numbers from public, anon, authenticated;
-- OTP columns are deliberately not granted to clients.
grant select (id, user_id, e164, country_code, verification_mode, status, verified_at, released_at, created_at, updated_at)
    on table public.phone_numbers to authenticated;
grant all on table public.phone_numbers to service_role;

create policy phone_numbers_select_own on public.phone_numbers
    for select to authenticated
    using (user_id = (select auth.uid()));
-- Writes are backend-only: verification touches rate limits, OTP delivery and audit.

-- user_consents: append-only consent history (FR-PRIVACY-007).
create table public.user_consents (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null constraint fk_user_consents_user references public.profiles (id) on delete restrict,
    consent_type    text not null,
    notice_version  text not null,
    decision        text not null,
    recipient_phone public.e164,
    source          text not null,
    ip_prefix       text,
    created_at      timestamptz not null default now(),

    constraint ck_user_consents_type check (
        consent_type in ('terms', 'privacy', 'ai_use', 'contact_import', 'sms_sender_attestation')),
    constraint ck_user_consents_decision check (decision in ('granted', 'withdrawn')),
    constraint ck_user_consents_source check (source in ('registration', 'settings', 'compose', 'import', 'admin')),
    constraint ck_user_consents_notice check (char_length(notice_version) between 1 and 40),
    -- SMS attestations are per recipient number; other consent types never carry one.
    constraint ck_user_consents_recipient check (
        (consent_type = 'sms_sender_attestation') = (recipient_phone is not null))
);

comment on table public.user_consents is
    'Append-only. Current state of a consent is the latest row for (user, type[, recipient]). Withdrawal inserts a new row. A recipient replying is not consent.';
comment on column public.user_consents.ip_prefix is 'Coarse network prefix only (for example /24). Never a full IP address.';

create index idx_user_consents_user_type on public.user_consents (user_id, consent_type, created_at desc);
create index idx_user_consents_recipient
    on public.user_consents (user_id, recipient_phone, created_at desc) where recipient_phone is not null;

create trigger trg_user_consents_immutable
    before update or delete on public.user_consents
    for each row execute function private.reject_mutation();

-- Latest decision for a consent. recipient is required for sms_sender_attestation.
create function private.has_active_consent(p_user_id uuid, p_type text, p_recipient public.e164 default null)
returns boolean
language sql
stable
set search_path = ''
as $$
    select coalesce((
        select c.decision = 'granted'
        from public.user_consents c
        where c.user_id = p_user_id
          and c.consent_type = p_type
          and c.recipient_phone is not distinct from p_recipient
        order by c.created_at desc, c.id desc
        limit 1
    ), false);
$$;

grant execute on function private.has_active_consent(uuid, text, public.e164) to service_role;

alter table public.user_consents enable row level security;
revoke all on table public.user_consents from public, anon, authenticated;
grant select on table public.user_consents to authenticated;
grant select, insert on table public.user_consents to service_role;

create policy user_consents_select_own on public.user_consents
    for select to authenticated
    using (user_id = (select auth.uid()));
-- Inserts are backend-only so the notice version and coarse IP are captured server-side.

commit;
