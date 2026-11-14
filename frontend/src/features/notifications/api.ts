import { apiClient, type ApiClient } from "@/lib/api/client";
import { unwrap, type Envelope } from "@/lib/api/envelope";
import type {
  AppNotification,
  NotificationPage,
  NotificationPreferences,
  PreferencesUpdate,
} from "@/features/notifications/types";

const BASE = "/api/v1/notifications";
export const NOTIFICATION_PAGE_SIZE = 20;

export function createNotificationsApi(client: ApiClient = apiClient) {
  return {
    feed: (page: number, unreadOnly: boolean, signal?: AbortSignal) =>
      client.get<NotificationPage>(BASE, {
        signal,
        query: {
          page,
          page_size: NOTIFICATION_PAGE_SIZE,
          unread_only: unreadOnly ? "true" : undefined,
        },
      }),
    unreadCount: (signal?: AbortSignal) =>
      client
        .get<Envelope<{ unread_count: number }>>(`${BASE}/unread-count`, { signal })
        .then(unwrap),
    markRead: (id: string) =>
      client.post<Envelope<AppNotification>>(`${BASE}/${id}/read`, {}).then(unwrap),
    markAllRead: () =>
      client
        .post<Envelope<{ updated: number; unread_count: number }>>(`${BASE}/read-all`, {})
        .then(unwrap),
    dismiss: (id: string) =>
      client.post<Envelope<{ unread_count: number }>>(`${BASE}/${id}/dismiss`, {}).then(unwrap),
    preferences: (signal?: AbortSignal) =>
      client.get<Envelope<NotificationPreferences>>(`${BASE}/preferences`, { signal }).then(unwrap),
    updatePreferences: (update: PreferencesUpdate) =>
      client.put<Envelope<NotificationPreferences>>(`${BASE}/preferences`, update).then(unwrap),
  };
}

export const notificationsApi = createNotificationsApi();
