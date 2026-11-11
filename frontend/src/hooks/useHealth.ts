import { useQuery } from "@tanstack/react-query";
import { fetchHealth, healthQueryKey } from "@/services/health-service";

export function useHealth() {
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: ({ signal }) => fetchHealth(undefined, signal),
  });
}
