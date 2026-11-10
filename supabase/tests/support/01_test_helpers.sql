-- Test support: assertion and role-switching helpers for the plain-SQL database tests.
-- Run once after the migrations on a TEST database. Each test file wraps its work in a
-- transaction and rolls it back, so tests do not leak data into each other.

create schema if not exists tests;
grant usage on schema tests to public;

create or replace function tests.fail(p_message text)
returns void
language plpgsql
as $$
begin
    raise exception 'TEST FAILED: %', p_message using errcode = 'P0001';
end;
$$;

create or replace function tests.assert_true(p_condition boolean, p_message text)
returns void
language plpgsql
as $$
begin
    if p_condition is not true then
        raise exception 'TEST FAILED: %', p_message using errcode = 'P0001';
    end if;
end;
$$;

create or replace function tests.assert_eq(p_actual anyelement, p_expected anyelement, p_message text)
returns void
language plpgsql
as $$
begin
    if p_actual is distinct from p_expected then
        raise exception 'TEST FAILED: % (expected %, got %)', p_message, p_expected, p_actual using errcode = 'P0001';
    end if;
end;
$$;

-- Runs a statement and requires it to fail. p_sqlstate may be null to accept any error.
-- The statement runs in a sub-transaction, so its failure does not abort the test.
create or replace function tests.assert_error(p_sql text, p_sqlstate text, p_message text)
returns void
language plpgsql
as $$
declare
    v_state text;
begin
    begin
        execute p_sql;
    exception when others then
        get stacked diagnostics v_state = returned_sqlstate;
        if p_sqlstate is not null and v_state <> p_sqlstate then
            raise exception 'TEST FAILED: % (expected SQLSTATE %, got % - %)', p_message, p_sqlstate, v_state, sqlerrm
                using errcode = 'P0001';
        end if;
        return;
    end;
    raise exception 'TEST FAILED: % (statement succeeded but should have failed)', p_message using errcode = 'P0001';
end;
$$;

-- Runs a statement and requires it to succeed.
create or replace function tests.assert_ok(p_sql text, p_message text)
returns void
language plpgsql
as $$
begin
    execute p_sql;
exception when others then
    raise exception 'TEST FAILED: % (unexpected error % - %)', p_message, sqlstate, sqlerrm using errcode = 'P0001';
end;
$$;

-- Counts the rows a query returns under the current role.
create or replace function tests.count_rows(p_sql text)
returns bigint
language plpgsql
as $$
declare
    v_count bigint;
begin
    execute format('select count(*) from (%s) q', p_sql) into v_count;
    return v_count;
end;
$$;

-- Role helpers. They mimic what PostgREST does for a request with a verified JWT.
create or replace function tests.as_user(p_user_id uuid)
returns void
language plpgsql
as $$
begin
    perform set_config('request.jwt.claims',
        json_build_object('sub', p_user_id, 'role', 'authenticated')::text, true);
    perform set_config('request.jwt.claim.sub', p_user_id::text, true);
    execute 'set local role authenticated';
end;
$$;

create or replace function tests.as_anon()
returns void
language plpgsql
as $$
begin
    perform set_config('request.jwt.claims', '', true);
    perform set_config('request.jwt.claim.sub', '', true);
    execute 'set local role anon';
end;
$$;

create or replace function tests.as_service()
returns void
language plpgsql
as $$
begin
    execute 'set local role service_role';
end;
$$;

create or replace function tests.reset_role()
returns void
language plpgsql
as $$
begin
    execute 'reset role';
end;
$$;

-- Creates an auth user (the trigger creates the profile) and optionally activates it.
create or replace function tests.create_user(
    p_id uuid, p_username text, p_status text default 'active', p_role text default 'user')
returns uuid
language plpgsql
as $$
begin
    insert into auth.users (id, email, raw_user_meta_data)
    values (p_id, p_username || '@chikka.test', jsonb_build_object('display_name', initcap(p_username) || ' Test'));

    update public.profiles
       set username = p_username,
           status = p_status,
           suspended_at = case when p_status = 'suspended' then now() end,
           deleted_at = case when p_status = 'deleted' then now() end,
           role = p_role
     where id = p_id;
    return p_id;
end;
$$;

-- Fixed identities used across the test files.
create or replace function tests.uid(p_n int)
returns uuid
language sql
immutable
as $$
    select ('00000000-0000-4000-8000-' || lpad(p_n::text, 12, '0'))::uuid;
$$;

-- Helpers must be callable while a test is running under the anon or authenticated role.
grant execute on all functions in schema tests to public;
