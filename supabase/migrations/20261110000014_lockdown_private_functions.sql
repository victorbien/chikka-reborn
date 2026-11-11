-- Migration: 20261110000014_lockdown_private_functions
-- Phase: 1
-- Description: Explicit, reviewable EXECUTE grants for every function in the private schema.
--              Defence in depth on top of the default-privileges change in the foundation migration.
-- Dependencies: all earlier migrations
-- Rollback: forward-fix only.
--
-- Rule: private functions are callable by nobody unless listed here.
--   authenticated: only helpers that RLS policies or CHECK constraints evaluate on the user's behalf
--   service_role : the backend

begin;

revoke all on all functions in schema private from public, anon, authenticated;

-- Needed by clients because policies and CHECK constraints run under the caller's privileges.
grant execute on function private.is_admin() to authenticated, service_role;
grant execute on function private.valid_notification_overrides(jsonb) to authenticated, service_role;

-- Backend only.
grant execute on function private.contains_unmasked_phone(text) to service_role;
grant execute on function private.mask_phone(text) to service_role;
grant execute on function private.has_active_consent(uuid, text, public.e164) to service_role;
grant execute on function private.is_blocked_between(uuid, uuid) to service_role;
grant execute on function private.accept_contact_request(uuid, uuid) to service_role;
grant execute on function private.get_or_create_chikka_conversation(uuid, uuid) to service_role;
grant execute on function private.get_or_create_sms_conversation(uuid, public.e164) to service_role;

-- Trigger functions (set_updated_at, reject_mutation, enforce_*, assign_message_seq, protect_*,
-- sync_*, apply_credit_transaction, bootstrap_profile_data, handle_new_auth_user) are deliberately
-- not granted: triggers run them without the caller needing EXECUTE.

commit;
