import { MessageSquareText, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { SimulatedBadge } from "@/components/shared/ChannelBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { formatListTime } from "@/features/chat/format";
import { useSmsConversations } from "@/features/sms/hooks/useSms";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";
import { cn } from "@/lib/utils";

export function SmsConversationList({ selectedId }: { selectedId?: string | undefined }) {
  const list = useSmsConversations();

  return (
    <section
      aria-label="SMS conversations"
      className="rounded-panel border border-border bg-surface"
    >
      <div className="flex items-center justify-between gap-2 border-b border-border p-2">
        <h2 className="text-sm font-semibold">SMS</h2>
        <Button asChild size="sm">
          <Link to={paths.smsNew}>
            <Plus aria-hidden className="size-4" /> New SMS
          </Link>
        </Button>
      </div>
      {list.isPending ? (
        <p role="status" className="p-4 text-sm text-fg-muted">
          Loading conversations…
        </p>
      ) : list.isError ? (
        <ErrorState
          kind={toUserFacingError(list.error).kind}
          message={toUserFacingError(list.error).message}
          {...(toUserFacingError(list.error).requestId
            ? { requestId: toUserFacingError(list.error).requestId as string }
            : {})}
          onRetry={() => void list.refetch()}
        />
      ) : list.data.data.length === 0 ? (
        <EmptyState
          icon={MessageSquareText}
          title="No SMS conversations yet"
          description="Send a text to a mobile phone. Replies appear here."
        />
      ) : (
        <ul>
          {list.data.data.map((conversation) => (
            <li key={conversation.id}>
              <Link
                to={`${paths.sms}/${conversation.id}`}
                aria-current={conversation.id === selectedId ? "page" : undefined}
                className={cn(
                  "block min-h-11 border-b border-border p-3 hover:bg-surface-raised",
                  conversation.id === selectedId && "bg-surface-raised",
                )}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">
                    {conversation.display_name ?? conversation.masked_phone}
                  </span>
                  <time className="shrink-0 text-xs text-fg-muted">
                    {formatListTime(conversation.last_message_at)}
                  </time>
                </span>
                {conversation.display_name ? (
                  <span className="block text-xs text-fg-muted">{conversation.masked_phone}</span>
                ) : null}
                <span className="mt-1 flex items-center gap-2 text-sm text-fg-muted">
                  <span className="truncate">
                    {conversation.last_message_direction === "outbound" ? "You: " : ""}
                    {conversation.last_message_preview ?? "No messages yet"}
                  </span>
                  {conversation.last_is_simulated ? <SimulatedBadge className="shrink-0" /> : null}
                  {conversation.unread_count > 0 ? (
                    <span className="ml-auto shrink-0 rounded-full bg-accent px-2 text-xs text-accent-fg">
                      {conversation.unread_count}
                      <span className="sr-only"> unread</span>
                    </span>
                  ) : null}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
