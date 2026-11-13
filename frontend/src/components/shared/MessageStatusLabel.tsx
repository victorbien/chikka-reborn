import {
  AlertTriangle,
  Check,
  CheckCheck,
  Clock,
  RefreshCw,
  Send,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { MessageChannel, MessageStatus } from "@/lib/types";

const STATUSES: Record<MessageStatus, { label: string; Icon: LucideIcon; tone: string }> = {
  pending: { label: "Sending", Icon: Clock, tone: "text-fg-muted" },
  queued: { label: "Queued", Icon: Clock, tone: "text-fg-muted" },
  retrying: { label: "Retrying", Icon: RefreshCw, tone: "text-fg-muted" },
  accepted: { label: "Accepted by provider", Icon: Send, tone: "text-fg-muted" },
  sent: { label: "Sent", Icon: Check, tone: "text-fg-muted" },
  delivered: { label: "Delivered", Icon: CheckCheck, tone: "text-fg-muted" },
  read: { label: "Read", Icon: CheckCheck, tone: "text-success" },
  failed: { label: "Failed", Icon: XCircle, tone: "text-danger" },
  undelivered: { label: "Undelivered", Icon: AlertTriangle, tone: "text-danger" },
};

export interface MessageStatusLabelProps {
  status: MessageStatus;
  channel?: MessageChannel;
  /** Shown on hover and focus, e.g. "Delivered 12 Nov, 14:02" (FR-MSG-002 AC3). */
  detail?: string;
  className?: string;
}

/**
 * Shows exactly the status the backend reported. "Accepted" is never rendered
 * as delivered. For SMS "sent", we state that delivery is unconfirmed.
 */
export function MessageStatusLabel({
  status,
  channel,
  detail,
  className,
}: MessageStatusLabelProps) {
  const { label, Icon, tone } = STATUSES[status];
  const unconfirmed = status === "sent" && channel === "sms-outbound";
  return (
    <span
      className={cn("inline-flex items-center gap-1 text-xs", tone, className)}
      title={detail}
      tabIndex={detail ? 0 : undefined}
      aria-label={detail ? `${label}. ${detail}` : undefined}
    >
      <Icon aria-hidden className="size-3.5" />
      <span>{label}</span>
      {unconfirmed ? <span className="text-fg-muted">(delivery unconfirmed)</span> : null}
    </span>
  );
}
