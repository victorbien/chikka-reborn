-- Test file 05: Row Level Security for message_attachments and contact_group_members.
-- Closes the gap left by file 04, which does not exercise these two tables.
-- Users: 1 alice (uploader / owner), 2 bob (conversation member), 5 eve (outsider).
begin;

select tests.create_user(tests.uid(1), 'alice');
select tests.create_user(tests.uid(2), 'bob');
select tests.create_user(tests.uid(5), 'eve');

create temporary table fx (name text primary key, id uuid) on commit drop;
grant all on fx to public;

do $$
declare
    v_req uuid;
    v_conv uuid;
    v_msg uuid;
    v_group uuid;
    v_contact uuid;
    v_id uuid;
begin
    insert into public.contact_requests (from_user_id, to_user_id) values (tests.uid(2), tests.uid(1)) returning id into v_req;
    perform private.accept_contact_request(v_req, tests.uid(1));
    v_conv := private.get_or_create_chikka_conversation(tests.uid(1), tests.uid(2));
    insert into fx values ('conv', v_conv);

    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', tests.uid(1), 'with a file', 'sent', gen_random_uuid()) returning id into v_msg;

    -- One upload that was sent with a message, one that is still unsent (uploader only).
    insert into public.message_attachments (conversation_id, uploader_id, message_id, storage_path, file_name, content_type, size_bytes)
    values (v_conv, tests.uid(1), v_msg, 'rls/sent.png', 'sent.png', 'image/png', 100) returning id into v_id;
    insert into fx values ('att_sent', v_id);
    insert into public.message_attachments (conversation_id, uploader_id, message_id, storage_path, file_name, content_type, size_bytes)
    values (v_conv, tests.uid(1), null, 'rls/unsent.png', 'unsent.png', 'image/png', 100) returning id into v_id;
    insert into fx values ('att_unsent', v_id);

    -- A file on a message that bob hid with "delete for me", and one on a message Alice's block hides from bob.
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key)
    values (v_conv, 'chikka', 'outbound', tests.uid(1), 'hidden by bob', 'sent', gen_random_uuid()) returning id into v_msg;
    insert into public.message_hides (message_id, user_id) values (v_msg, tests.uid(2));
    insert into public.message_attachments (conversation_id, uploader_id, message_id, storage_path, file_name, content_type, size_bytes)
    values (v_conv, tests.uid(1), v_msg, 'rls/hidden.png', 'hidden.png', 'image/png', 100) returning id into v_id;
    insert into fx values ('att_hidden', v_id);
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, status, idempotency_key, suppressed_at, suppressed_reason)
    values (v_conv, 'chikka', 'outbound', tests.uid(1), 'suppressed', 'sent', gen_random_uuid(), now(), 'blocked') returning id into v_msg;
    insert into public.message_attachments (conversation_id, uploader_id, message_id, storage_path, file_name, content_type, size_bytes)
    values (v_conv, tests.uid(1), v_msg, 'rls/suppressed.png', 'suppressed.png', 'image/png', 100) returning id into v_id;
    insert into fx values ('att_suppressed', v_id);

    insert into public.contacts (owner_id, contact_type, phone_e164, display_name)
    values (tests.uid(1), 'sms', '+15550100101', 'Sample') returning id into v_contact;
    insert into public.contact_groups (owner_id, name) values (tests.uid(1), 'Family') returning id into v_group;
    insert into public.contact_group_members (group_id, contact_id, owner_id) values (v_group, v_contact, tests.uid(1));
    insert into fx values ('group', v_group), ('contact', v_contact);
end
$$;

-- message_attachments: who can see what ---------------------------------------------------------------------------------
do $$
declare
    v_sent uuid := (select id from fx where name = 'att_sent');
    v_unsent uuid := (select id from fx where name = 'att_unsent');
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select 1 from public.message_attachments'), 4::bigint,
        'the uploader sees all of their own uploads, sent or not');

    -- Regression: this query used to fail with "permission denied for table messages" because the
    -- policy read messages.suppressed_at, a column clients cannot select.
    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows(format('select 1 from public.message_attachments where id = %L', v_sent)), 1::bigint,
        'a conversation member sees a file that was sent');
    perform tests.assert_eq(tests.count_rows(format('select 1 from public.message_attachments where id = %L', v_unsent)), 0::bigint,
        'a conversation member does not see an unsent upload');
    perform tests.assert_eq(tests.count_rows('select 1 from public.message_attachments'), 1::bigint,
        'a member sees only the file on a visible message');
    perform tests.assert_eq(tests.count_rows(format('select 1 from public.message_attachments where id = %L',
                                                    (select id from fx where name = 'att_hidden'))), 0::bigint,
        'a file on a message the member hid with "delete for me" is hidden too');
    perform tests.assert_eq(tests.count_rows(format('select 1 from public.message_attachments where id = %L',
                                                    (select id from fx where name = 'att_suppressed'))), 0::bigint,
        'a file on a suppressed (blocked sender) message is not shown to the recipient');
    perform tests.assert_error('select suppressed_at from public.messages', '42501',
        'the suppressed flag stays unreadable for clients, so recipients cannot learn they were blocked');

    perform tests.as_user(tests.uid(5));
    perform tests.assert_eq(tests.count_rows('select 1 from public.message_attachments'), 0::bigint,
        'an outsider sees no attachments at all');
    perform tests.reset_role();
end
$$;

-- message_attachments: clients can never read the storage path or write rows -----------------------------------------------
do $$
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_error('select storage_path from public.message_attachments', '42501',
        'storage_path is not readable by clients, even by the uploader');
    perform tests.assert_error(
        format('insert into public.message_attachments (conversation_id, uploader_id, storage_path, file_name, content_type, size_bytes) values (%L, %L, ''rls/x.png'', ''x.png'', ''image/png'', 1)',
               (select id from fx where name = 'conv'), tests.uid(1)),
        '42501', 'clients cannot insert attachments (the backend inspects content first)');
    perform tests.assert_error('update public.message_attachments set file_name = ''renamed''', '42501',
        'clients cannot update attachments');
    perform tests.assert_error('delete from public.message_attachments', '42501',
        'clients cannot delete attachments');

    perform tests.as_user(tests.uid(5));
    perform tests.assert_error(
        format('insert into public.message_attachments (conversation_id, uploader_id, storage_path, file_name, content_type, size_bytes) values (%L, %L, ''rls/e.png'', ''e.png'', ''image/png'', 1)',
               (select id from fx where name = 'conv'), tests.uid(5)),
        '42501', 'an outsider cannot attach a file to someone else''s conversation');

    perform tests.as_anon();
    perform tests.assert_error('select 1 from public.message_attachments', '42501', 'anon cannot read attachments');
    perform tests.reset_role();
end
$$;

-- message_attachments: the type and size rules hold even for the backend (service role) ---------------------------------
do $$
begin
    perform tests.assert_error(
        format('insert into public.message_attachments (conversation_id, uploader_id, storage_path, file_name, content_type, size_bytes) values (%L, %L, ''rls/bad.exe'', ''bad.exe'', ''application/x-msdownload'', 10)',
               (select id from fx where name = 'conv'), tests.uid(1)),
        '23514', 'an executable content type is refused by the database');
    perform tests.assert_error(
        format('insert into public.message_attachments (conversation_id, uploader_id, storage_path, file_name, content_type, size_bytes) values (%L, %L, ''rls/big.png'', ''big.png'', ''image/png'', 10485761)',
               (select id from fx where name = 'conv'), tests.uid(1)),
        '23514', 'a file over 10 MB is refused by the database');
    perform tests.assert_error(
        format('insert into public.message_attachments (conversation_id, uploader_id, storage_path, file_name, content_type, size_bytes) values (%L, %L, ''rls/zero.png'', ''zero.png'', ''image/png'', 0)',
               (select id from fx where name = 'conv'), tests.uid(1)),
        '23514', 'an empty file is refused by the database');
end
$$;

-- contact_group_members --------------------------------------------------------------------------------------------------------
do $$
declare
    v_group uuid := (select id from fx where name = 'group');
    v_contact uuid := (select id from fx where name = 'contact');
    v_rows bigint;
begin
    perform tests.as_user(tests.uid(1));
    perform tests.assert_eq(tests.count_rows('select 1 from public.contact_group_members'), 1::bigint,
        'the owner sees their own group membership');

    perform tests.as_user(tests.uid(2));
    perform tests.assert_eq(tests.count_rows('select 1 from public.contact_group_members'), 0::bigint,
        'another user, even a contact, does not see the owner''s group members');
    perform tests.assert_error(
        format('insert into public.contact_group_members (group_id, contact_id, owner_id) values (%L, %L, %L)', v_group, v_contact, tests.uid(1)),
        '42501', 'another user cannot add members to someone else''s group');
    perform tests.assert_error(
        format('insert into public.contact_group_members (group_id, contact_id, owner_id) values (%L, %L, %L)', v_group, v_contact, tests.uid(2)),
        null, 'another user cannot claim ownership of a membership in someone else''s group');

    update public.contact_group_members set position = 99;
    get diagnostics v_rows = row_count;
    perform tests.assert_eq(v_rows, 0::bigint, 'another user updates no rows');
    delete from public.contact_group_members;
    get diagnostics v_rows = row_count;
    perform tests.assert_eq(v_rows, 0::bigint, 'another user deletes no rows');

    perform tests.as_user(tests.uid(5));
    perform tests.assert_eq(tests.count_rows('select 1 from public.contact_group_members'), 0::bigint,
        'an outsider sees no group members');

    perform tests.as_anon();
    perform tests.assert_error('select 1 from public.contact_group_members', '42501', 'anon cannot read group members');

    perform tests.as_user(tests.uid(1));
    update public.contact_group_members set position = 3;
    get diagnostics v_rows = row_count;
    perform tests.assert_eq(v_rows, 1::bigint, 'the owner can reorder their own members');
    delete from public.contact_group_members;
    get diagnostics v_rows = row_count;
    perform tests.assert_eq(v_rows, 1::bigint, 'the owner can remove their own members');
    perform tests.reset_role();
end
$$;

rollback;
