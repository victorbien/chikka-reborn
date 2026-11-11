-- Migration: 20261110000003_platform_configuration
-- Phase: 1 (needed by Phase 2 SMS)
-- Description: system_settings, provider_configurations, sms_country_capabilities.
-- Dependencies: 20261110000002_profiles
-- Rollback: forward-fix only.

begin;

-- system_settings: admin-changeable runtime switches (FR-ADMIN-010, FR-ADMIN-013).
-- Server-only. Secrets never belong here.
create table public.system_settings (
    key         text primary key,
    value       jsonb not null,
    description text,
    updated_by  uuid constraint fk_system_settings_updated_by references public.profiles (id) on delete set null,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    constraint ck_system_settings_key check (key ~ '^[a-z][a-z0-9_.]*$')
);

comment on table public.system_settings is
    'Runtime switches and defaults editable by administrators (feature switches, demo grant). Server-only. No secrets.';

create trigger trg_system_settings_updated_at
    before update on public.system_settings
    for each row execute function private.set_updated_at();

alter table public.system_settings enable row level security;
revoke all on table public.system_settings from public, anon, authenticated;
grant all on table public.system_settings to service_role;
-- No policies: clients have no direct access.

-- provider_configurations: non-secret SMS provider settings (FR-ADMIN-014).
create table public.provider_configurations (
    id                          uuid primary key default gen_random_uuid(),
    provider                    text not null,
    display_name                text not null,
    mode                        text not null,
    is_active                   boolean not null default false,
    secret_ref                  text,
    sender_registration_status  text not null default 'not_registered',
    webhook_path                text,
    max_retry_attempts          smallint not null default 3,
    retry_base_seconds          integer not null default 5,
    retry_cap_seconds           integer not null default 300,
    retry_multiplier            numeric(4, 2) not null default 2,
    settings                    jsonb not null default '{}'::jsonb,
    live_confirmed_at           timestamptz,
    live_confirmed_by           uuid constraint fk_provider_cfg_confirmed_by references public.profiles (id) on delete set null,
    live_confirmed_environment  text,
    created_at                  timestamptz not null default now(),
    updated_at                  timestamptz not null default now(),

    constraint ck_provider_cfg_provider check (provider ~ '^[a-z][a-z0-9_]*$'),
    constraint ck_provider_cfg_mode check (mode in ('simulation', 'live')),
    constraint ck_provider_cfg_mock_is_simulation check ((provider = 'mock') = (mode = 'simulation')),
    constraint ck_provider_cfg_registration check (
        sender_registration_status in ('not_required', 'not_registered', 'pending', 'registered')),
    constraint ck_provider_cfg_retry_attempts check (max_retry_attempts between 1 and 10),
    constraint ck_provider_cfg_retry_timing check (
        retry_base_seconds > 0 and retry_cap_seconds >= retry_base_seconds and retry_multiplier >= 1),
    constraint ck_provider_cfg_settings check (jsonb_typeof(settings) = 'object'),
    -- A live provider can only be active after an operator confirmed it for an environment.
    constraint ck_provider_cfg_live_confirmed check (
        not (is_active and mode = 'live')
        or (live_confirmed_at is not null and live_confirmed_by is not null and live_confirmed_environment is not null)),
    constraint uq_provider_cfg_provider_mode unique (provider, mode)
);

comment on table public.provider_configurations is
    'Non-secret SMS provider settings. secret_ref names an environment variable or secret-manager key, never the secret itself.';
comment on column public.provider_configurations.secret_ref is
    'Name of the secret in the environment or secret manager. Never store the secret value here.';

-- Exactly one provider configuration is active at a time. This is the "never mix modes" rule.
create unique index uq_provider_cfg_single_active on public.provider_configurations ((true)) where is_active;

create trigger trg_provider_cfg_updated_at
    before update on public.provider_configurations
    for each row execute function private.set_updated_at();

alter table public.provider_configurations enable row level security;
revoke all on table public.provider_configurations from public, anon, authenticated;
grant select on table public.provider_configurations to authenticated;
grant all on table public.provider_configurations to service_role;

create policy provider_cfg_select_admin on public.provider_configurations
    for select to authenticated
    using ((select private.is_admin()));

-- sms_country_capabilities: versioned per-country SMS rules (FR-ADMIN-005, FR-CREDIT-002).
-- Each change inserts a new version; messages reference the version used.
create table public.sms_country_capabilities (
    id                          uuid primary key default gen_random_uuid(),
    country_code                char(2) not null,
    country_name                text not null,
    version                     integer not null default 1,
    is_current                  boolean not null default true,
    effective_from              timestamptz not null default now(),
    outbound_support            text not null default 'unsupported',
    inbound_support             text not null default 'unsupported',
    alphanumeric_sender_allowed boolean not null default false,
    registered_sender_required  boolean not null default false,
    registered_sender_status    text not null default 'not_required',
    content_restrictions        text,
    credit_multiplier           numeric(8, 4) not null default 1,
    max_segments                smallint not null default 10,
    notes                       text,
    verified_at                 timestamptz,
    verified_by                 uuid constraint fk_sms_cap_verified_by references public.profiles (id) on delete set null,
    created_by                  uuid constraint fk_sms_cap_created_by references public.profiles (id) on delete set null,
    created_at                  timestamptz not null default now(),
    updated_at                  timestamptz not null default now(),

    constraint ck_sms_cap_country check (country_code ~ '^[A-Z]{2}$'),
    constraint ck_sms_cap_outbound check (outbound_support in ('unsupported', 'requires_verification', 'supported')),
    constraint ck_sms_cap_inbound check (inbound_support in ('unsupported', 'requires_verification', 'supported')),
    constraint ck_sms_cap_registration check (
        registered_sender_status in ('not_required', 'not_registered', 'pending', 'registered')),
    constraint ck_sms_cap_multiplier check (credit_multiplier > 0),
    constraint ck_sms_cap_segments check (max_segments between 1 and 10),
    constraint ck_sms_cap_version check (version >= 1),
    -- Philippines always needs an explicit sender registration status (FR-ADMIN-005).
    constraint ck_sms_cap_ph_registration check (country_code <> 'PH' or registered_sender_status <> 'not_required'),
    -- A required registration must be complete before outbound can be marked supported.
    constraint ck_sms_cap_registered_for_support check (
        not (outbound_support = 'supported' and registered_sender_required)
        or registered_sender_status = 'registered'),
    -- Nothing is "supported" without recorded verification evidence.
    constraint ck_sms_cap_verified_for_support check (
        (outbound_support <> 'supported' and inbound_support <> 'supported')
        or (verified_at is not null and verified_by is not null)),
    constraint uq_sms_cap_country_version unique (country_code, version)
);

comment on table public.sms_country_capabilities is
    'Versioned per-country SMS capability rules. Unknown countries are treated as unsupported by the application.';

create unique index uq_sms_cap_current on public.sms_country_capabilities (country_code) where is_current;

create trigger trg_sms_cap_updated_at
    before update on public.sms_country_capabilities
    for each row execute function private.set_updated_at();

alter table public.sms_country_capabilities enable row level security;
revoke all on table public.sms_country_capabilities from public, anon, authenticated;
grant select on table public.sms_country_capabilities to authenticated;
grant insert on table public.sms_country_capabilities to authenticated;
-- Versions are immutable; the only column an admin may change is the current-version flag.
grant update (is_current) on table public.sms_country_capabilities to authenticated;
grant all on table public.sms_country_capabilities to service_role;

-- Everyone signed in can read the current rules (compose screen capability display).
create policy sms_cap_select_current on public.sms_country_capabilities
    for select to authenticated
    using (is_current);

create policy sms_cap_select_admin on public.sms_country_capabilities
    for select to authenticated
    using ((select private.is_admin()));

create policy sms_cap_insert_admin on public.sms_country_capabilities
    for insert to authenticated
    with check ((select private.is_admin()));

create policy sms_cap_update_admin on public.sms_country_capabilities
    for update to authenticated
    using ((select private.is_admin()))
    with check ((select private.is_admin()));

commit;
