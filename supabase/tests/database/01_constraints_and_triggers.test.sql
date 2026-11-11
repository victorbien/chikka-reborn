-- Test file 01: constraints, domains, bootstrap and immutability rules.
-- Runs in a transaction that is rolled back.
begin;

select tests.create_user(tests.uid(1), 'alice');
select tests.create_user(tests.uid(2), 'bob');
select tests.create_user(tests.uid(3), 'carol');

-- Profile bootstrap (OD-010) --------------------------------------------------------------
do $$
begin
    perform tests.assert_eq((select count(*) from public.messaging_credits where user_id = tests.uid(1)), 2::bigint,
        'new profile gets live and demo credit rows');
    perform tests.assert_eq((select balance_units from public.messaging_credits
                              where user_id = tests.uid(1) and ledger_type = 'demo'), 5000::bigint,
        'new profile gets the 50 credit demo grant');
    perform tests.assert_eq((select balance_units from public.messaging_credits
                              where user_id = tests.uid(1) and ledger_type = 'live'), 0::bigint,
        'live balance starts at zero');
    perform tests.assert_eq((select count(*) from public.notification_preferences where user_id = tests.uid(1)), 1::bigint,
        'new profile gets notification preferences');
    perform tests.assert_eq((select status from public.profiles where id = tests.uid(1)), 'active',
        'helper activated the profile');
end
$$;

-- Profiles ---------------------------------------------------------------------------------
do $$
begin
    perform tests.assert_error($q$update public.profiles set username = 'ALICE' where id = tests.uid(2)$q$, '23505',
        'usernames are unique case-insensitively');
    perform tests.assert_error($q$update public.profiles set username = 'ab' where id = tests.uid(2)$q$, '23514',
        'usernames shorter than 3 characters are rejected');
    perform tests.assert_error($q$update public.profiles set username = 'bad name!' where id = tests.uid(2)$q$, '23514',
        'usernames allow only letters, digits and underscore');
    perform tests.assert_error($q$update public.profiles set bio = repeat('x', 161) where id = tests.uid(2)$q$, '23514',
        'bio is limited to 160 characters');
    perform tests.assert_error($q$update public.profiles set display_name = 'A' where id = tests.uid(2)$q$, '23514',
        'display name needs at least 2 characters');
    perform tests.assert_error($q$update public.profiles set onboarding_completed_at = now(), username = null where id = tests.uid(2)$q$, '23514',
        'onboarding cannot complete without a username');
    perform tests.assert_error($q$update public.profiles set status = 'deleted' where id = tests.uid(2)$q$, '23514',
        'status deleted requires deleted_at');
    perform tests.assert_error($q$delete from auth.users where id = tests.uid(2)$q$, '23001',
        'deleting an auth user is blocked while a profile exists (ledgers and audit must survive)');
end
$$;

-- E.164 domain -----------------------------------------------------------------------------
do $$
begin
    perform tests.assert_error($q$select 'not-a-number'::public.e164$q$, '23514', 'text is not E.164');
    perform tests.assert_error($q$select '+0123456789'::public.e164$q$, '23514', 'country code cannot start with 0');
    perform tests.assert_error($q$select '05550100123'::public.e164$q$, '23514', 'local format lacks +');
    perform tests.assert_ok($q$select '+15550100001'::public.e164$q$, 'a valid E.164 number is accepted');
end
$$;

-- Phone numbers ----------------------------------------------------------------------------
do $$
begin
    insert into public.phone_numbers (user_id, e164, country_code, verification_mode, status, verified_at)
    values (tests.uid(1), '+15550100001', 'US', 'simulated', 'verified', now());

    perform tests.assert_error($q$insert into public.phone_numbers (user_id, e164, country_code, verification_mode, status, verified_at)
        values (tests.uid(2), '+15550100001', 'US', 'simulated', 'verified', now())$q$, '23505',
        'one account per verified number per mode');
    perform tests.assert_error($q$insert into public.phone_numbers (user_id, e164, country_code, verification_mode, status, verified_at)
        values (tests.uid(1), '+15550100002', 'US', 'simulated', 'verified', now())$q$, '23505',
        'one verified number per account per mode');
    perform tests.assert_ok($q$insert into public.phone_numbers (user_id, e164, country_code, verification_mode, status, verified_at)
        values (tests.uid(1), '+15550100001', 'US', 'live', 'verified', now())$q$,
        'simulation verification does not block live verification of the same number');
    perform tests.assert_error($q$insert into public.phone_numbers (user_id, e164, country_code, verification_mode, status, otp_attempts)
        values (tests.uid(3), '+15550100003', 'US', 'live', 'pending', 6)$q$, '23514',
        'OTP attempts are capped at 5');
end
$$;

-- Contacts ---------------------------------------------------------------------------------
do $$
begin
    perform tests.assert_error($q$insert into public.contacts (owner_id, contact_type, contact_user_id, phone_e164)
        values (tests.uid(1), 'chikka', tests.uid(2), '+15550100005')$q$, '23514', 'a contact is either a user or a number');
    perform tests.assert_error($q$insert into public.contacts (owner_id, contact_type, contact_user_id)
        values (tests.uid(1), 'chikka', tests.uid(1))$q$, '23514', 'cannot add yourself');
    perform tests.assert_error($q$insert into public.contacts (owner_id, contact_type, phone_e164)
        values (tests.uid(1), 'sms', '+15550100005')$q$, '23514', 'SMS contacts need a name');

    insert into public.contacts (owner_id, contact_type, phone_e164, display_name)
    values (tests.uid(1), 'sms', '+15550100005', 'Sample');
    perform tests.assert_error($q$insert into public.contacts (owner_id, contact_type, phone_e164, display_name)
        values (tests.uid(1), 'sms', '+15550100005', 'Again')$q$, '23505', 'one contact per number per owner');
    perform tests.assert_ok($q$insert into public.contacts (owner_id, contact_type, phone_e164, display_name)
        values (tests.uid(2), 'sms', '+15550100005', 'Other owner same number')$q$, 'different owners may share a number');
    perform tests.assert_error($q$update public.contacts set muted_until = now() + interval '1 hour', muted_indefinitely = true
        where owner_id = tests.uid(1)$q$, '23514', 'mute is timed or indefinite, not both');
end
$$;

-- Contact requests: one pending request per pair, in either direction ---------------------
do $$
begin
    insert into public.contact_requests (from_user_id, to_user_id) values (tests.uid(1), tests.uid(2));
    perform tests.assert_error($q$insert into public.contact_requests (from_user_id, to_user_id)
        values (tests.uid(2), tests.uid(1))$q$, '23505', 'a reverse pending request is rejected');
    perform tests.assert_error($q$insert into public.contact_requests (from_user_id, to_user_id)
        values (tests.uid(1), tests.uid(1))$q$, '23514', 'cannot request yourself');
    perform tests.assert_error($q$insert into public.contact_requests (from_user_id, to_user_id, note)
        values (tests.uid(3), tests.uid(1), repeat('n', 141))$q$, '23514', 'note is limited to 140 characters');
    perform tests.assert_error($q$update public.contact_requests set status = 'rejected'
        where from_user_id = tests.uid(1)$q$, '23514', 'a decision needs responded_at');
end
$$;

-- Contact groups: limit of 20, owner-consistent members -----------------------------------
do $$
declare
    v_group uuid;
    v_contact uuid;
    i int;
begin
    for i in 1..20 loop
        insert into public.contact_groups (owner_id, name) values (tests.uid(3), 'group ' || i);
    end loop;
    perform tests.assert_error($q$insert into public.contact_groups (owner_id, name) values (tests.uid(3), 'one too many')$q$,
        '23514', 'at most 20 groups per user');
    perform tests.assert_error($q$insert into public.contact_groups (owner_id, name) values (tests.uid(1), repeat('x', 31))$q$,
        '23514', 'group names are limited to 30 characters');

    insert into public.contact_groups (owner_id, name) values (tests.uid(1), 'Mine') returning id into v_group;
    perform tests.assert_error($q$insert into public.contact_groups (owner_id, name) values (tests.uid(1), 'MINE')$q$,
        '23505', 'group names are unique per owner, case-insensitively');
    select id into v_contact from public.contacts where owner_id = tests.uid(2) limit 1;
    perform tests.assert_error(format($q$insert into public.contact_group_members (group_id, contact_id, owner_id)
        values (%L, %L, %L)$q$, v_group, v_contact, tests.uid(1)), '23503',
        'a group cannot contain another owner''s contact (composite foreign key)');
end
$$;

-- accept_contact_request: atomic, recipient-only, idempotent -------------------------------
do $$
declare
    v_request uuid;
begin
    select id into v_request from public.contact_requests where from_user_id = tests.uid(1) and to_user_id = tests.uid(2);

    perform tests.assert_error(format($q$select private.accept_contact_request(%L, %L)$q$, v_request, tests.uid(1)),
        '42501', 'the sender cannot accept their own request');
    perform private.accept_contact_request(v_request, tests.uid(2));
    perform private.accept_contact_request(v_request, tests.uid(2));

    perform tests.assert_eq((select count(*) from public.contacts
        where contact_type = 'chikka' and owner_id in (tests.uid(1), tests.uid(2))), 2::bigint,
        'accepting creates exactly two contact rows, once');
    perform tests.assert_eq((select status from public.contact_requests where id = v_request), 'accepted', 'request marked accepted');
end
$$;

-- Platform configuration -------------------------------------------------------------------
do $$
begin
    perform tests.assert_error(format($q$insert into public.provider_configurations
        (provider, display_name, mode, is_active, live_confirmed_at, live_confirmed_by, live_confirmed_environment)
        values ('othersms', 'Other live', 'live', true, now(), %L, 'test')$q$, tests.uid(1)),
        '23505', 'only one provider configuration may be active');
    perform tests.assert_error($q$update public.provider_configurations set is_active = false where provider = 'mock';
        update public.provider_configurations set is_active = true where provider = 'twilio'$q$,
        '23514', 'live cannot be active without operator confirmation');
    perform tests.assert_error($q$insert into public.provider_configurations (provider, display_name, mode) values ('mock', 'x', 'live')$q$,
        '23514', 'the mock provider is always simulation');

    perform tests.assert_error($q$insert into public.sms_country_capabilities (country_code, country_name, version, outbound_support)
        values ('ZZ', 'Nowhere', 1, 'supported')$q$, '23514', 'supported needs recorded verification');
    perform tests.assert_error($q$insert into public.sms_country_capabilities (country_code, country_name, version, registered_sender_status)
        values ('PH', 'Philippines', 2, 'not_required')$q$, '23514', 'the Philippines needs an explicit registration status');
    perform tests.assert_error($q$insert into public.sms_country_capabilities (country_code, country_name, version)
        values ('PH', 'Philippines', 2)$q$, '23514', 'default registration status is rejected for PH');
    perform tests.assert_error($q$insert into public.sms_country_capabilities (country_code, country_name, version, registered_sender_status)
        values ('US', 'United States', 2, 'not_required')$q$, '23505', 'only one current version per country');
    perform tests.assert_error($q$insert into public.sms_country_capabilities (country_code, country_name, version, is_current, credit_multiplier)
        values ('US', 'United States', 3, false, 0)$q$, '23514', 'credit multiplier must be positive');
    perform tests.assert_eq((select outbound_support from public.sms_country_capabilities where country_code = 'PH' and is_current),
        'requires_verification', 'Philippines is seeded unverified');
    perform tests.assert_eq((select count(*) from public.sms_country_capabilities where outbound_support = 'supported'), 0::bigint,
        'no country is seeded as supported');
    perform tests.assert_eq((select mode from public.provider_configurations where is_active), 'simulation',
        'simulation is the only active provider after migration');
end
$$;

-- user_consents: append-only, attestation needs a recipient ---------------------------------
do $$
begin
    insert into public.user_consents (user_id, consent_type, notice_version, decision, source)
    values (tests.uid(1), 'terms', 'v1', 'granted', 'registration');
    perform tests.assert_error($q$update public.user_consents set decision = 'withdrawn'$q$, '55000', 'consents cannot be edited');
    perform tests.assert_error($q$delete from public.user_consents$q$, '55000', 'consents cannot be deleted');
    perform tests.assert_error($q$insert into public.user_consents (user_id, consent_type, notice_version, decision, source)
        values (tests.uid(1), 'sms_sender_attestation', 'v1', 'granted', 'compose')$q$, '23514', 'attestation needs a recipient number');
    perform tests.assert_error($q$insert into public.user_consents (user_id, consent_type, notice_version, decision, source, recipient_phone)
        values (tests.uid(1), 'terms', 'v1', 'granted', 'registration', '+15550100005')$q$, '23514', 'only attestations carry a number');

    perform tests.assert_true(private.has_active_consent(tests.uid(1), 'terms'), 'granted consent is active');
    insert into public.user_consents (user_id, consent_type, notice_version, decision, source, created_at)
    values (tests.uid(1), 'terms', 'v1', 'withdrawn', 'settings', now() + interval '1 second');
    perform tests.assert_true(not private.has_active_consent(tests.uid(1), 'terms'), 'withdrawal ends the consent');
    perform tests.assert_true(not private.has_active_consent(tests.uid(1), 'ai_use'), 'no record means no consent');

    insert into public.user_consents (user_id, consent_type, notice_version, decision, source, recipient_phone)
    values (tests.uid(1), 'sms_sender_attestation', 'v1', 'granted', 'compose', '+15550100005');
    perform tests.assert_true(private.has_active_consent(tests.uid(1), 'sms_sender_attestation', '+15550100005'),
        'attestation is per recipient');
    perform tests.assert_true(not private.has_active_consent(tests.uid(1), 'sms_sender_attestation', '+15550100006'),
        'attestation for one number does not cover another');
end
$$;

-- Opt-outs and routes ----------------------------------------------------------------------
do $$
begin
    insert into public.sms_opt_outs (remote_phone, source, keyword) values ('+15550100007', 'keyword', 'STOP');
    perform tests.assert_error($q$insert into public.sms_opt_outs (remote_phone, source) values ('+15550100007', 'admin')$q$,
        '23505', 'one platform-wide opt-out row per number');
    perform tests.assert_ok($q$insert into public.sms_opt_outs (remote_phone, platform_number, source)
        values ('+15550100007', '+15550100900', 'keyword')$q$, 'an opt-out scoped to one sender number is a separate row');
    perform tests.assert_error($q$update public.sms_opt_outs set is_opted_out = false where remote_phone = '+15550100007'$q$,
        '23514', 'lifting an opt-out records opted_in_at');
    perform tests.assert_error($q$update public.sms_opt_outs set is_opted_out = false, opted_in_at = now(),
        lift_source = 'admin' where remote_phone = '+15550100007' and platform_number is null$q$,
        '23514', 'an admin lift needs a reason and an admin');
end
$$;

-- Audit log guard rails ----------------------------------------------------------------------
do $$
declare
    v_id uuid;
begin
    insert into public.audit_logs (category, action, metadata)
    values ('sms', 'sms.send.accepted', jsonb_build_object('recipient', private.mask_phone('+15550109876'))) returning id into v_id;

    perform tests.assert_eq(private.mask_phone('+15550109876'), '+15****9876', 'phone masking keeps country prefix and last 4');
    perform tests.assert_error($q$insert into public.audit_logs (category, action, metadata)
        values ('sms', 'sms.send.accepted', '{"body": "hello"}')$q$, '23514', 'audit metadata may not carry message bodies');
    perform tests.assert_error($q$insert into public.audit_logs (category, action, metadata)
        values ('sms', 'sms.send.accepted', '{"recipient": "+15550109876"}')$q$, '23514', 'audit metadata may not carry raw phone numbers');
    perform tests.assert_error($q$insert into public.audit_logs (category, action, target_id)
        values ('sms', 'sms.send.accepted', '+15550109876')$q$, '23514', 'audit target ids may not carry raw phone numbers');
    perform tests.assert_error($q$insert into public.audit_logs (category, action) values ('bogus', 'x.y')$q$, '23514', 'unknown category');
    perform tests.assert_error(format($q$update public.audit_logs set action = 'tampered.x' where id = %L$q$, v_id), '55000',
        'audit rows cannot be updated');
    perform tests.assert_error(format($q$delete from public.audit_logs where id = %L$q$, v_id), '55000',
        'audit rows cannot be deleted before retain_until');
end
$$;

-- AI logs and reports --------------------------------------------------------------------------
do $$
begin
    perform tests.assert_error($q$insert into public.ai_assistance_logs (user_id, feature, model_id, outcome, input_text)
        values (tests.uid(1), 'translate', 'mock', 'success', 'hello')$q$, '23514', 'stored AI content needs an expiry');
    perform tests.assert_ok($q$insert into public.ai_assistance_logs (user_id, feature, model_id, outcome, input_text, content_expires_at)
        values (tests.uid(1), 'translate', 'mock', 'success', 'hello', now() + interval '30 days')$q$, 'AI content with expiry is accepted');
    perform tests.assert_error($q$insert into public.ai_assistance_logs (user_id, feature, model_id, outcome)
        values (tests.uid(1), 'unknown_feature', 'mock', 'success')$q$, '23514', 'unknown AI feature');

    perform tests.assert_error($q$insert into public.abuse_reports (reporter_id, reported_user_id, reason, snapshot)
        values (tests.uid(1), tests.uid(1), 'spam', '{}')$q$, '23514', 'cannot report yourself');
    perform tests.assert_error($q$insert into public.abuse_reports (reporter_id, reason, snapshot)
        values (tests.uid(1), 'spam', '{}')$q$, '23514', 'a report needs a target');
    perform tests.assert_error($q$insert into public.abuse_reports (reporter_id, reported_user_id, reason, snapshot, status)
        values (tests.uid(1), tests.uid(2), 'spam', '{}', 'dismissed')$q$, '23514', 'closing a report needs a resolution note and resolver');
end
$$;

-- Notification preferences --------------------------------------------------------------------
do $$
begin
    perform tests.assert_ok($q$update public.notification_preferences set overrides = '{"new_message.email": false}' where user_id = tests.uid(1)$q$,
        'valid override');
    perform tests.assert_error($q$update public.notification_preferences set overrides = '{"sms_failed.in_app": false}' where user_id = tests.uid(1)$q$,
        '23514', 'failed-SMS alerts cannot be turned off');
    perform tests.assert_error($q$update public.notification_preferences set overrides = '{"nonsense.push": true}' where user_id = tests.uid(1)$q$,
        '23514', 'unknown notification type');
    perform tests.assert_error($q$update public.notification_preferences set overrides = '{"new_message.push": "yes"}' where user_id = tests.uid(1)$q$,
        '23514', 'override values must be booleans');
    perform tests.assert_error($q$update public.notification_preferences set low_balance_threshold_units = 50 where user_id = tests.uid(1)$q$,
        '23514', 'low-balance threshold is 1 to 100 credits');
    perform tests.assert_error($q$update public.notification_preferences set quiet_hours_start = '22:00' where user_id = tests.uid(1)$q$,
        '23514', 'quiet hours need both start and end');
end
$$;

rollback;
