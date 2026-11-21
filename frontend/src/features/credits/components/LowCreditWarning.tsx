import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { useCreditBalance } from "@/features/credits/hooks/useCredits";
import { paths } from "@/lib/paths";

/** Shown while available demo credits are at or below the user's low-balance threshold. */
export function LowCreditWarning() {
  const balance = useCreditBalance();
  const ledger = balance.data?.ledgers.find((item) => item.ledger === balance.data?.active_ledger);
  if (!balance.data?.is_low || !ledger) return null;
  const empty = ledger.available_units <= 0;
  return (
    <div
      role="status"
      className="mb-3 flex items-start gap-2 rounded-panel border border-away p-3 text-sm"
    >
      <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-away" />
      <p>
        {empty
          ? "You are out of demo credits, so new SMS cannot be sent. "
          : `Your demo credits are running low: ${ledger.available_credits.toFixed(2)} left. `}
        <Link to={paths.credits} className="text-accent underline">
          See your credit history
        </Link>
        . An administrator can add more demo credits.
      </p>
    </div>
  );
}
