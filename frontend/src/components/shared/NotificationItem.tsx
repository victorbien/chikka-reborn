import { AlertTriangle, Bell, CheckCircle2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type NotificationKind = "info" | "success" | "warning";

const KINDS: Record<NotificationKind, { Icon: LucideIcon; tone: string; label: string }> = {
  info: { Icon: Bell, tone: "text-accent", label: "Info" },
  success: { Icon: CheckCircle2, tone: "text-success", label: "Success" },
  warning: { Icon: AlertTriangle, tone: "text-away", label: "Warning" },
};

export interface NotificationItemProps {
  title: string;
  /** Absent when there is nothing to add to the title (for example previews are off). */
  description?: string | null;
  /** How many events this one notification stands for. Shown from 2. */
  count?: number;
  /** Extra controls, such as Open and Dismiss. */
  actions?: ReactNode;
  timestamp: string;
  kind?: NotificationKind;
  isRead: boolean;
  onMarkRead: () => void;
}

export function NotificationItem({
  title,
  description,
  count = 1,
  actions,
  timestamp,
  kind = "info",
  isRead,
  onMarkRead,
}: NotificationItemProps) {
  const { Icon, tone, label } = KINDS[kind];
  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-panel border border-border p-3",
        isRead ? "bg-surface" : "bg-surface-raised",
      )}
    >
      <Icon
        aria-hidden
        className={cn("mt-0.5 size-5 shrink-0", tone, !isRead && "animate-notify")}
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">
          <span className="sr-only">{label}: </span>
          {title}
          {count > 1 ? (
            <span className="ml-2 text-xs font-normal text-fg-muted">({count})</span>
          ) : null}
          {!isRead ? <span className="ml-2 text-xs font-normal text-accent">New</span> : null}
        </p>
        {description ? <p className="text-sm text-fg-muted">{description}</p> : null}
        <time className="text-xs text-fg-muted">{timestamp}</time>
      </div>
      <div className="flex shrink-0 flex-wrap justify-end gap-1">
        {actions}
        {!isRead ? (
          <Button size="sm" variant="ghost" onClick={onMarkRead}>
            Mark as read
          </Button>
        ) : null}
      </div>
    </li>
  );
}
