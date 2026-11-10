-- Test file 02: conversations, messages, sequencing, delivery attempts and status rules.
begin;

select tests.create_user(tests.uid(1), 'alice');
select tests.create_user(tests.uid(2), 'bob');
select tests.create_user(tests.uid(3), 'carol');
select tests.create_user(tests.uid(4), 'dave', 'suspended');

-- Conversations: idempotent pair creation --------------------------------------------------
do $$
declare
    v_ab uuid;
    v_ba uuid;
begin
    v_ab := private.get_or_create_chikka_conversation(tests.uid(1), tests.uid(2));
    v_ba := private.get_or_create_chikka_conversation(tests.uid(2), tests.uid(1));
    perform tests.assert_eq(v_ab, v_ba, 'the same pair always resolves to one conversation, whatever the order');
    perform tests.assert_eq((select count(*) from public.conversation_members where conversation_id = v_ab), 2::bigint,
        'both users are members');
    perform tests.assert_error($q$select private.get_or_create_chikka_conversation(tests.uid(1), tests.uid(1))$q$,
        '22023', 'a conversation needs two different users');
    perform tests.assert_error($q$select private.get_or_create_chikka_conversation(tests.uid(1), tests.uid(4))$q$,
        '55000', 'suspended users cannot start conversations');

    perform tests.assert_eq(private.get_or_create_sms_conversation(tests.uid(1), '+15550100101'),
        private.get_or_create_sms_conversation(tests.uid(1), '+15550100101'),
        'one sms conversation per user and number');
    perform tests.assert_true(
        private.get_or_create_sms_conversation(tests.uid(1), '+15550100101')
        <> private.get_or_create_sms_conversation(tests.uid(2), '+15550100101'),
        'different users get separate sms conversations for the same number');
end
$$;

-- Message sequencing and validation ------------------------------------------------------------
do $$
declare
    v_conv uuid := private.get_or_create_chikka_conversation(tests.uid(1), tests.uid(2));
    v_sms  uuid := private.get_or_create_sms_conversation(tests.uid(1), '+15550100101');
    v_m1 uuid;
    v_m2 uuid;
    v_m3 uuid;
begin
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', tests.uid(1), 'one', 'sent', gen_random_uuid()) returning id into v_m1;
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', tests.uid(2), 'two', 'sent', gen_random_uuid()) returning id into v_m2;
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', tests.uid(1), 'three', 'sent', gen_random_uuid()) returning id into v_m3;

    perform tests.assert_eq((select seq from public.messages where id = v_m1), 1::bigint, 'first message is seq 1');
    perform tests.assert_eq((select seq from public.messages where id = v_m2), 2::bigint, 'second message is seq 2');
    perform tests.assert_eq((select seq from public.messages where id = v_m3), 3::bigint, 'third message is seq 3');
    perform tests.assert_eq((select last_seq from public.conversations where id = v_conv), 3::bigint, 'conversation counter follows');
    perform tests.assert_true((select last_message_at from public.conversations where id = v_conv) is not null,
        'last_message_at is maintained');

    -- A caller-supplied seq is ignored.
    insert into public.messages (conversation_id, seq, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 999, 'chikka', 'outbound', tests.uid(1), 'four', 'sent', gen_random_uuid());
    perform tests.assert_eq((select max(seq) from public.messages where conversation_id = v_conv), 4::bigint,
        'the database assigns seq, never the caller');

    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'chikka', 'outbound', %L, 'intruder', 'sent', gen_random_uuid())$q$, v_conv, tests.uid(3)),
        '42501', 'a non-member cannot post');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'sms', 'outbound', %L, 'wrong kind', 'queued', gen_random_uuid())$q$, v_conv, tests.uid(1)),
        '23514', 'channel must match the conversation type');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status)
        values (%L, 'chikka', 'outbound', %L, 'no key', 'sent')$q$, v_conv, tests.uid(1)),
        '23514', 'outbound messages need an idempotency key');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'chikka', 'outbound', %L, repeat('x', 2001), 'sent', gen_random_uuid())$q$, v_conv, tests.uid(1)),
        '23514', 'chikka messages are limited to 2000 characters');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'chikka', 'outbound', %L, '', 'sent', gen_random_uuid())$q$, v_conv, tests.uid(1)),
        '23514', 'empty bodies are rejected');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key, segment_count)
        values (%L, 'chikka', 'outbound', %L, 'x', 'sent', gen_random_uuid(), 1)$q$, v_conv, tests.uid(1)),
        '23514', 'chikka messages carry no SMS fields');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'chikka', 'outbound', %L, 'x', 'queued', gen_random_uuid())$q$, v_conv, tests.uid(1)),
        '23514', 'chikka messages cannot use SMS statuses');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key, is_simulated)
        values (%L, 'chikka', 'outbound', %L, 'x', 'sent', gen_random_uuid(), true)$q$, v_conv, tests.uid(1)),
        '23514', 'only SMS can be simulated');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'sms', 'outbound', %L, 'no segment info', 'queued', gen_random_uuid())$q$, v_sms, tests.uid(1)),
        '23514', 'outbound SMS needs encoding, character and segment counts');
end
$$;

-- Idempotency, identity protection, deletion ---------------------------------------------------
do $$
declare
    v_conv uuid := private.get_or_create_chikka_conversation(tests.uid(1), tests.uid(2));
    v_key uuid := gen_random_uuid();
    v_msg uuid;
begin
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', tests.uid(1), 'once', 'sent', v_key) returning id into v_msg;

    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'chikka', 'outbound', %L, 'twice', 'sent', %L)$q$, v_conv, tests.uid(1), v_key),
        '23505', 'a duplicate idempotency key from the same sender is rejected');
    perform tests.assert_ok(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'chikka', 'outbound', %L, 'other sender same key', 'sent', %L)$q$, v_conv, tests.uid(2), v_key),
        'idempotency keys are scoped per sender');

    perform tests.assert_error(format($q$update public.messages set seq = 99 where id = %L$q$, v_msg), '55000', 'seq is immutable');
    perform tests.assert_error(format($q$update public.messages set sender_user_id = %L where id = %L$q$, tests.uid(2), v_msg), '55000',
        'sender is immutable');
    perform tests.assert_error(format($q$update public.messages set deleted_for_everyone_at = now() where id = %L$q$, v_msg), '23514',
        'deleting for everyone must clear the body');
    perform tests.assert_ok(format($q$update public.messages set deleted_for_everyone_at = now(), body = null where id = %L$q$, v_msg),
        'delete for everyone clears the body and sets the marker');
end
$$;

-- SMS: delivery attempts, retries, forward-only status ------------------------------------------
do $$
declare
    v_sms uuid := private.get_or_create_sms_conversation(tests.uid(1), '+15550100101');
    v_mock uuid := (select id from public.provider_configurations where provider = 'mock');
    v_cap uuid := (select id from public.sms_country_capabilities where country_code = 'US' and is_current);
    v_msg uuid;
    v_a1 uuid;
    v_a2 uuid;
begin
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count, segment_count,
                                 status, idempotency_key, is_simulated, capability_id)
    values (v_sms, 'sms', 'outbound', tests.uid(1), 'sms test', 'gsm7', 8, 1, 'queued', gen_random_uuid(), true, v_cap)
    returning id into v_msg;

    perform tests.assert_error(format($q$insert into public.message_deliveries (message_id, channel, provider_configuration_id, recipient_phone, is_simulated, status)
        values (%L, 'sms', %L, '+15550100101', false, 'queued')$q$, v_msg, v_mock),
        '23514', 'a mock delivery must be flagged simulated');
    perform tests.assert_error(format($q$insert into public.message_deliveries (message_id, channel, recipient_phone, is_simulated, status)
        values (%L, 'sms', '+15550100101', true, 'queued')$q$, v_msg),
        '23514', 'an SMS delivery needs a provider configuration');
    perform tests.assert_error(format($q$insert into public.message_deliveries (message_id, channel, provider_configuration_id, is_simulated, status)
        values (%L, 'sms', %L, true, 'queued')$q$, v_msg, v_mock),
        '23514', 'a delivery needs a recipient');

    -- Attempt 1 fails transiently, so the message shows as retrying.
    insert into public.message_deliveries (message_id, attempt_number, channel, provider_configuration_id, recipient_phone, is_simulated, status)
    values (v_msg, 1, 'sms', v_mock, '+15550100101', true, 'queued') returning id into v_a1;
    perform tests.assert_eq((select status from public.messages where id = v_msg), 'queued', 'first attempt queued');

    perform tests.assert_error(format($q$update public.message_deliveries set status = 'failed' where id = %L$q$, v_a1),
        '23514', 'a failed attempt must say why');
    update public.message_deliveries set status = 'failed', failure_class = 'transient', failure_code = 'SIM_TIMEOUT' where id = v_a1;
    perform tests.assert_eq((select status from public.messages where id = v_msg), 'retrying',
        'a transient failure shows the message as retrying, not failed');

    -- Attempt 2 is a new row.
    perform tests.assert_error(format($q$insert into public.message_deliveries (message_id, attempt_number, channel, provider_configuration_id, recipient_phone, is_simulated)
        values (%L, 1, 'sms', %L, '+15550100101', true)$q$, v_msg, v_mock), '23505', 'attempt numbers are unique per message');
    insert into public.message_deliveries (message_id, attempt_number, retry_of_delivery_id, channel, provider_configuration_id, recipient_phone, is_simulated, status)
    values (v_msg, 2, v_a1, 'sms', v_mock, '+15550100101', true, 'queued') returning id into v_a2;
    perform tests.assert_eq((select status from public.messages where id = v_msg), 'retrying', 'a queued retry attempt keeps retrying');

    update public.message_deliveries set status = 'accepted', provider_status = 'queued', provider_message_id = 'SIM-T-1' where id = v_a2;
    perform tests.assert_eq((select status from public.messages where id = v_msg), 'accepted',
        'accepted is shown as accepted, never as delivered');
    perform tests.assert_true((select delivered_at from public.message_deliveries where id = v_a2) is null,
        'acceptance does not set delivered_at');

    perform tests.assert_error(format($q$update public.message_deliveries set provider_message_id = 'SIM-T-1' where id = %L$q$, v_a1),
        '23505', 'provider message IDs are unique per provider configuration');

    update public.message_deliveries set status = 'sent' where id = v_a2;
    perform tests.assert_error(format($q$update public.message_deliveries set status = 'accepted' where id = %L$q$, v_a2),
        '55000', 'status cannot move backwards');
    update public.message_deliveries set status = 'delivered', delivered_at = now() where id = v_a2;
    perform tests.assert_eq((select status from public.messages where id = v_msg), 'delivered', 'message shows delivered after the receipt');
    perform tests.assert_true((select terminal_at from public.message_deliveries where id = v_a2) is not null, 'terminal_at is set');
    perform tests.assert_error(format($q$update public.message_deliveries set status = 'undelivered' where id = %L$q$, v_a2),
        '55000', 'the first terminal state wins');
    perform tests.assert_true((select status_version from public.message_deliveries where id = v_a2) > 1,
        'status_version increases with each change');
end
$$;

-- Skipped states and the ambiguous-outcome correction -------------------------------------------
do $$
declare
    v_sms uuid := private.get_or_create_sms_conversation(tests.uid(1), '+15550100202');
    v_mock uuid := (select id from public.provider_configurations where provider = 'mock');
    v_cap uuid := (select id from public.sms_country_capabilities where country_code = 'US' and is_current);
    v_msg uuid;
    v_d uuid;
begin
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count, segment_count,
                                 status, idempotency_key, is_simulated, capability_id)
    values (v_sms, 'sms', 'outbound', tests.uid(1), 'ambiguous', 'gsm7', 9, 1, 'queued', gen_random_uuid(), true, v_cap)
    returning id into v_msg;
    insert into public.message_deliveries (message_id, channel, provider_configuration_id, recipient_phone, is_simulated, status)
    values (v_msg, 'sms', v_mock, '+15550100202', true, 'queued') returning id into v_d;

    -- Receipt arrives before the "sent" event: allowed, status skips forward.
    update public.message_deliveries set status = 'delivered' where id = v_d;
    perform tests.assert_eq((select status from public.message_deliveries where id = v_d), 'delivered', 'status may skip forward');

    -- Ambiguous failure can be corrected forward by a correlated provider event.
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count, segment_count,
                                 status, idempotency_key, is_simulated, capability_id)
    values (v_sms, 'sms', 'outbound', tests.uid(1), 'unknown outcome', 'gsm7', 15, 1, 'queued', gen_random_uuid(), true, v_cap)
    returning id into v_msg;
    insert into public.message_deliveries (message_id, channel, provider_configuration_id, recipient_phone, is_simulated, status)
    values (v_msg, 'sms', v_mock, '+15550100202', true, 'queued') returning id into v_d;
    update public.message_deliveries set status = 'failed', failure_class = 'ambiguous', is_permanent = true,
           failure_code = 'outcome_unknown' where id = v_d;
    perform tests.assert_eq((select status from public.messages where id = v_msg), 'failed', 'a permanent failure shows as failed');
    update public.message_deliveries set status = 'accepted', is_permanent = false, provider_message_id = 'SIM-T-9' where id = v_d;
    perform tests.assert_eq((select status from public.message_deliveries where id = v_d), 'accepted',
        'an ambiguous failure can be corrected by a correlated event');

    -- A definite failure cannot be reversed.
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count, segment_count,
                                 status, idempotency_key, is_simulated, capability_id)
    values (v_sms, 'sms', 'outbound', tests.uid(1), 'permanent', 'gsm7', 9, 1, 'queued', gen_random_uuid(), true, v_cap)
    returning id into v_msg;
    insert into public.message_deliveries (message_id, channel, provider_configuration_id, recipient_phone, is_simulated, status)
    values (v_msg, 'sms', v_mock, '+15550100202', true, 'queued') returning id into v_d;
    update public.message_deliveries set status = 'failed', failure_class = 'permanent', is_permanent = true where id = v_d;
    perform tests.assert_error(format($q$update public.message_deliveries set status = 'accepted' where id = %L$q$, v_d),
        '55000', 'a permanent failure cannot be reopened');
end
$$;

-- Inbound SMS and chikka delivery -------------------------------------------------------------------
do $$
declare
    v_sms uuid := private.get_or_create_sms_conversation(tests.uid(1), '+15550100303');
    v_conv uuid := private.get_or_create_chikka_conversation(tests.uid(1), tests.uid(2));
    v_in uuid;
    v_out uuid;
    v_d uuid;
begin
    insert into public.messages (conversation_id, channel, direction, sender_phone, body, status)
    values (v_sms, 'sms', 'inbound', '+15550100303', 'reply', 'received') returning id into v_in;
    perform tests.assert_eq((select seq from public.messages where id = v_in), 1::bigint, 'inbound SMS takes part in the same sequence');
    perform tests.assert_error(format($q$update public.messages set status = 'delivered' where id = %L$q$, v_in), '23514',
        'inbound messages stay received');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'sms', 'inbound', %L, 'x', 'received', gen_random_uuid())$q$, v_sms, tests.uid(1)),
        '23514', 'inbound messages have an external sender, not an account');

    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', tests.uid(1), 'chat', 'sent', gen_random_uuid()) returning id into v_out;
    insert into public.message_deliveries (message_id, channel, recipient_user_id, status)
    values (v_out, 'chikka', tests.uid(2), 'sent') returning id into v_d;
    update public.message_deliveries set status = 'delivered', delivered_at = now() where id = v_d;
    perform tests.assert_eq((select status from public.messages where id = v_out), 'delivered', 'chikka delivered mirrors the client ack');
    update public.message_deliveries set status = 'read', read_at = now() where id = v_d;
    perform tests.assert_eq((select status from public.messages where id = v_out), 'read', 'chikka read follows delivered');
    perform tests.assert_error(format($q$insert into public.message_deliveries (message_id, attempt_number, channel, recipient_user_id, status)
        values (%L, 2, 'chikka', %L, 'queued')$q$, v_out, tests.uid(2)), '23514', 'chikka deliveries never use queued');
end
$$;

-- Delivery events are append-only ---------------------------------------------------------------------
do $$
declare
    v_d uuid := (select id from public.message_deliveries limit 1);
begin
    insert into public.message_delivery_events (delivery_id, dedupe_key, source, normalised_status, applied)
    values (v_d, 'evt-1', 'webhook', 'sent', true);
    perform tests.assert_error(format($q$insert into public.message_delivery_events (delivery_id, dedupe_key, source, normalised_status, applied)
        values (%L, 'evt-1', 'webhook', 'sent', true)$q$, v_d), '23505', 'duplicate provider events are deduplicated');
    perform tests.assert_error(format($q$insert into public.message_delivery_events (delivery_id, dedupe_key, source, normalised_status, applied)
        values (%L, 'evt-2', 'webhook', 'sent', false)$q$, v_d), '23514', 'an ignored event must say why');
    perform tests.assert_error($q$update public.message_delivery_events set applied = false$q$, '55000', 'events cannot be edited');
    perform tests.assert_error($q$delete from public.message_delivery_events$q$, '55000', 'events cannot be deleted');
end
$$;

-- Webhooks: dedupe and size limit -----------------------------------------------------------------------
do $$
begin
    insert into public.provider_webhooks (provider, kind, dedupe_key, raw_payload, signature_verified_at)
    values ('twilio', 'status', 'SM1:delivered', '{"MessageStatus": "delivered"}', now());
    perform tests.assert_error($q$insert into public.provider_webhooks (provider, kind, dedupe_key, raw_payload, signature_verified_at)
        values ('twilio', 'status', 'SM1:delivered', '{}', now())$q$, '23505', 'duplicate webhook deliveries are rejected');
    perform tests.assert_error($q$insert into public.provider_webhooks (provider, kind, dedupe_key, raw_payload, signature_verified_at)
        values ('twilio', 'status', 'big', jsonb_build_object('x', repeat('a', 70000)), now())$q$, '23514', 'payloads are limited to 64 KB');
    perform tests.assert_error($q$insert into public.provider_webhooks (provider, kind, dedupe_key, raw_payload)
        values ('twilio', 'status', 'unsigned', '{}')$q$, '23502', 'only signature-verified events are stored');
end
$$;

-- Administrator triage of a failed message (FR-ADMIN-009) ----------------------------------------------------
do $$
declare
    v_sms uuid := private.get_or_create_sms_conversation(tests.uid(1), '+15550100505');
    v_cap uuid := (select id from public.sms_country_capabilities where country_code = 'US' and is_current);
    v_msg uuid;
begin
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count, segment_count,
                                 status, idempotency_key, is_simulated, capability_id)
    values (v_sms, 'sms', 'outbound', tests.uid(1), 'stuck', 'gsm7', 5, 1, 'queued', gen_random_uuid(), true, v_cap)
    returning id into v_msg;
    perform tests.assert_error(format($q$update public.messages set admin_resolved_at = now(), admin_resolved_by = %L where id = %L$q$, tests.uid(2), v_msg),
        '23514', 'resolving a message requires a note');
    perform tests.assert_error(format($q$update public.messages set admin_resolution_note = 'no timestamp' where id = %L$q$, v_msg),
        '23514', 'a note without a resolution time is rejected');
    perform tests.assert_ok(format($q$update public.messages set admin_resolved_at = now(), admin_resolved_by = %L,
        admin_resolution_note = 'Contacted provider, no action needed' where id = %L$q$, tests.uid(2), v_msg),
        'an administrator can resolve a stuck message with a note');
end
$$;

-- Routes ------------------------------------------------------------------------------------------------------
do $$
declare
    v_a uuid := private.get_or_create_sms_conversation(tests.uid(1), '+15550100404');
    v_b uuid := private.get_or_create_sms_conversation(tests.uid(2), '+15550100404');
begin
    insert into public.sms_routes (user_id, conversation_id, platform_number, remote_number)
    values (tests.uid(1), v_a, '+15550100900', '+15550100404');
    perform tests.assert_error(format($q$insert into public.sms_routes (user_id, conversation_id, platform_number, remote_number)
        values (%L, %L, '+15550100900', '+15550100404')$q$, tests.uid(2), v_b), '23505',
        'two users cannot hold the same active (platform number, remote number) route');
    perform tests.assert_ok(format($q$insert into public.sms_routes (user_id, conversation_id, platform_number, remote_number)
        values (%L, %L, '+15550100901', '+15550100404')$q$, tests.uid(2), v_b),
        'a different platform number can serve the same remote number');
end
$$;

rollback;
