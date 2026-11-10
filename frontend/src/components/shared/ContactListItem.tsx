import { Phone } from "lucide-react";
import type { PresenceStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Avatar } from "./Avatar";

export interface ContactListItemProps {
  name: string;
  /** Status line or masked phone number. */
  subtitle?: string;
  presence: PresenceStatus;
  /** SMS-only contacts have no Chikka account. */
  isSmsContact?: boolean;
  selected?: boolean;
  onSelect: () => void;
}

export function ContactListItem({
  name,
  subtitle,
  presence,
  isSmsContact = false,
  selected = false,
  onSelect,
}: ContactListItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "flex min-h-11 w-full items-center gap-3 rounded-control px-2 py-1.5 text-left hover:bg-surface-raised",
        selected && "bg-surface-raised",
      )}
    >
      <Avatar name={name} size="sm" presence={isSmsContact ? undefined : presence} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{name}</span>
        {subtitle ? <span className="block truncate text-xs text-fg-muted">{subtitle}</span> : null}
      </span>
      {isSmsContact ? (
        <span className="inline-flex items-center gap-1 text-xs text-sms">
          <Phone aria-hidden className="size-3" />
          SMS only
        </span>
      ) : (
        <span className="sr-only">{presence}</span>
      )}
    </button>
  );
}
