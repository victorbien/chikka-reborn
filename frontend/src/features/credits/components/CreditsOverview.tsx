import { Coins } from "lucide-react";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { LowCreditWarning } from "@/features/credits/components/LowCreditWarning";
import { useCreditBalance, useCreditTransactions } from "@/features/credits/hooks/useCredits";
import type { CreditTransaction } from "@/features/credits/types";
import { formatDateTime } from "@/lib/datetime";
import { toUserFacingError } from "@/lib/error-handling";
import { cn } from "@/lib/utils";
import { useState } from "react";

function signed(credits: number): string {
  const text = Math.abs(credits).toFixed(2);
  return credits > 0 ? `+${text}` : credits < 0 ? `-${text}` : text;
}

function Row({ item }: { item: CreditTransaction }) {
  const held = item.entry_type === "reservation" || item.entry_type === "reservation_release";
  return (
    <li className="flex items-start justify-between gap-3 rounded-panel border border-border p-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">{item.description}</p>
        <p className="text-xs text-fg-muted">
          {formatDateTime(item.created_at)}
          {item.segment_count
            ? ` · ${item.segment_count} ${item.segment_count === 1 ? "segment" : "segments"}`
            : ""}
          {item.country_code ? ` · ${item.country_code}` : ""}
        </p>
        {item.reason && item.entry_type !== "grant" ? (
          <p className="text-xs text-fg-muted">{item.reason}</p>
        ) : null}
      </div>
      <div className="shrink-0 text-right">
        <p
          className={cn(
            "text-sm font-semibold",
            item.credits_delta > 0 && "text-success",
            item.credits_delta < 0 && "text-danger",
          )}
        >
          {held ? (
            <>
              <span className="sr-only">Held: </span>
              {(Math.abs(item.reserved_delta) / 100).toFixed(2)}
              <span className="text-xs font-normal text-fg-muted">
                {item.reserved_delta > 0 ? " held" : " released"}
              </span>
            </>
          ) : (
            <>
              <span className="sr-only">Change: </span>
              {signed(item.credits_delta)}
            </>
          )}
        </p>
        {item.balance_after !== null ? (
          <p className="text-xs text-fg-muted">Balance {(item.balance_after / 100).toFixed(2)}</p>
        ) : null}
      </div>
    </li>
  );
}

/** Balance, the plain-language notice that these are not money, and the full ledger. */
export function CreditsOverview() {
  const [page, setPage] = useState(1);
  const balance = useCreditBalance();
  const history = useCreditTransactions(page);
  const ledger = balance.data?.ledgers.find((item) => item.ledger === balance.data?.active_ledger);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Credits</h1>
      <LowCreditWarning />

      <section
        aria-labelledby="balance-heading"
        className="rounded-panel border border-border bg-surface p-4"
      >
        <h2 id="balance-heading" className="text-lg font-semibold">
          {balance.data?.is_simulated === false ? "Credit balance" : "Demo credit balance"}
        </h2>
        {balance.isPending ? <p className="text-sm text-fg-muted">Loading your balance…</p> : null}
        {balance.isError ? (
          <ErrorState
            kind={toUserFacingError(balance.error).kind}
            message={toUserFacingError(balance.error).message}
            onRetry={() => void balance.refetch()}
          />
        ) : null}
        {balance.data && ledger ? (
          <div className="mt-2 space-y-2">
            {ledger.charges_apply ? (
              <>
                <p className="flex items-center gap-2 text-3xl font-bold">
                  <Coins aria-hidden className="size-6 text-accent" />
                  <span>
                    <span className="sr-only">Available: </span>
                    {ledger.available_credits.toFixed(2)}
                  </span>
                </p>
                {ledger.reserved_units > 0 ? (
                  <p className="text-sm text-fg-muted">
                    {(ledger.reserved_units / 100).toFixed(2)} credits are held for messages being
                    sent. They are spent when the carrier accepts a message and returned if it
                    fails.
                  </p>
                ) : null}
                <p className="text-sm text-fg-muted">
                  Low-credit alert at {(balance.data.low_balance_threshold_units / 100).toFixed(2)}{" "}
                  credits. You can change this in your notification settings.
                </p>
              </>
            ) : null}
            <p className="text-sm">{balance.data.notice}</p>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="history-heading" className="space-y-2">
        <h2 id="history-heading" className="text-lg font-semibold">
          History
        </h2>
        {history.isPending ? (
          <p role="status" className="text-sm text-fg-muted">
            Loading your history…
          </p>
        ) : null}
        {history.isError ? (
          <ErrorState
            kind={toUserFacingError(history.error).kind}
            message={toUserFacingError(history.error).message}
            requestId={toUserFacingError(history.error).requestId}
            onRetry={() => void history.refetch()}
          />
        ) : null}
        {history.data && history.data.data.length === 0 ? (
          <EmptyState
            icon={Coins}
            title="No credit activity yet"
            description="Sending an SMS in simulation will show up here."
          />
        ) : null}
        {history.data && history.data.data.length > 0 ? (
          <>
            <ul aria-label="Credit transactions" className="space-y-2">
              {history.data.data.map((item) => (
                <Row key={item.id} item={item} />
              ))}
            </ul>
            <nav aria-label="History pages" className="flex items-center justify-between">
              <Button
                variant="secondary"
                size="sm"
                disabled={!history.data.pagination.has_prev}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Newer
              </Button>
              <span className="text-xs text-fg-muted">
                Page {history.data.pagination.page} · {history.data.pagination.total} entries
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={!history.data.pagination.has_next}
                onClick={() => setPage((current) => current + 1)}
              >
                Older
              </Button>
            </nav>
          </>
        ) : null}
      </section>
    </div>
  );
}
