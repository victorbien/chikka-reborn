import { AlertCircle, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface FormAlertProps {
  tone: "error" | "success" | "info";
  children: ReactNode;
  requestId?: string | null;
  className?: string;
}

/** Inline form feedback. Errors interrupt (role=alert); confirmations are polite. */
export function FormAlert({ tone, children, requestId, className }: FormAlertProps) {
  const Icon = tone === "error" ? AlertCircle : CheckCircle2;
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "flex gap-2 rounded-panel border p-3 text-sm",
        tone === "error" && "border-danger text-fg",
        tone === "success" && "border-success text-fg",
        tone === "info" && "border-border text-fg",
        className,
      )}
    >
      <Icon
        aria-hidden
        className={cn("mt-0.5 size-4 shrink-0", tone === "error" ? "text-danger" : "text-success")}
      />
      <div className="space-y-1">
        <div>{children}</div>
        {requestId ? (
          <p className="font-mono text-xs text-fg-muted">Request ID: {requestId}</p>
        ) : null}
      </div>
    </div>
  );
}
