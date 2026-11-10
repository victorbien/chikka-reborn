-- Test file 03: credit balances and the append-only ledger.
-- Units are credits x 100. A new user receives 5000 demo units (50 credits).
begin;

select tests.create_user(tests.uid(1), 'alice');
select tests.create_user(tests.uid(2), 'bob');

-- Helper (rolled back with the test): creates a simulated SMS message and returns its id.
create function tests.make_sms(p_user uuid, p_remote text, p_simulated boolean default true)
returns uuid
language plpgsql
as $$
declare
    v_conv uuid := private.get_or_create_sms_conversation(p_user, p_remote::public.e164);
    v_cap uuid := (select id from public.sms_country_capabilities where country_code = 'US' and is_current);
    v_id uuid;
begin
    insert into public.messages (conversation_id, channel, direction, sender_user_id, body, encoding, char_count,
                                 segment_count, status, idempotency_key, is_simulated, capability_id)
    values (v_conv, 'sms', 'outbound', p_user, 'credit test', 'gsm7', 11, 1, 'queued', gen_random_uuid(), p_simulated, v_cap)
    returning id into v_id;
    return v_id;
end;
$$;

-- Reserve, capture and refund ------------------------------------------------------------------
do $$
declare
    v_msg uuid := tests.make_sms(tests.uid(1), '+15550100101');
begin
    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
    values (tests.uid(1), 'demo', 'reservation', 0, 100, v_msg);
    perform tests.assert_eq((select reserved_units from public.messaging_credits where user_id = tests.uid(1) and ledger_type = 'demo'),
        100::bigint, 'reservation increases reserved units');
    perform tests.assert_eq((select balance_units from public.messaging_credits where user_id = tests.uid(1) and ledger_type = 'demo'),
        5000::bigint, 'reservation does not change the balance');

    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'demo', 'reservation', 0, 100, %L)$q$, tests.uid(1), v_msg), '23505',
        'a message can only be reserved once');

    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
    values (tests.uid(1), 'demo', 'deduction', -100, -100, v_msg);
    perform tests.assert_eq((select balance_units from public.messaging_credits where user_id = tests.uid(1) and ledger_type = 'demo'),
        4900::bigint, 'deduction lowers the balance');
    perform tests.assert_eq((select reserved_units from public.messaging_credits where user_id = tests.uid(1) and ledger_type = 'demo'),
        0::bigint, 'deduction consumes the reservation');
    perform tests.assert_eq((select balance_after from public.credit_transactions where message_id = v_msg and entry_type = 'deduction'),
        4900::bigint, 'ledger rows record the balance after');

    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, message_id)
    values (tests.uid(1), 'demo', 'refund', 100, v_msg);
    perform tests.assert_eq((select balance_units from public.messaging_credits where user_id = tests.uid(1) and ledger_type = 'demo'),
        5000::bigint, 'refund restores the balance');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, message_id)
        values (%L, 'demo', 'refund', 100, %L)$q$, tests.uid(1), v_msg), '23505', 'a message is refunded exactly once');
end
$$;

-- Overdraw protection ------------------------------------------------------------------------------
do $$
declare
    v_m1 uuid := tests.make_sms(tests.uid(2), '+15550100201');
    v_m2 uuid := tests.make_sms(tests.uid(2), '+15550100202');
    v_m3 uuid := tests.make_sms(tests.uid(2), '+15550100203');
    v_real uuid := tests.make_sms(tests.uid(2), '+15550100204', false);
begin
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'live', 'reservation', 0, 100, %L)$q$, tests.uid(2), v_real), 'P0001',
        'the live ledger starts empty, so reserving credits fails');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'demo', 'reservation', 0, 5001, %L)$q$, tests.uid(2), v_m1), 'P0001',
        'cannot reserve more than the available balance');

    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
    values (tests.uid(2), 'demo', 'reservation', 0, 4000, v_m1);
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'demo', 'reservation', 0, 1500, %L)$q$, tests.uid(2), v_m2), 'P0001',
        'reserved credits are not available for another message');
    perform tests.assert_ok(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'demo', 'reservation', 0, 1000, %L)$q$, tests.uid(2), v_m2), 'the remaining available balance can still be reserved');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'demo', 'reservation_release', 0, -5, %L)$q$, tests.uid(2), v_m3), '55000',
        'cannot release a reservation that was never made');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'demo', 'deduction', -6000, 0, %L)$q$, tests.uid(2), v_m3), 'P0001',
        'a deduction cannot take the balance below zero');
    perform tests.assert_eq((select balance_units from public.messaging_credits where user_id = tests.uid(2) and ledger_type = 'demo'),
        5000::bigint, 'failed entries leave the balance untouched');

    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
    values (tests.uid(2), 'demo', 'reservation_release', 0, -4000, v_m1);
    perform tests.assert_eq((select reserved_units from public.messaging_credits where user_id = tests.uid(2) and ledger_type = 'demo'),
        1000::bigint, 'release returns reserved credits to the available balance');
end
$$;

-- Entry rules ------------------------------------------------------------------------------------------
do $$
declare
    v_msg uuid := tests.make_sms(tests.uid(1), '+15550100301');
begin
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, external_reference)
        values (%L, 'demo', 'top_up', 500, 'pay-1')$q$, tests.uid(1)), '23514', 'demo credits cannot be bought');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'demo', 'deduction', 100, 0, %L)$q$, tests.uid(1), v_msg), '23514', 'a deduction must be negative');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta)
        values (%L, 'demo', 'refund', 100)$q$, tests.uid(1)), '23514', 'a refund must reference a message');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta)
        values (%L, 'demo', 'adjustment', 100)$q$, tests.uid(1)), '23514', 'an adjustment needs a reason and an actor');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reason, actor_id)
        values (%L, 'demo', 'adjustment', -999999, 'correction', %L)$q$, tests.uid(1), tests.uid(2)), 'P0001',
        'an adjustment cannot make the balance negative');
    perform tests.assert_ok(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reason, actor_id)
        values (%L, 'demo', 'adjustment', 250, 'goodwill credit', %L)$q$, tests.uid(1), tests.uid(2)), 'a documented adjustment is accepted');

    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, external_reference)
    values (tests.uid(1), 'live', 'top_up', 1000, 'gateway-event-1');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, external_reference)
        values (%L, 'live', 'top_up', 1000, 'gateway-event-1')$q$, tests.uid(1)), '23505',
        'a payment event applies only once');
    perform tests.assert_eq((select balance_units from public.messaging_credits where user_id = tests.uid(1) and ledger_type = 'live'),
        1000::bigint, 'live and demo ledgers are separate');
end
$$;

-- Simulation never touches real credits -----------------------------------------------------------------
do $$
declare
    v_sim uuid := tests.make_sms(tests.uid(1), '+15550100401', true);
    v_real uuid := tests.make_sms(tests.uid(1), '+15550100402', false);
    v_before bigint;
begin
    insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, external_reference)
    values (tests.uid(1), 'live', 'top_up', 5000, 'gateway-event-2');
    select balance_units into v_before from public.messaging_credits where user_id = tests.uid(1) and ledger_type = 'live';

    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'live', 'reservation', 0, 100, %L)$q$, tests.uid(1), v_sim), '23514',
        'a simulated message cannot reserve live credits');
    perform tests.assert_error(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'demo', 'reservation', 0, 100, %L)$q$, tests.uid(1), v_real), '23514',
        'a real message cannot be paid with demo credits');
    perform tests.assert_ok(format($q$insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reserved_delta, message_id)
        values (%L, 'live', 'reservation', 0, 100, %L)$q$, tests.uid(1), v_real), 'a real message can reserve live credits');
    perform tests.assert_eq((select balance_units from public.messaging_credits where user_id = tests.uid(1) and ledger_type = 'live'),
        v_before, 'the live balance is untouched by simulated attempts');
end
$$;

-- Immutability and consistency --------------------------------------------------------------------------
do $$
begin
    perform tests.assert_error($q$update public.credit_transactions set balance_delta = 0$q$, '55000', 'the ledger cannot be edited');
    perform tests.assert_error($q$delete from public.credit_transactions$q$, '55000', 'the ledger cannot be deleted');

    -- Direct balance edits by clients are blocked at the privilege level (see the RLS tests).
    perform tests.assert_eq(
        (select count(*) from public.messaging_credits mc
          where balance_units <> (select coalesce(sum(balance_delta), 0) from public.credit_transactions t
                                   where t.user_id = mc.user_id and t.ledger_type = mc.ledger_type)), 0::bigint,
        'balance always equals the sum of the ledger');
    perform tests.assert_eq(
        (select count(*) from public.messaging_credits mc
          where reserved_units <> (select coalesce(sum(reserved_delta), 0) from public.credit_transactions t
                                    where t.user_id = mc.user_id and t.ledger_type = mc.ledger_type)), 0::bigint,
        'reserved always equals the sum of reservation movements');
end
$$;

rollback;
