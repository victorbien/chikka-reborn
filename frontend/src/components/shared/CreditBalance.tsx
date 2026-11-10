import { Coins } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CreditBalanceProps {
  available: number;
  reserved?: number;
  lowThreshold?: number;
  className?: string;
}

export function CreditBalance({ available, reserved, lowThreshold = 1, className }: CreditBalanceProps) {
  const low = available < lowThreshold;
  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <Coins aria-hidden className={cn("size-4", low ? "text-away" : "text-accent")} />
      <div>
        <p className="text-sm font-semibold">
          <span className="sr-only">Credit balance: </span>
          {available.toFixed(2)} credits
        </p>
        {reserved !== undefined ? (
          <p className="text-xs text-fg-muted">{reserved.toFixed(2)} reserved</p>
        ) : null}
        {low ? <p className="text-xs text-away">Low balance</p> : null}
      </div>
    </div>
  );
}
