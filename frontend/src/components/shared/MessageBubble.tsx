import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { MessageChannel, MessageStatus, SmsMode } from "@/lib/types";
import { ChannelBadge } from "./ChannelBadge";
import { MessageStatusLabel } from "./MessageStatusLabel";

export interface MessageBubbleProps {
  /** May be empty when the message is attachments only. */
  body: string;
  /** Preformatted time string, e.g. "12:34". */
  timestamp: string;
  /** Machine-readable time for <time dateTime>. */
  dateTime?: string;
  /** Full date and time, shown on hover and focus. */
  timestampTitle?: string;
  direction: "outgoing" | "incoming";
  channel: MessageChannel;
  smsMode?: SmsMode;
  status?: MessageStatus;
  /** Extra status wording on hover and focus, e.g. when it was delivered. */
  statusDetail?: string;
  senderName?: string;
  /** Hide the channel badge when the whole conversation is one channel (shown in the header). */
  hideChannel?: boolean;
  /** Attachments, rendered under the text. */
  children?: ReactNode;
  /** Actions under the bubble, e.g. "Try again" for a failed send. */
  footer?: ReactNode;
}

export function MessageBubble({
  body,
  timestamp,
  dateTime,
  timestampTitle,
  direction,
  channel,
  smsMode,
  status,
  statusDetail,
  senderName,
  hideChannel = false,
  children,
  footer,
}: MessageBubbleProps) {
  const outgoing = direction === "outgoing";
  return (
    <li className={cn("flex flex-col", outgoing ? "items-end" : "items-start")}>
      <article
        aria-label={`${outgoing ? "You" : (senderName ?? "Contact")}, ${timestamp}`}
        className={cn(
          "max-w-[85%] rounded-bubble px-3 py-2 md:max-w-[70%] bevel",
          outgoing ? "bg-bubble-out text-bubble-out-fg" : "bg-bubble-in text-bubble-in-fg",
          channel === "sms-inbound" && "border border-sms",
          status === "failed" && "border border-danger",
        )}
      >
        {hideChannel ? null : <ChannelBadge channel={channel} smsMode={smsMode} className="mb-1" />}
        {/* Rendered as text, never HTML, so user content cannot inject markup. */}
        {body ? <p className="whitespace-pre-wrap break-words text-sm">{body}</p> : null}
        {children}
        <p className="mt-1 flex items-center justify-end gap-2 text-xs opacity-90">
          <time dateTime={dateTime} title={timestampTitle}>
            {timestamp}
          </time>
          {outgoing && status ? (
            <MessageStatusLabel status={status} channel={channel} detail={statusDetail} />
          ) : null}
        </p>
      </article>
      {footer ? <div className="mt-1 text-xs">{footer}</div> : null}
    </li>
  );
}
