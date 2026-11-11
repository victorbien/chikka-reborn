import { PageLoader } from "@/components/common/PageLoader";
import { ErrorState } from "@/components/shared/ErrorState";
import { toUserFacingError } from "@/lib/error-handling";
import { useHealth } from "@/hooks/useHealth";

/** Shows backend reachability. Exercises the API client, query layer and error handling. */
export function ApiStatusCard() {
  const { data, error, isPending, isError, refetch } = useHealth();

  if (isPending) return <PageLoader label="Checking the server" />;

  if (isError) {
    const friendly = toUserFacingError(error);
    return (
      <ErrorState
        kind={friendly.kind}
        message={friendly.message}
        requestId={friendly.requestId}
        onRetry={friendly.retryable ? () => void refetch() : undefined}
      />
    );
  }

  return (
    <dl className="grid grid-cols-2 gap-2 text-sm">
      <dt className="text-fg-muted">Server</dt>
      <dd>{data.status === "ok" ? "Online" : "Degraded"}</dd>
      <dt className="text-fg-muted">Environment</dt>
      <dd>{data.environment}</dd>
      <dt className="text-fg-muted">Database</dt>
      <dd>{data.database}</dd>
      <dt className="text-fg-muted">SMS mode</dt>
      <dd>{data.sms_mode === "simulation" ? "Simulation (no real SMS)" : "Live"}</dd>
      <dt className="text-fg-muted">Version</dt>
      <dd>{data.version}</dd>
    </dl>
  );
}
