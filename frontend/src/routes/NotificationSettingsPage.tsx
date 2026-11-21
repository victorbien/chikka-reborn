import { Link } from "react-router-dom";
import { NotificationPreferencesForm } from "@/features/notifications/components/NotificationPreferencesForm";
import { paths } from "@/lib/paths";

export function NotificationSettingsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Notification settings</h1>
        <Link to={paths.notifications} className="text-sm text-accent underline">
          Back to notifications
        </Link>
      </div>
      <NotificationPreferencesForm />
    </div>
  );
}
