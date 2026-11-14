import { useState } from "react";
import { FormField } from "@/components/common/FormField";
import { Select } from "@/components/ui/input";
import type { AuditQuery } from "@/features/admin/api";
import {
  formatDateTime,
  Loading,
  Pager,
  QueryProblem,
  Section,
  TABLE,
  TD,
  TH,
} from "@/features/admin/components/shared";
import { useAuditLogs } from "@/features/admin/hooks";

const OUTCOME_LABEL = { success: "Succeeded", denied: "Refused", failure: "Failed" } as const;

export function AuditPanel() {
  const [outcome, setOutcome] = useState<AuditQuery["outcome"] | "">("");
  const [page, setPage] = useState(1);
  const logs = useAuditLogs({ outcome: outcome || undefined, page });

  return (
    <Section title="Audit log">
      <div className="mb-3 max-w-xs">
        <FormField label="Outcome">
          <Select
            value={outcome}
            onChange={(e) => {
              setOutcome(e.target.value as AuditQuery["outcome"] | "");
              setPage(1);
            }}
          >
            <option value="">Any outcome</option>
            <option value="success">Succeeded</option>
            <option value="denied">Refused</option>
            <option value="failure">Failed</option>
          </Select>
        </FormField>
      </div>
      {logs.isPending ? <Loading label="audit log" /> : null}
      {logs.isError ? <QueryProblem error={logs.error} retry={() => void logs.refetch()} /> : null}
      {logs.data && logs.data.data.length === 0 ? (
        <p className="text-sm text-fg-muted">No audit entries match.</p>
      ) : null}
      {logs.data && logs.data.data.length > 0 ? (
        <>
          <div className="overflow-x-auto">
            <table className={TABLE}>
              <thead>
                <tr>
                  {["Time", "Actor", "Action", "Resource", "Outcome"].map((h) => (
                    <th key={h} scope="col" className={TH}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.data.data.map((row) => (
                  <tr key={row.id}>
                    <td className={TD}>{formatDateTime(row.created_at)}</td>
                    <td className={TD}>
                      {row.actor_id
                        ? `${row.actor_role ?? "unknown"} ${row.actor_id.slice(0, 8)}`
                        : "system"}
                    </td>
                    <td className={TD}>{row.action}</td>
                    <td className={TD}>
                      {row.target_type ?? "—"}
                      {row.target_id ? ` ${row.target_id.slice(0, 8)}` : ""}
                    </td>
                    <td className={TD}>{OUTCOME_LABEL[row.outcome]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager
            page={page}
            hasNext={logs.data.pagination.has_next}
            hasPrev={logs.data.pagination.has_prev}
            onPage={setPage}
          />
        </>
      ) : null}
    </Section>
  );
}
