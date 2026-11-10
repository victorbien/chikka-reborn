import { AlertCircle, Lock, WifiOff, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export type ErrorKind = "error" | "offline" | "forbidden";

const KINDS: Record<ErrorKind, { Icon: LucideIcon; title: string }> = {
  error: { Icon: AlertCircle, title: "Something went wrong" },
  offline: { Icon: WifiOff, title: "You are offline" },
  forbidden: { Icon: Lock, title: "You do not have access" },
};

export interface ErrorStateProps {
  kind?: ErrorKind;
  message: string;
  requestId?: string;
  onRetry?: () => void;
}

export function ErrorState({ kind = "error", message, requestId, onRetry }: ErrorStateProps) {
  const { Icon, title } = KINDS[kind];
  return (
    <div role="alert" className="flex flex-col items-center gap-2 p-8 text-center">
      <Icon aria-hidden className="size-10 text-danger" />
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="max-w-sm text-sm text-fg-muted">{message}</p>
      {requestId ? <p className="font-mono text-xs text-fg-muted">Request ID: {requestId}</p> : null}
      {onRetry && kind !== "forbidden" ? (
        <Button variant="secondary" onClick={onRetry} className="mt-2">
          Try again
        </Button>
      ) : null}
    </div>
  );
}
