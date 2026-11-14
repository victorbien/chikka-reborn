import { useNotificationRealtime } from "@/features/notifications/hooks/useNotificationRealtime";

/** Renders nothing. Keeps the badge, the feed and browser notifications current on every page. */
export function NotificationRealtimeBridge() {
  useNotificationRealtime();
  return null;
}
