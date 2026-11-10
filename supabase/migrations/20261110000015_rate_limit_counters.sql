-- Migration: 20261110000015_rate_limit_counters
-- Phase: 1
-- Description: Shared fixed-window counters and lockouts for rate-limited actions.
-- Dependencies: 20261110000001_foundation
-- Rollback: forward-fix only. Rows are disposable; purge by window_start.
--
-- Why a table: login lockout (FR-AUTH-006), contact search (20/min), contact requests (30/day)
-- and similar limits must hold across several backend instances, and the stack has no Redis.
-- SMS and AI hourly limits are derived from messages and ai_assistance_logs instead.

begin;

create table public.rate_limit_counters (
    scope           text not null,
    subject_hash    text not null,
    window_start    timestamptz not null default now(),
    attempts        integer not null default 0,
    locked_until    timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    constraint pk_rate_limit_counters primary key (scope, subject_hash),
    constraint ck_rate_limit_scope check (scope ~ '^[a-z][a-z0-9_.:]*$'),
    constraint ck_rate_limit_subject check (char_length(subject_hash) between 16 and 128),
    constraint ck_rate_limit_attempts check (attempts >= 0)
);

comment on table public.rate_limit_counters is
    'Server-only. subject_hash is a keyed hash of an email, IP address or user id, so raw identifiers are never stored. The backend resets attempts when the window passes.';

create index idx_rate_limit_window on public.rate_limit_counters (window_start);
create index idx_rate_limit_locked on public.rate_limit_counters (locked_until) where locked_until is not null;

create trigger trg_rate_limit_updated_at
    before update on public.rate_limit_counters
    for each row execute function private.set_updated_at();

alter table public.rate_limit_counters enable row level security;
revoke all on table public.rate_limit_counters from public, anon, authenticated;
grant all on table public.rate_limit_counters to service_role;
-- No policies: no client access.

commit;
