-- Test file 04: Row Level Security and privileges.
-- Users: 1 alice, 2 bob, 3 carol, 4 admin, 5 eve (outsider).
-- Every section switches to a role, asserts, and switches back.
begin;

select tests.create_user(tests.uid(1), 'alice');
select tests.create_user(tests.uid(2), 'bob');
select tests.create_user(tests.uid(3), 'carol');
select tests.create_user(tests.uid(4), 'admin_user', 'active', 'admin');
select tests.create_user(tests.uid(5), 'eve');

-- Shared fixtures (created as the database owner) --------------------------------------------------------
create temporary table fx (name text primary key, id uuid) on commit drop;
grant all on fx to public;

do $$
declare
    v_ab uuid;
    v_sms uuid;
    v_mock uuid := (select id from public.provider_configurations where provider = 'mock');
    v_cap uuid := (select id from public.sms_country_capabilities where country_code = 'US' and is_current);
    v_req uuid;
    v_id uuid;
    v_del uuid;
begin
    update public.profiles set profile_visibility = 'contacts' where id = tests.uid(1);
    update public.profiles set profile_visibility = 'everyone' where id = tests.uid(2);
    update public.profiles set profile_visibility = 'private' where id = tests.uid(3);

    insert into public.contact_requests (from_user_id, to_user_id) values (tests.uid(2), tests.uid(1)) returning id into v_req;
    perform private.accept_contact_request(v_req, tests.uid(1));
    insert into public.contacts (owner_id, contact_type, phone_e164, display_name) values (tests.uid(1), 'sms', '+15550100101', 'Sample');
    insert into public.contact_requests (from_user_id, to_user_id) values (tests.uid(3), tests.uid(1));
    insert into public.user_blocks (blocker_id, blocked_user_id) values (tests.uid(2), tests.uid(3));
    insert into public.contact_groups (owner_id, name) values (tests.uid(1), 'Family') returning id into v_id;
    insert into fx values ('group', v_id);

    v_ab := private.get_or_create_chikka_conversation(tests.uid(1), tests.uid(2));
    insert into fx values ('conv_ab', v_ab);

    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_ab, 'chikka', 'outbound', tests.uid(1), 'm_a', 'sent', gen_random_uuid()) returning id into v_id;
    insert into fx values ('m_a', v_id);
    insert into public.message_deliveries (message_id, channel, recipient_user_id, status) values (v_id, 'chikka', tests.uid(2), 'sent');

    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_ab, 'chikka', 'outbound', tests.uid(2), 'm_b', 'sent', gen_random_uuid()) returning id into v_id;
    insert into fx values ('m_b', v_id);

    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key, suppressed_at, suppressed_reason)
    values (v_ab, 'chikka', 'outbound', tests.uid(2), 'm_suppressed', 'sent', gen_random_uuid(), now(), 'blocked') returning id into v_id;
    insert into fx values ('m_supp', v_id);

    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_ab, 'chikka', 'outbound', tests.uid(2), 'm_hidden', 'sent', gen_random_uuid()) returning id into v_id;
    insert into fx values ('m_hidden', v_id);
    insert into public.message_hides (message_id, user_id) values (v_id, tests.uid(1));

    v_sms := private.get_or_create_sms_conversation(tests.uid(1), '+15550100101');
    insert into fx values ('conv_sms', v_sms);
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count, segment_count,
                                 status, idempotency_key, is_simulated, capability_id, is_ai_assisted)
    values (v_sms, 'sms', 'outbound', tests.uid(1), 'sms body', 'gsm7', 8, 1, 'queued', gen_random_uuid(), true, v_cap, true)
    returning id into v_id;
    insert into fx values ('m_sms', v_id);
    insert into public.message_segments (message_id, segment_index, segment_count, encoding, char_count, units) values (v_id, 1, 1, 'gsm7', 8, 8);
    insert into public.message_deliveries (message_id, channel, provider_configuration_id, recipient_phone, is_simulated, status, provider_message_id)
    values (v_id, 'sms', v_mock, '+15550100101', true, 'accepted', 'SIM-RLS-1') returning id into v_del;
    insert into fx values ('d_sms', v_del);
    insert into public.sms_routes (user_id, conversation_id, platform_number, remote_number) values (tests.uid(1), v_sms, '+15550100900', '+15550100101');

    insert into public.notifications (user_id, notification_type, title) values (tests.uid(1), 'system', 'for alice'), (tests.uid(2), 'system', 'for bob');
    insert into public.user_consents (user_id, consent_type, notice_version, decision, source) values (tests.uid(1), 'terms', 'v1', 'granted', 'registration');
    insert into public.phone_numbers (user_id, e164, country_code, verification_mode, status, otp_hash, otp_expires_at)
    values (tests.uid(1), '+15550100001', 'US', 'live', 'pending', 'hash-not-a-code', now() + interval '10 minutes');
    insert into public.ai_assistance_logs (user_id, feature, model_id, outcome) values (tests.uid(1), 'rewrite', 'mock', 'success');
    insert into public.abuse_reports (reporter_id, reported_user_id, message_id, reason, snapshot)
    values (tests.uid(2), tests.uid(1), (select id from fx where name = 'm_a'), 'spam', '{"context": []}');
    insert into public.provider_webhooks (provider, kind, dedupe_key, raw_payload, signature_verified_at)
    values ('mock', 'inbound', 'rls-1', '{"Body": "private"}', now());
    insert into public.sms_opt_outs (remote_phone, source) values ('+15550100999', 'keyword');
    insert into public.message_delivery_events (delivery_id, dedupe_key, source, normalised_status, applied) values (v_del, 'e1', 'webhook', 'accepted', true);
    insert into public.audit_logs (category, action) values ('system', 'rls.test');
end
$$;

-- Structure: RLS everywhere, nothing for anon, no PUBLIC policies ---------------------------------------------
do $$
declare
    v_missing text;
begin
    select string_agg(c.relname, ', ') into v_missing
      from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;
    perform tests.assert_true(v_missing is null, 'RLS must be enabled on every public table, missing: ' || coalesce(v_missing, ''));

    select string_agg(c.relname, ', ') into v_missing
      from pg_class c join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relkind = 'r'
       and not exists (select 1 from pg_policies p where p.schemaname = 'public' and p.tablename = c.relname)
       and c.relname not in ('system_settings', 'provider_webhooks', 'message_delivery_events', 'sms_opt_outs', 'audit_logs', 'rate_limit_counters');
    perform tests.assert_true(v_missing is null,
        'every table that clients can reach needs a policy (only the six server-only tables may have none), missing: ' || coalesce(v_missing, ''));

    perform tests.assert_eq((select count(*) from information_schema.role_table_grants
                              where grantee in ('anon', 'PUBLIC') and table_schema = 'public'), 0::bigint,
        'anon and PUBLIC hold no table privileges');
    perform tests.assert_eq((select count(*) from pg_policies
                              where schemaname = 'public' and (roles && array['anon', 'public']::name[])), 0::bigint,
        'no policy applies to anon or PUBLIC');
    perform tests.assert_eq((select count(*) from information_schema.role_table_grants
                              where grantee = 'authenticated' and table_schema = 'public'
                                and table_name in ('system_settings', 'provider_webhooks', 'message_delivery_events', 'sms_opt_outs', 'audit_logs', 'rate_limit_counters')), 0::bigint,
        'authenticated has no privileges on server-only tables');
    perform tests.assert_eq((select count(*) from information_schema.role_table_grants
                              where grantee = 'authenticated' and table_schema = 'public'
                                and privilege_type in ('INSERT', 'DELETE', 'TRUNCATE')
                                and table_name in ('messages', 'message_deliveries', 'credit_transactions', 'messaging_credits',
                                                   'conversations', 'conversation_members', 'profiles', 'user_blocks')), 0::bigint,
        'clients cannot insert or delete rows in the core messaging, credit and identity tables');
end
$$;

-- Anonymous users get nothing --------------------------------------------------------------------------------------
do $$
declare
    r record;
begin
    perform tests.as_anon();
    for r in select table_name from information_schema.tables where table_schema = 'public' loop
        perform tests.assert_error(format('select 1 from public.%I limit 1', r.table_name), '42501',
            'anon must not read ' || r.table_name);
    end loop;
    perform tests.reset_role();
end
$$;

-- Profiles --------------------------------------------------------------------------------------------------------------
do $$
declare
    n int;
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.profiles'), 1::bigint, 'a user reads only their own profile row');
    update public.profiles set display_name = 'Alice Renamed' where id = tests.uid(1);
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 1, 'a user can edit their own profile');
    update public.profiles set display_name = 'Hijacked' where id = tests.uid(2);
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 0, 'a user cannot edit another profile');
    perform tests.assert_error($q$update public.profiles set role = 'admin' where id = tests.uid(1)$q$, '42501', 'a user cannot promote themselves');
    perform tests.assert_error($q$update public.profiles set status = 'active' where id = tests.uid(1)$q$, '42501', 'a user cannot change their own status');
    perform tests.assert_error($q$update public.profiles set username = 'newname' where id = tests.uid(1)$q$, '42501', 'username changes go through the backend');
    perform tests.assert_error($q$update public.profiles set ai_enabled = true where id = tests.uid(1)$q$, '42501', 'AI enablement needs recorded consent via the backend');
    perform tests.assert_error($q$insert into public.profiles (id) values (gen_random_uuid())$q$, '42501', 'clients cannot create profiles');
    perform tests.assert_error($q$delete from public.profiles where id = tests.uid(1)$q$, '42501', 'clients cannot delete profiles');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(4));
    perform tests.assert_eq(tests.count_rows('select id from public.profiles'), 5::bigint, 'an admin can read every profile');
    update public.profiles set display_name = 'Admin Edit' where id = tests.uid(1);
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 0, 'an admin has no direct write access to profiles (writes go through the audited backend)');
    perform tests.reset_role();
end
$$;

-- public_profiles ---------------------------------------------------------------------------------------------------------------
do $$
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.public_profiles'), 2::bigint, 'alice sees herself and bob (visibility everyone)');
    perform tests.assert_eq(tests.count_rows(format('select id from public.public_profiles where id = %L', tests.uid(3))), 0::bigint,
        'a private profile is hidden');
    perform tests.assert_error('select role from public.public_profiles', '42703', 'the view exposes no role column');
    perform tests.assert_error('select phone_number from public.public_profiles', '42703', 'the view exposes no phone number');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows(format('select id from public.public_profiles where id = %L', tests.uid(1))), 1::bigint,
        'a contacts-only profile is visible to its contacts');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(5));
    perform tests.assert_eq(tests.count_rows(format('select id from public.public_profiles where id = %L', tests.uid(1))), 0::bigint,
        'a contacts-only profile is hidden from strangers');
    perform tests.assert_eq(tests.count_rows(format('select id from public.public_profiles where id = %L', tests.uid(2))), 1::bigint,
        'an everyone profile is visible to strangers');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(3));
    perform tests.assert_eq(tests.count_rows(format('select id from public.public_profiles where id = %L', tests.uid(2))), 0::bigint,
        'a blocked user cannot see the blocker');
    perform tests.assert_eq(tests.count_rows(format('select id from public.public_profiles where id = %L', tests.uid(3))), 1::bigint,
        'a user always sees themselves');
    perform tests.reset_role();
end
$$;

-- Contacts, requests, groups, blocks ------------------------------------------------------------------------------------------
do $$
declare
    n int;
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.contacts'), 2::bigint, 'alice sees her own contacts');
    perform tests.assert_error(format($q$insert into public.contacts (owner_id, contact_type, contact_user_id) values (%L, 'chikka', %L)$q$, tests.uid(1), tests.uid(5)),
        '42501', 'a Chikka contact cannot be created without an accepted request');
    perform tests.assert_error(format($q$insert into public.contacts (owner_id, contact_type, contact_user_id) values (%L, 'sms', null)$q$, tests.uid(2)),
        '42501', 'cannot create a contact for someone else');
    perform tests.assert_ok(format($q$insert into public.contacts (owner_id, contact_type, phone_e164, display_name) values (%L, 'sms', '+15550100555', 'New')$q$, tests.uid(1)),
        'a user can add their own SMS contact');
    perform tests.assert_error('update public.contacts set contact_type = ''chikka''', '42501', 'contact type cannot be edited');
    perform tests.assert_error('update public.contacts set owner_id = gen_random_uuid()', '42501', 'contact ownership cannot be transferred');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows('select id from public.contacts'), 1::bigint, 'bob sees only his own contact row');
    update public.contacts set display_name = 'tamper' where contact_user_id = tests.uid(2);
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 0, 'cannot edit another owner''s contact');
    perform tests.assert_eq(tests.count_rows('select id from public.contact_requests'), 1::bigint, 'bob sees only the request he sent');
    perform tests.assert_eq(tests.count_rows('select id from public.contact_groups'), 0::bigint, 'groups are private to the owner');
    perform tests.assert_eq(tests.count_rows('select id from public.user_blocks'), 1::bigint, 'the blocker sees their block');
    perform tests.assert_error(format($q$insert into public.contact_groups (owner_id, name) values (%L, 'forged')$q$, tests.uid(1)),
        '42501', 'cannot create a group for someone else');
    perform tests.assert_error(format($q$insert into public.user_blocks (blocker_id, blocked_user_id) values (%L, %L)$q$, tests.uid(2), tests.uid(5)),
        '42501', 'blocks are written by the audited backend');
    perform tests.assert_error(format($q$insert into public.contact_requests (from_user_id, to_user_id) values (%L, %L)$q$, tests.uid(2), tests.uid(5)),
        '42501', 'requests are written by the backend');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(3));
    perform tests.assert_eq(tests.count_rows('select id from public.user_blocks'), 0::bigint, 'a blocked user cannot see that they are blocked');
    perform tests.assert_eq(tests.count_rows('select id from public.contact_requests'), 1::bigint, 'the sender sees their own request');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.contact_requests'), 2::bigint, 'the recipient sees requests addressed to them');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(5));
    perform tests.assert_eq(tests.count_rows('select id from public.contact_requests'), 0::bigint, 'a bystander sees no requests');
    perform tests.assert_eq(tests.count_rows('select id from public.contacts'), 0::bigint, 'a stranger sees no contacts');
    perform tests.reset_role();
end
$$;

-- Conversations, members, messages ------------------------------------------------------------------------------------------------
do $$
declare
    n int;
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.conversations'), 2::bigint, 'alice sees her two conversations');
    perform tests.assert_eq(tests.count_rows('select id from public.messages'), 3::bigint,
        'alice sees m_a, m_b and her SMS, but not the suppressed or self-hidden messages');
    perform tests.assert_eq(tests.count_rows('select conversation_id from public.conversation_members'), 2::bigint, 'a member sees only their own membership rows');
    perform tests.assert_eq(tests.count_rows('select id from public.message_segments'), 1::bigint, 'segments follow message visibility');
    perform tests.assert_eq(tests.count_rows('select message_id from public.message_hides'), 1::bigint, 'alice sees her own hide marker');
    perform tests.assert_error('select is_ai_assisted from public.messages', '42501', 'AI assistance is never readable by clients');
    perform tests.assert_error('select suppressed_at from public.messages', '42501', 'block suppression is never readable by clients');
    perform tests.assert_error('select request_hash from public.messages', '42501', 'request hashes are server-only');
    perform tests.assert_error('select * from public.messages', '42501', 'select * is refused because sensitive columns are not granted');
    perform tests.assert_error(format($q$insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
        values (%L, 'chikka', 'outbound', %L, 'direct write', 'sent', gen_random_uuid())$q$, (select id from fx where name = 'conv_ab'), tests.uid(1)),
        '42501', 'messages can only be written by the backend');
    perform tests.assert_error('update public.messages set body = ''edited''', '42501', 'clients cannot edit messages directly');
    perform tests.assert_error('delete from public.messages', '42501', 'clients cannot delete messages directly');

    update public.conversation_members set is_pinned = true, pinned_at = now() where user_id = tests.uid(1);
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 2, 'a member can pin their own conversations');
    perform tests.assert_error('update public.conversation_members set last_read_seq = 99', '42501', 'read markers are backend-only');
    perform tests.assert_error('update public.conversation_members set cleared_before_seq = 99', '42501', 'clearing history is backend-only');
    update public.conversation_members set is_archived = true where user_id = tests.uid(2);
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 0, 'cannot change another member''s view state');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows(format('select id from public.messages where conversation_id = %L', (select id from fx where name = 'conv_ab'))), 4::bigint,
        'bob sees all four messages, including his own suppressed one (the block stays invisible to him)');
    perform tests.assert_eq(tests.count_rows('select id from public.conversations'), 1::bigint, 'bob sees only his conversation');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(3));
    perform tests.assert_eq(tests.count_rows('select id from public.conversations'), 0::bigint, 'a non-member sees no conversations');
    perform tests.assert_eq(tests.count_rows('select id from public.messages'), 0::bigint, 'a non-member sees no messages');
    perform tests.assert_eq(tests.count_rows('select id from public.message_segments'), 0::bigint, 'a non-member sees no segments');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(4));
    perform tests.assert_eq(tests.count_rows('select id from public.messages'), 0::bigint, 'administrators cannot browse message content');
    perform tests.assert_eq(tests.count_rows('select id from public.conversations'), 0::bigint, 'administrators cannot browse conversations');
    perform tests.reset_role();
end
$$;

-- Clearing history and leaving ---------------------------------------------------------------------------------------------------------
do $$
declare
    v_ab uuid := (select id from fx where name = 'conv_ab');
begin
    update public.conversation_members set cleared_before_seq = 2 where conversation_id = v_ab and user_id = tests.uid(2);
    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows(format('select id from public.messages where conversation_id = %L', v_ab)), 2::bigint,
        'cleared history stays hidden: only messages after cleared_before_seq remain');
    perform tests.reset_role();

    update public.conversation_members set left_at = now() where conversation_id = v_ab and user_id = tests.uid(2);
    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows(format('select id from public.messages where conversation_id = %L', v_ab)), 0::bigint,
        'a member who left loses access to messages');
    perform tests.assert_eq(tests.count_rows(format('select id from public.conversations where id = %L', v_ab)), 0::bigint,
        'a member who left loses access to the conversation');
    perform tests.reset_role();
end
$$;

-- Deliveries --------------------------------------------------------------------------------------------------------------------------------
do $$
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.message_deliveries'), 2::bigint, 'the sender sees delivery state of their messages');
    perform tests.assert_error('select provider_message_id from public.message_deliveries', '42501', 'provider identifiers are server-only');
    perform tests.assert_error('select failure_code from public.message_deliveries', '42501', 'error codes are server-only');
    perform tests.assert_error('select read_at from public.message_deliveries', '42501', 'read timestamps are not client-readable');
    perform tests.assert_error('update public.message_deliveries set status = ''delivered''', '42501', 'clients cannot change delivery status');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows('select id from public.message_deliveries'), 1::bigint, 'the recipient sees their own delivery row');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(3));
    perform tests.assert_eq(tests.count_rows('select id from public.message_deliveries'), 0::bigint, 'strangers see no deliveries');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(4));
    perform tests.assert_eq(tests.count_rows('select id from public.message_deliveries'), 2::bigint, 'administrators can audit delivery state');
    perform tests.reset_role();
end
$$;

-- Notifications, preferences, phone numbers, consents -----------------------------------------------------------------------------------------
do $$
declare
    n int;
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.notifications'), 1::bigint, 'a user sees only their notifications');
    update public.notifications set read_at = now();
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 1, 'a user can mark their notification read, and only theirs');
    perform tests.assert_error('update public.notifications set title = ''forged''', '42501', 'notification content is not editable');
    perform tests.assert_error('delete from public.notifications', '42501', 'clients dismiss notifications instead of deleting');

    perform tests.assert_eq(tests.count_rows('select user_id from public.notification_preferences'), 1::bigint, 'own preferences only');
    update public.notification_preferences set show_previews = true;
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 1, 'a user can edit their own preferences');
    perform tests.assert_error('update public.notification_preferences set email_hard_bounce_count = 0', '42501', 'bounce counters are server-managed');

    perform tests.assert_eq(tests.count_rows('select id from public.phone_numbers'), 1::bigint, 'a user sees their own phone numbers');
    perform tests.assert_error('select otp_hash from public.phone_numbers', '42501', 'OTP hashes are never readable by clients');
    perform tests.assert_error('select otp_expires_at from public.phone_numbers', '42501', 'OTP state is never readable by clients');

    perform tests.assert_eq(tests.count_rows('select id from public.user_consents'), 1::bigint, 'a user sees their own consent history');
    perform tests.assert_error(format($q$insert into public.user_consents (user_id, consent_type, notice_version, decision, source)
        values (%L, 'terms', 'v2', 'granted', 'settings')$q$, tests.uid(1)), '42501', 'consent is recorded by the backend');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows('select id from public.notifications'), 1::bigint, 'bob sees only his notification');
    perform tests.assert_eq(tests.count_rows('select id from public.phone_numbers'), 0::bigint, 'bob sees no phone numbers');
    perform tests.assert_eq(tests.count_rows('select id from public.user_consents'), 0::bigint, 'bob sees no consents');
    perform tests.reset_role();
end
$$;

-- Credits -----------------------------------------------------------------------------------------------------------------------------------
do $$
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select user_id from public.messaging_credits'), 2::bigint, 'a user sees their own live and demo balances');
    perform tests.assert_eq(tests.count_rows('select id from public.credit_transactions'), 1::bigint, 'a user sees their own ledger');
    perform tests.assert_error('update public.messaging_credits set balance_units = 999999', '42501', 'balances cannot be edited by clients');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta)
        values (%L, 'live', 'top_up', 1000)$q$, tests.uid(1)), '42501', 'clients cannot create ledger entries');
    perform tests.assert_error('select external_reference from public.credit_transactions', '42501', 'payment references are server-only');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(3));
    perform tests.assert_eq(tests.count_rows(format('select user_id from public.messaging_credits where user_id = %L', tests.uid(1))), 0::bigint,
        'other users'' balances are invisible');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(4));
    perform tests.assert_eq(tests.count_rows('select user_id from public.messaging_credits'), 10::bigint, 'an administrator can read all balances');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reason, actor_id)
        values (%L, 'demo', 'adjustment', 100, 'x', %L)$q$, tests.uid(1), tests.uid(4)), '42501',
        'even administrators change credits only through the audited backend');
    perform tests.reset_role();
end
$$;

-- AI history and reports ---------------------------------------------------------------------------------------------------------------------
do $$
declare
    n int;
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.ai_assistance_logs'), 1::bigint, 'a user sees their own AI history');
    perform tests.assert_eq(tests.count_rows('select id from public.abuse_reports'), 0::bigint, 'the reported user cannot see reports about them');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows('select id from public.ai_assistance_logs'), 0::bigint, 'AI history is private');
    delete from public.ai_assistance_logs;
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 0, 'cannot delete another user''s AI history');
    perform tests.assert_eq(tests.count_rows('select id from public.abuse_reports'), 1::bigint, 'the reporter sees their report');
    update public.abuse_reports set status = 'dismissed', resolution_note = 'self-service', resolved_by = tests.uid(2), resolved_at = now();
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 0, 'a reporter cannot resolve their own report');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(4));
    perform tests.assert_eq(tests.count_rows('select id from public.ai_assistance_logs'), 0::bigint, 'administrators never see AI history or content');
    perform tests.assert_eq(tests.count_rows('select id from public.abuse_reports'), 1::bigint, 'an administrator sees the moderation queue');
    perform tests.assert_error('update public.abuse_reports set snapshot = ''{}''', '42501', 'evidence cannot be edited');
    perform tests.assert_error('update public.abuse_reports set reporter_id = reporter_id', '42501', 'report ownership cannot be edited');
    update public.abuse_reports set status = 'actioned', resolution_note = 'warned user', resolved_by = tests.uid(4), resolved_at = now();
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 1, 'an administrator can resolve a report');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(1));
    delete from public.ai_assistance_logs;
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 1, 'a user can clear their own AI history');
    perform tests.reset_role();
end
$$;

-- Platform configuration -----------------------------------------------------------------------------------------------------------------------
do $$
declare
    n int;
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select id from public.sms_country_capabilities'), 6::bigint, 'any user can read current country capabilities');
    perform tests.assert_eq(tests.count_rows('select id from public.provider_configurations'), 0::bigint, 'provider configuration is admin-only');
    perform tests.assert_eq(tests.count_rows('select id from public.sms_routes'), 1::bigint, 'a user sees their own reply route');
    perform tests.assert_error($q$insert into public.sms_country_capabilities (country_code, country_name, version, is_current) values ('ZZ', 'Nowhere', 1, true)$q$,
        '42501', 'a normal user cannot add capabilities');
    update public.sms_country_capabilities set is_current = false where country_code = 'GB';
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 0, 'a normal user cannot retire a capability version');
    perform tests.reset_role();

    perform tests.as_user(tests.uid(4));
    perform tests.assert_eq(tests.count_rows('select id from public.provider_configurations'), 2::bigint, 'an administrator can read provider configuration');
    perform tests.assert_eq(tests.count_rows('select id from public.sms_routes'), 1::bigint, 'an administrator can read reply routes');
    update public.sms_country_capabilities set is_current = false where country_code = 'GB';
    get diagnostics n = row_count;
    perform tests.assert_eq(n, 1, 'an administrator can retire a capability version');
    perform tests.assert_ok($q$insert into public.sms_country_capabilities (country_code, country_name, version, outbound_support)
        values ('GB', 'United Kingdom', 2, 'requires_verification')$q$, 'an administrator can publish a new capability version');
    perform tests.assert_error($q$update public.sms_country_capabilities set country_name = 'Renamed' where country_code = 'US'$q$, '42501',
        'published capability versions are immutable');
    perform tests.assert_error($q$update public.provider_configurations set is_active = true$q$, '42501', 'provider changes go through the audited backend');
    perform tests.reset_role();
end
$$;

-- Server-only tables: no client access, even for administrators -----------------------------------------------------------------------------------
do $$
declare
    t text;
    u int;
begin
    foreach u in array array[1, 4] loop
        perform tests.as_user(tests.uid(u));
        foreach t in array array['provider_webhooks', 'sms_opt_outs', 'message_delivery_events', 'audit_logs', 'system_settings', 'rate_limit_counters'] loop
            perform tests.assert_error(format('select 1 from public.%I limit 1', t), '42501',
                format('user %s must not read server-only table %s', u, t));
            perform tests.assert_error(format('delete from public.%I', t), '42501',
                format('user %s must not delete from server-only table %s', u, t));
        end loop;
        perform tests.reset_role();
    end loop;

    perform tests.as_service();
    perform tests.assert_true(tests.count_rows('select 1 from public.provider_webhooks') > 0, 'the service role can read webhooks');
    perform tests.assert_true(tests.count_rows('select 1 from public.messages') > 0, 'the service role bypasses RLS for backend work');
    perform tests.reset_role();
end
$$;

-- Helper function privileges --------------------------------------------------------------------------------------------------------------------------
do $$
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_error($q$select private.accept_contact_request(gen_random_uuid(), auth.uid())$q$, '42501',
        'clients cannot call backend-only functions');
    perform tests.assert_error($q$select private.get_or_create_chikka_conversation(auth.uid(), gen_random_uuid())$q$, '42501',
        'clients cannot create conversations directly');
    perform tests.assert_error($q$select private.has_active_consent(auth.uid(), 'terms')$q$, '42501',
        'clients cannot probe consent state through helpers');
    perform tests.reset_role();
end
$$;

rollback;
