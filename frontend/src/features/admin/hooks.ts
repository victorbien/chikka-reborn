import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  adminApi,
  type AuditQuery,
  type RestrictionReason,
  type SmsQuery,
  type UsersQuery,
} from "@/features/admin/api";

export const adminKeys = {
  all: ["admin"] as const,
  dashboard: () => [...adminKeys.all, "dashboard"] as const,
  users: (query: UsersQuery) => [...adminKeys.all, "users", query] as const,
  user: (id: string) => [...adminKeys.all, "user", id] as const,
  sms: (query: SmsQuery) => [...adminKeys.all, "sms", query] as const,
  smsMessage: (id: string) => [...adminKeys.all, "sms-message", id] as const,
  providers: () => [...adminKeys.all, "providers"] as const,
  ai: () => [...adminKeys.all, "ai"] as const,
  audit: (query: AuditQuery) => [...adminKeys.all, "audit", query] as const,
};

const REFRESH_MS = 60_000;

export function useDashboard() {
  return useQuery({
    queryKey: adminKeys.dashboard(),
    queryFn: ({ signal }) => adminApi.dashboard(signal),
    refetchInterval: REFRESH_MS,
  });
}

export function useAdminUsers(query: UsersQuery) {
  return useQuery({
    queryKey: adminKeys.users(query),
    queryFn: ({ signal }) => adminApi.users(query, signal),
    placeholderData: keepPreviousData,
  });
}

export function useAdminUser(id: string | null) {
  return useQuery({
    queryKey: adminKeys.user(id ?? ""),
    queryFn: ({ signal }) => adminApi.user(id as string, signal),
    enabled: id !== null,
  });
}

function useUserMutation<V>(fn: (variables: V) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    // Account status feeds the user list, the detail panel, the dashboard and the audit log.
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}

export const useRestrictUser = () =>
  useUserMutation((v: { id: string; reason: RestrictionReason }) =>
    adminApi.restrict(v.id, v.reason),
  );
export const useReinstateUser = () => useUserMutation((id: string) => adminApi.reinstate(id));

export function useAdminSms(query: SmsQuery) {
  return useQuery({
    queryKey: adminKeys.sms(query),
    queryFn: ({ signal }) => adminApi.smsMessages(query, signal),
    placeholderData: keepPreviousData,
  });
}

export function useAdminSmsMessage(id: string | null) {
  return useQuery({
    queryKey: adminKeys.smsMessage(id ?? ""),
    queryFn: ({ signal }) => adminApi.smsMessage(id as string, signal),
    enabled: id !== null,
  });
}

export function useProviderOverview() {
  return useQuery({
    queryKey: adminKeys.providers(),
    queryFn: ({ signal }) => adminApi.providers(signal),
    refetchInterval: REFRESH_MS,
  });
}

export function useAiMetrics() {
  return useQuery({
    queryKey: adminKeys.ai(),
    queryFn: ({ signal }) => adminApi.aiMetrics(signal),
  });
}

export function useAuditLogs(query: AuditQuery) {
  return useQuery({
    queryKey: adminKeys.audit(query),
    queryFn: ({ signal }) => adminApi.auditLogs(query, signal),
    placeholderData: keepPreviousData,
  });
}
