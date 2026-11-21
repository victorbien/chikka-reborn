import { Coins } from "lucide-react";
import { Link } from "react-router-dom";
import { useCreditBalance } from "@/features/credits/hooks/useCredits";
import { paths } from "@/lib/paths";
import { cn } from "@/lib/utils";

/** Header chip: the balance of the ledger the current SMS mode charges. Quietly absent while
 *  loading or when it cannot be loaded: credits are never needed to read or chat. */
export function CreditBadge() {
  const balance = useCreditBalance();
  const ledger = balance.data?.ledgers.find((item) => item.ledger === balance.data?.active_ledger);
  if (!balance.data || !ledger) return null;
  const metered = ledger.charges_apply;
  const label = metered
    ? `${ledger.available_credits.toFixed(2)} ${balance.data.is_simulated ? "demo " : ""}credits`
    : "Credits";
  return (
    <Link
      to={paths.credits}
      aria-label={
        metered
          ? `${label}${balance.data.is_low ? ", low balance" : ""}. Open credit history`
          : "Credits. Open credit history"
      }
      className={cn(
        "inline-flex min-h-11 items-center gap-2 rounded-control px-2 text-sm hover:bg-surface-raised",
        balance.data.is_low ? "text-away" : "text-fg",
      )}
    >
      <Coins aria-hidden className="size-4" />
      <span className="hidden sm:inline">{label}</span>
      {balance.data.is_low ? (
        <span className="text-xs font-semibold" aria-hidden>
          Low
        </span>
      ) : null}
    </Link>
  );
}
