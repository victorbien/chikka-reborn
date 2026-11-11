import { useRouteError } from "react-router-dom";
import { ErrorState } from "@/components/shared/ErrorState";
import { reportError, toUserFacingError } from "@/lib/error-handling";
import { useEffect } from "react";

/** Router-level errorElement for loader/render failures. */
export function RouteErrorPage() {
  const error = useRouteError();
  useEffect(() => {
    reportError(error, "route");
  }, [error]);
  const friendly = toUserFacingError(error);
  return (
    <ErrorState
      kind={friendly.kind}
      message={friendly.message}
      requestId={friendly.requestId}
      onRetry={() => window.location.reload()}
    />
  );
}
