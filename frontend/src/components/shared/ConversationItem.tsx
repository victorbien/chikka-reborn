import type { MessageChannel, PresenceStatus, SmsMode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Avatar } from "./Avatar";
import { ChannelBadge } from "./ChannelBadge";

export interface ConversationItemProps {
  name: string;
  avatarUrl?: string;
  lastMessagePreview: string;
  timestamp: string;
  unreadCount?: number;
  presence?: PresenceStatus;
  channel: MessageChannel;
  smsMode?: SmsMode;
  selected?: boolean;
  onSelect: () => void;
}

export function ConversationItem({
  name,
  avatarUrl,
  lastMessagePreview,
  timestamp,
  unreadCount = 0,
  presence,
  channel,
  smsMode,
  selected = false,
  onSelect,
}: ConversationItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "flex min-h-11 w-full items-start gap-3 rounded-control px-2 py-2 text-left hover:bg-surface-raised",
        selected && "bg-surface-raised",
      )}
    >
      <Avatar name={name} imageUrl={avatarUrl} presence={presence} />
      <span className="min-w-0 flex-1 space-y-0.5">
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-semibold">{name}</span>
          <time className="shrink-0 text-xs text-fg-muted">{timestamp}</time>
        </span>
        <span className="block truncate text-xs text-fg-muted">{lastMessagePreview}</span>
        <ChannelBadge channel={channel} smsMode={smsMode} />
      </span>
      {unreadCount > 0 ? (
        <span className="mt-1 inline-flex min-w-5 items-center justify-center rounded-full bg-accent px-1.5 text-xs font-bold text-accent-fg">
          <span aria-hidden>{unreadCount}</span>
          <span className="sr-only">{unreadCount} unread messages</span>
        </span>
      ) : null}
    </button>
  );
}
