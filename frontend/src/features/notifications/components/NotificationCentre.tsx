import { Bell } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { NotificationItem, type NotificationKind } from "@/components/shared/NotificationItem";
import { Button } from "@/components/ui/button";
import { BrowserNotificationControl } from "@/features/notifications/components/BrowserNotificationControl";
import {
  useDismissNotification,
  useMarkAllRead,
  useMarkRead,
  useNotificationFeed,
  useUnreadCount,
} from "@/features/notifications/hooks/useNotifications";
import { notificationLink } from "@/features/notifications/links";
import type { AppNotification, NotificationType } from "@/features/notifications/types";
import { formatDateTime } from "@/lib/datetime";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";

const KIND: Record<NotificationType, NotificationKind> = {
  new_message: "info",
  sms_inbound: "info",
  sms_delivered: "success",
  sms_failed: "warning",
  contact_request: "info",
  contact_accepted: "success",
  low_balance: "warning",
  system: "info",
  security: "warning",
};

function Item({ notification }: { notification: AppNotification }) {
  const markRead = useMarkRead();
  const dismiss = useDismissNotification();
  const link = notificationLink(notification);
  return (
    <NotificationItem
      title={notification.title}
      description={notification.body}
      count={notification.occurrence_count}
      timestamp={formatDateTime(notification.created_at)}
      kind={KIND[notification.type]}
      isRead={notification.is_read}
      onMarkRead={() => markRead.mutate(notification.id)}
      actions={
        <>
          {link ? (
            <Button asChild size="sm" variant="secondary">
              <Link
                to={link}
                onClick={() => !notification.is_read && markRead.mutate(notification.id)}
              >
                Open
              </Link>
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Dismiss: ${notification.title}`}
            disabled={dismiss.isPending}
            onClick={() => dismiss.mutate(notification.id)}
          >
            Dismiss
          </Button>
        </>
      }
    />
  );
}

/** The notification centre: newest first, unread filter, mark one or all as read. */
export function NotificationCentre() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const feed = useNotificationFeed(page, unreadOnly);
  const unread = useUnreadCount();
  const markAll = useMarkAllRead();
  const unreadCount = unread.data ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            aria-pressed={unreadOnly}
            onClick={() => {
              setUnreadOnly((value) => !value);
              setPage(1);
            }}
          >
            {unreadOnly ? "Showing unread" : "Show unread only"}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={unreadCount === 0 || markAll.isPending}
            onClick={() => markAll.mutate()}
          >
            Mark all as read
          </Button>
          <Button asChild size="sm" variant="ghost">
            <Link to={paths.notificationSettings}>Settings</Link>
          </Button>
        </div>
      </div>
      <p role="status" className="text-sm text-fg-muted">
        {unreadCount === 0 ? "You are all caught up." : `${unreadCount} unread`}
      </p>

      <BrowserNotificationControl compact />

      {feed.isPending ? (
        <p role="status" className="text-sm text-fg-muted">
          Loading your notifications…
        </p>
      ) : null}
      {feed.isError ? (
        <ErrorState
          kind={toUserFacingError(feed.error).kind}
          message={toUserFacingError(feed.error).message}
          requestId={toUserFacingError(feed.error).requestId}
          onRetry={() => void feed.refetch()}
        />
      ) : null}
      {feed.data && feed.data.data.length === 0 ? (
        <EmptyState
          icon={Bell}
          title={unreadOnly ? "Nothing unread" : "No notifications yet"}
          description={
            unreadOnly
              ? "Everything has been read."
              : "New messages, contact requests and SMS updates will appear here."
          }
        />
      ) : null}
      {feed.data && feed.data.data.length > 0 ? (
        <>
          <ul aria-label="Notifications" className="space-y-2">
            {feed.data.data.map((notification) => (
              <Item key={notification.id} notification={notification} />
            ))}
          </ul>
          <nav aria-label="Notification pages" className="flex items-center justify-between">
            <Button
              variant="secondary"
              size="sm"
              disabled={!feed.data.pagination.has_prev}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
            >
              Newer
            </Button>
            <span className="text-xs text-fg-muted">
              Page {feed.data.pagination.page} · {feed.data.pagination.total} total
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={!feed.data.pagination.has_next}
              onClick={() => setPage((current) => current + 1)}
            >
              Older
            </Button>
          </nav>
        </>
      ) : null}
    </div>
  );
}
