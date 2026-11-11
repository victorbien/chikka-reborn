import { Laptop } from "lucide-react";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { FormAlert } from "@/components/common/FormAlert";
import { PageLoader } from "@/components/common/PageLoader";
import { Button } from "@/components/ui/button";
import {
  useRevokeOtherSessions,
  useRevokeSession,
  useSessions,
} from "@/features/auth/hooks/useAuth";
import { toUserFacingError } from "@/lib/error-handling";

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** Active sessions (FR-AUTH-014). */
export function SessionList() {
  const sessions = useSessions();
  const revoke = useRevokeSession();
  const revokeOthers = useRevokeOtherSessions();

  if (sessions.isPending) return <PageLoader label="Loading your sessions" />;
  if (sessions.isError) {
    const friendly = toUserFacingError(sessions.error);
    return (
      <ErrorState
        kind={friendly.kind}
        message={friendly.message}
        requestId={friendly.requestId}
        onRetry={() => void sessions.refetch()}
      />
    );
  }

  const others = sessions.data.filter((session) => !session.current);
  const mutationError = revoke.error ?? revokeOthers.error;

  return (
    <div className="space-y-3">
      {mutationError ? (
        <FormAlert tone="error">{toUserFacingError(mutationError).message}</FormAlert>
      ) : null}
      {revokeOthers.isSuccess ? (
        <FormAlert tone="success">{revokeOthers.data.message}</FormAlert>
      ) : null}
      <ul className="divide-y divide-border rounded-panel border border-border">
        {sessions.data.map((session) => (
          <li key={session.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
            <div className="flex items-center gap-3">
              <Laptop aria-hidden className="size-5 text-fg-muted" />
              <div>
                <p className="text-sm font-medium">
                  {session.device}
                  {session.current ? (
                    <span className="ml-2 rounded-full bg-accent px-2 py-0.5 text-xs text-accent-fg">
                      This device
                    </span>
                  ) : null}
                </p>
                <p className="text-xs text-fg-muted">
                  Last active{" "}
                  {dateFormat.format(new Date(session.last_active_at ?? session.created_at))}
                  {session.ip_prefix ? ` · network ${session.ip_prefix}` : ""}
                </p>
              </div>
            </div>
            {session.current ? null : (
              <Button
                variant="secondary"
                size="sm"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(session.id)}
                aria-label={`Sign out ${session.device}`}
              >
                Sign out
              </Button>
            )}
          </li>
        ))}
      </ul>
      {others.length === 0 ? (
        <EmptyState
          icon={Laptop}
          title="No other sessions"
          description="You are only signed in on this device."
        />
      ) : (
        <Button
          variant="secondary"
          disabled={revokeOthers.isPending}
          onClick={() => revokeOthers.mutate()}
        >
          {revokeOthers.isPending ? "Signing out…" : "Sign out all other devices"}
        </Button>
      )}
    </div>
  );
}
