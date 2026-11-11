import { estimateSms } from "@/lib/sms";
import type { SmsMode } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface SmsCostEstimateProps {
  body: string;
  smsMode: SmsMode;
  creditsPerSegment: number;
  /** When known, flags an insufficient balance (live mode only). */
  creditBalance?: number;
  className?: string;
}

export function SmsCostEstimate({
  body,
  smsMode,
  creditsPerSegment,
  creditBalance,
  className,
}: SmsCostEstimateProps) {
  const estimate = estimateSms(body);
  const cost = estimate.segments * creditsPerSegment;
  const simulated = smsMode === "simulated";
  const shortfallBalance =
    !simulated && creditBalance !== undefined && cost > creditBalance ? creditBalance : null;
  const fill = Math.min(
    100,
    Math.round(
      (estimate.characters / (estimate.perSegment * Math.max(1, estimate.segments))) * 100,
    ),
  );

  return (
    <div className={cn("space-y-1 text-xs text-fg-muted", className)}>
      <progress
        aria-label="Characters used in current segment"
        max={100}
        value={fill}
        className={cn(
          "block h-1 w-full appearance-none overflow-hidden rounded-full [&::-webkit-progress-bar]:bg-surface-raised",
          fill > 90
            ? "[&::-webkit-progress-value]:bg-away [&::-moz-progress-bar]:bg-away"
            : "[&::-webkit-progress-value]:bg-accent [&::-moz-progress-bar]:bg-accent",
        )}
      />
      <p aria-live="polite">
        {estimate.characters} chars · {estimate.segments}{" "}
        {estimate.segments === 1 ? "segment" : "segments"} ·{" "}
        {estimate.encoding === "gsm7" ? "GSM-7" : "Unicode"} ·{" "}
        {simulated ? "No credits charged (simulation)" : `${cost.toFixed(2)} credits`}
      </p>
      {shortfallBalance !== null ? (
        <p role="alert" className="text-danger">
          Not enough credits. This message needs {cost.toFixed(2)}, you have{" "}
          {shortfallBalance.toFixed(2)}.
        </p>
      ) : null}
    </div>
  );
}
