-- Migration: 20261112000001_sms_gateway
-- Phase: 2
-- Description: SMS gateway support. Extends country capabilities (pricing, number types, consent,
--              provider settings), stores the redacted provider response per delivery attempt,
--              and seeds simulation sender numbers and rate-limit settings.
-- Dependencies: 20261110000003, 20261110000008, 20261110000013
-- Rollback: forward-fix only.
-- Safe to apply: additive columns with defaults, idempotent seeds. No data is dropped.

begin;

alter table public.sms_country_capabilities
    add column price_units_per_segment bigint,
    add column supported_number_types  text[] not null default array['mobile', 'fixed_line_or_mobile']::text[],
    add column consent_required        boolean not null default true,
    add column provider_settings       jsonb not null default '{}'::jsonb;

alter table public.sms_country_capabilities
    add constraint ck_sms_cap_price check (price_units_per_segment is null or price_units_per_segment >= 0),
    add constraint ck_sms_cap_number_types check (
        supported_number_types <@ array['mobile', 'fixed_line_or_mobile', 'fixed_line', 'voip']::text[]
        and cardinality(supported_number_types) >= 1),
    add constraint ck_sms_cap_provider_settings check (jsonb_typeof(provider_settings) = 'object');

comment on column public.sms_country_capabilities.price_units_per_segment is
    'Credit units (credits x 100) per segment before credit_multiplier. NULL means pricing is not configured: live sends are blocked, simulation uses system_settings.sms_demo_units_per_segment and says so.';
comment on column public.sms_country_capabilities.supported_number_types is
    'Number types that may receive SMS for this country. Premium, toll-free and shared-cost numbers are never allowed.';
comment on column public.sms_country_capabilities.consent_required is
    'When true the sender must hold a recorded sms_sender_attestation for the recipient before sending.';
comment on column public.sms_country_capabilities.provider_settings is
    'Non-secret routing hints: sender_id (registered alphanumeric sender) and sender_number. Never credentials.';

-- Redacted provider response for the attempt (no credentials, no message body).
alter table public.message_deliveries
    add column provider_response jsonb;

alter table public.message_deliveries
    add constraint ck_deliveries_provider_response check (
        provider_response is null
        or (jsonb_typeof(provider_response) = 'object' and octet_length(provider_response::text) <= 4096));

comment on column public.message_deliveries.provider_response is
    'Redacted provider response for this attempt. Server-only (not in the client column grant).';

insert into public.system_settings (key, value, description) values
    ('sms_demo_units_per_segment',  '100'::jsonb, 'Simulation only: units per segment when a country has no configured price (100 units = 1 credit).'),
    ('sms_recipient_limit_per_hour', '10'::jsonb, 'Outbound SMS per recipient number per hour, across all senders (harassment protection).')
on conflict (key) do nothing;

-- Fictional sender pool for simulation (NANP 555-01xx range is reserved for fiction).
update public.provider_configurations
   set settings = jsonb_build_object(
        'sender_numbers', jsonb_build_array('+12025550190', '+12025550191', '+12025550192'))
 where provider = 'mock' and mode = 'simulation' and settings = '{}'::jsonb;

commit;
