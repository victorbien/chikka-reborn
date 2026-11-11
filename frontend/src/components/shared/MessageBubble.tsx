import { cn } from "@/lib/utils";
import type { MessageChannel, MessageStatus, SmsMode } from "@/lib/types";
import { ChannelBadge } from "./ChannelBadge";
import { MessageStatusLabel } from "./MessageStatusLabel";

export interface MessageBubbleProps {
  body: string;
  /** Preformatted time string, e.g. "12:34". */
  timestamp: string;
  direction: "outgoing" | "incoming";
  channel: MessageChannel;
  smsMode?: SmsMode;
  status?: MessageStatus;
  /** Present on bubbles that show a status for outgoing messages only. */
  senderName?: string;
}

export function MessageBubble({
  body,
  timestamp,
  direction,
  channel,
  smsMode,
  status,
  senderName,
}: MessageBubbleProps) {
  const outgoing = direction === "outgoing";
  return (
    <li className={cn("flex", outgoing ? "justify-end" : "justify-start")}>
      <article
        aria-label={`${outgoing ? "You" : (senderName ?? "Contact")}, ${timestamp}`}
        className={cn(
          "max-w-[85%] rounded-bubble px-3 py-2 md:max-w-[70%] bevel",
          outgoing ? "bg-bubble-out text-bubble-out-fg" : "bg-bubble-in text-bubble-in-fg",
          channel === "sms-inbound" && "border border-sms",
        )}
      >
        <ChannelBadge channel={channel} smsMode={smsMode} className="mb-1" />
        {/* Rendered as text, never HTML, so user content cannot inject markup. */}
        <p className="whitespace-pre-wrap break-words text-sm">{body}</p>
        <p className="mt-1 flex items-center justify-end gap-2 text-xs opacity-90">
          <time>{timestamp}</time>
          {outgoing && status ? <MessageStatusLabel status={status} channel={channel} /> : null}
        </p>
      </article>
    </li>
  );
}
