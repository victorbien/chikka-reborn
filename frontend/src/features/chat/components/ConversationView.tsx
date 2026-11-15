import { Archive, ArchiveRestore, ArrowLeft, MessageCircle } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { FormAlert } from "@/components/common/FormAlert";
import { Avatar } from "@/components/shared/Avatar";
import { ChannelBadge } from "@/components/shared/ChannelBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { PresenceIndicator } from "@/components/shared/PresenceIndicator";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Tip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { PresenceStatus } from "@/lib/types";
import { ChatComposer, type ComposerSuggestion } from "@/features/chat/components/ChatComposer";
import { ConnectionBanner } from "@/features/chat/components/ConnectionBanner";
import { MessageThread } from "@/features/chat/components/MessageThread";
import {
  useConversation,
  useLoadOlder,
  useMarkRead,
  useSendMessage,
  useSetArchived,
  useThread,
} from "@/features/chat/hooks/useChat";
import { maxSeq } from "@/features/chat/thread";
import { useTypingUser } from "@/features/chat/typing-store";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";

const PRESENCE_WORDS: Record<PresenceStatus, string> = {
  online: "(Online)",
  away: "(Away)",
  busy: "(Busy)",
  offline: "(Offline)",
  unknown: "",
};

export interface ConversationViewProps {
  conversationId: string;
  viewerId: string;
  /** Classic shows a compact window title bar; Modern shows the roomy header. Same data. */
  variant?: "modern" | "classic";
  /** The viewer's nickname for this contact (Classic window title). */
  nickname?: string | null;
  /** Replaces the default minimum height, e.g. to fill a fixed-height column. */
  className?: string;
  suggestion?: ComposerSuggestion | null;
  onDraftChange?: (draft: string) => void;
  showAiToggle?: boolean;
}

function useVisible(): boolean {
  const [visible, setVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState !== "hidden",
  );
  useEffect(() => {
    const update = () => setVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return visible;
}

export function ConversationView({
  conversationId,
  viewerId,
  variant = "modern",
  nickname,
  className,
  suggestion,
  onDraftChange,
  showAiToggle,
}: ConversationViewProps) {
  const [confirmArchive, setConfirmArchive] = useState(false);
  const conversation = useConversation(conversationId);
  const thread = useThread(conversationId);
  const older = useLoadOlder(conversationId);
  const markRead = useMarkRead(conversationId);
  const archive = useSetArchived(conversationId);
  const { send, retry, discard } = useSendMessage(conversationId, viewerId);
  const typingUser = useTypingUser(conversationId);
  const visible = useVisible();
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  // Where "New messages" goes: the read position when the conversation was opened.
  const [unreadAfter, setUnreadAfter] = useState<number | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const lastAnnounced = useRef<string | null>(null);

  const data = thread.data;
  const name = conversation.data?.participant.display_name ?? "Contact";
  const messages = data?.messages ?? [];
  const latestIncoming = [...messages].reverse().find((m) => !m.is_mine && !m.local);
  const latest = messages[messages.length - 1];

  // Captured once, when the history first arrives (state adjusted during render, not in an effect).
  if (data && unreadAfter === null) setUnreadAfter(data.lastReadSeq);

  // Reading clears the unread count. Only while the page is actually visible.
  const highest = maxSeq(data);
  const { mutate: reportRead, isPending: reporting } = markRead;
  useEffect(() => {
    if (!data || !visible || reporting || !latestIncoming) return;
    if (latestIncoming.seq > data.lastReadSeq) reportRead(highest);
  }, [data, visible, latestIncoming, highest, reportRead, reporting]);

  // Announce messages that arrive while the conversation is open (not the initial history).
  useEffect(() => {
    if (!latestIncoming) return;
    if (lastAnnounced.current === null) {
      lastAnnounced.current = latestIncoming.id;
      return;
    }
    if (latestIncoming.id !== lastAnnounced.current) {
      lastAnnounced.current = latestIncoming.id;
      setAnnouncement(`New message from ${name}`);
    }
  }, [latestIncoming, name]);

  // Stay pinned to the newest message unless the user scrolled up to read history.
  useLayoutEffect(() => {
    const node = scrollRef.current;
    if (node && (nearBottom.current || latest?.is_mine)) node.scrollTop = node.scrollHeight;
  }, [latest?.id, latest?.is_mine, messages.length]);

  if (conversation.isPending) return <p role="status">Loading conversation…</p>;
  if (conversation.isError) {
    const friendly = toUserFacingError(conversation.error);
    return (
      <ErrorState
        kind={friendly.kind}
        message={
          friendly.kind === "forbidden"
            ? "You don't have access to this conversation."
            : friendly.message
        }
        requestId={friendly.requestId}
        onRetry={() => void conversation.refetch()}
      />
    );
  }
  const summary = conversation.data;
  const participant = summary.participant;

  const archiveButton = (
    <Tip
      label={
        summary.is_archived
          ? "Move this conversation back to your inbox"
          : "Hide this conversation from your inbox. A new message brings it back."
      }
    >
      <Button
        variant="ghost"
        size="sm"
        disabled={archive.isPending}
        onClick={() => (summary.is_archived ? archive.mutate(false) : setConfirmArchive(true))}
      >
        {summary.is_archived ? (
          <ArchiveRestore aria-hidden className="size-4" />
        ) : (
          <Archive aria-hidden className="size-4" />
        )}
        <span>{summary.is_archived ? "Unarchive" : "Archive"}</span>
      </Button>
    </Tip>
  );

  return (
    <section
      aria-labelledby="conversation-heading"
      data-variant={variant}
      className={cn("flex flex-col", className ?? "min-h-[60vh]")}
    >
      {variant === "classic" ? (
        <header className="flex items-center gap-2 border-b border-border bg-surface-raised px-2 py-1 bevel">
          <Button asChild variant="ghost" size="icon" className="md:hidden">
            <Link to={paths.messages} aria-label="Back to conversations">
              <ArrowLeft aria-hidden className="size-4" />
            </Link>
          </Button>
          <PresenceIndicator status={participant.presence} />
          <h2 id="conversation-heading" className="min-w-0 flex-1 truncate text-sm font-bold">
            {nickname ?? participant.display_name}
            <span className="ml-2 text-xs font-normal text-fg-muted">
              {PRESENCE_WORDS[participant.presence]}
            </span>
          </h2>
          {archiveButton}
        </header>
      ) : (
        <header className="flex items-center gap-3 border-b border-border p-3">
          <Button asChild variant="ghost" size="icon" className="md:hidden">
            <Link to={paths.messages} aria-label="Back to conversations">
              <ArrowLeft aria-hidden className="size-4" />
            </Link>
          </Button>
          <Avatar
            name={participant.display_name}
            imageUrl={participant.avatar_url ?? undefined}
            presence={participant.presence}
          />
          <div className="min-w-0 flex-1">
            <h2 id="conversation-heading" className="truncate text-base font-semibold">
              {participant.display_name}
            </h2>
            <p className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
              {participant.username ? <span>@{participant.username}</span> : null}
              <PresenceIndicator status={participant.presence} showLabel />
              <ChannelBadge channel="internet" />
            </p>
          </div>
          {archiveButton}
        </header>
      )}
      <ConfirmDialog
        open={confirmArchive}
        onOpenChange={setConfirmArchive}
        title="Archive this conversation?"
        description={`It leaves your inbox. Nothing is deleted, and a new message from ${participant.display_name} brings it back.`}
        confirmLabel="Archive"
        onConfirm={() => archive.mutate(true)}
      />

      <ConnectionBanner />
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>

      <div
        ref={scrollRef}
        onScroll={(event) => {
          const node = event.currentTarget;
          nearBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80;
        }}
        className={cn(
          "min-h-0 flex-1 space-y-2 overflow-y-auto",
          variant === "classic" ? "p-2" : "p-3",
        )}
      >
        {thread.isPending ? <p role="status">Loading messages…</p> : null}
        {thread.isError && !data ? (
          <ErrorState
            kind={toUserFacingError(thread.error).kind}
            message={toUserFacingError(thread.error).message}
            requestId={toUserFacingError(thread.error).requestId}
            onRetry={() => void thread.refetch()}
          />
        ) : null}
        {data?.hasMoreBefore ? (
          <div className="flex justify-center">
            <Button
              variant="secondary"
              size="sm"
              disabled={older.isPending}
              onClick={() => older.mutate()}
            >
              {older.isPending ? "Loading…" : "Load earlier messages"}
            </Button>
          </div>
        ) : null}
        {older.error ? (
          <FormAlert tone="error">{toUserFacingError(older.error).message}</FormAlert>
        ) : null}
        {data && messages.length === 0 ? (
          <EmptyState
            icon={MessageCircle}
            title="No messages yet"
            description={`Say hello to ${participant.display_name}.`}
          />
        ) : null}
        {data && messages.length > 0 ? (
          <MessageThread
            messages={messages}
            contactName={participant.display_name}
            unreadAfterSeq={unreadAfter ?? data.lastReadSeq}
            onRetry={retry}
            onDiscard={discard}
          />
        ) : null}
      </div>

      <p aria-live="polite" className="min-h-5 px-3 text-xs text-fg-muted">
        {typingUser === participant.user_id ? `${participant.display_name} is typing…` : ""}
      </p>

      <ChatComposer
        key={conversationId}
        conversationId={conversationId}
        onSend={send}
        disabledReason={summary.can_send ? undefined : (summary.cannot_send_reason ?? undefined)}
        suggestion={suggestion}
        onDraftChange={onDraftChange}
        showAiToggle={showAiToggle}
      />
    </section>
  );
}
