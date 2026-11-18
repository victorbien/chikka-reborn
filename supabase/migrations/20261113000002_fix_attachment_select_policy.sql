-- Migration: 20261113000002_fix_attachment_select_policy
-- Phase: 1
-- Description: A conversation member could not read the attachments of a sent message. The policy
--              message_attachments_select_member looked at messages.suppressed_at in a sub-query, but that
--              column is deliberately not granted to authenticated (recipients must not learn that a
--              sender was blocked). Postgres checks column grants on a sub-query's table, so the query
--              failed with "permission denied for table messages". The backend uses a privileged role and
--              never hit this, but the policy is the last line of defence for direct (PostgREST/Realtime)
--              access, and it has to work. The check now runs in a security-definer helper, as is_admin()
--              does. It also honours "delete for me" (message_hides) like the messages policy does.
-- Dependencies: 20261111000003_chat_attachments, 20261110000007_messages
-- Rollback: forward-fix only (restore the previous policy text from 20261111000003).
begin;

create function private.can_see_attachment_message(p_message_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.messages m
        join public.conversation_members cm
          on cm.conversation_id = m.conversation_id
         and cm.user_id = auth.uid()
         and cm.left_at is null
        where m.id = p_message_id
          and m.seq > cm.cleared_before_seq
          and (m.suppressed_at is null or m.sender_user_id = auth.uid())
          and m.deleted_for_everyone_at is null
          and not exists (
              select 1 from public.message_hides h
              where h.message_id = m.id and h.user_id = auth.uid())
    );
$$;

comment on function private.can_see_attachment_message(uuid) is
    'True when the calling user may see the message an attachment belongs to. Security definer because it reads messages.suppressed_at, which clients cannot select.';

revoke all on function private.can_see_attachment_message(uuid) from public, anon, authenticated;
grant execute on function private.can_see_attachment_message(uuid) to authenticated, service_role;

drop policy message_attachments_select_member on public.message_attachments;

create policy message_attachments_select_member on public.message_attachments
    for select to authenticated
    using (
        uploader_id = (select auth.uid())
        or (message_id is not null and private.can_see_attachment_message(message_id))
    );

commit;
