import { apiClient, type ApiClient } from "@/lib/api/client";
import type { HealthStatus } from "@/types/api";

export const healthQueryKey = ["system", "health"] as const;

export function fetchHealth(
  client: ApiClient = apiClient,
  signal?: AbortSignal,
): Promise<HealthStatus> {
  return client.get<HealthStatus>("/api/v1/health", { signal });
}
