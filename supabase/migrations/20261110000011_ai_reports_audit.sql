-- Migration: 20261110000011_ai_reports_audit
-- Phase: 3 (AI), 1 (reports), 1 (audit)
-- Description: ai_assistance_logs, abuse_reports, audit_logs, messages -> AI log foreign key.
-- Dependencies: 20261110000007_messages
-- Rollback: forward-fix only.

begin;

-- ai_assistance_logs: one row per AI request (FR-AI-011).
-- Metadata is always stored. Content (input_text/output_text) is stored only when the user turned
-- on AI history, and expires after 30 days. This replaces the earlier ai_usage_logs and ai_suggestions proposals:
-- usage metrics and the user-visible history are the same facts.
create table public.ai_assistance_logs (
    id                  uuid primary key default gen_random_uuid(),
    user_id             uuid not null constraint fk_ai_logs_user references public.profiles (id) on delete cascade,
    conversation_id     uuid constraint fk_ai_logs_conversation references public.conversations (id) on delete set null,
    feature             text not null,
    model_id            text not null,
    prompt_version      text,
    language            text,
    outcome             text not null,
    user_decision       text not null default 'pending',
    accepted_message_id uuid constraint fk_ai_logs_message references public.messages (id) on delete set null,
    meaning_preserved   boolean,
    input_tokens        integer,
    output_tokens       integer,
    latency_ms          integer,
    error_code          text,
    output_hash         text,
    input_text          text,
    output_text         text,
    content_expires_at  timestamptz,
    created_at          timestamptz not null default now(),

    constraint ck_ai_logs_feature check (feature in
        ('suggest_replies', 'translate', 'rewrite', 'tone_adjust', 'summarise', 'compose', 'optimise_sms')),
    constraint ck_ai_logs_outcome check (outcome in
        ('success', 'invalid_output', 'timeout', 'throttled', 'unavailable', 'blocked')),
    constraint ck_ai_logs_decision check (user_decision in ('pending', 'accepted', 'edited', 'dismissed')),
    constraint ck_ai_logs_tokens check (
        (input_tokens is null or input_tokens >= 0) and (output_tokens is null or output_tokens >= 0)
        and (latency_ms is null or latency_ms >= 0)),
    -- Stored content must always have an expiry (30 days by default, set by the backend).
    constraint ck_ai_logs_content_expiry check (
        (input_text is null and output_text is null) or content_expires_at is not null),
    constraint ck_ai_logs_input_length check (input_text is null or char_length(input_text) <= 4000),
    constraint ck_ai_logs_output_length check (output_text is null or char_length(output_text) <= 4000)
);

comment on table public.ai_assistance_logs is
    'AI request metadata plus optional user-history content. Administrators have no policy on this table: they see aggregates computed by the backend, never content (FR-AI-011).';

create index idx_ai_logs_user on public.ai_assistance_logs (user_id, created_at desc);
create index idx_ai_logs_feature on public.ai_assistance_logs (feature, created_at desc);
create index idx_ai_logs_outcome on public.ai_assistance_logs (outcome, created_at desc);
create index idx_ai_logs_content_expiry on public.ai_assistance_logs (content_expires_at)
    where content_expires_at is not null;

alter table public.messages
    add constraint fk_messages_ai_log
    foreign key (ai_assistance_log_id) references public.ai_assistance_logs (id) on delete set null;

alter table public.ai_assistance_logs enable row level security;
revoke all on table public.ai_assistance_logs from public, anon, authenticated;
grant select, delete on table public.ai_assistance_logs to authenticated;
grant all on table public.ai_assistance_logs to service_role;

create policy ai_logs_select_own on public.ai_assistance_logs
    for select to authenticated using (user_id = (select auth.uid()));
-- Users can delete single entries or clear all of their own history.
create policy ai_logs_delete_own on public.ai_assistance_logs
    for delete to authenticated using (user_id = (select auth.uid()));

-- abuse_reports (FR-PRIVACY-004, FR-ADMIN-011).
create table public.abuse_reports (
    id                  uuid primary key default gen_random_uuid(),
    reporter_id         uuid not null constraint fk_reports_reporter references public.profiles (id) on delete restrict,
    reported_user_id    uuid constraint fk_reports_reported references public.profiles (id) on delete restrict,
    reported_phone      public.e164,
    message_id          uuid constraint fk_reports_message references public.messages (id) on delete set null,
    conversation_id     uuid constraint fk_reports_conversation references public.conversations (id) on delete set null,
    reason              text not null,
    note                text,
    snapshot            jsonb not null,
    status              text not null default 'open',
    resolution_note     text,
    resolved_by         uuid constraint fk_reports_resolver references public.profiles (id) on delete set null,
    resolved_at         timestamptz,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),

    constraint ck_reports_reason check (reason in ('spam', 'harassment', 'scam', 'illegal_content', 'other')),
    constraint ck_reports_note check (note is null or char_length(note) <= 500),
    constraint ck_reports_snapshot check (jsonb_typeof(snapshot) = 'object'),
    constraint ck_reports_status check (status in ('open', 'reviewing', 'actioned', 'dismissed')),
    constraint ck_reports_target check (reported_user_id is not null or reported_phone is not null),
    constraint ck_reports_not_self check (reporter_id <> reported_user_id),
    constraint ck_reports_resolution check (
        status in ('open', 'reviewing')
        or (resolution_note is not null and char_length(btrim(resolution_note)) > 0
            and resolved_by is not null and resolved_at is not null))
);

comment on table public.abuse_reports is
    'snapshot holds the reported message and up to 5 messages of context, so evidence survives later deletion or edits. Reports on one message are grouped by message_id in the admin view; a reporter can report a message once.';

create unique index uq_reports_reporter_message on public.abuse_reports (reporter_id, message_id) where message_id is not null;
create index idx_reports_queue on public.abuse_reports (status, created_at) where status in ('open', 'reviewing');
create index idx_reports_message on public.abuse_reports (message_id) where message_id is not null;
create index idx_reports_reporter_day on public.abuse_reports (reporter_id, created_at desc);
create index idx_reports_reported_user on public.abuse_reports (reported_user_id) where reported_user_id is not null;

create trigger trg_reports_updated_at
    before update on public.abuse_reports
    for each row execute function private.set_updated_at();

alter table public.abuse_reports enable row level security;
revoke all on table public.abuse_reports from public, anon, authenticated;
grant select on table public.abuse_reports to authenticated;
grant update (status, resolution_note, resolved_by, resolved_at) on table public.abuse_reports to authenticated;
grant all on table public.abuse_reports to service_role;

-- Reporters see their own reports. The reported user never does.
create policy reports_select_reporter on public.abuse_reports
    for select to authenticated using (reporter_id = (select auth.uid()));
create policy reports_select_admin on public.abuse_reports
    for select to authenticated using ((select private.is_admin()));
-- Admins may move a report through its workflow; they cannot edit evidence or ownership.
create policy reports_update_admin on public.abuse_reports
    for update to authenticated
    using ((select private.is_admin()))
    with check ((select private.is_admin()));
-- Filing a report is backend-only (builds the snapshot, merges duplicates, applies the daily limit).

-- audit_logs: immutable audit trail (CC-03, FR-ADMIN-012, FR-PRIVACY-010).
create table public.audit_logs (
    id              uuid primary key default gen_random_uuid(),
    category        text not null,
    action          text not null,
    outcome         text not null default 'success',
    actor_id        uuid constraint fk_audit_actor references public.profiles (id) on delete restrict,
    actor_role      text,
    target_type     text,
    target_id       text,
    reason          text,
    request_id      text,
    ip_prefix       text,
    metadata        jsonb not null default '{}'::jsonb,
    retain_until    timestamptz not null default (now() + interval '90 days'),
    created_at      timestamptz not null default now(),

    constraint ck_audit_category check (category in
        ('auth', 'admin', 'sms', 'credit', 'consent', 'privacy', 'security', 'moderation', 'system')),
    constraint ck_audit_action check (action ~ '^[a-z][a-z0-9_.]*$'),
    constraint ck_audit_outcome check (outcome in ('success', 'denied', 'failure')),
    constraint ck_audit_metadata_object check (jsonb_typeof(metadata) = 'object'),
    -- Guard rails: no message content, secrets or unmasked phone numbers in the audit trail.
    constraint ck_audit_metadata_keys check (
        not (metadata ?| array['body', 'message', 'text', 'content', 'password', 'token', 'secret', 'otp', 'authorization'])),
    constraint ck_audit_no_phone check (
        not private.contains_unmasked_phone(metadata::text)
        and not private.contains_unmasked_phone(target_id)
        and not private.contains_unmasked_phone(reason))
);

comment on table public.audit_logs is
    'Append-only. Rows can be deleted only after retain_until (SMS audit entries: at least 90 days). Security events should set a longer retain_until per policy. Server-only.';

create index idx_audit_created on public.audit_logs (created_at desc);
create index idx_audit_category on public.audit_logs (category, created_at desc);
create index idx_audit_actor on public.audit_logs (actor_id, created_at desc) where actor_id is not null;
create index idx_audit_target on public.audit_logs (target_type, target_id) where target_id is not null;
create index idx_audit_retention on public.audit_logs (retain_until);

create function private.protect_audit_logs()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if tg_op = 'DELETE' and old.retain_until < now() then
        return old;
    end if;
    raise exception 'audit_logs is immutable until retain_until' using errcode = '55000';
end;
$$;

create trigger trg_audit_protect
    before update or delete on public.audit_logs
    for each row execute function private.protect_audit_logs();

alter table public.audit_logs enable row level security;
revoke all on table public.audit_logs from public, anon, authenticated;
grant select, insert, delete on table public.audit_logs to service_role;
-- No policies: no client access. Administrators read the audit log through the backend.

commit;
