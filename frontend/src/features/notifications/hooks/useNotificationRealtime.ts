import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useNavigate, type NavigateFunction } from "react-router-dom";
import { notificationKeys } from "@/features/notifications/query-keys";
import { notificationLink } from "@/features/notifications/links";
import type { NotificationCreatedEvent } from "@/features/notifications/types";
import { paths } from "@/lib/paths";
import { showBrowserNotification } from "@/lib/browser-notifications";
import type { ServerEvent } from "@/lib/realtime/client";
import { useRealtimeEvents } from "@/lib/realtime/provider";

function isCreated(value: unknown): value is NotificationCreatedEvent {
  const candidate = value as NotificationCreatedEvent | null;
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    typeof candidate.notification?.id === "string" &&
    typeof candidate.unread_count === "number"
  );
}

/** Applies one real-time event: badge and feed first, then a browser notification when the
 *  server flagged it, the user allowed it and the tab is in the background. */
export function handleNotificationEvent(
  queryClient: QueryClient,
  navigate: NavigateFunction,
  event: ServerEvent,
): void {
  if (event.type === "ready") {
    void queryClient.invalidateQueries({ queryKey: notificationKeys.all });
    return;
  }
  if (event.type !== "notification.created" || !isCreated(event.data)) return;
  const { notification, browser, unread_count: unread } = event.data;
  queryClient.setQueryData(notificationKeys.unread(), { unread_count: unread });
  void queryClient.invalidateQueries({ queryKey: [...notificationKeys.all, "feed"] });
  if (browser) {
    showBrowserNotification({
      title: notification.title,
      body: notification.body,
      tag: notification.id,
      onOpen: () => navigate(notificationLink(notification) ?? paths.notifications),
    });
  }
}

/** Keeps the badge, the feed and browser notifications current. Nothing is invented client-side. */
export function useNotificationRealtime(): void {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  useRealtimeEvents((event) => handleNotificationEvent(queryClient, navigate, event));
}
