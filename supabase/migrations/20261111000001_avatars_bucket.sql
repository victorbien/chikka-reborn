-- Migration: 20261111000001_avatars_bucket
-- Phase: 1
-- Description: Private Supabase Storage bucket for profile photos (FR-AUTH-011).
-- Dependencies: Supabase Storage (skipped on a plain PostgreSQL test database)
-- Rollback: forward-fix only.
--
-- Access model: the bucket is private and no storage.objects policy is created for
-- anon or authenticated, so the default RLS denial applies to every client. Only the
-- backend (service role) validates, re-encodes and writes objects under "<user_id>/",
-- and serves them through short-lived signed URLs. The backend re-encodes every upload
-- to WebP, so the bucket accepts nothing else.

begin;

do $$
begin
    if to_regclass('storage.buckets') is not null then
        insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        values ('avatars', 'avatars', false, 524288, array['image/webp'])
        on conflict (id) do update
            set public = false,
                file_size_limit = excluded.file_size_limit,
                allowed_mime_types = excluded.allowed_mime_types;
    end if;
end
$$;

commit;
