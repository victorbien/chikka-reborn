import { NavLink, Outlet } from "react-router-dom";
import { ErrorState } from "@/components/shared/ErrorState";
import { AiPanel } from "@/features/admin/components/AiPanel";
import { AuditPanel } from "@/features/admin/components/AuditPanel";
import { DashboardPanel } from "@/features/admin/components/DashboardPanel";
import { SmsLogPanel } from "@/features/admin/components/SmsLogPanel";
import { UsersPanel } from "@/features/admin/components/UsersPanel";
import { useMe } from "@/features/profile/hooks/useProfile";
import { paths } from "@/lib/paths";
import { cn } from "@/lib/utils";

const TABS = [
  { to: paths.admin, label: "Overview", end: true },
  { to: paths.adminUsers, label: "Users", end: false },
  { to: paths.adminMessages, label: "SMS messages", end: false },
  { to: paths.adminAi, label: "AI usage", end: false },
  { to: paths.adminAudit, label: "Audit log", end: false },
  { to: paths.adminSms, label: "SMS settings", end: false },
] as const;

/** Administration shell (Module J). The backend checks the role stored in the database on every
 *  request; this layout only avoids showing screens that would fail for everyone else. */
export function AdminLayout() {
  const me = useMe();
  if (me.isPending) {
    return (
      <p role="status" className="text-sm text-fg-muted">
        Loading…
      </p>
    );
  }
  if (me.data?.role !== "admin") {
    return <ErrorState kind="forbidden" message="Only administrators can open this area." />;
  }
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Administration</h1>
      <nav aria-label="Administration" className="flex flex-wrap gap-1">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              cn(
                "inline-flex min-h-11 items-center rounded-control px-3 text-sm font-medium hover:bg-surface-raised",
                isActive ? "bg-surface-raised text-accent" : "text-fg",
              )
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}

export const AdminOverviewPage = DashboardPanel;
export const AdminUsersPage = UsersPanel;
export const AdminMessagesPage = SmsLogPanel;
export const AdminAiPage = AiPanel;
export const AdminAuditPage = AuditPanel;
