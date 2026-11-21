import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import {
  RESTRICTION_REASONS,
  type AccountStatus,
  type AdminUserDetail,
  type RestrictionReason,
} from "@/features/admin/api";
import {
  formatDateTime,
  Loading,
  Pager,
  QueryProblem,
  Section,
  Stat,
  TABLE,
  TD,
  TH,
} from "@/features/admin/components/shared";
import {
  useAdminUser,
  useAdminUsers,
  useReinstateUser,
  useRestrictUser,
} from "@/features/admin/hooks";
import { toUserFacingError } from "@/lib/error-handling";

const searchSchema = z.object({
  q: z.string().trim().max(100, "Use 100 characters or fewer."),
  status: z.enum(["", "pending_verification", "active", "suspended"]),
});
type SearchInput = z.infer<typeof searchSchema>;

const STATUS_LABEL: Record<AccountStatus, string> = {
  pending_verification: "Awaiting email confirmation",
  active: "Active",
  suspended: "Suspended",
  deleted: "Deleted",
};

const REASON_LABEL: Record<RestrictionReason, string> = {
  abuse: "Abuse",
  spam: "Spam",
  fraud: "Fraud",
  security: "Security concern",
  other: "Other",
};

function UserDetailPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const detail = useAdminUser(id);
  const restrict = useRestrictUser();
  const reinstate = useReinstateUser();
  const [reason, setReason] = useState<RestrictionReason>("abuse");
  const [confirming, setConfirming] = useState(false);
  const mutationError = restrict.error ?? reinstate.error;

  const close = (
    <Button variant="ghost" size="sm" onClick={onClose}>
      Close
    </Button>
  );
  if (detail.isPending) {
    return (
      <Section title="Account details" action={close}>
        <Loading label="account" />
      </Section>
    );
  }
  if (detail.isError) {
    return (
      <Section title="Account details" action={close}>
        <QueryProblem error={detail.error} retry={() => void detail.refetch()} />
      </Section>
    );
  }
  const user: AdminUserDetail = detail.data;
  return (
    <Section title="Account details" action={close}>
      <p className="font-medium">{user.display_name ?? user.username ?? "Unnamed account"}</p>
      <p className="text-sm text-fg-muted">
        {user.masked_email ?? "No email"} · {user.masked_verified_phone ?? "No verified phone"} ·{" "}
        {user.role === "admin" ? "Administrator" : "User"} · {STATUS_LABEL[user.status]}
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Chikka messages sent" value={user.activity.chikka_messages_sent} />
        <Stat label="SMS sent" value={user.activity.sms_sent} />
        <Stat label="SMS received" value={user.activity.sms_received} />
        <Stat label="Conversations" value={user.activity.conversations} />
        <Stat label="AI requests" value={user.activity.ai_requests} />
        <Stat label="Open reports against" value={user.activity.open_reports_against} />
        <Stat label="Active sessions" value={user.activity.active_sessions} />
        <Stat label="Last seen" value={formatDateTime(user.last_seen_at)} />
      </dl>
      {user.credits.length > 0 ? (
        <p className="mt-3 text-sm">
          Credits:{" "}
          {user.credits
            .map(
              (c) =>
                `${c.ledger_type === "demo" ? "simulated" : "live"} ${c.balance_units} (${c.reserved_units} reserved)`,
            )
            .join(", ")}
        </p>
      ) : null}
      {mutationError ? (
        <FormAlert tone="error" className="mt-3">
          {toUserFacingError(mutationError).message}
        </FormAlert>
      ) : null}
      {user.role === "user" && user.status === "active" ? (
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <FormField label="Reason for restriction">
            <Select value={reason} onChange={(e) => setReason(e.target.value as RestrictionReason)}>
              {RESTRICTION_REASONS.map((r) => (
                <option key={r} value={r}>
                  {REASON_LABEL[r]}
                </option>
              ))}
            </Select>
          </FormField>
          <Button
            variant="destructive"
            disabled={restrict.isPending}
            onClick={() => setConfirming(true)}
          >
            Restrict account
          </Button>
          <ConfirmDialog
            open={confirming}
            onOpenChange={setConfirming}
            title="Restrict this account?"
            description="The person is signed out everywhere and cannot sign in until you lift the restriction. The action is recorded in the audit log."
            confirmLabel="Restrict account"
            destructive
            onConfirm={() => restrict.mutate({ id: user.id, reason })}
          />
        </div>
      ) : null}
      {user.status === "suspended" ? (
        <div className="mt-4">
          <Button
            variant="secondary"
            disabled={reinstate.isPending}
            onClick={() => reinstate.mutate(user.id)}
          >
            Lift restriction
          </Button>
        </div>
      ) : null}
    </Section>
  );
}

export function UsersPanel() {
  const [filters, setFilters] = useState<{ q: string; status: SearchInput["status"] }>({
    q: "",
    status: "",
  });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const form = useForm<SearchInput>({
    resolver: zodResolver(searchSchema),
    defaultValues: filters,
  });
  const users = useAdminUsers({
    q: filters.q || undefined,
    status: filters.status || undefined,
    page,
  });
  const { errors } = form.formState;

  return (
    <div className="space-y-4">
      <Section title="Accounts">
        <form
          className="mb-3 grid gap-3 sm:grid-cols-[1fr_14rem_auto] sm:items-end"
          role="search"
          onSubmit={form.handleSubmit((values) => {
            setFilters(values);
            setPage(1);
          })}
        >
          <FormField label="Search by name, username or email" error={errors.q?.message}>
            <Input type="search" {...form.register("q")} />
          </FormField>
          <FormField label="Status">
            <Select {...form.register("status")}>
              <option value="">Any status</option>
              <option value="active">Active</option>
              <option value="pending_verification">Awaiting email confirmation</option>
              <option value="suspended">Suspended</option>
            </Select>
          </FormField>
          <Button type="submit">Search</Button>
        </form>
        {users.isPending ? <Loading label="accounts" /> : null}
        {users.isError ? (
          <QueryProblem error={users.error} retry={() => void users.refetch()} />
        ) : null}
        {users.data && users.data.data.length === 0 ? (
          <p className="text-sm text-fg-muted">No accounts match. Try a different search.</p>
        ) : null}
        {users.data && users.data.data.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className={TABLE}>
                <thead>
                  <tr>
                    <th scope="col" className={TH}>
                      Account
                    </th>
                    <th scope="col" className={TH}>
                      Email
                    </th>
                    <th scope="col" className={TH}>
                      Role
                    </th>
                    <th scope="col" className={TH}>
                      Status
                    </th>
                    <th scope="col" className={TH}>
                      Last seen
                    </th>
                    <th scope="col" className={TH}>
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {users.data.data.map((user) => {
                    const name = user.display_name ?? user.username ?? "Unnamed account";
                    return (
                      <tr key={user.id}>
                        <td className={TD}>
                          {name}
                          {user.username ? (
                            <span className="block text-xs text-fg-muted">@{user.username}</span>
                          ) : null}
                        </td>
                        <td className={TD}>{user.masked_email ?? "—"}</td>
                        <td className={TD}>{user.role === "admin" ? "Administrator" : "User"}</td>
                        <td className={TD}>{STATUS_LABEL[user.status]}</td>
                        <td className={TD}>{formatDateTime(user.last_seen_at)}</td>
                        <td className={TD}>
                          <Button
                            variant="secondary"
                            size="sm"
                            aria-label={`View ${name}`}
                            onClick={() => setSelected(user.id)}
                          >
                            View
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pager
              page={page}
              hasNext={users.data.pagination.has_next}
              hasPrev={users.data.pagination.has_prev}
              onPage={setPage}
            />
          </>
        ) : null}
      </Section>
      {selected ? <UserDetailPanel id={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}
