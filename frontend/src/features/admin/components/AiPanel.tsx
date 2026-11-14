import {
  Loading,
  QueryProblem,
  Section,
  Stat,
  TABLE,
  TD,
  TH,
} from "@/features/admin/components/shared";
import { useAiMetrics } from "@/features/admin/hooks";

export function AiPanel() {
  const metrics = useAiMetrics();
  if (metrics.isPending) return <Loading label="AI usage" />;
  if (metrics.isError) {
    return <QueryProblem error={metrics.error} retry={() => void metrics.refetch()} />;
  }
  const m = metrics.data;
  return (
    <div className="space-y-4">
      <Section title={`AI usage, last ${m.window_days} days`}>
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Requests" value={m.total_requests} />
          <Stat label="Failed requests" value={m.failed_requests} />
          <Stat label="Input tokens" value={m.input_tokens} />
          <Stat label="Output tokens" value={m.output_tokens} />
          <Stat
            label="Approximate cost"
            value={
              m.estimated_cost_usd === null
                ? "Not available"
                : `$${m.estimated_cost_usd.toFixed(2)}`
            }
            hint={
              m.estimated_cost_usd === null
                ? "Set token prices in the server configuration to see a figure."
                : "Estimated from configured token prices."
            }
          />
        </dl>
        <p className="mt-2 text-xs text-fg-muted">
          Only counts and timings are shown. Drafts, prompts and AI output are never displayed.
        </p>
      </Section>
      <Section title="Feature usage">
        {m.features.length === 0 ? (
          <p className="text-sm text-fg-muted">No AI requests in this period.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE}>
              <thead>
                <tr>
                  {[
                    "Feature",
                    "Requests",
                    "Failures",
                    "Used by people",
                    "Average time",
                    "Tokens",
                  ].map((h) => (
                    <th key={h} scope="col" className={TH}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {m.features.map((f) => (
                  <tr key={f.feature}>
                    <td className={TD}>{f.feature}</td>
                    <td className={TD}>{f.requests}</td>
                    <td className={TD}>{f.failures}</td>
                    <td className={TD}>{f.accepted}</td>
                    <td className={TD}>
                      {f.average_latency_ms === null ? "—" : `${f.average_latency_ms} ms`}
                    </td>
                    <td className={TD}>{f.input_tokens + f.output_tokens}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <Section title="Provider errors">
        {m.errors.length === 0 ? (
          <p className="text-sm text-fg-muted">No errors in this period.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {m.errors.map((e) => (
              <li key={`${e.outcome}-${e.error_code ?? ""}`}>
                {e.outcome}
                {e.error_code ? ` (${e.error_code})` : ""}: {e.count}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
