import { Fragment } from "react";
import { MessageBubble } from "@/components/shared/MessageBubble";
import { Button } from "@/components/ui/button";
import { AttachmentView } from "@/features/chat/components/AttachmentView";
import { dayKey, formatDay, formatFull, formatTime } from "@/features/chat/format";
import type { ChatMessage } from "@/features/chat/types";

export interface MessageThreadProps {
  messages: ChatMessage[];
  contactName: string;
  /** Messages after this seq (from the other person) are marked "New messages". */
  unreadAfterSeq: number;
  onRetry: (clientMessageId: string) => void;
  onDiscard: (clientMessageId: string) => void;
}

function statusDetail(message: ChatMessage): string | undefined {
  if (message.status === "read" && message.read_at) return `Read ${formatFull(message.read_at)}`;
  if ((message.status === "delivered" || message.status === "read") && message.delivered_at) {
    return `Delivered ${formatFull(message.delivered_at)}`;
  }
  if (message.status === "sent") return "Stored on the server. Not yet received by their app.";
  return undefined;
}

/** History with date separators, a "New messages" divider and per-message status. */
export function MessageThread({
  messages,
  contactName,
  unreadAfterSeq,
  onRetry,
  onDiscard,
}: MessageThreadProps) {
  const firstUnread = messages.find((m) => !m.is_mine && !m.local && m.seq > unreadAfterSeq);

  return (
    <ol aria-label={`Messages with ${contactName}`} className="space-y-2">
      {messages.map((message, index) => {
        const previous = messages[index - 1];
        const newDay = !previous || dayKey(previous.created_at) !== dayKey(message.created_at);
        const failed = message.local?.state === "failed";
        return (
          <Fragment key={message.local ? `local-${message.client_message_id}` : message.id}>
            {newDay ? (
              <li role="separator" className="flex items-center gap-2 py-2 text-xs text-fg-muted">
                <span aria-hidden className="h-px flex-1 bg-border" />
                <span>{formatDay(message.created_at)}</span>
                <span aria-hidden className="h-px flex-1 bg-border" />
              </li>
            ) : null}
            {message === firstUnread ? (
              <li
                role="separator"
                className="flex items-center gap-2 py-1 text-xs font-semibold text-accent"
              >
                <span aria-hidden className="h-px flex-1 bg-accent" />
                <span>New messages</span>
                <span aria-hidden className="h-px flex-1 bg-accent" />
              </li>
            ) : null}
            <MessageBubble
              body={message.body ?? ""}
              timestamp={formatTime(message.created_at)}
              dateTime={message.created_at}
              timestampTitle={formatFull(message.created_at)}
              direction={message.is_mine ? "outgoing" : "incoming"}
              channel="internet"
              hideChannel
              senderName={contactName}
              status={message.is_mine ? (message.status ?? undefined) : undefined}
              statusDetail={message.is_mine ? statusDetail(message) : undefined}
              footer={
                failed && message.client_message_id ? (
                  <span role="alert" className="flex flex-wrap items-center gap-2 text-danger">
                    <span>{message.local?.error ?? "Not sent."}</span>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => onRetry(message.client_message_id as string)}
                    >
                      Try again
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onDiscard(message.client_message_id as string)}
                    >
                      Discard
                    </Button>
                  </span>
                ) : undefined
              }
            >
              {message.attachments.map((attachment) => (
                <AttachmentView key={attachment.id} attachment={attachment} />
              ))}
            </MessageBubble>
          </Fragment>
        );
      })}
    </ol>
  );
}
