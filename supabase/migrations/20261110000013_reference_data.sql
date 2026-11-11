-- Migration: 20261110000013_reference_data
-- Phase: 1
-- Description: Safe baseline data every environment needs: system settings, SMS provider
--              configurations (mock active), and UNVERIFIED country capability rows.
-- Dependencies: 20261110000003
-- Rollback: forward-fix only.
-- Idempotent: ON CONFLICT DO NOTHING. Contains no personal data and nothing that enables live SMS.

begin;

insert into public.system_settings (key, value, description) values
    ('demo_grant_units',          '5000'::jsonb, 'One-time demo credit grant per new user, in units (credits x 100). 5000 = 50 credits.'),
    ('sms_outbound_paused',       'false'::jsonb, 'Feature switch: pause all outbound SMS (FR-ADMIN-013).'),
    ('ai_enabled',                'true'::jsonb,  'Feature switch (kill switch): AI features available (FR-ADMIN-013).'),
    ('registration_enabled',      'true'::jsonb,  'Feature switch: new sign-ups allowed (FR-ADMIN-013).'),
    ('sms_user_limit_per_hour',   '30'::jsonb,    'Outbound SMS per user per hour (FR-SMS-001).'),
    ('ai_user_limit_per_hour',    '30'::jsonb,    'AI requests per user per hour (FR-AI-012).'),
    ('sms_route_ttl_days',        '30'::jsonb,    'Days a reply route stays active after the last outbound message.')
on conflict (key) do nothing;

-- Simulation is the default and the only active provider. Live is defined but inactive and unconfirmed.
insert into public.provider_configurations
    (provider, display_name, mode, is_active, sender_registration_status, webhook_path, secret_ref)
values
    ('mock',   'Simulation (MockSmsProvider)', 'simulation', true,  'not_required',  '/api/v1/webhooks/mock',   null),
    ('twilio', 'Twilio (live)',                'live',       false, 'not_registered', '/api/v1/webhooks/twilio', 'TWILIO_AUTH_TOKEN')
on conflict (provider, mode) do nothing;

-- Country capabilities. Every row is UNVERIFIED: nothing is marked supported without evidence
-- (ck_sms_cap_verified_for_support). Countries without a row are treated as unsupported by the app.
insert into public.sms_country_capabilities
    (country_code, country_name, outbound_support, inbound_support, alphanumeric_sender_allowed,
     registered_sender_required, registered_sender_status, content_restrictions, credit_multiplier, notes)
values
    ('PH', 'Philippines',          'requires_verification', 'requires_verification', false, true,  'not_registered',
        'No unsolicited promotional content. Grey routes are not acceptable.',
        1, 'UNVERIFIED. A2P sender registration is required. Outbound, two-way support and pricing must be confirmed with the provider (OD-007).'),
    ('US', 'United States',        'requires_verification', 'requires_verification', false, false, 'not_required', null, 1, 'UNVERIFIED. Confirm with provider.'),
    ('AU', 'Australia',            'requires_verification', 'requires_verification', false, false, 'not_required', null, 1, 'UNVERIFIED. Confirm with provider.'),
    ('AE', 'United Arab Emirates', 'requires_verification', 'requires_verification', false, false, 'not_required', null, 1, 'UNVERIFIED. Confirm with provider.'),
    ('SG', 'Singapore',            'requires_verification', 'requires_verification', false, false, 'not_required', null, 1, 'UNVERIFIED. Confirm with provider.'),
    ('GB', 'United Kingdom',       'requires_verification', 'requires_verification', false, false, 'not_required', null, 1, 'UNVERIFIED. Confirm with provider.')
on conflict (country_code, version) do nothing;

commit;
