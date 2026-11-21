import { ErrorState } from "@/components/shared/ErrorState";
import { toUserFacingError } from "@/lib/error-handling";

/** Readable failure with a retry button, for any failed query. */
export function QueryError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const friendly = toUserFacingError(error);
  return (
    <ErrorState
      kind={friendly.kind}
      message={friendly.message}
      requestId={friendly.requestId}
      onRetry={onRetry}
    />
  );
}
