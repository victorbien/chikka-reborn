import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { isApiError } from "@/lib/api/errors";
import { reportError } from "@/lib/error-handling";

const MAX_RETRIES = 2;

/** Retry only transient failures: network errors, 429 and 5xx. Never retry 4xx. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_RETRIES) return false;
  if (!isApiError(error)) return false;
  if (error.kind === "network") return true;
  return error.status === 429 || (error.status !== null && error.status >= 500);
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => reportError(error, "query"),
    }),
    mutationCache: new MutationCache({
      onError: (error) => reportError(error, "mutation"),
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: shouldRetry,
      },
      mutations: { retry: false },
    },
  });
}
