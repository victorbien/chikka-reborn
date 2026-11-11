-- Migration: 20261110000001_foundation
-- Phase: 1
-- Description: Shared schema objects used by every later migration: the private
--              schema, the E.164 domain, and generic trigger functions.
-- Dependencies: Supabase roles (anon, authenticated, service_role)
-- Rollback: forward-fix only. Dropping this schema is destructive and needs approval.

begin;

-- Helper functions live in a schema that PostgREST does not expose.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated, service_role;

-- PostgreSQL grants EXECUTE on new functions to PUBLIC by default, and a schema-scoped
-- "ALTER DEFAULT PRIVILEGES IN SCHEMA ... REVOKE" cannot remove that built-in default.
-- Revoke it for functions created by the migration role, so every function is private
-- until a migration grants it explicitly. The lockdown migration re-checks this at the end.
do $$
begin
    execute format('alter default privileges for role %I revoke execute on functions from public', current_user);
end
$$;

-- Phone numbers are always stored in E.164 form.
create domain public.e164 as text
    constraint ck_e164_format check (value ~ '^\+[1-9][0-9]{6,14}$');

-- Maintains updated_at on mutable tables.
create function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

-- Blocks UPDATE and DELETE on append-only tables (ledgers, consents, events).
create function private.reject_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    raise exception '% is append-only: % is not allowed', tg_table_name, tg_op
        using errcode = '55000';
end;
$$;

-- True when text contains something that looks like an unmasked phone number.
-- Used by audit_logs checks so raw numbers never reach the audit trail.
create function private.contains_unmasked_phone(value text)
returns boolean
language sql
immutable
set search_path = ''
as $$
    select coalesce(value ~ '\+[0-9]{7,15}', false);
$$;

-- Masks a phone number for logs and audit metadata: +63****1234.
create function private.mask_phone(value text)
returns text
language sql
immutable
set search_path = ''
as $$
    select case
        when value is null then null
        when char_length(value) < 8 then '****'
        else left(value, 3) || '****' || right(value, 4)
    end;
$$;

commit;
