import { Bell } from "lucide-react";
import { Link } from "react-router-dom";
import { useUnreadCount } from "@/features/notifications/hooks/useNotifications";
import { paths } from "@/lib/paths";

/** Header bell with the unread count. It is a plain link to the notification centre, so it
 *  works with the keyboard and screen readers without extra widgets. */
export function NotificationBell() {
  const unread = useUnreadCount();
  const count = unread.data ?? 0;
  return (
    <Link
      to={paths.notifications}
      aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
      className="relative inline-flex size-11 items-center justify-center rounded-control hover:bg-surface-raised"
    >
      <Bell aria-hidden className="size-5" />
      {count > 0 ? (
        <span
          aria-hidden
          className="absolute right-1 top-1 min-w-5 rounded-full bg-accent px-1 text-center text-xs font-semibold text-accent-fg"
        >
          {count > 99 ? "99+" : count}
        </span>
      ) : null}
    </Link>
  );
}
