-- Migration: 20261120000001_profiles_avatar_path_guard
-- Phase: 1 (security audit finding SEC-001)
-- Description: profiles.avatar_path was writable by any signed-in client and unconstrained, but
--              the backend turns it into a Storage path when it signs avatar URLs. A crafted
--              value could point at another user's avatar or, with "..", at another bucket.
--              Restrict the value to the owner's own folder and make the column backend-only.
-- Dependencies: 20261110000002_profiles
-- Rollback: forward-fix only (re-granting the column would reopen the finding).
--
-- Existing rows are not rewritten. The constraint is NOT VALID, so it applies to every new or
-- changed row. Operators should find legacy violations, null them, and then validate:
--   select id from public.profiles
--    where avatar_path is not null and avatar_path !~ ('^' || id::text || '/[0-9a-f]{32}\.webp$');
--   alter table public.profiles validate constraint ck_profiles_avatar_path;

begin;

-- Clients no longer write the column directly. The backend validates and re-encodes every
-- photo, uploads it to "<user_id>/<32 hex>.webp" and then records the path.
revoke update (avatar_path) on table public.profiles from authenticated;

alter table public.profiles
    add constraint ck_profiles_avatar_path
    check (avatar_path is null or avatar_path ~ ('^' || id::text || '/[0-9a-f]{32}\.webp$'))
    not valid;

comment on column public.profiles.avatar_path is
    'Storage object path "<id>/<32 hex>.webp" in the private avatars bucket. Backend-only writes.';

commit;
