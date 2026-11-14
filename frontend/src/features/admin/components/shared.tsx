import type { ReactNode } from "react";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { toUserFacingError } from "@/lib/error-handling";

export function Section({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section aria-label={title} className="rounded-panel border border-border bg-surface p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <p role="status" className="text-sm text-fg-muted">
      Loading {label}…
    </p>
  );
}

export function QueryProblem({ error, retry }: { error: unknown; retry: () => void }) {
  const friendly = toUserFacingError(error);
  return (
    <ErrorState
      kind={friendly.kind}
      message={friendly.message}
      requestId={friendly.requestId}
      onRetry={retry}
    />
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-control border border-border bg-surface-raised p-3">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd className="text-xl font-semibold">{value}</dd>
      {hint ? <p className="text-xs text-fg-muted">{hint}</p> : null}
    </div>
  );
}

export function Pager({
  page,
  hasNext,
  hasPrev,
  onPage,
}: {
  page: number;
  hasNext: boolean;
  hasPrev: boolean;
  onPage: (page: number) => void;
}) {
  return (
    <nav aria-label="Pagination" className="mt-3 flex items-center justify-between gap-2">
      <Button variant="secondary" size="sm" disabled={!hasPrev} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span className="text-sm text-fg-muted">Page {page}</span>
      <Button variant="secondary" size="sm" disabled={!hasNext} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </nav>
  );
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, { timeZone: "UTC", timeZoneName: "short" });
}

export function formatRate(rate: number | null): string {
  return rate === null ? "No settled messages" : `${Math.round(rate * 100)}%`;
}

export const TABLE = "w-full text-left text-sm";
export const TH = "py-2 pr-3 font-medium text-fg-muted";
export const TD = "py-2 pr-3 align-top";
