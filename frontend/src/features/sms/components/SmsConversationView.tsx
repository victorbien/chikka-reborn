import { useEffect, useRef } from "react";
import { ErrorState } from "@/components/shared/ErrorState";
import { SmsComposer } from "@/features/sms/components/SmsComposer";
import { SmsThread } from "@/features/sms/components/SmsThread";
import {
  useLoadOlderSms,
  useMarkSmsRead,
  useSmsConversations,
  useSmsThread,
} from "@/features/sms/hooks/useSms";
import type { Replies } from "@/features/sms/types";
import { toUserFacingError } from "@/lib/error-handling";

const REPLIES: Record<Replies, string> = {
  supported: "Replies can reach you here.",
  unverified: "Replies may arrive but are not guaranteed.",
  unsupported: "Replies are not supported for this country.",
};

export function SmsConversationView({ conversationId }: { conversationId: string }) {
  const thread = useSmsThread(conversationId);
  const conversations = useSmsConversations();
  const loadOlder = useLoadOlderSms(conversationId);
  const markRead = useMarkSmsRead(conversationId);
  const marked = useRef(0);
  const { mutate: mark } = markRead;

  const latestInbound = thread.data
    ? Math.max(
        0,
        ...thread.data.messages.filter((m) => m.direction === "inbound").map((m) => m.seq),
      )
    : 0;
  const lastRead = thread.data?.last_read_seq ?? 0;
  useEffect(() => {
    if (latestInbound > lastRead && latestInbound > marked.current) {
      marked.current = latestInbound;
      mark(latestInbound);
    }
  }, [latestInbound, lastRead, mark]);

  const summary = conversations.data?.data.find((c) => c.id === conversationId);

  if (thread.isPending) {
    return (
      <p role="status" className="p-4 text-sm text-fg-muted">
        Loading messages…
      </p>
    );
  }
  if (thread.isError) {
    const friendly = toUserFacingError(thread.error);
    return (
      <ErrorState
        kind={friendly.kind}
        message={friendly.message}
        requestId={friendly.requestId}
        onRetry={() => void thread.refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col">
      <header className="border-b border-border p-3">
        <h2 className="text-base font-semibold">
          {summary?.display_name ?? summary?.masked_phone ?? "SMS conversation"}
        </h2>
        {summary ? (
          <p className="text-xs text-fg-muted">
            {summary.display_name ? `${summary.masked_phone} · ` : ""}
            {REPLIES[summary.replies]}
          </p>
        ) : null}
      </header>
      {thread.data.messages.length === 0 ? (
        <p className="p-4 text-sm text-fg-muted">No messages yet. Write the first one below.</p>
      ) : (
        <SmsThread
          messages={thread.data.messages}
          hasMoreBefore={thread.data.has_more_before}
          loadingOlder={loadOlder.isPending}
          onLoadOlder={() => loadOlder.mutate()}
        />
      )}
      <div className="border-t border-border p-3">
        <SmsComposer target={{ kind: "conversation", conversationId }} onSent={() => undefined} />
      </div>
    </div>
  );
}
