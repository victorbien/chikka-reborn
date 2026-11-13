import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { LiveBadge, SimulatedBadge } from "@/components/shared/ChannelBadge";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import type { AdminProvider } from "@/features/sms/admin/api";
import {
  useActivateProvider,
  useAdminCapabilities,
  useAdminProviders,
  useMonitoring,
  useSetPaused,
  useSimulateInbound,
  useUnrouted,
  useUpdateProvider,
} from "@/features/sms/admin/hooks";
import {
  retrySettingsSchema,
  simulateReplySchema,
  type RetrySettingsInput,
  type SimulateReplyInput,
} from "@/features/sms/admin/schemas";
import { toUserFacingError } from "@/lib/error-handling";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="rounded-panel border border-border bg-surface p-4">
      <h2 className="mb-3 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Loading({ label }: { label: string }) {
  return (
    <p role="status" className="text-sm text-fg-muted">
      Loading {label}…
    </p>
  );
}

function QueryProblem({ error, retry }: { error: unknown; retry: () => void }) {
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

function RetrySettingsForm({ provider }: { provider: AdminProvider }) {
  const update = useUpdateProvider();
  const form = useForm<RetrySettingsInput>({
    resolver: zodResolver(retrySettingsSchema),
    defaultValues: {
      max_retry_attempts: provider.max_retry_attempts,
      retry_base_seconds: provider.retry_base_seconds,
      retry_cap_seconds: provider.retry_cap_seconds,
    },
  });
  const { errors } = form.formState;
  return (
    <form
      className="mt-3 grid gap-3 sm:grid-cols-3"
      onSubmit={form.handleSubmit((values) => {
        const parsed = retrySettingsSchema.parse(values);
        update.mutate({ id: provider.id, settings: parsed });
      })}
    >
      <FormField label="Maximum attempts" error={errors.max_retry_attempts?.message}>
        <Input type="number" inputMode="numeric" {...form.register("max_retry_attempts")} />
      </FormField>
      <FormField label="First wait (seconds)" error={errors.retry_base_seconds?.message}>
        <Input type="number" inputMode="numeric" {...form.register("retry_base_seconds")} />
      </FormField>
      <FormField label="Longest wait (seconds)" error={errors.retry_cap_seconds?.message}>
        <Input type="number" inputMode="numeric" {...form.register("retry_cap_seconds")} />
      </FormField>
      <div className="sm:col-span-3">
        <Button type="submit" variant="secondary" disabled={update.isPending}>
          Save retry settings
        </Button>
        {update.isError ? (
          <FormAlert tone="error" className="mt-2">
            {toUserFacingError(update.error).message}
          </FormAlert>
        ) : null}
        {update.isSuccess ? (
          <FormAlert tone="success" className="mt-2">
            Saved.
          </FormAlert>
        ) : null}
      </div>
    </form>
  );
}

function ActivateControl({ provider }: { provider: AdminProvider }) {
  const activate = useActivateProvider();
  const [environment, setEnvironment] = useState("");
  const live = provider.mode === "live";
  return (
    <div className="mt-3 space-y-2">
      {live ? (
        <FormField
          label="Type this environment's name to confirm live SMS"
          hint="Real messages will be sent to real phones."
        >
          <Input value={environment} onChange={(e) => setEnvironment(e.target.value)} />
        </FormField>
      ) : null}
      <Button
        variant={live ? "destructive" : "secondary"}
        disabled={activate.isPending || (live && environment.trim() === "")}
        onClick={() => activate.mutate({ id: provider.id, environment: environment.trim() })}
      >
        {live ? "Confirm and activate live SMS" : "Activate simulation"}
      </Button>
      {activate.isError ? (
        <FormAlert tone="error">{toUserFacingError(activate.error).message}</FormAlert>
      ) : null}
    </div>
  );
}

export function ProvidersSection() {
  const providers = useAdminProviders();
  return (
    <Section title="Providers">
      {providers.isPending ? (
        <Loading label="providers" />
      ) : providers.isError ? (
        <QueryProblem error={providers.error} retry={() => void providers.refetch()} />
      ) : (
        <ul className="space-y-4">
          {providers.data.map((provider) => (
            <li key={provider.id} className="rounded-control border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-medium">{provider.display_name}</h3>
                {provider.mode === "simulation" ? <SimulatedBadge /> : <LiveBadge />}
                {provider.is_active ? <span className="text-xs">Active</span> : null}
                {provider.is_running ? <span className="text-xs">Running</span> : null}
              </div>
              <dl className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
                <div>
                  <dt className="inline text-fg-muted">Credentials: </dt>
                  <dd className="inline">
                    {provider.credentials_configured ? "configured" : "not configured"}
                  </dd>
                </div>
                <div>
                  <dt className="inline text-fg-muted">Sender registration: </dt>
                  <dd className="inline">{provider.sender_registration_status}</dd>
                </div>
                <div>
                  <dt className="inline text-fg-muted">Sender numbers: </dt>
                  <dd className="inline">
                    {provider.sender_numbers.length ? provider.sender_numbers.join(", ") : "none"}
                  </dd>
                </div>
                {provider.live_confirmed_at ? (
                  <div>
                    <dt className="inline text-fg-muted">Live confirmed for: </dt>
                    <dd className="inline">{provider.live_confirmed_environment}</dd>
                  </div>
                ) : null}
              </dl>
              <RetrySettingsForm provider={provider} />
              {provider.is_running && !provider.is_active ? (
                <ActivateControl provider={provider} />
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export function MonitoringSection() {
  const monitoring = useMonitoring();
  const pause = useSetPaused();
  const percent = (value: number | null) =>
    value === null ? "no data yet" : `${Math.round(value * 100)}%`;
  return (
    <Section title="Delivery health (last 24 hours)">
      {monitoring.isPending ? (
        <Loading label="monitoring" />
      ) : monitoring.isError ? (
        <QueryProblem error={monitoring.error} retry={() => void monitoring.refetch()} />
      ) : (
        <div className="space-y-3 text-sm">
          <p>
            Running: {monitoring.data.provider} ({monitoring.data.mode}). Queue:{" "}
            {monitoring.data.queue_depth}. Delivered: {percent(monitoring.data.delivery_rate)}.
            Failed: {percent(monitoring.data.failure_rate)}.
          </p>
          <p>
            Unrouted replies: {monitoring.data.unrouted_inbound}. Callback failures:{" "}
            {monitoring.data.webhook_processing_failures}. Rejected signatures:{" "}
            {monitoring.data.webhook_signature_rejections}. Opt-outs: {monitoring.data.opt_outs}.
          </p>
          {monitoring.data.dispatch_paused_by_configuration_error ? (
            <FormAlert tone="error">
              Sending is paused because the provider rejected our configuration. Check credentials
              and sender settings.
            </FormAlert>
          ) : null}
          <Button
            variant={monitoring.data.outbound_paused ? "primary" : "secondary"}
            disabled={pause.isPending}
            onClick={() => pause.mutate(!monitoring.data.outbound_paused)}
          >
            {monitoring.data.outbound_paused ? "Resume sending" : "Pause all sending"}
          </Button>
          {monitoring.data.recent_failures.length > 0 ? (
            <table className="w-full text-left">
              <caption className="mb-1 text-left font-medium">Recent failed messages</caption>
              <thead>
                <tr className="text-fg-muted">
                  <th scope="col">Recipient</th>
                  <th scope="col">Status</th>
                  <th scope="col">Reason</th>
                  <th scope="col">Attempts</th>
                </tr>
              </thead>
              <tbody>
                {monitoring.data.recent_failures.map((row) => (
                  <tr key={row.message_id}>
                    <td>{row.masked_recipient}</td>
                    <td>
                      {row.status}
                      {row.is_simulated ? " (simulated)" : ""}
                    </td>
                    <td>{row.reason}</td>
                    <td>{row.attempts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-fg-muted">No failed messages.</p>
          )}
        </div>
      )}
    </Section>
  );
}

export function CapabilitiesSection() {
  const capabilities = useAdminCapabilities();
  return (
    <Section title="Country capabilities">
      {capabilities.isPending ? (
        <Loading label="capabilities" />
      ) : capabilities.isError ? (
        <QueryProblem error={capabilities.error} retry={() => void capabilities.refetch()} />
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-fg-muted">
              <th scope="col">Country</th>
              <th scope="col">Outbound</th>
              <th scope="col">Two-way</th>
              <th scope="col">Sender registration</th>
              <th scope="col">Verified</th>
            </tr>
          </thead>
          <tbody>
            {capabilities.data.map((row) => (
              <tr key={row.country_code}>
                <th scope="row">{row.country_name}</th>
                <td>{row.outbound_support.replace("_", " ")}</td>
                <td>{row.inbound_support.replace("_", " ")}</td>
                <td>
                  {row.registered_sender_required ? row.registered_sender_status : "not required"}
                </td>
                <td>{row.verified ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

export function UnroutedSection() {
  const unrouted = useUnrouted();
  return (
    <Section title="Replies that matched no conversation">
      {unrouted.isPending ? (
        <Loading label="replies" />
      ) : unrouted.isError ? (
        <QueryProblem error={unrouted.error} retry={() => void unrouted.refetch()} />
      ) : unrouted.data.data.length === 0 ? (
        <p className="text-sm text-fg-muted">None. Message text is never shown here.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {unrouted.data.data.map((row) => (
            <li key={row.id}>
              From {row.masked_sender} to {row.masked_platform_number}
              {row.is_simulated ? " (simulated)" : ""}, received{" "}
              {new Date(row.received_at).toLocaleString()}. Kept until{" "}
              {new Date(row.retained_until).toLocaleDateString()}.
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export function SimulateReplySection() {
  const simulate = useSimulateInbound();
  const form = useForm<SimulateReplyInput>({
    resolver: zodResolver(simulateReplySchema),
    defaultValues: { from_phone: "", to_number: "", body: "" },
  });
  const { errors } = form.formState;
  return (
    <Section title="Simulate a reply">
      <p className="mb-3 text-sm text-fg-muted">
        Sends a signed fake reply through the real webhook path. Simulation mode only. Use the
        sender number shown on the conversation&apos;s route.
      </p>
      <form className="space-y-3" onSubmit={form.handleSubmit((values) => simulate.mutate(values))}>
        <FormField label="From (the phone replying)" error={errors.from_phone?.message}>
          <Input {...form.register("from_phone")} />
        </FormField>
        <FormField label="To (our sender number)" error={errors.to_number?.message}>
          <Input {...form.register("to_number")} />
        </FormField>
        <FormField label="Reply text" error={errors.body?.message}>
          <Textarea {...form.register("body")} />
        </FormField>
        <Button type="submit" disabled={simulate.isPending}>
          Simulate reply
        </Button>
        {simulate.isError ? (
          <FormAlert tone="error">{toUserFacingError(simulate.error).message}</FormAlert>
        ) : null}
        {simulate.isSuccess ? (
          <FormAlert tone="success">
            {simulate.data.duplicate
              ? "That reply was already received. Nothing changed."
              : `Reply processed: ${simulate.data.routing_result ?? "pending"}.`}
          </FormAlert>
        ) : null}
      </form>
    </Section>
  );
}
