import { cn } from "@/lib/utils";
import type { PresenceStatus } from "@/lib/types";
import { PresenceIndicator } from "./PresenceIndicator";

const SIZES = { sm: "size-8 text-xs", md: "size-10 text-sm", lg: "size-16 text-xl" } as const;

export interface AvatarProps {
  name: string;
  imageUrl?: string;
  size?: keyof typeof SIZES;
  /** When provided, a presence dot is overlaid. */
  presence?: PresenceStatus;
  className?: string;
}

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

export function Avatar({ name, imageUrl, size = "md", presence, className }: AvatarProps) {
  return (
    <span className={cn("relative inline-flex shrink-0", className)}>
      <span
        className={cn(
          "inline-flex items-center justify-center overflow-hidden rounded-full border border-border bg-surface-raised font-semibold text-fg",
          SIZES[size],
        )}
      >
        {imageUrl ? (
          <img src={imageUrl} alt={`${name} profile`} className="size-full object-cover" />
        ) : (
          <span aria-hidden>{getInitials(name)}</span>
        )}
      </span>
      {presence ? (
        <PresenceIndicator
          status={presence}
          className="absolute -bottom-0.5 -right-0.5 ring-2 ring-surface"
        />
      ) : null}
    </span>
  );
}
