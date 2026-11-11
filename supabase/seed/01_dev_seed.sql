-- Development seed data. NEVER run against staging or production.
-- All people, emails and phone numbers are fictional: emails use the reserved .test domain and
-- phone numbers use the +1 555 01xx range reserved for fiction. No real numbers appear here.
--
-- Fixed UUIDs make the seed repeatable and let tests refer to known users.
--   a1 admin   a2 alice   a3 bob   a4 carol (pending verification)   a5 dave (suspended)

do $$
begin
    if coalesce(current_setting('app.environment', true), 'development') in ('production', 'staging') then
        raise exception 'Refusing to run development seed in environment %', current_setting('app.environment', true);
    end if;
end
$$;

-- Auth users. The profile row is created by the on_auth_user_created trigger.
-- A development-only password is set when pgcrypto is available (Supabase local has it in "extensions").
do $$
declare
    v_hash text := null;
begin
    if to_regprocedure('extensions.crypt(text,text)') is not null then
        execute $q$select extensions.crypt('dev-password-only', extensions.gen_salt('bf'))$q$ into v_hash;
    end if;

    insert into auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, raw_user_meta_data)
    values
        ('00000000-0000-4000-8000-0000000000a1', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
         'admin@chikka.test', v_hash, now(), '{"display_name": "Dev Admin"}'),
        ('00000000-0000-4000-8000-0000000000a2', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
         'alice@chikka.test', v_hash, now(), '{"display_name": "Alice Sample"}'),
        ('00000000-0000-4000-8000-0000000000a3', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
         'bob@chikka.test', v_hash, now(), '{"display_name": "Bob Sample"}'),
        ('00000000-0000-4000-8000-0000000000a4', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
         'carol@chikka.test', v_hash, null, '{"display_name": "Carol Pending"}'),
        ('00000000-0000-4000-8000-0000000000a5', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
         'dave@chikka.test', v_hash, now(), '{"display_name": "Dave Suspended"}')
    on conflict (id) do nothing;
end
$$;

-- Profiles ---------------------------------------------------------------------------------
update public.profiles set username = 'dev_admin', role = 'admin', status = 'active', country_code = 'PH',
       profile_visibility = 'everyone', onboarding_completed_at = now()
 where id = '00000000-0000-4000-8000-0000000000a1';
update public.profiles set username = 'alice', status = 'active', country_code = 'PH', language = 'en',
       time_zone = 'Asia/Manila', profile_visibility = 'contacts', ai_enabled = true, onboarding_completed_at = now()
 where id = '00000000-0000-4000-8000-0000000000a2';
update public.profiles set username = 'bob', status = 'active', country_code = 'SG', language = 'en',
       profile_visibility = 'everyone', onboarding_completed_at = now()
 where id = '00000000-0000-4000-8000-0000000000a3';
update public.profiles set username = 'carol', country_code = 'AU'
 where id = '00000000-0000-4000-8000-0000000000a4';
update public.profiles set username = 'dave', status = 'suspended', suspended_at = now(), country_code = 'US',
       onboarding_completed_at = now()
 where id = '00000000-0000-4000-8000-0000000000a5';

-- Consents ---------------------------------------------------------------------------------
insert into public.user_consents (user_id, consent_type, notice_version, decision, source, recipient_phone)
values
    ('00000000-0000-4000-8000-0000000000a2', 'terms',   '2026-11', 'granted', 'registration', null),
    ('00000000-0000-4000-8000-0000000000a2', 'privacy', '2026-11', 'granted', 'registration', null),
    ('00000000-0000-4000-8000-0000000000a2', 'ai_use',  '2026-11', 'granted', 'settings', null),
    ('00000000-0000-4000-8000-0000000000a2', 'sms_sender_attestation', '2026-11', 'granted', 'compose', '+15550100101'),
    ('00000000-0000-4000-8000-0000000000a2', 'sms_sender_attestation', '2026-11', 'granted', 'compose', '+15550100102'),
    ('00000000-0000-4000-8000-0000000000a3', 'terms',   '2026-11', 'granted', 'registration', null),
    ('00000000-0000-4000-8000-0000000000a3', 'privacy', '2026-11', 'granted', 'registration', null);

-- Phone numbers (verified in simulation only) ----------------------------------------------
insert into public.phone_numbers (user_id, e164, country_code, verification_mode, status, verified_at)
values ('00000000-0000-4000-8000-0000000000a2', '+15550100001', 'US', 'simulated', 'verified', now());

-- Contacts: alice and bob become mutual contacts through the real accept flow -------------
insert into public.contact_requests (id, from_user_id, to_user_id, note)
values ('00000000-0000-4000-8000-0000000000c1', '00000000-0000-4000-8000-0000000000a3',
        '00000000-0000-4000-8000-0000000000a2', 'Hi Alice, it is Bob.');
select private.accept_contact_request('00000000-0000-4000-8000-0000000000c1', '00000000-0000-4000-8000-0000000000a2');

insert into public.contact_requests (from_user_id, to_user_id, note)
values ('00000000-0000-4000-8000-0000000000a4', '00000000-0000-4000-8000-0000000000a2', 'Pending sample request');

insert into public.contacts (id, owner_id, contact_type, phone_e164, display_name, is_favourite)
values
    ('00000000-0000-4000-8000-0000000000d1', '00000000-0000-4000-8000-0000000000a2', 'sms', '+15550100101', 'Sample Relative', true),
    ('00000000-0000-4000-8000-0000000000d2', '00000000-0000-4000-8000-0000000000a2', 'sms', '+15550100102', 'Opted-Out Sample', false);

insert into public.contact_groups (id, owner_id, name, color)
values ('00000000-0000-4000-8000-0000000000e1', '00000000-0000-4000-8000-0000000000a2', 'Family', '#3366CC');
insert into public.contact_group_members (group_id, contact_id, owner_id)
values ('00000000-0000-4000-8000-0000000000e1', '00000000-0000-4000-8000-0000000000d1', '00000000-0000-4000-8000-0000000000a2');

-- Opt-out: recipient replied STOP to the platform sender -----------------------------------
insert into public.sms_opt_outs (remote_phone, platform_number, source, keyword)
values ('+15550100102', null, 'keyword', 'STOP');

-- Chikka-to-Chikka conversation with delivered and read messages ---------------------------
do $$
declare
    v_alice constant uuid := '00000000-0000-4000-8000-0000000000a2';
    v_bob   constant uuid := '00000000-0000-4000-8000-0000000000a3';
    v_conv  uuid;
    v_msg   uuid;
begin
    v_conv := private.get_or_create_chikka_conversation(v_alice, v_bob);

    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', v_bob, 'Hey Alice, are you online?', 'read', '10000000-0000-4000-8000-000000000001')
    returning id into v_msg;
    insert into public.message_deliveries (message_id, channel, recipient_user_id, status, sent_at, delivered_at, read_at)
    values (v_msg, 'chikka', v_alice, 'sent', now(), null, null);
    update public.message_deliveries set status = 'delivered', delivered_at = now() where message_id = v_msg;
    update public.message_deliveries set status = 'read', read_at = now() where message_id = v_msg;

    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', v_alice, 'Yes! This is the revived buddy list.', 'sent', '10000000-0000-4000-8000-000000000002')
    returning id into v_msg;
    insert into public.message_deliveries (message_id, channel, recipient_user_id, status, sent_at)
    values (v_msg, 'chikka', v_bob, 'sent', now());
    update public.message_deliveries set status = 'delivered', delivered_at = now() where message_id = v_msg;

    -- Notification for the pending contact request.
    insert into public.notifications (user_id, notification_type, title, body, reference_type, reference_id)
    values (v_alice, 'contact_request', 'New contact request', null, 'contact_request', '00000000-0000-4000-8000-0000000000c1');
end
$$;

-- SMS conversation (simulation): delivered, retried-then-failed, and an inbound reply ------
do $$
declare
    v_alice constant uuid := '00000000-0000-4000-8000-0000000000a2';
    v_mock  uuid;
    v_cap   uuid;
    v_conv  uuid;
    v_m1    uuid;
    v_m2    uuid;
    v_m3    uuid;
    v_d1    uuid;
    v_d2a   uuid;
    v_d2b   uuid;
    v_d3    uuid;
    v_wh    uuid;
begin
    select id into v_mock from public.provider_configurations where provider = 'mock' and mode = 'simulation';
    select id into v_cap from public.sms_country_capabilities where country_code = 'US' and is_current;
    v_conv := private.get_or_create_sms_conversation(v_alice, '+15550100101');

    insert into public.sms_routes (user_id, conversation_id, platform_number, remote_number)
    values (v_alice, v_conv, '+15550100900', '+15550100101');

    -- M1: queued -> accepted -> sent -> delivered, one segment, charged to the demo ledger.
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count,
                                 segment_count, status, idempotency_key, is_simulated, capability_id, credit_cost_units)
    values (v_conv, 'sms', 'outbound', v_alice, 'Hello from the browser! (simulated)', 'gsm7', 35, 1, 'queued',
            '10000000-0000-4000-8000-000000000011', true, v_cap, 100)
    returning id into v_m1;
    insert into public.message_segments (message_id, segment_index, segment_count, encoding, char_count, units)
    values (v_m1, 1, 1, 'gsm7', 35, 35);
    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id, provider, country_code, segment_count, capability_id)
    values (v_alice, 'demo', 'reservation', 0, 100, v_m1, 'mock', 'US', 1, v_cap);
    insert into public.message_deliveries (message_id, channel, provider_configuration_id, recipient_phone, is_simulated, status, next_attempt_at)
    values (v_m1, 'sms', v_mock, '+15550100101', true, 'queued', now()) returning id into v_d1;
    update public.message_deliveries set status = 'accepted', provider_status = 'accepted',
           provider_message_id = 'SIM-0001', accepted_at = now() where id = v_d1;
    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id, provider, country_code, segment_count, capability_id)
    values (v_alice, 'demo', 'deduction', -100, -100, v_m1, 'mock', 'US', 1, v_cap);
    update public.message_deliveries set status = 'sent', provider_status = 'sent', sent_at = now() where id = v_d1;
    update public.message_deliveries set status = 'delivered', provider_status = 'delivered', delivered_at = now() where id = v_d1;
    insert into public.message_delivery_events (delivery_id, dedupe_key, source, provider_status, normalised_status, applied, ignore_reason)
    values (v_d1, 'SIM-0001:accepted:1', 'send_response', 'accepted', 'accepted', true, null),
           (v_d1, 'SIM-0001:sent:2', 'simulation', 'sent', 'sent', true, null),
           (v_d1, 'SIM-0001:delivered:3', 'simulation', 'delivered', 'delivered', true, null),
           (v_d1, 'SIM-0001:delivered:3-duplicate', 'simulation', 'delivered', 'delivered', false, 'duplicate_callback');

    -- M2: attempt 1 fails transiently (retry scheduled), attempt 2 fails permanently. Hold is released.
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count,
                                 segment_count, status, idempotency_key, is_simulated, capability_id, credit_cost_units)
    values (v_conv, 'sms', 'outbound', v_alice, 'This one will fail in simulation.', 'gsm7', 33, 1, 'queued',
            '10000000-0000-4000-8000-000000000012', true, v_cap, 100)
    returning id into v_m2;
    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id, provider, country_code, segment_count, capability_id)
    values (v_alice, 'demo', 'reservation', 0, 100, v_m2, 'mock', 'US', 1, v_cap);
    insert into public.message_deliveries (message_id, attempt_number, channel, provider_configuration_id, recipient_phone, is_simulated, status, next_attempt_at)
    values (v_m2, 1, 'sms', v_mock, '+15550100101', true, 'queued', now()) returning id into v_d2a;
    update public.message_deliveries set status = 'failed', failure_class = 'transient', is_permanent = false,
           failure_code = 'SIM_TIMEOUT', failure_reason = 'Simulated provider timeout', http_status = 503
     where id = v_d2a;
    insert into public.message_deliveries (message_id, attempt_number, retry_of_delivery_id, channel, provider_configuration_id,
                                           recipient_phone, is_simulated, status, next_attempt_at)
    values (v_m2, 2, v_d2a, 'sms', v_mock, '+15550100101', true, 'queued', now() + interval '10 seconds') returning id into v_d2b;
    update public.message_deliveries set status = 'failed', failure_class = 'permanent', is_permanent = true,
           failure_code = 'SIM_INVALID_NUMBER', failure_reason = 'Simulated permanent failure'
     where id = v_d2b;
    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id, provider, country_code, segment_count, capability_id)
    values (v_alice, 'demo', 'reservation_release', 0, -100, v_m2, 'mock', 'US', 1, v_cap);

    -- M3: inbound reply routed from the sample number.
    insert into public.provider_webhooks (provider, provider_configuration_id, kind, dedupe_key, provider_message_id,
                                          raw_payload, signature_verified_at, is_simulated, processing_status,
                                          processed_at, routing_result)
    values ('mock', v_mock, 'inbound', 'SIM-IN-0001', 'SIM-IN-0001',
            '{"From": "+15550100101", "To": "+15550100900", "Body": "Got it, thanks! (simulated reply)"}',
            now(), true, 'processed', now(), 'routed')
    returning id into v_wh;
    insert into public.messages (conversation_id, channel, direction, sender_phone, body, status, is_simulated)
    values (v_conv, 'sms', 'inbound', '+15550100101', 'Got it, thanks! (simulated reply)', 'received', true)
    returning id into v_m3;
    insert into public.message_deliveries (message_id, channel, provider_configuration_id, recipient_user_id, recipient_phone,
                                           is_simulated, status, provider_status, provider_message_id, delivered_at)
    values (v_m3, 'sms', v_mock, v_alice, '+15550100900', true, 'delivered', 'received', 'SIM-IN-0001', now())
    returning id into v_d3;
    update public.provider_webhooks set delivery_id = v_d3, message_id = v_m3 where id = v_wh;

    -- Notifications and an AI history entry (metadata only; user history content is off by default).
    insert into public.notifications (user_id, notification_type, title, reference_type, reference_id)
    values (v_alice, 'sms_inbound', 'New SMS reply', 'message', v_m3),
           (v_alice, 'sms_failed', 'An SMS could not be delivered', 'message', v_m2);

    insert into public.ai_assistance_logs (user_id, conversation_id, feature, model_id, prompt_version, outcome,
                                           user_decision, input_tokens, output_tokens, latency_ms)
    values (v_alice, v_conv, 'suggest_replies', 'mock-model', 'reply.v1', 'success', 'dismissed', 210, 64, 480);

    -- Moderation sample: Bob reports a message. The snapshot keeps evidence if the message changes later.
    insert into public.abuse_reports (reporter_id, reported_user_id, message_id, conversation_id, reason, note, snapshot)
    select '00000000-0000-4000-8000-0000000000a3', v_alice, m.id, m.conversation_id, 'spam', 'Sample report for development',
           jsonb_build_object('reported', jsonb_build_object('message_id', m.id, 'body', m.body), 'context', '[]'::jsonb)
      from public.messages m
     where m.sender_user_id = v_alice and m.channel = 'chikka'
     limit 1;

    -- Audit samples: phone numbers masked, no message bodies.
    insert into public.audit_logs (category, action, actor_id, actor_role, target_type, target_id, metadata)
    values ('sms', 'sms.send.accepted', v_alice, 'user', 'message', v_m1::text,
            jsonb_build_object('recipient', private.mask_phone('+15550100101'), 'provider', 'mock', 'mode', 'simulation', 'segments', 1)),
           ('admin', 'sms.mode.confirmed_simulation', '00000000-0000-4000-8000-0000000000a1', 'admin', 'provider_configuration', v_mock::text,
            jsonb_build_object('environment', 'development'));
end
$$;
