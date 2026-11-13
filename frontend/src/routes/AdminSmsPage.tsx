import { ErrorState } from "@/components/shared/ErrorState";
import { useMe } from "@/features/profile/hooks/useProfile";
import {
  CapabilitiesSection,
  MonitoringSection,
  ProvidersSection,
  SimulateReplySection,
  UnroutedSection,
} from "@/features/sms/admin/AdminSmsPanels";
import { useMonitoring } from "@/features/sms/admin/hooks";

/** SMS administration (Module J). The backend enforces the admin role; this page just does not
 *  pretend to be available to everyone else. Secrets are never loaded into the browser. */
export function AdminSmsPage() {
  const me = useMe();
  const monitoring = useMonitoring();
  if (me.isPending) {
    return (
      <p role="status" className="text-sm text-fg-muted">
        Loading…
      </p>
    );
  }
  if (me.data?.role !== "admin") {
    return <ErrorState kind="forbidden" message="Only administrators can manage SMS settings." />;
  }
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">SMS administration</h1>
      <MonitoringSection />
      <ProvidersSection />
      <CapabilitiesSection />
      <UnroutedSection />
      {monitoring.data?.mode === "simulation" ? <SimulateReplySection /> : null}
    </div>
  );
}
