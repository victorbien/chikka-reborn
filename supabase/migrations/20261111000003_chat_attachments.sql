-- Migration: 20261111000003_chat_attachments
-- Phase: 1
-- Description: message attachments for Chikka conversations (FR-MSG-010), attachment-only
--              messages, and the private Storage bucket that holds the files.
-- Dependencies: 20261110000006_conversations, 20261110000007_messages
-- Rollback: forward-fix only.

begin;

-- A message may now carry files with no text. attachment_count is maintained by the backend
-- in the same transaction that links the files, so the check below can rely on it.
alter table public.messages
    add column attachment_count smallint not null default 0,
    add constraint ck_messages_attachment_count check (attachment_count between 0 and 5),
    add constraint ck_messages_attachment_chikka check (attachment_count = 0 or channel = 'chikka');

alter table public.messages drop constraint ck_messages_body_presence;
alter table public.messages add constraint ck_messages_body_presence check (
    (deleted_for_everyone_at is null
        and ((body is not null and char_length(body) >= 1) or attachment_count > 0))
    or (deleted_for_everyone_at is not null and body is null));

grant select (attachment_count) on table public.messages to authenticated;

-- message_attachments: one row per uploaded file. A file is uploaded first (message_id null,
-- visible only to the uploader), then linked when the message is sent.
create table public.message_attachments (
    id              uuid primary key default gen_random_uuid(),
    conversation_id uuid not null constraint fk_message_attachments_conversation references public.conversations (id) on delete cascade,
    uploader_id     uuid not null constraint fk_message_attachments_uploader references public.profiles (id) on delete cascade,
    message_id      uuid constraint fk_message_attachments_message references public.messages (id) on delete cascade,
    storage_path    text not null,
    file_name       text not null,
    content_type    text not null,
    size_bytes      integer not null,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    constraint uq_message_attachments_path unique (storage_path),
    constraint ck_message_attachments_name check (char_length(file_name) between 1 and 255),
    constraint ck_message_attachments_type check (content_type in
        ('image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf')),
    constraint ck_message_attachments_size check (size_bytes between 1 and 10485760)
);

comment on table public.message_attachments is
    'Files shared in chikka conversations. The type is detected from the file content by the backend, never trusted from the client. Unlinked rows (message_id null) are uploads not yet sent.';

create index idx_message_attachments_message on public.message_attachments (message_id) where message_id is not null;
create index idx_message_attachments_unlinked on public.message_attachments (uploader_id, created_at) where message_id is null;
create index idx_message_attachments_conversation on public.message_attachments (conversation_id);

create trigger trg_message_attachments_updated_at
    before update on public.message_attachments
    for each row execute function private.set_updated_at();

alter table public.message_attachments enable row level security;
revoke all on table public.message_attachments from public, anon, authenticated;
-- storage_path is not granted: clients only ever get short-lived signed URLs from the backend.
grant select (id, conversation_id, uploader_id, message_id, file_name, content_type, size_bytes, created_at)
    on table public.message_attachments to authenticated;
grant all on table public.message_attachments to service_role;

-- Members see files of sent messages they can see; uploaders also see their unsent uploads.
-- Writes are backend-only (content inspection, size limits, linking).
create policy message_attachments_select_member on public.message_attachments
    for select to authenticated
    using (
        uploader_id = (select auth.uid())
        or (message_id is not null and exists (
            select 1 from public.messages m
            join public.conversation_members cm
              on cm.conversation_id = m.conversation_id
             and cm.user_id = (select auth.uid())
             and cm.left_at is null
            where m.id = message_attachments.message_id
              and m.seq > cm.cleared_before_seq
              and (m.suppressed_at is null or m.sender_user_id = (select auth.uid()))
              and m.deleted_for_everyone_at is null))
    );

-- Private bucket. No storage.objects policy exists for clients, so only the backend (service
-- role) reads and writes, and members download through short-lived signed URLs.
do $$
begin
    if to_regclass('storage.buckets') is not null then
        insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        values ('message-attachments', 'message-attachments', false, 10485760,
                array['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf'])
        on conflict (id) do update
            set public = false,
                file_size_limit = excluded.file_size_limit,
                allowed_mime_types = excluded.allowed_mime_types;
    end if;
end
$$;

commit;
