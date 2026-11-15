-- Demo data for the administration dashboard and manual testing. NEVER run against staging or
-- production.
--
-- Adds 20 fictional accounts (demo01 to demo20) with contacts, Chikka conversations, simulated
-- SMS in every delivery state (including retries and permanent failures), simulated credit
-- activity, AI usage, reports, notifications and audit entries. It is meant to run after
-- 01_dev_seed.sql, on a database that has been through supabase/tools/reset_dev_data.sql.
--
-- Everything is fictional. Emails use the reserved .test domain and phone numbers are in the
-- +1 555 01xx style range. All SMS use the simulation provider, so the dashboard shows
-- SIMULATED traffic only and no live message exists.
--
--   Sign in as demo01@chikka.test ... demo18@chikka.test, password: dev-password-only
--   (only when pgcrypto is available, as in Supabase local and hosted).
--   demo17, demo18  awaiting email confirmation
--   demo19          suspended
--   demo20          administrator (demo20@chikka.test)
--
-- Not seeded on purpose: message_attachments (needs files in Storage), message_hides and
-- rate_limit_counters (short-lived runtime state).

do $$
begin
    if coalesce(current_setting('app.environment', true), 'development') in ('production', 'staging') then
        raise exception 'Refusing to run demo seed in environment %', current_setting('app.environment', true);
    end if;
    if exists (select 1 from auth.users where email like 'demo%@chikka.test') then
        raise exception 'Demo data is already present. Run supabase/tools/reset_dev_data.sql, then the files in supabase/seed/ in order.';
    end if;
end
$$;

-- Helpers live in the session's temporary schema and disappear when it ends.
create or replace function pg_temp.demo_user(n int) returns uuid
language sql immutable
as $$ select ('20000000-0000-4000-8000-' || lpad(n::text, 12, '0'))::uuid $$;

-- One delivery attempt plus the status events that attempt would have produced.
create or replace function pg_temp.add_attempt(
    p_message uuid, p_attempt int, p_retry_of uuid, p_phone text, p_status text,
    p_class text, p_permanent boolean, p_code text, p_reason text,
    p_provider_id text, p_at timestamptz, p_provider uuid
) returns uuid
language plpgsql
as $$
declare
    v_id   uuid;
    v_rank int := case p_status when 'accepted' then 1 when 'sent' then 2
                                when 'delivered' then 3 when 'undelivered' then 3 else 0 end;
begin
    insert into public.message_deliveries
        (message_id, attempt_number, retry_of_delivery_id, channel, provider_configuration_id, recipient_phone,
         is_simulated, status, provider_status, provider_message_id, failure_class, is_permanent, failure_code,
         failure_reason, next_attempt_at, started_at, accepted_at, sent_at, delivered_at, terminal_at, created_at)
    values
        (p_message, p_attempt, p_retry_of, 'sms', p_provider, p_phone,
         true, p_status, p_status, p_provider_id, p_class, p_permanent, p_code,
         p_reason,
         case when p_status = 'queued' then p_at end,
         case when p_status <> 'queued' then p_at end,
         case when v_rank >= 1 then p_at + interval '2 seconds' end,
         case when v_rank >= 2 then p_at + interval '5 seconds' end,
         case when p_status = 'delivered' then p_at + interval '9 seconds' end,
         case when p_status in ('delivered', 'undelivered', 'failed') then p_at + interval '9 seconds' end,
         p_at)
    returning id into v_id;

    if v_rank >= 1 then
        insert into public.message_delivery_events (delivery_id, dedupe_key, source, provider_status, normalised_status, applied, received_at)
        values (v_id, p_provider_id || ':accepted', 'send_response', 'accepted', 'accepted', true, p_at + interval '2 seconds');
    end if;
    if v_rank >= 2 then
        insert into public.message_delivery_events (delivery_id, dedupe_key, source, provider_status, normalised_status, applied, received_at)
        values (v_id, p_provider_id || ':sent', 'simulation', 'sent', 'sent', true, p_at + interval '5 seconds');
    end if;
    if v_rank = 3 then
        insert into public.message_delivery_events (delivery_id, dedupe_key, source, provider_status, normalised_status, applied, received_at)
        values (v_id, p_provider_id || ':' || p_status, 'simulation', p_status, p_status, true, p_at + interval '9 seconds');
    end if;
    if p_status = 'failed' then
        insert into public.message_delivery_events (delivery_id, dedupe_key, source, provider_status, normalised_status, applied, received_at)
        values (v_id, 'attempt-' || p_attempt || ':failed', 'system', 'failed', 'failed', true, p_at + interval '1 second');
    end if;
    return v_id;
end;
$$;

-- 1. Auth users and profiles ----------------------------------------------------------------
do $$
declare
    v_hash text := null;
    v_names text[] := array['Maria Santos', 'Juan Dela Cruz', 'Liza Reyes', 'Paolo Garcia', 'Ana Mendoza',
        'Carlo Bautista', 'Rina Aquino', 'Miguel Torres', 'Joy Ramos', 'Dennis Cruz', 'Grace Flores',
        'Mark Villanueva', 'Tessa Navarro', 'Ramon Castillo', 'Bea Domingo', 'Noel Salazar', 'Lea Pascual',
        'Jun Aguilar', 'Nina Soriano', 'Eric Valdez'];
    v_countries text[] := array['PH', 'PH', 'PH', 'PH', 'SG', 'PH', 'AE', 'PH', 'US', 'PH', 'AU', 'PH', 'PH',
        'SG', 'PH', 'AE', 'PH', 'US', 'PH', 'AU'];
    v_column text;
    n int;
begin
    if to_regprocedure('extensions.crypt(text,text)') is not null then
        execute $q$select extensions.crypt('dev-password-only', extensions.gen_salt('bf'))$q$ into v_hash;
    end if;

    for n in 1..20 loop
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
                                raw_user_meta_data, raw_app_meta_data, created_at, updated_at)
        values (pg_temp.demo_user(n), '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
                format('demo%s@chikka.test', lpad(n::text, 2, '0')), v_hash,
                case when n in (17, 18) then null else now() end,
                jsonb_build_object('display_name', v_names[n]),
                '{"provider": "email", "providers": ["email"]}', now(), now());
    end loop;

    -- Same GoTrue repairs as 01_dev_seed.sql so the accounts can sign in on hosted Supabase.
    foreach v_column in array array['confirmation_token', 'recovery_token', 'email_change', 'email_change_token_new']
    loop
        if exists (select 1 from information_schema.columns
                    where table_schema = 'auth' and table_name = 'users' and column_name = v_column) then
            execute format('update auth.users set %1$I = coalesce(%1$I, '''') where email like %2$L',
                           v_column, 'demo%@chikka.test');
        end if;
    end loop;
    if to_regclass('auth.identities') is not null then
        insert into auth.identities (provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
        select u.id::text, u.id,
               jsonb_build_object('sub', u.id::text, 'email', u.email, 'email_verified', u.email_confirmed_at is not null),
               'email', now(), now(), now()
          from auth.users u
         where u.email like 'demo%@chikka.test'
           and not exists (select 1 from auth.identities i where i.user_id = u.id);
    end if;

    -- The on_auth_user_created trigger made the profiles; fill them in.
    for n in 1..20 loop
        update public.profiles set
            username = format('demo_%s', lpad(n::text, 2, '0')),
            country_code = v_countries[n],
            time_zone = case when v_countries[n] = 'PH' then 'Asia/Manila' else 'UTC' end,
            role = case when n = 20 then 'admin' else 'user' end,
            status = case when n in (17, 18) then 'pending_verification' when n = 19 then 'suspended' else 'active' end,
            suspended_at = case when n = 19 then now() - interval '3 days' end,
            ai_enabled = (n % 2 = 0 and n <= 16),
            onboarding_completed_at = case when n in (17, 18) then null else now() - interval '20 days' end,
            last_seen_at = case when n in (17, 18) then null else now() - n * interval '29 hours' end,
            created_at = now() - (45 - n) * interval '1 day'
         where id = pg_temp.demo_user(n);
    end loop;
end
$$;

-- 2. Phone numbers, consents, contacts, groups, blocks --------------------------------------
do $$
declare
    n int;
    k int;
    v_request uuid;
    v_contact uuid;
    v_group uuid;
    v_labels text[] := array['Nanay', 'Kuya', 'Ate', 'Tito Ben', 'Lola', 'Pinsan'];
begin
    for n in 1..16 loop
        insert into public.phone_numbers (user_id, e164, country_code, verification_mode, status, verified_at)
        values (pg_temp.demo_user(n), '+1555011' || lpad(n::text, 4, '0'), 'US', 'simulated', 'verified', now() - interval '19 days');

        insert into public.user_consents (user_id, consent_type, notice_version, decision, source)
        values (pg_temp.demo_user(n), 'terms', '2026-11', 'granted', 'registration'),
               (pg_temp.demo_user(n), 'privacy', '2026-11', 'granted', 'registration');
        if n % 2 = 0 then
            insert into public.user_consents (user_id, consent_type, notice_version, decision, source)
            values (pg_temp.demo_user(n), 'ai_use', '2026-11', 'granted', 'settings');
        end if;
    end loop;

    -- Mutual Chikka contacts through the real accept flow: 1-2, 2-3, ... 15-16.
    for n in 1..15 loop
        insert into public.contact_requests (from_user_id, to_user_id, note)
        values (pg_temp.demo_user(n), pg_temp.demo_user(n + 1), 'Hi, it is demo' || lpad(n::text, 2, '0') || '.')
        returning id into v_request;
        perform private.accept_contact_request(v_request, pg_temp.demo_user(n + 1));
    end loop;

    -- Pending requests from accounts that have not confirmed their email yet.
    insert into public.contact_requests (from_user_id, to_user_id, note)
    values (pg_temp.demo_user(17), pg_temp.demo_user(1), 'Pending sample request'),
           (pg_temp.demo_user(18), pg_temp.demo_user(2), 'Pending sample request');

    -- Two SMS contacts per sender, with attestation for each recipient.
    for n in 1..14 loop
        for k in 1..2 loop
            insert into public.contacts (owner_id, contact_type, phone_e164, display_name, is_favourite)
            values (pg_temp.demo_user(n), 'sms', '+1555012' || lpad((n * 2 - 2 + k)::text, 4, '0'),
                    v_labels[(n + k) % 6 + 1], k = 1)
            returning id into v_contact;
            insert into public.user_consents (user_id, consent_type, notice_version, decision, source, recipient_phone)
            values (pg_temp.demo_user(n), 'sms_sender_attestation', '2026-11', 'granted', 'compose',
                    '+1555012' || lpad((n * 2 - 2 + k)::text, 4, '0'));
            if k = 1 and n <= 8 then
                insert into public.contact_groups (owner_id, name, color)
                values (pg_temp.demo_user(n), 'Family', '#3366CC') returning id into v_group;
                insert into public.contact_group_members (group_id, contact_id, owner_id)
                values (v_group, v_contact, pg_temp.demo_user(n));
            end if;
        end loop;
    end loop;

    insert into public.user_blocks (blocker_id, blocked_user_id) values (pg_temp.demo_user(15), pg_temp.demo_user(19));
    insert into public.user_blocks (blocker_id, blocked_phone) values (pg_temp.demo_user(16), '+15550129999');
end
$$;

-- 3. Chikka-to-Chikka conversations ----------------------------------------------------------
do $$
declare
    n int;
    i int;
    v_total int;
    v_conv uuid;
    v_msg uuid;
    v_from uuid;
    v_to uuid;
    v_at timestamptz;
    v_status text;
    v_bodies text[] := array['Kumusta?', 'Online ka ba?', 'Sige, mamaya tayo mag-usap.', 'Salamat!', 'Nakauwi ka na ba?',
        'Ingat ka lagi.', 'Tawagan kita mamaya.', 'Okay, noted.', 'Miss na kita!'];
begin
    for n in 1..15 loop
        v_conv := private.get_or_create_chikka_conversation(pg_temp.demo_user(n), pg_temp.demo_user(n + 1));
        v_total := 4 + n % 4;
        for i in 1..v_total loop
            v_from := case when i % 2 = 1 then pg_temp.demo_user(n) else pg_temp.demo_user(n + 1) end;
            v_to   := case when i % 2 = 1 then pg_temp.demo_user(n + 1) else pg_temp.demo_user(n) end;
            v_at := now() - interval '12 days' + (n * 7 + i * 3) * interval '1 hour';
            v_status := case when n = 9 and i = 4 then 'failed'
                             when i = v_total or (n + i) % 3 = 0 then 'delivered'
                             else 'read' end;

            insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key, created_at)
            values (v_conv, 'chikka', 'outbound', v_from, v_bodies[(n + i) % 9 + 1], 'sent', gen_random_uuid(), v_at)
            returning id into v_msg;

            insert into public.message_deliveries
                (message_id, channel, recipient_user_id, status, failure_class, failure_code, sent_at, delivered_at, read_at, created_at)
            values (v_msg, 'chikka', v_to, v_status,
                    case when v_status = 'failed' then 'transient' end,
                    case when v_status = 'failed' then 'recipient_unavailable' end,
                    v_at, case when v_status in ('delivered', 'read') then v_at + interval '2 seconds' end,
                    case when v_status = 'read' then v_at + interval '1 minute' end, v_at);
        end loop;
    end loop;
end
$$;

-- 4. Simulated SMS, credits, webhooks, opt-outs ----------------------------------------------
do $$
declare
    v_mock uuid;
    v_cap  uuid;
    v_n int;
    v_k int;
    v_m int;
    v_pick int;
    v_seq int := 0;
    v_user uuid;
    v_remote text;
    v_conv uuid;
    v_msg uuid;
    v_in uuid;
    v_d1 uuid;
    v_d2 uuid;
    v_wh uuid;
    v_at timestamptz;
    v_body text;
    v_bodies text[] := array['Kumusta po kayo diyan?', 'Padala ko na po ang pera ngayon.', 'Nakarating na ba ang package?',
        'Happy birthday! Ingat lagi.', 'Tawag ako mamaya pagkatapos ng trabaho.', 'Mag-ingat po kayo sa biyahe.'];
    v_final text;
begin
    select id into v_mock from public.provider_configurations where provider = 'mock' and mode = 'simulation';
    select id into v_cap from public.sms_country_capabilities where country_code = 'US' and is_current;
    if v_mock is null or v_cap is null then
        raise exception 'Reference data is missing (mock provider or US capability). Apply the migrations first.';
    end if;

    for v_n in 1..14 loop
        v_user := pg_temp.demo_user(v_n);
        for v_k in 1..2 loop
            v_remote := '+1555012' || lpad((v_n * 2 - 2 + v_k)::text, 4, '0');
            v_conv := private.get_or_create_sms_conversation(v_user, v_remote);
            insert into public.sms_routes (user_id, conversation_id, platform_number, remote_number, last_outbound_at)
            values (v_user, v_conv, '+15550100900', v_remote, now() - interval '1 day');

            for v_m in 1..3 loop
                v_seq := v_seq + 1;
                v_pick := (v_n * 7 + v_k * 3 + v_m * 5) % 10;
                v_body := v_bodies[(v_n + v_k + v_m) % 6 + 1];
                v_at := case when v_pick in (6, 9) then now() - (v_n + v_m) * interval '1 minute'
                             else now() - (((v_n * 17 + v_k * 31 + v_m * 53) % 230) + 1) * interval '1 hour' end;
                v_final := case
                    when v_pick <= 3 then 'delivered'
                    when v_pick = 4 then 'delivered'   -- after one transient failure
                    when v_pick = 5 then 'sent'
                    when v_pick = 6 then 'accepted'
                    when v_pick = 7 then 'undelivered'
                    when v_pick = 8 then 'failed'
                    else 'queued' end;

                insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count,
                                             segment_count, status, idempotency_key, is_simulated, capability_id,
                                             credit_cost_units, created_at)
                values (v_conv, 'sms', 'outbound', v_user, v_body, 'gsm7', char_length(v_body), 1, 'queued',
                        gen_random_uuid(), true, v_cap, 100, v_at)
                returning id into v_msg;
                insert into public.message_segments (message_id, segment_index, segment_count, encoding, char_count, units)
                values (v_msg, 1, 1, 'gsm7', char_length(v_body), char_length(v_body));

                insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id,
                                                        provider, country_code, segment_count, capability_id, created_at)
                values (v_user, 'demo', 'reservation', 0, 100, v_msg, 'mock', 'US', 1, v_cap, v_at);

                if v_pick = 4 then
                    v_d1 := pg_temp.add_attempt(v_msg, 1, null, v_remote, 'failed', 'transient', false,
                                                'SIM-TRANSIENT', 'Simulated provider outage', null, v_at, v_mock);
                    perform pg_temp.add_attempt(v_msg, 2, v_d1, v_remote, 'delivered', null, false, null, null,
                                                'SIM-D' || lpad(v_seq::text, 5, '0'), v_at + interval '30 seconds', v_mock);
                elsif v_pick = 8 then
                    v_d1 := pg_temp.add_attempt(v_msg, 1, null, v_remote, 'failed', 'transient', false,
                                                'SIM-TRANSIENT', 'Simulated provider outage', null, v_at, v_mock);
                    v_d2 := pg_temp.add_attempt(v_msg, 2, v_d1, v_remote, 'failed', 'transient', false,
                                                'SIM-TRANSIENT', 'Simulated provider outage', null, v_at + interval '30 seconds', v_mock);
                    perform pg_temp.add_attempt(v_msg, 3, v_d2, v_remote, 'failed', 'permanent', true,
                                                'SIM-INVALID', 'Simulated permanent failure', null, v_at + interval '90 seconds', v_mock);
                elsif v_pick = 9 then
                    perform pg_temp.add_attempt(v_msg, 1, null, v_remote, 'queued', null, false, null, null, null, v_at, v_mock);
                else
                    perform pg_temp.add_attempt(v_msg, 1, null, v_remote, v_final, null, false, null, null,
                                                'SIM-D' || lpad(v_seq::text, 5, '0'), v_at, v_mock);
                end if;

                -- Credits follow the rule: charged once the provider accepts, released on permanent failure.
                if v_final in ('delivered', 'sent', 'accepted', 'undelivered') then
                    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id,
                                                            provider, country_code, segment_count, capability_id, created_at)
                    values (v_user, 'demo', 'deduction', -100, -100, v_msg, 'mock', 'US', 1, v_cap, v_at + interval '3 seconds');
                elsif v_final = 'failed' then
                    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id,
                                                            provider, country_code, segment_count, capability_id, created_at)
                    values (v_user, 'demo', 'reservation_release', 0, -100, v_msg, 'mock', 'US', 1, v_cap, v_at + interval '90 seconds');
                end if;
            end loop;

            -- Every other contact replies once.
            if (v_n + v_k) % 2 = 0 then
                v_seq := v_seq + 1;
                v_at := now() - (((v_n * 11 + v_k * 29) % 100) + 1) * interval '1 hour';
                insert into public.provider_webhooks (provider, provider_configuration_id, kind, dedupe_key, provider_message_id,
                                                      raw_payload, signature_verified_at, is_simulated, processing_status,
                                                      processed_at, routing_result, received_at)
                values ('mock', v_mock, 'inbound', 'SIM-IN-' || lpad(v_seq::text, 5, '0'), 'SIM-IN-' || lpad(v_seq::text, 5, '0'),
                        jsonb_build_object('From', v_remote, 'To', '+15550100900', 'Body', 'Salamat po! (simulated reply)'),
                        v_at, true, 'processed', v_at, 'routed', v_at)
                returning id into v_wh;
                insert into public.messages (conversation_id, channel, direction, sender_phone, body, status, is_simulated, created_at)
                values (v_conv, 'sms', 'inbound', v_remote, 'Salamat po! (simulated reply)', 'received', true, v_at)
                returning id into v_in;
                insert into public.message_deliveries (message_id, channel, provider_configuration_id, recipient_user_id, recipient_phone,
                                                       is_simulated, status, provider_status, provider_message_id, delivered_at, created_at)
                values (v_in, 'sms', v_mock, v_user, '+15550100900', true, 'delivered', 'received',
                        'SIM-IN-' || lpad(v_seq::text, 5, '0'), v_at, v_at);
                update public.provider_webhooks set message_id = v_in where id = v_wh;
            end if;
        end loop;
    end loop;

    -- Callbacks that need an administrator's attention.
    insert into public.provider_webhooks (provider, provider_configuration_id, kind, dedupe_key, raw_payload, signature_verified_at,
                                          is_simulated, processing_status, processed_at, routing_result, received_at)
    values ('mock', v_mock, 'inbound', 'SIM-UNROUTED-1', '{"From": "+15550129201", "To": "+15550100900", "Body": "Wrong number?"}',
            now() - interval '5 hours', true, 'processed', now() - interval '5 hours', 'unrouted', now() - interval '5 hours'),
           ('mock', v_mock, 'inbound', 'SIM-UNROUTED-2', '{"From": "+15550129202", "To": "+15550100900", "Body": "Who is this?"}',
            now() - interval '2 hours', true, 'processed', now() - interval '2 hours', 'unrouted', now() - interval '2 hours');
    insert into public.provider_webhooks (provider, provider_configuration_id, kind, dedupe_key, provider_message_id, raw_payload,
                                          signature_verified_at, is_simulated, processing_status, process_attempts, error_code, received_at)
    values ('mock', v_mock, 'status', 'SIM-STATUS-FAILED-1', 'SIM-D99999', '{"MessageStatus": "delivered"}',
            now() - interval '3 hours', true, 'failed', 2, 'processing_error', now() - interval '3 hours'),
           ('mock', v_mock, 'status', 'SIM-STATUS-ORPHAN-1', 'SIM-D88888', '{"MessageStatus": "sent"}',
            now() - interval '4 hours', true, 'orphaned', 1, 'delivery_not_found', now() - interval '4 hours');

    insert into public.sms_opt_outs (remote_phone, platform_number, source, keyword, opted_out_at)
    values ('+15550129991', null, 'keyword', 'STOP', now() - interval '6 days'),
           ('+15550129992', null, 'provider_block', null, now() - interval '2 days');

    -- A small manual credit adjustment by the administrator.
    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reason, actor_id, external_reference)
    values (pg_temp.demo_user(5), 'demo', 'adjustment', 500, 'Goodwill credits (demo data)', pg_temp.demo_user(20), 'admin_adjust:demo-seed-1');
end
$$;

-- 5. Notifications, AI usage, reports, audit trail --------------------------------------------
do $$
declare
    n int;
    i int;
    v_features text[] := array['suggest_replies', 'translate', 'rewrite', 'tone_adjust', 'summarise', 'compose', 'optimise_sms'];
    v_decisions text[] := array['accepted', 'edited', 'dismissed', 'dismissed'];
    v_outcome text;
    v_at timestamptz;
begin
    for n in 1..16 loop
        insert into public.notifications (user_id, notification_type, title, body, created_at)
        values (pg_temp.demo_user(n), 'system', 'Welcome to Chikka Reborn', 'Demo account. Messages sent here are simulated.',
                now() - interval '19 days');
    end loop;
    insert into public.notifications (user_id, notification_type, title, reference_type, reference_id)
    select m.sender_user_id, 'sms_failed', 'An SMS could not be delivered', 'message', m.id
      from public.messages m
     where m.channel = 'sms' and m.status = 'failed' and m.is_simulated;

    -- AI usage: metadata only. No prompts or output are stored.
    for n in 2..16 by 2 loop
        for i in 1..5 loop
            v_outcome := case when (n + i) % 9 = 0 then 'timeout'
                              when (n + i) % 11 = 0 then 'throttled'
                              when (n + i) % 13 = 0 then 'invalid_output'
                              else 'success' end;
            v_at := now() - (((n * 19 + i * 41) % 28) + 1) * interval '1 day' - i * interval '3 hours';
            insert into public.ai_assistance_logs (user_id, feature, model_id, prompt_version, outcome, user_decision,
                                                   input_tokens, output_tokens, latency_ms, error_code, created_at)
            values (pg_temp.demo_user(n), v_features[(n + i) % 7 + 1], 'mock-model', 'v1', v_outcome,
                    case when v_outcome = 'success' then v_decisions[(n + i) % 4 + 1] else 'pending' end,
                    80 + (n * i * 13) % 300,
                    case when v_outcome = 'success' then 30 + (n * i * 7) % 120 else 0 end,
                    case when v_outcome = 'timeout' then 15000 else 300 + (n * i * 37) % 1800 end,
                    case when v_outcome = 'success' then null else v_outcome end,
                    v_at);
        end loop;
    end loop;

    -- Reports from three pairs of users who chat with each other: one open, one actioned, one dismissed.
    insert into public.abuse_reports (reporter_id, reported_user_id, message_id, conversation_id, reason, note, snapshot,
                                      status, resolution_note, resolved_by, resolved_at, created_at)
    select pg_temp.demo_user(r.reporter), pg_temp.demo_user(r.reported), m.id, m.conversation_id, r.reason,
           'Demo report', jsonb_build_object('reported', jsonb_build_object('message_id', m.id, 'body', m.body), 'context', '[]'::jsonb),
           r.status, case when r.status in ('actioned', 'dismissed') then 'Reviewed (demo data)' end,
           case when r.status in ('actioned', 'dismissed') then pg_temp.demo_user(20) end,
           case when r.status in ('actioned', 'dismissed') then now() - interval '1 day' end,
           now() - interval '2 days'
      from (values (4, 3, 'spam', 'open'), (6, 5, 'harassment', 'actioned'), (8, 7, 'scam', 'dismissed')) as r(reporter, reported, reason, status)
      cross join lateral (
          select x.id, x.conversation_id, x.body from public.messages x
           where x.sender_user_id = pg_temp.demo_user(r.reported) and x.channel = 'chikka'
           order by x.created_at limit 1) m;

    -- Audit trail: no message bodies, phone numbers masked.
    for n in 1..16 loop
        insert into public.audit_logs (category, action, actor_id, actor_role, target_type, target_id, ip_prefix, created_at)
        values ('auth', 'auth.login', pg_temp.demo_user(n), 'user', 'user', pg_temp.demo_user(n)::text, '203.0.113.0/24',
                now() - (n * 5 % 40 + 1) * interval '1 hour');
    end loop;
    insert into public.audit_logs (category, action, outcome, actor_id, actor_role, target_type, target_id, metadata, created_at)
    values ('admin', 'admin.user_restricted', 'success', pg_temp.demo_user(20), 'admin', 'user', pg_temp.demo_user(19)::text,
            '{"reason_code": "abuse", "sessions_revoked": 1}', now() - interval '3 days'),
           ('admin', 'admin.user_viewed', 'success', pg_temp.demo_user(20), 'admin', 'user', pg_temp.demo_user(19)::text,
            '{}', now() - interval '3 days'),
           ('credit', 'credit.adjusted', 'success', pg_temp.demo_user(20), 'admin', 'user', pg_temp.demo_user(5)::text,
            '{"units": 500}', now() - interval '2 days'),
           ('moderation', 'moderation.report_resolved', 'success', pg_temp.demo_user(20), 'admin', 'report', null,
            '{"status": "actioned"}', now() - interval '1 day'),
           ('security', 'admin.access_denied', 'denied', pg_temp.demo_user(3), 'user', 'endpoint', null,
            '{"method": "GET", "route": "/api/v1/admin/dashboard"}', now() - interval '20 hours'),
           ('sms', 'sms.send.accepted', 'success', pg_temp.demo_user(1), 'user', 'provider', 'mock',
            jsonb_build_object('recipient', private.mask_phone('+15550120001'), 'mode', 'simulation', 'segments', 1),
            now() - interval '10 hours');
end
$$;
