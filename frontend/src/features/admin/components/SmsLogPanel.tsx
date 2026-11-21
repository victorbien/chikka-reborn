import { useState } from "react";
import { LiveBadge, SimulatedBadge } from "@/components/shared/ChannelBadge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { FormField } from "@/components/common/FormField";
import type { SmsMessageRow } from "@/features/admin/api";
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
import { useAdminSms, useAdminSmsMessage } from "@/features/admin/hooks";

function MessageDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const detail = useAdminSmsMessage(id);
  const close = (
    <Button variant="ghost" size="sm" onClick={onClose}>
      Close
    </Button>
  );
  if (detail.isPending) {
    return (
      <Section title="Delivery attempts" action={close}>
        <Loading label="attempts" />
      </Section>
    );
  }
  if (detail.isError) {
    return (
      <Section title="Delivery attempts" action={close}>
        <QueryProblem error={detail.error} retry={() => void detail.refetch()} />
      </Section>
    );
  }
  const message = detail.data;
  return (
    <Section title="Delivery attempts" action={close}>
      <p className="text-sm text-fg-muted">
        Status: <strong className="text-fg">{message.status}</strong>
        {message.failure_reason ? ` · ${message.failure_reason}` : ""}
      </p>
      <ol className="mt-3 space-y-3">
        {message.attempts_history.map((attempt) => (
          <li
            key={attempt.attempt_number}
            className="rounded-control border border-border bg-surface-raised p-3 text-sm"
          >
            <p className="font-medium">
              Attempt {attempt.attempt_number}: {attempt.status}
            </p>
            <p className="text-fg-muted">
              Provider message ID: {attempt.provider_message_id ?? "none yet"}
            </p>
            {attempt.failure_code ? (
              <p>
                Failure: {attempt.failure_reason ?? attempt.failure_code} ({attempt.failure_class},{" "}
                {attempt.failure_code}){attempt.is_permanent ? " · permanent" : ""}
              </p>
            ) : null}
            {attempt.next_attempt_at ? (
              <p className="text-fg-muted">Next retry: {formatDateTime(attempt.next_attempt_at)}</p>
            ) : null}
            {attempt.events.length > 0 ? (
              <ul className="mt-2 list-disc pl-5">
                {attempt.events.map((event) => (
                  <li key={`${event.source}-${event.received_at}-${event.normalised_status}`}>
                    {formatDateTime(event.received_at)}: {event.normalised_status} ({event.source}
                    {event.applied ? "" : `, not applied: ${event.ignore_reason ?? "ignored"}`})
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ol>
    </Section>
  );
}

function Row({ row, onOpen }: { row: SmsMessageRow; onOpen: (id: string) => void }) {
  return (
    <tr>
      <td className={TD}>{formatDateTime(row.created_at)}</td>
      <td className={TD}>{row.masked_phone ?? "—"}</td>
      <td className={TD}>{row.is_simulated ? <SimulatedBadge /> : <LiveBadge />}</td>
      <td className={TD}>{row.status}</td>
      <td className={TD}>{row.attempts}</td>
      <td className={TD}>{row.provider_message_id ?? "—"}</td>
      <td className={TD}>{row.failure_reason ?? "—"}</td>
      <td className={TD}>
        <Button
          variant="secondary"
          size="sm"
          aria-label={`Attempts for message ${row.id}`}
          onClick={() => onOpen(row.id)}
        >
          Attempts
        </Button>
      </td>
    </tr>
  );
}

export function SmsLogPanel() {
  const [direction, setDirection] = useState<"outbound" | "inbound">("outbound");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useAdminSms({ direction, status: status || undefined, page });

  return (
    <div className="space-y-4">
      <Section title="SMS messages">
        <div className="mb-3 grid gap-3 sm:grid-cols-2">
          <FormField label="Direction">
            <Select
              value={direction}
              onChange={(e) => {
                setDirection(e.target.value as "outbound" | "inbound");
                setStatus("");
                setPage(1);
              }}
            >
              <option value="outbound">Outbound</option>
              <option value="inbound">Inbound</option>
            </Select>
          </FormField>
          <FormField label="Status">
            <Select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Any status</option>
              {(direction === "outbound"
                ? ["queued", "retrying", "accepted", "sent", "delivered", "undelivered", "failed"]
                : ["received"]
              ).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        <p className="mb-3 text-xs text-fg-muted">
          Numbers are masked and message text is never shown here.
        </p>
        {list.isPending ? <Loading label="messages" /> : null}
        {list.isError ? (
          <QueryProblem error={list.error} retry={() => void list.refetch()} />
        ) : null}
        {list.data && list.data.data.length === 0 ? (
          <p className="text-sm text-fg-muted">No SMS messages match.</p>
        ) : null}
        {list.data && list.data.data.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className={TABLE}>
                <thead>
                  <tr>
                    {[
                      "Created",
                      direction === "outbound" ? "Recipient" : "Sender",
                      "Mode",
                      "Status",
                      "Attempts",
                      "Provider message ID",
                      "Failure reason",
                    ].map((heading) => (
                      <th key={heading} scope="col" className={TH}>
                        {heading}
                      </th>
                    ))}
                    <th scope="col" className={TH}>
                      <span className="sr-only">Details</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.data.map((row) => (
                    <Row key={row.id} row={row} onOpen={setSelected} />
                  ))}
                </tbody>
              </table>
            </div>
            <Pager
              page={page}
              hasNext={list.data.pagination.has_next}
              hasPrev={list.data.pagination.has_prev}
              onPage={setPage}
            />
          </>
        ) : null}
      </Section>
      {selected ? <MessageDetail id={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}
