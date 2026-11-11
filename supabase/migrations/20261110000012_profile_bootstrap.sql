-- Migration: 20261110000012_profile_bootstrap
-- Phase: 1
-- Description: Creates per-user rows when a profile is created: credit balances, the one-time
--              demo grant, and default notification preferences.
-- Dependencies: 20261110000003 (system_settings), 20261110000009 (credits), 20261110000010 (notifications)
-- Rollback: forward-fix only.

begin;

create function private.bootstrap_profile_data()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_grant bigint;
begin
    insert into public.messaging_credits (user_id, ledger_type)
    values (new.id, 'live'), (new.id, 'demo')
    on conflict do nothing;

    insert into public.notification_preferences (user_id)
    values (new.id)
    on conflict do nothing;

    -- One-time demo grant (FR-CREDIT-006). Amount is an admin setting in units (credits x 100).
    select (value #>> '{}')::bigint into v_grant
    from public.system_settings where key = 'demo_grant_units';
    v_grant := coalesce(v_grant, 5000);

    if v_grant > 0 then
        insert into public.credit_transactions (user_id, ledger_type, entry_type, balance_delta, reason)
        values (new.id, 'demo', 'grant', v_grant, 'Initial demo credits');
    end if;

    return new;
end;
$$;

create trigger trg_profiles_bootstrap
    after insert on public.profiles
    for each row execute function private.bootstrap_profile_data();

commit;
