import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminSmsApi, type RetrySettings } from "@/features/sms/admin/api";
import { smsKeys } from "@/features/sms/query-keys";

const key = (name: string) => [...smsKeys.admin(), name] as const;
const REFRESH_MS = 30_000;

export function useAdminProviders() {
  return useQuery({
    queryKey: key("providers"),
    queryFn: ({ signal }) => adminSmsApi.providers(signal),
  });
}

export function useAdminCapabilities() {
  return useQuery({
    queryKey: key("capabilities"),
    queryFn: ({ signal }) => adminSmsApi.capabilities(signal),
  });
}

export function useMonitoring() {
  return useQuery({
    queryKey: key("monitoring"),
    queryFn: ({ signal }) => adminSmsApi.monitoring(signal),
    refetchInterval: REFRESH_MS,
  });
}

export function useUnrouted() {
  return useQuery({
    queryKey: key("unrouted"),
    queryFn: ({ signal }) => adminSmsApi.unrouted(signal),
  });
}

function useAdminMutation<V, R>(fn: (variables: V) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: smsKeys.admin() }),
  });
}

export const useUpdateProvider = () =>
  useAdminMutation((v: { id: string; settings: RetrySettings }) =>
    adminSmsApi.updateProvider(v.id, v.settings),
  );
export const useActivateProvider = () =>
  useAdminMutation((v: { id: string; environment: string }) =>
    adminSmsApi.activate(v.id, v.environment),
  );
export const useSetPaused = () =>
  useAdminMutation((paused: boolean) => adminSmsApi.setPaused(paused));
export const useSimulateInbound = () =>
  useAdminMutation((v: Parameters<typeof adminSmsApi.simulateInbound>[0]) =>
    adminSmsApi.simulateInbound(v),
  );
