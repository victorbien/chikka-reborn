import { Link } from "react-router-dom";
import { LiveBadge, SimulatedBadge } from "@/components/shared/ChannelBadge";
import type { ProviderOverview, SmsModeStats } from "@/features/admin/api";
import {
  formatDateTime,
  formatRate,
  Loading,
  QueryProblem,
  Section,
  Stat,
  TABLE,
  TD,
  TH,
} from "@/features/admin/components/shared";
import { useDashboard, useProviderOverview } from "@/features/admin/hooks";
import { paths } from "@/lib/paths";

const HEALTH_LABEL: Record<ProviderOverview["health"]["health"], string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  paused: "Paused by an administrator",
  unavailable: "Unavailable",
};

function SmsStats({ title, stats }: { title: React.ReactNode; stats: SmsModeStats }) {
  return (
    <div>
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">{title}</h3>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat label="SMS sent" value={stats.sent} />
        <Stat label="SMS received" value={stats.received} />
        <Stat label="Failed SMS" value={stats.failed + stats.undelivered} />
        <Stat label="Delivered" value={stats.delivered} />
        <Stat label="In progress" value={stats.in_progress} />
        <Stat label="Delivery success rate" value={formatRate(stats.delivery_success_rate)} />
      </dl>
    </div>
  );
}

export function DashboardPanel() {
  const dashboard = useDashboard();
  if (dashboard.isPending) return <Loading label="dashboard" />;
  if (dashboard.isError) {
    return <QueryProblem error={dashboard.error} retry={() => void dashboard.refetch()} />;
  }
  const d = dashboard.data;
  return (
    <div className="space-y-4">
      <p className="text-xs text-fg-muted">
        Figures come from the database. Updated {formatDateTime(d.generated_at)}.
      </p>
      <Section title="People and conversations">
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Registered users" value={d.users.total_registered} />
          <Stat
            label="Active users"
            value={d.users.active_last_30d}
            hint={`${d.users.active_last_24h} in 24 hours, ${d.users.active_last_7d} in 7 days`}
          />
          <Stat label="Suspended accounts" value={d.users.suspended} />
          <Stat label="Conversations" value={d.conversations.total} />
          <Stat label="Chikka messages sent" value={d.messages.chikka_messages_sent} />
          <Stat
            label="AI requests"
            value={d.ai.total_requests}
            hint={`${d.ai.failed_requests} failed`}
          />
        </dl>
      </Section>
      <Section title="SMS">
        <div className="grid gap-4 md:grid-cols-2">
          <SmsStats title={<SimulatedBadge />} stats={d.sms.simulated} />
          <SmsStats title={<LiveBadge />} stats={d.sms.live} />
        </div>
        <p className="mt-2 text-xs text-fg-muted">
          Simulated and live traffic are counted separately. Sent means handed to the provider,
          which is not the same as delivered.
        </p>
      </Section>
      <Section title="Credit activity">
        {d.credits.length === 0 ? (
          <p className="text-sm text-fg-muted">No credit activity yet.</p>
        ) : (
          <table className={TABLE}>
            <thead>
              <tr>
                <th scope="col" className={TH}>
                  Ledger
                </th>
                <th scope="col" className={TH}>
                  Entries
                </th>
                <th scope="col" className={TH}>
                  Granted
                </th>
                <th scope="col" className={TH}>
                  Used
                </th>
                <th scope="col" className={TH}>
                  Refunded
                </th>
                <th scope="col" className={TH}>
                  Adjusted
                </th>
              </tr>
            </thead>
            <tbody>
              {d.credits.map((row) => (
                <tr key={row.ledger_type}>
                  <td className={TD}>
                    {row.ledger_type === "demo" ? "Simulated (demo) credits" : "Live credits"}
                  </td>
                  <td className={TD}>{row.transactions}</td>
                  <td className={TD}>{row.units_granted}</td>
                  <td className={TD}>{row.units_deducted}</td>
                  <td className={TD}>{row.units_refunded}</td>
                  <td className={TD}>{row.units_adjusted}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
      <ProvidersPanel />
    </div>
  );
}

export function ProvidersPanel() {
  const overview = useProviderOverview();
  const manage = (
    <Link className="text-sm text-accent underline" to={paths.adminSms}>
      Manage SMS settings
    </Link>
  );
  if (overview.isPending) {
    return (
      <Section title="Provider">
        <Loading label="provider status" />
      </Section>
    );
  }
  if (overview.isError) {
    return (
      <Section title="Provider">
        <QueryProblem error={overview.error} retry={() => void overview.refetch()} />
      </Section>
    );
  }
  const { health, configuration, capabilities } = overview.data;
  return (
    <Section title="Provider" action={manage}>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Health" value={HEALTH_LABEL[health.health]} />
        <Stat
          label="Mode"
          value={
            health.mode === "live" ? "Live" : health.mode === "simulation" ? "Simulation" : "—"
          }
        />
        <Stat label="Running provider" value={health.running_provider ?? "none"} />
        <Stat label="Queue" value={health.queue_depth} hint="messages waiting to send" />
        <Stat label="Delivery rate (24h)" value={formatRate(health.delivery_success_rate_24h)} />
        <Stat label="Callback failures (24h)" value={health.webhook_failures_24h} />
        <Stat label="Rejected signatures (24h)" value={health.webhook_signature_rejections_24h} />
        <Stat
          label="Credentials"
          value={health.credentials_configured ? "configured" : "not configured"}
          hint="Values are never shown"
        />
      </dl>
      {health.reasons.length > 0 ? (
        <ul className="mt-3 list-disc pl-5 text-sm">
          {health.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <h3 className="mt-4 text-sm font-semibold">Configuration</h3>
      <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Environment" value={configuration.app_env} />
        <Stat label="SMS mode setting" value={configuration.sms_provider_mode} />
        <Stat label="Live SMS confirmed" value={configuration.sms_live_confirmed ? "yes" : "no"} />
        <Stat label="AI provider" value={configuration.ai_provider_mode} />
        <Stat label="AI configured" value={configuration.ai_provider_configured ? "yes" : "no"} />
        <Stat label="Email provider" value={configuration.email_provider_mode} />
      </dl>
      <h3 className="mt-4 text-sm font-semibold">Country capabilities</h3>
      <table className={`${TABLE} mt-2`}>
        <thead>
          <tr>
            <th scope="col" className={TH}>
              Country
            </th>
            <th scope="col" className={TH}>
              Outbound
            </th>
            <th scope="col" className={TH}>
              Two-way
            </th>
            <th scope="col" className={TH}>
              Sender registration
            </th>
          </tr>
        </thead>
        <tbody>
          {capabilities.map((c) => (
            <tr key={c.country_code}>
              <td className={TD}>{c.country_name}</td>
              <td className={TD}>{c.outbound_support}</td>
              <td className={TD}>{c.inbound_support}</td>
              <td className={TD}>
                {c.registered_sender_required ? c.registered_sender_status : "not required"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}
