import { isApiError } from "@/lib/api/errors";

export interface UserFacingError {
  kind: "error" | "offline" | "forbidden";
  message: string;
  requestId?: string;
  retryable: boolean;
}

/** Convert any thrown value into a message that is safe to show to a user. */
export function toUserFacingError(error: unknown): UserFacingError {
  if (isApiError(error)) {
    const requestId = error.requestId ?? undefined;
    if (error.kind === "network") {
      return { kind: "offline", message: error.message, requestId, retryable: true };
    }
    if (error.status === 401 || error.status === 403) {
      return {
        kind: "forbidden",
        message: "You do not have permission to see this.",
        requestId,
        retryable: false,
      };
    }
    const serverFault = error.status !== null && error.status >= 500;
    return {
      kind: "error",
      message: serverFault ? "The server had a problem. Please try again shortly." : error.message,
      requestId,
      retryable: serverFault || error.status === 429,
    };
  }
  return {
    kind: "error",
    message: "Something unexpected happened. Please try again.",
    retryable: true,
  };
}

/** Central sink for errors; swap the body for a real reporter later. */
export function reportError(error: unknown, context: string): void {
  const requestId = isApiError(error) ? error.requestId : null;
  const name = error instanceof Error ? error.name : "UnknownError";
  // Deliberately omit messages and payloads: they may contain user content.
  console.error(`[${context}] ${name}`, requestId ? { requestId } : {});
}
