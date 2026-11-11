import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  /** Next-step control, e.g. a Button. */
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 p-8 text-center">
      <Icon aria-hidden className="size-10 text-fg-muted" />
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="max-w-sm text-sm text-fg-muted">{description}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
