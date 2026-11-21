import { cn } from "@/lib/utils";
import type { PresenceStatus } from "@/lib/types";

const LABELS: Record<PresenceStatus, string> = {
  online: "Online",
  away: "Away",
  busy: "Busy",
  offline: "Offline",
  unknown: "Presence hidden",
};

// Status is never colour alone: shape differs too (filled, half, hollow).
const SHAPES: Record<PresenceStatus, string> = {
  online: "bg-online",
  away: "bg-away",
  busy: "bg-danger",
  offline: "border-2 border-offline bg-transparent",
  unknown: "border-2 border-dashed border-offline bg-transparent",
};

export interface PresenceIndicatorProps {
  status: PresenceStatus;
  /** Show the text label next to the dot. */
  showLabel?: boolean;
  className?: string;
}

export function PresenceIndicator({
  status,
  showLabel = false,
  className,
}: PresenceIndicatorProps) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", showLabel && className)}>
      <span
        role="img"
        aria-label={LABELS[status]}
        className={cn("inline-block size-3 rounded-full", SHAPES[status], !showLabel && className)}
      />
      {showLabel ? <span className="text-xs text-fg-muted">{LABELS[status]}</span> : null}
    </span>
  );
}
