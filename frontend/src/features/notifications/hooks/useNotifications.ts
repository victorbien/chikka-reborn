import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "@/features/notifications/api";
import { notificationKeys } from "@/features/notifications/query-keys";
import type { PreferencesUpdate } from "@/features/notifications/types";

const SAFETY_REFRESH_MS = 60_000;

/** The unread badge. Real-time events keep it current; the interval repairs a missed event. */
export function useUnreadCount(enabled = true) {
  return useQuery({
    queryKey: notificationKeys.unread(),
    queryFn: ({ signal }) => notificationsApi.unreadCount(signal),
    select: (data) => data.unread_count,
    refetchInterval: SAFETY_REFRESH_MS,
    enabled,
  });
}

export function useNotificationFeed(page: number, unreadOnly: boolean) {
  return useQuery({
    queryKey: notificationKeys.feed(page, unreadOnly),
    queryFn: ({ signal }) => notificationsApi.feed(page, unreadOnly, signal),
    placeholderData: keepPreviousData,
  });
}

function useRefreshAfter<TVariables, TData>(mutationFn: (variables: TVariables) => Promise<TData>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
  });
}

export function useMarkRead() {
  return useRefreshAfter((id: string) => notificationsApi.markRead(id));
}

export function useMarkAllRead() {
  return useRefreshAfter(() => notificationsApi.markAllRead());
}

export function useDismissNotification() {
  return useRefreshAfter((id: string) => notificationsApi.dismiss(id));
}

export function useNotificationPreferences() {
  return useQuery({
    queryKey: notificationKeys.preferences(),
    queryFn: ({ signal }) => notificationsApi.preferences(signal),
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: PreferencesUpdate) => notificationsApi.updatePreferences(update),
    onSuccess: (saved) => queryClient.setQueryData(notificationKeys.preferences(), saved),
  });
}
